import React, { useMemo, useRef, useState } from "react";
import { CameraIcon, PlusIcon, MegaphoneIcon, ColumnsIcon, XIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { usePatientPhotos } from "./usePatientPhotos";
import { PHOTO_STAGES, type PhotoStage, type PatientPhotoResponse } from "../../../api/entities";
import { BeforeAfterSlider } from "./BeforeAfterSlider";

const STAGE_ORDER: (PhotoStage | "untagged")[] = ["before", "day7", "day14", "1mo", "3mo", "6mo", "1yr", "other", "untagged"];
const STAGE_LABELS: Record<string, string> = Object.fromEntries(PHOTO_STAGES.map((s) => [s.value, s.label]));
STAGE_LABELS.untagged = "Untagged";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// Owner/Doctor only — matches the backend's own visibility boundary for
// clinical photography (see patient_photos_router.py).
export function PatientPhotosGallery({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const { photos, loading, upload, update, remove } = usePatientPhotos(authedFetch, patientId);
  const [stage, setStage] = useState<PhotoStage>("before");
  const [bodyArea, setBodyArea] = useState("");
  const [uploading, setUploading] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [compareIds, setCompareIds] = useState<[string | null, string | null]>([null, null]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const grouped = useMemo(() => {
    const map = new Map<string, PatientPhotoResponse[]>();
    for (const photo of photos) {
      const key = photo.stage || "untagged";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(photo);
    }
    return STAGE_ORDER.filter((s) => map.has(s)).map((s) => ({ stage: s, photos: map.get(s)! }));
  }, [photos]);

  const compareBefore = photos.find((p) => p.id === compareIds[0]);
  const compareAfter = photos.find((p) => p.id === compareIds[1]);

  // This guard has to sit *after* every hook above, not before them. `role`
  // arrives asynchronously from Clerk, so the first render can hit it (role
  // still undefined) and a later one miss it — bailing out early used to change
  // the hook count between renders, which React rejects outright.
  if (role !== "owner" && role !== "doctor") return null;

  async function handleFilePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    await upload(file, stage, undefined, stage, bodyArea.trim() || undefined);
    setUploading(false);
  }

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sand-200 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <CameraIcon className="h-4 w-4 text-teal-600" /> Photo timeline
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {photos.length >= 2 &&
          <button
            type="button"
            onClick={() => { setCompareMode((v) => !v); setCompareIds([null, null]); }}
            className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors ${compareMode ? "border-teal-600/40 bg-teal-600/8 text-teal-600" : "border-sand-200 text-ink-soft hover:border-teal-600/40 hover:text-teal-600"}`}>
              <ColumnsIcon className="h-3.5 w-3.5" /> {compareMode ? "Exit compare" : "Compare"}
            </button>
          }
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value as PhotoStage)}
            className="rounded-lg border border-sand-200 bg-canvas px-2.5 py-1.5 text-xs font-semibold text-ink-soft outline-none focus:border-teal-600/40">
            {PHOTO_STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <input
            value={bodyArea}
            onChange={(e) => setBodyArea(e.target.value)}
            placeholder="Body area (optional)"
            className="w-36 rounded-lg border border-sand-200 bg-canvas px-2.5 py-1.5 text-xs text-ink-soft outline-none focus:border-teal-600/40" />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
            <PlusIcon className="h-3.5 w-3.5" /> {uploading ? "Uploading…" : "Upload photo"}
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFilePick} className="hidden" />
        </div>
      </div>

      {compareMode &&
      <div className="border-b border-sand-200 p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <select
            value={compareIds[0] || ""}
            onChange={(e) => setCompareIds([e.target.value || null, compareIds[1]])}
            className="rounded-lg border border-sand-200 bg-canvas px-2.5 py-1.5 text-xs text-ink-soft outline-none focus:border-teal-600/40">
              <option value="">Pick "before" photo…</option>
              {photos.map((p) => <option key={p.id} value={p.id}>{STAGE_LABELS[p.stage || "untagged"]} · {formatDate(p.created_at)}</option>)}
            </select>
            <select
            value={compareIds[1] || ""}
            onChange={(e) => setCompareIds([compareIds[0], e.target.value || null])}
            className="rounded-lg border border-sand-200 bg-canvas px-2.5 py-1.5 text-xs text-ink-soft outline-none focus:border-teal-600/40">
              <option value="">Pick "after" photo…</option>
              {photos.map((p) => <option key={p.id} value={p.id}>{STAGE_LABELS[p.stage || "untagged"]} · {formatDate(p.created_at)}</option>)}
            </select>
          </div>
          {compareBefore && compareAfter ?
        <div className="max-w-xl">
              <BeforeAfterSlider
            beforeUrl={compareBefore.cloudinary_url}
            afterUrl={compareAfter.cloudinary_url}
            beforeLabel={STAGE_LABELS[compareBefore.stage || "untagged"]}
            afterLabel={STAGE_LABELS[compareAfter.stage || "untagged"]} />
            </div> :

        <p className="text-sm text-ink-muted">Pick two photos to compare — drag the divider to reveal each one.</p>
        }
        </div>
      }

      <div className="p-5">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :
        photos.length === 0 ?
        <p className="text-sm text-ink-muted">No photos yet.</p> :

        <div className="space-y-6">
            {grouped.map(({ stage: s, photos: stagePhotos }) =>
          <div key={s}>
                <p className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">{STAGE_LABELS[s]} ({stagePhotos.length})</p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {stagePhotos.map((photo) =>
              <PhotoCard key={photo.id} photo={photo} onUpdate={update} onRemove={remove} />
              )}
                </div>
              </div>
          )}
          </div>
        }
      </div>
    </div>);

}

function PhotoCard({
  photo,
  onUpdate,
  onRemove
}: {
  photo: PatientPhotoResponse;
  onUpdate: (id: string, data: { stage?: string | null; is_marketing_approved?: boolean | null }) => Promise<unknown>;
  onRemove: (id: string) => Promise<unknown>;
}) {
  const [editingStage, setEditingStage] = useState(false);

  return (
    <div className="group relative overflow-hidden rounded-xl border border-sand-200">
      <img src={photo.cloudinary_url} alt={photo.body_area || "Patient photo"} className="aspect-square w-full object-cover" />

      {editingStage ?
      <select
        autoFocus
        value={photo.stage || "other"}
        onChange={(e) => { onUpdate(photo.id, { stage: e.target.value }); setEditingStage(false); }}
        onBlur={() => setEditingStage(false)}
        className="absolute left-1.5 top-1.5 rounded-full border-none bg-ink px-2 py-0.5 text-[10px] font-semibold text-white outline-none">
          {PHOTO_STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select> :

      <button
        type="button"
        onClick={() => setEditingStage(true)}
        className="absolute left-1.5 top-1.5 rounded-full bg-ink/70 px-2 py-0.5 text-[10px] font-semibold capitalize text-white transition-colors hover:bg-ink">
          {STAGE_LABELS[photo.stage || "untagged"]}
        </button>
      }

      {photo.body_area &&
      <span className="absolute bottom-1.5 left-1.5 rounded-full bg-ink/70 px-2 py-0.5 text-[10px] font-medium text-white">
          {photo.body_area}
        </span>
      }

      <button
        type="button"
        onClick={() => onUpdate(photo.id, { is_marketing_approved: !photo.is_marketing_approved })}
        title={photo.is_marketing_approved ? "Approved for marketing use — click to revoke" : "Not approved for marketing — click to approve"}
        className={`absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full transition-colors ${photo.is_marketing_approved ? "bg-success text-white" : "bg-ink/70 text-white opacity-0 hover:bg-ink group-hover:opacity-100"}`}>
        <MegaphoneIcon className="h-3 w-3" />
      </button>

      <button
        type="button"
        onClick={() => onRemove(photo.id)}
        className="absolute bottom-1.5 right-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-ink/70 text-white opacity-0 transition-opacity hover:bg-danger group-hover:opacity-100">
        <XIcon className="h-3 w-3" />
      </button>
    </div>);

}
