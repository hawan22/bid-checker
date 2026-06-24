"""
名称一致性扫描模块
提取公司名/法定代表人/项目名，检查全文是否前后一致
"""
import re
from dataclasses import dataclass, field
from collections import Counter
from typing import List, Dict, Tuple, Optional


@dataclass
class EntityHit:
    entity_type: str    # 公司名/法定代表人/项目名
    value: str          # 具体值
    location: str       # 第N页
    context: str        # 上下文


@dataclass
class InconsistencyIssue:
    entity_type: str
    values_found: Dict[str, int]   # value -> 出现次数
    description: str
    risk_level: str


@dataclass
class NameConsistencyResult:
    entities: List[EntityHit] = field(default_factory=list)
    issues: List[InconsistencyIssue] = field(default_factory=list)
    summary: str = ""


# ---- 提取模式 ----

# 公司名：XX有限公司/集团/股份/合伙企业
COMPANY_PATTERN = re.compile(
    r'([\u4e00-\u9fa5a-zA-Z0-9（）\(\)·•]{2,30}'
    r'(?:有限公司|股份有限公司|集团有限公司|有限责任公司|'
    r'工程有限公司|科技有限公司|建设集团|集团公司|'
    r'合伙企业|个人独资企业))'
)

# 法定代表人：常见引导词 + 姓名（2-4个汉字）
LEGAL_REP_PATTERN = re.compile(
    r'(?:法定代表人|法人代表|法人|代表人)[：:：\s]*([^\s，。、（）]{2,6})'
)

# 项目名：XXX项目（招标/采购/工程/建设/改造）
PROJECT_PATTERN = re.compile(
    r'([\u4e00-\u9fa5a-zA-Z0-9（）]{4,40}'
    r'(?:招标项目|采购项目|工程项目|建设项目|改造项目|'
    r'施工项目|服务项目|货物项目|项目))'
)

CONTEXT_WINDOW = 40


def _ctx(text: str, start: int) -> str:
    s = max(0, start - CONTEXT_WINDOW)
    e = min(len(text), start + CONTEXT_WINDOW)
    return text[s:e].replace('\n', ' ').strip()


def _page(pages: List[str], offset: int) -> str:
    cumlen = 0
    for i, pg in enumerate(pages):
        if cumlen + len(pg) >= offset:
            return f"第{i+1}页"
        cumlen += len(pg)
    return f"第{len(pages)}页" if pages else "全文"


def _extract_entities(text: str, pages: List[str] = None) -> List[EntityHit]:
    hits: List[EntityHit] = []

    def add_hits(pattern, etype):
        for m in pattern.finditer(text):
            val = m.group(1).strip()
            if len(val) < 2:
                continue
            hits.append(EntityHit(
                entity_type=etype,
                value=val,
                location=_page(pages or [], m.start()),
                context=_ctx(text, m.start()),
            ))

    add_hits(COMPANY_PATTERN, "公司名称")
    add_hits(LEGAL_REP_PATTERN, "法定代表人")
    add_hits(PROJECT_PATTERN, "项目名称")

    return hits


def _check_consistency(hits: List[EntityHit]) -> List[InconsistencyIssue]:
    issues: List[InconsistencyIssue] = []

    # 按类型分组
    by_type: Dict[str, List[EntityHit]] = {}
    for h in hits:
        by_type.setdefault(h.entity_type, []).append(h)

    for etype, group in by_type.items():
        counter = Counter(h.value for h in group)
        if len(counter) <= 1:
            continue  # 全部一致，没问题

        # 找出出现最多的（主流值）和少数值
        most_common_val, most_count = counter.most_common(1)[0]
        minority = {v: c for v, c in counter.items() if v != most_common_val}

        for minority_val, minority_count in minority.items():
            # 计算相似度，避免误报（如"XX有限公司"和"XX公司"是同一公司缩写）
            if _is_abbreviation(minority_val, most_common_val) or \
               _is_abbreviation(most_common_val, minority_val):
                risk = "中"
                desc_suffix = "（可能为缩写，建议统一全称）"
            else:
                risk = "高"
                desc_suffix = "（存在实质差异，须核查）"

            locs = [h.location for h in group if h.value == minority_val]
            locs_str = "、".join(sorted(set(locs)))

            issues.append(InconsistencyIssue(
                entity_type=etype,
                values_found=dict(counter),
                description=(
                    f"{etype}不一致{desc_suffix}：\n"
                    f"  主要写法（{most_count}次）：「{most_common_val}」\n"
                    f"  差异写法（{minority_count}次，位于{locs_str}）：「{minority_val}」"
                ),
                risk_level=risk,
            ))

    return issues


def _is_abbreviation(short: str, long: str) -> bool:
    """简单判断 short 是否是 long 的缩写（包含关系）"""
    if len(short) >= len(long):
        return False
    # 短串的每个字符都出现在长串中（顺序不一定，但连续子串更严格）
    return short in long or all(c in long for c in short)


def check_name_consistency(text: str, pages: List[str] = None) -> NameConsistencyResult:
    entities = _extract_entities(text, pages)
    if not entities:
        return NameConsistencyResult(summary="未从文档中提取到公司名/法人/项目名")

    issues = _check_consistency(entities)

    # 统计
    type_counts: Dict[str, int] = {}
    for e in entities:
        type_counts[e.entity_type] = type_counts.get(e.entity_type, 0) + 1

    counts_str = "、".join(f"{t} {c}处" for t, c in type_counts.items())

    if not issues:
        summary = f"✅ 已检查 {counts_str}，名称前后一致"
    else:
        high = sum(1 for i in issues if i.risk_level == "高")
        mid = sum(1 for i in issues if i.risk_level == "中")
        parts = []
        if high:
            parts.append(f"🔴 高风险 {high} 项")
        if mid:
            parts.append(f"🟠 中风险 {mid} 项")
        summary = f"发现名称不一致：{'、'.join(parts)}（{counts_str}）"

    return NameConsistencyResult(entities=entities, issues=issues, summary=summary)
