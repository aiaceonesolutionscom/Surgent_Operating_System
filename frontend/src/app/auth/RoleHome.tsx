import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@clerk/clerk-react";
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

async function resolveRole(authedFetch: ReturnType<typeof useAuthedFetch>["authedFetch"]): Promise<Resolved> {
  if (!authedFetch) return { kind: "none" };
  try {
    const practice = await getMyPractice(authedFetch);
    return { kind: "practice", role: practice.role };
  } catch {
    // no practice membership yet — check pending applications below
  }
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
    // A genuinely new self-signup (no invite/apply code) — org_apply's own
    // page handles pending/approved/rejected states; here we only need to
    // know a request EXISTS to route there instead of the marketing site.
    await getMyOrgRequest(authedFetch);
    return { kind: "org-request" };
  } catch {
    // no org request either
  }
  return { kind: "none" };
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
  const { authedFetch } = useAuthedFetch();
  const [resolved, setResolved] = useState<Resolved | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setResolved({ kind: "none" });
      return;
    }
    let cancelled = false;
    (async () => {
      const result = await resolveRole(authedFetch);
      if (cancelled) return;
      setResolved(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, authedFetch]);

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