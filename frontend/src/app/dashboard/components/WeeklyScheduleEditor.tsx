import { useState } from "react";
import { CalendarDaysIcon } from "lucide-react";

export type WorkSchedule = Record<string, Array<{ start: string; end: string }>>;

const DAYS: Array<{ key: string; label: string }> = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
];

// Shared weekly schedule editor for staff (doctors + receptionists). Produces
// the same shape the backend uses everywhere — Doctor.working_hours /
// User.work_schedule: {"mon": [{"start": "09:00", "end": "17:00"}], ...}.
// Multi-range days are collapsed to their first range; the backend and the
// Owner's late view only need the earliest start / latest end anyway.
export function WeeklyScheduleEditor({
  value,
  onChange,
}: {
  value: WorkSchedule;
  onChange: (next: WorkSchedule) => void;
}) {
  const [draft, setDraft] = useState<WorkSchedule>(() => normalize(value));

  function normalize(input: WorkSchedule): WorkSchedule {
    const out: WorkSchedule = {};
    for (const { key } of DAYS) {
      const ranges = input?.[key];
      const first = Array.isArray(ranges) ? ranges[0] : undefined;
      if (first && typeof first?.start === "string") {
        out[key] = [{ start: first.start, end: typeof first.end === "string" ? first.end : "" }];
      }
    }
    return out;
  }

  function enabled(day: string) {
    return Boolean(draft[day]);
  }

  function setRange(day: string, start: string, end: string) {
    const next = { ...draft };
    if (start || end) next[day] = [{ start, end }];
    else delete next[day];
    setDraft(next);
    onChange(next);
  }

  return (
    <div className="space-y-2">
      {DAYS.map((d) => {
        const on = enabled(d.key);
        return (
          <div key={d.key} className="flex flex-wrap items-center gap-3 rounded-2xl border border-sand-200 bg-white px-4 py-2.5">
            <button
              type="button"
              onClick={() => {
                if (on) {
                  const next = { ...draft };
                  delete next[d.key];
                  setDraft(next);
                  onChange(next);
                } else {
                  const next = { ...draft, [d.key]: [{ start: "09:00", end: "17:00" }] };
                  setDraft(next);
                  onChange(next);
                }
              }}
              className={`flex h-7 w-11 items-center justify-center rounded-full text-[13px] font-semibold transition-colors ${
                on ? "bg-teal-600 text-white" : "bg-sand-100 text-ink-soft"
              }`}>
              {d.label}
            </button>
            {on && (
              <div className="flex items-center gap-2 text-sm">
                <input
                  type="time"
                  value={draft[d.key]?.[0]?.start ?? ""}
                  onChange={(e) => setRange(d.key, e.target.value, draft[d.key]?.[0]?.end ?? "")}
                  className="rounded-xl border border-sand-200 bg-canvas px-2.5 py-1.5 text-sm font-medium text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white"
                />
                <span className="text-ink-muted">to</span>
                <input
                  type="time"
                  value={draft[d.key]?.[0]?.end ?? ""}
                  onChange={(e) => setRange(d.key, draft[d.key]?.[0]?.start ?? "", e.target.value)}
                  className="rounded-xl border border-sand-200 bg-canvas px-2.5 py-1.5 text-sm font-medium text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white"
                />
              </div>
            )}
          </div>
        );
      })}
      <p className="flex items-center gap-1.5 text-xs text-ink-muted">
        <CalendarDaysIcon className="h-3.5 w-3.5" />
        These are the days and times you work each week — the clinic uses them to see when you&apos;re in and how late arrivals are.
      </p>
    </div>
  );
}