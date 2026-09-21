"""Shared ReportLab brand constants for every generated clinic PDF (invoices,
visit documents, signed consent forms) — extracted from invoice_pdf_service.py
so every document generator uses the same on-brand look without each one
redefining the palette and header stripe from scratch."""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

BRAND = colors.HexColor("#0D9488")  # teal-600, matches the app's own brand color
INK = colors.HexColor("#0F172A")
INK_SOFT = colors.HexColor("#475569")
SAND = colors.HexColor("#F8F5F0")
HAIRLINE = colors.HexColor("#E2E8F0")


class TopBar(Flowable):
    """A thin brand-color bar across the top of the page, matching the
    reference invoice design's header stripe."""

    def __init__(self, width, height=4 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(BRAND)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)
