"""One-off script: generates the AIACEONE investment/partnership proposal PDF.

Not part of the running app — a business document generator, reusing the
same reportlab styling already proven in services/billing/invoice_pdf_service.py
so it looks like the same professional, on-brand family of documents.

Run: python scripts/generate_investment_proposal.py
Output: ../AIACEONE_Investment_Proposal.pdf (project root)
"""
from __future__ import annotations
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable, PageBreak, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

_BRAND = colors.HexColor("#0D9488")
_BRAND_DARK = colors.HexColor("#0A4F4E")
_INK = colors.HexColor("#0F172A")
_INK_SOFT = colors.HexColor("#475569")
_INK_MUTED = colors.HexColor("#6B7E86")
_SAND = colors.HexColor("#F8F5F0")
_SAND_BORDER = colors.HexColor("#E7E0D3")
_GOLD = colors.HexColor("#C9A24B")
_WHITE = colors.white


class _TopBar(Flowable):
    def __init__(self, width, height=5 * mm, color=_BRAND):
        super().__init__()
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


styles = getSampleStyleSheet()
S_COVER_TITLE = ParagraphStyle("CoverTitle", parent=styles["Heading1"], fontSize=28, textColor=_INK, spaceAfter=6, alignment=TA_CENTER, leading=32)
S_COVER_SUB = ParagraphStyle("CoverSub", parent=styles["Normal"], fontSize=13, textColor=_BRAND_DARK, alignment=TA_CENTER, spaceAfter=4)
S_COVER_META_LABEL = ParagraphStyle("CoverMetaLabel", parent=styles["Normal"], fontSize=9, textColor=_BRAND, fontName="Helvetica-Bold", spaceAfter=2)
S_COVER_META = ParagraphStyle("CoverMeta", parent=styles["Normal"], fontSize=10.5, textColor=_INK_SOFT, spaceAfter=2)
S_H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=17, textColor=_INK, spaceBefore=0, spaceAfter=10)
S_H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5, textColor=_BRAND_DARK, spaceBefore=14, spaceAfter=6)
S_BODY = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, textColor=_INK_SOFT, leading=15, spaceAfter=6)
S_BODY_SMALL = ParagraphStyle("BodySmall", parent=styles["Normal"], fontSize=8.5, textColor=_INK_MUTED, leading=12, spaceAfter=4)
S_CELL = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=9, textColor=_INK_SOFT, leading=12)
S_CELL_BOLD = ParagraphStyle("CellBold", parent=styles["Normal"], fontSize=9, textColor=_INK, fontName="Helvetica-Bold", leading=12)
S_CELL_HEAD = ParagraphStyle("CellHead", parent=styles["Normal"], fontSize=8.5, textColor=_WHITE, fontName="Helvetica-Bold", leading=11)
S_LABEL_PILL = ParagraphStyle("LabelPill", parent=styles["Normal"], fontSize=9, textColor=_BRAND_DARK, fontName="Helvetica-Bold", spaceBefore=2, spaceAfter=6)
S_FOOTNOTE = ParagraphStyle("Footnote", parent=styles["Normal"], fontSize=8, textColor=_INK_MUTED, leading=11, spaceAfter=4)


def _header_row(cells):
    return [Paragraph(c, S_CELL_HEAD) for c in cells]


def _row(cells, bold_first=False):
    out = []
    for i, c in enumerate(cells):
        style = S_CELL_BOLD if (bold_first and i == 0) else S_CELL
        out.append(Paragraph(str(c), style))
    return out


def _table(data, col_widths, header=True, zebra=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("BOX", (0, 0), (-1, -1), 0.6, _SAND_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _SAND_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), _BRAND_DARK))
    if zebra:
        for r in range(1 if header else 0, len(data)):
            if (r - (1 if header else 0)) % 2 == 1:
                style.append(("BACKGROUND", (0, r), (-1, r), _SAND))
    t.setStyle(TableStyle(style))
    return t


