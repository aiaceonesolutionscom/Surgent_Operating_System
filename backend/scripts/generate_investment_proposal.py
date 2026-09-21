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
        _header_row(["Phase", "Duration", "Deliverables"]),
        _row(["Phase 2 — Sellable Product", "3–4 weeks", "Green API paid plan, Meta (Instagram + Facebook Messenger), Twilio number + voice SDK, automated tenant-isolation tests, production VPS deploy, Sentry monitoring"]),
        _row(["Phase 3 — Scale Infrastructure", "3–4 weeks", "Second WhatsApp number for the Owner's outbound agent (bulk onboarding, CRM automation), AWS S3 + CloudFront migration"]),
        _row(["Phase 3 — Mobile App", "6–10 weeks", "Flutter app (Android + iOS) wrapping the already-built Patient Portal &amp; doctor APIs"]),
    ]
    story.append(_table(deliv_rows, [W * 0.26, W * 0.16, W * 0.58]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("The real cost of this work is the team's time — see Section 6 for the actual cash cost.", S_FOOTNOTE))
    story.append(PageBreak())

    # ---------------- 5. WHAT'S NEEDED TO GO LIVE (sourced) ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("5. What's Needed to Go Live — Sourced Technical Requirements", S_H1))
    story.append(Paragraph(
        "There is currently <b>no hired team</b> — the figures below are pure tool/infrastructure costs, "
        "each priced from the vendor's own current published rate. Team and marketing costs are kept "
        "completely separate (Section 6) since they are a different kind of decision.", S_BODY))
    req_rows = [
        _header_row(["Requirement", "Why It's Needed", "Real Cost", "Source"]),
        _row(["WhatsApp — Green API paid plan", "Removes the free tier's message limits", "~$8/mo (690 RUB)", "green-api.com/en/docs/about-tariffs"]),
        _row(["Instagram + Facebook Messenger", "Adds two more real channels", "Free (Meta App Review required)", "developers.facebook.com"]),
        _row(["Twilio — phone number + voice", "Enables a real phone/voice channel", "$1.15/mo number + $0.0085–0.014/min", "twilio.com/en-us/voice/pricing/us"]),
        _row(["Production hosting — Hetzner VPS", "Move off a dev machine onto a real server", "€5.49 – 14.86/mo (~$6 – 16/mo)", "hetzner.com/cloud"]),
        _row(["AWS S3 + CloudFront", "Scalable storage for patient photos/documents", "$0.023/GB storage + $0.085/GB delivery", "aws.amazon.com/s3/pricing"]),
        _row(["LLM — GPT-4.1-mini (production)", "Production-grade AI replies", "$0.40 / 1M input + $1.60 / 1M output tokens", "OpenAI API pricing"]),
        _row(["Deepgram — voice transcription", "Voice-note and call transcription", "$0.0043/min pre-recorded", "deepgram.com/pricing"]),
        _row(["LangSmith — AI monitoring", "Debug AI conversations, control LLM cost drift", "Free (5,000 traces/mo) → $39/seat/mo Plus", "langchain.com/pricing"]),
        _row(["Sentry — error monitoring", "Catch bugs before customers do", "Free (5,000 errors/mo) → $26/mo Team", "sentry.io pricing"]),
        _row(["Domain + SSL", "Real production URL, HTTPS", "~$12 – 15/yr (SSL itself is free — Let's Encrypt)", "standard registrar pricing"]),
    ]
    story.append(_table(req_rows, [W * 0.22, W * 0.28, W * 0.30, W * 0.20]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Real Monthly Infrastructure Cost — At Two Honest Scale Points", S_H2))
    scale_rows = [
        _header_row(["Scale", "What It Covers", "Monthly Cost (sourced)"]),
        _row(["Pilot (1–5 clinics, getting started)", "Light usage of every item above — realistic for the first few real customers", "≈ $35 – $60/mo"]),
        _row(["Growth (10–25 clinics)", "Heavier LLM/voice/storage usage as message volume scales up", "≈ $200 – $800/mo"]),
    ]
    story.append(_table(scale_rows, [W * 0.28, W * 0.44, W * 0.28]))
    story.append(PageBreak())

    # ---------------- 6. TEAM & 3-MONTH PLAN (separate, since no team exists) ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("6. If Hiring a Team — 3-Month Plan &amp; Cost", S_H1))
    story.append(Paragraph(
        "This is a genuinely <b>new, additive cost</b> — no one is currently on payroll for this project. "
        "The roles and salaries below are realistic full-time Pakistan tech salaries (not freelance/agency "
        "rates, which run higher per hour).", S_BODY))
    team_rows = [
        _header_row(["Role", "Monthly Salary (PKR)", "3 Months (PKR / USD)", "Responsibility"]),
        _row(["Senior Full-Stack Engineer", "150,000", "450,000 (~$1,624)", "Backend + frontend core work"]),
        _row(["DevOps Engineer", "100,000", "300,000 (~$1,083)", "VPS, CI/CD, monitoring, scaling"]),
        _row(["Data Scientist / ML Engineer", "100,000", "300,000 (~$1,083)", "Agents, prompts, evals, LLM cost control"]),
        _row(["3-person team, 3 months", "350,000/mo", "1,050,000 (~$3,790)", ""], bold_first=True),
        _row(["+ Optional: Flutter Mobile Developer", "120,000 – 150,000", "360,000 – 450,000 (~$1,300 – 1,624)", "Only if the mobile app is wanted in this same window"]),
    ]
    story.append(_table(team_rows, [W * 0.24, W * 0.16, W * 0.26, W * 0.34]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("What 3 Months of Work Realistically Delivers", S_H2))
    month_rows = [
        _header_row(["Month", "Deliverables"]),
        _row(["Month 1", "Finance/accounting module completed end-to-end; AWS S3 migration; automated tenant-isolation &amp; auth tests"]),
        _row(["Month 2", "Production VPS deploy (Hetzner), domain + SSL, Sentry + LangSmith wired in; Instagram + Facebook Messenger channels; Twilio voice pilot"]),
        _row(["Month 3", "Two real pilot clinics onboarded in Pakistan; bug fixes from real usage; polish and documentation for an international launch"]),
    ]
    story.append(_table(month_rows, [W * 0.18, W * 0.82]))
    story.append(PageBreak())

    # ---------------- 7. MARKETING ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("7. Marketing Investment — When It's Spent &amp; What It Returns", S_H1))
    story.append(Paragraph(
        "This is spent <b>after</b> the 3-month build (Section 6), not during it — there is nothing ready to "
        "market until Month 3's pilot clinics are live. It is not PKR 500,000 in one go; it is spread across "
        "Months 4–6 as below. The total can come in lower if early ad tests perform well, or the contingency "
        "line gets used if they don't — it is a planning budget, not a fixed bill.", S_BODY))
    mkt_rows = [
        _header_row(["Item", "Budget (PKR)", "When It's Spent"]),
        _row(["Multi-language landing page (EN / AR / UR)", "80,000", "Month 4, week 1 — one-off, before any ads run"]),
        _row(["Product demo videos / pilot clinic testimonial", "50,000", "Month 4 — one-off, needs the Month 3 pilot clinics' footage"]),
        _row(["LinkedIn + Meta lead-gen ads (US / UK / Dubai)", "200,000", "Months 4–6 — spread ~67,000/month as campaigns run"]),
        _row(["Cold outreach — email + LinkedIn sequences to clinics", "30,000", "Months 4–6 — ongoing, ~10,000/month"]),
        _row(["Google + clinic-directory SEO / launch activity", "60,000", "Months 4–6 — mostly upfront setup, some ongoing"]),
        _row(["Two discounted pilot clinics + live case study", "60,000", "Months 3–4 — a discount given, not cash paid to a vendor"]),
        _row(["Ad-test contingency (5%)", "20,000", "Held in reserve, spent only if needed"]),
        _row(["Total", "500,000 (~$1,800)"], bold_first=True),
    ]
    story.append(_table(mkt_rows, [W * 0.44, W * 0.18, W * 0.38]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("What This Realistically Returns", S_H2))
    story.append(Paragraph(
        "Using published B2B SaaS benchmarks (not Aiaceone-specific data, since there's no ad history yet): "
        "healthcare B2B SaaS lead-to-paying-customer conversion runs 2–5%, and healthcare trial-to-paid "
        "conversion runs ~21.5% once someone actually starts a trial.", S_BODY))
    story.append(_bullets([
        "PKR 200,000 (~$720) in ads, at a typical $20–50 cost-per-lead for B2B healthcare software → roughly 15–35 leads.",
        "At 2–5% lead-to-customer conversion → realistically <b>1–2 paying clinics</b> directly from the ad spend alone.",
        "Combined with cold outreach, SEO, and the two discounted pilot clinics already live → a realistic total of <b>8–12 paying clinics by the end of Month 6</b> — this is what Section 13's \"Break-even\" and \"Conservative\" scenarios are built from.",
    ]))
    story.append(PageBreak())

    # ---------------- 8. TOTAL INVESTMENT SUMMARY ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("8. Total Investment Summary", S_H1))
    total_rows = [
        _header_row(["Item", "Cost (USD)"]),
        _row(["3-person team, 3 months (Section 6)", "$3,790"]),
        _row(["Infrastructure, 3 months at pilot scale (Section 5)", "$105 – $180"]),
        _row(["Marketing launch budget (Section 7)", "$1,800"]),
        _row(["TOTAL — without mobile app", "≈ $5,700 – $5,800"], bold_first=True),
        _row(["+ Flutter Mobile Developer, 3 months (optional)", "$1,300 – $1,624"]),
        _row(["TOTAL — with mobile app included", "≈ $7,000 – $7,400"], bold_first=True),
    ]
    story.append(_table(total_rows, [W * 0.7, W * 0.3]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Monthly Cost After the 3 Months (Ongoing, If the Business Is Live)", S_H2))
    ongoing_rows = [
        _header_row(["Item", "Monthly Cost"]),
        _row(["Team, if retained", "PKR 350,000 (~$1,270)"]),
        _row(["Infrastructure (pilot → growth scale)", "$35 – $800"]),
        _row(["TOTAL ongoing monthly", "≈ $1,300 – $2,070/mo"], bold_first=True),
    ]
    story.append(_table(ongoing_rows, [W * 0.7, W * 0.3]))
    story.append(PageBreak())

    # ---------------- 9. PER-CLINIC REAL COST ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("9. What It Really Costs to Serve One Clinic", S_H1))
    story.append(Paragraph(
        "Green API (WhatsApp) is <b>not</b> Aiaceone's cost — each clinic connects their own Green API account "
        "(~$8/mo, paid by them directly to Green API) from Settings → Integrations. What Aiaceone pays for, "
        "per clinic, is the AI (LLM), the optional voice add-on, and a share of the fixed server/monitoring "
        "cost. Both usage levels below are stated assumptions, not measured data — there is no live client yet.", S_BODY))

    story.append(Paragraph("AI (LLM) Cost Per Clinic", S_H2))
    llm_rows = [
        _header_row(["Clinic Activity", "Assumption", "LLM Cost / Month"]),
        _row(["Light clinic", "~300 AI conversations/mo, ~4 AI replies each", "≈ $1 – $2"]),
        _row(["Active clinic", "~1,000 AI conversations/mo, ~4 AI replies each", "≈ $4 – $6"]),
    ]
    story.append(_table(llm_rows, [W * 0.28, W * 0.44, W * 0.28]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Computed from GPT-4.1-mini's real rate ($0.40/1M input + $1.60/1M output tokens), assuming ~2,000 input tokens (system prompt + booking tools + conversation history) and ~150 output tokens per AI reply.", S_FOOTNOTE))

    story.append(Paragraph("Voice Add-On Cost Per Clinic (Optional Tier)", S_H2))
    voice_rows = [
        _header_row(["Clinic Activity", "Assumption", "Voice Cost / Month"]),
        _row(["Light voice usage", "~300 call minutes/mo + 1 Twilio number", "≈ $5 – $6"]),
        _row(["Active voice usage", "~800 call minutes/mo + 1 Twilio number", "≈ $13 – $14"]),
    ]
    story.append(_table(voice_rows, [W * 0.28, W * 0.44, W * 0.28]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Twilio number $1.15/mo + $0.0085–0.014/min, plus Deepgram transcription at $0.0043/min — both real vendor rates (Section 5).", S_FOOTNOTE))

    story.append(Paragraph("Shared Fixed Cost (Server, Storage, Monitoring)", S_H2))
    story.append(Paragraph(
        "The VPS, S3 storage, and monitoring tools do not grow per clinic — the same server serves 1 clinic or "
        "15. This shared cost is roughly <b>$16 – $26/month total</b>, whoever is using the platform.", S_BODY))
    story.append(PageBreak())

    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Total Real Cost: 1 Clinic vs. 10 Clinics", S_H2))
    cost_compare_rows = [
        _header_row(["", "1 Clinic (chatbot only)", "10 Clinics (chatbot only)"]),
        _row(["LLM cost", "$1 – $6", "$10 – $60"]),
        _row(["Shared fixed cost (this client's full share vs. split 10 ways)", "$16 – $26 (100% on one client)", "$16 – $65 (some tools cross into paid tier)"]),
        _row(["Total monthly cost to Aiaceone", "$18 – $32", "$40 – $125"]),
        _row(["Cost per clinic", "$18 – $32/clinic", "$4 – $12.50/clinic"], bold_first=True),
    ]
    story.append(_table(cost_compare_rows, [W * 0.34, W * 0.33, W * 0.33]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The per-clinic cost drops sharply with scale — the fixed server/monitoring cost barely changes "
        "whether it's serving 1 client or 10. This is why margin improves as the client count grows.", S_BODY))

    story.append(Paragraph("Cost of a Free Trial", S_H2))
    story.append(Paragraph(
        "For a 14-day free trial, the real cost is that clinic's share of the \"1 Clinic\" row above, prorated "
        "for half a month: <b>≈ $9 – $16 per trial clinic</b>. Three simultaneous free trials cost Aiaceone "
        "roughly <b>$27 – $48 total</b> — cheap enough to give away freely to get real case studies.", S_BODY))
    story.append(PageBreak())

    # ---------------- TECH STACK ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("10. Technology Stack", S_H1))
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

    # ---------------- COMPETITORS ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("11. Competitor Pricing (Verified)", S_H1))
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
    story.append(Paragraph("12. Recommended Selling Price", S_H1))
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
    story.append(Paragraph("13. Revenue &amp; ROI Projection — How These Numbers Are Built", S_H1))

    story.append(Paragraph("Step 1 — The Fixed Monthly Cost Baseline", S_H2))
    story.append(Paragraph(
        "Team, if retained (Section 6): PKR 350,000 (~$1,270/mo) + shared infrastructure (Section 9): "
        "$16–$26/mo → <b>fixed cost ≈ $1,286 – $1,296/month</b>, before counting any per-clinic LLM/voice cost.", S_BODY))

    story.append(Paragraph("Step 2 — Revenue Per Clinic by Market (from Section 12)", S_H2))
    rev_rows = [
        _header_row(["Market", "Chatbot Price", "In USD"]),
        _row(["Pakistan", "PKR 15,000 – 25,000/mo", "$54 – $90"]),
        _row(["US", "$199 – 249/mo", "$199 – $249"]),
        _row(["UK", "£199 – 249/mo (GBP/USD ≈ 1.34)", "$267 – $334"]),
        _row(["Dubai", "AED 2,500 – 3,000/mo (AED/USD ≈ 3.6725)", "$681 – $817"]),
    ]
    story.append(_table(rev_rows, [W * 0.2, W * 0.4, W * 0.4]))

    story.append(Paragraph("Step 3 — Break-Even Point (Depends Heavily on Market Mix)", S_H2))
    story.append(Paragraph(
        "Break-even clinic count = fixed cost ÷ average revenue per clinic. This varies a lot by market:", S_BODY))
    be_rows = [
        _header_row(["If Selling Only To...", "Avg. Revenue / Clinic", "Clinics Needed to Break Even"]),
        _row(["Pakistan only", "~$72", "~18 clinics"]),
        _row(["US only", "~$224", "~6 clinics"]),
        _row(["Dubai only", "~$749", "~2 clinics"]),
        _row(["Realistic early mix (2 PK + 2 US + 1 Dubai)", "~$310 blended", "~4 – 5 clinics"]),
    ]
    story.append(_table(be_rows, [W * 0.4, W * 0.3, W * 0.3]))

    story.append(Paragraph("Step 4 — Growth Scenarios (Explicit Math)", S_H2))
    roi_rows = [
        _header_row(["Scenario", "Clinics (mix)", "Revenue Math", "Monthly Revenue", "Monthly Profit"]),
        _row(["Conservative", "15 (5 US / 5 UK / 5 Dubai)", "5×$249 + 5×$334 + 5×$817", "≈ $7,000", "≈ $5,600 (~PKR 1.55M)"]),
        _row(["Moderate", "30 (12 US / 10 UK / 8 Dubai)", "12×$249 + 10×$334 + 8×$817", "≈ $12,900", "≈ $11,500 (~PKR 3.2M)"]),
        _row(["Scale", "60 (25 US / 20 UK / 15 Dubai)", "25×$249 + 20×$334 + 15×$817", "≈ $25,200", "≈ $23,600 (~PKR 6.5M)"]),
    ]
    story.append(_table(roi_rows, [W * 0.14, W * 0.20, W * 0.30, W * 0.18, W * 0.18]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Profit = Revenue − fixed cost (~$1,290/mo) − LLM/voice cost at that client count (Section 9, roughly "
        "$0.30–$6/clinic/month, small enough not to change these totals meaningfully).", S_FOOTNOTE))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Payback on the $5,700–$7,400 build investment (Section 8): under the Conservative scenario "
        "(~$5,600/mo profit), roughly <b>1–1.5 months</b>.", S_BODY))
    story.append(PageBreak())

    # ---------------- SOURCES ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("14. Sources", S_H1))
    story.append(Paragraph("Every cost figure in Section 5 was checked against the vendor's own current pricing (September 2026):", S_BODY))
    story.append(_bullets([
        "Green API — green-api.com/en/docs/about-tariffs",
        "Twilio Voice — twilio.com/en-us/voice/pricing/us",
        "Hetzner Cloud — hetzner.com/cloud",
        "AWS S3 — aws.amazon.com/s3/pricing",
        "OpenAI API (GPT-4.1-mini) — developers.openai.com/api/docs/pricing",
        "Deepgram — deepgram.com/pricing",
        "LangSmith — langchain.com/pricing",
        "Sentry — sentry.io (pricing page)",
        "Flutter/mobile dev rates — Cleveroad, Solguruz, Vivasoft (2026 Flutter cost guides)",
        "Pakistan software dev rates — Payscale, SalaryExpert, GoodFirms (Pakistan, 2026)",
        "Competitor prices (Section 11) — each provider's own pricing page, checked September 2026",
        "GBP/USD and AED/USD exchange rates — checked September 2026",
        "B2B SaaS / healthcare conversion benchmarks (Section 7) — LeanLabs, Orbix Studio industry reports, 2026",
    ]))
    story.append(PageBreak())

    # ---------------- NEXT STEPS ----------------
    story.append(_TopBar(letter[0]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("15. Next Steps", S_H1))
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
