
export function Toggle({
  checked,
  onChange,
  label,
  disabled



}: {checked: boolean;onChange: (v: boolean) => void;label: string;disabled?: boolean;}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
      checked ? "border-success bg-success" : "border-ink-muted/30 bg-white"}`
      }>

      <span
        className={`inline-block h-4.5 w-4.5 transform rounded-full shadow transition-transform ${
        checked ? "translate-x-[22px] bg-white" : "translate-x-[3px] bg-ink-muted/40"}`
        } />

    </button>);

}