def _bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, S_BODY), leftIndent=6) for i in items],
        bulletType="bullet", start="circle", leftIndent=14, bulletFontSize=6, bulletColor=_BRAND,
    )


def build():
    out_path = os.path.join(os.path.dirname(__file__), "..", "..", "AIACEONE_Investment_Proposal.pdf")
    out_path = os.path.abspath(out_path)
    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        topMargin=0, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []
    W = letter[0] - 36 * mm  # usable width

    # ---------------- COVER ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 55 * mm))
    story.append(Paragraph("AIACEONE", ParagraphStyle("Brand", parent=styles["Normal"], fontSize=15, textColor=_BRAND, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=18)))
    story.append(Paragraph("Investment &amp; Partnership Proposal", S_COVER_TITLE))
    story.append(Paragraph("The Clinic Operating System for Plastic Surgery &amp; Aesthetic Practices", S_COVER_SUB))
    story.append(Spacer(1, 40 * mm))

    meta = Table([
        [Paragraph("PREPARED FOR", S_COVER_META_LABEL), Paragraph("PREPARED BY", S_COVER_META_LABEL)],
        [Paragraph("Prospective Investor / Partner", S_COVER_META), Paragraph("Aiaceone Founding Team", S_COVER_META)],
        [Paragraph("Date: 17 September 2026", S_COVER_META), Paragraph("aiaceonesolutions.com", S_COVER_META)],
    ], colWidths=[W / 2, W / 2])
    meta.setStyle(TableStyle([("ALIGN", (0, 0), (0, -1), "LEFT"), ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
    story.append(meta)
    story.append(PageBreak())

    # ---------------- ABOUT ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("1. About Aiaceone", S_H1))
    story.append(Paragraph(
        "Aiaceone is a complete <b>Clinic Operating System</b> for plastic-surgery and aesthetic-medicine "
        "practices — real dashboards for the Owner, Doctor, Receptionist, and Patient, layered with a real "
        "AI system: a WhatsApp AI Receptionist that answers instantly, checks live doctor availability, "
        "books real appointments, and hands the conversation to a human whenever it's needed.", S_BODY))
    story.append(Paragraph(
        "Unlike most competitors, who sell either an AI voice/chat receptionist <i>or</i> practice-management "
        "software, Aiaceone sells both in one product — AI across every channel (WhatsApp, Instagram, Facebook, "
        "voice) plus a full clinic operating system and a real patient portal.", S_BODY))

    story.append(Paragraph("What's Verified Working Today", S_H2))
    story.append(_bullets([
        "Core clinic workflow — patients, doctors, appointments, consultation notes, consent, surgery, billing, inventory, expenses, leads — no mock data in the clinical core.",
        "WhatsApp AI Receptionist — live-connected number, real end-to-end booking via function-calling, human-takeover so the bot and a staff member never talk over each other.",
        "Patient Portal — Portal ID + PIN login; patients see appointments, treatment plans, invoices, consent documents, and their own photo timeline.",
        "Multi-tenant foundation — isolated organizations, a Super Admin approval/oversight panel, and a guided onboarding path for a brand-new clinic.",
        "Versioned e-consent, before/after photo timelines, real surgery lifecycle tracking, and in-app staff messaging.",
    ]))
    story.append(PageBreak())

    # ---------------- PROBLEM ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("2. The Problem Being Solved", S_H1))
    problem_rows = [
        _header_row(["Problem", "Evidence", "Aiaceone's Fix"]),
        _row(["Clinics reply to leads in hours", "Average 4+ hour response time industry-wide", "AI replies in ~3 seconds, 24/7"]),
        _row(["After-hours calls get missed", "37% of patient calls happen after hours (MGMA)", "AI covers every hour, every day"]),
        _row(["A receptionist is expensive", "US full-time receptionist ≈ $35–55k/yr (~$53,700 fully loaded)", "AI from ~$99–249/mo — 93–98% cheaper"]),
        _row(["A missed inquiry is lost revenue", "Dubai: one missed patient can be AED 3k–20k lifetime value", "AI captures and books leads overnight"]),
        _row(["Hold times frustrate patients", "Front desks field 60–80 calls/day, 4+ min holds", "AI picks up in seconds, every time"]),
        _row(["Language barriers", "50%+ of Dubai patients prefer Arabic", "Bilingual Arabic / Urdu / English support"]),
    ]
    story.append(_table(problem_rows, [W * 0.28, W * 0.36, W * 0.36]))
    story.append(PageBreak())

    # ---------------- SOLUTION OVERVIEW ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("3. Solution Overview", S_H1))

    story.append(Paragraph("1. WhatsApp AI Receptionist", S_H2))
    story.append(_bullets([
        "Real inbound/outbound WhatsApp — instant reply, real doctor-availability lookup, and real booking via function-calling.",
        "Returning-patient detection (phone number is a durable identity) and bilingual support.",
        "Human-takeover — a staff member can reply over the same real WhatsApp thread and pause the AI so it never talks over a human.",
    ]))
    story.append(Paragraph("2. The Four Live Dashboards", S_H2))
    story.append(_bullets([
        "<b>Owner</b> — practice control room: finance, expenses, funnel, staff messaging, every AI agent, and a Command Center for plain-language business questions.",
        "<b>Doctor</b> — their own patients, SOAP consultation notes, treatment plans with real procedure pricing, surgery module, photo timelines.",
        "<b>Receptionist</b> — front-desk workflow: Scheduled → Checked-in → With Doctor → Ready for Checkout → Completed, waitlist, invoicing, WhatsApp human-takeover.",
        "<b>Patient Portal</b> — Portal ID + PIN login; patients see appointments, treatment plans, invoices, consent, and photo history, and can request new appointments.",
    ]))
    story.append(Paragraph("3. AI Command Center", S_H2))
    story.append(_bullets([
        "A natural-language assistant over five real categories — front desk, consultation, surgery, post-care, business — that genuinely queries the live database, gated by plan tier.",
        "Hard safety rule: the AI never diagnoses or decides treatment — it collects, classifies, and escalates to a human.",
    ]))
    story.append(PageBreak())

    # ---------------- DELIVERABLES & TIMELINE ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("4. Deliverables &amp; Timeline — What's Left to Build", S_H1))
    story.append(Paragraph(
        "Phase 1 (the core Clinic OS + live WhatsApp AI receptionist) is largely complete today. The table "
        "below is what remains to take the product from a working dev build to a fully sellable, "
        "production-hardened, multi-market product.", S_BODY))

    deliv_rows = [
        _header_row(["Phase", "Duration", "Deliverables", "Cost (work value)"]),
        _row(["Phase 2 — Sellable Product", "3–4 weeks", "Green API paid plan, Meta (Instagram + Facebook Messenger), Twilio number + voice SDK, automated tenant-isolation tests, production VPS deploy, Sentry monitoring", "$2,500 – $5,000"]),
        _row(["Phase 3 — Scale Infrastructure", "3–4 weeks", "Second WhatsApp number for the Owner's outbound agent (bulk onboarding, CRM automation), AWS S3 + CloudFront migration", "$2,000 – $5,000"]),
        _row(["Phase 3 — Mobile App", "6–10 weeks", "Flutter app (Android + iOS) wrapping the already-built Patient Portal &amp; doctor APIs", "$3,000 – $8,000"]),
        _row(["Total (work value, if built by an outside team)", "", "", "$7,500 – $18,000"], bold_first=True),
    ]
    story.append(_table(deliv_rows, [W * 0.24, W * 0.14, W * 0.44, W * 0.18]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Note on the Mobile App line: earlier drafts of this document priced it up to $18,000, benchmarked "
        "against a Western outsourced agency. Aiaceone's own in-house team can build it — same team, same "
        "codebase, same APIs already live — for a realistic $3,000–$8,000. See Section 5 for the real-cash "
        "version of this number.", S_FOOTNOTE))
    story.append(PageBreak())

    # ---------------- PRICING / INVESTMENT (the corrected core) ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("5. Pricing &amp; Investment — Two Honest Scenarios", S_H1))
    story.append(Paragraph(
        "The figures in Section 4 are <b>market work-value</b> — what this would cost if bought from an "
        "outside agency. That is not the same as the real new cash a founder needs, since Aiaceone already "
        "has an in-house team on salary. Both are shown below so neither number is misleading on its own.", S_BODY))

    story.append(Paragraph("Scenario A — Real Cash Needed (team already on payroll, unaffected either way)", S_H2))
    scenA = [
        _header_row(["Item", "One-time", "Monthly"]),
        _row(["App Store registrations (Apple $99/yr + Google Play $25 one-time)", "$124", "—"]),
        _row(["Domain + SSL", "$50 – $100", "—"]),
        _row(["Platform infrastructure (hosting, WhatsApp, LLM, S3, monitoring — scales with client count, see Section 7)", "—", "$190 – $1,290"]),
        _row(["Real new cash needed", "$174 – $224", "$190 – $1,290"], bold_first=True),
    ]
    story.append(_table(scenA, [W * 0.58, W * 0.21, W * 0.21]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "The team's own build-hours (Phase 2/3/Mobile) are not an <i>additional</i> cost here — they are "
        "already covered by the payroll below, whether or not this specific work is happening.", S_FOOTNOTE))

    story.append(Paragraph("Scenario B — Full Investment (team payroll + marketing included)", S_H2))
    scenB = [
        _header_row(["Item", "One-time", "Monthly"]),
        _row(["Team payroll — Senior Full-Stack Engineer, DevOps Engineer, ML/Data Engineer (see Section 6)", "—", "PKR 350,000 (~$1,270)"]),
        _row(["Platform infrastructure", "—", "$190 – $1,290"]),
        _row(["International launch marketing (landing page, paid ads, outreach, two pilot case studies)", "PKR 500,000 (~$1,800)", "—"]),
        _row(["Real one-time non-labor cash (app store, domain)", "$174 – $224", "—"]),
        _row(["Total", "≈ $2,000 – $2,050", "≈ $1,460 – $2,560 / month"], bold_first=True),
    ]
    story.append(_table(scenB, [W * 0.58, W * 0.21, W * 0.21]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Recommended framing for investors: present the <b>work already delivered</b> (Section 4 style "
        "value, roughly $75,000–$150,000+ if this scope were purchased from an outside Pakistan-based agency "
        "at $25–50/hr for an estimated 3,000–5,000 development hours) separately from the <b>forward cash "
        "ask</b> (Scenario A or B above) — conflating the two, as an earlier draft did, is what made a "
        "<i>$6,000–$28,500</i> total read as inconsistent with an <i>$8,000–$15,000</i> figure elsewhere in "
        "the same document.", S_BODY))
    story.append(PageBreak())

    # ---------------- TEAM & TECH STACK ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("6. Team &amp; Technology Stack", S_H1))
    story.append(Paragraph("Founding Team (Monthly, PKR)", S_H2))
    team_rows = [
        _header_row(["Role", "Monthly Salary (PKR)", "Responsibility"]),
        _row(["Senior Full-Stack Engineer", "150,000", "Backend + frontend core"]),
        _row(["DevOps Engineer", "100,000", "VPS, CI/CD, monitoring, scaling"]),
        _row(["Data Scientist / ML Engineer", "100,000", "Agents, prompts, evals, LLM cost control"]),
        _row(["Team total", "350,000 (~$1,270/mo)", ""], bold_first=True),
    ]
    story.append(_table(team_rows, [W * 0.32, W * 0.28, W * 0.40]))

    story.append(Paragraph("Technology Stack", S_H2))
    tech_rows = [
        _header_row(["Layer", "Technology"]),
        _row(["Backend", "FastAPI, async SQLAlchemy 2.0, PostgreSQL, Alembic, Pydantic v2"]),
        _row(["Frontend", "React 18, TypeScript, Vite, Tailwind CSS"]),
        _row(["Staff Auth", "Clerk (Owner / Doctor / Receptionist)"]),
        _row(["Patient Auth", "Custom Portal ID + PIN (JWT, rate-limited)"]),
        _row(["LLM", "Mistral (free fallback) → Groq → OpenAI GPT-4.1-mini (production)"]),
        _row(["Messaging", "Green API (WhatsApp), Meta API (Instagram / Facebook), Twilio (voice), Resend (email)"]),
        _row(["File storage", "Cloudinary today → AWS S3 at scale"]),
        _row(["Observability", "LangSmith (tracing), Sentry (errors)"]),
    ]
    story.append(_table(tech_rows, [W * 0.26, W * 0.74]))
    story.append(PageBreak())

    # ---------------- MONTHLY PLATFORM COST ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("7. Estimated Monthly Platform Cost (all clients combined)", S_H1))
    plat_rows = [
        _header_row(["Item", "Cost (USD/mo)"]),
        _row(["Green API × 2 numbers", "24"]),
        _row(["Hosting (Hetzner VPS) + database", "20 – 50"]),
        _row(["S3 + CloudFront", "10 – 30"]),
        _row(["LLM (GPT-4.1-mini, agentic use)", "50 – 400"]),
        _row(["Deepgram (speech-to-text / text-to-speech)", "20 – 120"]),
        _row(["Twilio numbers + voice usage", "20 – 500"]),
        _row(["LangSmith (Plus)", "39 – 80"]),
        _row(["Sentry / monitoring / uptime", "0 – 30"]),
        _row(["Email (Resend)", "0 – 30"]),
        _row(["Domains / SSL / backups", "6 – 25"]),
        _row(["Platform total (10–25 clinics on the platform)", "≈ 190 – 1,290"], bold_first=True),
    ]
    story.append(_table(plat_rows, [W * 0.7, W * 0.3]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Per-clinic delivery cost: chatbot-only ≈ $20–45/clinic/month; chatbot + voice ≈ $60–180/clinic/month (voice-volume dependent).", S_BODY))
    story.append(PageBreak())

    # ---------------- COMPETITORS ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("8. Competitor Pricing (Verified)", S_H1))
    comp_rows = [
        _header_row(["Provider", "Price", "Market"]),
        _row(["S10.AI", "$99/mo + usage", "US — medical AI receptionist"]),
        _row(["DeepCura", "$129/provider/mo", "US — receptionist + scribe + billing (closest comparable)"]),
        _row(["Smith.ai", "$95 – $300/mo", "US — AI + human hybrid"]),
        _row(["AgentZap", "$109 / $295 / $899/mo", "US — medical receptionist with EHR"]),
        _row(["Cliniko / Jane / Pabau / SimplePractice", "$19 – $395/mo (per practitioner)", "US / UK / AU — clinic management only, no AI"]),
        _row(["ZayaDesk / Norango / Intavia", "£69.95 – £349/mo", "UK — AI receptionist"]),
        _row(["Bertos / Grow50X", "AED 499 – 5,000/mo", "Dubai — WhatsApp / clinic AI"]),
        _row(["Custom hospital chatbot builds", "AED 120,000 – 850,000 one-time", "Dubai — fully custom enterprise"]),
    ]
    story.append(_table(comp_rows, [W * 0.30, W * 0.30, W * 0.40]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Aiaceone's position:</b> most competitors sell either an AI receptionist or clinic-management "
        "software. Aiaceone sells both, across every channel, in one product — the differentiating bundle.", S_BODY))
    story.append(PageBreak())

    # ---------------- SELLING PRICE ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("9. Recommended Selling Price", S_H1))
    sell_rows = [
        _header_row(["Market", "Target Customer", "Monthly Price", "One-time Setup Fee"]),
        _row(["Pakistan", "Solo / small aesthetic, dental, dermatology clinics", "PKR 15,000 – 25,000 (chatbot); PKR 60,000+ (+voice)", "None — self-serve"]),
        _row(["United States", "Boutique plastic surgery practices, medspas", "$199 – 249 (chatbot); $299 – 399 (+voice)", "None (standard); $500–1,500 for multi-location/enterprise"]),
        _row(["United Kingdom", "Same segment", "£199 – 249 (chatbot); £299 – 349 (+voice)", "Same rule as US"]),
        _row(["Dubai / UAE", "Clinics + hospital groups", "AED 2,500 – 3,000 (WhatsApp+IG); AED 3,500 – 4,000 (full+mobile)", "AED 3,000 – 10,000 — normal in this market"]),
    ]
    story.append(_table(sell_rows, [W * 0.16, W * 0.28, W * 0.34, W * 0.22]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "No setup fee for self-serve tiers (Pakistan, US, UK standard) — every direct competitor researched "
        "(Cliniko, Jane, SimplePractice, DeepCura, S10.AI) sells pure subscription with no setup fee; adding "
        "one would create signup friction a small clinic won't tolerate. Dubai is the exception — local "
        "competitors (Bertos, Grow50X) already charge AED 1,500–40,000 in setup fees, so buyers expect and "
        "budget for one.", S_BODY))
    story.append(PageBreak())

    # ---------------- ROI ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("10. Revenue &amp; ROI Projection", S_H1))
    roi_rows = [
        _header_row(["Scenario", "Clinics (mix)", "Monthly Revenue", "Monthly Profit"]),
        _row(["Break-even", "~8–10", "~$2,000", "~$50 – 100"]),
        _row(["Conservative", "15 (5 US / 5 UK / 5 Dubai)", "~$5,100", "~$3,150 (~PKR 870k)"]),
        _row(["Moderate", "30 (12 / 10 / 8)", "~$10,500", "~$8,500 (~PKR 2.3M)"]),
        _row(["Scale", "60 (25 / 20 / 15)", "~$22,500", "~$20,500 (~PKR 5.6M)"]),
    ]
    story.append(_table(roi_rows, [W * 0.2, W * 0.28, W * 0.26, W * 0.26]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Payback on the Scenario B forward investment (Section 5): roughly 1–2 months at the conservative "
        "scenario, given the real monthly cash need is $1,460–$2,560 against a $5,100 conservative-scenario "
        "revenue.", S_BODY))
    story.append(PageBreak())

    # ---------------- NEXT STEPS ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("11. Next Steps", S_H1))
    story.append(_bullets([
        "<b>Weeks 1–3:</b> Finance/accounting module end-to-end, S3 migration, LangSmith live evaluation.",
        "<b>Weeks 3–4:</b> Production VPS deploy, domain + SSL, Sentry, Redis, tenant-isolation tests, verified backups.",
        "<b>Month 2:</b> Instagram + Facebook Messenger channels, Twilio voice pilot.",
        "<b>Month 2–3:</b> Two pilot clinics in Pakistan → live case study and testimonial.",
        "<b>Month 2–3:</b> Marketing launch in US / UK / Dubai.",
        "<b>Year 1:</b> Scale to 60+ clinics across four markets.",
    ]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This document updates alongside the codebase. Nothing here is softened — free-tier ceilings, "
        "multi-tenant scaling work, and production-hardening are called out explicitly and priced.", S_FOOTNOTE))

    doc.build(story)
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"Generated: {path}")
