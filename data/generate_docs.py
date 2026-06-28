#!/usr/bin/env python3
"""Generate synthetic AkzoNobel coatings documents (real multi-page PDFs).

Produces:
  - 8 GHS Safety Data Sheets (16-section structure) under data/output/docs/sds/
  - 6 supplier contracts under data/output/docs/contracts/

Each doc embeds clearly extractable ground-truth fields so downstream
ai_extract accuracy can be checked against the README ground-truth table.

Requires: reportlab (pip3 install --user reportlab). If the default python3
cannot import reportlab, run this with an interpreter that can, e.g.:
  /opt/homebrew/bin/python3.10 data/generate_docs.py
"""

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_SDS = os.path.join(HERE, "output", "docs", "sds")
OUT_CONTRACTS = os.path.join(HERE, "output", "docs", "contracts")

AKZO_BLUE = colors.HexColor("#0033A0")
GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#EEEEEE")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("AkzoTitle", parent=s["Title"], textColor=AKZO_BLUE,
                         fontSize=18, spaceAfter=4, alignment=TA_LEFT))
    s.add(ParagraphStyle("AkzoSub", parent=s["Normal"], textColor=GREY,
                         fontSize=9, spaceAfter=10))
    s.add(ParagraphStyle("Sec", parent=s["Heading2"], textColor=AKZO_BLUE,
                         fontSize=12, spaceBefore=10, spaceAfter=4))
    s.add(ParagraphStyle("Body", parent=s["Normal"], fontSize=9.5,
                         leading=13, spaceAfter=3))
    s.add(ParagraphStyle("Field", parent=s["Normal"], fontSize=9.5,
                         leading=13, spaceAfter=2))
    s.add(ParagraphStyle("Foot", parent=s["Normal"], fontSize=7.5,
                         textColor=GREY, alignment=TA_CENTER))
    return s


S = styles()


def kv_table(rows):
    t = Table(rows, colWidths=[6.0 * cm, 11.0 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (0, 0), (0, -1), AKZO_BLUE),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, LIGHT),
    ]))
    return t


def _header_footer(doc_title):
    def fn(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(AKZO_BLUE)
        canvas.rect(0, A4[1] - 1.1 * cm, A4[0], 1.1 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(1.5 * cm, A4[1] - 0.75 * cm, "AkzoNobel")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 1.5 * cm, A4[1] - 0.72 * cm, doc_title)
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(
            A4[0] / 2, 0.8 * cm,
            f"AkzoNobel N.V.  -  Christian Neefestraat 2, 1077 WW Amsterdam, NL"
            f"   |   Page {doc.page}   |   SYNTHETIC DEMO DOCUMENT")
        canvas.restoreState()
    return fn


def build(path, title, flow):
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=1.6 * cm, bottomMargin=1.4 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=title,
    )
    hf = _header_footer(title)
    doc.build(flow, onFirstPage=hf, onLaterPages=hf)


# ---------------------------------------------------------------------------
# Safety Data Sheets
# ---------------------------------------------------------------------------

