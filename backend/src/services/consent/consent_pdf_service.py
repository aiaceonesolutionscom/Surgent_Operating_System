from __future__ import annotations
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from src.models.consent_document import ConsentDocument
from src.models.patient import Patient
from src.models.practice import Practice
from src.models.user import User
from src.services.documents.pdf_brand import BRAND, INK, INK_SOFT, TopBar


def _line(label: str, value: str | None) -> str | None:
    if not value:
        return None
    return f"<b>{label}:</b> {value}"


def generate_consent_pdf(
    document: ConsentDocument, patient: Patient, practice: Practice, witness: User | None
) -> bytes:
    """The signed-consent PDF — rendered from the FROZEN snapshot on
    `document` (`sections` if the template had structured clause groups,
    else `content` as plain paragraphs), never re-read live off the
    template, so this always reflects exactly what the patient signed even
    if the template has since moved on to a later version. No file is ever
    written to disk — same in-memory-bytes pattern as every other generator
    here (generate_invoice_pdf, generate_visit_document_pdf)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CTitle", parent=styles["Heading1"], fontSize=18, textColor=INK, spaceAfter=0)
    section_style = ParagraphStyle("CSection", parent=styles["Normal"], fontSize=10, textColor=BRAND, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    heading_style = ParagraphStyle("CHeading", parent=styles["Normal"], fontSize=9.5, textColor=INK, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=2)
    body_style = ParagraphStyle("CBody", parent=styles["Normal"], fontSize=9.5, textColor=INK_SOFT, leading=14)
    sig_style = ParagraphStyle("CSig", parent=styles["Normal"], fontSize=13, textColor=INK, fontName="Helvetica-Oblique")

    elements: list = [TopBar(doc.width + doc.leftMargin + doc.rightMargin), Spacer(1, 10 * mm)]
    elements.append(Paragraph("CONSENT FORM", title_style))
    elements.append(Paragraph(document.document_type.replace("_", " ").title(), ParagraphStyle("CSub", parent=body_style, fontSize=11, textColor=INK)))
    elements.append(Spacer(1, 4 * mm))

    header_lines = [
        _line("Patient", f"{patient.first_name} {patient.last_name}"),
        _line("Date of birth", patient.date_of_birth.strftime("%d %b %Y") if patient.date_of_birth else None),
        _line("Emergency contact", patient.emergency_contact_name),
        _line("Emergency phone", patient.emergency_contact_phone),
        _line("Regular physician", patient.regular_physician_name),
        _line("Physician phone", patient.regular_physician_phone),
    ]
    header_lines = [l for l in header_lines if l]
    elements.append(Paragraph("PATIENT DETAILS", section_style))
    elements.append(Paragraph("<br/>".join(header_lines) if header_lines else "Not on file.", body_style))

    sections = document.sections or {}
    treatment_sections = sections.get("treatment_sections") or []
    if treatment_sections:
        for section in treatment_sections:
            elements.append(Paragraph(str(section.get("treatment_type") or "Treatment").upper(), section_style))
            for group in section.get("clause_groups") or []:
                if group.get("heading"):
                    elements.append(Paragraph(str(group["heading"]), heading_style))
                clauses = group.get("clauses") or []
                if clauses:
                    elements.append(Paragraph("<br/>".join(f"&bull; {c}" for c in clauses), body_style))

        photography = sections.get("photography_consent") or {}
        if photography.get("records_consent_clause"):
            elements.append(Paragraph("CONSENT TO MEDICAL PHOTOGRAPHY", section_style))
            elements.append(Paragraph(str(photography["records_consent_clause"]), body_style))

        statement = sections.get("patient_statement") or {}
        if statement.get("clauses"):
            elements.append(Paragraph("PATIENT STATEMENT", section_style))
            elements.append(Paragraph("<br/>".join(f"&bull; {c}" for c in statement["clauses"]), body_style))
    elif document.content:
        elements.append(Paragraph("CONSENT TEXT", section_style))
        for para in document.content.split("\n"):
            if para.strip():
                elements.append(Paragraph(para, body_style))

    if document.treatment_plan_notes:
        elements.append(Paragraph("TREATMENT PLAN", section_style))
        elements.append(Paragraph(document.treatment_plan_notes, body_style))

    elements.append(Paragraph("TREATMENT RECORD", section_style))
    clinician_name = witness.name if witness and getattr(witness, "name", None) else "—"
    record_lines = [
        _line("Treating clinician", clinician_name),
        _line("Treatment date", document.signed_at.strftime("%d %b %Y") if document.signed_at else None),
    ]
    record_lines = [l for l in record_lines if l]
    elements.append(Paragraph("<br/>".join(record_lines) if record_lines else "—", body_style))

    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph("PATIENT SIGNATURE (typed, staff-witnessed)", heading_style))
    elements.append(Paragraph(document.signed_by_name or "—", sig_style))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("TREATING CLINICIAN SIGNATURE", heading_style))
    elements.append(Paragraph(clinician_name, sig_style))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(BRAND)
        canvas.rect(0, 0, letter[0], 16 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(18 * mm, 6.5 * mm, practice.name)
        canvas.setFont("Helvetica", 8)
        contact = practice.email or ""
        if practice.phone:
            contact = f"{contact}  ·  {practice.phone}" if contact else practice.phone
        canvas.drawRightString(letter[0] - 18 * mm, 6.5 * mm, contact)
        canvas.restoreState()

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
