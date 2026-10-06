import { Link, useNavigate } from "react-router-dom";
import { LogOutIcon } from "lucide-react";
import { useAdminAccess } from "../useAdminAccess";
import { clearAdminToken } from "../../../api/admin";
import { ADMIN_ROUTES } from "../constants/routes";

export function AdminTopbar() {
  const { username } = useAdminAccess();
  const navigate = useNavigate();

  function handleLogout() {
    clearAdminToken();
    navigate(ADMIN_ROUTES.signIn, { replace: true });
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-sand-200/80 bg-canvas/80 px-6 backdrop-blur-md">
      <div>
        <p className="text-sm font-semibold text-ink">{username ? `Signed in as ${username}` : "Super Admin"}</p>
      </div>
      <div className="flex items-center gap-4">
        <Link to="/" className="hidden text-sm font-medium text-ink-muted transition-colors hover:text-ink sm:inline">
          Back to site
        </Link>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-sm font-medium text-ink-soft transition-colors hover:border-danger/40 hover:text-danger">

          <LogOutIcon className="h-3.5 w-3.5" /> Log out
        </button>
      </div>
    </header>);

}
