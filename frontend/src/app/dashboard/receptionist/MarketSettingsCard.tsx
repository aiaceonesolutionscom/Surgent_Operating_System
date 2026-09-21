import { useEffect, useMemo, useState } from "react";
import { CheckIcon, PlusIcon, RefreshCwIcon, TrashIcon, AlertTriangleIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import {
  clearAIReceptionistMarket,
  getAIReceptionistMarkets,
  saveAIReceptionistMarket,
  type ClinicLocation,
  type MarketSettings,
  type MarketsSettingsResponse
} from "../../../api/entities";

// Per-market configuration for the WhatsApp receptionist (SOP s3.4, s7, s10.1).
//
// Why this matters more than it looks: the receptionist is told never to state a
// price that is not on the approved list for the market it routed the patient
// to, and never to convert currencies. So a market left blank makes the AI
// answer "let me confirm that for you" instead of inventing a number — which is
// the safe behaviour, but the practice should be able to see it is happening and
// fix it here. The currency, clinic city, price list and payment methods below
// are exactly what goes into that market's prompt block.

interface PriceRow {
  name: string;
  price: string;
}

interface MarketForm {
  currency: string;
  clinicName: string;
  clinics: ClinicLocation[];
  consultationFee: string;
  paymentMethods: string;
  languages: string[];
  customLanguage: string;
  priceRows: PriceRow[];
}

// Fixed shortcuts matching the codes the AI receptionist itself already
// routes on (see backend/src/services/ai_receptionist/markets.py's
// language_code / detect_language) — picking "Urdu" here isn't just a label,
// it tells the receptionist this clinic actually offers that language
// rather than only mirroring what a patient happens to type.
const LANGUAGE_SHORTCUTS: { key: string; label: string }[] = [
  { key: "E", label: "English" },
  { key: "U", label: "Urdu" },
  { key: "R", label: "Roman Urdu" },
  { key: "A", label: "Arabic" },
  { key: "S", label: "Spanish" }
];

function formFrom(market: MarketSettings): MarketForm {
  return {
    currency: market.currency,
    clinicName: market.clinic_name ?? "",
    // Defensive against a stale/older API response that predates `clinics`
    // (e.g. a backend not yet restarted with this field) — never crash the
    // whole card over one missing key.
    clinics: (market.clinics ?? []).length > 0 ? market.clinics : market.clinic_city ? [{ city: market.clinic_city, address: "" }] : [],
    consultationFee: market.consultation_fee ?? "",
    paymentMethods: market.payment_methods ?? "",
    languages: market.languages ?? [],
    customLanguage: "",
    priceRows: Object.entries(market.prices).map(([name, price]) => ({ name, price }))
  };
}

export function MarketSettingsCard() {
  const { authedFetch, role } = usePlan();
  const canEdit = role === "owner";
  const [data, setData] = useState<MarketsSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [selectedCode, setSelectedCode] = useState<string>("PK");
  const [form, setForm] = useState<MarketForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [flashError, setFlashError] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    getAIReceptionistMarkets(authedFetch)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        // Land on the market that actually matters to this practice: its home
        // market, the one a message with no usable signal routes to.
        setSelectedCode(response.home_market ?? response.markets[0]?.code ?? "PK");
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const selected = useMemo(
    () => data?.markets.find((market) => market.code === selectedCode) ?? null,
    [data, selectedCode]
  );

  // Re-seed the form whenever the selected market (or freshly saved data)
  // changes, so the fields always show what is actually stored.
  useEffect(() => {
    setForm(selected ? formFrom(selected) : null);
    setFlash(null);
  }, [selected]);

  // Start a never-configured market straight in edit mode (there's nothing
  // to summarize yet); a market that already has something saved opens
  // collapsed to a summary, with an explicit Edit button — save() below
  // collapses it again afterward. Deliberately keyed only on switching
  // markets, not on `data` itself, so a fresh save (which also replaces
  // `data`) doesn't silently reopen the form out from under the Owner.
  useEffect(() => {
    setIsEditing(!data?.markets.find((market) => market.code === selectedCode)?.configured);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCode]);

  const note = (message: string, isError = false) => {
    setFlash(message);
    setFlashError(isError);
  };

  const setField = <K extends keyof MarketForm>(key: K, value: MarketForm[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  const setPriceRow = (index: number, patch: Partial<PriceRow>) => {
    setForm((current) => {
      if (!current) return current;
      const priceRows = current.priceRows.map((row, i) => (i === index ? { ...row, ...patch } : row));
      return { ...current, priceRows };
    });
  };

  const toggleLanguage = (label: string) => {
    setForm((current) => {
      if (!current) return current;
      const has = current.languages.includes(label);
      return { ...current, languages: has ? current.languages.filter((l) => l !== label) : [...current.languages, label] };
    });
  };

  const addCustomLanguage = () => {
    setForm((current) => {
      if (!current) return current;
      const value = current.customLanguage.trim();
      if (!value || current.languages.includes(value)) return { ...current, customLanguage: "" };
      return { ...current, languages: [...current.languages, value], customLanguage: "" };
    });
  };

  const removeLanguage = (label: string) => setForm((c) => (c ? { ...c, languages: c.languages.filter((l) => l !== label) } : c));

  const addClinic = () => setForm((c) => (c ? { ...c, clinics: [...c.clinics, { city: "", address: "" }] } : c));

  const setClinic = (index: number, patch: Partial<ClinicLocation>) => {
    setForm((current) => {
      if (!current) return current;
      const clinics = current.clinics.map((row, i) => (i === index ? { ...row, ...patch } : row));
      return { ...current, clinics };
    });
  };

  const removeClinic = (index: number) => setForm((c) => (c ? { ...c, clinics: c.clinics.filter((_, i) => i !== index) } : c));

  const addPriceRow = () => setForm((c) => (c ? { ...c, priceRows: [...c.priceRows, { name: "", price: "" }] } : c));

  const removePriceRow = (index: number) =>
    setForm((c) => (c ? { ...c, priceRows: c.priceRows.filter((_, i) => i !== index) } : c));

  const save = async (isHome: boolean) => {
    if (!authedFetch || !selected || !form) return;
    setSaving(true);
    try {
      const prices: Record<string, string> = {};
      form.priceRows.forEach((row) => {
        const name = row.name.trim();
        const price = row.price.trim();
        if (name && price) prices[name] = price;
      });
      const clinics = form.clinics
        .map((c) => ({ city: c.city.trim(), address: (c.address ?? "").trim() || null }))
        .filter((c) => c.city);
      const response = await saveAIReceptionistMarket(authedFetch, selected.code, {
        currency: form.currency,
        clinic_name: form.clinicName,
        clinics,
        consultation_fee: form.consultationFee,
        payment_methods: form.paymentMethods,
        prices,
        languages: form.languages,
        is_home: isHome
      });
      setData(response);
      setIsEditing(false);
      note(
        isHome
          ? `${selected.label} saved and set as your home market — new messages with no clear location route here.`
          : `${selected.label} saved — the receptionist quotes from this from the next message.`
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      note(detail ? `Couldn't save: ${detail}` : "Couldn't save — try again.", true);
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    if (!authedFetch || !selected) return;
    setSaving(true);
    try {
      const response = await clearAIReceptionistMarket(authedFetch, selected.code);
      setData(response);
      note(`${selected.label} cleared — the receptionist will stop quoting for it rather than quoting old figures.`);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "";
      note(detail ? `Couldn't clear: ${detail}` : "Couldn't clear — try again.", true);
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    "w-full rounded-xl border border-sand-200 bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-teal-500/40 disabled:bg-sand-50 disabled:text-ink-muted";

  return (
    <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div>
        <p className="text-sm font-bold text-ink">Markets, currencies &amp; approved prices</p>
        <p className="mt-0.5 text-xs text-ink-muted">
          {canEdit
            ? "What the receptionist is allowed to quote, per market. A market with no price list is told never to name a figure — it will offer a confirmation instead."
            : "Read-only for you — only the practice owner can change prices and currencies."}
        </p>
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-ink-muted">Loading…</p>
      ) : failed || !data ? (
        <p className="mt-4 text-sm text-ink-muted">Couldn't load market settings.</p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            {data.markets.map((market) => (
              <button
                key={market.code}
                onClick={() => setSelectedCode(market.code)}
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                  market.code === selectedCode
                    ? "border-teal-500 bg-teal-50 text-teal-700"
                    : "border-sand-200 text-ink-soft hover:border-teal-300 hover:text-teal-700"
                }`}>
                {market.label}
                {market.is_home && <span className="ml-1.5 text-[10px] uppercase tracking-wide text-teal-600">home</span>}
                {!market.configured && <span className="ml-1.5 text-[10px] uppercase tracking-wide text-amber-600">not set</span>}
              </button>
            ))}
          </div>

          {selected && form && !isEditing && (
            <div className="mt-5 rounded-2xl border border-sand-200 bg-sand-50/50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1 text-sm text-ink-soft">
                  <p>
                    <span className="font-semibold text-ink">Currency:</span> {selected.currency}
                  </p>
                  <p>
                    <span className="font-semibold text-ink">
                      {form.clinics.length > 1 ? "Clinics:" : "Clinic:"}
                    </span>{" "}
                    {form.clinics.length > 0 ? form.clinics.map((c) => c.city).join(", ") : "Not set"}
                  </p>
                  <p>
                    <span className="font-semibold text-ink">Approved prices:</span>{" "}
                    {form.priceRows.length > 0 ? `${form.priceRows.length} procedure${form.priceRows.length === 1 ? "" : "s"}` : "None yet"}
                  </p>
                  <p>
                    <span className="font-semibold text-ink">Languages:</span>{" "}
                    {form.languages.length > 0 ? form.languages.join(", ") : "Not set"}
                  </p>
                </div>
                {canEdit && (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="flex shrink-0 items-center gap-1.5 rounded-full border border-sand-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-300 hover:text-teal-700">
                    Edit
                  </button>
                )}
              </div>
              {flash && <p className={`mt-3 text-xs font-semibold ${flashError ? "text-red-600" : "text-teal-700"}`}>{flash}</p>}
            </div>
          )}

          {selected && form && isEditing && (
            <div className="mt-5">
              {!selected.configured && (
                <div className="mb-4 flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-3">
                  <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <p className="text-xs text-amber-800">
                    Nothing configured for {selected.label} yet. Patients routed here are answered in{" "}
                    {selected.language_label}, but the receptionist will not state any price or estimate — it will say
                    the team will confirm. Add your approved prices below to let it quote.
                  </p>
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="text-xs font-semibold text-ink-soft">Currency</span>
                  <select
                    value={form.currency}
                    disabled={!canEdit}
                    onChange={(event) => setField("currency", event.target.value)}
                    className={`mt-1 ${inputClass}`}>
                    {data.supported_currencies.map((currency) => (
                      <option key={currency} value={currency}>
                        {currency}
                        {currency === selected.default_currency ? " (default for " + selected.label + ")" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-ink-soft">Clinic name for this market</span>
                  <input
                    value={form.clinicName}
                    disabled={!canEdit}
                    onChange={(event) => setField("clinicName", event.target.value)}
                    placeholder="Defaults to your practice name"
                    className={`mt-1 ${inputClass}`}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-ink-soft">Consultation fee</span>
                  <input
                    value={form.consultationFee}
                    disabled={!canEdit}
                    onChange={(event) => setField("consultationFee", event.target.value)}
                    placeholder={`e.g. ${form.currency} 5,000 — adjusted against treatment`}
                    className={`mt-1 ${inputClass}`}
                  />
                </label>
                <label className="block sm:col-span-2">
                  <span className="text-xs font-semibold text-ink-soft">Approved payment methods</span>
                  <input
                    value={form.paymentMethods}
                    disabled={!canEdit}
                    onChange={(event) => setField("paymentMethods", event.target.value)}
                    placeholder="e.g. Bank transfer or card at the clinic"
                    className={`mt-1 ${inputClass}`}
                  />
                  <span className="mt-1 block text-[11px] text-ink-muted">
                    Only what you list here may be offered. Card details are never taken in a chat message.
                  </span>
                </label>
                <div className="block sm:col-span-2">
                  <span className="text-xs font-semibold text-ink-soft">Languages spoken at this clinic</span>
                  <p className="mt-0.5 text-[11px] text-ink-muted">
                    Trains the receptionist on which languages this clinic actually offers, on top of mirroring whatever
                    a patient types. Click to toggle, or add your own below.
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {LANGUAGE_SHORTCUTS.map(({ key, label }) => {
                      const active = form.languages.includes(label);
                      return (
                        <button
                          key={key}
                          type="button"
                          disabled={!canEdit}
                          onClick={() => toggleLanguage(label)}
                          className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                            active
                              ? "border-teal-500 bg-teal-50 text-teal-700"
                              : "border-sand-200 text-ink-soft hover:border-teal-300 hover:text-teal-700"
                          }`}>
                          <span
                            className={`flex h-4 w-4 items-center justify-center rounded text-[10px] font-bold ${
                              active ? "bg-teal-600 text-white" : "bg-sand-100 text-ink-muted"
                            }`}>
                            {key}
                          </span>
                          {label}
                        </button>
                      );
                    })}
                  </div>
                  {form.languages.some((l) => !LANGUAGE_SHORTCUTS.some((s) => s.label === l)) && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {form.languages
                        .filter((l) => !LANGUAGE_SHORTCUTS.some((s) => s.label === l))
                        .map((label) => (
                          <span
                            key={label}
                            className="flex items-center gap-1.5 rounded-full border border-teal-500 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700">
                            {label}
                            {canEdit && (
                              <button type="button" onClick={() => removeLanguage(label)} aria-label={`Remove ${label}`} className="text-teal-500 hover:text-teal-800">
                                ×
                              </button>
                            )}
                          </span>
                        ))}
                    </div>
                  )}
                  {canEdit && (
                    <div className="mt-2 flex items-center gap-2">
                      <input
                        value={form.customLanguage}
                        onChange={(event) => setField("customLanguage", event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            addCustomLanguage();
                          }
                        }}
                        placeholder="Other language, e.g. French"
                        className={inputClass}
                      />
                      <button
                        type="button"
                        onClick={addCustomLanguage}
                        className="flex shrink-0 items-center gap-1 rounded-full border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-300 hover:text-teal-700">
                        <PlusIcon className="h-3.5 w-3.5" /> Add
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-ink-soft">Clinic locations</p>
                    <p className="mt-0.5 text-[11px] text-ink-muted">
                      More than one branch in this market? Add each city with its full address so the receptionist can
                      name the right one instead of just the country.
                    </p>
                  </div>
                  {canEdit && (
                    <button
                      onClick={addClinic}
                      className="flex shrink-0 items-center gap-1 rounded-full border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-300 hover:text-teal-700">
                      <PlusIcon className="h-3.5 w-3.5" /> Add location
                    </button>
                  )}
                </div>

                {form.clinics.length === 0 ? (
                  <p className="mt-3 rounded-2xl bg-sand-50 p-3 text-xs text-ink-muted">
                    No clinic location set for {selected.label} yet — the receptionist will only name the market, not a
                    specific city or address.
                  </p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {form.clinics.map((clinic, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <input
                          value={clinic.city}
                          disabled={!canEdit}
                          onChange={(event) => setClinic(index, { city: event.target.value })}
                          placeholder="City, e.g. Lahore"
                          className={inputClass}
                        />
                        <input
                          value={clinic.address ?? ""}
                          disabled={!canEdit}
                          onChange={(event) => setClinic(index, { address: event.target.value })}
                          placeholder="Full address (optional)"
                          className={inputClass}
                        />
                        {canEdit && (
                          <button
                            onClick={() => removeClinic(index)}
                            aria-label="Remove clinic location"
                            className="shrink-0 rounded-full border border-sand-200 p-2 text-ink-muted transition-colors hover:border-red-300 hover:text-red-500">
                            <TrashIcon className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-ink-soft">Approved price list</p>
                    <p className="mt-0.5 text-[11px] text-ink-muted">
                      The receptionist always says “starts from”. Write the figure with its currency (that&rsquo;s just a
                      format example below, not a real price — this list starts empty until you add your own).
                    </p>
                  </div>
                  {canEdit && (
                    <button
                      onClick={addPriceRow}
                      className="flex items-center gap-1 rounded-full border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-300 hover:text-teal-700">
                      <PlusIcon className="h-3.5 w-3.5" /> Add procedure
                    </button>
                  )}
                </div>

                {form.priceRows.length === 0 ? (
                  <p className="mt-3 rounded-2xl bg-sand-50 p-3 text-xs text-ink-muted">
                    No approved prices yet — the receptionist will not quote a figure for {selected.label}.
                  </p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {form.priceRows.map((row, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <input
                          value={row.name}
                          disabled={!canEdit}
                          onChange={(event) => setPriceRow(index, { name: event.target.value })}
                          placeholder="Procedure, e.g. Rhinoplasty"
                          className={inputClass}
                        />
                        <input
                          value={row.price}
                          disabled={!canEdit}
                          onChange={(event) => setPriceRow(index, { price: event.target.value })}
                          placeholder={`Starts from, e.g. ${form.currency} 900,000`}
                          className={inputClass}
                        />
                        {canEdit && (
                          <button
                            onClick={() => removePriceRow(index)}
                            aria-label="Remove price"
                            className="shrink-0 rounded-full border border-sand-200 p-2 text-ink-muted transition-colors hover:border-red-300 hover:text-red-500">
                            <TrashIcon className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-5 rounded-2xl bg-sand-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  How patients are routed here
                </p>
                <p className="mt-1 text-xs text-ink-soft">
                  {selected.timezone} · {selected.consult_format} · regulated by {selected.regulator}
                </p>
                <p className="mt-1 text-xs text-ink-muted">{selected.advertising_note}</p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  This only limits messages the AI sends on its own (reminders, follow-ups) — 09:00-21:00 in the
                  patient's own local time, so nobody gets pinged at 3am. It always replies instantly, any hour, the
                  moment a patient messages first.
                </p>
              </div>

              {canEdit && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => void save(false)}
                    disabled={saving}
                    className="flex items-center gap-1.5 rounded-full bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-60">
                    {saving ? <RefreshCwIcon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />} Save
                  </button>
                  {!selected.is_home && (
                    <button
                      onClick={() => void save(true)}
                      disabled={saving}
                      className="rounded-full border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-300 hover:text-teal-700 disabled:opacity-60">
                      Save &amp; make {selected.label} my home market
                    </button>
                  )}
                  {selected.configured && (
                    <button
                      onClick={() => void clear()}
                      disabled={saving}
                      className="text-xs font-semibold text-red-500 hover:text-red-600 disabled:opacity-60">
                      Clear this market
                    </button>
                  )}
                  {selected.configured && (
                    <button
                      onClick={() => {
                        setForm(formFrom(selected));
                        setIsEditing(false);
                      }}
                      disabled={saving}
                      className="ml-auto text-xs font-semibold text-ink-muted hover:text-ink disabled:opacity-60">
                      Cancel
                    </button>
                  )}
                </div>
              )}

              {flash && (
                <p className={`mt-3 text-xs font-semibold ${flashError ? "text-red-600" : "text-teal-700"}`}>{flash}</p>
              )}
            </div>
          )}

          {data.updated_at && (
            <p className="mt-3 text-[11px] text-ink-muted">
              Last changed {new Date(data.updated_at).toLocaleString()}
            </p>
          )}
        </>
      )}
    </div>
  );
}
