"""Rebuild P1 slides 11-13 with formal wording and readable graphics."""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_p1_slides import (  # noqa: E402
    ASSETS, SRC, WHITE, GREEN, MUTED, AMBER, CARD, BORDER, BODY_FONT,
    clear, text_box, bullets, add_picture_fit, background, title, card, page_num, set_notes,
)

DST = Path(__file__).resolve().parents[2] / "汇报PPT(1)_P1版_正式.pptx"


def table_cell(cell, value, size=13, color=WHITE, bold=False, fill=None):
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill or CARD
    cell.margin_left = Inches(0.08)
    cell.margin_right = Inches(0.08)
    cell.margin_top = Inches(0.03)
    cell.margin_bottom = Inches(0.03)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = value
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def data_table(slide, x, y, w, h):
    rows = [
        ("patents", "专利主表", "106,393", "patent_id · title · type · dates"),
        ("applicants", "专利-申请人", "115,927", "patent_id · applicant_std"),
        ("patent_ipc", "专利-IPC", "306,023", "patent_id · ipc_code · is_main"),
        ("patent_topic", "专利-主题", "104,723", "patent_id · topic · domain"),
        ("patent_efficacy", "专利-功效", "391,642", "patent_id · efficacy_l1/2/3"),
        ("citations", "引用", "442,917", "citing_id → cited_id"),
        ("cooperation", "合作", "9,826", "app_a · app_b · weight"),
    ]
    table_shape = slide.shapes.add_table(8, 4, Inches(x), Inches(y), Inches(w), Inches(h))
    table = table_shape.table
    widths = [2.05, 1.95, 1.25, 4.2]
    for i, cw in enumerate(widths):
        table.columns[i].width = Inches(cw)
    for r in range(8):
        table.rows[r].height = Inches(h / 8)
    headers = ["表", "内容", "行数", "关键字段"]
    for c, head in enumerate(headers):
        table_cell(table.cell(0, c), head, size=13, color=MUTED, bold=True,
                   fill=RGBColor(0x16, 0x25, 0x1C))
    for r, (name, desc, n, fields) in enumerate(rows, start=1):
        table_cell(table.cell(r, 0), name, size=13, color=GREEN, bold=True)
        table_cell(table.cell(r, 1), desc, size=13, color=WHITE)
        table_cell(table.cell(r, 2), n, size=13, color=RGBColor(0xD7, 0xF9, 0xE2))
        table_cell(table.cell(r, 3), fields, size=12, color=MUTED)


def page1(slide, prs):
    clear(slide)
    background(slide, prs)
    title(slide, "知识建模：字段体系与表结构设计",
          "P1-1 ~ P1-3  ·  表结构与图结构同步确定")
    add_picture_fit(slide, ASSETS / "p1_modeling_flow.png", 0.95, 1.62, 18.1, 4.35)
    cards = [
        ("主要工作", [
            "字段梳理：统一公开号、申请号、申请人、IPC、主题、功效等字段口径",
            "七表结构：确定七张表的列名、字段顺序与表间对应关系",
            "实体与关系：设计 5 类节点、6 类关系",
            "编号与接口：明确唯一编号、表间对应关系及统一读取入口",
        ]),
        ("输出结果", [
            "七张表结构稳定，专利编号唯一，子表可回溯至主表",
            "图谱结构固定为 5 类节点、6 类关系",
            "P2/P3 可按统一表结构读取数据或查询图谱",
        ]),
        ("设计作用", [
            "降低后续抽取、建图和页面开发的返工风险",
            "保证图谱中的节点与关系可回溯至原始表",
            "为跨角色协作提供统一字段说明与接口边界",
        ]),
    ]
    for i, (head, items) in enumerate(cards):
        x = 0.95 + i * 6.05
        card(slide, x, 6.22, 5.72, 3.05)
        bullets(slide, x + 0.28, 6.4, 5.15, 2.72, head, items, size=13.5, heading_size=19)
    text_box(slide, 0.95, 9.55, 18.1, 0.35,
             "数据口径：16 个批次按法律状态分层导出，并非随机全量；2024—2025 年数据不完整。",
             size=13, color=AMBER)
    set_notes(slide, "第一页介绍知识建模。本部分首先统一公开号、申请号、申请人、IPC、主题和功效等字段口径，再确定七张表的列名、字段顺序与表间对应关系。在此基础上设计图谱结构，包括 5 类节点、6 类关系，并明确唯一编号和统一读取入口。输出结果是七张表结构与图谱结构均已固定，子表可以回溯至主表，P2 和 P3 可以直接按统一结构读取数据或查询图谱。这样设计的作用是降低后续抽取、建图和页面开发的返工风险，同时保证节点与关系可追溯，并为跨角色协作提供统一的字段说明和接口边界。")
    page_num(slide, 11)


