"""
Seed script — realistic inbound leads for practices that have no patients.

The demo practice started life with an inventory catalogue but no people, so
the funnel page opened on an empty chart and the real question ("does the
funnel actually narrow the way a clinic's does?") could not be answered
locally. This fills each empty practice with a plausible lead pipeline.

Design notes:
  * Idempotent, keyed on (practice_id, phone). Phone is the durable business
    identity for a lead, so re-running never duplicates and never overwrites
    real staff edits. This only holds because each practice is generated from
    a deterministic RNG seeded with (practice_id, per_practice): a re-run
    redraws the *same* phones, finds them present, and inserts nothing. A
    non-deterministic generator would append a fresh batch on every run.
  * Deliberately seeds stages across the WHOLE lifecycle, not just `inquiry`.
    A funnel where everything sits in one stage tests nothing.
  * `qualification` uses the exact shape LeadQualificationService writes, so
    the score badges in the dashboard read the same for seeded and live leads.
  * Only touches practices with 0 patients. A practice that has real patients
    is never modified - this must not touch production-like data.

Usage:
    python scripts/seed_leads.py
    python scripts/seed_leads.py --per-practice 25
    python scripts/seed_leads.py --practice-email a@b.com
    python scripts/seed_leads.py --dry-run
"""

import argparse
import asyncio
import logging
import random
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text

from src.database import async_session_factory
from src.models.patient import Patient, PatientLifecycleStage
from src.models.practice import Practice


# Pr practices with nobody in them yet. Anything not listed here has real
# patients and is left alone.
EMPTY_PRACTICE_EMAILS = [
    "demo@aesthetixai.com",
    "coastalplastic.demo@gmail.com",
    "hello@chenaesthetics.demo",
    "contact@lakesidesurgical.demo",
    "usageforworking@gmail.com",
]

# A real plastic-surgery funnel is heavily top-of-funnel weighted and loses
# people at every step, so the distribution below mirrors what an aesthetic
# clinic actually sees over ~6 weeks rather than being uniform.
STAGE_MIX = [
    (PatientLifecycleStage.INQUIRY, 7),
    (PatientLifecycleStage.CONTACTED, 4),
    (PatientLifecycleStage.CONSULT_SCHEDULED, 3),
    (PatientLifecycleStage.CONSULT_COMPLETED, 2),
    (PatientLifecycleStage.TREATMENT_PLANNED, 2),
    (PatientLifecycleStage.PATIENT, 1),
    (PatientLifecycleStage.LOST, 1),
]

PROCEDURES = [
    ("Rhinoplasty", "wants to address a dorsal hump and breathing difficulty"),
    ("Breast augmentation", "wants volume restored after two pregnancies"),
    ("Liposuction", "asking about stubborn abdominal and flank fat"),
    ("Facelift", "wants jawline definition ahead of a wedding"),
    ("Hair transplant", "wants density back in the crown area"),
    ("PRP hair treatment", "early-stage thinning, wants a non-surgical option"),
    ("Botox and fillers", "first-time, wants subtle natural results"),
    ("Tummy tuck", "post-pregnancy loose skin and separated muscles"),
    ("Mole removal", "concerned about a changing lesion on her back"),
    ("Skin resurfacing", "sun damage and uneven texture on the cheeks"),
    ("Gynecomastia", "wants chest contour reduced"),
    ("Eyelid surgery", "upper lids hooding her vision when she drives"),
    ("Ear reshaping", "protruding ears, has avoided photos for years"),
    ("Body contouring after weight loss", "loose skin after a 60 lb loss"),
    ("Cheek fillers", "wants volume lost to age, wants to look rested"),
    ("Neck lift", "wants the neck lines gone before a family event"),
    ("Arm lift", "loose upper arms after weight loss"),
    ("Lip augmentation", "wants fuller lips, had a filler elsewhere before"),
    ("Acne scar treatment", "pitted scars on both cheeks"),
    ("Skin cancer screening", "wants a mole checked, referred by his GP"),
]

SOURCES = [
    ("whatsapp", 30),
    ("instagram", 22),
    ("google", 20),
    ("website", 14),
    ("referral", 9),
    ("facebook", 5),
]

BUDGET_SIGNALS = ["low", "medium", "high", "unknown"]
URGENCIES = ["immediate", "within_month", "just_browsing", "unknown"]

