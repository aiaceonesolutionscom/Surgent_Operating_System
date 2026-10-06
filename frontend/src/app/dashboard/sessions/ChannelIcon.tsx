import { channelMeta, type ChannelId } from "../data/channels";

export function ChannelIcon({ channel, size = 16 }: { channel: ChannelId; size?: number }) {
  const meta = channelMeta(channel);
  const Icon = meta.icon;
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-md text-white"
      style={{ backgroundColor: meta.color, width: size + 12, height: size + 12 }}>

      <Icon style={{ width: size, height: size }} />
    </span>);

}
