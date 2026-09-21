from __future__ import annotations
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from src.models.patient import Patient, PregnancyStatus
from src.models.practice import Practice
from src.models.doctor import Doctor
from src.models.appointment import Appointment
from src.services.documents.pdf_brand import BRAND, INK, INK_SOFT, SAND, HAIRLINE, TopBar


def _line(label: str, value: str | None) -> str | None:
    if not value:
        return None
    return f"<b>{label}:</b> {value}"


def generate_visit_document_pdf(
    patient: Patient, practice: Practice, doctor: Doctor | None, appointment: Appointment | None
) -> bytes:
    """The patient-facing "bring this to your visit" summary — whatever
    structured intake data exists on `patient` (AI-receptionist-collected or
    patient-portal-collected), rendered into one page the patient can print
    or show on their phone, and the same file shared in-app with the
    assigned doctor and receptionist. No file is ever written to disk —
    callers get bytes back, same as generate_invoice_pdf."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("VDTitle", parent=styles["Heading1"], fontSize=18, textColor=INK, spaceAfter=0)
    section_style = ParagraphStyle("VDSection", parent=styles["Normal"], fontSize=10, textColor=BRAND, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("VDBody", parent=styles["Normal"], fontSize=9.5, textColor=INK_SOFT, leading=14)

    elements: list = [TopBar(doc.width + doc.leftMargin + doc.rightMargin), Spacer(1, 10 * mm)]

    elements.append(Paragraph("VISIT SUMMARY", title_style))
    elements.append(Paragraph(f"{patient.first_name} {patient.last_name}", ParagraphStyle("VDSub", parent=body_style, fontSize=11, textColor=INK)))
    elements.append(Spacer(1, 4 * mm))

    # --- Appointment / clinic details -----------------------------------
    appt_lines = []
    if appointment is not None:
        appt_lines.append(_line("Appointment", appointment.start_time.strftime("%A, %d %b %Y — %I:%M %p")))
        appt_lines.append(_line("Type", appointment.appointment_type))
    appt_lines.append(_line("Doctor", doctor.name if doctor else "Not yet assigned"))
    appt_lines.append(_line("Clinic", practice.name))
    appt_lines = [l for l in appt_lines if l]
    if appt_lines:
        elements.append(Paragraph("VISIT DETAILS", section_style))
        elements.append(Paragraph("<br/>".join(appt_lines), body_style))

    # --- Demographics ------------------------------------------------------
    demo_lines = [
        _line("Date of birth", patient.date_of_birth.strftime("%d %b %Y") if patient.date_of_birth else None),
        _line("Gender", patient.gender),
        _line("Occupation", patient.occupation),
        _line("Phone", patient.phone),
    ]
    if patient.pregnancy_status and patient.pregnancy_status != PregnancyStatus.NOT_APPLICABLE:
        demo_lines.append(_line("Pregnancy / nursing status", patient.pregnancy_status.value.replace("_", " ")))
    demo_lines = [l for l in demo_lines if l]
    if demo_lines:
        elements.append(Paragraph("PATIENT DETAILS", section_style))
        elements.append(Paragraph("<br/>".join(demo_lines), body_style))

    # --- Emergency contact / physician --------------------------------
    contact_lines = [
        _line("Emergency contact", f"{patient.emergency_contact_name} ({patient.emergency_contact_relationship})" if patient.emergency_contact_name and patient.emergency_contact_relationship else patient.emergency_contact_name),
        _line("Emergency phone", patient.emergency_contact_phone),
        _line("Regular physician", patient.regular_physician_name),
        _line("Physician phone", patient.regular_physician_phone),
    ]
    contact_lines = [l for l in contact_lines if l]
    if contact_lines:
        elements.append(Paragraph("EMERGENCY CONTACT & PHYSICIAN", section_style))
        elements.append(Paragraph("<br/>".join(contact_lines), body_style))

    # --- Chief complaint --------------------------------------------------
    if patient.chief_complaint:
        elements.append(Paragraph("REASON FOR VISIT", section_style))
        elements.append(Paragraph(patient.chief_complaint, body_style))

    # --- Allergies table ----------------------------------------------
    if patient.allergies:
        elements.append(Paragraph("ALLERGIES", section_style))
        rows = [["Name", "Severity", "Reaction"]]
        for a in patient.allergies:
            rows.append([a.get("name", "—"), a.get("severity", "—"), a.get("reaction", "—")])
        table = Table(rows, colWidths=[doc.width * 0.34, doc.width * 0.22, doc.width * 0.44])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK),
            ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, HAIRLINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("ALLERGIES", section_style))
        elements.append(Paragraph("None reported.", body_style))

    # --- Current medications --------------------------------------------
    if patient.current_medications:
        elements.append(Paragraph("CURRENT MEDICATIONS", section_style))
        rows = [["Name", "Dosage", "Frequency"]]
        for m in patient.current_medications:
            rows.append([m.get("name", "—"), m.get("dosage", "—"), m.get("frequency", "—")])
        table = Table(rows, colWidths=[doc.width * 0.34, doc.width * 0.33, doc.width * 0.33])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK),
            ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, HAIRLINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)

    # --- Doctor-facing AI summary (closing note) --------------------------
    if patient.intake_summary:
        elements.append(Paragraph("PRE-VISIT SUMMARY (for the clinical team)", section_style))
        note_style = ParagraphStyle("VDNote", parent=body_style, backColor=SAND, borderPadding=6)
        elements.append(Paragraph(patient.intake_summary, note_style))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "Please bring this summary to your visit. If any of the above has changed, let our team know when you arrive.",
        ParagraphStyle("VDFootnote", parent=body_style, fontSize=8, textColor=colors.HexColor("#94A3B8")),
    ))

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