FIRST_NAMES = [
    "Amelia", "Olivia", "Sophia", "Isabella", "Mia", "Charlotte", "Ava", "Emily",
    "Harper", "Ella", "Grace", "Chloe", "Zoe", "Lily", "Hannah", "Nora",
    "Layla", "Aria", "Priya", "Fatima", "Yasmin", "Omar", "Daniel", "Marcus",
    "James", "Michael", "David", "Joseph", "Thomas", "Andrew", "Robert",
    "Daniela", "Sofia", "Camila", "Valentina", "Mariana", "Elena", "Ana",
]
LAST_NAMES = [
    "Anderson", "Baker", "Carter", "Delgado", "Ellis", "Foster", "Garcia",
    "Hughes", "Ibrahim", "Jensen", "Kaur", "Lopez", "Mitchell", "Nakamura",
    "Okafor", "Patel", "Quinn", "Ramirez", "Singh", "Thompson", "Ueda",
    "Vasquez", "Whitfield", "Xu", "Young", "Zimmerman", "Bennett", "Coleman",
    "Doyle", "Emerson", "Fitzgerald", "Granger", "Holloway", "Ingram",
]

LANGUAGES = ["en", "es", "ar", "hi", "zh", "fr", "pt"]
GENDERS = ["female", "male", "other"]
LOST_REASONS = [
    "price too high after quote",
    "booked with another clinic",
    "not medically suitable",
    "no longer interested",
    "timing - postponed to next year",
]

# Fixed shuffle size for the stage ladder, so its prefix (and therefore the
# stage already assigned to each seeded lead) never depends on --per-practice.
_LADDER_POOL_SIZE = 400


def _weighted(rng: random.Random, options: list[tuple[object, int]]) -> object:
    return rng.choices([o for o, _ in options], weights=[w for _, w in options], k=1)[0]


def _phone(rng: random.Random) -> str:
    return f"+1{rng.choice([212, 305, 310, 404, 415, 512, 617, 702, 713, 858])}" \
           f"{rng.randint(200, 999)}{rng.randint(1000, 9999)}"


def _build_stage_ladder(rng: random.Random, count: int) -> list[PatientLifecycleStage]:
    """Fill `count` stages from STAGE_MIX, spreading the weighted mix.

    The pool is built at a fixed size from repeated *weighted* cycles and
    shuffled once, then truncated. Two things this has to get right:

    * The repeat must re-add the whole weighted cycle. Repeating the bare
      stage list instead adds one of each stage per pass, which dilutes the
      weights (a 7/4/3/2/2/1/1 mix turns into ~62/59/58/57/57/56/56) and
      quietly flattens the funnel into a near-uniform one.
    * The pool must not be sized to `count`, or the shuffle would depend on
      the requested total and `--per-practice 25` would re-stage the 20 leads
      that already exist.
    """
    cycle: list[PatientLifecycleStage] = []
    for stage, weight in STAGE_MIX:
        cycle.extend([stage] * weight)

    pool: list[PatientLifecycleStage] = []
    while len(pool) < _LADDER_POOL_SIZE:
        pool.extend(cycle)
    rng.shuffle(pool)
    return pool[:count]


def _qualification(rng: random.Random, procedure: str, stage: PatientLifecycleStage) -> dict:
    """Same shape LeadQualificationService produces."""
    depth = {
        PatientLifecycleStage.INQUIRY: rng.randint(5, 30),
        PatientLifecycleStage.CONTACTED: rng.randint(20, 45),
        PatientLifecycleStage.CONSULT_SCHEDULED: rng.randint(40, 65),
        PatientLifecycleStage.CONSULT_COMPLETED: rng.randint(55, 80),
        PatientLifecycleStage.TREATMENT_PLANNED: rng.randint(70, 90),
        PatientLifecycleStage.PATIENT: rng.randint(80, 98),
        PatientLifecycleStage.LOST: rng.randint(5, 35),
    }[stage]
    return {
        "interested_procedure": procedure,
        "budget_signal": rng.choice(BUDGET_SIGNALS),
        "urgency": rng.choice(URGENCIES),
        "score": depth,
        "summary": f"Inbound lead interested in {procedure.lower()}.",
    }


async def _empty_practice_ids(db) -> list[tuple[str, str]]:
    rows = await db.execute(
        text("""
            SELECT p.id::text, p.email
            FROM practices p
            WHERE NOT EXISTS (SELECT 1 FROM patients pt WHERE pt.practice_id = p.id)
            ORDER BY p.name
        """)
    )
    return [(r[0], r[1]) for r in rows.fetchall()]


