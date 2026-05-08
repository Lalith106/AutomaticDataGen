"""
Generates a polished PowerPoint presentation for the Synthetic Data Generation Agent.
Run with:  venv\Scripts\python.exe create_ppt.py
Output:    Synthetic_Data_Generation_Agent.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import pptx.enum.shapes
import pptx.oxml.ns as nsmap
from lxml import etree

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG_DARK    = RGBColor(0x0D, 0x11, 0x17)   # near-black background
C_BG_CARD    = RGBColor(0x16, 0x21, 0x3E)   # card dark blue
C_ACCENT     = RGBColor(0x63, 0xB3, 0xED)   # bright sky blue
C_ACCENT2    = RGBColor(0x76, 0xE4, 0xF7)   # teal highlight
C_WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
C_LIGHT_TEXT = RGBColor(0xA8, 0xB2, 0xD8)   # muted lavender
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
    blank_layout = prs.slide_layouts[6]  # completely blank
    return prs.slides.add_slide(blank_layout)


def fill_bg(slide, color: RGBColor):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, fill_color=None, line_color=None, line_width=Pt(0)):
    shape = slide.shapes.add_shape(
        pptx.enum.shapes.MSO_SHAPE_TYPE.RECTANGLE if False else 1,
        left, top, width, height
    )
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


def add_gradient_rect(slide, left, top, width, height, color1: RGBColor, color2: RGBColor):
    """Add a rectangle with a left-to-right gradient via XML manipulation."""
    shape = add_rect(slide, left, top, width, height, fill_color=color1)
    # Apply gradient via spPr XML
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
        <a:gs pos="0">
          <a:srgbClr val="{str(color1)}"/>
        </a:gs>
        <a:gs pos="100000">
          <a:srgbClr val="{str(color2)}"/>
        </a:gs>
      </a:gsLst>
      <a:lin ang="5400000" scaled="0"/>
    </a:gradFill>
    """
    grad_elem = etree.fromstring(grad_xml)
    spPr.append(grad_elem)
    return shape


def bullet_tf(slide, items, left, top, width, height,
              font_size=Pt(13), color=C_LIGHT_TEXT, bullet_color=C_ACCENT,
              title=None, title_size=Pt(16), title_color=C_WHITE):
    """Add a text box with bullet-style lines."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    if title:
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = title_size
        run.font.bold = True
        run.font.color.rgb = title_color
        first = False
    else:
        first = True

    for item in items:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        run = p.add_run()
        run.text = f"  {item}"
        run.font.size = font_size
        run.font.color.rgb = color
        p.space_before = Pt(4)
    return txBox


# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def slide_title(prs):
    """Slide 1 — Title / Hero"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)

    # Full-width gradient strip at top
    add_gradient_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(7.5),
                      RGBColor(0x0D, 0x11, 0x17), RGBColor(0x0F, 0x34, 0x60))

    # Decorative accent bar
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    # Badge pill
    badge = add_rect(slide, Inches(4.8), Inches(1.4), Inches(3.7), Inches(0.4),
                     fill_color=RGBColor(0x1A, 0x26, 0x44), line_color=C_ACCENT, line_width=Pt(1))
    add_text_box(slide, "🤖  AI-POWERED · LLM-DRIVEN · ENTERPRISE READY",
                 Inches(4.8), Inches(1.4), Inches(3.7), Inches(0.4),
                 font_size=Pt(9), color=C_ACCENT, align=PP_ALIGN.CENTER, bold=True)

    # Main title
    add_text_box(slide, "Synthetic Data\nGeneration Agent",
                 Inches(1.5), Inches(2.0), Inches(10.3), Inches(2.0),
                 font_size=Pt(52), bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)

    # Subtitle
    add_text_box(slide,
                 "Generate realistic, schema-compliant synthetic datasets at scale\n"
                 "using large language models — fully configurable, batch-ready, instantly downloadable.",
                 Inches(2.0), Inches(4.1), Inches(9.3), Inches(1.2),
                 font_size=Pt(15), color=C_LIGHT_TEXT, align=PP_ALIGN.CENTER)

    # Bottom strip
    add_rect(slide, Inches(0), Inches(7.2), SLIDE_W, Inches(0.3),
             fill_color=RGBColor(0x0F, 0x34, 0x60))
    add_text_box(slide, "Powered by Databricks · Claude Sonnet · Streamlit",
                 Inches(0), Inches(7.2), SLIDE_W, Inches(0.3),
                 font_size=Pt(10), color=C_MUTED, align=PP_ALIGN.CENTER)


