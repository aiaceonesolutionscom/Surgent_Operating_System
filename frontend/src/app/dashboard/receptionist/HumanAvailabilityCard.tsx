import { useEffect, useState } from "react";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { getHumanAvailability, saveHumanAvailability, type HumanAvailabilityResponse } from "../../../api/entities";

const DAYS: { value: number; label: string }[] = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" }
];

// When the AI receptionist's escalation tools can honestly tell a patient
// "connecting you with our team now" versus "the team will follow up when
// they reopen" — see backend/src/services/ai_receptionist/human_availability_service.py
// and its use in inbound_service.py's request_human_handoff /
// request_refund_or_cancellation tools.
export function HumanAvailabilityCard() {
  const { authedFetch, role } = usePlan();
  const canEdit = role === "owner";
  const [data, setData] = useState<HumanAvailabilityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("18:00");
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    getHumanAvailability(authedFetch)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        setStart(response.start);
        setEnd(response.end);
        setDays(response.days);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const toggleDay = (value: number) => {
    setDays((current) => (current.includes(value) ? current.filter((d) => d !== value) : [...current, value].sort()));
  };

  const save = async () => {
    if (!authedFetch || days.length === 0) return;
    setSaving(true);
    try {
      const response = await saveHumanAvailability(authedFetch, { start, end, days });
      setData(response);
      setFlash("Saved — the AI receptionist now checks this before promising a human is available.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      setFlash(detail ? `Couldn't save: ${detail}` : "Couldn't save — try again.");
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    "w-full rounded-xl border border-sand-200 bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-teal-500/40 disabled:bg-sand-50 disabled:text-ink-muted";

  return (
    <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-ink">Front-desk support hours</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            When a patient asks for a human, or wants a refund/cancellation, the AI checks this before saying
            anything — it never promises "connecting you now" when nobody's actually there.
          </p>
        </div>
        {data && (
          <span
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold ${
              data.available_now ? "border border-teal-500 bg-teal-50 text-teal-700" : "border border-amber-200 bg-amber-50 text-amber-700"
            }`}>
            {data.status_label}
          </span>
        )}
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-ink-muted">Loading…</p>
      ) : (
        <div className="mt-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs font-semibold text-ink-soft">Team available from</span>
              <input type="time" value={start} disabled={!canEdit} onChange={(e) => setStart(e.target.value)} className={`mt-1 ${inputClass}`} />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-ink-soft">Until</span>
              <input type="time" value={end} disabled={!canEdit} onChange={(e) => setEnd(e.target.value)} className={`mt-1 ${inputClass}`} />
            </label>
          </div>

          <div className="mt-4">
            <span className="text-xs font-semibold text-ink-soft">Working days</span>
            <div className="mt-2 flex flex-wrap gap-2">
              {DAYS.map(({ value, label }) => {
                const active = days.includes(value);
                return (
                  <button
                    key={value}
                    type="button"
                    disabled={!canEdit}
                    onClick={() => toggleDay(value)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                      active ? "border-teal-500 bg-teal-50 text-teal-700" : "border-sand-200 text-ink-soft hover:border-teal-300 hover:text-teal-700"
                    }`}>
                    {label}
                  </button>
                );
              })}
            </div>
            <p className="mt-1.5 text-[11px] text-ink-muted">In your practice's own time zone{data ? ` (${data.timezone})` : ""} — not the patient's.</p>
          </div>

          {canEdit && (
            <button
              onClick={() => void save()}
              disabled={saving || days.length === 0}
              className="mt-4 flex items-center gap-1.5 rounded-full bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-60">
              {saving ? <RefreshCwIcon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />} Save
            </button>
          )}
          {!canEdit && <p className="mt-4 text-xs text-ink-muted">Read-only for you — only the practice owner can change support hours.</p>}
          {flash && <p className="mt-3 text-xs font-semibold text-teal-700">{flash}</p>}
        </div>
      )}
    </div>
  );
}
