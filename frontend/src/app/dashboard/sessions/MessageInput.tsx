import React, { useState, useRef } from "react";
import { SendIcon, MicIcon, MicOffIcon, PaperclipIcon, XIcon, FileTextIcon } from "lucide-react";

interface MessageInputProps {
  onSendText: (text: string) => void;
  onSendVoice?: (blob: Blob) => void;
  onSendFile?: (file: File) => void;
  disabled?: boolean;
}

export function MessageInput({ onSendText, onSendVoice, onSendFile, disabled }: MessageInputProps) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (text.trim()) {
      onSendText(text.trim());
      setText("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
    } catch (err) {
      console.error("Microphone access denied:", err);
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const cancelRecording = () => {
    setRecordedBlob(null);
    setRecordedUrl(null);
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
  };

  const sendVoice = () => {
    if (recordedBlob && onSendVoice) {
      onSendVoice(recordedBlob);
      setRecordedBlob(null);
      setRecordedUrl(null);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    if (file.type.startsWith("image/")) {
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const cancelFile = () => {
    setSelectedFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const sendFile = () => {
    if (selectedFile && onSendFile) {
      onSendFile(selectedFile);
      cancelFile();
    }
  };

  // Recording state UI
  if (recording) {
    return (
      <div className="flex items-center gap-3 border-t border-sand-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2 text-danger">
          <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
          <span className="text-sm font-medium">Recording...</span>
        </div>
        <div className="flex-1" />
        <button onClick={cancelRecording} className="rounded-lg p-2 text-ink-muted hover:bg-sand-100">
          <XIcon className="h-4 w-4" />
        </button>
        <button
          onClick={stopRecording}
          className="flex items-center gap-1.5 rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-white hover:bg-danger/90"
        >
          <MicOffIcon className="h-4 w-4" />
          Stop
        </button>
      </div>
    );
  }

  // Recorded preview UI
  if (recordedBlob) {
    return (
      <div className="flex items-center gap-3 border-t border-sand-200 bg-white px-4 py-3">
        <audio src={recordedUrl || ""} controls className="h-8 flex-1" />
        <button onClick={cancelRecording} className="rounded-lg p-2 text-ink-muted hover:bg-sand-100">
          <XIcon className="h-4 w-4" />
        </button>
        <button
          onClick={sendVoice}
          className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
        >
          <SendIcon className="h-4 w-4" />
          Send voice
        </button>
      </div>
    );
  }

  // File preview UI
  if (selectedFile) {
    return (
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
          <button onClick={cancelFile} className="rounded-lg p-2 text-ink-muted hover:bg-sand-100">
            <XIcon className="h-4 w-4" />
          </button>
          <button
            onClick={sendFile}
            className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
          >
            <SendIcon className="h-4 w-4" />
            Send
          </button>
        </div>
      </div>
    );
  }

  // Default input UI
  return (
    <div className="flex items-end gap-2 border-t border-sand-200 bg-white px-4 py-3">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept="image/*,application/pdf,.doc,.docx,.txt"
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={disabled}
        className="shrink-0 rounded-lg p-2 text-ink-muted transition-colors hover:bg-sand-100 hover:text-ink disabled:opacity-50"
        title="Attach file"
      >
        <PaperclipIcon className="h-5 w-5" />
      </button>
      {onSendVoice && (
        <button
          onClick={startRecording}
          disabled={disabled}
          className="shrink-0 rounded-lg p-2 text-ink-muted transition-colors hover:bg-sand-100 hover:text-ink disabled:opacity-50"
          title="Record voice message"
        >
          <MicIcon className="h-5 w-5" />
        </button>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
        disabled={disabled}
        rows={1}
        className="min-h-[36px] flex-1 resize-none rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        className="shrink-0 rounded-lg bg-teal-600 p-2 text-white transition-colors hover:bg-teal-700 disabled:opacity-50 disabled:hover:bg-teal-600"
      >
        <SendIcon className="h-5 w-5" />
      </button>
    </div>
  );
}
