"""Fill slides 11-13 of the team report deck with P1 content."""
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "汇报PPT(1).pptx"
DST = ROOT.parent / "汇报PPT(1)_P1版.pptx"
ASSETS = ROOT / "交付给同伴的内容" / "P1-9_文档与交接" / "assets"
BG = ROOT / "_tools" / "p1_dark_bg.png"

WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0xB8, 0xFB, 0x87)
MUTED = RGBColor(0xB7, 0xC6, 0xBD)
AMBER = RGBColor(0xFB, 0xBF, 0x24)
CARD = RGBColor(0x0F, 0x17, 0x13)
BORDER = RGBColor(0x2A, 0x40, 0x34)
TITLE_FONT = "可画风暴黑-简"
BODY_FONT = "微软雅黑"


def clear(slide):
    for shape in list(slide.shapes):
        element = shape._element
        element.getparent().remove(element)


def text_box(slide, x, y, w, h, value, size=18, color=WHITE, bold=False,
             font=BODY_FONT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             line_spacing=1.05):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = value
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return shape


def bullets(slide, x, y, w, h, heading, items, size=15, heading_size=20):
    text_box(slide, x, y, w, 0.45, heading, size=heading_size, color=GREEN,
             bold=True, font=TITLE_FONT)
    shape = slide.shapes.add_textbox(Inches(x), Inches(y + 0.5), Inches(w), Inches(h - 0.5))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(5)
        p.line_spacing = 1.02
        r1 = p.add_run()
        r1.text = "• "
        r1.font.name = BODY_FONT
        r1.font.size = Pt(size)
        r1.font.color.rgb = GREEN
        r2 = p.add_run()
        r2.text = item
        r2.font.name = BODY_FONT
        r2.font.size = Pt(size)
        r2.font.color.rgb = WHITE


def add_picture_fit(slide, path, x, y, w, h):
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    left = x + (w - pw) / 2
    top = y + (h - ph) / 2
    return slide.shapes.add_picture(str(path), Inches(left), Inches(top),
                                    Inches(pw), Inches(ph))


def background(slide, prs):
    slide.shapes.add_picture(str(BG), 0, 0, width=prs.slide_width, height=prs.slide_height)


def title(slide, main, sub):
    text_box(slide, 0.95, 0.52, 18.2, 0.75, main, size=36, color=WHITE,
             bold=False, font=TITLE_FONT)
    text_box(slide, 0.97, 1.18, 18.0, 0.38, sub, size=15, color=MUTED)
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.97), Inches(1.57),
                                  Inches(3.0), Inches(0.045))
    line.fill.solid()
    line.fill.fore_color.rgb = GREEN
    line.line.fill.background()
    line.shadow.inherit = False


def card(slide, x, y, w, h):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                   Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD
    shape.line.color.rgb = BORDER
    shape.line.width = Pt(1)
    shape.shadow.inherit = False
    return shape


def page_num(slide, n):
    text_box(slide, 19.0, 10.72, 0.5, 0.3, str(n), size=10, color=MUTED,
             align=PP_ALIGN.RIGHT)


def set_notes(slide, value):
    slide.notes_slide.notes_text_frame.text = value


def page1(slide, prs):
    clear(slide)
    background(slide, prs)
    title(slide, "知识建模：从字段到七张表",
          "P1-1 ~ P1-3  ·  先定表结构，再定图结构")
    add_picture_fit(slide, ASSETS / "p1_modeling_flow.png", 0.95, 1.75, 18.1, 3.62)
    cards = [
        ("我做了什么", [
            "字段梳理：公开号、申请号、申请人、IPC、主题、功效",
            "七表结构：列名、顺序、表间对应关系一次定好",
            "实体与关系：5 类节点、6 类关系",
            "编号与接口：唯一编号 + 表间对应 + 读取入口",
        ]),
        ("结果如何", [
            "七张表结构固定，专利编号唯一，子表可对应回主表",
            "图谱结构固定为 5 类节点、6 类关系",
            "P2/P3 可直接按表结构读表或查图",
        ]),
        ("作用是什么", [
            "不返工：抽取、建图、页面都按同一套字段做",
            "可解释：图上的节点和关系都能对应回七张表",
            "可交接：P2/P3/P4/P5 看同一份结构说明",
        ]),
    ]
    for i, (head, items) in enumerate(cards):
        x = 0.95 + i * 6.05
        card(slide, x, 5.75, 5.72, 3.55)
        bullets(slide, x + 0.28, 5.95, 5.15, 3.2, head, items, size=14, heading_size=19)
    text_box(slide, 0.95, 9.72, 18.1, 0.35,
             "数据口径：16 批次按法律状态分层，不是随机全量；2024—2025 不完整",
             size=14, color=AMBER)
    set_notes(slide, "第一页是知识建模。我先梳理原始字段，再把它们收敛成七张表：专利、申请人、IPC、主题、功效、引用、合作，列名、顺序、表间对应关系一次定好。然后在这个表结构上设计图模型：5 类节点、6 类关系，明确引用方向、合作边和唯一编号。最后确定读取接口：表用 load_table，图用 run_query，预计算指标用 load_result。这样做的结果是，七张表和图谱结构都固定下来，后面的抽取、建图、页面不用再改模型；P2/P3 可以直接按这套表结构开发，P4/P5 也能按同一份字段说明写文档和验收。")
    page_num(slide, 11)