def slide_agenda(prs):
    """Slide 2 — Agenda"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Agenda", Inches(0.6), Inches(0.25), Inches(10), Inches(0.7),
                 font_size=Pt(32), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(1.5), Inches(0.04), fill_color=C_ACCENT)

    items = [
        ("01", "Problem & Opportunity", "Why synthetic data matters in enterprise AI/ML"),
        ("02", "Solution Overview",     "What the agent does and how it works"),
        ("03", "Core Capabilities",     "Key features powering the agent"),
        ("04", "Supported Data Schemas","Cluster CSV and ProductVendor JSON"),
        ("05", "Architecture",          "System design and data flow"),
        ("06", "Use Cases",             "Where organisations deploy synthetic data"),
        ("07", "Technology Stack",      "Python, Streamlit, Databricks, Claude"),
        ("08", "Extensibility",         "How to add new data types in minutes"),
        ("09", "Next Steps",            "Getting started and future roadmap"),
    ]

    for i, (num, title, sub) in enumerate(items):
        row = i % 5
        col = i // 5
        left = Inches(0.6 + col * 6.5)
        top  = Inches(1.3 + row * 1.1)

        add_rect(slide, left, top, Inches(0.5), Inches(0.5),
                 fill_color=C_ACCENT, line_color=None)
        add_text_box(slide, num, left, top + Inches(0.05), Inches(0.5), Inches(0.4),
                     font_size=Pt(14), bold=True, color=C_BG_DARK, align=PP_ALIGN.CENTER)
        add_text_box(slide, title, left + Inches(0.6), top, Inches(5.5), Inches(0.3),
                     font_size=Pt(13), bold=True, color=C_WHITE)
        add_text_box(slide, sub, left + Inches(0.6), top + Inches(0.28), Inches(5.5), Inches(0.3),
                     font_size=Pt(11), color=C_MUTED)


def slide_problem(prs):
    """Slide 3 — Problem & Opportunity"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "The Problem with Real Data", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(2.5), Inches(0.04), fill_color=C_ACCENT)

    problems = [
        ("🔐", "Privacy & Compliance",
         "Real data contains PII — sharing it for dev/test\nviolates GDPR, HIPAA, and data governance policies."),
        ("⏳", "Slow Data Access",
         "Getting production data approved for dev use\ncan take weeks through data governance processes."),
        ("📉", "Limited Edge Cases",
         "Real data often lacks rare events, outliers,\nor specific scenarios needed for robust testing."),
        ("💸", "High Cost",
         "Sanitising and masking real datasets is\nexpensive, error-prone, and time-consuming."),
    ]

    for i, (icon, title, desc) in enumerate(problems):
        col = i % 2
        row = i // 2
        left = Inches(0.5 + col * 6.4)
        top  = Inches(1.3 + row * 2.6)

        add_rect(slide, left, top, Inches(6.0), Inches(2.3),
                 fill_color=C_BG_CARD,
                 line_color=RGBColor(0x45, 0x56, 0x78))
        add_text_box(slide, icon, left + Inches(0.2), top + Inches(0.15),
                     Inches(0.6), Inches(0.5), font_size=Pt(28))
        add_text_box(slide, title, left + Inches(0.9), top + Inches(0.15),
                     Inches(4.8), Inches(0.4), font_size=Pt(15), bold=True, color=C_WHITE)
        add_text_box(slide, desc, left + Inches(0.2), top + Inches(0.7),
                     Inches(5.6), Inches(1.4), font_size=Pt(12), color=C_LIGHT_TEXT)