async def seed(per_practice: int, only_email: str | None, dry_run: bool) -> None:
    async with async_session_factory() as db:
        if only_email:
            found = await db.execute(
                text("SELECT id::text, email FROM practices WHERE email = :e"), {"e": only_email}
            )
            targets = found.fetchall()
            if not targets:
                raise SystemExit(f"No practice found with email {only_email!r}")
        else:
            targets = await _empty_practice_ids(db)

        if not targets:
            print("No empty practices found - nothing to do.")
            return

        total_new = 0
        for practice_id, email in targets:
            name_row = await db.execute(
                text("SELECT name FROM practices WHERE id = :i"), {"i": practice_id}
            )
            practice_name = name_row.scalar_one()

            existing = await db.execute(
                text("SELECT phone FROM patients WHERE practice_id = :i"),
                {"i": practice_id},
            )
            existing_phones = {r[0] for r in existing.fetchall()}

            # Each lead is a stable SLOT, generated from (practice_id, slot
            # index) rather than from a running stream. That gives two things
            # a single batch seed cannot:
            #   * a re-run redraws identical phones, so the phone key skips
            #     them and nothing is inserted, and
            #   * raising --per-practice from 20 to 25 adds exactly the 5 new
            #     slots instead of a whole fresh batch.
            # A single RNG seeded with the batch size would break the first
            # (different size => different stream) and a global RNG would
            # break both.
            stages = _build_stage_ladder(random.Random(f"ladder:{practice_id}"), per_practice)
            new_rows: list[dict] = []
            skipped = 0

            for slot, stage in enumerate(stages):
                rng = random.Random(f"lead:{practice_id}:{slot}")

                # Draw the ENTIRE row before testing the phone key. The
                # duplicate check must not change how much of the RNG stream
                # this iteration consumes: if it did, a re-run would consume a
                # different number of draws than the original run, the
                # generator would desynchronise, and every later phone would
                # differ - turning "idempotent" into "appends 20 more leads
                # per run" for every lead that follows the first collision.
                procedure, complaint = rng.choice(PROCEDURES)
                phone = _phone(rng)
                first = rng.choice(FIRST_NAMES)
                last = rng.choice(LAST_NAMES)
                age = rng.randint(21, 68)
                dob = date.today() - timedelta(days=age * 365 + rng.randint(0, 364))
                # Leads trickle in over the last ~6 weeks, oldest first.
                age_days = rng.randint(0, 41)
                email_suffix = rng.randint(10, 99)
                gender = rng.choice(GENDERS)
                language = rng.choice(LANGUAGES)
                source = _weighted(rng, SOURCES)
                qualification = _qualification(rng, procedure, stage)
                lost_reason = (
                    LOST_REASONS[rng.randrange(len(LOST_REASONS))]
                    if stage == PatientLifecycleStage.LOST else None
                )
                updated_days = max(0, age_days - rng.randint(0, 5))

                if phone in existing_phones:
                    skipped += 1
                    continue
                existing_phones.add(phone)

                new_rows.append({
                    "practice_id": practice_id,
                    "first_name": first,
                    "last_name": last,
                    "phone": phone,
                    "email": f"{first.lower()}.{last.lower()}{email_suffix}@example.com",
                    "date_of_birth": dob,
                    "gender": gender,
                    "preferred_language": language,
                    "source": source,
                    "chief_complaint": complaint,
                    "lifecycle_stage": stage,
                    "qualification": qualification,
                    "lost_reason": lost_reason,
                    "needs_surgery": stage in (
                        PatientLifecycleStage.TREATMENT_PLANNED, PatientLifecycleStage.PATIENT,
                    ),
                    "portal_enabled": False,
                    "is_archived": False,
                    "created_at": datetime.now(timezone.utc) - timedelta(days=age_days),
                    "updated_at": datetime.now(timezone.utc) - timedelta(days=updated_days),
                })

            verb = "would insert" if dry_run else "inserted"
            print(f"[{practice_name} <{email}>] "
                  f"{verb} {len(new_rows)} leads, skipped {skipped} duplicate phone(s)")

            if new_rows and not dry_run:
                # ORM insert, not raw SQL: Patient has ~10 NOT NULL columns
                # whose default is a Python-side callable, and a raw INSERT
                # would bypass every one of them and violate NOT NULL.
                for row in new_rows:
                    row["practice_id"] = UUID(row["practice_id"])
                    row["lifecycle_stage"] = PatientLifecycleStage(row["lifecycle_stage"])
                    db.add(Patient(**row))
                await db.commit()
                total_new += len(new_rows)

        if dry_run:
            await db.rollback()
            print(f"\nDRY RUN - rolled back. {total_new} leads would have been created.")
        else:
            print(f"\nDone. {total_new} leads created across {len(targets)} practice(s).")


def main() -> None:
    logging.disable(logging.INFO)
    parser = argparse.ArgumentParser(description="Seed realistic inbound leads into empty practices.")
    parser.add_argument(
        "--per-practice", type=int, default=20,
        help="Leads per empty practice (default 20).",
    )
    parser.add_argument(
        "--practice-email", default=None,
        help="Seed only this practice email (must still be empty).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be inserted without committing.",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.per_practice, args.practice_email, args.dry_run))


if __name__ == "__main__":
    main()
