"""P1-3: build patent_ipc / patent_topic / patent_efficacy and representatives.

Reads the merged raw workbook once, keeps only rows whose public number is a
representative patent_id from patents.parquet, then writes:
- data/processed/patent_ipc.parquet
- data/processed/patent_topic.parquet
- data/processed/patent_efficacy.parquet
- data/results/representatives.parquet (for P1-4 citations/cooperation)
- data/results/tech_counts.json
"""
import argparse
import json
import re
import shutil
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from core import config

RAW_FILE = config.DATA_DIR / "raw" / "原始专利汇总.xlsx"
SAMPLE_RAW = config.RESULTS_DIR / "raw_sample_1000.parquet"
PATENTS_FULL = config.PROCESSED_DIR / "patents.parquet"
PATENTS_SAMPLE = config.RESULTS_DIR / "_clean_sample" / "patents.parquet"
OUT_FULL = config.PROCESSED_DIR
OUT_SAMPLE = config.RESULTS_DIR / "_tech_sample"
DELIVERY_DIR = config.ROOT_DIR / "交付给同伴的内容" / "P1-3_技术识别"

KEYS = {
    "pid": "公开（公告）号", "appno": "申请号", "ptype": "专利类型",
    "country": "公开国别", "legal": "当前法律状态",
    "title": "标题 (中文)", "abstract": "摘要 (中文)",
    "appdate": "申请日", "pubdate": "公开（公告）日",
    "ipc_main": "IPC主分类", "ipc": "IPC", "cpc": "CPC",
    "eff_phrase": "技术功效短语", "eff1": "技术功效1级",
    "eff2": "技术功效2级", "eff3": "技术功效3级",
    "applicants": "申请人", "std_app": "标准化申请人",
    "app_country": "申请人国家/地区",
    "cite": "引证专利", "cited": "被引证专利", "cited_app": "被引证申请人",
    "cite_n": "引证次数", "cited_n": "被引证次数",
}

REP_COLUMNS = ["patent_id", "application_no", "title", "abstract", "apply_date",
               "pub_date", "patent_type", "country", "legal_status",
               "ipc_main", "ipc", "cpc", "eff_phrase", "eff1", "eff2", "eff3",
               "applicants_raw", "applicants_std", "applicant_country",
               "cites", "cited_by", "cited_applicants", "cite_count", "cited_count"]

IPC_DOMAIN = {
    "H01M": "动力电池", "H01G": "动力电池",
    "H02J": "充电设施",
    "H02K": "电驱动", "H02P": "电驱动",
    "B60L": "整车与能量管理", "B60W": "整车与能量管理", "B60T": "整车与能量管理",
    "B60K": "整车与能量管理", "B62D": "整车与能量管理", "B60R": "整车与能量管理",
    "B60H": "热管理",
    "G01R": "测试与安全",
    "G05B": "智能驾驶", "G06F": "智能驾驶", "G06Q": "智能驾驶", "G06N": "智能驾驶",
    "C01B": "材料与制造", "C01G": "材料与制造", "C22": "材料与制造",
    "H01B": "材料与制造",
}

IPC_FALLBACK = {
    "H01M": ("电池（未细分）", "动力电池"),
    "H02J": ("充电（未细分）", "充电设施"),
    "H02K": ("电机（未细分）", "电驱动"),
    "H02P": ("电机控制（未细分）", "电驱动"),
    "B60L": ("整车电控（未细分）", "整车与能量管理"),
    "B60K": ("整车动力（未细分）", "整车与能量管理"),
    "B60W": ("整车控制（未细分）", "整车与能量管理"),
    "B60H": ("热管理（未细分）", "热管理"),
    "G01R": ("测试（未细分）", "测试与安全"),
    "G05B": ("智能控制（未细分）", "智能驾驶"),
    "G06F": ("智能控制（未细分）", "智能驾驶"),
    "G06Q": ("智能控制（未细分）", "智能驾驶"),
}

