from __future__ import annotations
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from src.models.invoice import Invoice
from src.models.patient import Patient
from src.models.practice import Practice
from src.models.doctor import Doctor

_BRAND = colors.HexColor("#0D9488")  # teal-600, matches the app's own brand color
_INK = colors.HexColor("#0F172A")
_INK_SOFT = colors.HexColor("#475569")
_SAND = colors.HexColor("#F8F5F0")


class _TopBar(Flowable):
    """A thin brand-color bar across the top of the page, matching the
    reference invoice design's header stripe."""

    def __init__(self, width, height=4 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(_BRAND)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def generate_invoice_pdf(
    invoice: Invoice, patient: Patient, practice: Practice, doctor: Doctor | None
) -> bytes:
    """Builds a professional, branded, itemized invoice PDF — the layout
    mirrors a standard medical billing invoice (patient info / physician
    info side by side, an invoice-number/date/due-date/amount-due strip,
    an itemized table, then subtotal/tax/total and a clinic-branded
    footer). No file is ever written to disk — callers get bytes back and
    either stream them straight to the browser or hand them to
    StorageService for a shareable URL (WhatsApp/email receipts)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvoiceTitle", parent=styles["Heading1"], fontSize=20, textColor=_INK, spaceAfter=0)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8, textColor=_BRAND, fontName="Helvetica-Bold", spaceAfter=2)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5, textColor=_INK_SOFT, leading=13)
    right_style = ParagraphStyle("Right", parent=body_style, alignment=TA_RIGHT)

    elements: list = [_TopBar(doc.width + doc.leftMargin + doc.rightMargin), Spacer(1, 10 * mm)]

    elements.append(Paragraph("MEDICAL BILLING INVOICE", title_style))
    elements.append(Spacer(1, 8 * mm))

    patient_lines = [f"<b>{patient.first_name} {patient.last_name}</b>"]
    if patient.phone:
        patient_lines.append(patient.phone)
    if patient.email:
        patient_lines.append(patient.email)

    doctor_lines = [f"<b>{doctor.name}</b>"] if doctor else ["<b>Not specified</b>"]
    if doctor and doctor.phone:
        doctor_lines.append(doctor.phone)
    if doctor and doctor.email:
        doctor_lines.append(doctor.email)

    info_table = Table(
        [[
            Paragraph("PATIENT INFORMATION<br/>" + "<br/>".join(patient_lines), body_style),
            Paragraph("PRESCRIBING PHYSICIAN'S INFORMATION<br/>" + "<br/>".join(doctor_lines), body_style),
        ]],
        colWidths=[doc.width / 2, doc.width / 2],
    )
    info_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    meta_table = Table(
        [
            [Paragraph("INVOICE NUMBER", label_style), Paragraph("DATE", label_style),
             Paragraph("DUE DATE", label_style), Paragraph("AMOUNT DUE", label_style)],
            [
                Paragraph(str(invoice.id)[:8].upper(), body_style),
                Paragraph(invoice.created_at.strftime("%m/%d/%Y"), body_style),
                Paragraph(invoice.due_date.strftime("%m/%d/%Y") if invoice.due_date else "—", body_style),
                Paragraph(f"<b>{_money(invoice.balance_due, invoice.currency)}</b>", body_style),
            ],
        ],
        colWidths=[doc.width / 4] * 4,
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (3, 0), (3, 1), _SAND),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8 * mm))

    item_rows = [["ITEM", "DESCRIPTION", "AMOUNT"]]
    for line in invoice.line_items:
        item_rows.append([
            Paragraph(line.description, body_style),
            Paragraph(f"Qty {line.quantity}", body_style),
            Paragraph(_money(float(line.unit_price) * line.quantity, invoice.currency), right_style),
        ])
    items_table = Table(item_rows, colWidths=[doc.width * 0.4, doc.width * 0.35, doc.width * 0.25])
    items_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), _INK),
        ("LINEBELOW", (0, 0), (-1, 0), 1, _BRAND),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 8 * mm))

    totals_rows = [["SUB TOTAL", _money(float(invoice.subtotal_amount), invoice.currency)]]
    if float(invoice.tax_amount):
        totals_rows.append(["TAX", _money(float(invoice.tax_amount), invoice.currency)])
    if float(invoice.discount_amount):
        totals_rows.append(["DISCOUNT", f"-{_money(float(invoice.discount_amount), invoice.currency)}"])
    if invoice.amount_paid:
        totals_rows.append(["PAID", _money(invoice.amount_paid, invoice.currency)])
    totals_table = Table(totals_rows, colWidths=[doc.width * 0.6, doc.width * 0.4])
    totals_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    total_label = "TOTAL" if invoice.balance_due >= float(invoice.total_amount) else "BALANCE DUE"
    grand_total = Table(
        [[Paragraph(f"<b>{total_label}</b>", ParagraphStyle("GT", parent=styles["Normal"], fontSize=13, textColor=_INK)),
          Paragraph(f"<b>{_money(invoice.balance_due, invoice.currency)}</b>", ParagraphStyle("GTR", parent=styles["Normal"], fontSize=13, textColor=_INK, alignment=TA_RIGHT))]],
        colWidths=[doc.width * 0.6, doc.width * 0.4],
    )
    grand_total.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SAND),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    right_col = Table([[totals_table], [Spacer(1, 3 * mm)], [grand_total]], colWidths=[doc.width])
    elements.append(right_col)
    elements.append(Spacer(1, 14 * mm))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_BRAND)
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
