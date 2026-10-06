import { useState } from "react";
import { TagIcon, PlusIcon, XIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useMarketingOffers } from "./useMarketingOffers";

// Owner-facing editor for the offers marketing_followup_agent_services.py's
// send_offer() reads (AgentConfig.config.offers) — the first real writer of
// that JSONB column beyond `enabled`. Only rendered for owners since the
// backend PUT is require_role(OWNER)-gated.
export function MarketingOffersEditor() {
  const { authedFetch, role } = usePlan();
  const { offers, loading, saving, error, addOffer, removeOffer } = useMarketingOffers(authedFetch);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [expiresAt, setExpiresAt] = useState("");

  if (role !== "owner") return null;

  async function handleAdd() {
    if (!title.trim()) return;
    const ok = await addOffer({
      title: title.trim(),
      description: description.trim(),
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : null
    });
    if (ok) {
      setTitle("");
      setDescription("");
      setExpiresAt("");
    }
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="border-b border-sand-200 px-5 py-4">
        <p className="text-sm font-bold text-ink">Marketing offers</p>
        <p className="mt-0.5 text-xs text-ink-muted">
          What the Marketing Follow-up agent offers dormant leads when it reaches out — real, sent to real patients.
        </p>
      </div>

      <div className="p-5">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :

        <>
            {offers.length === 0 &&
          <p className="mb-4 text-sm text-ink-muted">No offers configured yet — the agent has nothing to send until you add one.</p>
          }

            {offers.length > 0 &&
          <div className="mb-4 space-y-2">
                {offers.map((offer, i) =>
            <div key={i} className="flex items-start gap-3 rounded-xl bg-sand-100 px-4 py-3">
                    <TagIcon className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-ink">{offer.title}</p>
                      {offer.description && <p className="text-xs text-ink-muted">{offer.description}</p>}
                      {offer.expires_at &&
                <p className="mt-0.5 text-[11px] text-ink-muted">
                          Expires {new Date(offer.expires_at).toLocaleDateString()}
                        </p>
                }
                    </div>
                    <button
                type="button"
                onClick={() => removeOffer(i)}
                disabled={saving}
                className="shrink-0 text-ink-muted hover:text-danger disabled:opacity-40">

                      <XIcon className="h-4 w-4" />
                    </button>
                  </div>
            )}
              </div>
          }

            <div className="grid gap-3 sm:grid-cols-2">
              <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Offer title — e.g. 20% off consultations"
              className="rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white sm:col-span-2" />

              <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

              <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </div>
            <button
            type="button"
            onClick={handleAdd}
            disabled={!title.trim() || saving}
            className="mt-3 flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:cursor-not-allowed disabled:opacity-40">

              <PlusIcon className="h-4 w-4" /> {saving ? "Saving…" : "Add offer"}
            </button>
            {error && <p className="mt-2 text-xs font-medium text-danger">{error}</p>}
          </>
        }
      </div>
    </div>);

}
