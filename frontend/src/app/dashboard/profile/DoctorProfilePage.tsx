import React, { useEffect, useMemo, useState } from "react";
import { BadgeCheckIcon, CalendarDaysIcon, MailIcon, PhoneIcon, PlusIcon, StethoscopeIcon, TrashIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import {
  getMyDoctor,
  listMyAttendance,
  updateMyDoctorProfile,
  type AttendanceRecordResponse,
  type DoctorResponse,
} from "../../../api/entities";
import { WeeklyScheduleEditor, type WorkSchedule } from "../components/WeeklyScheduleEditor";
import { AttendanceCalendar } from "../attendance/AttendanceCalendar";

function fmtDuration(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function ymKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

type Qualification = NonNullable<DoctorResponse["qualifications"]>[number];

export function DoctorProfilePage() {
  const { authedFetch } = usePlan();
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [records, setRecords] = useState<AttendanceRecordResponse[]>([]);
  const [schedule, setSchedule] = useState<WorkSchedule>({});
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [license, setLicense] = useState("");
  const [qualifications, setQualifications] = useState<Qualification[]>([]);

  const [busyDetails, setBusyDetails] = useState(false);
  const [busySchedule, setBusySchedule] = useState(false);
  const [savedDetails, setSavedDetails] = useState(false);
  const [savedSchedule, setSavedSchedule] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) {
        setLoaded(true);
        return;
      }
      try {
        const [doc, rows] = await Promise.all([
          getMyDoctor(authedFetch),
          listMyAttendance(authedFetch, ymKey(new Date())),
        ]);
        if (!cancelled) {
          setDoctor(doc);
          setSchedule((doc.working_hours ?? {}) as WorkSchedule);
          setEmail(doc.email || "");
          setPhone(doc.phone || "");
          setLicense(doc.license_number || "");
          setQualifications(doc.qualifications || []);
          setRecords(rows);
        }
      } catch {
        if (!cancelled) setLoadError("Your doctor profile couldn't be loaded.");
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const presentDays = useMemo(
    () => records.filter((r) => r.status === "checked_in" || r.status === "checked_out").length,
    [records]
  );
  const workedMinutesThisMonth = useMemo(
    () => records.reduce((sum, r) => sum + (r.worked_minutes ?? 0), 0),
    [records]
  );

  async function saveDetails() {
    if (!authedFetch || busyDetails) return;
    setBusyDetails(true);
    setSavedDetails(false);
    setError(null);
    try {
      const updated = await updateMyDoctorProfile(authedFetch, {
        email,
        phone,
        license_number: license,
        qualifications,
      });
      setDoctor(updated);
      setSavedDetails(true);
    } catch {
      setError("Couldn't save your details — try again.");
    } finally {
      setBusyDetails(false);
    }
  }

  async function saveSchedule() {
    if (!authedFetch || busySchedule) return;
    setBusySchedule(true);
    setSavedSchedule(false);
    setError(null);
    try {
      const updated = await updateMyDoctorProfile(authedFetch, { working_hours: schedule });
      setDoctor(updated);
      setSchedule((updated.working_hours ?? {}) as WorkSchedule);
      setSavedSchedule(true);
    } catch {
      setError("Couldn't save your schedule — try again.");
    } finally {
      setBusySchedule(false);
    }
  }

  function updateQualification(index: number, patch: Partial<Qualification>) {
    setQualifications((qs) => qs.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  }

  return (
    <>
      <PageHeader title="My profile" subtitle="Your details, working schedule, and attendance record." />

      {!authedFetch && (
        <p className="mb-6 rounded-3xl border border-dashed border-sand-200 bg-white p-6 text-sm text-ink-muted">
          Sign in to see your profile.
        </p>
      )}

      {authedFetch && !doctor && loaded && (
        <p className="mb-6 rounded-3xl border border-dashed border-sand-200 bg-white p-6 text-sm font-medium text-ink-muted">
          {loadError ?? "No doctor profile is linked to your account yet — ask the clinic owner to add you."}
        </p>
      )}

      {doctor && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex flex-wrap items-center gap-4">
            {doctor.photo_url ? (
              <img
                src={doctor.photo_url}
                alt={doctor.name}
                className="h-14 w-14 rounded-2xl object-cover"
              />
            ) : (
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/10 text-accent-600">
                <StethoscopeIcon className="h-6 w-6" />
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-lg font-bold text-ink">{doctor.name || "Doctor"}</p>
              <p className="text-sm text-ink-muted">{doctor.specialty || "Medical professional"}</p>
            </div>
            <span className="rounded-full bg-accent-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-accent-600">
              Doctor
            </span>
          </div>
          {doctor.bio && <p className="mt-4 text-sm leading-relaxed text-ink-soft">{doctor.bio}</p>}
          <p className="mt-4 text-xs text-ink-muted">
            Your name and photo are managed by the clinic owner — you can update your contact, education, license, and
            weekly schedule below.
          </p>
        </div>
      )}

      {doctor && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-bold text-ink">My details</p>
            <button
              type="button"
              onClick={saveDetails}
              disabled={busyDetails || !authedFetch}
              className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50">
              {busyDetails ? "Saving…" : "Save details"}
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field icon={MailIcon} label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="doctor@clinic.com"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white"
              />
            </Field>
            <Field icon={PhoneIcon} label="Phone number">
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+92 300 0000000"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white"
              />
            </Field>
            <Field icon={BadgeCheckIcon} label="Medical license (MIT / PMDC)">
              <input
                type="text"
                value={license}
                onChange={(e) => setLicense(e.target.value)}
                placeholder="PMDC-ABC-0001"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white"
              />
            </Field>
            <Field icon={CalendarDaysIcon} label="Member since">
              <p className="py-2 text-sm font-semibold text-ink">
                {new Date(doctor.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" })}
              </p>
            </Field>
          </div>

          <p className="mb-2 mt-5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Education</p>
          {qualifications.length === 0 && (
            <p className="mb-2 text-sm text-ink-muted">No education listed yet — add your college and university degrees.</p>
          )}
          <div className="space-y-2">
            {qualifications.map((q, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-2xl bg-sand-100/70 p-2">
                <input
                  value={q.degree}
                  onChange={(e) => updateQualification(i, { degree: e.target.value })}
                  placeholder="Degree (MBBS, FCPS…)"
                  className="min-w-40 flex-1 rounded-xl border border-sand-200 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40"
                />
                <input
                  value={q.institution ?? ""}
                  onChange={(e) => updateQualification(i, { institution: e.target.value })}
                  placeholder="Institution / university"
                  className="min-w-48 flex-1 rounded-xl border border-sand-200 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40"
                />
                <input
                  value={q.year ?? ""}
                  onChange={(e) =>
                    updateQualification(i, { year: e.target.value === "" ? null : Number(e.target.value) })
                  }
                  placeholder="Year"
                  type="number"
                  className="w-20 rounded-xl border border-sand-200 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40"
                />
                <button
                  type="button"
                  onClick={() => setQualifications((qs) => qs.filter((_, x) => x !== i))}
                  className="rounded-xl p-2 text-ink-muted transition-colors hover:bg-danger/10 hover:text-danger"
                  aria-label="Remove education entry">
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setQualifications((qs) => [...qs, { degree: "", institution: "", year: null }])}
            className="mt-2 inline-flex items-center gap-1.5 rounded-xl px-2 py-1.5 text-sm font-semibold text-teal-700 transition-colors hover:bg-teal-50">
            <PlusIcon className="h-4 w-4" /> Add education
          </button>
          {savedDetails && <p className="mt-3 text-xs font-semibold text-teal-600">Details saved.</p>}
          {error && <p className="mt-3 text-xs font-medium text-danger">{error}</p>}
        </div>
      )}

      {doctor && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-bold text-ink">My working schedule</p>
            <button
              type="button"
              onClick={saveSchedule}
              disabled={busySchedule || !authedFetch}
              className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50">
              {busySchedule ? "Saving…" : "Save schedule"}
            </button>
          </div>
          <WeeklyScheduleEditor value={schedule} onChange={setSchedule} />
          {savedSchedule && <p className="mt-3 text-xs font-semibold text-teal-600">Schedule saved.</p>}
        </div>
      )}

      {doctor && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold text-ink">This month</p>
            <span className="rounded-xl bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-700">{presentDays} day{presentDays === 1 ? "" : "s"} present</span>
            <span className="rounded-xl bg-ink/5 px-3 py-1 text-xs font-semibold text-ink-soft">{fmtDuration(workedMinutesThisMonth)} worked</span>
          </div>
          <div className="mt-4">
            <AttendanceCalendar />
          </div>
        </div>
      )}
    </>
  );
}

function Field({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </p>
      {children}
    </div>
  );
}