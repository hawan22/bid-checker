"""
日期逻辑一致性检查模块
提取文档中所有带上下文的日期，标注角色，检查逻辑矛盾
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Tuple


@dataclass
class DateEntry:
    raw: str            # 原始文字
    parsed: date        # 解析后的日期
    role: str           # 推断角色：开标/授权/有效期/截止/签字/其他
    context: str        # 前后文片段
    location: str       # 第N页


@dataclass
class LogicIssue:
    description: str
    risk_level: str     # 高/中
    date_a: DateEntry
    date_b: DateEntry


@dataclass
class DateLogicResult:
    entries: List[DateEntry] = field(default_factory=list)
    issues: List[LogicIssue] = field(default_factory=list)
    summary: str = ""


# ---- 日期正则 ----
DATE_PATTERNS = [
    # 2026年06月12日
    (r'(\d{4})[年](\d{1,2})[月](\d{1,2})[日号]?', '%Y %m %d'),
    # 2026-06-12 / 2026/06/12 / 2026.06.12
    (r'(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})', '%Y %m %d'),
    # 两位年份模式用负向后瞻，避免在四位年份中间匹配（如"2025年"的"25年"部分）
    (r'(?<!\d)(\d{2})[年](\d{1,2})[月](\d{1,2})[日号]?', '%y %m %d'),
]

# ---- 角色关键词（先后顺序影响优先级）----
ROLE_PATTERNS = [
    (r'开标',          "开标日期"),
    (r'投标截止',      "投标截止"),
    (r'递交截止',      "递交截止"),
    (r'签订合同|合同签',  "合同签订"),
    (r'授权.*?日期|委托.*?日期|法定代表人.*?授权', "授权日期"),
    (r'有效期.*?至|至.*?有效|有效截止',  "有效期截止"),
    (r'营业执照.*?至|至.*?营业执照',    "营业执照到期"),
    (r'资质.*?有效|有效.*?资质',        "资质有效期"),
    (r'签字日期|签署日期|盖章日期',      "签字日期"),
    (r'成立日期|注册日期',              "企业成立日"),
]

PRE_CONTEXT_WINDOW = 10   # 角色判断只看日期前方10字符（最长角色标签≤7字符）
CONTEXT_WINDOW = 50       # 显示用的前后上下文


def _parse_date_str(y: str, m: str, d: str, pattern: str) -> Optional[date]:
    try:
        fmt_str = f"{y.zfill(4) if len(y)==4 else '20'+y} {m.zfill(2)} {d.zfill(2)}"
        return datetime.strptime(fmt_str, '%Y %m %d').date()
    except Exception:
        return None


def _infer_role(context_text: str) -> str:
    for pattern, role in ROLE_PATTERNS:
        if re.search(pattern, context_text):
            return role
    return "其他日期"


def _get_context(text: str, start: int) -> str:
    s = max(0, start - CONTEXT_WINDOW)
    e = min(len(text), start + CONTEXT_WINDOW)
    return text[s:e].replace('\n', ' ').strip()


def _get_page(pages: List[str], offset: int) -> str:
    cumlen = 0
    for i, pg in enumerate(pages):
        if cumlen + len(pg) >= offset:
            return f"第{i+1}页"
        cumlen += len(pg)
    return f"第{len(pages)}页" if pages else "全文"


def extract_dates(text: str, pages: List[str] = None) -> List[DateEntry]:
    entries: List[DateEntry] = []
    seen_positions = set()

    for pattern, _ in DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            if m.start() in seen_positions:
                continue
            groups = m.groups()
            parsed = _parse_date_str(groups[0], groups[1], groups[2], pattern)
            if parsed is None:
                continue
            # 过滤明显无效日期（太早或太远未来）
            if parsed.year < 2000 or parsed.year > 2040:
                continue
            seen_positions.add(m.start())
            ctx = _get_context(text, m.start())
            # 角色判断只用前向上下文（避免后方无关词汇干扰）
            pre_ctx = text[max(0, m.start() - PRE_CONTEXT_WINDOW): m.start()]
            role = _infer_role(pre_ctx)
            loc = _get_page(pages or [], m.start()) if pages else "全文"
            entries.append(DateEntry(
                raw=m.group(0),
                parsed=parsed,
                role=role,
                context=ctx,
                location=loc,
            ))

    # 去重：同一日期值只保留最先出现的那个（避免两位/四位年份模式重复命中）
    seen_dates = set()
    unique_entries = []
    for e in sorted(entries, key=lambda x: text.find(x.raw)):
        if e.parsed not in seen_dates:
            seen_dates.add(e.parsed)
            unique_entries.append(e)

    unique_entries.sort(key=lambda e: e.parsed)
    return unique_entries


def check_date_logic(entries: List[DateEntry]) -> List[LogicIssue]:
    issues: List[LogicIssue] = []

    def find_by_role(role_keyword: str) -> List[DateEntry]:
        return [e for e in entries if role_keyword in e.role]

    # 规则1：授权日期必须 ≤ 开标日期
    auth_dates = find_by_role("授权日期") + find_by_role("签字日期")
    bid_dates = find_by_role("开标日期") + find_by_role("投标截止") + find_by_role("递交截止")
    for a in auth_dates:
        for b in bid_dates:
            if a.parsed > b.parsed:
                issues.append(LogicIssue(
                    description=f"【授权/签字日期 晚于 开标/截止日期】：{a.role}（{a.raw}）> {b.role}（{b.raw}）— 逻辑矛盾，可能废标",
                    risk_level="高",
                    date_a=a,
                    date_b=b,
                ))

    # 规则2：有效期截止不能早于开标日期
    validity_dates = find_by_role("有效期截止") + find_by_role("营业执照到期") + find_by_role("资质有效期")
    for v in validity_dates:
        for b in bid_dates:
            if v.parsed < b.parsed:
                issues.append(LogicIssue(
                    description=f"【证件有效期 早于 开标日期】：{v.role}（{v.raw}）在 {b.role}（{b.raw}）之前到期 — 届时资质已失效",
                    risk_level="高",
                    date_a=v,
                    date_b=b,
                ))

    # 规则3：合同签订日期应在开标日期之后
    contract_dates = find_by_role("合同签订")
    for c in contract_dates:
        for b in bid_dates:
            if c.parsed < b.parsed:
                issues.append(LogicIssue(
                    description=f"【合同签订日期 早于 开标日期】：{c.role}（{c.raw}）< {b.role}（{b.raw}）— 时序错误",
                    risk_level="中",
                    date_a=c,
                    date_b=b,
                ))

    # 规则4：投标有效期过短（授权日期与递交截止差距 < 90 天则警告）
    if auth_dates and bid_dates:
        earliest_auth = min(e.parsed for e in auth_dates)
        latest_bid = max(e.parsed for e in bid_dates)
        delta = (latest_bid - earliest_auth).days
        if 0 < delta < 30:
            issues.append(LogicIssue(
                description=f"授权日期距开标截止仅 {delta} 天，投标有效期可能不足（通常要求 ≥90 天）",
                risk_level="中",
                date_a=auth_dates[0],
                date_b=bid_dates[0],
            ))

    return issues


def analyze_date_logic(text: str, pages: List[str] = None) -> DateLogicResult:
    entries = extract_dates(text, pages)
    if not entries:
        return DateLogicResult(summary="未提取到日期信息")

    issues = check_date_logic(entries)

    if not issues:
        summary = f"✅ 共提取 {len(entries)} 个日期，未发现逻辑矛盾"
    else:
        high = sum(1 for i in issues if i.risk_level == "高")
        mid = sum(1 for i in issues if i.risk_level == "中")
        parts = []
        if high:
            parts.append(f"🔴 高风险 {high} 项")
        if mid:
            parts.append(f"🟠 中风险 {mid} 项")
        summary = f"发现日期逻辑问题：{'、'.join(parts)}（共 {len(entries)} 个日期）"

    return DateLogicResult(entries=entries, issues=issues, summary=summary)
