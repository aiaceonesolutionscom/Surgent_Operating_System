import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth, useUser } from "@clerk/clerk-react";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyPractice } from "../../api/practice";
import { getMyApplication, getMyStaffApplication, getMyOrgRequest } from "../../api/entities";
import { HomePage } from "../../pages/HomePage";

type Role = "owner" | "doctor" | "receptionist" | "staff";

// Land / for a signed-in user:
//   practice membership (owner/doctor/receptionist) → their OWN dashboard area
//   pending doctor application (no practice row yet)  → /doctor/apply/pending
//   pending staff application (no practice row yet)   → /staff/apply/pending
//   pending/reviewed org request (brand-new signup)   → /org/apply
//   nothing                                          → marketing home page
// This is the fix for "I signed in as a doctor and / still showed the
// marketing site" — each role is auto-put into their area instead of relying
// on bookmarks, and it never drops anyone on a foreign dashboard.
type Resolved =
  | { kind: "practice"; role: Role }
  | { kind: "pending-doctor" }
  | { kind: "pending-staff" }
  | { kind: "org-request" }
  | { kind: "none" };

async function resolveRole(
  authedFetch: ReturnType<typeof useAuthedFetch>["authedFetch"],
  isFreshOrgRequest: boolean,
): Promise<Resolved> {
  if (!authedFetch) return { kind: "none" };
  try {
    const practice = await getMyPractice(authedFetch);
    return { kind: "practice", role: practice.role };
  } catch {
    // no practice membership yet — check pending applications below
  }

  // Fast path for the brand-new /sign-up org request, BEFORE the two
  // application probes below.
  //
  // ORDER IS LOAD-BEARING: the practice check above has to stay first. Clerk's
  // unsafeMetadata persists for the lifetime of the account, so an org request
  // that has since been APPROVED still carries invite_type="org_request"
  // forever — testing the metadata first would bounce that owner back to
  // /org/apply on every login instead of their dashboard.
  //
  // Reading it client-side also means a brand-new signup costs ONE request
  // instead of four. The previous version probed /practice/my-org-request and
  // depended on the backend's Clerk API call to self-heal a missing row
  // (practice_controllers.get_my_org_request). When that self-heal didn't fire,
  // a user who had just requested free access silently landed on the marketing
  // HomePage instead of their request form — with no error shown anywhere,
  // because every probe was wrapped in a bare catch. The answer is already in
  // Clerk's client-side user object, so don't spend network calls asking for it.
  if (isFreshOrgRequest) return { kind: "org-request" };

  try {
    const doctor = await getMyApplication(authedFetch);
    if (doctor.status === "pending") return { kind: "pending-doctor" };
  } catch {
    // no doctor application
  }
  try {
    const staff = await getMyStaffApplication(authedFetch);
    if (staff.status === "pending") return { kind: "pending-staff" };
  } catch {
    // no staff application either
  }
  try {
    // A genuinely new self-signup whose Clerk metadata hasn't landed yet — the
    // backend row is the last resort. Kept as a fallback rather than deleted.
    await getMyOrgRequest(authedFetch);
    return { kind: "org-request" };
  } catch {
    // no org request either
  }
  // Signed in, but no practice, no doctor/staff application and no org-request
  // row. The dev database had never produced a single org-request row, so this
  // is NOT a rare corner — it is the normal state of a brand-new signup whose
  // Clerk metadata is absent, and it used to dump them on the marketing
  // HomePage. resolveRole only ever runs for signed-in users (the signed-out
  // branch returns "none" before we get here), so "none" at this point means
  // "has nothing" — and a signed-in user with nothing wants to start a clinic,
  // not read a sales page. OrgApplyPage renders its own submit form when no row
  // exists yet, so sending them there is correct whether or not the row is
  // there.
  return { kind: "org-request" };
}

function destinationFor(resolved: Resolved): string | null {
  switch (resolved.kind) {
    case "practice":
      return resolved.role === "doctor"
        ? "/dashboard/doctor"
        : resolved.role === "receptionist"
        ? "/dashboard/front-desk"
        : resolved.role === "owner"
        ? "/dashboard"
        : null;
    case "pending-doctor":
      return "/doctor/apply/pending";
    case "pending-staff":
      return "/staff/apply/pending";
    case "org-request":
      return "/org/apply";
    case "none":
      return null;
  }
}

export function RoleHome() {
  const { isLoaded, isSignedIn } = useAuth();
  // useUser() has its OWN isLoaded, independent of useAuth()'s. Both are
  // awaited before resolving, because unsafeMetadata is null until the user
  // object itself has loaded — running resolveRole on that null would skip the
  // org-request fast path and land the brand-new signup back on HomePage,
  // which is the exact bug this fast path exists to fix.
  const { user, isLoaded: isUserLoaded } = useUser();
  const { authedFetch } = useAuthedFetch();
  const [resolved, setResolved] = useState<Resolved | null>(null);

  const inviteType = (user?.unsafeMetadata as Record<string, unknown> | undefined)?.invite_type;
  const isFreshOrgRequest = inviteType === "org_request";

  useEffect(() => {
    if (!isLoaded || !isUserLoaded) return;
    if (!isSignedIn) {
      setResolved({ kind: "none" });
      return;
    }
    let cancelled = false;
    (async () => {
      const result = await resolveRole(authedFetch, isFreshOrgRequest);
      if (cancelled) return;
      setResolved(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoaded, isUserLoaded, isSignedIn, authedFetch, isFreshOrgRequest]);

  const destination = resolved && destinationFor(resolved);

  if (destination) return <Navigate to={destination} replace />;

  if (resolved === null) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <div style={{ width: 32, height: 32, border: "3px solid #e5e7eb", borderTopColor: "#6366f1", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
      </div>);

  }

  return <HomePage />;
}