def slide_solution(prs):
    """Slide 4 — Solution Overview"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Our Solution: LLM-Powered Synthetic Data Agent",
                 Inches(0.6), Inches(0.25), Inches(12), Inches(0.7),
                 font_size=Pt(28), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(4.0), Inches(0.04), fill_color=C_ACCENT)

    # Left: what it is
    add_text_box(slide,
                 "A Streamlit-powered web application that uses Claude Sonnet (Anthropic) via Databricks "
                 "to generate realistic, schema-compliant synthetic datasets on demand.\n\n"
                 "Users configure the data type, record count, and batch size — the agent handles the rest: "
                 "prompting the LLM, parsing and validating results, retrying failures, and delivering "
                 "clean CSV or JSON files ready for immediate use.",
                 Inches(0.6), Inches(1.2), Inches(6.8), Inches(3.0),
                 font_size=Pt(13.5), color=C_LIGHT_TEXT)

    # Right: key highlights
    highlights = [
        ("⚡", "Batch Generation", "Up to 10,000+ records per run"),
        ("✅", "Schema Validation", "Every field validated on parse"),
        ("🔁", "Auto-Retry", "2× retries per failed batch"),
        ("📥", "Instant Download", "CSV or JSON — one click"),
        ("✏️", "Editable Prompts", "Customise rules in the UI"),
    ]
    for i, (icon, title, sub) in enumerate(highlights):
        top = Inches(1.2 + i * 1.1)
        add_rect(slide, Inches(8.0), top, Inches(4.8), Inches(0.95),
                 fill_color=C_BG_CARD, line_color=C_ACCENT, line_width=Pt(0.75))
        add_text_box(slide, icon, Inches(8.15), top + Inches(0.1),
                     Inches(0.5), Inches(0.5), font_size=Pt(22))
        add_text_box(slide, title, Inches(8.75), top + Inches(0.08),
                     Inches(3.8), Inches(0.35), font_size=Pt(13), bold=True, color=C_WHITE)
        add_text_box(slide, sub, Inches(8.75), top + Inches(0.42),
                     Inches(3.8), Inches(0.35), font_size=Pt(11), color=C_MUTED)


def slide_capabilities(prs):
    """Slide 5 — Core Capabilities"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Core Capabilities", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(2.0), Inches(0.04), fill_color=C_ACCENT)

    caps = [
        ("🧠", "LLM-Powered",     C_ACCENT,   "Leverages Claude Sonnet via Databricks. Contextually rich, business-rule-aware generation."),
        ("📋", "Schema Enforced", C_ACCENT2,  "Field-level validation on every record. Wrong format = retry, not silent corruption."),
        ("🔄", "Batch Streaming", C_GREEN,    "Large volumes split into configurable batches. Live progress bar in the UI."),
        ("⚙️", "Configurable",    C_PURPLE,   "Row count, batch size, and prompts all controlled by the user — no code changes needed."),
        ("📥", "Multi-Format",    C_ORANGE,   "CSV for tabular/flat data. JSON for nested/hierarchical schemas."),
        ("🔁", "Fault Tolerant",  C_ACCENT,   "Each batch retries 2× automatically. Skipped batches are logged, not silently lost."),
    ]

    cols = 3
    for i, (icon, title, color, desc) in enumerate(caps):
        col = i % cols
        row = i // cols
        left = Inches(0.4 + col * 4.3)
        top  = Inches(1.2 + row * 2.8)

        add_rect(slide, left, top, Inches(4.0), Inches(2.5),
                 fill_color=C_BG_CARD, line_color=color, line_width=Pt(1.5))
        add_text_box(slide, icon, left + Inches(0.2), top + Inches(0.15),
                     Inches(0.6), Inches(0.55), font_size=Pt(26))
        add_text_box(slide, title, left + Inches(0.9), top + Inches(0.2),
                     Inches(2.8), Inches(0.4), font_size=Pt(14), bold=True, color=color)
        add_text_box(slide, desc, left + Inches(0.2), top + Inches(0.8),
                     Inches(3.6), Inches(1.5), font_size=Pt(11.5), color=C_LIGHT_TEXT)


