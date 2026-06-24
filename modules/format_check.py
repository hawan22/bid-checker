"""
格式规范检查模块（三合一）
① 标点符号规范性
② 日期格式统一性
③ 关键字段完整性
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from collections import Counter


# ═══════════════════════════════════════════════════════════════
# ① 标点符号规范性
# ═══════════════════════════════════════════════════════════════

@dataclass
class PunctIssue:
    issue_type: str
    description: str
    examples: List[str]
    count: int
    risk_level: str   # 高/中/提示


@dataclass
class PunctResult:
    issues: List[PunctIssue] = field(default_factory=list)
    summary: str = ""
    problems: List[str] = field(default_factory=list)


# 中文标点 ↔ 英文半角对照
FULLHALF_MAP = {
    # 中文文档中不应出现的英文标点（常见误用）
    r'(?<=[\u4e00-\u9fa5\d])\s*,\s*(?=[\u4e00-\u9fa5\d])':
        ("中文句中使用半角逗号","应为全角逗号，"),
    r'(?<=[\u4e00-\u9fa5\d])\s*\.\s*(?=[\u4e00-\u9fa5])':
        ("中文句中使用半角句号","应为全角句号。"),
    r'(?<=[\u4e00-\u9fa5\d])\s*;\s*(?=[\u4e00-\u9fa5\d])':
        ("中文句中使用半角分号","应为全角分号；"),
    r'(?<=[\u4e00-\u9fa5\d])\s*:\s*(?=[\u4e00-\u9fa5])':
        ("中文句中使用半角冒号","应为全角冒号："),
    r'\([\u4e00-\u9fa5]{1,20}\)':
        ("括号使用半角","中文内容的括号应用全角（）"),
}

# 连续重复标点
REPEAT_PUNCT = re.compile(r'([，。！？；：、]{2,})')

# 中文里混入全角英文字母（常见OCR或复制粘贴问题）
FULLWIDTH_ALPHA = re.compile(r'[Ａ-Ｚａ-ｚ０-９]{2,}')

# 空格误用（中文之间不应有空格，除非是分隔符）
ZH_SPACE = re.compile(r'[\u4e00-\u9fa5] {2,}[\u4e00-\u9fa5]')

# 书名号/引号不配对
BRACKET_PAIRS = [('《', '》'), ('【', '】'), ('「', '」'), ('"', '"'), (''', ''')]


def _find_examples(text: str, pattern: str, max_ex: int = 3) -> List[str]:
    matches = re.findall(pattern, text)
    seen = []
    for m in matches:
        if m not in seen:
            seen.append(m)
        if len(seen) >= max_ex:
            break
    return seen


def check_punctuation(text: str) -> PunctResult:
    issues: List[PunctIssue] = []

    # 1. 全角/半角混用
    for pattern, (desc, fix) in FULLHALF_MAP.items():
        matches = re.findall(pattern, text)
        if matches:
            examples = list(dict.fromkeys(matches))[:3]
            issues.append(PunctIssue(
                issue_type="全角半角混用",
                description=f"{desc}（建议{fix}）",
                examples=examples,
                count=len(matches),
                risk_level="中",
            ))

    # 2. 连续重复标点
    repeats = REPEAT_PUNCT.findall(text)
    if repeats:
        examples = list(dict.fromkeys(repeats))[:3]
        issues.append(PunctIssue(
            issue_type="连续重复标点",
            description=f"出现连续重复标点符号 {len(repeats)} 处（如{examples[0]}），多为复制粘贴残留",
            examples=examples,
            count=len(repeats),
            risk_level="提示",
        ))

    # 3. 全角英文字母/数字（OCR问题）
    fullwidth = FULLWIDTH_ALPHA.findall(text)
    if fullwidth:
        examples = list(dict.fromkeys(fullwidth))[:3]
        issues.append(PunctIssue(
            issue_type="全角英文/数字",
            description=f"发现全角英文字母或数字 {len(fullwidth)} 处（如{'、'.join(examples)}）"
                        "，可能导致系统无法识别货号/编号",
            examples=examples,
            count=len(fullwidth),
            risk_level="中",
        ))

    # 4. 中文间多余空格
    spaces = ZH_SPACE.findall(text)
    if spaces:
        issues.append(PunctIssue(
            issue_type="中文间多余空格",
            description=f"中文字符之间出现连续空格 {len(spaces)} 处，影响版式整洁",
            examples=spaces[:3],
            count=len(spaces),
            risk_level="提示",
        ))

    # 5. 括号不配对
    for open_b, close_b in BRACKET_PAIRS:
        open_count = text.count(open_b)
        close_count = text.count(close_b)
        if open_count != close_count:
            issues.append(PunctIssue(
                issue_type=f"括号不配对（{open_b}{close_b}）",
                description=f"「{open_b}」出现 {open_count} 次，「{close_b}」出现 {close_count} 次，"
                            f"差 {abs(open_count-close_count)} 个",
                examples=[],
                count=abs(open_count - close_count),
                risk_level="中",
            ))

    if not issues:
        summary = "✅ 标点符号规范，未发现明显问题"
    else:
        high = sum(1 for i in issues if i.risk_level in ("高", "中"))
        summary = f"发现标点问题 {len(issues)} 类（🟠 {high} 项需修正）"

    problems = [f"{i.issue_type}：{i.description}" for i in issues]
    return PunctResult(issues=issues, summary=summary, problems=problems)


# ═══════════════════════════════════════════════════════════════
# ② 日期格式统一性
# ═══════════════════════════════════════════════════════════════

@dataclass
class DateFormatResult:
    formats_found: Dict[str, int]   # 格式名 -> 出现次数
    is_consistent: bool
    dominant_format: str
    problems: List[str] = field(default_factory=list)
    summary: str = ""


# 各种日期格式的正则
DATE_FORMAT_PATTERNS: List[Tuple[str, str]] = [
    (r'\d{4}年\d{1,2}月\d{1,2}日',  "中文全写（2026年6月12日）"),
    (r'\d{4}-\d{2}-\d{2}',           "连字符ISO（2026-06-12）"),
    (r'\d{4}/\d{2}/\d{2}',           "斜线分隔（2026/06/12）"),
    (r'\d{4}\.\d{1,2}\.\d{1,2}',     "点号分隔（2026.6.12）"),
    (r'\d{2}年\d{1,2}月\d{1,2}日',   "两位年（26年6月12日）"),
    (r'\d{1,2}/\d{1,2}/\d{4}',       "日月年倒置（12/6/2026）"),
    (r'\d{8}',                        "纯数字（20260612）"),
]


def check_date_format(text: str) -> DateFormatResult:
    counts: Dict[str, int] = {}
    for pattern, label in DATE_FORMAT_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            counts[label] = len(matches)

    if not counts:
        return DateFormatResult(
            formats_found={}, is_consistent=True,
            dominant_format="未找到日期", summary="未识别到日期格式"
        )

    # 超过1种格式 = 不统一
    is_consistent = len(counts) <= 1
    dominant = max(counts, key=counts.get)

    problems = []
    if not is_consistent:
        minority = [f for f in counts if f != dominant]
        for fmt in minority:
            problems.append(
                f"日期格式不统一：主要格式「{dominant}」，但有 {counts[fmt]} 处使用了「{fmt}」"
            )
        problems.append(f"建议：全文统一使用「{dominant}」")

    summary = "✅ 日期格式统一" if is_consistent else f"⚠️ 日期格式混用（{len(counts)} 种格式）"
    return DateFormatResult(
        formats_found=counts,
        is_consistent=is_consistent,
        dominant_format=dominant,
        problems=problems,
        summary=summary,
    )


# ═══════════════════════════════════════════════════════════════
# ③ 关键字段完整性
# ═══════════════════════════════════════════════════════════════

@dataclass
class FieldCheckItem:
    field_name: str
    is_present: bool
    evidence: str      # 命中的文字片段，或"未找到"
    risk_level: str    # 高/中/提示


@dataclass
class FieldCheckResult:
    items: List[FieldCheckItem] = field(default_factory=list)
    missing_high: int = 0
    missing_mid: int = 0
    problems: List[str] = field(default_factory=list)
    summary: str = ""


# 字段名 → (搜索正则列表, 风险等级, 说明)
REQUIRED_FIELDS = [
    ("报价单位（元/万元）",
     [r'[万元]{1,3}(?:人民币|RMB)?', r'(?:单位|报价单位)[：:]\s*[万元]'],
     "中", "未标注报价单位（元/万元）易引发理解歧义"),

    ("项目名称",
     [r'项目名称[：:：\s]', r'采购项目[：:：\s]', r'工程名称[：:：\s]'],
     "高", "投标文件必须明确载明项目名称"),

    ("招标编号/项目编号",
     [r'招标编号[：:：\s]?\w', r'项目编号[：:：\s]?\w', r'采购编号[：:：\s]?\w',
      r'编号[：:：\s][A-Z\d\-]{4,}'],
     "高", "未标注招标编号，可能被判为响应错误项目"),

    ("投标人名称",
     [r'投标(?:人|方|单位)[：:：\s][\u4e00-\u9fa5]',
      r'(?:甲|乙)方[：:：\s][\u4e00-\u9fa5]'],
     "高", "未在文件中明确载明投标人名称"),

    ("法定代表人/授权代表",
     [r'法定代表人', r'授权代表', r'法人代表'],
     "高", "须有法人或授权代表签字"),

    ("联系人",
     [r'联系人[：:：\s][\u4e00-\u9fa5]{2,4}', r'经办人[：:：\s]'],
     "中", "建议填写联系人以便评标方核实"),

    ("联系电话",
     [r'(?:电话|联系电话|手机)[：:：\s]*1[3-9]\d{9}',
      r'(?:电话|联系电话)[：:：\s]*0\d{2,3}[\-\s]\d{7,8}',
      r'Tel[：:]\s*\d'],
     "中", "未提供联系方式，影响后续沟通"),

    ("投标报价合计",
     [r'(?:投标|报价)(?:总价|合计|金额)[：:：\s]*[¥￥]?[\d,，万]+',
      r'合计[：:：\s]*[¥￥]?[\d,，万]+元'],
     "高", "投标文件必须有明确的报价合计"),

    ("投标有效期",
     [r'投标有效期', r'报价有效期'],
     "中", "须明确投标有效期（通常要求≥90天）"),

    ("付款条件/方式",
     [r'付款(?:条件|方式|周期)', r'结算方式'],
     "提示", "付款条款影响合同执行，建议明确"),
]


def check_field_completeness(text: str) -> FieldCheckResult:
    items: List[FieldCheckItem] = []

    for field_name, patterns, risk, hint in REQUIRED_FIELDS:
        found = False
        evidence = "未找到"
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                found = True
                # 取命中片段前后各15字符作为证据
                s = max(0, m.start() - 5)
                e = min(len(text), m.end() + 15)
                evidence = text[s:e].replace('\n', ' ').strip()
                break
        items.append(FieldCheckItem(
            field_name=field_name,
            is_present=found,
            evidence=evidence,
            risk_level=risk,
        ))

    missing_high = sum(1 for i in items if not i.is_present and i.risk_level == "高")
    missing_mid = sum(1 for i in items if not i.is_present and i.risk_level == "中")

    problems = []
    for item in items:
        if not item.is_present:
            icon = "🔴" if item.risk_level == "高" else ("🟠" if item.risk_level == "中" else "🔵")
            hint_text = next((h for n, _, _, h in REQUIRED_FIELDS if n == item.field_name), "")
            problems.append(f"{icon} 缺失「{item.field_name}」：{hint_text}")

    if missing_high == 0 and missing_mid == 0:
        summary = f"✅ 所有关键字段均已找到（共{len(items)}项）"
    else:
        parts = []
        if missing_high: parts.append(f"🔴 高风险缺失 {missing_high} 项")
        if missing_mid:  parts.append(f"🟠 中风险缺失 {missing_mid} 项")
        summary = "关键字段不完整：" + "、".join(parts)

    return FieldCheckResult(
        items=items,
        missing_high=missing_high,
        missing_mid=missing_mid,
        problems=problems,
        summary=summary,
    )
