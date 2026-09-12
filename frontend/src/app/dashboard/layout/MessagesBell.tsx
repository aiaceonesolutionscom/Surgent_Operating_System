import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageCircleIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useMessageThreads } from "../messages/useMessageThreads";
import { DASHBOARD_ROUTES } from "../constants/routes";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// Owned-only quick preview, next to the practice's much bigger surfaces — a
// compact list of the Owner's team conversations, with the full inbox
// (MessagesPage) one click away.
export function MessagesBell() {
  // usePlanTier() seeds `role` with a placeholder value ("owner") until the
  // real /practice/me response resolves — gating strictly on
  // `role === "owner"` fired this component's fetch during that transient
  // window for every non-owner login too, hitting a 403-ish path on every
  // Doctor/Receptionist sign-in. `loading` distinguishes "still resolving"
  // from "confirmed owner".
  const { role, authedFetch, loading: roleLoading } = usePlan();
  const isConfirmedOwner = !roleLoading && role === "owner";
  const { threads, loading } = useMessageThreads(isConfirmedOwner ? authedFetch : null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  if (!isConfirmedOwner) return null;

  const active = threads.filter((t) => t.message_count > 0);
  const badgeCount = active.length;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Messages"
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-sand-100 hover:text-ink">
        <MessageCircleIcon className="h-4.5 w-4.5" />
        {badgeCount > 0 &&
        <span className="absolute -right-0.5 -top-0.5 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">
            {badgeCount}
          </span>
        }
      </button>

      {open &&
      <div className="absolute right-0 top-11 z-40 w-80 overflow-hidden rounded-2xl border border-sand-200 bg-white shadow-[0_12px_32px_rgba(15,23,42,0.12)]">
          <div className="border-b border-sand-100 px-4 py-3">
            <p className="text-sm font-bold text-ink">Messages</p>
          </div>

          {loading ?
        <p className="px-4 py-6 text-center text-sm text-ink-muted">Loading…</p> :
        threads.length === 0 ?
        <p className="px-4 py-6 text-center text-sm text-ink-muted">No staff yet — invite a doctor or receptionist to start messaging.</p> :

        <div className="max-h-80 divide-y divide-sand-100 overflow-y-auto">
              {threads.map((t) => {
          const name = t.recipient_name || t.recipient_email || "Unnamed";
          return (
          <button
            key={t.conversation_id}
            type="button"
            onClick={() => {
              setOpen(false);
              navigate(DASHBOARD_ROUTES.messageThread(t.conversation_id));
            }}
            className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-sand-50">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sand-200 text-xs font-bold text-ink-soft">
                    {name[0]?.toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-semibold text-ink">{name}</span>
                      <span className="shrink-0 rounded-full bg-sand-100 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-ink-muted">{t.recipient_role}</span>
                    </span>
                    <span className="block truncate text-xs text-ink-muted">{t.last_message_preview || "No messages yet"}</span>
                  </span>
                  {t.last_message_at &&
            <span className="shrink-0 text-[10px] text-ink-muted">{formatTime(t.last_message_at)}</span>
            }
                </button>);
          })}
            </div>
        }

          <button
          type="button"
          onClick={() => {
            setOpen(false);
            navigate(DASHBOARD_ROUTES.messages);
          }}
          className="block w-full border-t border-sand-100 px-4 py-2.5 text-center text-xs font-semibold text-teal-600 transition-colors hover:bg-sand-50">
            View all messages
          </button>
        </div>
      }
    </div>);

}
