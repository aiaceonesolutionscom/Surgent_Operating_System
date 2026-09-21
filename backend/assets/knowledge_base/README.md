# Knowledge base — clinic operating documents

Source-of-truth documents the product's agent behaviour is derived from. They live
**outside `src/`** on purpose: they are content, not code. `src/` is importable Python;
nothing here is imported, and nothing here should ever ship inside the application image.

> These are the vendor/clinic-authored editions (AceOne — Aiaceone Clinic OS, v2.0
> International). Text is extracted with `pdftotext -layout <file> -` when you need to
> quote it; there is no parser in the codebase and no vector store behind this folder.

## Contents

| Document | What it is | Wired into |
| --- | --- | --- |
| `Front-Desk-Call-Script-SOP.pdf` | The master SOP: locale/market detection (s3), data to capture (s4), the seven-step flow (s5), word-for-word scripts (s6), price-quoting rules (s7), objections (s8), booking/deposit/time zones (s9), escalation + per-market compliance (s10), follow-up cadence & quiet hours (s11), do/don't word list (s12), KPIs (s13), Appendix A prompt skeleton, Appendix B intents/slots | `src/services/ai_receptionist/markets.py`, `src/services/ai_receptionist/locale_service.py`, `src/services/ai_receptionist/prompt_blocks.py` (consumed by `src/services/channels/inbound_service.py`) |
| `Aesthetic-Fee-Schedule-Benchmark-2026.pdf` | Per-market fee ranges for the common aesthetic procedures, four currencies | Reference for a practice's `settings["markets"][<code>]["prices"]`. Not hardcoded — see the note below |
| `Aesthetics-Intake.pdf` | Intake / medical-history form fields | `Patient` (gender, pregnancy_status, allergies, current_medications, emergency contact, regular physician, height/weight — see models/patient.py's "Clinical intake depth" section), the AI receptionist's `record_intake_field` tool (`services/channels/inbound_service.py`), `prompt_blocks.py`'s BASIC INTAKE block, and `VisitDocumentService` / `visit_document_pdf_service.py`'s generated intake-summary PDF |
| `Consent-Form.pdf.pdf` | Consent wording and the signature block | `ConsentTemplate.sections` / `ConsentDocument.sections` (structured per-treatment-type clause groups, admin-configurable), `services/consent/consent_pdf_service.py`'s generated signed-consent PDF, snapshotted onto `ConsentDocument.file_url` at signing time |
| `DBL-HIPAA-Compliance-Checklist-2026.pdf.pdf` | HIPAA readiness checklist | `AuditLog`, photo consent (`PatientPhoto.is_marketing_approved`), data-subject handling |
| `Post-procedure aftercare patient handout HCE A4.pdf.pdf` | Patient-facing aftercare instructions per procedure | `RecoveryJournal` / `RecoveryCheckIn` patient messaging — clinical content, human-approved before sending |

## Rules for using this folder

1. **Never invent a price.** The SOP (s7, s10.1) forbids quoting a figure that is not on
   the relevant market's approved list, and forbids converting currencies. Prices therefore
   live in `Practice.settings["markets"][<code>]["prices"]`, typed in by the practice owner
   on the AI Receptionist monitor ("Markets, currencies & approved prices") — the benchmark
   PDF above is *input to that decision*, never a runtime source.
2. **Never machine-translate clinical, consent or policy text at runtime** (s3.4). A
   translation is selected, not generated.
3. **Keep the version.** When a document is superseded, add the new file and delete the old
   one in the same change; the SOP references itself by section number, and code comments
   cite those section numbers.
4. **Diff before you delete.** Prompt text derived from this folder carries a comment naming
   the section it came from, so a document revision can be traced to the affected code.
