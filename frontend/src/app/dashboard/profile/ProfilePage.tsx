import React from "react";
import { useUser, UserButton } from "@clerk/clerk-react";
import { BuildingIcon, ClockIcon, MapPinIcon, PhoneIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePracticeProfile } from "./usePracticeProfile";
import { usePlan } from "../plan/PlanContext";
import { DoctorProfilePage } from "./DoctorProfilePage";
import { ReceptionistProfilePage } from "./ReceptionistProfilePage";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

function AccountCard() {
  if (!clerkEnabled) {
    return (
      <div className="rounded-3xl border border-dashed border-sand-200 bg-white p-6 text-sm text-ink-muted">
        Clerk isn't configured in this environment (
        <code className="rounded bg-sand-100 px-1.5 py-0.5">VITE_CLERK_PUBLISHABLE_KEY</code> not set) — account
        details would show here once it is.
      </div>);

  }
  return <AccountCardWithUser />;
}

function AccountCardWithUser() {
  const { user, isLoaded } = useUser();
  if (!isLoaded) return null;

  return (
    <div className="flex items-center justify-between rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-4">
        <UserButton afterSignOutUrl="/" />
        <div>
          <p className="text-sm font-bold text-ink">{user?.fullName || user?.username || "Signed in"}</p>
          <p className="text-xs text-ink-muted">{user?.primaryEmailAddress?.emailAddress}</p>
        </div>
      </div>
      <span className="rounded-full bg-success/10 px-3 py-1 text-xs font-semibold text-success">
        Signed in
      </span>
    </div>);

}

export function ProfilePage() {
  const { role } = usePlan();
  // Doctor and Receptionist get their own staff profile (roster details +
  // self-editable weekly schedule + attendance); the Owner keeps the
  // practice-level profile below.
  if (role === "doctor") return <DoctorProfilePage />;
  if (role === "receptionist") return <ReceptionistProfilePage />;

  return <OwnerProfileContent />;
}

function OwnerProfileContent() {
  const { profile, update } = usePracticeProfile();

  return (
    <>
      <PageHeader title="Profile" subtitle="Your account and practice details." />

      <div className="mb-6">
        <AccountCard />
      </div>

      <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <p className="mb-4 text-sm font-bold text-ink">Practice details</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field icon={BuildingIcon} label="Practice name" value={profile.name} onChange={(v) => update({ name: v })} />
          <Field icon={ClockIcon} label="Timezone" value={profile.timezone} onChange={(v) => update({ timezone: v })} />
          <Field icon={MapPinIcon} label="Address" value={profile.address} onChange={(v) => update({ address: v })} placeholder="Not set" />
          <Field icon={PhoneIcon} label="On-call phone" value={profile.onCallPhone} onChange={(v) => update({ onCallPhone: v })} placeholder="Not set" />
        </div>
        <p className="mt-4 text-xs text-ink-muted">
          Saved to this browser for now — the real{" "}
          <code className="rounded bg-sand-100 px-1.5 py-0.5">Practice</code> model already exists on the backend;
          a settings API to persist this for real is a later phase.
        </p>
      </div>
    </>);

}

function Field({
  icon: Icon,
  label,
  value,
  onChange,
  placeholder



}: {icon: React.ComponentType<{className?: string;}>;label: string;value: string;onChange: (v: string) => void;placeholder?: string;}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        <Icon className="h-3.5 w-3.5" /> {label}
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

    </label>);

}
