import { useEffect, useState } from "react";
import { SearchIcon, Loader2Icon, ShieldIcon, ShieldOffIcon } from "lucide-react";
import { listAdminUsers, updateAdminUser, type AdminUserItem } from "../../../api/admin";

// Display labels for the practice-scoped role (models/user.py's UserRole) —
// the same four roles the clinic dashboard's Sidebar gates on.
const ROLE_LABEL: Record<string, string> = {
  owner: "Owner",
  doctor: "Doctor",
  receptionist: "Receptionist",
  staff: "Staff",
};

const ROLE_CLASS: Record<string, string> = {
  owner: "bg-accent-500/10 text-accent-700",
  doctor: "bg-blue-500/10 text-blue-700",
  receptionist: "bg-green-500/10 text-green-700",
  staff: "bg-ink-muted/10 text-ink-muted",
};

// Platform-wide user roster (backend GET/PATCH /admin/users). Shows WHO each
// user is, WHICH clinic they belong to, and WHAT access they actually have:
// their practice-scoped role plus any granular permission grants (today only
// receptionists carry them) and the platform-admin flag that gates this panel.
export function AdminUsersPage() {
  const [rows, setRows] = useState<AdminUserItem[] | null>(null);
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    listAdminUsers(q || undefined)
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load users.");
      });
    return () => {
      cancelled = true;
    };
  }, [q]);

  async function togglePlatformAdmin(user: AdminUserItem) {
    setBusyId(user.id);
    setError(null);
    try {
      const updated = await updateAdminUser(user.id, !user.is_platform_admin);
      setRows((prev) => prev?.map((r) => (r.id === updated.id ? updated : r)) ?? prev);
    } catch {
      setError("Couldn't update the user — try again.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">Users</p>
        <h1 className="font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">Every staff account, every clinic</h1>
        <p className="text-sm text-ink-muted">
          Each account's role, clinic, and exactly what they can reach — a receptionist's granular grants are listed per
          user, and the platform-admin flag is what gates this panel itself.
        </p>
      </div>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      <div className="mt-6 flex items-center gap-2 rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 sm:w-96">
        <SearchIcon className="h-4 w-4 text-ink-muted" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by email…"
          className="w-full bg-transparent text-sm outline-none placeholder:text-ink-muted/60"
        />
      </div>

      <div className="mt-4 overflow-hidden rounded-2xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        {rows === null ? (
          <div className="flex justify-center py-12">
            <Loader2Icon className="h-6 w-6 animate-spin text-accent-500" />
          </div>
        ) : rows.length === 0 ? (
          <p className="py-12 text-center text-sm text-ink-muted">No users match “{q}”.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-sand-200 text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-5 py-3 font-semibold">Email</th>
                <th className="px-5 py-3 font-semibold">Clinic</th>
                <th className="px-5 py-3 font-semibold">Role &amp; access</th>
                <th className="px-5 py-3 text-right font-semibold">Platform admin</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((user) => (
                <tr key={user.id} className="border-b border-sand-100 last:border-0 align-top">
                  <td className="px-5 py-4">
                    <p className="font-medium text-ink">{user.email}</p>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {user.name ?? "—"}
                      {!user.is_active && <span className="ml-1.5 rounded-full bg-danger/10 px-1.5 py-0.5 text-[10px] font-semibold text-danger">Disabled</span>}
                    </p>
                  </td>
                  <td className="px-5 py-4 text-ink-muted">{user.practice_name ?? "—"}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ROLE_CLASS[user.role] ?? ROLE_CLASS.staff}`}>
                        {ROLE_LABEL[user.role] ?? user.role}
                      </span>
                      {user.role === "owner" && (
                        <span className="text-xs text-ink-muted">full clinic control</span>
                      )}
                    </div>
                    {user.permissions.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {user.permissions.map((grant) => (
                          <span
                            key={grant.key}
                            title={grant.key}
                            className="rounded-md bg-sand-100 px-1.5 py-0.5 text-[11px] font-medium text-ink-muted"
                          >
                            {grant.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <span className={`mr-3 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${user.is_platform_admin ? "bg-accent-500/10 text-accent-700" : "bg-ink-muted/10 text-ink-muted"}`}>
                      {user.is_platform_admin ? "Admin" : "Staff"}
                    </span>
                    <button
                      onClick={() => togglePlatformAdmin(user)}
                      disabled={busyId === user.id}
                      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 ${
                        user.is_platform_admin
                          ? "border border-sand-200 text-ink-muted hover:bg-sand-100"
                          : "bg-accent-500 text-white hover:bg-accent-600"
                      }`}
                    >
                      {busyId === user.id ? (
                        <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                      ) : user.is_platform_admin ? (
                        <ShieldOffIcon className="h-3.5 w-3.5" />
                      ) : (
                        <ShieldIcon className="h-3.5 w-3.5" />
                      )}
                      {user.is_platform_admin ? "Demote" : "Make admin"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
