import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Loader2Icon, CheckCircle2Icon, XCircleIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { completeMetaConnect } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

const STATE_KEY = "aiaceone_meta_oauth_state";
const REDIRECT_KEY = "aiaceone_meta_oauth_redirect";

// Meta redirects the browser HERE after the OAuth consent screen (see
// IntegrationsPage's "Connect" button, which stores state+redirect_uri in
// sessionStorage before sending the browser to Meta). Verifies the state
// matches (CSRF guard) then hands the code to the backend to exchange for a
// real Page access token.
export function MetaCallbackPage() {
  const { authedFetch } = usePlan();
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"working" | "success" | "error">("working");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const code = params.get("code");
      const state = params.get("state");
      const expectedState = sessionStorage.getItem(STATE_KEY);
      const redirectUri = sessionStorage.getItem(REDIRECT_KEY);

      if (!code || !state || !redirectUri || state !== expectedState) {
        setStatus("error");
        setError("This connection link is invalid or expired — try connecting again.");
        return;
      }
      if (!authedFetch) return;
      try {
        await completeMetaConnect(authedFetch, code, state, redirectUri);
        sessionStorage.removeItem(STATE_KEY);
        sessionStorage.removeItem(REDIRECT_KEY);
        setStatus("success");
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error && err.message ? err.message : "Couldn't complete the connection.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-sm rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
        {status === "working" && (
          <>
            <Loader2Icon className="mx-auto h-8 w-8 animate-spin text-accent-500" />
            <p className="mt-4 text-sm text-ink-muted">Connecting your Instagram/Facebook account…</p>
          </>
        )}
        {status === "success" && (
          <>
            <CheckCircle2Icon className="mx-auto h-8 w-8 text-success" />
            <p className="mt-4 text-sm font-semibold text-ink">Connected!</p>
            <Link to={DASHBOARD_ROUTES.settingsIntegrations} className="mt-4 inline-block rounded-xl bg-accent-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent-600">
              Back to Integrations
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <XCircleIcon className="mx-auto h-8 w-8 text-danger" />
            <p className="mt-4 text-sm text-danger">{error}</p>
            <Link to={DASHBOARD_ROUTES.settingsIntegrations} className="mt-4 inline-block rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft hover:bg-sand-100">
              Back to Integrations
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export const META_OAUTH_STORAGE_KEYS = { STATE_KEY, REDIRECT_KEY };
