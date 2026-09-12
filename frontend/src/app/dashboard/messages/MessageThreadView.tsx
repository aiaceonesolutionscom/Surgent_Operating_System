import React, { useEffect, useRef, useState } from "react";
import { SendIcon, MessageCircleIcon, MicIcon, MicOffIcon, PaperclipIcon, XIcon, FileTextIcon } from "lucide-react";
import type { StaffMessageResponse } from "../../../api/entities";
import { EmptyState } from "../components/EmptyState";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { hour: "numeric", minute: "2-digit" });
}

function formatDay(iso: string) {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function initials(name: string | null) {
  return (name || "?")[0]?.toUpperCase() || "?";
}

export function MessageThreadView({
  title,
  subtitle,
  messages,
  loading,
  onSend,
  onSendFile
}: {
  title: string;
  subtitle?: string;
  messages: StaffMessageResponse[];
  loading: boolean;
  onSend: (body: string) => Promise<unknown>;
  onSendFile?: (file: File) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setSending(true);
    try {
      await onSend(draft.trim());
      setDraft("");
    } finally {
      setSending(false);
    }
  }

  async function handleSendVoice() {
    if (!recordedBlob || !onSendFile) return;
    const file = new File([recordedBlob], `voice_note_${Date.now()}.webm`, { type: "audio/webm" });
    setSending(true);
    try {
      await onSendFile(file);
      setRecordedBlob(null);
      if (recordedUrl) URL.revokeObjectURL(recordedUrl);
      setRecordedUrl(null);
    } finally {
      setSending(false);
    }
  }

  async function handleSendFile() {
    if (!selectedFile || !onSendFile) return;
    setSending(true);
    try {
      await onSendFile(selectedFile);
      cancelFile();
    } finally {
      setSending(false);
    }
  }

  function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });
      chunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        setRecordedBlob(blob);
        setRecordedUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setRecording(true);
    }).catch(() => {});
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  function cancelRecording() {
    setRecordedBlob(null);
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedUrl(null);
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    if (file.type.startsWith("image/")) {
      setPreviewUrl(URL.createObjectURL(file));
    }
  }

  function cancelFile() {
    setSelectedFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  let lastDay: string | null = null;

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center gap-3 border-b border-sand-200 px-5 py-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-600/10 text-sm font-bold text-teal-600">
          {initials(title)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-ink">{title}</p>
          {subtitle && <p className="truncate text-xs text-ink-muted">{subtitle}</p>}
        </div>
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto bg-sand-50/40 px-5 py-4">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :
        messages.length === 0 ?
        <div className="flex h-full items-center justify-center">
            <EmptyState icon={MessageCircleIcon} title="No messages yet" body={`Say hello to ${title} to start the conversation.`} />
          </div> :

        <>
            {messages.map((m, i) => {
              const mine = m.mine;
              const day = formatDay(m.created_at);
              const showDaySeparator = day !== lastDay;
              lastDay = day;
              const prevMine = i > 0 ? messages[i - 1].mine : null;
              const grouped = !showDaySeparator && prevMine === mine;

              return (
                <React.Fragment key={m.id}>
                  {showDaySeparator &&
                <div className="flex items-center justify-center py-2">
                      <span className="rounded-full bg-sand-200/70 px-3 py-1 text-[11px] font-semibold text-ink-muted">{day}</span>
                    </div>
                }
                  <div className={`flex ${mine ? "justify-end" : "justify-start"} ${grouped ? "mt-0.5" : "mt-2.5"}`}>
                    {!mine &&
                    <span className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sand-200 text-[9px] font-bold text-ink-soft">
                        {initials(m.sender_name)}
                      </span>
                    }
                    <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${mine ? "bg-teal-600 text-white" : "border border-sand-200 bg-white text-ink"}`}>
                      {!mine && m.sender_name &&
                      <p className="mb-0.5 text-[10px] font-semibold text-teal-600">{m.sender_name}</p>
                      }
                      <p className="text-sm leading-relaxed">{m.body}</p>
                      <p className={`mt-1 text-[10px] ${mine ? "text-white/70" : "text-ink-muted"}`}>
                        {formatTime(m.created_at)}
                      </p>
                    </div>
                  </div>
                </React.Fragment>);

            })}
            <div ref={bottomRef} />
          </>
        }
      </div>

      {/* Recording state */}
      {recording && (
        <div className="flex items-center gap-3 border-t border-sand-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2 text-danger">
            <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
            <span className="text-sm font-medium">Recording...</span>
          </div>
          <div className="flex-1" />
          <button type="button" onClick={cancelRecording} className="rounded-lg p-2 text-ink-muted hover:bg-sand-100">
            <XIcon className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={stopRecording}
            className="flex items-center gap-1.5 rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-white hover:bg-danger/90"
          >
            <MicOffIcon className="h-4 w-4" />
            Stop
          </button>
        </div>
      )}

      {/* Recorded voice preview */}
      {!recording && recordedBlob && (
        <div className="flex items-center gap-3 border-t border-sand-200 bg-white px-4 py-3">
          <audio src={recordedUrl || ""} controls className="h-8 flex-1" />
          <button type="button" onClick={cancelRecording} className="rounded-lg p-2 text-ink-muted hover:bg-sand-100">
            <XIcon className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={handleSendVoice}
            disabled={sending}
            className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
          >
            <SendIcon className="h-4 w-4" />
            Send voice
          </button>
        </div>
      )}

      {/* File preview */}
      {!recording && selectedFile && (
        <div className="border-t border-sand-200 bg-white px-4 py-3">
          <div className="flex items-center gap-3">
            {previewUrl ? (
              <img src={previewUrl} alt="" className="h-12 w-12 rounded-lg object-cover" />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-sand-100">
                <FileTextIcon className="h-5 w-5 text-ink-muted" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{selectedFile.name}</p>
              <p className="text-xs text-ink-muted">{(selectedFile.size / 1024).toFixed(0)} KB</p>
            </div>
            <button type="button" onClick={cancelFile} className="rounded-lg p-2 text-ink-muted hover:bg-sand-100">
              <XIcon className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={handleSendFile}
              disabled={sending}
              className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              <SendIcon className="h-4 w-4" />
              Send
            </button>
          </div>
        </div>
      )}

      {/* Default input */}
      {!recording && !recordedBlob && !selectedFile && (
        <form onSubmit={handleSubmit} className="flex items-center gap-2.5 border-t border-sand-200 px-4 py-3.5">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept="image/*,application/pdf,.doc,.docx,.txt"
            className="hidden"
          />
          {onSendFile && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="shrink-0 rounded-lg p-2 text-ink-muted transition-colors hover:bg-sand-100 hover:text-ink"
              title="Attach file"
            >
              <PaperclipIcon className="h-5 w-5" />
            </button>
          )}
          {onSendFile && (
            <button
              type="button"
              onClick={startRecording}
              className="shrink-0 rounded-lg p-2 text-ink-muted transition-colors hover:bg-sand-100 hover:text-ink"
              title="Record voice message"
            >
              <MicIcon className="h-5 w-5" />
            </button>
          )}
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write a message…"
            className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />

          <button
            type="submit"
            disabled={sending || !draft.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

            <SendIcon className="h-4 w-4" />
          </button>
        </form>
      )}
    </div>);

}
