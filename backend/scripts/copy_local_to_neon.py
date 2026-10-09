"""Copy the practices that have real users (and everything hanging off them) from the LOCAL dev
database into Neon, so existing Clerk accounts find their clinic on the deployed site.

Why: the deployed database starts EMPTY. A person who already has a Clerk account (and a clinic in your
local database) is signed in on the deployed site but has no user/practice row there, so the app treats
them as a brand-new organization. Copying their clinic across fixes that.

Run from backend/ (needs the LOCAL database in .env and Neon's DIRECT url):

    NEON_DIRECT_URL='postgresql://...@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require' python scripts/copy_local_to_neon.py
    NEON_DIRECT_URL=... APPLY=1 python scripts/copy_local_to_neon.py

Dry-run by default (prints what WOULD be copied). Insert-only (ON CONFLICT DO NOTHING), one transaction
(all or nothing), safe to re-run. Review the dry-run first: it writes patient and clinic data to Neon.

Scope rule: a row is copied only if every foreign key it holds points at a row that is itself copied, and
any table with a practice_id only keeps rows of the selected practices (= practices that have users). So
demo practices, platform-level rows (landing-chat conversations, sales leads) and telemetry stay behind.
"""
import asyncio
import os
import sys
import warnings

sys.path.insert(0, os.getcwd())   # run from backend/
warnings.filterwarnings("ignore")

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import create_async_engine

import src.models  # noqa: F401  (registers every table on Base.metadata)
from src.database import Base, engine as local_engine
from src.db_url import engine_config

APPLY = os.environ.get("APPLY") == "1"
NEON_URL = os.environ["NEON_DIRECT_URL"]

# Seeded by migrations / self-seeding, global, or noise that should not travel.
SKIP = {
    "alembic_version", "plans", "agent_costing",
    "llm_calls", "system_metric_buckets", "slow_query_log",   # dev telemetry
    "demo_requests", "sales_leads",                          # Aiaceone's own pipeline, not a clinic's
}
BATCH = 400

local_engine.echo = False


async def main():
    url, args = engine_config(NEON_URL)
    neon = create_async_engine(url, connect_args=args)

    tables = [t for t in Base.metadata.sorted_tables if t.name not in SKIP]
    copied: dict[str, set] = {}
    plan: list[tuple[str, int, int]] = []
    payload: dict[str, list[dict]] = {}

    async with local_engine.connect() as lc:
        selected = set((await lc.execute(text("select distinct practice_id from users"))).scalars().all())
        print(f"practices with users: {len(selected)}")
        for t in tables:
            rows = [dict(r._mapping) for r in (await lc.execute(select(t))).all()]
            keep = []
            has_practice = "practice_id" in t.c
            for r in rows:
                if t.name == "practices":
                    if r["id"] not in selected:
                        continue
                elif has_practice:
                    if r["practice_id"] is None or r["practice_id"] not in copied.get("practices", set()):
                        continue
                ok = True
                for fk in t.foreign_keys:
                    parent = fk.column.table.name
                    val = r.get(fk.parent.name)
                    if val is None or parent in SKIP:
                        continue
                    if parent not in copied or val not in copied[parent]:
                        ok = False
                        break
                if ok:
                    keep.append(r)
            pk = [c.name for c in t.primary_key.columns]
            if len(pk) == 1:
                copied[t.name] = {r[pk[0]] for r in keep}
            if rows or keep:
                plan.append((t.name, len(rows), len(keep)))
            payload[t.name] = keep

    print(f"\n{'table':28} {'local':>6} {'to copy':>8}")
    for name, total, keep in plan:
        if total:
            print(f"{name:28} {total:>6} {keep:>8}")
    print("\ntotal rows to copy:", sum(k for _, _, k in plan))

    if not APPLY:
        print("\n(dry run - nothing written. Re-run with APPLY=1 to copy.)")
        await neon.dispose()
        return

    inserted: dict[str, int] = {}
    async with neon.begin() as nc:
        for t in tables:
            rows = payload.get(t.name) or []
            n = 0
            for i in range(0, len(rows), BATCH):
                res = await nc.execute(pg_insert(t).values(rows[i:i + BATCH]).on_conflict_do_nothing())
                n += res.rowcount if res.rowcount and res.rowcount > 0 else 0
            if rows:
                inserted[t.name] = n
    print("\ninserted into Neon:")
    for k, v in inserted.items():
        print(f"  {k:28} {v}")
    async with neon.connect() as nc:
        print("\nNeon now: practices =", (await nc.execute(text("select count(*) from practices"))).scalar_one(),
              "| users =", (await nc.execute(text("select count(*) from users"))).scalar_one(),
              "| patients =", (await nc.execute(text("select count(*) from patients"))).scalar_one())
    await neon.dispose()


asyncio.run(main())