def slide_schemas(prs):
    """Slide 6 — Data Schemas"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Supported Data Schemas", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(2.8), Inches(0.04), fill_color=C_ACCENT)

    # Left — Cluster CSV
    add_rect(slide, Inches(0.4), Inches(1.15), Inches(6.0), Inches(5.9),
             fill_color=C_BG_CARD, line_color=C_ACCENT, line_width=Pt(1))
    add_text_box(slide, "📦  Cluster  ·  CSV", Inches(0.6), Inches(1.25),
                 Inches(5.5), Inches(0.5), font_size=Pt(18), bold=True, color=C_ACCENT)

    cluster_fields = [
        "STORE_NO     4-digit zero-padded, digits 1–9",
        "DEPT_NO      G5- + 2–4 alphanumeric chars",
        "CSTD_GRADE   Exactly 2 alphanumeric chars",
        "PHASE_STARTDATE  DD-MMM-YY format",
    ]
    add_text_box(slide, "\n".join(cluster_fields), Inches(0.6), Inches(1.9),
                 Inches(5.5), Inches(1.8), font_size=Pt(11), color=C_LIGHT_TEXT,
                 italic=True)

    add_text_box(slide, "Sample output:", Inches(0.6), Inches(3.8),
                 Inches(5.5), Inches(0.3), font_size=Pt(11), bold=True, color=C_MUTED)
    add_rect(slide, Inches(0.5), Inches(4.1), Inches(5.8), Inches(0.04),
             fill_color=C_MUTED)
    cluster_sample = "0142, G5-AB12, A1, 15-Jan-25\n0587, G5-XY3,  B3, 22-Mar-25\n0931, G5-MN45, C2, 07-Jun-25"
    add_text_box(slide, cluster_sample, Inches(0.6), Inches(4.2),
                 Inches(5.5), Inches(1.0), font_size=Pt(11), color=C_GREEN, italic=True)
    add_text_box(slide, "✅ Unique STORE_NO and DEPT_NO per batch guaranteed",
                 Inches(0.6), Inches(5.3), Inches(5.5), Inches(0.5),
                 font_size=Pt(11), color=C_GREEN)
    add_text_box(slide, "Use cases: Store planning · Inventory clustering · Retail simulation",
                 Inches(0.6), Inches(5.8), Inches(5.5), Inches(0.6),
                 font_size=Pt(11), color=C_MUTED)

    # Right — ProductVendor JSON
    add_rect(slide, Inches(6.8), Inches(1.15), Inches(6.0), Inches(5.9),
             fill_color=C_BG_CARD, line_color=C_ACCENT2, line_width=Pt(1))
    add_text_box(slide, "🛍️  ProductVendor  ·  JSON", Inches(7.0), Inches(1.25),
                 Inches(5.5), Inches(0.5), font_size=Pt(18), bold=True, color=C_ACCENT2)

    pv_fields = [
        "productId      18-digit zero-padded string",
        "season.seasonYear    4-digit year",
        "season.seasonName    Unique code (SP24, FA25...)",
        "vendors[].supplierNumber  6-char, starts with M",
        "vendors[].factoryNumber   11-digit string",
        "vendors[].isActive        \"true\" or \"false\"",
    ]
    add_text_box(slide, "\n".join(pv_fields), Inches(7.0), Inches(1.9),
                 Inches(5.5), Inches(1.8), font_size=Pt(11), color=C_LIGHT_TEXT, italic=True)

    add_text_box(slide, "Sample output:", Inches(7.0), Inches(3.8),
                 Inches(5.5), Inches(0.3), font_size=Pt(11), bold=True, color=C_MUTED)
    add_rect(slide, Inches(6.9), Inches(4.1), Inches(5.8), Inches(0.04),
             fill_color=C_MUTED)
    pv_sample = ('{ "productId": "000000000006059884",\n'
                 '  "season": { "seasonYear": "2025",\n'
                 '              "seasonName": "SP25" },\n'
                 '  "vendors": [{ "supplierNumber": "M00055",\n'
                 '               "isActive": "true" }] }')
    add_text_box(slide, pv_sample, Inches(7.0), Inches(4.2),
                 Inches(5.5), Inches(1.3), font_size=Pt(10), color=C_GREEN, italic=True)
    add_text_box(slide, "✅ Nested validation: season + vendors checked per record",
                 Inches(7.0), Inches(5.6), Inches(5.5), Inches(0.5),
                 font_size=Pt(11), color=C_GREEN)
    add_text_box(slide, "Use cases: Product catalogue · Vendor management · Supply chain",
                 Inches(7.0), Inches(6.1), Inches(5.5), Inches(0.6),
                 font_size=Pt(11), color=C_MUTED)


def slide_architecture(prs):
    """Slide 7 — Architecture"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "System Architecture & Data Flow", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(3.5), Inches(0.04), fill_color=C_ACCENT)

    # Flow boxes
    flow = [
        (Inches(0.4),  "🖥️ Streamlit UI",    "User selects data type,\nrow count, batch size\n& edits prompt",        C_ACCENT),
        (Inches(3.2),  "⚙️ DataGenBot",       "Builds prompt, calls\nLLM API per batch,\nstreams progress",           C_ACCENT2),
        (Inches(6.0),  "🤖 Databricks LLM",  "Claude Sonnet via\nOpenAI-compatible\nserving endpoint",              C_GREEN),
        (Inches(8.8),  "✅ Parser/Validator", "CSV: Pandas parsing\nJSON: field-by-field\nnested validation",         C_PURPLE),
        (Inches(11.6), "📥 Output",           "Session state stores\nresults for preview\n& download",               C_ORANGE),
    ]

    box_w = Inches(2.5)
    box_h = Inches(3.0)
    box_top = Inches(1.6)

    for left, title, desc, color in flow:
        add_rect(slide, left, box_top, box_w, box_h,
                 fill_color=C_BG_CARD, line_color=color, line_width=Pt(1.5))
        add_text_box(slide, title, left + Inches(0.1), box_top + Inches(0.15),
                     box_w - Inches(0.2), Inches(0.5),
                     font_size=Pt(12), bold=True, color=color)
        add_rect(slide, left + Inches(0.1), box_top + Inches(0.65),
                 box_w - Inches(0.2), Inches(0.03), fill_color=color)
        add_text_box(slide, desc, left + Inches(0.1), box_top + Inches(0.75),
                     box_w - Inches(0.2), Inches(2.0),
                     font_size=Pt(11), color=C_LIGHT_TEXT)

    # Arrows between boxes
    for i in range(len(flow) - 1):
        left_of_box = flow[i][0] + box_w + Inches(0.05)
        top_of_arrow = box_top + box_h / 2 - Inches(0.15)
        add_text_box(slide, "→", left_of_box, top_of_arrow,
                     Inches(0.3), Inches(0.3), font_size=Pt(20), color=C_ACCENT,
                     align=PP_ALIGN.CENTER)

    # Retry note
    add_rect(slide, Inches(3.2), Inches(5.0), Inches(5.4), Inches(0.7),
             fill_color=RGBColor(0x1A, 0x20, 0x2C),
             line_color=RGBColor(0x76, 0x4A, 0x00), line_width=Pt(1))
    add_text_box(slide,
                 "🔁  Auto-Retry: Each batch retries up to 2× on parse or API error before being skipped & logged",
                 Inches(3.3), Inches(5.05), Inches(5.2), Inches(0.6),
                 font_size=Pt(11), color=C_ORANGE)


