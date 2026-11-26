"""Generate three 16:9 dark/neon-green storyboards for the P1 PPT."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "交付给同伴的内容" / "P1-9_文档与交接" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BG_TOP = (7, 12, 9)
BG_BOTTOM = (16, 27, 20)
INK = "#F2F7F4"
MUTED = "#9FB3A8"
DIM = "#6B7F73"
NEON = "#39FF88"
NEON_SOFT = "#A7F3D0"
AMBER = "#FBBF24"
RED = "#FB7185"
CARD = "#0F1713"
CARD_2 = "#121E17"
BORDER = "#2A4034"
BLACK = "#061009"

FONT_DIR = Path("C:/Windows/Fonts")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / ("msyhbd.ttc" if bold else "msyh.ttc")), size)


def mono(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / "consola.ttf"), size)


def make_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        t = y / (H - 1)
        color = tuple(int(BG_TOP[i] * (1 - t) + BG_BOTTOM[i] * t) for i in range(3))
        draw.line((0, y, W, y), fill=color)
    # subtle grid
    for x in range(0, W, 80):
        draw.line((x, 0, x, H), fill="#122119", width=1)
    for y in range(0, H, 80):
        draw.line((0, y, W, y), fill="#122119", width=1)
    return image, draw


def frame(draw, title: str, subtitle: str):
    draw.text((80, 55), title, font=font(50, True), fill=INK)
    draw.text((80, 122), subtitle, font=font(26), fill=MUTED)
    draw.line((80, 172, 1840, 172), fill="#1F3528", width=2)
    draw.line((80, 172, 280, 172), fill=NEON, width=4)


def box(draw, xy, fill=CARD, outline=BORDER, width=2, radius=24):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw, xy, text, fill=NEON, text_fill=BLACK, text_font=None):
    tf = text_font or font(23, True)
    bbox = draw.textbbox((0, 0), text, font=tf)
    w = bbox[2] - bbox[0] + 30
    h = bbox[3] - bbox[1] + 16
    x, y = xy
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=fill)
    draw.text((x + w / 2, y + h / 2), text, font=tf, fill=text_fill, anchor="mm")
    return w, h


def label_box(draw, xy, text, text_font, fill=CARD_2, text_fill=NEON, outline=BORDER):
    bbox = draw.multiline_textbbox((0, 0), text, font=text_font, spacing=4)
    w = bbox[2] - bbox[0] + 18
    h = bbox[3] - bbox[1] + 12
    x, y = xy
    draw.rounded_rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2),
                           radius=9, fill=fill, outline=outline, width=1)
    draw.multiline_text((x, y), text, font=text_font, fill=text_fill,
                        anchor="mm", align="center", spacing=3)


def arrow(draw, start, end, color=NEON, width=4, label=None, label_font=None,
          offset=(0, -22), double=False):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    head = 14
    ends = [(x2, y2, angle)]
    if double:
        ends.append((x1, y1, angle + math.pi))
    for px, py, a in ends:
        p1 = (px - head * math.cos(a - 0.5), py - head * math.sin(a - 0.5))
        p2 = (px - head * math.cos(a + 0.5), py - head * math.sin(a + 0.5))
        draw.polygon([(px, py), p1, p2], fill=color)
    if label:
        lf = label_font or font(16)
        mx = (x1 + x2) / 2 + offset[0]
        my = (y1 + y2) / 2 + offset[1]
        label_box(draw, (mx, my), label, lf)


def table(draw, x, y, row_h, headers, rows, col_widths, text_font=None):
    tf = text_font or font(20)
    total_w = sum(col_widths)
    draw.rounded_rectangle((x, y, x + total_w, y + row_h * (len(rows) + 1)),
                           radius=14, fill=CARD, outline=BORDER, width=2)
    draw.rectangle((x, y, x + total_w, y + row_h), fill="#16251C")
    cx = x
    for head, cw in zip(headers, col_widths):
        draw.text((cx + 12, y + row_h / 2), head, font=font(18, True),
                  fill=MUTED, anchor="lm")
        cx += cw
    for r, row in enumerate(rows, start=1):
        ry = y + r * row_h
        draw.line((x, ry, x + total_w, ry), fill=BORDER, width=1)
        cx = x
        for i, (val, cw) in enumerate(zip(row, col_widths)):
            if i == 0:
                draw.text((cx + 12, ry + row_h / 2), str(val), font=tf, fill=INK, anchor="lm")
            else:
                draw.text((cx + cw - 12, ry + row_h / 2), str(val), font=tf, fill=NEON, anchor="rm")
            cx += cw


def slide1():
    image, draw = make_canvas()
    frame(draw, "知识建模 + 数据获取", "先冻结契约，再做数据接入、去重与探查")
    # left card
    box(draw, (80, 210, 800, 830), CARD)
    pill(draw, (110, 235), "01 知识建模", NEON, BLACK)
    draw.text((110, 305), "七表契约 C", font=font(40, True), fill=INK)
    draw.text((110, 365), "专利 / 申请人 / IPC / 主题 / 功效 / 引用 / 合作",
              font=font(23), fill=MUTED)
    draw.text((110, 415), "列名 · 顺序 · 外键 冻结", font=font(24, True), fill=NEON)
    draw.text((110, 465), "图与表同源，避免后面返工", font=font(21), fill=MUTED)
    # node chips
    nodes = ["Patent", "Applicant", "IPC", "Technology", "Domain"]
    x = 110
    for n in nodes:
        w = 126
        draw.rounded_rectangle((x, 545, x + w, 590), radius=10,
                               fill="#14251B", outline="#2F5D43", width=1)
        draw.text((x + w / 2, 568), n, font=font(16), fill=NEON_SOFT, anchor="mm")
        x += w + 8
    draw.text((110, 620), "5 类节点", font=font(20, True), fill=INK)
    draw.text((110, 660), "APPLIES_FOR · CITES · HAS_IPC", font=font(18), fill=MUTED)
    draw.text((110, 695), "INVOLVES · BELONGS_TO · CO_APPLIED_WITH", font=font(18), fill=MUTED)
    draw.text((110, 755), "契约先行：表结构 / 关系方向 / 唯一键", font=font(20), fill=AMBER)

    # right card
    box(draw, (840, 210, 1840, 830), CARD)
    pill(draw, (870, 235), "02 数据获取", NEON, BLACK)
    draw.text((870, 300), "16 个 xlsx → 去重 → 7 张表", font=font(31, True), fill=INK)
    stages = [
        ("16 个 xlsx", "142,112 行 × 204 列", 870, 370),
        ("按申请号去重", "106,393 件", 1145, 370),
        ("7 张契约表", "同名同列 / 可校验", 1420, 370),
    ]
    for title, sub, x, y in stages:
        box(draw, (x, y, x + 230, y + 125), CARD_2, "#2F5D43", radius=16)
        draw.text((x + 115, y + 42), title, font=font(21, True), fill=INK, anchor="mm")
        draw.text((x + 115, y + 82), sub, font=font(16), fill=MUTED, anchor="mm")
    arrow(draw, (1100, 432), (1145, 432), NEON, 3)
    arrow(draw, (1375, 432), (1420, 432), NEON, 3)
    bullets = [
        "代表公开号：发明授权 > 发明申请 > 实用新型 > 外观设计",
        "非主文献 3,668 行；外观设计保留，但不写技术属性",
        "16 批次按法律状态分层，不是随机全量",
    ]
    for i, text in enumerate(bullets):
        y = 535 + i * 52
        draw.ellipse((875, y + 8, 887, y + 20), fill=NEON)
        draw.text((905, y), text, font=font(21), fill=INK)
    # coverage chips
    chips = [("IPC", "99.0%", "85,946 / 86,814"),
             ("主题", "82.35%", "71,487 / 86,814"),
             ("功效", "89.41%", "77,617 / 86,814")]
    for i, (name, pct, sub) in enumerate(chips):
        x = 870 + i * 320
        box(draw, (x, 705, x + 300, 795), "#10251A", "#2F5D43", radius=14)
        draw.text((x + 18, 718), name, font=font(18, True), fill=MUTED)
        draw.text((x + 18, 742), pct, font=font(30, True), fill=NEON)
        draw.text((x + 128, 755), sub, font=font(15), fill=MUTED)
    draw.text((870, 815), "2024—2025 不完整，趋势只用 2010/2015—2023",
              font=font(19), fill=AMBER)
    draw.rounded_rectangle((80, 895, 1840, 960), radius=14, fill="#10251A", outline="#2F5D43", width=1)
    draw.text((110, 927), "研究数据集：16 批次 × 法律状态分层   |   全部 106,393 / 技术类 86,814   |   2024—2025 不完整",
              font=font(20, True), fill=NEON_SOFT, anchor="lm")
    image.save(OUT / "slide1_data_pipeline.png", quality=95)


def slide2():
    image, draw = make_canvas()
    frame(draw, "抽取融合 + 知识存储", "从七张表到 147,174 节点 / 571,663 条关系")
    # left
    box(draw, (80, 210, 840, 860), CARD)
    pill(draw, (110, 235), "03 抽取融合", NEON, BLACK)
    rows = [
        ("申请人", "分号拆 + 去后缀；别名 393 条"),
        ("IPC", "306,023 行 / 13,166 个"),
        ("主题", "104,723 行 / 50 主题 / 8 领域"),
        ("功效", "391,642 行"),
        ("引用", "442,917 条（样本内 35,114）"),
        ("合作", "9,826 对 / 6,704 件多申请人"),
    ]
    for i, (name, desc) in enumerate(rows):
        y = 305 + i * 72
        draw.text((110, y), name, font=font(23, True), fill=NEON)
        draw.text((230, y), desc, font=font(21), fill=INK)
    draw.text((110, 760), "（未细分）16,839 行单列", font=font(21, True), fill=AMBER)
    draw.text((110, 800), "别名只是展示层，契约表不改", font=font(19), fill=MUTED)

    # right
    box(draw, (880, 210, 1840, 860), CARD)
    pill(draw, (910, 235), "04 知识存储", NEON, BLACK)
    # nodes
    nodes = {
        "Applicant A": (930, 300, 1100, 360),
        "Applicant B": (930, 470, 1100, 530),
        "Patent": (1180, 300, 1350, 360),
        "IPC": (1430, 300, 1570, 360),
        "Technology": (1180, 470, 1350, 530),
        "Domain": (1430, 470, 1570, 530),
    }
    for name, (x1, y1, x2, y2) in nodes.items():
        box(draw, (x1, y1, x2, y2), "#12251B", "#2F5D43", radius=12, width=2)
        draw.text(((x1 + x2) / 2, (y1 + y2) / 2), name, font=font(17, True),
                  fill=INK, anchor="mm")
    arrow(draw, (1100, 330), (1180, 330), NEON, 3, "APPLIES_FOR", font(12), (0, -24))
    arrow(draw, (1350, 330), (1430, 330), NEON, 3, "HAS_IPC", font(12), (0, -24))
    arrow(draw, (1265, 360), (1265, 470), NEON, 3, "INVOLVES", font(12), (60, 0))
    arrow(draw, (1350, 500), (1430, 500), NEON, 3, "BELONGS_TO", font(11), (0, -24))
    arrow(draw, (1015, 360), (1015, 470), NEON, 3, "CO_APPLIED_WITH", font(11), (76, 0), double=True)
    # CITES self-loop above Patent
    draw.line([(1265, 300), (1265, 255), (1310, 255), (1310, 300)], fill=NEON, width=3)
    draw.polygon([(1310, 300), (1301, 286), (1319, 286)], fill=NEON)
    label_box(draw, (1338, 270), "CITES", font(12))
    draw.text((910, 580), "APPLIES_FOR · CITES · HAS_IPC · INVOLVES · BELONGS_TO · CO_APPLIED_WITH",
              font=font(15), fill=MUTED)
    # counts
    draw.text((910, 610), "147,174 节点  /  571,663 关系", font=font(26, True), fill=NEON)
    draw.text((910, 655), "5 约束  /  2 索引  /  计数与 parquet 一致", font=font(19), fill=MUTED)
    # query panel
    draw.rounded_rectangle((910, 700, 1810, 825), radius=14, fill=BLACK, outline="#2F5D43", width=1)
    draw.text((930, 716), "MATCH (p:Patent) RETURN count(p) AS patents;", font=mono(20), fill="#7DD3FC")
    draw.text((930, 755), "patents", font=mono(16), fill=MUTED)
    draw.text((930, 780), "106393", font=mono(32), fill=INK)
    draw.text((1210, 785), "CITES 仅样本内；外部 407,803 用辅助表", font=font(16), fill=AMBER)
    draw.rounded_rectangle((80, 895, 1840, 960), radius=14, fill="#10251A", outline="#2F5D43", width=1)
    draw.text((110, 927), "CITES 样本内 35,114 / 外部 407,803 用辅助表   |   节点/关系数与 parquet 逐项一致",
              font=font(20, True), fill=NEON_SOFT, anchor="lm")
    image.save(OUT / "slide2_graph_schema.png", quality=95)


def slide3():
    image, draw = make_canvas()
    frame(draw, "分析方法 + 质量边界", "P1 只做预计算指标；分析与问答由 P2/P3 完成")
    # top wide card
    box(draw, (80, 210, 1840, 500), CARD)
    pill(draw, (110, 235), "05 分析方法（P1 支撑）", NEON, BLACK)
    cards = [
        ("company_metrics", "27,557 家", "PageRank · 度 · 中介"),
        ("topic_year", "1,293 行", "主题 × 年度"),
        ("company_citation_pairs", "135,007 对", "企业级引用聚合（口径 C）"),
    ]
    for i, (name, num, desc) in enumerate(cards):
        x = 110 + i * 570
        box(draw, (x, 305, x + 530, 455), "#10251A", "#2F5D43", radius=16)
        draw.text((x + 24, 325), name, font=font(22, True), fill=MUTED)
        draw.text((x + 24, 365), num, font=font(40, True), fill=NEON)
        draw.text((x + 24, 420), desc, font=font(18), fill=INK)
    draw.text((110, 470), "P2 页面一/二、P3 问答读这些表；P1 不画页面、不做意图",
              font=font(18), fill=MUTED)

    # bottom left quality
    box(draw, (80, 540, 880, 860), CARD)
    draw.text((110, 565), "质量（分母 86,814 技术类）", font=font(23, True), fill=INK)
    q = [("IPC", "99.0%"), ("主题", "82.35%"), ("功效", "89.41%")]
    for i, (name, pct) in enumerate(q):
        y = 620 + i * 68
        draw.text((110, y), name, font=font(22), fill=MUTED)
        draw.text((240, y - 5), pct, font=font(28, True), fill=NEON)
    draw.text((110, 825), "（未细分）16,839 行单列，不混入细粒度排名", font=font(18), fill=AMBER)

    # bottom right boundaries
    box(draw, (920, 540, 1840, 860), CARD)
    draw.text((950, 565), "边界（答辩时说清楚）", font=font(23, True), fill=INK)
    bullets = [
        "16 批次按法律状态分层，不是随机全量",
        "2024—2025 不完整，趋势只用 2010/2015—2023",
        "CITES 样本内 7.93%；外部主体覆盖 3.90%",
        "别名 393 条展示层；Kia / Hyundai 不合并",
        "CQ10：用 external 明细算 c(A,B)/C_A，C_A<30 不判",
    ]
    for i, text in enumerate(bullets):
        y = 615 + i * 44
        draw.ellipse((950, y + 8, 962, y + 20), fill=AMBER)
        draw.text((980, y), text, font=font(18), fill=INK)
    draw.text((950, 825), "中国南方 pending_review；P/R/F1 待 P5 标注", font=font(17), fill=RED)

    # bottom strip
    draw.rounded_rectangle((80, 900, 1840, 965), radius=14, fill="#10251A", outline="#2F5D43", width=1)
    draw.text((110, 932), "样例 481   |   全量 106,393   |   100 条抽样框   |   P/R/F1 待 P5",
              font=font(21, True), fill=NEON_SOFT, anchor="lm")
    image.save(OUT / "slide3_quality_boundary.png", quality=95)


if __name__ == "__main__":
    slide1()
    slide2()
    slide3()
    print("written", *[str(p) for p in sorted(OUT.glob("slide*.png"))], sep="\n")
