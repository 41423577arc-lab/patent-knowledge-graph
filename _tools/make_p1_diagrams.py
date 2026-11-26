"""Generate three transparent-background P1 flow diagrams.

Designed for a dark PPT: light text + neon-green lines, no slide title/background.
Place the PNG directly on the PPT page.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "交付给同伴的内容" / "P1-9_文档与交接" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
INK = (242, 255, 248, 255)
MUTED = (190, 212, 201, 255)
DIM = (135, 160, 147, 255)
NEON = (57, 255, 136, 255)
NEON_SOFT = (167, 243, 208, 255)
AMBER = (251, 191, 36, 255)
RED = (251, 113, 133, 255)
CARD = (8, 18, 13, 120)
BORDER = (57, 255, 136, 210)
FONT_DIR = Path("C:/Windows/Fonts")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("msyhbd.ttc" if bold else "msyh.ttc")), size)


def mono(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / "consola.ttf"), size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def text(draw, xy, value, size, fill=INK, bold=False, anchor="la", spacing=8):
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, anchor=anchor,
                        spacing=spacing, stroke_width=1, stroke_fill=(0, 0, 0, 150))


def box(draw, xy, fill=CARD, outline=BORDER, radius=18, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw, xy, value, fill=NEON, text_fill=(3, 10, 6, 255), size=22):
    tf = font(size, True)
    bbox = draw.textbbox((0, 0), value, font=tf)
    w = bbox[2] - bbox[0] + 26
    h = bbox[3] - bbox[1] + 14
    x, y = xy
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=fill)
    draw.text((x + w / 2, y + h / 2), value, font=tf, fill=text_fill, anchor="mm")


def arrow(draw, start, end, color=NEON, width=3):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    head = 14
    p1 = (x2 - head * math.cos(angle - 0.5), y2 - head * math.sin(angle - 0.5))
    p2 = (x2 - head * math.cos(angle + 0.5), y2 - head * math.sin(angle + 0.5))
    draw.polygon([(x2, y2), p1, p2], fill=color)


def top_tag(draw, tag: str, title: str, subtitle: str):
    pill(draw, (80, 55), tag, fill=NEON, text_fill=(3, 10, 6, 255), size=20)
    text(draw, (80, 110), title, 44, INK, bold=True)
    text(draw, (80, 170), subtitle, 22, MUTED)


def step_box(draw, x, y, w, h, step, title, sub, note):
    box(draw, (x, y, x + w, y + h))
    text(draw, (x + 24, y + 22), step, 18, NEON, bold=True)
    text(draw, (x + 24, y + 55), title, 28, INK, bold=True)
    text(draw, (x + 24, y + 105), sub, 20, MUTED)
    text(draw, (x + 24, y + h + 24), note, 16, DIM, spacing=5)


def node_chips(draw, y, labels):
    x = 80
    for label in labels:
        w = 150
        draw.rounded_rectangle((x, y, x + w, y + 48), radius=10,
                               fill=(8, 20, 14, 160), outline=(47, 93, 67, 220), width=1)
        text(draw, (x + w / 2, y + 24), label, 16, NEON_SOFT, anchor="mm")
        x += w + 12


def diagram1():
    # Pure modeling flow: tightly cropped, no slide furniture.
    image = Image.new("RGBA", (1640, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    boxes = [
        ("P1-1", "字段梳理", "公开号 / 申请号\n申请人 / IPC / 主题 / 功效"),
        ("P1-2", "七表结构", "patents · applicants\nIPC · 主题 · 功效\n引用 · 合作"),
        ("P1-2 / P1-3", "实体与关系", "5 类节点\n6 类关系"),
        ("P1-3", "编号与接口", "唯一编号 / 表间对应\nload_table / run_query"),
    ]
    xs = [50, 440, 830, 1220]
    y, w, h = 70, 340, 250
    for i, (step, title, sub) in enumerate(boxes):
        box(draw, (xs[i], y, xs[i] + w, y + h))
        text(draw, (xs[i] + 24, y + 24), step, 23, NEON, bold=True)
        text(draw, (xs[i] + 24, y + 66), title, 38, INK, bold=True)
        text(draw, (xs[i] + 24, y + 132), sub, 24, MUTED, spacing=8)
        if i < 3:
            arrow(draw, (xs[i] + 345, y + h / 2), (xs[i + 1] - 5, y + h / 2))
    image.save(OUT / "p1_modeling_flow.png")


def diagram2():
    image, draw = canvas()
    top_tag(draw, "P1 图谱构建", "图谱构建", "从关系到可查询的 Neo4j 图  ·  P1-4 ~ P1-7")
    draw.line((80, 215, 1840, 215), fill=(42, 64, 52, 200), width=2)
    boxes = [
        ("P1-4", "引用 / 合作", "442,917 条引用\n9,826 对合作", "CITES 仅样本内 35,114"),
        ("P1-5", "七表校验", "34 / 34 PASS\n无悬空 ID", "列名 / 外键 / 合作权重"),
        ("P1-6", "真实样例", "481 件\n七表同步", "300–500 条，字段完整"),
        ("P1-7", "Neo4j 图谱", "147,174 节点\n571,663 关系", "5 约束 · 2 索引；计数与 parquet 一致"),
    ]
    xs = [80, 500, 920, 1340]
    for i, (step, title, sub, note) in enumerate(boxes):
        step_box(draw, xs[i], 280, 360, 200, step, title, sub, note)
        if i < 3:
            arrow(draw, (xs[i] + 365, 380), (xs[i + 1] - 5, 380))
    draw.rounded_rectangle((80, 700, 1840, 790), radius=14,
                           fill=(4, 12, 8, 160), outline=(47, 93, 67, 220), width=1)
    text(draw, (110, 718), "MATCH (p:Patent) RETURN count(p) AS patents;", 20,
         (125, 211, 252, 255), mono=True) if False else text(
        draw, (110, 718), "MATCH (p:Patent) RETURN count(p) AS patents;", 20, (125, 211, 252, 255))
    text(draw, (110, 754), "106393", 30, INK, bold=True)
    text(draw, (450, 754), "5 类节点 · 6 类关系 · 导入后逐项核对", 20, MUTED)
    text(draw, (80, 840), "外部引用 407,803 条不建占位节点，用 external_citation_applicants 辅助表", 18, AMBER)
    text(draw, (80, 890), "CITES 方向：citing → cited；合作边逻辑无向，每对只存一条", 18, MUTED)
    image.save(OUT / "p1_graph_flow.png")


def diagram3():
    image, draw = canvas()
    top_tag(draw, "P1 质量与交付", "质量与交付", "规模、别名、预计算指标、文档交接  ·  P1-8 ~ P1-9")
    draw.line((80, 215, 1840, 215), fill=(42, 64, 52, 200), width=2)
    boxes = [
        ("P1-8", "规模 / 质量", "106,393 件\n86,814 技术类", "IPC 99.0% · 主题 82.35%\n功效 89.41%"),
        ("P1-8", "别名 / 引用", "393 条别名\n135,007 主体对", "Kia / Hyundai 不合并\n中国南方 pending_review"),
        ("P1-8", "预计算指标", "27,557 家\n1,293 行", "company_metrics / topic_year\nload_result 读取"),
        ("P1-9", "文档 / 交接", "handoff\npage_metrics", "P2/P3/P4/P5 各一段\n复现命令与口径"),
    ]
    xs = [80, 500, 920, 1340]
    for i, (step, title, sub, note) in enumerate(boxes):
        step_box(draw, xs[i], 280, 360, 200, step, title, sub, note)
        if i < 3:
            arrow(draw, (xs[i] + 365, 380), (xs[i + 1] - 5, 380))
    draw.rounded_rectangle((80, 700, 1840, 805), radius=14,
                           fill=(4, 12, 8, 160), outline=(120, 70, 30, 220), width=1)
    text(draw, (110, 720), "不能宣称", 22, RED, bold=True)
    text(draw, (230, 720), "全量产业数据  ·  2024–2025 趋势  ·  完整引用网络  ·  精确企业层级", 22, AMBER)
    text(draw, (110, 760), "16 批次按法律状态分层；CITES 样本内 7.93%、外部主体 3.90%；100 条抽样框待 P5 标 P/R/F1",
         17, MUTED)
    text(draw, (80, 850), "P1 交付：七张可校验表  ·  可复现图谱  ·  预计算指标  ·  写清边界的文档", 20, NEON_SOFT)
    image.save(OUT / "p1_quality_flow.png")


def neo4j_graph():
    src = ROOT / "交付给同伴的内容" / "P1-7_图谱建图" / "bloom-visualisation-detail.png"
    image = Image.open(src).convert("RGBA")
    bbox = image.getbbox()
    margin = 36
    left = max(150, bbox[0] - margin)
    cropped = image.crop((left, max(0, bbox[1] - margin),
                          min(image.width, bbox[2] + margin), min(image.height, bbox[3] + 60)))
    cropped.save(OUT / "p1_neo4j_graph.png")
    print("neo4j graph", cropped.size)


def data_structure_table():
    image = Image.new("RGBA", (1640, 640), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rows = [
        ("patents", "专利主表", "106,393", "patent_id · title · type · dates"),
        ("applicants", "专利-申请人", "115,927", "patent_id · applicant_std"),
        ("patent_ipc", "专利-IPC", "306,023", "patent_id · ipc_code · is_main"),
        ("patent_topic", "专利-主题", "104,723", "patent_id · topic · domain"),
        ("patent_efficacy", "专利-功效", "391,642", "patent_id · efficacy_l1/2/3"),
        ("citations", "引用", "442,917", "citing_id → cited_id"),
        ("cooperation", "合作", "9,826", "app_a · app_b · weight"),
    ]
    x, y = 20, 20
    widths = [260, 280, 170, 880]
    row_h = 64
    total_w = sum(widths)
    draw.rounded_rectangle((x, y, x + total_w, y + row_h * (len(rows) + 1)),
                           radius=16, fill=(8, 18, 13, 120), outline=(57, 255, 136, 200), width=2)
    draw.rectangle((x, y, x + total_w, y + row_h), fill=(16, 37, 28, 230))
    headers = ["表", "内容", "行数", "关键字段"]
    cx = x
    for head, cw in zip(headers, widths):
        text(draw, (cx + 16, y + row_h / 2), head, 19, MUTED, bold=True, anchor="lm")
        cx += cw
    for r, (name, desc, n, fields) in enumerate(rows, start=1):
        ry = y + r * row_h
        draw.line((x, ry, x + total_w, ry), fill=(42, 64, 52, 180), width=1)
        text(draw, (x + 16, ry + row_h / 2), name, 19, NEON, bold=True, anchor="lm")
        text(draw, (x + widths[0] + 16, ry + row_h / 2), desc, 18, INK, anchor="lm")
        text(draw, (x + widths[0] + widths[1] + widths[2] - 16, ry + row_h / 2),
             n, 18, NEON_SOFT, anchor="rm")
        text(draw, (x + widths[0] + widths[1] + widths[2] + 16, ry + row_h / 2),
             fields, 16, MUTED, anchor="lm")
    text(draw, (20, y + row_h * (len(rows) + 1) + 20),
         "7 张表  →  5 类节点 / 6 类关系", 20, AMBER, bold=True)
    image.save(OUT / "p1_data_structure.png")
    print("data structure", image.size)


if __name__ == "__main__":
    diagram1()
    diagram2()
    diagram3()
    neo4j_graph()
    data_structure_table()
    print("written", *[str(p) for p in sorted(OUT.glob("p1_*.png"))], sep="\n")
