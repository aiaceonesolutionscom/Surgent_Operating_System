import { PlusIcon, TrashIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import { useState } from "react";

// Mirrors backend/src/models/consent_document.py's ConsentTemplate.sections
// JSONB shape exactly — this builder edits that structure directly (no JSON
// text in between), matching what the consent PDF generator
// (services/consent/consent_pdf_service.py) reads section by section.
export interface ClauseGroup {
  heading: string;
  clauses: string[];
}
export interface TreatmentSection {
  treatment_type: string;
  clause_groups: ClauseGroup[];
}
export interface ConsentSections {
  treatment_sections: TreatmentSection[];
  photography_consent?: {
    records_consent_clause?: string;
    marketing_consent_optional?: boolean;
    anonymization_optional?: boolean;
  };
  patient_statement?: { clauses: string[] };
}

const EMPTY_SECTIONS: ConsentSections = {
  treatment_sections: [],
  photography_consent: { records_consent_clause: "", marketing_consent_optional: true, anonymization_optional: true },
  patient_statement: { clauses: [] }
};

const inputClass = "w-full rounded-lg border border-sand-200 bg-white px-3 py-1.5 text-sm text-ink outline-none focus:border-teal-600/40";

function StringListEditor({
  items, onChange, placeholder
}: {
  items: string[]; onChange: (items: string[]) => void; placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      {items.map((clause, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <input
            value={clause}
            onChange={(e) => {
              const next = [...items];
              next[i] = e.target.value;
              onChange(next);
            }}
            placeholder={placeholder}
            className={inputClass} />
          <button type="button" onClick={() => onChange(items.filter((_, idx) => idx !== i))} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100 hover:text-danger">
            <TrashIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...items, ""])}
        className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
        <PlusIcon className="h-3 w-3" /> Add line
      </button>
    </div>);

}

function ClauseGroupEditor({
  group, onChange, onRemove
}: {
  group: ClauseGroup; onChange: (group: ClauseGroup) => void; onRemove: () => void;
}) {
  return (
    <div className="rounded-lg border border-sand-200 bg-sand-50/50 p-3">
      <div className="mb-2 flex items-center gap-2">
        <input
          value={group.heading}
          onChange={(e) => onChange({ ...group, heading: e.target.value })}
          placeholder="e.g. I understand that:"
          className={`${inputClass} font-semibold`} />
        <button type="button" onClick={onRemove} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100 hover:text-danger">
          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      <StringListEditor items={group.clauses} onChange={(clauses) => onChange({ ...group, clauses })} placeholder="A specific risk/consent statement" />
    </div>);

}

function TreatmentSectionEditor({
  section, onChange, onRemove
}: {
  section: TreatmentSection; onChange: (section: TreatmentSection) => void; onRemove: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);

  function updateGroup(i: number, group: ClauseGroup) {
    const next = [...section.clause_groups];
    next[i] = group;
    onChange({ ...section, clause_groups: next });
  }

  return (
    <div className="rounded-xl border border-sand-200 bg-white">
      <div className="flex items-center gap-2 border-b border-sand-100 px-3.5 py-2.5">
        <button type="button" onClick={() => setCollapsed((v) => !v)} className="text-ink-muted hover:text-ink">
          {collapsed ? <ChevronRightIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
        </button>
        <input
          value={section.treatment_type}
          onChange={(e) => onChange({ ...section, treatment_type: e.target.value })}
          placeholder="e.g. Botulinum Toxin Treatment"
          className={`${inputClass} flex-1 font-semibold`} />
        <button type="button" onClick={onRemove} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100 hover:text-danger">
          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      {!collapsed &&
      <div className="space-y-2.5 p-3.5">
          {section.clause_groups.map((group, i) =>
        <ClauseGroupEditor
          key={i}
          group={group}
          onChange={(g) => updateGroup(i, g)}
          onRemove={() => onChange({ ...section, clause_groups: section.clause_groups.filter((_, idx) => idx !== i) })} />

        )}
          <button
          type="button"
          onClick={() => onChange({ ...section, clause_groups: [...section.clause_groups, { heading: "", clauses: [""] }] })}
          className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
            <PlusIcon className="h-3 w-3" /> Add clause group
          </button>
        </div>
      }
    </div>);

}

// The structured, admin-configurable consent editor — replaces a raw JSON
// textarea entirely. `value` is null when a template is plain free-text
// wording only (the `body` field alone); toggling this on gives it real
// per-treatment-type clause groups the consent PDF generator renders.
export function ConsentSectionsBuilder({
  value, onChange
}: {
  value: ConsentSections | null; onChange: (value: ConsentSections | null) => void;
}) {
  const enabled = value !== null;
  const sections = value ?? EMPTY_SECTIONS;

  function updateTreatmentSection(i: number, section: TreatmentSection) {
    const next = [...sections.treatment_sections];
    next[i] = section;
    onChange({ ...sections, treatment_sections: next });
  }

  return (
    <div>
      <label className="flex items-center gap-2 text-sm font-semibold text-ink">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked ? EMPTY_SECTIONS : null)}
          className="h-4 w-4 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
        Use structured sections for this template
      </label>
      <p className="mt-1 text-[11px] text-ink-muted">
        Per-treatment clause groups drive the generated, signed consent PDF. Leave off to use the plain wording above only.
      </p>

      {enabled &&
      <div className="mt-3 space-y-4 rounded-2xl border border-sand-200 bg-sand-50/30 p-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Treatment sections</p>
            <div className="space-y-3">
              {sections.treatment_sections.map((section, i) =>
            <TreatmentSectionEditor
              key={i}
              section={section}
              onChange={(s) => updateTreatmentSection(i, s)}
              onRemove={() => onChange({ ...sections, treatment_sections: sections.treatment_sections.filter((_, idx) => idx !== i) })} />

            )}
            </div>
            <button
            type="button"
            onClick={() => onChange({ ...sections, treatment_sections: [...sections.treatment_sections, { treatment_type: "", clause_groups: [] }] })}
            className="mt-2 flex items-center gap-1.5 rounded-lg border border-dashed border-sand-300 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600">
              <PlusIcon className="h-3.5 w-3.5" /> Add treatment section
            </button>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Consent to medical photography</p>
            <textarea
            rows={2}
            value={sections.photography_consent?.records_consent_clause || ""}
            onChange={(e) => onChange({ ...sections, photography_consent: { ...sections.photography_consent, records_consent_clause: e.target.value } })}
            placeholder="I consent to clinical photographs being taken for my medical record."
            className={inputClass} />
            <div className="mt-2 flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-xs text-ink-soft">
                <input
                type="checkbox"
                checked={sections.photography_consent?.marketing_consent_optional ?? true}
                onChange={(e) => onChange({ ...sections, photography_consent: { ...sections.photography_consent, marketing_consent_optional: e.target.checked } })}
                className="h-3.5 w-3.5 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
                Ask separately for marketing/social-media use
              </label>
              <label className="flex items-center gap-2 text-xs text-ink-soft">
                <input
                type="checkbox"
                checked={sections.photography_consent?.anonymization_optional ?? true}
                onChange={(e) => onChange({ ...sections, photography_consent: { ...sections.photography_consent, anonymization_optional: e.target.checked } })}
                className="h-3.5 w-3.5 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
                Ask whether images should be anonymised
              </label>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Patient statement</p>
            <StringListEditor
            items={sections.patient_statement?.clauses || []}
            onChange={(clauses) => onChange({ ...sections, patient_statement: { clauses } })}
            placeholder="e.g. I have read and understood the possible complications" />
          </div>
        </div>
      }
    </div>);

}
