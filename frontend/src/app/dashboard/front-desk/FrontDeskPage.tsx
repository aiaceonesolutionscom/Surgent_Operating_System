import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { useFrontDesk } from "./useFrontDesk";
import { ReceptionistFrontDesk } from "./ReceptionistFrontDesk";
import { OwnerFrontDeskOverview } from "./OwnerFrontDeskOverview";
import { getMyStaff } from "../../../api/entities";
import { AttendanceCalendar } from "../attendance/AttendanceCalendar";

// One route, one real data source (useFrontDesk), two different views —
// Receptionist gets the operate-it workspace (check-in, waiting room,
// calendar, waitlist), Owner gets a read-only live overview of the whole
// clinic grouped by doctor. Previously both roles landed on the exact same
// operate-it UI, which is more control than an Owner walking through for a
// quick status check actually needs.
export function FrontDeskPage() {
  const { role, authedFetch } = usePlan();
  const frontDesk = useFrontDesk(authedFetch);
  const [staffName, setStaffName] = useState<string | null>(null);
  const [todayStats] = useState(() => new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }));

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (role !== "receptionist" || !authedFetch) return;
      try {
        const me = await getMyStaff(authedFetch);
        if (!cancelled) setStaffName(me.name);
      } catch {
        // Greeting stays generic if the profile can't be fetched.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [role, authedFetch]);

  return (
    <>
      {role === "receptionist" ? (
        <>
          <div className="mb-2">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">Front desk</p>
            <h1 className="mt-2 font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">
              {staffName ? `Welcome receptionist ${staffName}` : "Welcome receptionist"}
            </h1>
            <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">{todayStats}</p>
          </div>
          <ReceptionistFrontDesk {...frontDesk} />
          <div className="mt-6">
            <AttendanceCalendar />
          </div>
        </>
      ) : (
        <>
          <PageHeader
            title="Front Desk"
            subtitle="Live view of every doctor's patient flow today." />
          <OwnerFrontDeskOverview appointments={frontDesk.appointments} loading={frontDesk.loading} />
        </>
      )}
    </>);
}