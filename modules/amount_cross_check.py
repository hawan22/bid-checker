# -*- coding: utf-8 -*-
"""
投标函金额与报价单金额交叉核对
提取文档中不同章节的金额，检查是否一致。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class AmountRecord:
    raw_text: str       # 原始文本片段
    amount: float       # 解析出的金额（元）
    source_section: str # 所在章节/上下文
    page_hint: str      # 页面提示
    is_cny_upper: bool  # 是否大写金额


@dataclass
class AmountIssue:
    issue_type: str
    description: str
    amounts: List[float]
    locations: List[str]
    suggestion: str
    risk_level: str = "高"


@dataclass
class AmountCrossResult:
    all_amounts: List[AmountRecord]
    issues: List[AmountIssue]
    score: int
    summary: str


# ── 金额提取正则 ──────────────────────────────────────────────

# 数字金额：¥1,234,567.00 / 123456元 / 12.34万元 / 1234.56万
_NUM_PAT = re.compile(
    r'(?:¥|￥|人民币|RMB)?\s*'
    r'([\d,，]+(?:\.\d{1,2})?)\s*'
    r'(亿元|百万元|万元|千元|元整|元)?',
    re.IGNORECASE
)

# 中文大写金额
_CN_UPPER_CHARS = "零壹贰叁肆伍陆柒捌玖拾佰仟万亿元角分整圆"
_CN_UPPER_PAT = re.compile(
    r'[' + _CN_UPPER_CHARS + r']{4,30}'
)

# 章节关键词（用于判断金额所在上下文）
_SECTION_KEYWORDS = {
    "投标函":   ["投标函", "投标报价函", "投标总价", "投标人郑重承诺"],
    "报价单":   ["报价单", "报价表", "投标报价明细", "综合单价", "总价合计", "价格清单"],
    "合同":     ["合同价", "合同总价", "合同金额", "签约金额"],
    "保证金":   ["投标保证金", "保证金金额"],
    "预算":     ["预算金额", "最高投标限价", "控制价", "预算价"],
}


def _unit_to_multiplier(unit: Optional[str]) -> float:
    if not unit:
        return 1.0
    u = unit.strip()
    if u in ("亿元",):      return 1e8
    if u in ("百万元",):    return 1e6
    if u in ("万元",):      return 1e4
    if u in ("千元",):      return 1e3
    return 1.0


def _parse_numeric_amount(text: str) -> Optional[float]:
    """把 '1,234,567.89万元' 解析成浮点元值"""
    m = _NUM_PAT.search(text)
    if not m:
        return None
    num_str = m.group(1).replace(",", "").replace("，", "")
    try:
        val = float(num_str)
    except ValueError:
        return None
    val *= _unit_to_multiplier(m.group(2))
    # 过滤明显非价格（年份、编号、百分比上下文）
    if val < 100:  # 金额通常 >= 100元
        return None
    return val


def _cn_upper_to_float(text: str) -> Optional[float]:
    """粗略解析中文大写金额，返回元值；失败返回 None"""
    digit_map = {"零":0,"壹":1,"贰":2,"叁":3,"肆":4,
                 "伍":5,"陆":6,"柒":7,"捌":8,"玖":9}
    unit_map  = {"拾":10,"佰":100,"仟":1000,
                 "万":10000,"亿":100000000}
    total = 0
    current = 0
    section = 0
    for ch in text:
        if ch in digit_map:
            current = digit_map[ch]
        elif ch in unit_map:
            u = unit_map[ch]
            if u in (10000, 100000000):
                section = (section + current) * u
                current = 0
            else:
                section += current * u
                current = 0
        elif ch in ("元", "圆", "整", "角", "分"):
            break
    total = section + current
    return float(total) if total > 0 else None


def _get_section_label(context: str) -> str:
    for label, kws in _SECTION_KEYWORDS.items():
        for kw in kws:
            if kw in context:
                return label
    return "正文"


def _extract_amounts_from_text(text: str) -> List[AmountRecord]:
    records: List[AmountRecord] = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        # 获取上下文（前后各2行）
        ctx_start = max(0, i - 2)
        ctx_end = min(len(lines), i + 3)
        context = "\n".join(lines[ctx_start:ctx_end])
        section = _get_section_label(context)
        page_hint = f"约第{i // 40 + 1}页" if i > 0 else "首页"

        # 数字金额
        for m in _NUM_PAT.finditer(line):
            amount = _parse_numeric_amount(m.group(0))
            if amount and amount >= 1000:  # 只关心 1000元 以上
                records.append(AmountRecord(
                    raw_text=m.group(0).strip(),
                    amount=amount,
                    source_section=section,
                    page_hint=page_hint,
                    is_cny_upper=False
                ))

        # 大写金额
        for m in _CN_UPPER_PAT.finditer(line):
            amount = _cn_upper_to_float(m.group(0))
            if amount and amount >= 1000:
                records.append(AmountRecord(
                    raw_text=m.group(0),
                    amount=amount,
                    source_section=section,
                    page_hint=page_hint,
                    is_cny_upper=True
                ))

    return records


def _fmt_amount(val: float) -> str:
    if val >= 1e8:
        return f"{val/1e8:.4g}亿元"
    if val >= 1e4:
        return f"{val/1e4:.4g}万元"
    return f"{val:.2f}元"


def check_amount_cross(file_bytes: bytes, filename: str,
                       text: str, pages: list) -> AmountCrossResult:
    """提取全文金额，按章节分组，做交叉一致性核对。"""
    if not text and not pages:
        return AmountCrossResult([], [], 60, "ℹ️ 无文本内容，无法提取金额")

    full_text = text or "\n".join(pages)
    records = _extract_amounts_from_text(full_text)

    if not records:
        return AmountCrossResult([], [], 80,
            "ℹ️ 未在文档中识别到金额信息（金额 ≥ 1000元）")

    issues: List[AmountIssue] = []

    # ── 按章节聚合 ──────────────────────────────────────────
    by_section: dict = {}
    for r in records:
        by_section.setdefault(r.source_section, []).append(r)

    # ── 投标函 vs 报价单 核对 ────────────────────────────────
    bid_letter_amts  = by_section.get("投标函", [])
    price_list_amts  = by_section.get("报价单", [])

    if bid_letter_amts and price_list_amts:
        # 取各自最大金额（通常是合计）
        max_bl = max(r.amount for r in bid_letter_amts)
        max_pl = max(r.amount for r in price_list_amts)
        diff_pct = abs(max_bl - max_pl) / max(max_bl, max_pl, 1) * 100

        if diff_pct > 1.0:  # 误差 > 1% 报警
            issues.append(AmountIssue(
                "投标函与报价单金额不一致",
                f"投标函最大金额 {_fmt_amount(max_bl)}，"
                f"报价单最大金额 {_fmt_amount(max_pl)}，"
                f"差异 {diff_pct:.1f}%",
                [max_bl, max_pl],
                ["投标函", "报价单"],
                "两处金额必须严格一致，否则可能被认定为废标",
                "高"
            ))

    # ── 大/小写金额配对核对 ───────────────────────────────────
    num_amts = [r for r in records if not r.is_cny_upper and r.amount >= 10000]
    cn_amts  = [r for r in records if r.is_cny_upper and r.amount >= 10000]

    if num_amts and cn_amts:
        # 找最接近配对
        for na in num_amts[:5]:
            best_cn = min(cn_amts, key=lambda c: abs(c.amount - na.amount))
            diff = abs(best_cn.amount - na.amount) / max(na.amount, 1) * 100
            if diff > 1.0 and diff < 200:  # 有关联但有偏差
                issues.append(AmountIssue(
                    "大小写金额不一致",
                    f"数字 {_fmt_amount(na.amount)}（{na.source_section}）"
                    f" vs 大写 {_fmt_amount(best_cn.amount)}（{best_cn.source_section}）"
                    f"，差异 {diff:.1f}%",
                    [na.amount, best_cn.amount],
                    [na.source_section, best_cn.source_section],
                    "大小写金额必须完全一致，以大写为准；请仔细核对",
                    "高"
                ))
                break  # 只报首个

    # ── 预算限价核对 ─────────────────────────────────────────
    budget_amts = by_section.get("预算", [])
    if budget_amts and bid_letter_amts:
        max_budget = max(r.amount for r in budget_amts)
        max_bid    = max(r.amount for r in bid_letter_amts)
        if max_bid > max_budget * 1.01:
            issues.append(AmountIssue(
                "投标价超出最高限价",
                f"投标报价 {_fmt_amount(max_bid)} 超过最高限价 {_fmt_amount(max_budget)}",
                [max_bid, max_budget],
                ["投标函", "预算/限价"],
                "超出最高投标限价将直接废标，请重新核算报价",
                "高"
            ))

    # ── 评分 ─────────────────────────────────────────────────
    n_high = sum(1 for i in issues if i.risk_level == "高")
    if not issues:
        score = 100
        summary = (f"✅ 金额核对通过（识别 {len(records)} 条金额记录，"
                   f"覆盖{len(by_section)}个章节）")
    elif n_high:
        score = max(30, 70 - n_high * 20)
        summary = f"🔴 发现 {n_high} 处高风险金额不一致，请立即核查"
    else:
        score = 80
        summary = f"⚠️ 发现 {len(issues)} 处金额提示，建议人工复核"

    return AmountCrossResult(records, issues, score, summary)