def page2(slide, prs):
    clear(slide)
    background(slide, prs)
    title(slide, "数据处理与图谱：从七张表到 Neo4j",
          "P1-4 ~ P1-7  ·  关系、校验、样例、建图")
    add_picture_fit(slide, ASSETS / "p1_neo4j_graph.png", 0.85, 1.78, 8.25, 5.0)
    add_picture_fit(slide, ASSETS / "p1_data_structure.png", 9.45, 1.78, 9.55, 3.73)
    cards = [
        ("做了什么处理", [
            "建关系：引用 442,917 条、合作 9,826 对",
            "做校验：34 / 34 通过，无悬空编号",
            "抽样例：481 件真实专利，七表同步",
            "导入图：147,174 节点、571,663 条关系",
        ]),
        ("处理成啥样", [
            "七张表规模固定：专利 106,393 件",
            "图谱为 5 类节点、6 类关系，5 个唯一编号规则",
            "查询返回 106393；固定查询与两跳路径已跑通",
        ]),
        ("为什么这么处理", [
            "表结构先定，图按表建，节点/关系可追溯",
            "引用只建样本内，外部 40.7 万条用辅助表",
            "先校验再建图，避免悬空编号进入图谱",
        ]),
    ]
    for i, (head, items) in enumerate(cards):
        x = 0.95 + i * 6.05
        card(slide, x, 7.08, 5.72, 2.78)
        bullets(slide, x + 0.26, 7.22, 5.18, 2.48, head, items, size=12.5, heading_size=18)
    text_box(slide, 0.95, 10.16, 18.1, 0.3,
             "Neo4j Desktop 2026.10.2  ·  5 个唯一编号规则  ·  2 个索引",
             size=12, color=MUTED)
    set_notes(slide, "第二页是数据处理和图谱，覆盖 P1-4 到 P1-7。我先用七张表生成引用和合作关系：引用 442,917 条、合作 9,826 对；再做七表校验，34 项全过，没有悬空编号；抽 481 件真实样例做联调。然后把七张表导入 Neo4j，得到 147,174 个节点、571,663 条关系。右边是实际图谱局部：蓝色是专利、绿色是申请人、橙色是 IPC，边上能看到 APPLIES_FOR、HAS_IPC、CITES。为什么这么处理：表结构先固定，图直接按表建，每个节点和关系都能追溯；引用只建样本内 35,114 条，外部 40.7 万条没有建占位节点，用辅助表补，避免把不完整的引用网说成全量。")
    page_num(slide, 12)


def page3(slide, prs):
    clear(slide)
    background(slide, prs)
    title(slide, "总结与交付：给网页同学留下了什么",
          "P1-8 ~ P1-9  ·  质量、指标、文档")
    cards = [
        ("我做了什么", [
            "质量核验：规模、覆盖率、缺失、关系一致性",
            "企业名称归一：展示层别名，不硬并不同集团",
            "引用聚合：把专利引用整理成企业级辅助表",
            "指标预计算：企业指标、主题年度计数",
            "文档交接：页面口径、复现命令、边界说明",
        ]),
        ("结果如何", [
            "数据链路可复现，每一步都有校验结果",
            "页面所需数据都有对应表或查询入口",
            "已知局限被单独记录，避免误读为全量产业数据",
            "P4/P5 可直接引用同一套数据说明和质量报告",
        ]),
        ("给 P2/P3 提供了什么", [
            "P2：企业专利数、合作关系、企业指标、主题年度统计",
            "P3：Neo4j 查询入口、引用覆盖说明、企业级引用辅助表",
            "共用：load_table / load_result / run_query",
            "样例与全量同名同列，USE_SAMPLE 一键切换",
        ]),
    ]
    for i, (head, items) in enumerate(cards):
        x = 0.95 + i * 6.05
        card(slide, x, 2.05, 5.72, 4.75)
        bullets(slide, x + 0.3, 2.28, 5.12, 4.35, head, items, size=15, heading_size=21)
    chips = ["七张表", "Neo4j 图谱", "预计算指标", "口径文档"]
    for i, chip_text in enumerate(chips):
        cx = 0.95 + i * 4.62
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(7.25),
                                       Inches(4.25), Inches(0.82))
        shape.fill.solid(); shape.fill.fore_color.rgb = CARD
        shape.line.color.rgb = BORDER; shape.line.width = Pt(1); shape.shadow.inherit = False
        text_box(slide, cx + 0.2, 7.43, 3.85, 0.45, chip_text, size=16, color=GREEN,
                 bold=True, align=PP_ALIGN.CENTER)
    text_box(slide, 0.95, 9.55, 18.2, 0.45,
             "交付不是一堆文件，而是“七张表 + 一个可查询图谱 + 一套可复用指标 + 一份边界说明”。",
             size=15, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    set_notes(slide, "最后我做一次总结。除了前面的数据建模和图谱构建，我还完成了质量核验和交付整理：检查七张表的规模、覆盖率、缺失和关系一致性；对企业名称做展示层归一；把引用关系整理成企业级聚合；并把页面需要的排名、网络指标和主题年度统计预计算成结果表。最终形成的不是单个文件，而是一套可以直接复用的数据资产：七张表、一个可查询的图谱、一份质量报告、企业别名和指标表，以及人工抽样框。对后面做网页的同学，我主要提供了三层支持：第一，统一取数接口，P2 用 load_table 和 load_result 读表与指标，P3 用 run_query 查图；第二，样例和全量同名同列，通过 USE_SAMPLE 切换，前端不需要改代码；第三，页面口径文档，明确分母、时间窗口、引用覆盖率和哪些结论不能下。这样 P2 和 P3 可以在不接触底层数据的情况下完成页面和问答，P4 和 P5 也能按同一套口径写文档和验收。")
    page_num(slide, 13)


def main():
    prs = Presentation(str(SRC))
    page1(prs.slides[10], prs)
    page2(prs.slides[11], prs)
    page3(prs.slides[12], prs)
    prs.save(str(DST))
    print("saved", DST)


if __name__ == "__main__":
    main()