def slide_use_cases(prs):
    """Slide 8 — Use Cases"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Enterprise Use Cases", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(2.5), Inches(0.04), fill_color=C_ACCENT)

    use_cases = [
        ("🧪", "QA & Testing Without PII",       "Test applications with realistic data\nthat contains no real customer information."),
        ("🏗️", "Dev Environment Seeding",         "Instantly populate dev/staging databases\nwith representative data for development."),
        ("📊", "BI & Analytics Prototyping",      "Build dashboards and reports before\nreal data pipelines are ready."),
        ("🤖", "ML Model Training",               "Create large, labelled training datasets\nfor machine learning experiments."),
        ("🔐", "Privacy-Safe Data Sharing",       "Share data across teams or with\nvendors without compliance risk."),
        ("🔄", "ETL Pipeline Validation",         "Stress-test data pipelines with\ncontrolled, high-volume synthetic inputs."),
        ("📦", "Supply Chain Simulation",         "Model inventory and vendor scenarios\nfor planning and optimisation."),
        ("🎓", "Demo & Training Environments",    "Create compelling, realistic demos\nfor client presentations and training."),
    ]

    cols = 4
    for i, (icon, title, desc) in enumerate(use_cases):
        col = i % cols
        row = i // cols
        left = Inches(0.3 + col * 3.2)
        top  = Inches(1.3 + row * 2.8)

        add_rect(slide, left, top, Inches(3.0), Inches(2.5),
                 fill_color=C_BG_CARD, line_color=RGBColor(0x2D, 0x37, 0x48))
        add_text_box(slide, icon, left + Inches(0.15), top + Inches(0.1),
                     Inches(0.5), Inches(0.5), font_size=Pt(24))
        add_text_box(slide, title, left + Inches(0.7), top + Inches(0.1),
                     Inches(2.1), Inches(0.5), font_size=Pt(11.5), bold=True, color=C_WHITE)
        add_text_box(slide, desc, left + Inches(0.15), top + Inches(0.75),
                     Inches(2.7), Inches(1.5), font_size=Pt(10.5), color=C_MUTED)


def slide_tech_stack(prs):
    """Slide 9 — Technology Stack"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Technology Stack", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(2.2), Inches(0.04), fill_color=C_ACCENT)

    tech = [
        ("🐍", "Python 3.12",       "Core runtime & orchestration", C_ACCENT),
        ("🎈", "Streamlit",         "Interactive web UI, session\nstate, progress bar, downloads", C_ACCENT2),
        ("🤖", "Claude Sonnet",     "Anthropic LLM for contextually\nrich data generation", C_GREEN),
        ("⚡", "Databricks",        "Model serving endpoint\n(OpenAI-compatible API)", C_PURPLE),
        ("🐼", "Pandas",            "CSV parsing, dataframe\nmanipulation, column mapping", C_ORANGE),
    ]

    for i, (icon, name, desc, color) in enumerate(tech):
        left = Inches(0.5 + i * 2.5)
        top  = Inches(1.3)
        add_rect(slide, left, top, Inches(2.2), Inches(4.5),
                 fill_color=C_BG_CARD, line_color=color, line_width=Pt(1.5))
        add_text_box(slide, icon, left + Inches(0.6), top + Inches(0.3),
                     Inches(1.0), Inches(0.8), font_size=Pt(36), align=PP_ALIGN.CENTER)
        add_text_box(slide, name, left + Inches(0.1), top + Inches(1.2),
                     Inches(2.0), Inches(0.45), font_size=Pt(14), bold=True,
                     color=color, align=PP_ALIGN.CENTER)
        add_rect(slide, left + Inches(0.3), top + Inches(1.75),
                 Inches(1.6), Inches(0.03), fill_color=color)
        add_text_box(slide, desc, left + Inches(0.1), top + Inches(1.9),
                     Inches(2.0), Inches(1.8), font_size=Pt(11), color=C_LIGHT_TEXT,
                     align=PP_ALIGN.CENTER)

    # OpenAI SDK note
    add_rect(slide, Inches(0.5), Inches(6.0), Inches(12.3), Inches(0.8),
             fill_color=RGBColor(0x1A, 0x26, 0x44),
             line_color=C_ACCENT, line_width=Pt(1))
    add_text_box(slide,
                 "💡  The agent uses the openai Python SDK to call Databricks endpoints — "
                 "making it trivially swappable between Databricks, Azure OpenAI, or any OpenAI-compatible provider.",
                 Inches(0.7), Inches(6.1), Inches(11.9), Inches(0.6),
                 font_size=Pt(12), color=C_LIGHT_TEXT)


