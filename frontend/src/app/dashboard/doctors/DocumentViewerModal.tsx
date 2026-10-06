import { useEffect, useState } from "react";
import { DownloadIcon, FileTextIcon, XIcon } from "lucide-react";
import type { DoctorDocument } from "./types";

// A raw `data:` URI works fine for small files, but Chromium's built-in PDF
// viewer silently fails to render one once it gets large (confirmed: a
// ~1KB PDF renders instantly, a 15MB one renders as a blank page — with no
// error, so it just looks broken/frozen). Converting to a `blob:` URL fixes
// it at any size, since the bytes are referenced instead of inlined into
// the URL string itself. Real license/certification scans are exactly the
// kind of file this hits — a photo-scanned multi-page PDF is easily 5-20MB.
function dataUrlToBlobUrl(dataUrl: string): string {
  const [header, base64] = dataUrl.split(",");
  const mime = header.match(/data:(.*?);base64/)?.[1] || "application/octet-stream";
  const bin = atob(base64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

export function DocumentViewerModal({ doc, onClose }: { doc: DoctorDocument; onClose: () => void }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    const url = dataUrlToBlobUrl(doc.dataUrl);
    setBlobUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [doc.dataUrl]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const isPdf = doc.mimeType === "application/pdf" || doc.name.toLowerCase().endsWith(".pdf");
  const href = blobUrl || doc.dataUrl;

  return (
    <div className="fixed inset-0 z-[70] flex flex-col bg-ink/90 backdrop-blur-sm">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 px-6">
        <div className="flex min-w-0 items-center gap-2.5 text-white">
          <FileTextIcon className="h-4 w-4 shrink-0 text-teal-300" />
          <span className="truncate text-sm font-semibold">{doc.name}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={href}
            download={doc.name}
            className="flex items-center gap-1.5 rounded-xl bg-white/10 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/20">

            <DownloadIcon className="h-4 w-4" /> Download
          </a>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-xl text-white/70 transition-colors hover:bg-white/10 hover:text-white">

            <XIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 p-4">
        {!blobUrl ?
        <div className="flex h-full items-center justify-center text-sm text-white/60">Loading…</div> :
        isPdf ?
        <iframe src={blobUrl} title={doc.name} className="h-full w-full rounded-xl bg-white" /> :

        <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-white/80">
            <FileTextIcon className="h-12 w-12 text-white/40" />
            <p className="text-sm">Preview isn't available for this file type.</p>
            <a
            href={href}
            download={doc.name}
            className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

              <DownloadIcon className="h-4 w-4" /> Download to view
            </a>
          </div>
        }
      </div>
    </div>);

}