SDS_PRODUCTS = [
    {
        "product_name": "Interpon RAL 9016 Polyester Powder Coating",
        "code": "SDS-AN-0413", "revision": "4.2", "date": "2026-02-11",
        "use": "Electrostatic powder coating for architectural aluminium and steel.",
        "hazard_class": "Combustible Dust, Category 1 (dust cloud)",
        "signal": "Warning",
        "ghs": "GHS07; H335 May cause respiratory irritation; combustible dust hazard.",
        "ingredients": [
            ("Titanium dioxide (rutile)", "13463-67-7", "8 - 14%", "Carc. 2 (inhalable dust)"),
            ("Polyester resin (saturated)", "Proprietary", "55 - 70%", "Not classified"),
            ("Barium sulfate (filler)", "7727-43-7", "10 - 20%", "Not classified"),
            ("Triglycidyl isocyanurate (TGIC)", "2451-62-9", "< 4%", "Muta. 2; Repr. 2; H317"),
        ],
        "flash_point": "Not applicable (solid powder); minimum ignition energy 10 mJ",
        "flash_point_field": "N/A (solid powder)",
        "voc": "12 g/L",
        "storage_temp": "5 to 30 deg C",
        "ppe": "Nitrile gloves, dust mask FFP2, safety goggles, anti-static footwear",
        "physical": [("Form", "Fine free-flowing powder"), ("Colour", "Traffic white (RAL 9016)"),
                     ("Odour", "Odourless"), ("pH", "Not applicable"),
                     ("Density", "1.5 - 1.7 g/cm3"), ("Solubility (water)", "Insoluble")],
    },
    {
        "product_name": "Sikkens Autocryl LV Basecoat Solvent Base",
        "code": "SDS-AN-1187", "revision": "3.0", "date": "2025-11-30",
        "use": "Solvent-borne automotive refinish basecoat.",
        "hazard_class": "Flammable Liquid, Category 2",
        "signal": "Danger",
        "ghs": "GHS02, GHS07, GHS08; H225 Highly flammable; H319; H336; H373.",
        "ingredients": [
            ("n-Butyl acetate", "123-86-4", "25 - 40%", "Flam. Liq. 3; H226; STOT SE 3"),
            ("Xylene (mixed isomers)", "1330-20-7", "10 - 20%", "Flam. Liq. 3; H312+H332; H315"),
            ("Acrylic copolymer resin", "Proprietary", "20 - 35%", "Not classified"),
            ("Titanium dioxide (rutile)", "13463-67-7", "3 - 8%", "Carc. 2 (inhalable dust)"),
        ],
        "flash_point": "23 deg C (closed cup, ISO 13736)",
        "flash_point_field": "23 deg C",
        "voc": "680 g/L",
        "storage_temp": "10 to 25 deg C",
        "ppe": "Solvent-resistant gloves (nitrile), organic-vapour respirator A2, face shield, coverall",
        "physical": [("Form", "Liquid"), ("Colour", "Pigmented, various"),
                     ("Odour", "Solvent / aromatic"), ("pH", "Not applicable"),
                     ("Density", "0.95 - 1.05 g/cm3"), ("Solubility (water)", "Immiscible")],
    },
    {
        "product_name": "International Intergard 5000 Epoxy Primer (Part A)",
        "code": "SDS-AN-2204", "revision": "2.5", "date": "2026-01-19",
        "use": "Two-pack high-build epoxy primer for marine and protective coatings.",
        "hazard_class": "Flammable Liquid, Category 3",
        "signal": "Danger",
        "ghs": "GHS02, GHS07, GHS09; H226; H317; H318; H411.",
        "ingredients": [
            ("Bisphenol-A epoxy resin", "25068-38-6", "30 - 45%", "Skin Sens. 1; Aquatic Chronic 2; H317; H411"),
            ("Xylene (mixed isomers)", "1330-20-7", "8 - 15%", "Flam. Liq. 3; H312+H332"),
            ("Talc", "14807-96-6", "10 - 20%", "Not classified"),
            ("Titanium dioxide (rutile)", "13463-67-7", "5 - 10%", "Carc. 2 (inhalable dust)"),
        ],
        "flash_point": "31 deg C (closed cup)",
        "flash_point_field": "31 deg C",
        "voc": "250 g/L",
        "storage_temp": "5 to 35 deg C",
        "ppe": "Chemical-resistant gloves (butyl/nitrile), goggles, vapour respirator A1, protective coverall",
        "physical": [("Form", "Viscous liquid"), ("Colour", "Grey"),
                     ("Odour", "Mild solvent"), ("pH", "Not applicable"),
                     ("Density", "1.4 - 1.5 g/cm3"), ("Solubility (water)", "Insoluble")],
    },
    {
        "product_name": "Dulux Weathershield Exterior Acrylic (Water-Based)",
        "code": "SDS-AN-0876", "revision": "5.1", "date": "2026-03-04",
        "use": "Water-based acrylic emulsion paint for exterior masonry and render.",
        "hazard_class": "Not classified as hazardous (GHS)",
        "signal": "None (no signal word required)",
        "ghs": "Not classified; contains preservatives, may produce an allergic reaction. EUH208.",
        "ingredients": [
            ("Water", "7732-18-5", "30 - 45%", "Not classified"),
            ("Styrene-acrylic latex", "Proprietary", "25 - 40%", "Not classified"),
            ("Titanium dioxide (rutile)", "13463-67-7", "10 - 18%", "Carc. 2 (inhalable dust)"),
            ("1,2-Benzisothiazol-3(2H)-one (BIT)", "2634-33-5", "< 0.05%", "Skin Sens. 1; H317"),
        ],
        "flash_point": "Not applicable (water-based, non-flammable)",
        "flash_point_field": "N/A (water-based)",
        "voc": "30 g/L",
        "storage_temp": "5 to 30 deg C (protect from frost)",
        "ppe": "Nitrile gloves, safety glasses; respirator not normally required",
        "physical": [("Form", "Liquid emulsion"), ("Colour", "White / tintable"),
                     ("Odour", "Low odour"), ("pH", "8.5 - 9.5"),
                     ("Density", "1.25 - 1.40 g/cm3"), ("Solubility (water)", "Miscible")],
    },
    {
        "product_name": "Interpon D2525 Architectural Powder (Matt Black)",
        "code": "SDS-AN-0419", "revision": "1.8", "date": "2025-09-22",
        "use": "Super-durable polyester powder coating for facade systems.",
        "hazard_class": "Combustible Dust, Category 1 (dust cloud)",
        "signal": "Warning",
        "ghs": "GHS07; H319; combustible dust; avoid dust accumulation.",
        "ingredients": [
            ("Polyester resin (super-durable)", "Proprietary", "60 - 75%", "Not classified"),
            ("Carbon black", "1333-86-4", "1 - 4%", "Not classified (bound in matrix)"),
            ("Calcium carbonate (filler)", "1317-65-3", "10 - 20%", "Not classified"),
            ("Titanium dioxide (rutile)", "13463-67-7", "1 - 5%", "Carc. 2 (inhalable dust)"),
        ],
        "flash_point": "Not applicable (solid powder)",
        "flash_point_field": "N/A (solid powder)",
        "voc": "5 g/L",
        "storage_temp": "10 to 28 deg C",
        "ppe": "FFP2 dust mask, nitrile gloves, safety goggles, anti-static footwear",
        "physical": [("Form", "Fine powder"), ("Colour", "Matt black"),
                     ("Odour", "Odourless"), ("pH", "Not applicable"),
                     ("Density", "1.3 - 1.6 g/cm3"), ("Solubility (water)", "Insoluble")],
    },
    {
        "product_name": "International Interthane 990 Polyurethane Topcoat",
        "code": "SDS-AN-3301", "revision": "3.7", "date": "2026-04-15",
        "use": "Two-component aliphatic acrylic polyurethane finish for steelwork.",
        "hazard_class": "Flammable Liquid, Category 3",
        "signal": "Danger",
        "ghs": "GHS02, GHS07; H226; H319; H335; H336.",
        "ingredients": [
            ("Acrylic polyol resin", "Proprietary", "35 - 50%", "Not classified"),
            ("n-Butyl acetate", "123-86-4", "15 - 25%", "Flam. Liq. 3; H226; STOT SE 3"),
            ("Solvent naphtha (aromatic, light)", "64742-95-6", "8 - 15%", "Flam. Liq. 3; H304; H336"),
            ("Titanium dioxide (rutile)", "13463-67-7", "8 - 15%", "Carc. 2 (inhalable dust)"),
        ],
        "flash_point": "27 deg C (closed cup)",
        "flash_point_field": "27 deg C",
        "voc": "420 g/L",
        "storage_temp": "5 to 30 deg C",
        "ppe": "Nitrile gloves, organic-vapour respirator A2, goggles, coverall",
        "physical": [("Form", "Liquid"), ("Colour", "Various (pigmented)"),
                     ("Odour", "Solvent"), ("pH", "Not applicable"),
                     ("Density", "1.1 - 1.3 g/cm3"), ("Solubility (water)", "Immiscible")],
    },
    {
        "product_name": "Sikkens Cetol Filter 7 Plus Wood Stain",
        "code": "SDS-AN-1542", "revision": "2.2", "date": "2025-12-08",
        "use": "Solvent-borne translucent wood stain for exterior joinery.",
        "hazard_class": "Flammable Liquid, Category 4 (combustible)",
        "signal": "Warning",
        "ghs": "GHS07, GHS08; H226 (border); H304; H317; H412.",
        "ingredients": [
            ("White spirit (Stoddard solvent)", "64742-48-9", "30 - 45%", "Asp. Tox. 1; H304; H336"),
            ("Alkyd resin (long oil)", "Proprietary", "30 - 45%", "Not classified"),
            ("Iron oxide pigments", "1309-37-1", "2 - 8%", "Not classified"),
            ("Cobalt bis(2-ethylhexanoate) drier", "136-52-7", "< 0.5%", "Skin Sens. 1; H317"),
        ],
        "flash_point": "62 deg C (closed cup)",
        "flash_point_field": "62 deg C",
        "voc": "400 g/L",
        "storage_temp": "5 to 25 deg C",
        "ppe": "Nitrile gloves, safety glasses, A1 vapour respirator in poor ventilation",
        "physical": [("Form", "Liquid"), ("Colour", "Translucent wood tones"),
                     ("Odour", "White-spirit / solvent"), ("pH", "Not applicable"),
                     ("Density", "0.88 - 0.95 g/cm3"), ("Solubility (water)", "Immiscible")],
    },
    {
        "product_name": "Interpon Redox Plus Zinc-Rich Primer Powder",
        "code": "SDS-AN-0455", "revision": "1.3", "date": "2026-05-20",
        "use": "Zinc-rich anti-corrosive powder primer for galvanic protection of steel.",
        "hazard_class": "Combustible Dust Cat 1; Hazardous to Aquatic Environment Cat 1",
        "signal": "Warning",
        "ghs": "GHS07, GHS09; H410 Very toxic to aquatic life; combustible dust.",
        "ingredients": [
            ("Zinc (powder/dust, stabilised)", "7440-66-6", "55 - 70%", "Aquatic Acute 1; Aquatic Chronic 1; H410"),
            ("Epoxy resin (solid)", "25068-38-6", "20 - 30%", "Skin Sens. 1; H317"),
            ("Dicyandiamide (curing agent)", "461-58-5", "< 3%", "Not classified"),
            ("Titanium dioxide (rutile)", "13463-67-7", "1 - 5%", "Carc. 2 (inhalable dust)"),
        ],
        "flash_point": "Not applicable (solid powder)",
        "flash_point_field": "N/A (solid powder)",
        "voc": "8 g/L",
        "storage_temp": "8 to 26 deg C",
        "ppe": "FFP3 dust mask, nitrile gloves, goggles, anti-static footwear; avoid release to drains",
        "physical": [("Form", "Grey metallic powder"), ("Colour", "Grey"),
                     ("Odour", "Odourless"), ("pH", "Not applicable"),
                     ("Density", "2.0 - 2.6 g/cm3"), ("Solubility (water)", "Insoluble")],
    },
]


