"""
Generates a single beautiful all-in-one overview slide for the Synthetic Data Generation Agent.
Run with:  venv\Scripts\python.exe create_single_slide.py
Output:    Single_Slide_Overview.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import pptx.oxml.ns as nsmap
from lxml import etree

C_BG_DARK    = RGBColor(0x0D, 0x11, 0x17)
C_BG_CARD    = RGBColor(0x16, 0x21, 0x3E)
C_ACCENT     = RGBColor(0x63, 0xB3, 0xED)
C_ACCENT2    = RGBColor(0x76, 0xE4, 0xF7)
C_WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
C_LIGHT_TEXT = RGBColor(0xA8, 0xB2, 0xD8)
C_MUTED      = RGBColor(0x71, 0x80, 0x96)
C_GREEN      = RGBColor(0x68, 0xD3, 0x91)
C_PURPLE     = RGBColor(0xB7, 0x94, 0xF4)
C_ORANGE     = RGBColor(0xF6, 0xAD, 0x55)

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


def new_prs():
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def fill_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, fill_color=None, line_color=None, line_width=Pt(0)):
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.line.width = line_width
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
    else:
        shape.line.fill.background()
    return shape


def add_text_box(slide, text, left, top, width, height,
                 font_size=Pt(14), bold=False, color=C_WHITE,
                 align=PP_ALIGN.LEFT, wrap=True, italic=False):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = font_size
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.italic = italic
    return txBox


def add_gradient_rect(slide, left, top, width, height, color1, color2):
    shape = add_rect(slide, left, top, width, height, fill_color=color1)
    sp = shape._element
    spPr = sp.find(nsmap.qn('p:spPr'))
    if spPr is None:
        return shape
    solid_fill = spPr.find(nsmap.qn('a:solidFill'))
    if solid_fill is not None:
        spPr.remove(solid_fill)
    grad_xml = f"""
    <a:gradFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" rotWithShape="1">
      <a:gsLst>
        <a:gs pos="0"><a:srgbClr val="{str(color1)}"/></a:gs>
        <a:gs pos="100000"><a:srgbClr val="{str(color2)}"/></a:gs>
      </a:gsLst>
      <a:lin ang="5400000" scaled="0"/>
    </a:gradFill>"""
    spPr.append(etree.fromstring(grad_xml))
    return shape


def build_slide(prs):
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)

    # ── Background gradient ────────────────────────────────────────────────────
    add_gradient_rect(slide, Inches(0), Inches(0), SLIDE_W, SLIDE_H,
                      RGBColor(0x08, 0x0C, 0x14), RGBColor(0x0B, 0x22, 0x40))

    # ── Decorative top-right glow ──────────────────────────────────────────────
    add_gradient_rect(slide, Inches(9.5), Inches(0), Inches(3.83), Inches(2.2),
                      RGBColor(0x0E, 0x2E, 0x55), RGBColor(0x08, 0x0C, 0x14))

    # ── Top pixel bar ──────────────────────────────────────────────────────────
    add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.055), fill_color=C_ACCENT)
    # thin accent stripe below header
    add_rect(slide, Inches(0), Inches(1.02), SLIDE_W, Inches(0.022),
             fill_color=RGBColor(0x1E, 0x3A, 0x5F))

    # ══ HEADER ════════════════════════════════════════════════════════════════
    add_rect(slide, Inches(0), Inches(0.055), SLIDE_W, Inches(0.965),
             fill_color=RGBColor(0x0E, 0x1A, 0x30))

    # Robot icon box
    add_rect(slide, Inches(0.28), Inches(0.13), Inches(0.72), Inches(0.72),
             fill_color=C_ACCENT, line_color=None)
    add_text_box(slide, "🤖", Inches(0.28), Inches(0.12), Inches(0.72), Inches(0.72),
                 font_size=Pt(26), align=PP_ALIGN.CENTER)

    # Title + tagline
    add_text_box(slide, "Synthetic Data Generation Agent",
                 Inches(1.12), Inches(0.10), Inches(8.2), Inches(0.50),
                 font_size=Pt(26), bold=True, color=C_WHITE)
    add_text_box(slide,
                 "LLM-powered  ·  Schema-validated  ·  Batch-streaming  ·  Multi-format  ·  Instantly downloadable",
                 Inches(1.12), Inches(0.60), Inches(8.8), Inches(0.33),
                 font_size=Pt(10.5), color=C_ACCENT, italic=True)

    # Right tech badge
    add_rect(slide, Inches(10.9), Inches(0.20), Inches(2.1), Inches(0.55),
             fill_color=RGBColor(0x16, 0x26, 0x44), line_color=C_ACCENT, line_width=Pt(1))
    add_text_box(slide, "⚡  Databricks  ·  Claude Sonnet",
                 Inches(10.9), Inches(0.20), Inches(2.1), Inches(0.55),
                 font_size=Pt(8.5), bold=True, color=C_ACCENT2, align=PP_ALIGN.CENTER)

    # ══ COLUMN LAYOUT (3 main columns) ════════════════════════════════════════
    # Col A: What it does + Scalability  (left, W=4.0)
    # Col B: Schemas                     (centre, W=4.65)
    # Col C: Use Cases + Features        (right, W=4.3)

    COL_A = Inches(0.22)
    COL_B = Inches(4.45)
    COL_C = Inches(9.32)
    ROW1  = Inches(1.10)
    ROW2  = Inches(3.35)
    ROW3  = Inches(5.48)
    CA_W  = Inches(4.05)
    CB_W  = Inches(4.65)
    CC_W  = Inches(3.85)

    # ── A1: What It Does ──────────────────────────────────────────────────────
    add_rect(slide, COL_A, ROW1, CA_W, Inches(2.05),
             fill_color=C_BG_CARD, line_color=C_ACCENT, line_width=Pt(1.2))
    add_rect(slide, COL_A, ROW1, Inches(0.04), Inches(2.05),
             fill_color=C_ACCENT)
    add_text_box(slide, "✨  What It Does",
                 COL_A + Inches(0.15), ROW1 + Inches(0.08), CA_W - Inches(0.2), Inches(0.36),
                 font_size=Pt(12.5), bold=True, color=C_ACCENT)
    add_text_box(slide,
                 "A Streamlit web application that calls Claude Sonnet via Databricks to generate "
                 "realistic, rule-compliant synthetic datasets on demand.\n\n"
                 "Pick data type, row count & batch size — the agent handles prompting, "
                 "parsing, validation, retry and one-click download.",
                 COL_A + Inches(0.15), ROW1 + Inches(0.46), CA_W - Inches(0.2), Inches(1.50),
                 font_size=Pt(9.8), color=C_LIGHT_TEXT)

    # ── A2: Why Scalable ──────────────────────────────────────────────────────
    add_rect(slide, COL_A, ROW2, CA_W, Inches(1.95),
             fill_color=C_BG_CARD, line_color=C_GREEN, line_width=Pt(1.2))
    add_rect(slide, COL_A, ROW2, Inches(0.04), Inches(1.95),
             fill_color=C_GREEN)
    add_text_box(slide, "📈  Why It's Scalable",
                 COL_A + Inches(0.15), ROW2 + Inches(0.08), CA_W - Inches(0.2), Inches(0.36),
                 font_size=Pt(12.5), bold=True, color=C_GREEN)
    scale_pts = [
        "🔄  Configurable batch streaming — live progress, 10 000+ rows per run",
        "🔁  Auto-retry 2× per batch — failures logged, never silent",
        "⚙️  Prompts & params tweakable in UI — zero code changes",
        "🌐  OpenAI-compatible — swap Databricks for Azure OpenAI anytime",
    ]
    for j, pt in enumerate(scale_pts):
        add_text_box(slide, pt,
                     COL_A + Inches(0.15), ROW2 + Inches(0.46 + j * 0.35),
                     CA_W - Inches(0.2), Inches(0.33),
                     font_size=Pt(9.5), color=C_LIGHT_TEXT)

    # ── A3: Core Features chips ───────────────────────────────────────────────
    add_text_box(slide, "CORE FEATURES",
                 COL_A, ROW3 - Inches(0.22), CA_W, Inches(0.22),
                 font_size=Pt(7.5), bold=True, color=C_MUTED)
    feats = [
        ("🧠", "LLM-Powered",    C_ACCENT),
        ("📋", "Schema Enforced",C_ACCENT2),
        ("✏️", "Editable Prompts",C_PURPLE),
        ("📥", "Multi-Format",   C_ORANGE),
    ]
    fw = Inches(0.96)
    for j, (ico, lbl, col) in enumerate(feats):
        fl = COL_A + j * Inches(1.01)
        add_rect(slide, fl, ROW3, fw, Inches(1.78),
                 fill_color=RGBColor(0x12, 0x1C, 0x35), line_color=col, line_width=Pt(1.1))
        add_text_box(slide, ico, fl + Inches(0.22), ROW3 + Inches(0.12),
                     Inches(0.52), Inches(0.50), font_size=Pt(22), align=PP_ALIGN.CENTER)
        add_text_box(slide, lbl, fl + Inches(0.04), ROW3 + Inches(0.68),
                     fw - Inches(0.08), Inches(0.45),
                     font_size=Pt(8.5), bold=True, color=col, align=PP_ALIGN.CENTER)
        add_rect(slide, fl + Inches(0.12), ROW3 + Inches(1.15),
                 fw - Inches(0.24), Inches(0.02), fill_color=col)
        feat_desc = {
            "LLM-Powered":    "Rich\ngeneration",
            "Schema Enforced": "Field-level\nvalidation",
            "Editable Prompts": "UI rules\nno code edit",
            "Multi-Format":   "CSV & JSON\noutput",
        }
        add_text_box(slide, feat_desc[lbl], fl + Inches(0.04), ROW3 + Inches(1.18),
                     fw - Inches(0.08), Inches(0.56),
                     font_size=Pt(7.5), color=C_MUTED, align=PP_ALIGN.CENTER)

    # ══ COL B: DATA SCHEMAS ═══════════════════════════════════════════════════
    add_text_box(slide, "SUPPORTED DATA SCHEMAS",
                 COL_B, ROW1 - Inches(0.0), CB_W, Inches(0.22),
                 font_size=Pt(7.5), bold=True, color=C_MUTED)

    # Cluster card
    add_rect(slide, COL_B, ROW1 + Inches(0.0), CB_W, Inches(2.9),
             fill_color=RGBColor(0x10, 0x1A, 0x32), line_color=C_ACCENT, line_width=Pt(1.2))
    add_rect(slide, COL_B, ROW1 + Inches(0.0), CB_W, Inches(0.04), fill_color=C_ACCENT)
    add_text_box(slide, "📦  Cluster  ·  CSV",
                 COL_B + Inches(0.15), ROW1 + Inches(0.08), CB_W - Inches(0.2), Inches(0.38),
                 font_size=Pt(13.5), bold=True, color=C_ACCENT)
    cluster_rows = [
        ("STORE_NO",        "4-digit zero-padded  (e.g. 0142)"),
        ("DEPT_NO",         "G5- + 2–4 alphanumeric  (e.g. G5-AB12)"),
        ("CSTD_GRADE",      "Exactly 2 alphanumeric chars  (e.g. A1)"),
        ("PHASE_STARTDATE", "DD-MMM-YY format  (e.g. 15-Jan-25)"),
    ]
    for j, (field, rule) in enumerate(cluster_rows):
        y = ROW1 + Inches(0.52 + j * 0.38)
        # field name pill
        add_rect(slide, COL_B + Inches(0.15), y + Inches(0.04),
                 Inches(1.45), Inches(0.28), fill_color=RGBColor(0x1A, 0x30, 0x50))
        add_text_box(slide, field, COL_B + Inches(0.18), y + Inches(0.03),
                     Inches(1.4), Inches(0.30), font_size=Pt(9), bold=True, color=C_ACCENT)
        add_text_box(slide, rule, COL_B + Inches(1.65), y + Inches(0.03),
                     CB_W - Inches(1.8), Inches(0.32), font_size=Pt(9), color=C_LIGHT_TEXT)
    # sample row
    add_rect(slide, COL_B + Inches(0.15), ROW1 + Inches(2.08),
             CB_W - Inches(0.3), Inches(0.03), fill_color=RGBColor(0x2A, 0x3A, 0x55))
    add_text_box(slide, "Sample:  0142, G5-AB12, A1, 15-Jan-25",
                 COL_B + Inches(0.15), ROW1 + Inches(2.12), CB_W - Inches(0.3), Inches(0.28),
                 font_size=Pt(9), color=C_GREEN, italic=True)
    add_text_box(slide, "✅  Unique STORE_NO + DEPT_NO per batch guaranteed",
                 COL_B + Inches(0.15), ROW1 + Inches(2.42), CB_W - Inches(0.3), Inches(0.28),
                 font_size=Pt(9), bold=True, color=C_GREEN)

    # ProductVendor card
    PV_TOP = ROW1 + Inches(3.08)
    add_rect(slide, COL_B, PV_TOP, CB_W, Inches(3.07),
             fill_color=RGBColor(0x10, 0x1A, 0x32), line_color=C_ACCENT2, line_width=Pt(1.2))
    add_rect(slide, COL_B, PV_TOP, CB_W, Inches(0.04), fill_color=C_ACCENT2)
    add_text_box(slide, "🛍️  ProductVendor  ·  JSON",
                 COL_B + Inches(0.15), PV_TOP + Inches(0.08), CB_W - Inches(0.2), Inches(0.38),
                 font_size=Pt(13.5), bold=True, color=C_ACCENT2)
    pv_rows = [
        ("productId",              "18-digit zero-padded string"),
        ("season.seasonYear",      "4-digit year  (e.g. 2025)"),
        ("season.seasonName",      "Unique season code  (e.g. SP25)"),
        ("vendors[].supplierNumber","6-char, starts with M  (e.g. M00055)"),
        ("vendors[].factoryNumber", "11-digit numeric string"),
        ("vendors[].isActive",      "\"true\" or \"false\" string"),
    ]
    for j, (field, rule) in enumerate(pv_rows):
        y = PV_TOP + Inches(0.52 + j * 0.36)
        add_rect(slide, COL_B + Inches(0.15), y + Inches(0.03),
                 Inches(1.9), Inches(0.27), fill_color=RGBColor(0x16, 0x2A, 0x46))
        add_text_box(slide, field, COL_B + Inches(0.18), y + Inches(0.02),
                     Inches(1.85), Inches(0.28), font_size=Pt(8.5), bold=True, color=C_ACCENT2)
        add_text_box(slide, rule, COL_B + Inches(2.1), y + Inches(0.02),
                     CB_W - Inches(2.25), Inches(0.30), font_size=Pt(8.5), color=C_LIGHT_TEXT)
    add_text_box(slide, "✅  Nested validation: season + every vendor checked on parse",
                 COL_B + Inches(0.15), PV_TOP + Inches(2.68), CB_W - Inches(0.3), Inches(0.28),
                 font_size=Pt(9), bold=True, color=C_GREEN)

    # ══ COL C: USE CASES ══════════════════════════════════════════════════════
    add_text_box(slide, "ENTERPRISE USE CASES",
                 COL_C, ROW1 - Inches(0.0), CC_W, Inches(0.22),
                 font_size=Pt(7.5), bold=True, color=C_MUTED)

    use_cases = [
        ("🧪", "QA Without PII",
         "Test apps with realistic data — no real customer info exposed",
         C_ACCENT),
        ("🏗️", "Dev Environment Seeding",
         "Populate dev/staging DBs instantly with representative data",
         C_ACCENT2),
        ("📊", "BI & Analytics Prototyping",
         "Build dashboards before real pipelines are ready",
         C_GREEN),
        ("🤖", "ML Model Training",
         "Create large labelled training datasets for experiments",
         C_PURPLE),
        ("🔐", "Privacy-Safe Sharing",
         "Share data across teams or vendors — zero compliance risk",
         C_ORANGE),
        ("📦", "Supply Chain Simulation",
         "Model inventory & vendor scenarios for planning",
         C_ACCENT),
    ]

    UC_H = Inches(1.04)
    for j, (ico, title, desc, col) in enumerate(use_cases):
        ut = ROW1 + j * Inches(1.05)
        add_rect(slide, COL_C, ut, CC_W, UC_H - Inches(0.02),
                 fill_color=RGBColor(0x0F, 0x18, 0x2E), line_color=col, line_width=Pt(0.8))
        # colour left tab
        add_rect(slide, COL_C, ut, Inches(0.05), UC_H - Inches(0.02), fill_color=col)
        add_text_box(slide, ico,
                     COL_C + Inches(0.12), ut + Inches(0.12),
                     Inches(0.42), Inches(0.60), font_size=Pt(22))
        add_text_box(slide, title,
                     COL_C + Inches(0.60), ut + Inches(0.08),
                     CC_W - Inches(0.68), Inches(0.32),
                     font_size=Pt(10.5), bold=True, color=col)
        add_text_box(slide, desc,
                     COL_C + Inches(0.60), ut + Inches(0.42),
                     CC_W - Inches(0.68), Inches(0.52),
                     font_size=Pt(9), color=C_LIGHT_TEXT)

    # ── Bottom bar ─────────────────────────────────────────────────────────────
    add_rect(slide, Inches(0), Inches(7.38), SLIDE_W, Inches(0.06), fill_color=C_ACCENT)
    add_rect(slide, Inches(0), Inches(7.20), SLIDE_W, Inches(0.18),
             fill_color=RGBColor(0x0C, 0x18, 0x2E))
    add_text_box(slide,
                 "Powered by Databricks · Claude Sonnet · Streamlit  ·  "
                 "Extend in 3 steps: PROMPT_TEMPLATES → COLUMN_NAMES → UI selector",
                 Inches(0), Inches(7.21), SLIDE_W, Inches(0.18),
                 font_size=Pt(8), color=C_MUTED, align=PP_ALIGN.CENTER)


if __name__ == "__main__":
    prs = new_prs()
    build_slide(prs)
    output_path = r"C:\Users\P9193015\Downloads\DATA GEN\Single_Slide_Overview.pptx"
    prs.save(output_path)
    print(f"✅  Saved to: {output_path}")