def page2(slide, prs):
    clear(slide)
    background(slide, prs)
    title(slide, "数据处理与图谱构建",
          "P1-4 ~ P1-7  ·  关系抽取、质量校验、图谱入库")
    add_picture_fit(slide, ASSETS / "p1_neo4j_graph.png", 0.85, 1.75, 8.35, 4.85)
    text_box(slide, 0.95, 6.68, 8.2, 0.3,
             "蓝色：专利    绿色：申请人    橙色：IPC", size=13, color=GREEN, bold=True)
    text_box(slide, 0.95, 6.98, 8.2, 0.3,
             "关系：APPLIES_FOR / HAS_IPC / CITES", size=12, color=MUTED)
    data_table(slide, 9.45, 1.78, 9.45, 4.05)
    text_box(slide, 9.45, 5.95, 9.45, 0.3,
             "七张表 → 5 类节点 / 6 类关系", size=14, color=AMBER, bold=True)
    cards = [
        ("处理内容", [
            "关系构建：生成引用 442,917 条、合作 9,826 对，引用仅以样本内专利为引用方",
            "质量校验：34 项检查全部通过，无悬空编号，合作权重与共同专利数一致",
            "样例抽取：抽取 481 件真实专利，七表同步，供页面联调",
            "图谱入库：导入 Neo4j，形成 147,174 个节点、571,663 条关系",
        ]),
        ("输出结果", [
            "七张表规模确定：专利 106,393 件，其余表与主表保持对应",
            "图谱包含 5 类节点、6 类关系，设置 5 个唯一编号规则与 2 个索引",
            "查询验证：专利总数为 106,393，固定查询与两跳路径均通过",
        ]),
        ("设计考虑", [
            "表结构先行，图谱按表构建，保证数据可追溯",
            "引用仅保留样本内边，避免以不完整外部数据冒充全量",
            "先校验后入库，防止悬空编号和错误权重进入图谱",
        ]),
    ]
    for i, (head, items) in enumerate(cards):
        x = 0.95 + i * 6.05
        card(slide, x, 7.38, 5.72, 2.55)
        bullets(slide, x + 0.26, 7.52, 5.18, 2.28, head, items, size=11.5, heading_size=17)
    text_box(slide, 0.95, 10.1, 18.1, 0.3,
             "Neo4j Desktop 2026.10.2  ·  5 个唯一编号规则  ·  2 个索引",
             size=11.5, color=MUTED)
    set_notes(slide, "第二页介绍数据处理与图谱构建。本部分从七张表生成引用和合作关系，其中引用 442,917 条、合作 9,826 对；随后完成七表质量校验，34 项检查全部通过，没有悬空编号；并抽取 481 件真实专利形成开发样例。最后将七张表导入 Neo4j，得到 147,174 个节点、571,663 条关系。左侧是实际图谱局部，蓝色为专利、绿色为申请人、橙色为 IPC，关系包括 APPLIES_FOR、HAS_IPC 和 CITES。这样处理的原因是：表结构先行，图谱按表构建，保证节点和关系可追溯；引用仅保留样本内边，避免以不完整的外部数据冒充全量；先校验后入库，防止悬空编号和错误权重进入图谱。")
    page_num(slide, 12)


def page3(slide, prs):
    clear(slide)
    background(slide, prs)
    title(slide, "总结与交付：数据资产与下游支撑",
          "P1-8 ~ P1-9  ·  质量核验、指标预计算、文档交接")
    cards = [
        ("主要工作", [
            "质量核验：检查规模、覆盖率、缺失与关系一致性",
            "主体归一：形成展示层企业名称表，避免不同集团误并",
            "引用聚合：将专利引用整理为企业级辅助表",
            "指标预计算：生成企业指标与主题年度统计",
            "文档交接：整理页面口径、复现命令与数据边界",
        ]),
        ("输出结果", [
            "数据链路可复现，各环节均有校验记录",
            "页面所需数据均有对应表或查询入口",
            "已知局限单独记录，避免误读为全量产业数据",
            "P4/P5 可直接引用统一的数据说明与质量报告",
        ]),
        ("对下游开发的支持", [
            "P2：企业专利数、合作关系、企业指标、主题年度统计",
            "P3：Neo4j 查询入口、引用覆盖说明、企业引用辅助表",
            "共用：load_table / load_result / run_query",
            "样例与全量同构，通过 USE_SAMPLE 切换",
        ]),
    ]
    for i, (head, items) in enumerate(cards):
        x = 0.95 + i * 6.05
        card(slide, x, 2.05, 5.72, 5.05)
        bullets(slide, x + 0.3, 2.25, 5.12, 4.7, head, items, size=14.5, heading_size=20)
    chips = ["七表数据", "Neo4j 图谱", "预计算指标", "口径文档"]
    for i, chip_text in enumerate(chips):
        cx = 0.95 + i * 4.62
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(7.48),
                                       Inches(4.25), Inches(0.82))
        shape.fill.solid()
        shape.fill.fore_color.rgb = CARD
        shape.line.color.rgb = BORDER
        shape.line.width = Pt(1)
        shape.shadow.inherit = False
        text_box(slide, cx + 0.2, 7.66, 3.85, 0.45, chip_text, size=16, color=GREEN,
                 bold=True, align=PP_ALIGN.CENTER)
    text_box(slide, 0.95, 9.4, 18.2, 0.45,
             "本部分交付的是一套可复用的数据资产：七表数据、可查询图谱、预计算指标与统一口径文档。",
             size=15, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    set_notes(slide, "本部分最后进行总结。在数据建模和图谱构建之后，P1 还完成了质量核验与交付整理：检查七张表的规模、覆盖率、缺失和关系一致性；形成展示层企业名称表；将专利引用整理为企业级辅助表；并预计算企业指标与主题年度统计。最终形成的是一套可复用的数据资产，包括七表数据、可查询图谱、质量报告、企业名称与指标表，以及人工抽样框。对下游开发的支持主要体现在三个方面：第一，统一取数接口，P2 使用 load_table 和 load_result 读取表与指标，P3 使用 run_query 查询图谱；第二，样例与全量数据结构同构，通过 USE_SAMPLE 切换，前端无需改代码；第三，页面口径文档明确分母、时间窗口、引用覆盖率和结论边界。这样 P2 和 P3 可以在不直接处理底层数据的情况下完成页面与问答，P4 和 P5 也可按同一套口径完成文档与验收。")
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