def slide_extensibility(prs):
    """Slide 10 — Extensibility"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Adding New Data Types — 3 Simple Steps",
                 Inches(0.6), Inches(0.25), Inches(12), Inches(0.7),
                 font_size=Pt(28), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(4.0), Inches(0.04), fill_color=C_ACCENT)

    steps = [
        ("1️⃣", "Add Prompt Template", "backend.py",
         'PROMPT_TEMPLATES["MyType"] = """\nGenerate exactly {batch_size} UNIQUE CSV rows.\n\nColumns: COL_A, COL_B, COL_C\n\nRules:\n- COL_A: ...\n- COL_B: ...\n"""'),
        ("2️⃣", "Register Columns & Output Format", "backend.py",
         'COLUMN_NAMES["MyType"] = ["COL_A", "COL_B", "COL_C"]\nOUTPUT_FORMATS["MyType"] = "csv"  # or "json"'),
        ("3️⃣", "Add to UI Selector", "app.py",
         'data_type = st.selectbox(\n    "Element Type",\n    options=["Cluster", "ProductVendor", "MyType"],\n)'),
    ]

    for i, (num, title, file, code) in enumerate(steps):
        top = Inches(1.3 + i * 1.95)
        add_rect(slide, Inches(0.4), top, Inches(12.5), Inches(1.8),
                 fill_color=C_BG_CARD, line_color=C_ACCENT, line_width=Pt(0.75))
        add_text_box(slide, num, Inches(0.5), top + Inches(0.1),
                     Inches(0.5), Inches(0.45), font_size=Pt(22))
        add_text_box(slide, title, Inches(1.1), top + Inches(0.1),
                     Inches(5.0), Inches(0.4), font_size=Pt(14), bold=True, color=C_WHITE)
        add_text_box(slide, f"File: {file}", Inches(1.1), top + Inches(0.5),
                     Inches(3.0), Inches(0.3), font_size=Pt(11), color=C_MUTED, italic=True)
        add_rect(slide, Inches(6.5), top + Inches(0.1), Inches(6.0), Inches(1.55),
                 fill_color=RGBColor(0x0D, 0x11, 0x17))
        add_text_box(slide, code, Inches(6.6), top + Inches(0.2),
                     Inches(5.8), Inches(1.4), font_size=Pt(10), color=C_GREEN, italic=True)


def slide_next_steps(prs):
    """Slide 11 — Next Steps"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_gradient_rect(slide, Inches(0), Inches(0), SLIDE_W, SLIDE_H,
                      RGBColor(0x0D, 0x11, 0x17), RGBColor(0x0F, 0x34, 0x60))
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Next Steps & Roadmap", Inches(0.6), Inches(0.25),
                 Inches(10), Inches(0.7), font_size=Pt(30), bold=True, color=C_WHITE)
    add_rect(slide, Inches(0.6), Inches(1.0), Inches(2.8), Inches(0.04), fill_color=C_ACCENT)

    immediate = [
        "▶  Run the app: venv\\Scripts\\python.exe -m streamlit run app.py",
        "▶  Generate Cluster CSV and ProductVendor JSON end-to-end",
        "▶  Review batch logs and download output files",
        "▶  Customise prompts in the UI to match your specific data rules",
    ]
    roadmap = [
        "🔜  Add new data schemas (e.g. Customer, Transaction, Employee)",
        "🔜  Export to Excel, Parquet, and database formats",
        "🔜  Multi-schema generation in a single run",
        "🔜  Schema inference from existing table DDL",
        "🔜  Volume scale-out via parallel batch workers",
        "🔜  Configurable LLM provider (Azure OpenAI, OpenAI, local models)",
    ]

    # Immediate actions
    add_rect(slide, Inches(0.4), Inches(1.2), Inches(6.0), Inches(4.8),
             fill_color=C_BG_CARD, line_color=C_GREEN, line_width=Pt(1))
    add_text_box(slide, "✅  Immediate Actions", Inches(0.6), Inches(1.3),
                 Inches(5.5), Inches(0.45), font_size=Pt(15), bold=True, color=C_GREEN)
    for i, item in enumerate(immediate):
        add_text_box(slide, item, Inches(0.6), Inches(1.9 + i * 0.85),
                     Inches(5.6), Inches(0.7), font_size=Pt(12), color=C_LIGHT_TEXT)

    # Roadmap
    add_rect(slide, Inches(6.8), Inches(1.2), Inches(6.1), Inches(4.8),
             fill_color=C_BG_CARD, line_color=C_ACCENT2, line_width=Pt(1))
    add_text_box(slide, "🗺️  Future Roadmap", Inches(7.0), Inches(1.3),
                 Inches(5.5), Inches(0.45), font_size=Pt(15), bold=True, color=C_ACCENT2)
    for i, item in enumerate(roadmap):
        add_text_box(slide, item, Inches(7.0), Inches(1.9 + i * 0.75),
                     Inches(5.7), Inches(0.65), font_size=Pt(12), color=C_LIGHT_TEXT)

    # Footer CTA
    add_rect(slide, Inches(0.4), Inches(6.3), Inches(12.5), Inches(0.9),
             fill_color=RGBColor(0x0F, 0x34, 0x60), line_color=C_ACCENT, line_width=Pt(1))
    add_text_box(slide,
                 "🚀  Ready to generate synthetic data at scale?  "
                 "Let's configure your environment and get started today.",
                 Inches(0.7), Inches(6.4), Inches(11.9), Inches(0.7),
                 font_size=Pt(13), bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)


