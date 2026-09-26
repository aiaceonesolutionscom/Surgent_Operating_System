"""
Seed script — demo practice, agent configs, and a realistic aesthetic-clinic
inventory catalogue WITH stock on hand.

Everything here is idempotent: run it as many times as you like. It never
deletes or overwrites stock/usage history; it only
  * creates the practice if it's missing,
  * creates any missing agent config,
  * inserts catalogue items that aren't there yet (matched on SKU),
  * tops up the starting stock for items that have NO batches at all.

Usage:
    python scripts/seed_data.py                        # seed every practice
    python scripts/seed_data.py --practice-email a@b.com
"""

import argparse
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory
from src.models.practice import Practice
from src.models.agent_config import AgentConfig
from src.models.inventory_item import InventoryItem
from src.models.inventory_batch import InventoryBatch


AGENT_TYPES = [
    "receptionist", "appointment_reminder",
    "lead_qualification", "patient_intake", "consultation_assistant",
    "post_op_recovery", "marketing_retention",
    "finance_agent", "main_agent",
]

DEMO_PRACTICE = {
    "name": "Demo Aesthetic Practice",
    "email": "demo@aesthetixai.com",
    "phone": "+1234567890",
}

# ---------------------------------------------------------------------------
# Realistic aesthetic-clinic stock catalogue.
#
# `stock` is the starting on-hand quantity the script creates a first batch
# for, `expiry_months` how long that batch stays good for (None = the clinic
# doesn't date-track it, e.g. a compression garment or a steel instrument).
# `reorder_threshold` is what drives the Low stock badge.
# ---------------------------------------------------------------------------
CATALOGUE: list[dict] = [
    # ---------------------------------------------------------------- surgical
    {"name": "Sterile Surgical Gloves (Size 7, Latex-Free)", "sku": "SG-S7-050", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("68.00"), "reorder_threshold": 6, "is_implant": False, "stock": 24, "expiry_months": 30},
    {"name": "Sterile Surgical Gloves (Size 8, Latex-Free)", "sku": "SG-S8-050", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("68.00"), "reorder_threshold": 6, "is_implant": False, "stock": 19, "expiry_months": 30},
    {"name": "Nitrile Exam Gloves (M, Powder-Free)", "sku": "SG-NT-M100", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("14.50"), "reorder_threshold": 12, "is_implant": False, "stock": 48, "expiry_months": 36},
    {"name": "Sterile Gauze Pads 4x4 (12-Ply)", "sku": "SC-GZ-4X4-10", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("8.50"), "reorder_threshold": 20, "is_implant": False, "stock": 86, "expiry_months": 30},
    {"name": "Sterile Gauze Swabs (Cotton, 10cm)", "sku": "SC-GZ-SW-100", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("6.20"), "reorder_threshold": 15, "is_implant": False, "stock": 64, "expiry_months": 30},
    {"name": "Sterile Disposable Surgical Drape (Small)", "sku": "SC-DR-SM-05", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("15.00"), "reorder_threshold": 12, "is_implant": False, "stock": 41, "expiry_months": 36},
    {"name": "Sterile Surgical Drape Sheet (Large)", "sku": "SC-DR-LG-05", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("19.50"), "reorder_threshold": 12, "is_implant": False, "stock": 37, "expiry_months": 36},
    {"name": "Adhesive U-Drape (Sterile Film, 30x45cm)", "sku": "SC-UDR-10", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("42.00"), "reorder_threshold": 6, "is_implant": False, "stock": 22, "expiry_months": 36},
    {"name": "Nylon Suture 3-0 (5/0) with Needle", "sku": "SC-NY-30-12", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("52.00"), "reorder_threshold": 4, "is_implant": False, "stock": 14, "expiry_months": 36},
    {"name": "Nylon Suture 4-0 (6/0) with Needle", "sku": "SC-NY-40-12", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("52.00"), "reorder_threshold": 4, "is_implant": False, "stock": 11, "expiry_months": 36},
    {"name": "Polyglactin Suture 3-0 (Vicryl)", "sku": "SC-VC-30-12", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("46.00"), "reorder_threshold": 4, "is_implant": False, "stock": 16, "expiry_months": 36},
    {"name": "Absorbable Monocryl Suture 5-0", "sku": "SC-MC-50-12", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("58.00"), "reorder_threshold": 3, "is_implant": False, "stock": 9, "expiry_months": 36},
    {"name": "Silk Suture 6-0 (Microsurgery)", "sku": "SC-SK-60-12", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("61.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": 24},
    {"name": "Skin Stapler 5mm (Disposable)", "sku": "SC-STP-25", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("118.00"), "reorder_threshold": 3, "is_implant": False, "stock": 8, "expiry_months": 36},
    {"name": "Surgical Skin Staples (5mm)", "sku": "SC-STL-50-25", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("34.00"), "reorder_threshold": 4, "is_implant": False, "stock": 12, "expiry_months": 36},
    {"name": "Scalpel Blades #10", "sku": "SC-SB-10-100", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("12.00"), "reorder_threshold": 8, "is_implant": False, "stock": 31, "expiry_months": 60},
    {"name": "Scalpel Blades #15", "sku": "SC-SB-15-100", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("12.00"), "reorder_threshold": 8, "is_implant": False, "stock": 27, "expiry_months": 60},
    {"name": "Scalpel Blades #11 (Stub/Dermatology)", "sku": "SC-SB-11-100", "category": "Surgical Consumables", "unit": "box", "unit_cost": Decimal("13.50"), "reorder_threshold": 6, "is_implant": False, "stock": 18, "expiry_months": 60},
    {"name": "Scalpel Handle No. 4 (Reusable, Stainless)", "sku": "SC-SH-04", "category": "Surgical Consumables", "unit": "piece", "unit_cost": Decimal("9.80"), "reorder_threshold": 4, "is_implant": False, "stock": 9, "expiry_months": None},
    {"name": "Surgical Skin Marker (Violet, Washable)", "sku": "SC-MK-VIO", "category": "Surgical Consumables", "unit": "piece", "unit_cost": Decimal("3.20"), "reorder_threshold": 10, "is_implant": False, "stock": 38, "expiry_months": 24},
    {"name": "Eyelid / Facial Marker (Blue, Ocular)", "sku": "SC-MK-BLU", "category": "Surgical Consumables", "unit": "piece", "unit_cost": Decimal("4.50"), "reorder_threshold": 8, "is_implant": False, "stock": 6, "expiry_months": 24},
    {"name": "Chlorhexidine Gluconate Prep 4% (500ml)", "sku": "SC-CHX-4-500", "category": "Surgical Consumables", "unit": "bottle", "unit_cost": Decimal("11.00"), "reorder_threshold": 6, "is_implant": False, "stock": 21, "expiry_months": 24},
    {"name": "Povidone-Iodine Solution 10% (100ml)", "sku": "SC-PVI-10-100", "category": "Surgical Consumables", "unit": "bottle", "unit_cost": Decimal("6.40"), "reorder_threshold": 8, "is_implant": False, "stock": 29, "expiry_months": 24},
    {"name": "Sterile Normal Saline 0.9% (500ml)", "sku": "SC-NS-09-500", "category": "Surgical Consumables", "unit": "bottle", "unit_cost": Decimal("4.80"), "reorder_threshold": 15, "is_implant": False, "stock": 62, "expiry_months": 24},
    {"name": "Adhesive Micropore Tape 1 inch", "sku": "SC-TAP-MP-1", "category": "Surgical Consumables", "unit": "roll", "unit_cost": Decimal("5.50"), "reorder_threshold": 12, "is_implant": False, "stock": 44, "expiry_months": 36},
    {"name": "Zinc Oxide Adhesive Tape 2 inch", "sku": "SC-TAP-ZN-2", "category": "Surgical Consumables", "unit": "roll", "unit_cost": Decimal("6.20"), "reorder_threshold": 10, "is_implant": False, "stock": 33, "expiry_months": 36},
    {"name": "Steri-Strips (Suture Strips, 5mm)", "sku": "SC-STR-05-50", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("24.00"), "reorder_threshold": 6, "is_implant": False, "stock": 17, "expiry_months": 36},
    {"name": "Sterile Abdominal Pad (Large)", "sku": "SC-ABP-LG-25", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("18.00"), "reorder_threshold": 8, "is_implant": False, "stock": 25, "expiry_months": 36},
    {"name": "Sterile Cotton Balls", "sku": "SC-CB-100", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("4.90"), "reorder_threshold": 10, "is_implant": False, "stock": 40, "expiry_months": 36},
    {"name": "Sterile Cotton Buds", "sku": "SC-CBD-100", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("4.20"), "reorder_threshold": 10, "is_implant": False, "stock": 36, "expiry_months": 36},
    {"name": "Sterilization Pouch (Self-Seal, 9x13cm)", "sku": "SC-STP-0913-100", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("22.00"), "reorder_threshold": 6, "is_implant": False, "stock": 20, "expiry_months": 60},
    {"name": "Autoclave Indicator Strips", "sku": "SC-AUT-IND-100", "category": "Surgical Consumables", "unit": "pack", "unit_cost": Decimal("16.00"), "reorder_threshold": 4, "is_implant": False, "stock": 11, "expiry_months": 36},
    {"name": "Absorbable Surgical Mesh (10x10cm)", "sku": "SC-MSH-1010", "category": "Surgical Consumables", "unit": "piece", "unit_cost": Decimal("145.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": 36},

    # -------------------------------------------------------------- anaesthesia
    {"name": "Lidocaine 1% with Epinephrine 1:100,000 (10ml)", "sku": "AN-LID-1E-10", "category": "Anaesthesia & Analgesia", "unit": "vial", "unit_cost": Decimal("7.80"), "reorder_threshold": 20, "is_implant": False, "stock": 74, "expiry_months": 24},
    {"name": "Mepivacaine 3% Plain (10ml)", "sku": "AN-MEP-3-10", "category": "Anaesthesia & Analgesia", "unit": "vial", "unit_cost": Decimal("9.20"), "reorder_threshold": 12, "is_implant": False, "stock": 31, "expiry_months": 24},
    {"name": "Bupivacaine 0.5% Plain (10ml)", "sku": "AN-BUP-05-10", "category": "Anaesthesia & Analgesia", "unit": "vial", "unit_cost": Decimal("12.40"), "reorder_threshold": 10, "is_implant": False, "stock": 18, "expiry_months": 24},
    {"name": "Topical Anaesthetic Cream (Lidocaine/Prilocaine 5%, 30g)", "sku": "AN-TAC-5-30", "category": "Anaesthesia & Analgesia", "unit": "tube", "unit_cost": Decimal("22.00"), "reorder_threshold": 12, "is_implant": False, "stock": 43, "expiry_months": 24},
    {"name": "Topical Anaesthetic Ointment (Tetracaine 4%, 15g)", "sku": "AN-TOT-4-15", "category": "Anaesthesia & Analgesia", "unit": "tube", "unit_cost": Decimal("14.00"), "reorder_threshold": 8, "is_implant": False, "stock": 21, "expiry_months": 18},
    {"name": "Disposable Local Anaesthetic Syringe 5ml (Luer Lock)", "sku": "AN-SYR-5-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("19.00"), "reorder_threshold": 10, "is_implant": False, "stock": 28, "expiry_months": 48},
    {"name": "Syringe 3ml Luer Lock", "sku": "AN-SYR-3-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("9.50"), "reorder_threshold": 12, "is_implant": False, "stock": 47, "expiry_months": 60},
    {"name": "Syringe 5ml Luer Lock", "sku": "AN-SYR-5L-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("10.80"), "reorder_threshold": 12, "is_implant": False, "stock": 52, "expiry_months": 60},
    {"name": "Syringe 10ml Luer Lock", "sku": "AN-SYR-10-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("12.20"), "reorder_threshold": 10, "is_implant": False, "stock": 39, "expiry_months": 60},
    {"name": "Hypodermic Needle 25G x 25mm", "sku": "AN-NDL-2525-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("11.00"), "reorder_threshold": 12, "is_implant": False, "stock": 55, "expiry_months": 60},
    {"name": "Hypodermic Needle 27G x 13mm (Dental)", "sku": "AN-NDL-2713-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("10.20"), "reorder_threshold": 12, "is_implant": False, "stock": 44, "expiry_months": 60},
    {"name": "Winged Infusion Set (Butterfly Needle) 24G", "sku": "AN-BFL-24-100", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("16.50"), "reorder_threshold": 8, "is_implant": False, "stock": 19, "expiry_months": 48},
    {"name": "Adrenaline/Epinephrine 1mg/ml Ampoule", "sku": "AN-EPI-1-10", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("14.00"), "reorder_threshold": 4, "is_implant": False, "stock": 13, "expiry_months": 18},
    {"name": "Atropine 600mcg Ampoule", "sku": "AN-ATR-06-10", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("21.00"), "reorder_threshold": 3, "is_implant": False, "stock": 5, "expiry_months": 18},
    {"name": "Sterile Water for Injection 5ml", "sku": "AN-WFI-5-20", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("15.00"), "reorder_threshold": 6, "is_implant": False, "stock": 16, "expiry_months": 24},
    {"name": "Instant Cold Pack (Chemical Activation)", "sku": "AN-ICP-24", "category": "Anaesthesia & Analgesia", "unit": "pack", "unit_cost": Decimal("13.50"), "reorder_threshold": 8, "is_implant": False, "stock": 33, "expiry_months": 36},

    # -------------------------------------------------------------- injectables
    {"name": "HA Filler — Nose / Dorsal (1ml)", "sku": "IN-HAF-NSE-1", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("185.00"), "reorder_threshold": 8, "is_implant": False, "stock": 26, "expiry_months": 24},
    {"name": "HA Filler — Lip / Perioral (1ml)", "sku": "IN-HAF-LIP-1", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("180.00"), "reorder_threshold": 8, "is_implant": False, "stock": 31, "expiry_months": 24},
    {"name": "HA Filler — Cheek / Mid-Face (1ml)", "sku": "IN-HAF-CHK-1", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("195.00"), "reorder_threshold": 6, "is_implant": False, "stock": 18, "expiry_months": 24},
    {"name": "HA Filler — Tear Trough (0.5ml)", "sku": "IN-HAF-TT-05", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("165.00"), "reorder_threshold": 6, "is_implant": False, "stock": 14, "expiry_months": 24},
    {"name": "HA Filler — Chin & Jawline (1ml)", "sku": "IN-HAF-CHN-1", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("190.00"), "reorder_threshold": 6, "is_implant": False, "stock": 4, "expiry_months": 24},
    {"name": "HA Filler — Temple Volume Loss (1ml)", "sku": "IN-HAF-TMP-1", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("198.00"), "reorder_threshold": 4, "is_implant": False, "stock": 0, "expiry_months": 24},
    {"name": "Botulinum Toxin Type A 100U", "sku": "IN-BTX-A100", "category": "Injectables", "unit": "vial", "unit_cost": Decimal("365.00"), "reorder_threshold": 4, "is_implant": False, "stock": 17, "expiry_months": 18},
    {"name": "Botulinum Toxin Type A 200U", "sku": "IN-BTX-A200", "category": "Injectables", "unit": "vial", "unit_cost": Decimal("640.00"), "reorder_threshold": 3, "is_implant": False, "stock": 8, "expiry_months": 18},
    {"name": "Calcium Hydroxylapatite Biostimulator 1.5ml (Radiesse-type)", "sku": "IN-RAD-15", "category": "Injectables", "unit": "syringe", "unit_cost": Decimal("420.00"), "reorder_threshold": 4, "is_implant": False, "stock": 11, "expiry_months": 24},
    {"name": "Poly-L-Lactic Acid Biostimulator (Sculptra-type, 1 vial)", "sku": "IN-PLLA-V1", "category": "Injectables", "unit": "vial", "unit_cost": Decimal("480.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": 24},
    {"name": "PDO Absorbable Thread — Smooth (Box of 12)", "sku": "IN-PDO-SM-12", "category": "Injectables", "unit": "box", "unit_cost": Decimal("240.00"), "reorder_threshold": 3, "is_implant": False, "stock": 9, "expiry_months": 30},
    {"name": "PDO Absorbable Thread — Cog / Lift (Box of 12)", "sku": "IN-PDO-CG-12", "category": "Injectables", "unit": "box", "unit_cost": Decimal("295.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": 30},
    {"name": "PDO Thread Cartridge — Nose Lift (5x5)", "sku": "IN-PDO-NSE", "category": "Injectables", "unit": "box", "unit_cost": Decimal("180.00"), "reorder_threshold": 2, "is_implant": False, "stock": 5, "expiry_months": 30},
    {"name": "Lipolytic Injection (Phosphatidylcholine 250mg)", "sku": "IN-LIP-PPC", "category": "Injectables", "unit": "vial", "unit_cost": Decimal("135.00"), "reorder_threshold": 4, "is_implant": False, "stock": 10, "expiry_months": 18},
    {"name": "Deoxycholic Acid 10% (Submental Fat Dissolving)", "sku": "IN-DXA-10", "category": "Injectables", "unit": "vial", "unit_cost": Decimal("195.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": 18},
    {"name": "Mesotherapy Cocktail (Microneedling Hydration Blend)", "sku": "IN-MESO-5", "category": "Injectables", "unit": "vial", "unit_cost": Decimal("88.00"), "reorder_threshold": 4, "is_implant": False, "stock": 13, "expiry_months": 18},
    {"name": "Blunt Cannula 25G x 50mm (Filler Trained)", "sku": "IN-CAN-2550-10", "category": "Injectables", "unit": "pack", "unit_cost": Decimal("42.00"), "reorder_threshold": 5, "is_implant": False, "stock": 22, "expiry_months": 48},
    {"name": "Blunt Cannula 25G x 70mm (Deep Filler)", "sku": "IN-CAN-2570-10", "category": "Injectables", "unit": "pack", "unit_cost": Decimal("46.00"), "reorder_threshold": 5, "is_implant": False, "stock": 3, "expiry_months": 48},
    {"name": "Microcannula 27G x 40mm (Tear Trough)", "sku": "IN-CAN-2740-10", "category": "Injectables", "unit": "pack", "unit_cost": Decimal("44.00"), "reorder_threshold": 4, "is_implant": False, "stock": 15, "expiry_months": 48},

    # ------------------------------------------------------------------- PRP/hair
    {"name": "PRP Kit — Tubes, Activator & Butterfly (10 Tests)", "sku": "HP-PRP-KT10", "category": "Hair & PRP", "unit": "kit", "unit_cost": Decimal("78.00"), "reorder_threshold": 5, "is_implant": False, "stock": 18, "expiry_months": 24},
    {"name": "PRF Tube 10ml (Glass, Coated)", "sku": "HP-PRF-10-20", "category": "Hair & PRP", "unit": "pack", "unit_cost": Decimal("64.00"), "reorder_threshold": 4, "is_implant": False, "stock": 12, "expiry_months": 24},
    {"name": "PRP Centrifuge Tube 50ml (Conical)", "sku": "HP-PRP-50-10", "category": "Hair & PRP", "unit": "pack", "unit_cost": Decimal("58.00"), "reorder_threshold": 4, "is_implant": False, "stock": 0, "expiry_months": 24},
    {"name": "Platelet-Rich Fibrin (PRF) Kit — Face Rejuvenation", "sku": "HP-PRF-KT", "category": "Hair & PRP", "unit": "kit", "unit_cost": Decimal("96.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": 24},
    {"name": "Nanofat / Microfat Processing Kit", "sku": "HP-NF-KIT", "category": "Hair & PRP", "unit": "kit", "unit_cost": Decimal("185.00"), "reorder_threshold": 2, "is_implant": False, "stock": 5, "expiry_months": 30},
    {"name": "Fat Grafting Cannula 2.4mm (Blunt)", "sku": "HP-CAN-24", "category": "Hair & PRP", "unit": "piece", "unit_cost": Decimal("72.00"), "reorder_threshold": 4, "is_implant": False, "stock": 11, "expiry_months": 48},
    {"name": "Scalp Cooling Cap (Hair Transplant)", "sku": "HP-COOL-CAP", "category": "Hair & PRP", "unit": "piece", "unit_cost": Decimal("320.00"), "reorder_threshold": 1, "is_implant": False, "stock": 2, "expiry_months": None},
    {"name": "Hair Grafting Punch Set (0.8-1.0mm)", "sku": "HP-PUNCH-SET", "category": "Hair & PRP", "unit": "set", "unit_cost": Decimal("210.00"), "reorder_threshold": 1, "is_implant": False, "stock": 3, "expiry_months": None},
    {"name": "Microneedling Scalp Serum (Hair Growth, 30ml)", "sku": "HP-SER-SCALP", "category": "Hair & PRP", "unit": "bottle", "unit_cost": Decimal("72.00"), "reorder_threshold": 5, "is_implant": False, "stock": 16, "expiry_months": 18},
    {"name": "Growth Factor Serum (EGF, 30ml)", "sku": "HP-SER-EGF", "category": "Hair & PRP", "unit": "bottle", "unit_cost": Decimal("148.00"), "reorder_threshold": 4, "is_implant": False, "stock": 9, "expiry_months": 18},
    {"name": "Stem Cell Serum (Hair & Face, 30ml)", "sku": "HP-SER-STEM", "category": "Hair & PRP", "unit": "bottle", "unit_cost": Decimal("185.00"), "reorder_threshold": 3, "is_implant": False, "stock": 5, "expiry_months": 18},

    # ------------------------------------------------------------ device consumables
    {"name": "CO2 Laser Handpiece — Fractional 1.5mm Tip", "sku": "DC-CO2-FR15", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("425.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": 36},
    {"name": "CO2 Laser Handpiece — Fractional 2.0mm Tip", "sku": "DC-CO2-FR20", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("425.00"), "reorder_threshold": 3, "is_implant": False, "stock": 5, "expiry_months": 36},
    {"name": "CO2 Laser Handpiece — Non-Fractional Tip", "sku": "DC-CO2-NF01", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("395.00"), "reorder_threshold": 2, "is_implant": False, "stock": 4, "expiry_months": 36},
    {"name": "CO2 Laser UltraPulse Resurfacing Tip", "sku": "DC-CO2-UP01", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("520.00"), "reorder_threshold": 2, "is_implant": False, "stock": 3, "expiry_months": 36},
    {"name": "Erbium:YAG Laser Fractional Tip", "sku": "DC-ERB-FR01", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("380.00"), "reorder_threshold": 2, "is_implant": False, "stock": 2, "expiry_months": 36},
    {"name": "Nd:YAG 1064nm Spot Handpiece (Laser Toning)", "sku": "DC-NDY-SPOT", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("460.00"), "reorder_threshold": 2, "is_implant": False, "stock": 3, "expiry_months": 36},
    {"name": "Nd:YAG 1064nm Mopps (Hair Removal)", "sku": "DC-NDY-MOPP", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("285.00"), "reorder_threshold": 3, "is_implant": False, "stock": 4, "expiry_months": 36},
    {"name": "Diode Laser Handpiece 808nm (Hair Removal)", "sku": "DC-DIO-808", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("340.00"), "reorder_threshold": 2, "is_implant": False, "stock": 2, "expiry_months": 36},
    {"name": "Diode Laser Sliver Probe (Vascular/Skin)", "sku": "DC-DIO-SLV", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("295.00"), "reorder_threshold": 2, "is_implant": False, "stock": 0, "expiry_months": 36},
    {"name": "IPL Filter Set (Cutoff Filters)", "sku": "DC-IPL-FLT", "category": "Device Consumables", "unit": "set", "unit_cost": Decimal("540.00"), "reorder_threshold": 1, "is_implant": False, "stock": 2, "expiry_months": 60},
    {"name": "IPL Handpiece Flashlamp / Bulb", "sku": "DC-IPL-BULB", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("310.00"), "reorder_threshold": 2, "is_implant": False, "stock": 3, "expiry_months": 36},
    {"name": "RF Microneedling Needle Cartridge (24-pin)", "sku": "DC-RF-24P", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("185.00"), "reorder_threshold": 4, "is_implant": False, "stock": 11, "expiry_months": 24},
    {"name": "RF Microneedling Fractional Tip (8-pin)", "sku": "DC-RF-08P", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("165.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": 24},
    {"name": "Morpheus8-type RF Fractional Tip", "sku": "DC-RF-MORP", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("410.00"), "reorder_threshold": 2, "is_implant": False, "stock": 4, "expiry_months": 24},
    {"name": "HIFU Cartridge / Ultrasound Transducer", "sku": "DC-HIFU-CRT", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("480.00"), "reorder_threshold": 2, "is_implant": False, "stock": 2, "expiry_months": 36},
    {"name": "Cryolipolysis Applicator Pad", "sku": "DC-CRY-PAD", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("350.00"), "reorder_threshold": 2, "is_implant": False, "stock": 3, "expiry_months": None},
    {"name": "Cryolipolysis Cold Tip / Head", "sku": "DC-CRY-TIP", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("275.00"), "reorder_threshold": 2, "is_implant": False, "stock": 2, "expiry_months": None},
    {"name": "HydraFacial Serum Infusion Ampoule (Clear)", "sku": "DC-HYD-CLR", "category": "Device Consumables", "unit": "pack", "unit_cost": Decimal("148.00"), "reorder_threshold": 3, "is_implant": False, "stock": 8, "expiry_months": 12},
    {"name": "HydraFacial Tip Set (5 Pack)", "sku": "DC-HYD-TIP", "category": "Device Consumables", "unit": "pack", "unit_cost": Decimal("120.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": None},
    {"name": "Ultrasound Gel 250ml (Bottle)", "sku": "DC-USG-250", "category": "Device Consumables", "unit": "bottle", "unit_cost": Decimal("9.50"), "reorder_threshold": 8, "is_implant": False, "stock": 24, "expiry_months": 24},
    {"name": "Conductive Gel for RF / Diathermy 250g", "sku": "DC-RFG-250", "category": "Device Consumables", "unit": "jar", "unit_cost": Decimal("14.00"), "reorder_threshold": 6, "is_implant": False, "stock": 15, "expiry_months": 24},
    {"name": "Post-Treatment Cooling Gel 500ml", "sku": "DC-COOL-500", "category": "Device Consumables", "unit": "bottle", "unit_cost": Decimal("18.00"), "reorder_threshold": 6, "is_implant": False, "stock": 19, "expiry_months": 24},
    {"name": "Laser Safety Eyewear — Patient (OD 6+)", "sku": "DC-EYE-P6", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("68.00"), "reorder_threshold": 4, "is_implant": False, "stock": 12, "expiry_months": None},
    {"name": "Laser Safety Eyewear — Operator (OD 8+)", "sku": "DC-EYE-O8", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("185.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": None},
    {"name": "Microdermabrasion Diamond Tip", "sku": "DC-MDA-DIA", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("42.00"), "reorder_threshold": 3, "is_implant": False, "stock": 9, "expiry_months": None},
    {"name": "Dermaplaning Blade (10 Pack)", "sku": "DC-DPL-BLD", "category": "Device Consumables", "unit": "pack", "unit_cost": Decimal("36.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": 36},
    {"name": "Ultrasonic Scalpel Tip (Harmonic)", "sku": "DC-USC-TIP", "category": "Device Consumables", "unit": "piece", "unit_cost": Decimal("590.00"), "reorder_threshold": 2, "is_implant": False, "stock": 3, "expiry_months": 24},
    {"name": "Electrocautery Pencil Tip (Disposable)", "sku": "DC-ELE-TIP", "category": "Device Consumables", "unit": "box", "unit_cost": Decimal("165.00"), "reorder_threshold": 2, "is_implant": False, "stock": 4, "expiry_months": 36},
    {"name": "Electrosurgical Grounding Pad (Split)", "sku": "DC-ELE-PAD", "category": "Device Consumables", "unit": "box", "unit_cost": Decimal("88.00"), "reorder_threshold": 4, "is_implant": False, "stock": 10, "expiry_months": 36},

    # ------------------------------------------------------------------ post-op
    {"name": "Compression Garment — Face Mask (Chin & Jaw)", "sku": "PO-CG-FACE", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("45.00"), "reorder_threshold": 6, "is_implant": False, "stock": 22, "expiry_months": None},
    {"name": "Compression Garment — Chin", "sku": "PO-CG-CHIN", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("38.00"), "reorder_threshold": 6, "is_implant": False, "stock": 17, "expiry_months": None},
    {"name": "Compression Garment — Breast (Post Augmentation)", "sku": "PO-CG-BR-A", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("78.00"), "reorder_threshold": 5, "is_implant": False, "stock": 19, "expiry_months": None},
    {"name": "Compression Garment — Breast (Post Reduction)", "sku": "PO-CG-BR-R", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("82.00"), "reorder_threshold": 4, "is_implant": False, "stock": 3, "expiry_months": None},
    {"name": "Compression Garment — Abdomen", "sku": "PO-CG-ABD", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("85.00"), "reorder_threshold": 5, "is_implant": False, "stock": 24, "expiry_months": None},
    {"name": "Compression Garment — Full Body Suit", "sku": "PO-CG-FULL", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("165.00"), "reorder_threshold": 3, "is_implant": False, "stock": 11, "expiry_months": None},
    {"name": "Compression Garment — Thigh (Body Shaper)", "sku": "PO-CG-THG", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("78.00"), "reorder_threshold": 4, "is_implant": False, "stock": 14, "expiry_months": None},
    {"name": "Compression Garment — Calf / Sleeve", "sku": "PO-CG-CALF", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("52.00"), "reorder_threshold": 4, "is_implant": False, "stock": 12, "expiry_months": None},
    {"name": "Compression Sleeve — Arm (Brachioplasty)", "sku": "PO-CG-ARM", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("48.00"), "reorder_threshold": 4, "is_implant": False, "stock": 2, "expiry_months": None},
    {"name": "Elastic Compression Bandage (Ace Wrap, 7.5cm)", "sku": "PO-ACE-075", "category": "Post-Op Care", "unit": "roll", "unit_cost": Decimal("7.20"), "reorder_threshold": 12, "is_implant": False, "stock": 38, "expiry_months": None},
    {"name": "Silicone Scar Sheet — Small", "sku": "PO-SS-SM", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("24.00"), "reorder_threshold": 8, "is_implant": False, "stock": 27, "expiry_months": 36},
    {"name": "Silicone Scar Sheet — Large", "sku": "PO-SS-LG", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("34.00"), "reorder_threshold": 6, "is_implant": False, "stock": 16, "expiry_months": 36},
    {"name": "Silicone Gel Sheeting (Scar Treatment, 15g)", "sku": "PO-SGS-15", "category": "Post-Op Care", "unit": "tube", "unit_cost": Decimal("42.00"), "reorder_threshold": 6, "is_implant": False, "stock": 13, "expiry_months": 24},
    {"name": "Mepitel Adhesive Contact Layer (Post-Op Wound)", "sku": "PO-MEP-10", "category": "Post-Op Care", "unit": "pack", "unit_cost": Decimal("128.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": 36},
    {"name": "PICO Dressings (Post-Op, Single Use)", "sku": "PO-PICO-SGL", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("29.00"), "reorder_threshold": 8, "is_implant": False, "stock": 20, "expiry_months": 36},
    {"name": "Surgical Drainage Bag (Suction, 400ml)", "sku": "PO-DRN-400", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("8.90"), "reorder_threshold": 10, "is_implant": False, "stock": 31, "expiry_months": 48},
    {"name": "Blake Silicone Drain (Round, 10 Fr)", "sku": "PO-BLD-10", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("145.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": 36},
    {"name": "Arm Sling / Immobiliser (Adjustable)", "sku": "PO-SLG-ADJ", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("26.00"), "reorder_threshold": 5, "is_implant": False, "stock": 12, "expiry_months": None},
    {"name": "Nipple Shield (Post-Augmentation Protection)", "sku": "PO-NIP-SHD", "category": "Post-Op Care", "unit": "piece", "unit_cost": Decimal("11.50"), "reorder_threshold": 8, "is_implant": False, "stock": 25, "expiry_months": None},
    {"name": "Perineal Irrigation / Sitz Bath Kit", "sku": "PO-SIT-KIT", "category": "Post-Op Care", "unit": "kit", "unit_cost": Decimal("19.00"), "reorder_threshold": 4, "is_implant": False, "stock": 9, "expiry_months": None},
    {"name": "Arnica Bruise Gel (Post-Op)", "sku": "PO-ARN-GEL", "category": "Post-Op Care", "unit": "tube", "unit_cost": Decimal("16.00"), "reorder_threshold": 8, "is_implant": False, "stock": 21, "expiry_months": 24},
    {"name": "Post-Op Wound Care Kit (Patient Take-Home)", "sku": "PO-CARE-KIT", "category": "Post-Op Care", "unit": "kit", "unit_cost": Decimal("58.00"), "reorder_threshold": 10, "is_implant": False, "stock": 34, "expiry_months": None},
    {"name": "Scar Gel SPF 50+ (Post-Op Sun Protection)", "sku": "PO-SCAR-SPF", "category": "Post-Op Care", "unit": "tube", "unit_cost": Decimal("32.00"), "reorder_threshold": 8, "is_implant": False, "stock": 18, "expiry_months": 18},

    # ---------------------------------------------------------------- implants
    {"name": "Breast Implant — Round Smooth, Moderate 250cc", "sku": "IM-BI-RS-250", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("495.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Breast Implant — Round Smooth, Moderate 300cc", "sku": "IM-BI-RS-300", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("520.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Breast Implant — Round Smooth, Moderate 350cc", "sku": "IM-BI-RS-350", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("545.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Breast Implant — Round Smooth, High 400cc", "sku": "IM-BI-RS-400", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("575.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Breast Implant — Round Textured, Moderate 325cc", "sku": "IM-BI-RT-325", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("560.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Breast Implant — Anatomical/Teardrop 300cc", "sku": "IM-BI-AT-300", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("610.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Breast Implant — Anatomical/Teardrop 350cc", "sku": "IM-BI-AT-350", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("640.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Breast Implant — Anatomical/Teardrop 400cc", "sku": "IM-BI-AT-400", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("680.00"), "reorder_threshold": 1, "is_implant": True, "stock": 0, "expiry_months": 60},
    {"name": "Breast Implant Sizer Set (Consultation)", "sku": "IM-BI-SIZER", "category": "Implants & Prosthetics", "unit": "set", "unit_cost": Decimal("380.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Breast Tissue Expander (Rectangular, 400cc)", "sku": "IM-TX-EXP-40", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("720.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Chin Implant — Small (Extended)", "sku": "IM-CHIN-S", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("295.00"), "reorder_threshold": 1, "is_implant": True, "stock": 3, "expiry_months": 60},
    {"name": "Chin Implant — Medium (Extended)", "sku": "IM-CHIN-M", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("320.00"), "reorder_threshold": 1, "is_implant": True, "stock": 3, "expiry_months": 60},
    {"name": "Chin Implant — Large (Extended)", "sku": "IM-CHIN-L", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("355.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Cheek / Malar Implant (Standard)", "sku": "IM-CHEEK-S", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("285.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Submental / Jawline Implant (Custom)", "sku": "IM-JAW-CUS", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("640.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Orbital Rim Implant (Eye)", "sku": "IM-ORB-RIM", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("410.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Nasal / Septal Implant", "sku": "IM-NOSE-IMP", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("395.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Gluteal Implant (Round)", "sku": "IM-GLU-01", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("890.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Calf Implant", "sku": "IM-CALF-01", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("760.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Silicone Facial Implant (Chin & Paranasal, M)", "sku": "IM-SIL-FAC-M", "category": "Implants & Prosthetics", "unit": "pair", "unit_cost": Decimal("330.00"), "reorder_threshold": 1, "is_implant": True, "stock": 2, "expiry_months": 60},
    {"name": "Miniplate & Screw Fixation Set (Frontozygomatic)", "sku": "IM-FIX-MINI", "category": "Implants & Prosthetics", "unit": "set", "unit_cost": Decimal("980.00"), "reorder_threshold": 1, "is_implant": True, "stock": 1, "expiry_months": 60},
    {"name": "Titanium Mini Plate (L-Shape, 1.5mm)", "sku": "IM-PL-L15", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("165.00"), "reorder_threshold": 2, "is_implant": True, "stock": 4, "expiry_months": 60},
    {"name": "Surgical Steel Cerclage Wire (0.6mm)", "sku": "IM-WIR-06", "category": "Implants & Prosthetics", "unit": "piece", "unit_cost": Decimal("42.00"), "reorder_threshold": 4, "is_implant": True, "stock": 9, "expiry_months": 60},

    # --------------------------------------------------------------- skincare
    {"name": "Medical Grade Sunscreen SPF 50+ (Broad Spectrum, 50ml)", "sku": "SK-SUN-50-50", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("36.00"), "reorder_threshold": 12, "is_implant": False, "stock": 42, "expiry_months": 18},
    {"name": "Post-Procedure Mineral Sunscreen SPF 30 (Titanium, 50ml)", "sku": "SK-SUN-MIN-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("42.00"), "reorder_threshold": 10, "is_implant": False, "stock": 28, "expiry_months": 18},
    {"name": "Vitamin C Serum 15% (L-Ascorbic Acid, 30ml)", "sku": "SK-VTC-15-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("65.00"), "reorder_threshold": 8, "is_implant": False, "stock": 26, "expiry_months": 12},
    {"name": "Encapsulated Retinol Serum 0.3% (30ml)", "sku": "SK-RET-03-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("78.00"), "reorder_threshold": 6, "is_implant": False, "stock": 19, "expiry_months": 12},
    {"name": "Retinol Cream 0.5% (30g)", "sku": "SK-RET-05-30", "category": "Skincare & Home Care", "unit": "jar", "unit_cost": Decimal("56.00"), "reorder_threshold": 6, "is_implant": False, "stock": 17, "expiry_months": 12},
    {"name": "Hyaluronic Acid Moisturizer (HA 2%, 50ml)", "sku": "SK-HA-MOIST-50", "category": "Skincare & Home Care", "unit": "jar", "unit_cost": Decimal("48.00"), "reorder_threshold": 8, "is_implant": False, "stock": 24, "expiry_months": 18},
    {"name": "Niacinamide 10% Serum (30ml)", "sku": "SK-NIA-10-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("38.00"), "reorder_threshold": 8, "is_implant": False, "stock": 31, "expiry_months": 18},
    {"name": "Peptide Serum (Multi-Peptide Complex, 30ml)", "sku": "SK-PEP-CX-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("85.00"), "reorder_threshold": 5, "is_implant": False, "stock": 13, "expiry_months": 18},
    {"name": "Post-Procedure Healing Gel (Calendula + Panthenol)", "sku": "SK-HEAL-GEL", "category": "Skincare & Home Care", "unit": "tube", "unit_cost": Decimal("22.00"), "reorder_threshold": 12, "is_implant": False, "stock": 38, "expiry_months": 18},
    {"name": "Ceramide Barrier Repair Cream (50g)", "sku": "SK-CER-CRM-50", "category": "Skincare & Home Care", "unit": "jar", "unit_cost": Decimal("58.00"), "reorder_threshold": 6, "is_implant": False, "stock": 16, "expiry_months": 18},
    {"name": "Gentle Foaming Cleanser (200ml)", "sku": "SK-CLN-FM-200", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("24.00"), "reorder_threshold": 8, "is_implant": False, "stock": 29, "expiry_months": 24},
    {"name": "Soothing Micellar Cleansing Water (400ml)", "sku": "SK-CLN-MIC-400", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("19.00"), "reorder_threshold": 8, "is_implant": False, "stock": 34, "expiry_months": 24},
    {"name": "Azelaic Acid Cream 15% (30g)", "sku": "SK-AZE-15-30", "category": "Skincare & Home Care", "unit": "jar", "unit_cost": Decimal("46.00"), "reorder_threshold": 5, "is_implant": False, "stock": 14, "expiry_months": 18},
    {"name": "Hydroquinone Cream 4% (30g)", "sku": "SK-HQ-04-30", "category": "Skincare & Home Care", "unit": "jar", "unit_cost": Decimal("42.00"), "reorder_threshold": 4, "is_implant": False, "stock": 9, "expiry_months": 18},
    {"name": "Depigmenting Serum (Arbutin + Tranexamic, 30ml)", "sku": "SK-DEP-SER-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("68.00"), "reorder_threshold": 5, "is_implant": False, "stock": 18, "expiry_months": 18},
    {"name": "Mandelic Acid Peel 20% (30ml)", "sku": "SK-PEL-MAN-20", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("52.00"), "reorder_threshold": 4, "is_implant": False, "stock": 12, "expiry_months": 12},
    {"name": "Glycolic Acid Peel 50% (30ml)", "sku": "SK-PEL-GLY-50", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("58.00"), "reorder_threshold": 4, "is_implant": False, "stock": 7, "expiry_months": 12},
    {"name": "Salicylic Acid Peel 30% (Jessner, 30ml)", "sku": "SK-PEL-SAL-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("54.00"), "reorder_threshold": 4, "is_implant": False, "stock": 4, "expiry_months": 12},
    {"name": "Jessner Peel Solution (30ml)", "sku": "SK-PEL-JSN-30", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("56.00"), "reorder_threshold": 3, "is_implant": False, "stock": 0, "expiry_months": 12},
    {"name": "TCA Peel 20% (30ml)", "sku": "SK-PEL-TCA-20", "category": "Skincare & Home Care", "unit": "bottle", "unit_cost": Decimal("62.00"), "reorder_threshold": 3, "is_implant": False, "stock": 6, "expiry_months": 12},
    {"name": "Chemical Peel Pre-Prep Kit (Pre & Post)", "sku": "SK-PEL-PRE", "category": "Skincare & Home Care", "unit": "kit", "unit_cost": Decimal("44.00"), "reorder_threshold": 5, "is_implant": False, "stock": 20, "expiry_months": 12},
    {"name": "Hydrocolloid Acne Patch (24 Pack)", "sku": "SK-PTCH-ACNE", "category": "Skincare & Home Care", "unit": "pack", "unit_cost": Decimal("14.00"), "reorder_threshold": 8, "is_implant": False, "stock": 41, "expiry_months": 24},
    {"name": "Microneedling Serum (Growth Factor, 5ml)", "sku": "SK-SER-MN-5", "category": "Skincare & Home Care", "unit": "vial", "unit_cost": Decimal("96.00"), "reorder_threshold": 5, "is_implant": False, "stock": 15, "expiry_months": 12},
    {"name": "Hyaluronic Acid Sheet Mask (5 Pack)", "sku": "SK-MSK-HA-5", "category": "Skincare & Home Care", "unit": "pack", "unit_cost": Decimal("32.00"), "reorder_threshold": 6, "is_implant": False, "stock": 22, "expiry_months": 18},
    {"name": "Collagen Sheet Mask (5 Pack)", "sku": "SK-MSK-COL-5", "category": "Skincare & Home Care", "unit": "pack", "unit_cost": Decimal("38.00"), "reorder_threshold": 5, "is_implant": False, "stock": 17, "expiry_months": 18},
    {"name": "Lip Balm SPF 15 (Post-Procedure)", "sku": "SK-LIP-SPF15", "category": "Skincare & Home Care", "unit": "piece", "unit_cost": Decimal("9.50"), "reorder_threshold": 10, "is_implant": False, "stock": 44, "expiry_months": 24},
    {"name": "Mole & Skin Tag Removal Kit", "sku": "SK-MOL-KIT", "category": "Skincare & Home Care", "unit": "kit", "unit_cost": Decimal("72.00"), "reorder_threshold": 2, "is_implant": False, "stock": 6, "expiry_months": 36},

    # ------------------------------------------------------- clinic consumables
    {"name": "Disposable Treatment Bed Sheet", "sku": "CC-BED-SHEET", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("16.00"), "reorder_threshold": 10, "is_implant": False, "stock": 33, "expiry_months": None},
    {"name": "Disposable Head Cover / Hair Cap", "sku": "CC-HAIR-CAP", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("13.00"), "reorder_threshold": 10, "is_implant": False, "stock": 27, "expiry_months": None},
    {"name": "Disposable Face Shield (with Ear Loops)", "sku": "CC-FACE-SHD", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("18.00"), "reorder_threshold": 8, "is_implant": False, "stock": 21, "expiry_months": 36},
    {"name": "Disposable Apron (Non-Sterile)", "sku": "CC-APRON", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("22.00"), "reorder_threshold": 6, "is_implant": False, "stock": 15, "expiry_months": None},
    {"name": "Disposable Shoe Covers", "sku": "CC-SHOE-COV", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("15.00"), "reorder_threshold": 8, "is_implant": False, "stock": 19, "expiry_months": None},
    {"name": "Treatment Chair Cover (Disposable)", "sku": "CC-CHR-COV", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("26.00"), "reorder_threshold": 6, "is_implant": False, "stock": 12, "expiry_months": None},
    {"name": "Nitrile Finger Cots", "sku": "CC-FINGER-COT", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("11.00"), "reorder_threshold": 6, "is_implant": False, "stock": 14, "expiry_months": None},
    {"name": "Clinical Waste Bag — Yellow (25 Pack)", "sku": "CC-WST-YEL-25", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("17.00"), "reorder_threshold": 8, "is_implant": False, "stock": 25, "expiry_months": None},
    {"name": "Domestic Waste Bag — Black (30 Pack)", "sku": "CC-WST-BLK-30", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("12.00"), "reorder_threshold": 8, "is_implant": False, "stock": 23, "expiry_months": None},
    {"name": "Sharps Container 1 Litre (Yellow)", "sku": "CC-SHRP-1L", "category": "Clinic Consumables", "unit": "piece", "unit_cost": Decimal("9.80"), "reorder_threshold": 4, "is_implant": False, "stock": 8, "expiry_months": 60},
    {"name": "Surface Disinfectant Wipes (Tub of 75)", "sku": "CC-DIS-WIPE-75", "category": "Clinic Consumables", "unit": "tub", "unit_cost": Decimal("14.50"), "reorder_threshold": 10, "is_implant": False, "stock": 30, "expiry_months": 24},
    {"name": "Instrument Ultrasonic Cleaner Solution (1 Litre)", "sku": "CC-ULT-SOL-1L", "category": "Clinic Consumables", "unit": "bottle", "unit_cost": Decimal("28.00"), "reorder_threshold": 4, "is_implant": False, "stock": 6, "expiry_months": 24},
    {"name": "Surgical Hand Scrub Solution 500ml", "sku": "CC-SCRUB-500", "category": "Clinic Consumables", "unit": "bottle", "unit_cost": Decimal("19.00"), "reorder_threshold": 6, "is_implant": False, "stock": 13, "expiry_months": 24},
    {"name": "Stainless Steel Instrument Tray (Reusable)", "sku": "CC-TRAY-SS", "category": "Clinic Consumables", "unit": "piece", "unit_cost": Decimal("42.00"), "reorder_threshold": 2, "is_implant": False, "stock": 5, "expiry_months": None},
    {"name": "Stainless Steel Kidney Dish (Reusable)", "sku": "CC-KIDNEY-SS", "category": "Clinic Consumables", "unit": "piece", "unit_cost": Decimal("16.00"), "reorder_threshold": 3, "is_implant": False, "stock": 7, "expiry_months": None},
    {"name": "Wooden Tongue Depressor", "sku": "CC-TNG-DEP", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("5.80"), "reorder_threshold": 6, "is_implant": False, "stock": 16, "expiry_months": 36},
    {"name": "Pulse Oximeter Probe (Adult)", "sku": "CC-PULS-PRB", "category": "Clinic Consumables", "unit": "piece", "unit_cost": Decimal("48.00"), "reorder_threshold": 2, "is_implant": False, "stock": 3, "expiry_months": None},
    {"name": "NIBP Cuff — Adult (Reusable)", "sku": "CC-NIBP-ADT", "category": "Clinic Consumables", "unit": "piece", "unit_cost": Decimal("56.00"), "reorder_threshold": 2, "is_implant": False, "stock": 4, "expiry_months": None},
    {"name": "Thermometer Probe Covers", "sku": "CC-THRM-COV", "category": "Clinic Consumables", "unit": "pack", "unit_cost": Decimal("13.00"), "reorder_threshold": 6, "is_implant": False, "stock": 18, "expiry_months": 36},

    # ------------------------------------------------------ consultation aids
    {"name": "Breast Sizing Implant Set (Consultation, 8 Sizes)", "sku": "CA-SIZE-BR", "category": "Consultation Aids", "unit": "set", "unit_cost": Decimal("420.00"), "reorder_threshold": 1, "is_implant": False, "stock": 1, "expiry_months": None},
    {"name": "Chin / Jawline Sizer (Silicone, Graduated)", "sku": "CA-SIZE-CHIN", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("185.00"), "reorder_threshold": 1, "is_implant": False, "stock": 2, "expiry_months": None},
    {"name": "External Prosthetic Breast Form (Left)", "sku": "CA-BRF-L", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("96.00"), "reorder_threshold": 1, "is_implant": False, "stock": 2, "expiry_months": None},
    {"name": "External Prosthetic Breast Form (Right)", "sku": "CA-BRF-R", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("96.00"), "reorder_threshold": 1, "is_implant": False, "stock": 2, "expiry_months": None},
    {"name": "Facial Assessment / Facial Analysis Grid", "sku": "CA-FA-GRID", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("58.00"), "reorder_threshold": 1, "is_implant": False, "stock": 3, "expiry_months": None},
    {"name": "Caliper for Fat Grafting Measurement", "sku": "CA-CALIPER", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("245.00"), "reorder_threshold": 1, "is_implant": False, "stock": 1, "expiry_months": None},
    {"name": "Anatomical Face Model (Teaching & Consent)", "sku": "CA-ANAT-FACE", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("320.00"), "reorder_threshold": 1, "is_implant": False, "stock": 1, "expiry_months": None},
    {"name": "Nose Aesthetic Assessment Tool (Rhinoplasty Simulator)", "sku": "CA-NOSE-SIM", "category": "Consultation Aids", "unit": "piece", "unit_cost": Decimal("275.00"), "reorder_threshold": 1, "is_implant": False, "stock": 1, "expiry_months": None},
]

FIELD_KEYS = ("name", "sku", "category", "unit", "unit_cost", "reorder_threshold", "is_implant")


def _lot_prefix() -> str:
    return "LOT" + date.today().strftime("%y%m")


async def _ensure_demo_practice(session: AsyncSession) -> Practice:
    result = await session.execute(
        text("SELECT id FROM practices WHERE email = :email"), {"email": DEMO_PRACTICE["email"]}
    )
    row = result.fetchone()
    if row:
        return await session.get(Practice, row[0])
    practice = Practice(**DEMO_PRACTICE)
    session.add(practice)
    await session.flush()
    return practice


async def _seed_agents(session: AsyncSession, practice_id) -> int:
    existing = await session.execute(
        select(AgentConfig.agent_type).where(AgentConfig.practice_id == practice_id)
    )
    have = {r[0] for r in existing.all()}
    added = 0
    for agent_type in AGENT_TYPES:
        if agent_type in have:
            continue
        session.add(AgentConfig(
            practice_id=practice_id,
            agent_type=agent_type,
            enabled=True,
            config={"tone": "professional", "language": "en"},
        ))
        added += 1
    return added


async def _seed_inventory(session: AsyncSession, practice_id) -> tuple[int, int, int]:
    """Returns (items_added, items_updated, batches_added)."""
    existing = await session.execute(
        select(InventoryItem).where(InventoryItem.practice_id == practice_id)
    )
    by_sku: dict[str, InventoryItem] = {}
    for item in existing.scalars().all():
        if item.sku:
            by_sku[item.sku] = item

    lot = _lot_prefix()
    today = date.today()
    items_added = items_updated = batches_added = 0

    # Items that already exist — only the catalogue fields are refreshed. Batch
    # history, on-hand stock and is_active are deliberately left untouched so
    # re-running the script can't resurrect an archived item or invent stock.
    item_ids_needing_stock: list[tuple[InventoryItem, int, int | None]] = []

    for entry in CATALOGUE:
        existing_item = by_sku.get(entry["sku"])
        if existing_item is None:
            item = InventoryItem(practice_id=practice_id, **{k: entry[k] for k in FIELD_KEYS})
            session.add(item)
            by_sku[entry["sku"]] = item
            items_added += 1
        else:
            item = existing_item
            dirty = False
            for key in FIELD_KEYS:
                if getattr(item, key) != entry[key]:
                    setattr(item, key, entry[key])
                    dirty = True
            if dirty:
                items_updated += 1
        item_ids_needing_stock.append((item, entry["stock"], entry["expiry_months"]))

    await session.flush()

    # Only items with NO batches at all get the starting stock — that's the
    # "brand new practice" case. Anything already stocked keeps its real
    # received/consumed/wasted history.
    for item, stock, expiry_months in item_ids_needing_stock:
        if item.id is None or stock <= 0:
            continue
        has_batches = await session.execute(
            select(InventoryBatch.id).where(InventoryBatch.inventory_item_id == item.id).limit(1)
        )
        if has_batches.scalar_one_or_none() is not None:
            continue
        received = today - timedelta(days=(index_seed_offset(item.sku) % 45))
        session.add(InventoryBatch(
            inventory_item_id=item.id,
            lot_number=f"{lot}-{item.sku[-4:]}",
            quantity=stock,
            expiry_date=_add_months(received, expiry_months) if expiry_months else None,
            received_at=received,
        ))
        batches_added += 1

    return items_added, items_updated, batches_added


def index_seed_offset(sku: str) -> int:
    return sum(ord(ch) for ch in sku)


def _add_months(start: date, months: int) -> date:
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    # Clamp the day so e.g. 31 Jan + 1 month doesn't blow up.
    day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                           31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


async def seed(practice_email: str | None = None) -> None:
    async with async_session_factory() as session:
        if practice_email:
            result = await session.execute(
                text("SELECT id FROM practices WHERE email = :email"), {"email": practice_email}
            )
            row = result.fetchone()
            if not row:
                raise SystemExit(f"No practice found with email {practice_email!r}")
            practices = [await session.get(Practice, row[0])]
        else:
            # Always make sure the demo practice exists so there's something to
            # sign in to, then seed EVERY practice in the database. Seeding per
            # practice (not one hard-coded practice) is what makes the data show
            # up for whichever account you actually sign in with.
            demo = await _ensure_demo_practice(session)
            await session.flush()
            all_practices = (await session.execute(select(Practice))).scalars().all()
            practices = list({p.id: p for p in all_practices}.values()) or [demo]

        total_items = total_updated = total_batches = 0
        for practice in practices:
            agents = await _seed_agents(session, practice.id)
            await session.flush()
            added, updated, batches = await _seed_inventory(session, practice.id)
            total_items += added
            total_updated += updated
            total_batches += batches
            print(
                f"[{practice.name} <{practice.email}>] "
                f"agents +{agents} | items +{added} (updated {updated}) | stock batches +{batches}"
            )

        await session.commit()
        print(
            f"\nDone. {len(practices)} practice(es) — "
            f"{total_items} new items, {total_updated} refreshed, {total_batches} stock batches."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo practice + realistic aesthetic-clinic inventory.")
    parser.add_argument(
        "--practice-email",
        help="Only seed this practice (default: seed every practice in the database).",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.practice_email))


if __name__ == "__main__":
    main()