def sds_flow(p):
    f = []
    f.append(Paragraph("SAFETY DATA SHEET", S["AkzoTitle"]))
    f.append(Paragraph(
        f"According to Regulation (EC) No 1907/2006 (REACH) and (EU) 2020/878. "
        f"Document {p['code']} - Revision {p['revision']} - Date of issue {p['date']}.",
        S["AkzoSub"]))

    # Section 1
    f.append(Paragraph("SECTION 1: Identification of the substance/mixture and of the company", S["Sec"]))
    f.append(kv_table([
        ["Product name", p["product_name"]],
        ["Product code", p["code"]],
        ["Product type", "Industrial / professional coating"],
        ["Relevant identified uses", p["use"]],
        ["Supplier", "AkzoNobel N.V., Christian Neefestraat 2, 1077 WW Amsterdam, The Netherlands"],
        ["Emergency telephone", "+31 (0)20 502 7555 (24h)"],
    ]))

    # Section 2
    f.append(Paragraph("SECTION 2: Hazards identification", S["Sec"]))
    f.append(kv_table([
        ["Classification (CLP)", p["hazard_class"]],
        ["Signal word", p["signal"]],
        ["Hazard statements", p["ghs"]],
        ["Precautionary statements", "P210 Keep away from heat/sparks. P280 Wear protective gloves/eye protection. "
                                     "P403+P233 Store in a well-ventilated place, keep container tightly closed."],
    ]))

    # Section 3
    f.append(Paragraph("SECTION 3: Composition / information on ingredients", S["Sec"]))
    comp = [["Chemical name", "CAS No.", "Conc.", "Classification"]]
    comp += [list(r) for r in p["ingredients"]]
    t = Table(comp, colWidths=[5.5 * cm, 2.6 * cm, 2.3 * cm, 6.6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AKZO_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    f.append(t)

    # Section 4
    f.append(Paragraph("SECTION 4: First-aid measures", S["Sec"]))
    f.append(Paragraph("<b>Inhalation:</b> Move to fresh air. If symptoms persist, obtain medical attention. "
                       "<b>Skin contact:</b> Wash with soap and water; remove contaminated clothing. "
                       "<b>Eye contact:</b> Rinse cautiously with water for several minutes. "
                       "<b>Ingestion:</b> Do not induce vomiting; seek medical advice.", S["Body"]))

    # Section 5
    f.append(Paragraph("SECTION 5: Fire-fighting measures", S["Sec"]))
    f.append(kv_table([
        ["Flash point", p["flash_point"]],
        ["Suitable extinguishing media", "Foam, CO2, dry powder, water spray. Do not use water jet."],
        ["Special hazards", "Combustion may release CO, CO2 and nitrogen oxides. "
                            "Powders may form explosive dust-air mixtures."],
    ]))

    f.append(PageBreak())

    # Section 6
    f.append(Paragraph("SECTION 6: Accidental release measures", S["Sec"]))
    f.append(Paragraph("Eliminate ignition sources. Use personal protection as in Section 8. "
                       "Collect mechanically; avoid dust generation. Prevent entry into drains and watercourses.",
                       S["Body"]))

    # Section 7
    f.append(Paragraph("SECTION 7: Handling and storage", S["Sec"]))
    f.append(kv_table([
        ["Safe handling", "Avoid inhalation of dust/vapour. Ensure adequate ventilation. No smoking."],
        ["Storage conditions", "Store in original closed container in a dry, well-ventilated area."],
        ["Storage temperature", p["storage_temp"]],
        ["Incompatible materials", "Strong oxidising agents, strong acids and bases."],
        ["Shelf life", "24 months from date of manufacture under recommended conditions."],
    ]))

    # Section 8
    f.append(Paragraph("SECTION 8: Exposure controls / personal protection", S["Sec"]))
    f.append(kv_table([
        ["Occupational exposure limits", "Observe local OEL/WEL values for solvents, dusts and TiO2 (inhalable)."],
        ["Engineering controls", "Provide local exhaust ventilation; maintain airborne levels below OEL."],
        ["Required PPE", p["ppe"]],
    ]))

    # Section 9
    f.append(Paragraph("SECTION 9: Physical and chemical properties", S["Sec"]))
    phys = [["Property", "Value"]] + [list(x) for x in p["physical"]]
    phys.append(["VOC content", p["voc"]])
    phys.append(["Flash point", p["flash_point_field"]])
    t2 = Table(phys, colWidths=[6.0 * cm, 11.0 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AKZO_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.25, LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    f.append(t2)

    # Sections 10-16 condensed
    f.append(Paragraph("SECTION 10: Stability and reactivity", S["Sec"]))
    f.append(Paragraph("Stable under normal conditions. Avoid heat, sparks and open flame. "
                       "Hazardous polymerisation does not occur.", S["Body"]))
    f.append(Paragraph("SECTION 11: Toxicological information", S["Sec"]))
    f.append(Paragraph("May cause irritation of eyes, skin and respiratory tract. "
                       "Titanium dioxide classified Carc. 2 by inhalation of dust. See Section 3 for sensitisers.",
                       S["Body"]))
    f.append(Paragraph("SECTION 12: Ecological information", S["Sec"]))
    f.append(Paragraph("Do not allow to enter drains, soil or watercourses. "
                       "Aquatic toxicity depends on components; see Section 3 classifications.", S["Body"]))
    f.append(Paragraph("SECTION 13: Disposal considerations", S["Sec"]))
    f.append(Paragraph("Dispose of contents/container in accordance with local, regional and national regulations. "
                       "European Waste Catalogue code per use.", S["Body"]))
    f.append(Paragraph("SECTION 14: Transport information", S["Sec"]))
    f.append(Paragraph("Classify for transport (ADR/IMDG/IATA) according to flammability and environmental hazard. "
                       "Non-flammable water-based products are generally not regulated.", S["Body"]))
    f.append(Paragraph("SECTION 15: Regulatory information", S["Sec"]))
    f.append(Paragraph("Complies with REACH (EC) 1907/2006 and CLP (EC) 1272/2008. "
                       "VOC content stated in Section 9 per Directive 2004/42/EC.", S["Body"]))
    f.append(Paragraph("SECTION 16: Other information", S["Sec"]))
    f.append(Paragraph(f"Revision {p['revision']}. This SDS is a SYNTHETIC document created for a "
                       f"Databricks document-intelligence demo and does not describe a real product formulation.",
                       S["Body"]))
    return f


# ---------------------------------------------------------------------------
# Supplier contracts
# ---------------------------------------------------------------------------

CONTRACTS = [
    {
        "file": "contract_tronox_tio2.pdf",
        "supplier_name": "Tronox Pigments (Holland) B.V.",
        "category": "Titanium Dioxide (TiO2) Pigment Supply",
        "contract_no": "AN-PUR-2026-TIO2-014",
        "effective": "1 January 2026", "term": "36 months",
        "annual_spend": "EUR 4,250,000",
        "annual_spend_num": 4250000,
        "payment_terms": "Net 90 days from date of invoice",
        "payment_days": 90,
        "escalation": "Yes",
        "escalation_terms": "Annual price review tied to the Tronox feedstock index; maximum increase capped at 6% per year.",
        "termination_notice": "180 days",
        "nonstandard": True,
        "volume": "approximately 5,200 tonnes of rutile-grade TiO2 per annum",
    },
    {
        "file": "contract_allnex_resin.pdf",
        "supplier_name": "Allnex Netherlands B.V.",
        "category": "Resin Supply (Polyester and Acrylic Resins)",
        "contract_no": "AN-PUR-2026-RES-027",
        "effective": "15 February 2026", "term": "24 months",
        "annual_spend": "EUR 2,900,000",
        "annual_spend_num": 2900000,
        "payment_terms": "Net 120 days from end of month of invoice",
        "payment_days": 120,
        "escalation": "Yes",
        "escalation_terms": "Quarterly raw-material pass-through linked to propylene and adipic acid indices; "
                            "no annual cap, reviewed each calendar quarter.",
        "termination_notice": "120 days",
        "nonstandard": True,
        "volume": "approximately 3,400 tonnes of saturated polyester and acrylic resins per annum",
    },
    {
        "file": "contract_shell_solvent.pdf",
        "supplier_name": "Shell Chemicals Europe B.V.",
        "category": "Solvent Supply (Butyl Acetate, Xylene, White Spirit)",
        "contract_no": "AN-PUR-2026-SOL-009",
        "effective": "1 March 2026", "term": "24 months",
        "annual_spend": "EUR 1,650,000",
        "annual_spend_num": 1650000,
        "payment_terms": "Net 30 days from date of invoice",
        "payment_days": 30,
        "escalation": "Yes",
        "escalation_terms": "Monthly price set against Platts NWE spot quotations; "
                            "escalation strictly index-linked with no fixed cap.",
        "termination_notice": "90 days",
        "nonstandard": False,
        "volume": "approximately 2,800 tonnes of mixed coating solvents per annum",
    },
    {
        "file": "contract_mauser_packaging.pdf",
        "supplier_name": "Mauser Packaging Solutions GmbH",
        "category": "Packaging Supply (Steel Pails, Drums, IBCs)",
        "contract_no": "AN-PUR-2026-PAK-033",
        "effective": "1 April 2026", "term": "12 months",
        "annual_spend": "EUR 620,000",
        "annual_spend_num": 620000,
        "payment_terms": "Net 45 days from date of invoice",
        "payment_days": 45,
        "escalation": "No",
        "escalation_terms": "Prices fixed for the full 12-month term; no escalation clause applies.",
        "termination_notice": "60 days",
        "nonstandard": False,
        "volume": "approximately 1.1 million steel pails and 90,000 drums per annum",
    },
    {
        "file": "contract_dbschenker_freight.pdf",
        "supplier_name": "DB Schenker Logistics Nederland N.V.",
        "category": "Freight and Logistics Services",
        "contract_no": "AN-PUR-2026-FRT-041",
        "effective": "1 January 2026", "term": "24 months",
        "annual_spend": "EUR 980,000",
        "annual_spend_num": 980000,
        "payment_terms": "Net 30 days from date of invoice",
        "payment_days": 30,
        "escalation": "Yes",
        "escalation_terms": "Fuel surcharge adjusted monthly per the published diesel index; "
                            "base haulage rates fixed for the contract term.",
        "termination_notice": "90 days",
        "nonstandard": False,
        "volume": "approximately 14,000 full-truckload and groupage movements per annum across EMEA",
    },
    {
        "file": "contract_kronos_additives.pdf",
        "supplier_name": "Kronos Worldwide Additives Ltd",
        "category": "Specialty Additives and Driers Supply",
        "contract_no": "AN-PUR-2026-ADD-058",
        "effective": "1 May 2026", "term": "18 months",
        "annual_spend": "EUR 410,000",
        "annual_spend_num": 410000,
        "payment_terms": "Net 45 days from date of invoice",
        "payment_days": 45,
        "escalation": "No",
        "escalation_terms": "Unit prices held firm for the contract term; no price escalation clause.",
        "termination_notice": "90 days",
        "nonstandard": False,
        "volume": "approximately 240 tonnes of dispersants, defoamers and metal driers per annum",
    },
]


def contract_flow(c):
    f = []
    f.append(Paragraph("SUPPLY AGREEMENT", S["AkzoTitle"]))
    f.append(Paragraph(
        f"Contract reference {c['contract_no']}. This agreement is entered into between "
        f"AkzoNobel N.V. (the \"Buyer\") and {c['supplier_name']} (the \"Supplier\").",
        S["AkzoSub"]))

    f.append(Paragraph("1. Parties and Background", S["Sec"]))
    f.append(Paragraph(
        f"This Supply Agreement (the \"Agreement\") is made between AkzoNobel N.V., having its registered "
        f"office at Christian Neefestraat 2, 1077 WW Amsterdam, The Netherlands (the \"Buyer\"), and "
        f"{c['supplier_name']} (the \"Supplier\"). The Supplier provides goods and/or services in the "
        f"category of {c['category']}. The Buyer wishes to procure such goods and/or services on the "
        f"terms set out below.", S["Body"]))

    f.append(Paragraph("2. Scope of Supply", S["Sec"]))
    f.append(kv_table([
        ["Supplier name", c["supplier_name"]],
        ["Procurement category", c["category"]],
        ["Estimated annual volume", c["volume"]],
        ["Contract reference", c["contract_no"]],
    ]))

    f.append(Paragraph("3. Term and Commencement", S["Sec"]))
    f.append(Paragraph(
        f"This Agreement shall commence on {c['effective']} (the \"Effective Date\") and shall continue "
        f"in force for an initial term of {c['term']}, unless terminated earlier in accordance with "
        f"Clause 7. Upon expiry the Agreement may be renewed by mutual written agreement of the parties.",
        S["Body"]))

    f.append(Paragraph("4. Pricing and Annual Spend", S["Sec"]))
    f.append(kv_table([
        ["Estimated annual spend", c["annual_spend"]],
        ["Currency", "Euro (EUR)"],
        ["Pricing basis", "Per the agreed price schedule in Appendix A, exclusive of VAT."],
    ]))
    f.append(Paragraph(
        f"The estimated total annual spend under this Agreement is {c['annual_spend']}. This figure is an "
        f"estimate based on forecast volumes and does not constitute a minimum purchase commitment unless "
        f"expressly stated in Appendix A.", S["Body"]))

    f.append(Paragraph("5. Payment Terms", S["Sec"]))
    note = ""
    if c["nonstandard"]:
        note = (" The parties acknowledge that these payment terms DEVIATE from the Buyer's standard "
                "procurement terms of Net 30 to Net 45 days and were agreed as a NON-STANDARD exception "
                "in consideration of the strategic volume and pricing under this Agreement.")
    f.append(Paragraph(
        f"The Buyer shall pay correctly rendered and undisputed invoices on terms of {c['payment_terms']}. "
        f"Payment shall be made by bank transfer to the account nominated by the Supplier." + note,
        S["Body"]))

    f.append(PageBreak())

    f.append(Paragraph("6. Price Escalation", S["Sec"]))
    esc_lead = ("A price escalation clause APPLIES to this Agreement. "
                if c["escalation"] == "Yes"
                else "No price escalation clause applies to this Agreement. ")
    f.append(Paragraph(esc_lead + c["escalation_terms"], S["Body"]))
    f.append(kv_table([
        ["Price escalation clause", c["escalation"]],
        ["Escalation mechanism", c["escalation_terms"]],
    ]))

    f.append(Paragraph("7. Termination", S["Sec"]))
    f.append(Paragraph(
        f"Either party may terminate this Agreement for convenience by giving not less than "
        f"{c['termination_notice']} prior written notice to the other party. Either party may terminate "
        f"immediately on written notice if the other commits a material breach which is not remedied "
        f"within 30 days of notice, or becomes insolvent.", S["Body"]))
    f.append(kv_table([
        ["Termination notice (for convenience)", c["termination_notice"]],
        ["Material breach cure period", "30 days"],
    ]))

    f.append(Paragraph("8. Quality and Compliance", S["Sec"]))
    f.append(Paragraph(
        "The Supplier shall ensure that all goods conform to the agreed specifications, applicable REACH "
        "and CLP obligations, and the Buyer's Supplier Code of Conduct. The Supplier shall provide current "
        "Safety Data Sheets for all hazardous materials supplied.", S["Body"]))

    f.append(Paragraph("9. Liability and Insurance", S["Sec"]))
    f.append(Paragraph(
        "The Supplier shall maintain product liability and general liability insurance of not less than "
        "EUR 5,000,000 per occurrence. Save for liability that cannot be excluded by law, each party's "
        "aggregate liability shall be limited to the total charges paid in the preceding twelve months.",
        S["Body"]))

    f.append(Paragraph("10. Governing Law", S["Sec"]))
    f.append(Paragraph(
        "This Agreement shall be governed by and construed in accordance with the laws of The Netherlands. "
        "The courts of Amsterdam shall have exclusive jurisdiction over any dispute arising out of or in "
        "connection with this Agreement.", S["Body"]))

    f.append(Spacer(1, 0.6 * cm))
    sig = Table([
        ["For and on behalf of AkzoNobel N.V.", f"For and on behalf of {c['supplier_name']}"],
        ["", ""],
        ["_______________________________", "_______________________________"],
        ["Name: J. van der Berg", "Name: Authorised Signatory"],
        ["Title: Director of Procurement", "Title: Commercial Director"],
        [f"Date: {c['effective']}", f"Date: {c['effective']}"],
    ], colWidths=[8.5 * cm, 8.5 * cm])
    sig.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    f.append(sig)
    f.append(Spacer(1, 0.4 * cm))
    f.append(Paragraph("SYNTHETIC document created for a Databricks document-intelligence demo. "
                       "Parties, figures and terms are fictitious.", S["Foot"]))
    return f


# ---------------------------------------------------------------------------
# README ground-truth table
# ---------------------------------------------------------------------------

def write_readme(sds_files, contract_files):
    path = os.path.join(HERE, "output", "docs", "README.md")
    lines = []
    lines.append("# AkzoNobel Synthetic Demo Documents")
    lines.append("")
    lines.append("Generated by `data/generate_docs.py` using reportlab. All documents are SYNTHETIC and "
                 "created for a Databricks document-intelligence (ai_extract) demo. Use the ground-truth "
                 "tables below to score extraction accuracy.")
    lines.append("")
    lines.append("## Safety Data Sheets (`sds/`)")
    lines.append("")
    lines.append("Extractable fields: `product_name`, `hazard_class`, `flash_point`, `voc_g_per_l`, "
                 "`storage_temp_range`, `required_ppe`.")
    lines.append("")
    lines.append("| File | product_name | hazard_class | flash_point | voc_g_per_l | storage_temp_range | required_ppe |")
    lines.append("|---|---|---|---|---|---|---|")
    for fn, p in sds_files:
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            fn, p["product_name"], p["hazard_class"], p["flash_point_field"],
            p["voc"].replace(" g/L", ""), p["storage_temp"], p["ppe"]))
    lines.append("")
    lines.append("## Supplier Contracts (`contracts/`)")
    lines.append("")
    lines.append("Extractable fields: `supplier_name`, `category`, `annual_spend_eur`, `payment_terms_net_days`, "
                 "`price_escalation_clause`, `termination_notice_days`.")
    lines.append("")
    lines.append("| File | supplier_name | category | annual_spend_eur | payment_terms_net_days | "
                 "price_escalation_clause | termination_notice_days | non_standard_flag |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for fn, c in contract_files:
        flag = "YES (Net %d AND spend >EUR1M)" % c["payment_days"] if c["nonstandard"] else "no"
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            fn, c["supplier_name"], c["category"], c["annual_spend"],
            c["payment_days"], c["escalation"], c["termination_notice"], flag))
    lines.append("")
    lines.append("### Demo flag: suppliers with NON-STANDARD payment terms AND annual spend > EUR 1M")
    lines.append("")
    flagged = [c for _, c in contract_files if c["nonstandard"]]
    for c in flagged:
        lines.append("- **{}** ({}) - payment terms **Net {}** (standard is Net 30/45), annual spend **{}**.".format(
            c["supplier_name"], c["category"], c["payment_days"], c["annual_spend"]))
    lines.append("")

    # Append if file exists, else create
    mode = "a" if os.path.exists(path) else "w"
    with open(path, mode) as fh:
        if mode == "a":
            fh.write("\n\n---\n\n")
        fh.write("\n".join(lines) + "\n")
    return path


def main():
    os.makedirs(OUT_SDS, exist_ok=True)
    os.makedirs(OUT_CONTRACTS, exist_ok=True)

    sds_files = []
    for p in SDS_PRODUCTS:
        fn = p["code"].lower().replace("-", "_") + ".pdf"
        build(os.path.join(OUT_SDS, fn), f"SDS {p['code']}", sds_flow(p))
        sds_files.append((fn, p))
        print("wrote sds/%s" % fn)

    contract_files = []
    for c in CONTRACTS:
        build(os.path.join(OUT_CONTRACTS, c["file"]),
              f"Supply Agreement {c['contract_no']}", contract_flow(c))
        contract_files.append((c["file"], c))
        print("wrote contracts/%s" % c["file"])

    readme = write_readme(sds_files, contract_files)
    print("wrote %s" % readme)


if __name__ == "__main__":
    main()