def slide_closing(prs):
    """Slide 12 — Closing"""
    slide = blank_slide(prs)
    fill_bg(slide, C_BG_DARK)
    add_gradient_rect(slide, Inches(0), Inches(0), SLIDE_W, SLIDE_H,
                      RGBColor(0x0D, 0x11, 0x17), RGBColor(0x53, 0x34, 0x83))
    add_rect(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), fill_color=C_ACCENT)

    add_text_box(slide, "Thank You", Inches(1.5), Inches(2.0), Inches(10.3), Inches(1.2),
                 font_size=Pt(60), bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
    add_text_box(slide,
                 "Synthetic Data Generation Agent\n"
                 "Powered by Databricks · Claude Sonnet · Streamlit",
                 Inches(1.5), Inches(3.4), Inches(10.3), Inches(1.0),
                 font_size=Pt(18), color=C_LIGHT_TEXT, align=PP_ALIGN.CENTER)

    add_rect(slide, Inches(4.0), Inches(4.6), Inches(5.3), Inches(0.04), fill_color=C_ACCENT)

    add_text_box(slide, "Questions & Discussion",
                 Inches(1.5), Inches(4.8), Inches(10.3), Inches(0.6),
                 font_size=Pt(22), bold=True, color=C_ACCENT, align=PP_ALIGN.CENTER)

    add_rect(slide, Inches(0), Inches(7.2), SLIDE_W, Inches(0.3),
             fill_color=RGBColor(0x0F, 0x34, 0x60))
    add_text_box(slide, "Confidential · For Client Presentation Only",
                 Inches(0), Inches(7.2), SLIDE_W, Inches(0.3),
                 font_size=Pt(10), color=C_MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    prs = new_prs()

    print("Building slides...")
    slide_title(prs)
    print("  ✔ Slide 1: Title")
    slide_agenda(prs)
    print("  ✔ Slide 2: Agenda")
    slide_problem(prs)
    print("  ✔ Slide 3: Problem")
    slide_solution(prs)
    print("  ✔ Slide 4: Solution")
    slide_capabilities(prs)
    print("  ✔ Slide 5: Capabilities")
    slide_schemas(prs)
    print("  ✔ Slide 6: Schemas")
    slide_architecture(prs)
    print("  ✔ Slide 7: Architecture")
    slide_use_cases(prs)
    print("  ✔ Slide 8: Use Cases")
    slide_tech_stack(prs)
    print("  ✔ Slide 9: Tech Stack")
    slide_extensibility(prs)
    print("  ✔ Slide 10: Extensibility")
    slide_next_steps(prs)
    print("  ✔ Slide 11: Next Steps")
    slide_closing(prs)
    print("  ✔ Slide 12: Closing")

    output_path = r"C:\Users\P9193015\Downloads\DATA GEN\Synthetic_Data_Generation_Agent.pptx"
    prs.save(output_path)
    print(f"\n✅ Presentation saved to:\n   {output_path}")

