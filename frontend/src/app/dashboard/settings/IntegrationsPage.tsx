import { useEffect, useState } from "react";
import { MessageCircleIcon, CheckCircle2Icon, XCircleIcon, Loader2Icon, InstagramIcon, ExternalLinkIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import {
  getGreenApiSettings,
  updateGreenApiSettings,
  disconnectGreenApi,
  getMetaSettings,
  getMetaConnectUrl,
  disconnectMeta,
  type GreenApiSettingsResponse,
  type MetaSettingsResponse
} from "../../../api/entities";
import { META_OAUTH_STORAGE_KEYS } from "./MetaCallbackPage";

// Owner-only step-by-step self-connect for the two channels the AI
// Receptionist/patient messaging run on. Green API is real end-to-end
// (WhatsAppGreenAPI already reads Practice.settings["green_api"] — this page
// is only the missing entry side). Meta/Instagram's OAuth code is real too,
// but gated platform-wide on a registered Facebook App existing
// (MetaService.is_configured()) — until Aiaceone's team registers one, the
// card below honestly shows "not available yet" instead of a dead button.
export function IntegrationsPage() {
  return (
    <>
      <PageHeader
        title="Integrations"
        subtitle="Connect your own WhatsApp account so the AI Receptionist and patient messaging run through your practice's number." />
      <div className="mt-6 space-y-4">
        <GreenApiCard />
        <MetaCard />
      </div>
    </>
  );
}

function GreenApiCard() {
  const { authedFetch } = usePlan();
  const [status, setStatus] = useState<GreenApiSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [instanceId, setInstanceId] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  async function load() {
    if (!authedFetch) return;
    try {
      const s = await getGreenApiSettings(authedFetch);
      setStatus(s);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!authedFetch || !instanceId.trim() || !apiToken.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const result = await updateGreenApiSettings(authedFetch, instanceId.trim(), apiToken.trim());
      setStatus(result);
      setEditing(false);
      setInstanceId("");
      setApiToken("");
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't connect — check your instance ID and token.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect() {
    if (!authedFetch) return;
    setSaving(true);
    try {
      await disconnectGreenApi(authedFetch);
      setStatus({ connected: false, instance_id: null, state: null, error: null });
    } finally {
      setSaving(false);
    }
  }

  const isConnected = status?.connected;

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-teal-600/8 text-teal-600">
            <MessageCircleIcon className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-bold text-ink">WhatsApp (Green API)</p>
            <p className="text-xs text-ink-muted">Real-time patient messaging &amp; the AI Receptionist</p>
          </div>
        </div>
        {!loading && status && (
          <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${isConnected ? "bg-success/10 text-success" : "bg-ink-muted/10 text-ink-muted"}`}>
            {isConnected ? <CheckCircle2Icon className="h-3 w-3" /> : <XCircleIcon className="h-3 w-3" />}
            {isConnected ? "Connected" : "Not connected"}
          </span>
        )}
      </div>

      {loading && <Loader2Icon className="mt-4 h-5 w-5 animate-spin text-accent-500" />}

      {!loading && status?.instance_id && !editing && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-sand-200 bg-canvas px-4 py-3">
          <div>
            <p className="text-xs text-ink-muted">Instance ID</p>
            <p className="text-sm font-semibold text-ink">{status.instance_id}</p>
            {status.error && <p className="mt-1 text-xs text-danger">{status.error}</p>}
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setEditing(true)} className="rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:bg-sand-100">
              Change
            </button>
            <button type="button" onClick={handleDisconnect} disabled={saving} className="rounded-lg border border-danger/25 px-3 py-1.5 text-xs font-semibold text-danger hover:bg-danger/5 disabled:opacity-50">
              Disconnect
            </button>
          </div>
        </div>
      )}

      {!loading && (!status?.instance_id || editing) && (
        <form onSubmit={handleConnect} className="mt-4 space-y-3">
          <ol className="list-decimal space-y-1.5 pl-4 text-xs text-ink-muted">
            <li>
              Create a free account at{" "}
              <a href="https://green-api.com" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-teal-600 hover:underline">
                green-api.com <ExternalLinkIcon className="h-3 w-3" />
              </a>{" "}
              and create a WhatsApp instance.
            </li>
            <li>Scan the QR code shown there with the WhatsApp account you want your practice to use.</li>
            <li>Copy the Instance ID and API Token from your Green API dashboard and paste them below.</li>
          </ol>
          <input
            value={instanceId}
            onChange={(e) => setInstanceId(e.target.value)}
            placeholder="Instance ID"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-accent-500/50 focus:bg-white" />
          <input
            value={apiToken}
            onChange={(e) => setApiToken(e.target.value)}
            type="password"
            placeholder="API Token"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-accent-500/50 focus:bg-white" />
          {error && <p className="text-xs text-danger">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={saving || !instanceId.trim() || !apiToken.trim()}
              className="rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50">
              {saving ? "Connecting…" : "Connect"}
            </button>
            {editing && (
              <button type="button" onClick={() => setEditing(false)} className="rounded-xl px-4 py-2.5 text-sm font-semibold text-ink-muted hover:text-ink">
                Cancel
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
}

function MetaCard() {
  const { authedFetch } = usePlan();
  const [status, setStatus] = useState<MetaSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!authedFetch) return;
    try {
      setStatus(await getMetaSettings(authedFetch));
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  async function handleConnect() {
    if (!authedFetch) return;
    setConnecting(true);
    setError(null);
    try {
      const redirectUri = `${window.location.origin}/dashboard/settings/integrations/meta-callback`;
      const { url, state } = await getMetaConnectUrl(authedFetch, redirectUri);
      sessionStorage.setItem(META_OAUTH_STORAGE_KEYS.STATE_KEY, state);
      sessionStorage.setItem(META_OAUTH_STORAGE_KEYS.REDIRECT_KEY, redirectUri);
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't start the connection.");
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    if (!authedFetch) return;
    setDisconnecting(true);
    try {
      await disconnectMeta(authedFetch);
      await load();
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-pink-600/8 text-pink-600">
            <InstagramIcon className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-bold text-ink">Instagram &amp; Facebook (Meta)</p>
            <p className="text-xs text-ink-muted">DMs and comments from your Page &amp; Instagram Business account</p>
          </div>
        </div>
        {!loading && status?.connected && (
          <span className="flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-semibold text-success">
            <CheckCircle2Icon className="h-3 w-3" /> Connected
          </span>
        )}
      </div>

      {loading && <Loader2Icon className="mt-4 h-5 w-5 animate-spin text-accent-500" />}

      {!loading && status && !status.configured && (
        <div className="mt-4 flex items-start gap-2 rounded-2xl border border-dashed border-sand-200 bg-canvas px-4 py-3">
          <XCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-ink-muted" />
          <p className="text-xs text-ink-muted">
            Not available yet — this needs a platform-level Facebook App that Aiaceone's team sets up once for
            everyone. Nothing you can do here yet; check back soon.
          </p>
        </div>
      )}

      {!loading && status?.configured && status.connected && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-sand-200 bg-canvas px-4 py-3">
          <div>
            <p className="text-xs text-ink-muted">Connected Page</p>
            <p className="text-sm font-semibold text-ink">{status.page_name}</p>
          </div>
          <button type="button" onClick={handleDisconnect} disabled={disconnecting} className="rounded-lg border border-danger/25 px-3 py-1.5 text-xs font-semibold text-danger hover:bg-danger/5 disabled:opacity-50">
            {disconnecting ? "Disconnecting…" : "Disconnect"}
          </button>
        </div>
      )}

      {!loading && status?.configured && !status.connected && (
        <div className="mt-4">
          <p className="text-xs text-ink-muted">
            Connects the Facebook Page you manage, and its linked Instagram Business account, in one step via Meta's
            own sign-in.
          </p>
          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
          <button
            type="button"
            onClick={handleConnect}
            disabled={connecting}
            className="mt-3 flex items-center gap-1.5 rounded-xl bg-pink-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-pink-700 disabled:opacity-50">
            {connecting ? "Redirecting…" : "Connect with Meta"} <ExternalLinkIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
