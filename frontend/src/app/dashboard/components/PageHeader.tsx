
export function PageHeader({ title, subtitle, imgSrc }: { title: string; subtitle?: string; imgSrc?: string }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-3">
        {imgSrc && <img src={imgSrc} alt="" className="h-8 w-8 rounded-lg object-contain" />}
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
      </div>
      {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
    </div>);

}
