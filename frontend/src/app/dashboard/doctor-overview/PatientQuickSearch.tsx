import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SearchIcon, UserCircleIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { DASHBOARD_ROUTES } from "../constants/routes";

function highlight(text: string, query: string) {
  const trimmed = query.trim();
  if (!trimmed) return text;
  const idx = text.toLowerCase().indexOf(trimmed.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span className="bg-teal-600/15 text-teal-700">{text.slice(idx, idx + trimmed.length)}</span>
      {text.slice(idx + trimmed.length)}
    </>
  );
}

export function PatientQuickSearch() {
  const { authedFetch } = usePlan();
  const { patients } = usePatients(authedFetch);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const blurTimer = useRef<number | null>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients.slice(0, 6);
    return patients.filter((p) =>
      p.name.toLowerCase().includes(q) ||
      p.phone.toLowerCase().includes(q) ||
      p.email.toLowerCase().includes(q)
    ).slice(0, 7);
  }, [patients, query]);

  function go(id: string) {
    setOpen(false);
    setQuery("");
    navigate(DASHBOARD_ROUTES.patientDetail(id));
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-2 rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 shadow-[0_2px_10px_rgba(15,23,42,0.04)] transition-colors focus-within:border-teal-600/40">
        <SearchIcon className="h-4 w-4 shrink-0 text-ink-muted" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            blurTimer.current = window.setTimeout(() => setOpen(false), 150);
          }}
          placeholder="Search patients (name, phone, email)…"
          className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />
      </div>

      {open && query.trim() !== "" &&
      <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-xl border border-sand-200 bg-white shadow-[0_10px_32px_rgba(15,23,42,0.16)]">
          {results.length === 0 ?
          <p className="px-4 py-3 text-sm text-ink-muted">No patients match &ldquo;{query}&rdquo;.</p> :

          results.map((p) =>
          <button
            key={p.id}
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => go(p.id)}
            className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-sand-100/60">

              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sand-200 text-xs font-bold text-ink-soft">
                {p.initial}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-ink">{highlight(p.name, query)}</span>
                <span className="block truncate text-xs text-ink-muted">
                  {p.procedures[0] || p.chiefComplaint || "No procedures yet"}
                </span>
              </span>
              <UserCircleIcon className="h-4 w-4 shrink-0 text-ink-muted/60" />
            </button>
        )}
        </div>
      }
    </div>
  );
}