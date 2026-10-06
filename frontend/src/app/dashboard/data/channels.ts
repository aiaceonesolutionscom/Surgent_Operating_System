import { FaInstagram, FaWhatsapp, FaFacebook, FaPhone, FaComments, FaCommentSms, FaEnvelope } from "react-icons/fa6";
import type { IconType } from "react-icons";

export type ChannelId = "instagram" | "whatsapp" | "facebook" | "phone" | "web_chat" | "sms" | "email";

export interface ChannelMeta {
  id: ChannelId;
  label: string;
  icon: IconType;
  color: string;
}

// Same brand icons/colors as the marketing site's Omnichannel.tsx — the
// dashboard and marketing site should read as the same product, not two.
export const CHANNELS: Record<ChannelId, ChannelMeta> = {
  instagram: { id: "instagram", label: "Instagram", icon: FaInstagram, color: "#D6336C" },
  whatsapp: { id: "whatsapp", label: "WhatsApp", icon: FaWhatsapp, color: "#25D366" },
  facebook: { id: "facebook", label: "Facebook", icon: FaFacebook, color: "#1877F2" },
  // Phone/web-chat aren't real third-party brands (unlike the platforms
  // above, which keep their actual brand colors for recognizability) — these
  // fold into the site's own primary/secondary pair instead of an arbitrary
  // unrelated hue.
  phone: { id: "phone", label: "Phone", icon: FaPhone, color: "#0B6362" },
  web_chat: { id: "web_chat", label: "Web chat", icon: FaComments, color: "#C9A24B" },
  sms: { id: "sms", label: "SMS", icon: FaCommentSms, color: "#6366F1" },
  email: { id: "email", label: "Email", icon: FaEnvelope, color: "#64748B" }
};

// Shown when the API reports a channel we have no icon for. Rendering an
// unrecognised channel as "Web chat" is far better than letting
// `CHANNELS[channel].icon` throw and white-screen the whole dashboard.
const FALLBACK_CHANNEL: ChannelId = "web_chat";

/**
 * Coerce whatever the API sent into a known ChannelId. The backend enum and
 * older stored rows are UPPERCASE ("WHATSAPP"), and other producers use dashes
 * or spaces ("web-chat"), so normalise before looking the channel up.
 */
export function toChannelId(raw: unknown): ChannelId {
  if (typeof raw !== "string") return FALLBACK_CHANNEL;
  const key = raw.trim().toLowerCase().replace(/[\s-]+/g, "_") as ChannelId;
  return CHANNELS[key] ? key : FALLBACK_CHANNEL;
}

/** Always-defined channel metadata, for render sites that used to index CHANNELS directly. */
export function channelMeta(raw: unknown): ChannelMeta {
  return CHANNELS[toChannelId(raw)];
}