TOPIC_RULES = [
    {"topic": "电池热管理", "domain": "动力电池",
     "keywords": ["电池热管理", "电池冷却", "电池加热", "液冷", "风冷", "冷板", "热管理"]},
    {"topic": "电池热失控", "domain": "动力电池",
     "keywords": ["热失控", "热蔓延", "热失控预警", "起火", "爆炸", "热扩散"]},
    {"topic": "电池均衡", "domain": "动力电池",
     "keywords": ["电池均衡", "均衡电路", "单体均衡", "均衡控制", "主动均衡", "被动均衡"]},
    {"topic": "电池成组与结构", "domain": "动力电池",
     "keywords": ["电池包", "电池模组", "电池箱", "成组", "刀片电池", "CTP", "结构件", "电池托盘"]},
    {"topic": "电池寿命与健康", "domain": "动力电池",
     "keywords": ["电池寿命", "健康状态", "SOH", "老化", "衰减", "循环寿命"]},
    {"topic": "电池安全", "domain": "动力电池",
     "keywords": ["电池安全", "短路保护", "过充保护", "过放保护", "防爆", "安全阀"]},
    {"topic": "电池检测与诊断", "domain": "动力电池",
     "keywords": ["电池检测", "电池诊断", "内阻检测", "绝缘检测", "故障诊断"]},
    {"topic": "固态电池", "domain": "动力电池",
     "keywords": ["固态电池", "固态电解质", "半固态", "全固态"]},
    {"topic": "磷酸铁锂", "domain": "动力电池",
     "keywords": ["磷酸铁锂", "LFP"]},
    {"topic": "三元电池", "domain": "动力电池",
     "keywords": ["三元", "NCM", "NCA", "高镍"]},
    {"topic": "钠离子电池", "domain": "动力电池",
     "keywords": ["钠离子", "钠电"]},
    {"topic": "电池回收与梯次利用", "domain": "动力电池",
     "keywords": ["电池回收", "梯次利用", "拆解", "再生", "退役电池"]},
    {"topic": "电池管理系统", "domain": "动力电池",
     "keywords": ["BMS", "电池管理系统", "SOC估算", "SOH估算", "电池管理"]},
    {"topic": "驱动电机", "domain": "电驱动",
     "keywords": ["驱动电机", "永磁电机", "异步电机", "轮毂电机", "电机"]},
    {"topic": "电机控制", "domain": "电驱动",
     "keywords": ["电机控制", "矢量控制", "逆变器", "电机控制器"]},
    {"topic": "电控与功率器件", "domain": "电驱动",
     "keywords": ["电控", "功率模块", "IGBT", "SiC", "碳化硅", "功率器件"]},
    {"topic": "减速器与传动", "domain": "电驱动",
     "keywords": ["减速器", "变速器", "传动系统", "差速器", "齿轮"]},
    {"topic": "无线充电", "domain": "充电设施",
     "keywords": ["无线充电", "非接触充电", "电磁感应充电", "无线能量传输"]},
    {"topic": "快速充电", "domain": "充电设施",
     "keywords": ["快充", "快速充电", "大功率充电", "超充"]},
    {"topic": "换电", "domain": "充电设施",
     "keywords": ["换电", "电池更换", "换电站", "快换"]},
    {"topic": "充电桩", "domain": "充电设施",
     "keywords": ["充电桩", "充电机", "充电设备", "充电枪", "充电接口"]},
    {"topic": "车网互动", "domain": "充电设施",
     "keywords": ["V2G", "车网互动", "有序充电", "需求响应", "峰谷"]},
    {"topic": "充电控制", "domain": "充电设施",
     "keywords": ["充电控制", "充电策略", "充电管理", "恒流恒压"]},
    {"topic": "整车控制", "domain": "整车与能量管理",
     "keywords": ["整车控制", "整车控制器", "VCU", "域控制器"]},
    {"topic": "能量管理", "domain": "整车与能量管理",
     "keywords": ["能量管理", "能量回收", "制动能量回收", "续航"]},
    {"topic": "轻量化", "domain": "整车与能量管理",
     "keywords": ["轻量化", "铝合金", "高强度钢", "碳纤维", "复合材料"]},
    {"topic": "整车结构", "domain": "整车与能量管理",
     "keywords": ["车身", "底盘", "车架", "悬架", "碰撞安全"]},
    {"topic": "整车热管理", "domain": "热管理",
     "keywords": ["整车热管理", "空调", "热泵", "乘员舱", "冷却回路"]},
    {"topic": "电机电控热管理", "domain": "热管理",
     "keywords": ["电机冷却", "电控冷却", "功率模块冷却"]},
    {"topic": "智能驾驶", "domain": "智能驾驶",
     "keywords": ["智能驾驶", "自动驾驶", "辅助驾驶", "ADAS", "无人驾驶"]},
    {"topic": "环境感知", "domain": "智能驾驶",
     "keywords": ["激光雷达", "毫米波雷达", "摄像头", "感知", "传感器融合"]},
    {"topic": "车规芯片", "domain": "智能驾驶",
     "keywords": ["车规级芯片", "车规芯片", "MCU", "SoC", "域控制芯片"]},
    {"topic": "智能座舱", "domain": "智能驾驶",
     "keywords": ["智能座舱", "人机交互", "语音控制", "车机"]},
    {"topic": "正极材料", "domain": "材料与制造",
     "keywords": ["正极材料", "三元材料", "磷酸铁锂材料", "高镍"]},
    {"topic": "负极材料", "domain": "材料与制造",
     "keywords": ["负极材料", "石墨", "硅碳", "硅负极"]},
    {"topic": "电解液", "domain": "材料与制造",
     "keywords": ["电解液", "添加剂", "溶剂"]},
    {"topic": "隔膜", "domain": "材料与制造",
     "keywords": ["隔膜", "涂层隔膜", "陶瓷隔膜"]},
    {"topic": "制造工艺", "domain": "材料与制造",
     "keywords": ["焊接", "涂布", "卷绕", "叠片", "装配", "制造工艺"]},
    {"topic": "测试与验证", "domain": "测试与安全",
     "keywords": ["测试台", "充放电测试", "循环测试", "台架试验", "测试方法"]},
    {"topic": "电磁兼容", "domain": "测试与安全",
     "keywords": ["电磁兼容", "EMC", "电磁干扰"]},
]


