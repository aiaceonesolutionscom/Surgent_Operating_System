import React from "react";
import { Link } from "react-router-dom";
import { CheckCircle2Icon, DownloadIcon, FileTextIcon, PlayIcon, PauseIcon } from "lucide-react";
import type { Session } from "./types";
import type { SessionMessage } from "./types";
import { ChannelIcon } from "./ChannelIcon";
import { CHANNELS } from "../data/channels";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { MessageInput } from "./MessageInput";
import { Toggle } from "../components/Toggle";

const STATUS_LABEL: Record<Session["status"], string> = {
  active: "Active",
  needs_attention: "Needs attention",
  resolved: "Resolved"
};

const STATUS_CLASS: Record<Session["status"], string> = {
  active: "bg-teal-600/10 text-teal-600",
  needs_attention: "bg-danger/10 text-danger",
  resolved: "bg-success/10 text-success"
};

function AudioPlayer({ url }: { url: string }) {
  const [playing, setPlaying] = React.useState(false);
  const audioRef = React.useRef<HTMLAudioElement>(null);

  const toggle = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setPlaying(!playing);
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={toggle}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/20 transition-colors hover:bg-white/30"
      >
        {playing ? <PauseIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
      </button>
      <audio ref={audioRef} src={url} onEnded={() => setPlaying(false)} className="hidden" />
      <div className="h-1 w-24 rounded-full bg-white/30">
        <div className="h-full w-0 rounded-full bg-white transition-all" />
      </div>
    </div>
  );
}

function MessageContent({ message }: { message: SessionMessage }) {
  const { contentType, extraData, text } = message;

  if (contentType === "audio" && extraData?.audio_url) {
    return (
      <div className="space-y-1">
        <p className="text-xs opacity-70">Voice message</p>
        <AudioPlayer url={extraData.audio_url as string} />
        {extraData.transcription ? (
          <p className="mt-1 text-xs opacity-70 italic">"{String(extraData.transcription)}"</p>
        ) : null}
      </div>
    );
  }

  if (contentType === "image" && extraData?.image_url) {
    return (
      <div className="space-y-1">
        <img
          src={extraData.image_url as string}
          alt="Shared image"
          className="max-h-48 rounded-lg object-cover"
          loading="lazy"
        />
        {text && text !== "[Image]" && <p className="text-sm">{text}</p>}
      </div>
    );
  }

  if (contentType === "file" && extraData?.file_url) {
    return (
      <a
        href={extraData.file_url as string}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 underline-offset-2 hover:underline"
      >
        <FileTextIcon className="h-4 w-4 shrink-0" />
        <span className="text-sm">{(extraData.filename as string) || "Download file"}</span>
        <DownloadIcon className="h-3 w-3 shrink-0 opacity-60" />
      </a>
    );
  }

  if (contentType === "video" && extraData?.video_url) {
    return (
      <div className="space-y-1">
        <video
          src={extraData.video_url as string}
          controls
          className="max-h-48 rounded-lg"
        />
        {text && text !== "[Video]" && <p className="text-sm">{text}</p>}
      </div>
    );
  }

  return <>{text}</>;
}

const SELF_ROLES: Array<SessionMessage["from"]> = ["agent", "staff", "system"];

export function SessionDetailPane({
  session,
  onResolve,
  onSendMessage,
  onToggleAi,
}: {
  session: Session;
  onResolve?: (sessionId: string) => void;
  onSendMessage?: (sessionId: string, body: string) => Promise<void>;
  // Accepted for interface-compatibility with SessionsView's callbacks. For
  // WhatsApp sessions it powers the per-conversation "AI replying" toggle
  // (the AI Receptionist pauses auto-reply once a human replies — this is
  // how staff hand control back, and is the manual half of the AI-pause
  // mechanism in ConversationsService). Portal/other channels have no AI
  // auto-reply to pause, so the toggle is hidden there.
  onToggleAi?: (sessionId: string, paused: boolean) => Promise<void>;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-sand-200 px-6 py-4">
        <Link to={DASHBOARD_ROUTES.patientDetail(session.patientId)} className="group flex items-center gap-3">
          {session.avatarUrl ? (
            <img src={session.avatarUrl} alt="" className="h-10 w-10 rounded-full object-cover" />
          ) : (
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-sand-200 text-sm font-bold text-ink-soft">
              {session.patientInitial}
            </span>
          )}
          <div>
            <p className="text-sm font-bold text-ink group-hover:text-teal-600">{session.patientName}</p>
            <div className="flex items-center gap-1.5">
              <ChannelIcon channel={session.channel} size={10} />
              <p className="text-xs text-ink-muted">
                {CHANNELS[session.channel].label} · handled by {session.agentName}
              </p>
            </div>
          </div>
        </Link>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_CLASS[session.status]}`}>
          {STATUS_LABEL[session.status]}
        </span>
        {session.channel === "whatsapp" && onToggleAi &&
        <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold ${session.aiPaused ? "text-ink-muted" : "text-success"}`}>
              AI replying
            </span>
            <Toggle
              checked={!session.aiPaused}
              onChange={(on) => onToggleAi(session.id, !on)}
              label="AI replying"
            />
          </div>
        }
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
        {session.messages.map((m) =>
        m.from === "system" ?
        <div key={m.id} className="flex items-center justify-center gap-2 text-xs font-medium text-ink-muted">
              <CheckCircle2Icon className="h-3.5 w-3.5" />
              {m.text}
            </div> :

        <div key={m.id} className={`flex ${SELF_ROLES.includes(m.from) ? "justify-end" : "justify-start"}`}>
              <div
            className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            SELF_ROLES.includes(m.from) ? "bg-teal-600 text-white" : "bg-sand-100 text-ink"}`
            }>

                <MessageContent message={m} />
              </div>
            </div>

        )}
      </div>

      {session.status === "needs_attention" && onResolve &&
      <div className="border-b border-sand-200 px-6 py-3">
          <button
            onClick={() => onResolve(session.id)}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-teal-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
            <CheckCircle2Icon className="h-4 w-4" /> Mark as resolved
          </button>
        </div>
      }

      {onSendMessage && <MessageInput onSendText={(text) => onSendMessage(session.id, text)} />}
    </div>);

}
