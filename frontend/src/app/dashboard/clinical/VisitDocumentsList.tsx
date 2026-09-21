import { useEffect, useState } from "react";
import { FileDownIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { listVisitDocuments, type VisitDocumentResponse } from "../../../api/entities";

const GENERATED_BY_LABEL: Record<string, string> = {
  ai_receptionist: "AI receptionist",
  staff: "Front desk",
  system: "System"
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

// Read-only — generation always happens server-side (appointment booking,
// AI-receptionist chat reaching enough intake data). This just surfaces the
// download link for the patient/doctor/receptionist to review.
export function VisitDocumentsList({ patientId }: { patientId: string }) {
  const { authedFetch } = usePlan();
  const [documents, setDocuments] = useState<VisitDocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authedFetch || !patientId) {
      setDocuments([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    listVisitDocuments(authedFetch, patientId)
      .then((data) => {
        if (!cancelled) setDocuments(data);
      })
      .catch(() => {
        if (!cancelled) setDocuments([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authedFetch, patientId]);

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <FileDownIcon className="h-4 w-4 text-teal-600" /> Visit documents
        </p>
      </div>
      <div className="p-2">
        {loading ? (
          <p className="px-3 py-4 text-sm text-ink-muted">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="px-3 py-4 text-sm text-ink-muted">No visit summary generated yet.</p>
        ) : (
          <div className="divide-y divide-sand-100">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between gap-3 px-3 py-3.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-ink">Visit summary</p>
                  <p className="text-xs text-ink-muted">
                    Generated {formatDate(doc.generated_at)} · {GENERATED_BY_LABEL[doc.generated_by] || doc.generated_by}
                  </p>
                </div>
                <a
                  href={doc.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex shrink-0 items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600"
                >
                  <FileDownIcon className="h-3.5 w-3.5" /> Download
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