def s(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def split_multi(v) -> list[str]:
    return [x.strip() for x in re.split(r"[;；|]", s(v)) if x.strip()]


def iter_xlsx(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    ws.reset_dimensions()
    it = ws.iter_rows(values_only=True)
    header = [s(x) for x in next(it)]
    idx = {name: i for i, name in enumerate(header)}
    for row in it:
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        yield {k: (row[idx[name]] if name in idx and idx[name] < len(row) else None)
               for k, name in KEYS.items()}
    wb.close()


def iter_sample(path):
    df = pd.read_parquet(path)
    for rec in df.to_dict("records"):
        yield {k: rec.get(name) for k, name in KEYS.items()}


def make_rep(pid, rec, ptype, main):
    return {
        "patent_id": pid,
        "application_no": s(rec.get("appno")) or None,
        "title": s(rec.get("title")) or None,
        "abstract": s(rec.get("abstract")) or None,
        "apply_date": s(rec.get("appdate")) or None,
        "pub_date": s(rec.get("pubdate")) or None,
        "patent_type": ptype or None,
        "country": s(rec.get("country")) or None,
        "legal_status": s(rec.get("legal")) or None,
        "ipc_main": main or None,
        "ipc": s(rec.get("ipc")) or None,
        "cpc": s(rec.get("cpc")) or None,
        "eff_phrase": s(rec.get("eff_phrase")) or None,
        "eff1": s(rec.get("eff1")) or None,
        "eff2": s(rec.get("eff2")) or None,
        "eff3": s(rec.get("eff3")) or None,
        "applicants_raw": s(rec.get("applicants")) or None,
        "applicants_std": s(rec.get("std_app")) or None,
        "applicant_country": s(rec.get("app_country")) or None,
        "cites": s(rec.get("cite")) or None,
        "cited_by": s(rec.get("cited")) or None,
        "cited_applicants": s(rec.get("cited_app")) or None,
        "cite_count": s(rec.get("cite_n")) or None,
        "cited_count": s(rec.get("cited_n")) or None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    raw_source = SAMPLE_RAW if args.sample else RAW_FILE
    patents_path = PATENTS_SAMPLE if args.sample else PATENTS_FULL
    if not raw_source.is_file():
        raise SystemExit(f"missing raw: {raw_source}")
    if not patents_path.is_file():
        raise SystemExit(f"missing patents: {patents_path}")

    patents = pd.read_parquet(patents_path)
    want = set(patents["patent_id"].astype(str))
    ptype_map = dict(zip(patents["patent_id"].astype(str), patents["patent_type"].fillna("")))

    reps = {}
    for rec in (iter_sample(raw_source) if args.sample else iter_xlsx(raw_source)):
        pid = s(rec.get("pid"))
        if pid in want and pid not in reps:
            reps[pid] = rec
        if len(reps) == len(want):
            break
    missing = want - set(reps)

    ipc_rows = []
    topic_rows = []
    eff_rows = []
    rep_rows = []
    patents_with_ipc = set()
    patents_with_topic = set()
    patents_with_eff = set()
    topic_counter = Counter()
    domain_counter = Counter()
    topic_keyword_rows = 0
    topic_fallback_rows = 0
    designs_skipped = 0
    ipc_codes = set()

    for pid in want:
        rec = reps.get(pid)
        if not rec:
            continue
        ptype = s(rec.get("ptype")) or ptype_map.get(pid, "")
        main = s(rec.get("ipc_main")).upper().strip()
        rep = make_rep(pid, rec, ptype, main)
        if ptype == "外观设计":
            rep_rows.append(rep)
            designs_skipped += 1
            continue

        codes = [c.strip().upper() for c in re.split(r"[;；]", s(rec.get("ipc"))) if c.strip()]
        if main and main not in codes:
            codes.insert(0, main)
        seen_codes = set()
        for c in codes:
            if c in seen_codes:
                continue
            seen_codes.add(c)
            ipc_rows.append((pid, c, c == main))
            ipc_codes.add(c)
            patents_with_ipc.add(pid)

        text = " ".join([
            s(rec.get("title")), s(rec.get("abstract")), s(rec.get("eff_phrase")),
            s(rec.get("eff1")), s(rec.get("eff2")), s(rec.get("eff3")),
        ]).lower()
        hits = []
        for rule in TOPIC_RULES:
            matched = [kw for kw in rule["keywords"] if kw.lower() in text]
            if matched:
                score = sum(len(kw) for kw in matched)
                hits.append((score, rule))
        hits.sort(key=lambda x: (-x[0], x[1]["topic"]))
        chosen = hits[:3]
        if chosen:
            for _, rule in chosen:
                topic_rows.append((pid, rule["topic"], rule["domain"]))
                topic_counter[rule["topic"]] += 1
                domain_counter[rule["domain"]] += 1
                topic_keyword_rows += 1
            patents_with_topic.add(pid)
        else:
            base = (main[:4] if len(main) >= 4 else (codes[0][:4] if codes else ""))
            fb = IPC_FALLBACK.get(base)
            if fb:
                topic, domain = fb
                topic_rows.append((pid, topic, domain))
                topic_counter[topic] += 1
                domain_counter[domain] += 1
                topic_fallback_rows += 1
                patents_with_topic.add(pid)

        l1 = split_multi(rec.get("eff1"))
        l2 = split_multi(rec.get("eff2"))
        l3 = split_multi(rec.get("eff3"))
        if not (l1 or l2 or l3):
            l3 = split_multi(rec.get("eff_phrase"))
        seen_eff = set()
        for i in range(max(len(l1), len(l2), len(l3))):
            a = l1[i] if i < len(l1) else None
            b = l2[i] if i < len(l2) else None
            c = l3[i] if i < len(l3) else None
            if not any((a, b, c)):
                continue
            key = (a, b, c)
            if key in seen_eff:
                continue
            seen_eff.add(key)
            eff_rows.append((pid, a, b, c))
            patents_with_eff.add(pid)

        rep_rows.append(rep)

    ipc_df = pd.DataFrame(ipc_rows, columns=["patent_id", "ipc_code", "is_main"])
    for col in ["patent_id", "ipc_code"]:
        ipc_df[col] = ipc_df[col].astype("string")
    ipc_df["is_main"] = ipc_df["is_main"].astype("boolean")

    topic_df = pd.DataFrame(topic_rows, columns=["patent_id", "topic", "domain"])
    for col in ["patent_id", "topic", "domain"]:
        topic_df[col] = topic_df[col].astype("string")

    eff_df = pd.DataFrame(eff_rows, columns=["patent_id", "efficacy_l1", "efficacy_l2", "efficacy_l3"])
    for col in ["patent_id", "efficacy_l1", "efficacy_l2", "efficacy_l3"]:
        eff_df[col] = eff_df[col].astype("string")

    rep_df = pd.DataFrame(rep_rows, columns=REP_COLUMNS)

    if args.sample:
        out_dir = OUT_SAMPLE
        counts_path = config.RESULTS_DIR / "tech_counts_sample.json"
        reps_path = out_dir / "representatives.parquet"
    else:
        out_dir = OUT_FULL
        counts_path = config.RESULTS_DIR / "tech_counts.json"
        reps_path = config.RESULTS_DIR / "representatives.parquet"

    out_dir.mkdir(parents=True, exist_ok=True)
    ipc_df.to_parquet(out_dir / "patent_ipc.parquet", index=False)
    topic_df.to_parquet(out_dir / "patent_topic.parquet", index=False)
    eff_df.to_parquet(out_dir / "patent_efficacy.parquet", index=False)
    rep_df.to_parquet(reps_path, index=False)

    total = len(patents)
    counts = {
        "source": str(raw_source),
        "sample_mode": args.sample,
        "patents": total,
        "representatives_matched": len(reps),
        "missing_representatives": len(missing),
        "designs_skipped": designs_skipped,
        "patent_ipc_rows": len(ipc_df),
        "patents_with_ipc": len(patents_with_ipc),
        "ipc_coverage": round(len(patents_with_ipc) / max(total - designs_skipped, 1), 4),
        "unique_ipc": len(ipc_codes),
        "patent_topic_rows": len(topic_df),
        "patents_with_topic": len(patents_with_topic),
        "topic_coverage": round(len(patents_with_topic) / max(total - designs_skipped, 1), 4),
        "topic_keyword_rows": topic_keyword_rows,
        "topic_fallback_rows": topic_fallback_rows,
        "topics": dict(topic_counter.most_common(50)),
        "domains": dict(domain_counter.most_common()),
        "patent_efficacy_rows": len(eff_df),
        "patents_with_efficacy": len(patents_with_eff),
        "efficacy_coverage": round(len(patents_with_eff) / max(total - designs_skipped, 1), 4),
        "representatives_path": str(reps_path),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    counts_path.write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.sample:
        DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("patent_ipc.parquet", "patent_topic.parquet", "patent_efficacy.parquet"):
            shutil.copy2(out_dir / name, DELIVERY_DIR / name)
        shutil.copy2(counts_path, DELIVERY_DIR / "tech_counts.json")
        top_topics = "\n".join(
            f"| {k} | {v:,} |" for k, v in topic_counter.most_common(15)
        )
        readme = f"""# P1-3 技术识别

生成时间：{datetime.now().isoformat(timespec='seconds')}
来源：`{RAW_FILE.name}`；按 `data/processed/patents.parquet` 的 `patent_id` 取代表记录。

## 文件

| 文件 | 行 × 列 | 说明 |
|---|---|---|
| `patent_ipc.parquet` | {len(ipc_df):,} × 3 | 专利—IPC 关系，`is_main` 标主分类 |
| `patent_topic.parquet` | {len(topic_df):,} × 3 | 专利—技术主题—领域 |
| `patent_efficacy.parquet` | {len(eff_df):,} × 4 | 技术功效 1/2/3 级 |
| `tech_counts.json` | — | 覆盖率与主题分布 |

## 口径

- 外观设计不写 IPC/主题/功效；非外观设计缺字段时留空行，不伪造。
- IPC 按 `;` 拆分，主分类不在列表时补入并标 `is_main=True`。
- 主题优先用关键词词典（标题+摘要+功效），最多 3 个；无命中时按主 IPC 给一个 `（未细分）` 兜底主题。
- 功效按 `技术功效1/2/3级` 拆分；三级全空时用 `技术功效短语` 兜底到三级。
- 一个专利可以有多条 IPC/主题/功效；统计时注意去重。

## 覆盖率

- IPC：{len(patents_with_ipc):,} / {total - designs_skipped:,} 非外观设计（{counts['ipc_coverage']*100:.1f}%）
- 主题：{len(patents_with_topic):,}（{counts['topic_coverage']*100:.1f}%）；其中关键词命中 {topic_keyword_rows:,} 行，兜底 {topic_fallback_rows:,} 行
- 功效：{len(patents_with_eff):,}（{counts['efficacy_coverage']*100:.1f}%）

## Top 主题

| 主题 | 行数 |
|---|---:|
{top_topics}

## 局限

- 主题词典是人工规则，不是标准分类；`（未细分）` 是 IPC 兜底，不是细粒度主题。
- `电机`、`热管理` 等宽泛关键词可能造成主题过匹配，P1-8 抽样时会调整。
- 同一专利最多 3 个主题，主题行数会大于专利数。
- 申请人/引用/合作不在本步；`representatives.parquet` 仅供 P1-4 内部使用。
"""
        (DELIVERY_DIR / "说明.md").write_text(readme, encoding="utf-8")

    print("written", out_dir, reps_path, counts_path)
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print("missing representatives", len(missing), "elapsed", counts["elapsed_sec"])


if __name__ == "__main__":
    main()
