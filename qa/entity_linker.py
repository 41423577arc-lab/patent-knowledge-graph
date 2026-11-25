"""Resolve display entities to exact data-scope names or request clarification."""
from collections import defaultdict
from dataclasses import dataclass
import re
import unicodedata

from rapidfuzz import fuzz, process

from core.data_loader import load_table


def normalize(value):
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


@dataclass(frozen=True)
class Entity:
    name: str
    kind: str
    members: tuple[str, ...]

    @property
    def public(self):
        return {"id": f"{self.kind}:{self.name}", "name": self.name, "type": self.kind}


class Catalog:
    def __init__(self, slot, aliases):
        self.slot = slot
        self.kind = "Applicant" if slot == "applicant" else "Technology"
        self.keys = defaultdict(set)
        self.members = defaultdict(set)
        if slot == "applicant":
            frame = load_table("applicants")[["applicant_std", "applicant_raw"]].drop_duplicates().dropna(subset=["applicant_std"])
            for std, raw in frame.itertuples(index=False, name=None):
                canonical = aliases.get(std, std)
                self.members[canonical].add(std)
                self._add(canonical, canonical)
                self._add(std, canonical)
                if isinstance(raw, str):
                    self._add(raw, canonical)
            for alias, canonical in aliases.items():
                if canonical in self.members:
                    self._add(alias, canonical)
        else:
            for name in load_table("patent_topic").topic.dropna().unique():
                self.members[name].add(name)
                self._add(name, name)

    def _add(self, label, canonical):
        key = normalize(label)
        if key:
            self.keys[key].add(canonical)

    def link(self, question, mention=None):
        """Embedded exact matches may resolve; approximate matches require confirmation."""
        text = normalize(question)
        if mention:
            key = normalize(mention)
            matched = self.keys.get(key, set())
        else:
            spans = []
            for key in self.keys:
                # Single characters and generic labels are unsafe without explicit confirmation.
                if len(key) < 2 or key in {"企业", "主体", "未知", "某企业", "某创新主体", "某技术主题", "其他", "公司"}:
                    continue
                pattern = re.escape(key)
                if key.isascii() and key.isalnum():
                    # Preserve word boundaries in the original spaced question.
                    if not re.search(r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])",
                                     unicodedata.normalize("NFKC", question).casefold()):
                        continue
                start = text.find(key)
                if start >= 0:
                    spans.append((start, start + len(key), key))
            spans.sort(key=lambda item: (-(item[1] - item[0]), item[0]))
            selected = []
            for start, end, key in spans:
                if not any(left <= start and end <= right for left, right, _ in selected):
                    selected.append((start, end, key))
            matched = {name for _, _, key in selected for name in self.keys[key]}
        if len(matched) == 1:
            name = next(iter(matched))
            return Entity(name, self.kind, tuple(sorted(self.members[name]))), []
        if matched:
            return None, [self._candidate(name, 1.0) for name in sorted(matched)[:8]]
        guessed = mention or re.split(
            r"布局|涉及|的年度|的近|这些年|近年来|和哪些|与哪些|的合作|引用|的代表性|的技术|的专利|的主要|是否|[？?]",
            question, maxsplit=1,
        )[0]
        guessed = re.sub(r"^(请问|请查询|查询|请分析|分析|请列出|请介绍|列出|介绍|想了解)\s*", "", guessed.strip())
        if not guessed or guessed.startswith(("某创新主体", "某技术主题", "某企业")):
            return None, []
        scores = {}
        for key, score, _ in process.extract(normalize(guessed), list(self.keys), scorer=fuzz.WRatio,
                                              limit=16, score_cutoff=45):
            for name in self.keys[key]:
                scores[name] = max(scores.get(name, 0), score / 100)
        return None, [self._candidate(name, score) for name, score in
                      sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:8]]

    def _candidate(self, name, score):
        return {**Entity(name, self.kind, ()).public, "slot": self.slot, "score": score}
