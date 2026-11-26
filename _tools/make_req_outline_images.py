"""Generate diagrams for the P1 outline aligned with assignment items 2/3/4.

Each figure is written twice:
- <name>.png        dark preview, readable in Markdown/Word
- <name>_alpha.png  transparent background, for the dark PPT
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "交付给同伴的内容" / "P1-9_文档与交接" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

INK = (242, 255, 248, 255)
MUTED = (190, 212, 201, 255)
DIM = (145, 170, 157, 255)
GREEN = (184, 251, 135, 255)
NEON = (57, 255, 136, 255)
AMBER = (251, 191, 36, 255)
BLUE = (125, 211, 252, 255)
ORANGE = (251, 146, 60, 255)
RED = (251, 113, 133, 255)

CARD = (10, 24, 17, 245)
CARD2 = (14, 34, 24, 245)
BORDER = (64, 112, 82, 255)
GRID = (34, 58, 44, 255)
DARK = (9, 17, 13, 255)

FONT_DIR = Path("C:/Windows/Fonts")
_font_cache = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(
            str(FONT_DIR / ("msyhbd.ttc" if bold else "msyh.ttc")), size
        )
    return _font_cache[key]


def text(draw, xy, value, size, fill=INK, bold=False, anchor="la", spacing=10,
         align="left"):
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, anchor=anchor,
                        spacing=spacing, align=align, stroke_width=1,
                        stroke_fill=(0, 0, 0, 190))


def tw(draw, value, size, bold=False):
    box = draw.textbbox((0, 0), value, font=font(size, bold))
    return box[2] - box[0], box[3] - box[1]


def wrap(draw, value, size, max_width, bold=False):
    lines = []
    for raw in value.split("\n"):
        if not raw:
            lines.append("")
            continue
        line = ""
        for ch in raw:
            candidate = line + ch
            if tw(draw, candidate, size, bold)[0] <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = ch
        if line:
            lines.append(line)
    return "\n".join(lines)


def rounded(draw, box, fill=CARD, outline=BORDER, radius=20, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def node(draw, box, title, pk, attrs, accent=GREEN, title_size=46, attr_size=29):
    x0, y0, x1, y1 = box
    rounded(draw, box, fill=CARD, outline=accent, radius=22, width=3)
    text(draw, (x0 + 26, y0 + 22), title, title_size, INK, bold=True)
    text(draw, (x0 + 26, y0 + 22 + title_size + 12), pk, attr_size, accent, bold=True)
    y = y0 + 22 + title_size + 12 + attr_size + 16
    for item in attrs:
        if y + attr_size > y1 - 12:
            break
        text(draw, (x0 + 26, y), item, attr_size, MUTED)
        y += attr_size + 12


def arrow(draw, start, end, color=NEON, width=4, head=18):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - head * math.cos(angle - 0.55), y2 - head * math.sin(angle - 0.55))
    p2 = (x2 - head * math.cos(angle + 0.55), y2 - head * math.sin(angle + 0.55))
    draw.polygon([(x2, y2), p1, p2], fill=color)


def label(draw, xy, value, size=24, fill=GREEN, bold=True, pad=8):
    w, h = tw(draw, value, size, bold)
    x, y = xy
    draw.rounded_rectangle((x - pad, y - pad, x + w + pad, y + h + pad),
                           radius=8, fill=(6, 14, 10, 235),
                           outline=(58, 92, 70, 255), width=1)
    text(draw, (x, y), value, size, fill, bold=bold)


def loop_right(draw, x0, y1, y2, out_x, color=NEON, width=4):
    """Rectangular self-loop attached to the left edge of a node."""
    draw.line([(x0, y1), (out_x, y1), (out_x, y2), (x0, y2)],
              fill=color, width=width, joint="curve")
    arrow(draw, (out_x + 1, y2), (x0 - 1, y2), color=color, width=width, head=16)


def loop_down(draw, x1, x2, y0, out_y, color=NEON, width=4):
    """Rectangular self-loop attached to the top edge of a node."""
    draw.line([(x1, y0), (x1, out_y), (x2, out_y), (x2, y0)],
              fill=color, width=width, joint="curve")
    arrow(draw, (x2, out_y + 1), (x2, y0 - 1), color=color, width=width, head=16)


def save_pair(image, name):
    image.save(OUT / f"{name}_alpha.png")
    bg = Image.new("RGBA", image.size, DARK)
    bg.alpha_composite(image)
    bg.convert("RGB").save(OUT / f"{name}.png")
    print(name, image.size)


def schema_ontology():
    W, H = 1800, 1220
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    text(draw, (76, 48), "5 类实体 · 6 类关系 · 括号内为唯一键", 30, INK, bold=True)
    text(draw, (1250, 48), "Neo4j: 147,174 节点 / 571,663 关系", 25, MUTED)

    applicant = (80, 300, 500, 690)
    patent = (650, 340, 1150, 790)
    ipc = (1290, 110, 1700, 380)
    tech = (1260, 490, 1710, 810)
    domain = (1290, 860, 1700, 1070)

    node(draw, applicant, "Applicant 申请人", "name（唯一键）",
         ["raw_names", "type", "country"], accent=GREEN)
    node(draw, patent, "Patent 专利", "patent_id（唯一键）",
         ["title / abstract", "apply_date / apply_year", "pub_date / patent_type",
          "country / legal_status", "is_in_sample"], accent=BLUE)
    node(draw, ipc, "IPC 分类", "code（唯一键）", ["name", "level"], accent=ORANGE)
    node(draw, tech, "Technology 技术主题", "name（唯一键）",
         ["keywords", "description"], accent=GREEN)
    node(draw, domain, "Domain 技术领域", "name（唯一键）",
         ["description"], accent=ORANGE)

    arrow(draw, (500, 500), (650, 500))
    label(draw, (505, 438), "APPLIES_FOR", 21)

    arrow(draw, (1120, 390), (1320, 310))
    label(draw, (1128, 322), "HAS_IPC", 21)

    arrow(draw, (1150, 620), (1260, 620))
    label(draw, (1144, 646), "INVOLVES", 21)

    arrow(draw, (1490, 810), (1490, 860))
    label(draw, (1504, 816), "BELONGS_TO", 21)

    loop_down(draw, 800, 1000, 340, 230)
    label(draw, (840, 180), "CITES  引用方 → 被引方", 24, AMBER)

    loop_right(draw, 80, 420, 560, 18)
    label(draw, (80, 712), "CO_APPLIED_WITH {weight}", 21, AMBER)
    text(draw, (80, 750), "同类型实体间；逻辑无向，存一条", 20, MUTED)

    text(draw, (76, 1100),
         "箭头 = 语义方向；属性未在源表出现的留空，不伪造。",
         24, MUTED)
    save_pair(image, "req2_schema_ontology")


def schema_map():
    """Compact schema map for a slide: entities, keys, 3-5 attributes, directions."""
    W, H = 1800, 1000
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    text(draw, (76, 44), "5 类实体 · 6 类关系 · 括号内为唯一键", 31, INK, bold=True)
    text(draw, (1200, 44), "图谱：147,174 节点 / 571,663 关系", 25, MUTED)

    applicant = (80, 300, 520, 640)
    patent = (680, 280, 1180, 730)
    ipc = (1300, 100, 1720, 330)
    tech = (1280, 420, 1720, 700)
    domain = (1300, 780, 1720, 970)

    node(draw, applicant, "Applicant 申请人", "name（唯一键）",
         ["raw_names", "type"], accent=GREEN, title_size=44, attr_size=31)
    node(draw, patent, "Patent 专利", "patent_id（唯一键）",
         ["title / abstract", "apply_year", "patent_type", "legal_status",
          "is_in_sample"], accent=BLUE, title_size=44, attr_size=31)
    node(draw, ipc, "IPC 分类", "code（唯一键）", ["name", "level"],
         accent=ORANGE, title_size=44, attr_size=31)
    node(draw, tech, "Technology 技术主题", "name（唯一键）",
         ["keywords", "description"], accent=GREEN, title_size=44, attr_size=31)
    node(draw, domain, "Domain 技术领域", "name（唯一键）", ["description"],
         accent=ORANGE, title_size=44, attr_size=31)

    arrow(draw, (520, 470), (680, 470))
    label(draw, (532, 430), "APPLIES_FOR", 22)

    arrow(draw, (1130, 330), (1340, 270))
    label(draw, (1136, 242), "HAS_IPC", 22)

    arrow(draw, (1180, 560), (1280, 560))
    label(draw, (1152, 590), "INVOLVES", 22)

    arrow(draw, (1500, 700), (1500, 780))
    label(draw, (1512, 726), "BELONGS_TO", 22)

    loop_down(draw, 820, 1040, 280, 180)
    label(draw, (856, 128), "CITES  引用方 → 被引方", 24, AMBER)

    loop_right(draw, 80, 340, 470, 18)
    label(draw, (80, 660), "CO_APPLIED_WITH {weight}", 21, AMBER)
    text(draw, (80, 696), "同类型实体间；逻辑无向，存一条", 20, MUTED)

    text(draw, (76, 920),
         "箭头 = 语义方向；关键属性见表；源表没有的属性留空，不伪造。",
         24, MUTED)
    save_pair(image, "req2_schema_map")


def schema_iterations():
    W, H = 1800, 540
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line((80, 260, 1720, 260), fill=(48, 82, 62, 255), width=5)

    cards = [
        ("V1", "基础层", ["+ Patent / Applicant / IPC",
                          "+ APPLIES_FOR / CITES",
                          "+ HAS_IPC"],
         "专利检索与引用查询"),
        ("V2", "主题层", ["+ Technology / Domain",
                          "+ INVOLVES / BELONGS_TO"],
         "主题识别与领域多跳"),
        ("V3", "网络层", ["+ CO_APPLIED_WITH",
                          "+ weight（共同专利数）"],
         "合作网络与中心性"),
        ("V4", "问答层", ["+ is_in_sample",
                          "+ 预计算指标 / 别名表"],
         "样本区分与实体链接"),
    ]
    xs = [80, 500, 920, 1340]
    for i, (ver, stage, lines, trigger) in enumerate(cards):
        x = xs[i]
        rounded(draw, (x, 70, x + 380, 430), fill=CARD2, outline=BORDER, radius=18)
        text(draw, (x + 24, 94), ver, 36, GREEN, bold=True)
        text(draw, (x + 94, 98), stage, 29, INK, bold=True)
        y = 166
        for line in lines:
            text(draw, (x + 24, y), line, 23, MUTED)
            y += 34
        text(draw, (x + 24, 338), "触发：" + trigger, 21, AMBER)
    for x in (460, 880, 1300):
        arrow(draw, (x, 260), (x + 36, 260), color=NEON, width=4, head=14)
    text(draw, (80, 470),
         "每次迭代均由能力问题触发；实体、关系、属性变更同步到七表结构与 Neo4j Schema。",
         24, MUTED)
    save_pair(image, "req2_schema_iterations")


def data_pipeline():
    W, H = 1800, 560
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    boxes = [
        ("01 来源", "incoPat 导出",
         ["16 个 xlsx", "2025-08-07/08", "142,112 行 × 204 列"]),
        ("02 探查", "重复 / 缺失 / 异常",
         ["公开号重复 46 行", "申请号重复 35,719 行", "缺失 / 日期异常已记录"]),
        ("03 清洗", "按申请号去重",
         ["代表公开优先：", "授权 > 申请 >", "实用新型 > 外观", "删除非主文献 3,668 行"]),
        ("04 建表", "七张表",
         ["106,393 件专利", "applicants 115,927", "IPC 306,023",
          "主题 104,723", "功效 391,642"]),
        ("05 校验", "34 / 34 PASS",
         ["0 悬空编号", "0 重复边", "0 主表重复"]),
    ]
    xs = [40, 390, 740, 1090, 1440]
    for i, (step, title, lines) in enumerate(boxes):
        x = xs[i]
        rounded(draw, (x, 70, x + 310, 430), fill=CARD, outline=BORDER, radius=18)
        text(draw, (x + 22, 92), step, 21, GREEN, bold=True)
        text(draw, (x + 22, 130), title, 27, INK, bold=True)
        y = 198
        for line in lines:
            text(draw, (x + 22, y), line, 20, MUTED)
            y += 44
        if i < 4:
            arrow(draw, (x + 312, 250), (xs[i + 1] - 4, 250), color=NEON, width=4, head=14)
    text(draw, (40, 480),
         "数据边界：16 批次按法律状态分层导出，不是随机全量；2024—2025 不完整；外观设计不进入技术表。",
         23, AMBER)
    save_pair(image, "req3_data_pipeline")


def bar(draw, x, y, w, h, ratio, color=GREEN, bg=(24, 44, 32, 255)):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=bg)
    fill_w = max(4, int(w * ratio))
    draw.rounded_rectangle((x, y, x + fill_w, y + h), radius=8, fill=color)


def quality_chart():
    W, H = 1800, 720
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    text(draw, (60, 50), "规模收敛", 32, INK, bold=True)
    rows = [
        ("原始记录", 142112, 142112, "142,112 行"),
        ("去重后专利", 106393, 142112, "106,393 件"),
        ("技术类专利", 86814, 142112, "86,814 件"),
    ]
    y = 130
    for name, value, maximum, caption in rows:
        text(draw, (60, y), name, 24, MUTED)
        bar(draw, 250, y - 4, 470, 52, value / maximum,
            color=GREEN if value != 86814 else BLUE)
        text(draw, (738, y), caption, 24, INK, bold=True)
        y += 92
    text(draw, (60, 430),
         "去重减少 35,719 行（25.1%）；\n保留代表公开，避免同一申请重复计数。",
         22, MUTED, spacing=8)

    text(draw, (900, 50), "字段覆盖（分母：技术类专利 86,814）", 32, INK, bold=True)
    cover = [
        ("IPC", 0.990, "99.0%", GREEN),
        ("技术主题", 0.8235, "82.35%", GREEN),
        ("技术功效", 0.8941, "89.41%", GREEN),
        ("样本内引用", 0.0793, "7.93%", AMBER),
        ("外部主体", 0.0390, "3.90%", ORANGE),
    ]
    y = 130
    for name, ratio, caption, color in cover:
        text(draw, (900, y), name, 24, MUTED)
        bar(draw, 1060, y - 4, 440, 40, ratio, color=color)
        text(draw, (1516, y - 2), caption, 24, INK, bold=True)
        y += 78
    text(draw, (900, 560),
         "引用两项分母为 442,917 条引用边，\n不与字段覆盖率同轴比较。",
         22, MUTED, spacing=8)
    save_pair(image, "req3_quality_chart")


def extraction_fusion():
    W, H = 1800, 760
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cols = [
        ("实体识别", "结构化字段 + 规则词典", [
            "Patent：公开号/申请号",
            "Applicant：申请人拆分",
            "IPC：分类号拆分",
            "Technology：关键词规则",
            "Domain：IPC 映射",
        ], BLUE),
        ("关系抽取", "字段映射 + 引用解析", [
            "APPLIES_FOR ← 申请人",
            "CITES ← 引证专利",
            "HAS_IPC ← IPC 字段",
            "INVOLVES ← 主题命中",
            "BELONGS_TO ← 领域词典",
            "CO_APPLIED_WITH ← 共同申请",
        ], GREEN),
        ("属性抽取", "分层字段 + 关键词", [
            "专利：10 个属性",
            "功效：L1/L2/L3",
            "主题：最多 3 个",
            "日期/法律状态/国别",
            "缺失属性留空",
        ], ORANGE),
        ("融合归一", "去重 + 别名 + 抽样", [
            "按申请号去重",
            "393 条别名",
            "覆盖 9,151 件专利",
            "27,190 个企业主体",
            "合作边 9,826 → 9,750",
            "100 条分层抽样",
        ], AMBER),
    ]
    xs = [40, 480, 920, 1360]
    for i, (head, sub, items, accent) in enumerate(cols):
        x = xs[i]
        rounded(draw, (x, 70, x + 360, 630), fill=CARD, outline=accent, radius=18)
        text(draw, (x + 24, 92), head, 34, INK, bold=True)
        text(draw, (x + 24, 142), sub, 21, accent, bold=True)
        y = 198
        for item in items:
            text(draw, (x + 24, y), "• " + item, 20, MUTED)
            y += 60
        if i < 3:
            arrow(draw, (x + 362, 350), (xs[i + 1] - 4, 350), color=NEON, width=4, head=14)
    text(draw, (40, 686),
         "方法选择：规则 / 词典可复现、可逐条追溯；未使用不可解释的黑箱抽取。",
         24, MUTED)
    save_pair(image, "req4_extraction_fusion")


def eval_results():
    W, H = 1800, 800
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    text(draw, (60, 36), "100 条人工核对结果", 34, INK, bold=True)

    text(draw, (60, 100), "字段准确率（0.5 按半分）", 27, MUTED, bold=True)
    rows = [
        ("申请人", 1.0, "100%"),
        ("IPC", 1.0, "100%"),
        ("技术功效", 1.0, "100%"),
        ("引用（一致性）", 1.0, "100%"),
        ("合作（n=9）", 1.0, "100%"),
        ("技术主题", 0.675, "67.5%"),
    ]
    y = 160
    for name, ratio, caption in rows:
        text(draw, (60, y), name, 24, MUTED)
        bar(draw, 300, y - 2, 470, 38, ratio,
            color=GREEN if ratio >= 0.999 else AMBER)
        text(draw, (790, y - 2), caption, 24,
             GREEN if ratio >= 0.999 else AMBER, bold=True)
        y += 78

    text(draw, (1060, 100), "技术主题标注分布", 27, MUTED, bold=True)
    # stacked bar: 50 correct / 35 partial / 15 wrong
    x0, y0, width, height = 1060, 160, 600, 56
    parts = [(0.50, GREEN, "正确 50"), (0.35, AMBER, "部分 35"), (0.15, RED, "错误 15")]
    x = x0
    for ratio, color, label_text in parts:
        w = int(width * ratio)
        draw.rectangle((x, y0, x + w, y0 + height), fill=color)
        text(draw, (x + 10, y0 + 14), label_text, 18, (5, 12, 8, 255), bold=True)
        x += w
    text(draw, (1060, 246),
         "主题准确率 67.5%；非外观设计 60.4%",
         26, INK, bold=True)
    text(draw, (1060, 300),
         "18 条外观设计无主题，按正确计；\n主题规则是主要误差来源。",
         21, MUTED, spacing=7)
    text(draw, (1060, 390),
         "主要问题：兜底过粗、宽泛词误命中、\n空主题漏检；见 notes 列。",
         21, MUTED, spacing=7)
    text(draw, (1060, 500),
         "主题 P/R/F1（micro）= 61.1 / 61.7 / 61.4",
         22, GREEN, bold=True)
    text(draw, (1060, 540),
         "领域 P/R/F1（micro）= 66.7 / 68.1 / 67.4",
         22, GREEN, bold=True)
    text(draw, (1060, 586),
         "引用 418/418 一致；结构化字段\n只做一致性检查，不计算 P/R/F1。",
         20, MUTED, spacing=6)
    text(draw, (1060, 650),
         "合作：9 条多申请人全部覆盖；\n91 条单申请人无共同申请对。",
         20, MUTED, spacing=6)

    text(draw, (60, 728),
         "结论：结构化字段抽样未发现错误；主题规则需继续补充词典与负向规则。",
         23, MUTED)
    save_pair(image, "req4_eval_results")


def eval_results_200():
    W, H = 1800, 800
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    text(draw, (80, 48), "技术主题抽取结果（200 条抽检）", 34, INK, bold=True)
    text(draw, (1280, 54), "200 条独立随机样本", 23, MUTED)

    cards = [
        ("Precision", "71.43%", GREEN),
        ("Recall", "63.88%", BLUE),
        ("F1", "67.44%", AMBER),
    ]
    for i, (label, value, color) in enumerate(cards):
        x = 80 + i * 560
        rounded(draw, (x, 170, x + 480, 430), fill=CARD2, outline=color, radius=20, width=3)
        text(draw, (x + 32, 200), label, 28, MUTED)
        text(draw, (x + 32, 255), value, 72, color, bold=True)
        text(draw, (x + 32, 360), "主题级", 24, MUTED)

    rounded(draw, (80, 500, 1720, 650), fill=CARD, outline=BORDER, radius=18)
    text(draw, (110, 520), "领域级 F1", 28, MUTED)
    text(draw, (110, 560), "72.93%", 52, GREEN, bold=True)
    bar(draw, 520, 565, 1090, 34, 0.7293, color=GREEN)
    text(draw, (1630, 565), "72.93%", 24, GREEN, bold=True)

    text(draw, (80, 700),
         "主要误差：兜底主题过粗、宽泛词误命中、细粒度主题漏检。",
         24, MUTED)
    save_pair(image, "req4_eval_results")


def eval_results_200_bar():
    W, H = 1800, 800
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    text(draw, (80, 48), "技术主题标注分布（200 条抽检）", 34, INK, bold=True)
    text(draw, (1320, 54), "200 条随机抽检", 23, MUTED)

    x0, y0, width, height = 80, 170, 1640, 96
    parts = [(117, GREEN, "正确 117"), (42, AMBER, "部分 42"), (41, RED, "错误 41")]
    x = x0
    for n, color, label_text in parts:
        w = int(width * n / 200)
        draw.rectangle((x, y0, x + w, y0 + height), fill=color)
        text(draw, (x + 18, y0 + 30), label_text, 26, (5, 12, 8, 255), bold=True)
        x += w

    text(draw, (80, 310), "69.0% 主题得分", 52, AMBER, bold=True)
    text(draw, (620, 322), "|", 40, MUTED)
    text(draw, (670, 310), "非外观设计 61.7%", 42, INK, bold=True)
    text(draw, (80, 400), "200 条随机抽检；主题得分按 1 / 0.5 / 0 计算。", 23, MUTED)

    rounded(draw, (80, 500, 1720, 640), fill=CARD, outline=BORDER, radius=18)
    text(draw, (110, 522), "主要误差", 26, GREEN, bold=True)
    text(draw, (110, 568),
         "兜底主题过粗、宽泛词误命中、细粒度主题漏检。",
         25, MUTED)
    text(draw, (110, 612),
         "FP：整车电控（未细分）15、驱动电机 14；FN：充电控制 12、整车控制 12。",
         21, MUTED)

    text(draw, (80, 700),
         "申请人、IPC、功效、引用为结构化字段，抽样一致。",
         23, MUTED)
    save_pair(image, "req4_eval_results")


def eval_framework():
    W, H = 1800, 820
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    text(draw, (60, 36), "100 条分层抽样：核对对象与指标", 32, INK, bold=True)

    table_x, table_y = 60, 96
    widths = [220, 550, 200]
    row_h = 68
    headers = ["核对对象", "判定标准", "指标"]
    x = table_x
    for head, cw in zip(headers, widths):
        draw.rectangle((x, table_y, x + cw, table_y + row_h), fill=(20, 42, 30, 255),
                       outline=BORDER, width=1)
        text(draw, (x + 18, table_y + 20), head, 23, GREEN, bold=True)
        x += cw
    rows = [
        ("申请人", "拆分、去后缀、去重后与原文一致", "Accuracy"),
        ("IPC", "主 IPC 与原文一致", "Accuracy"),
        ("技术主题", "过匹配 / 漏匹配 / 兜底是否合理", "P / R / F1"),
        ("技术功效", "三级功效是否对应原文", "Accuracy"),
        ("引用", "引用方向与数量是否与原文一致", "一致率"),
        ("合作", "共同申请人配对是否正确", "覆盖率"),
    ]
    y = table_y + row_h
    for i, (obj, rule, metric) in enumerate(rows):
        x = table_x
        fill = (12, 28, 20, 255) if i % 2 == 0 else (9, 22, 16, 255)
        for value, cw in zip((obj, rule, metric), widths):
            draw.rectangle((x, y, x + cw, y + row_h), fill=fill, outline=BORDER, width=1)
            text(draw, (x + 18, y + 18), wrap(draw, value, 20, cw - 32), 20,
                 INK if value != metric else AMBER)
            x += cw
        y += row_h

    rx = 1140
    rounded(draw, (rx, 96, 1740, 560), fill=CARD2, outline=BORDER, radius=18)
    text(draw, (rx + 28, 118), "抽样构成", 28, INK, bold=True)
    strata = [("发明授权", 40), ("实用新型", 23), ("发明申请", 19), ("外观设计", 18)]
    y = 176
    for name, n in strata:
        text(draw, (rx + 28, y), name, 22, MUTED)
        bar(draw, rx + 190, y + 2, 250, 26, n / 40, color=GREEN if n == 40 else BLUE)
        text(draw, (rx + 456, y - 4), str(n), 22, INK, bold=True)
        y += 52
    text(draw, (rx + 28, 402),
         "边界样本：无 IPC、无主题、\n无功效、有引用、多申请人。",
         20, MUTED, spacing=7)
    text(draw, (rx + 28, 494), "标注：1 正确 / 0.5 部分 / 0 错误", 20, MUTED)

    rounded(draw, (60, 600, 1740, 690), fill=(34, 24, 8, 235), outline=(120, 82, 24, 255), radius=14)
    text(draw, (84, 620),
         "标注已完成：6 个 label_* 列已填；结果见 req4_eval_results.png。",
         24, AMBER, bold=True)
    text(draw, (60, 728),
         "Accuracy =（1×正确 + 0.5×部分）/ 已核对；主题按边计 P/R/F1；引用/合作做一致/覆盖检查。",
         22, MUTED)
    save_pair(image, "req4_eval_framework")


if __name__ == "__main__":
    schema_ontology()
    schema_map()
    schema_iterations()
    data_pipeline()
    quality_chart()
    extraction_fusion()
    eval_framework()
    eval_results_200_bar()
    print("written to", OUT)
