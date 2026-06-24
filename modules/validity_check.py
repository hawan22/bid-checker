"""
Module B: 资质文件有效期检查
从PDF/图片/Word文档中提取日期，计算剩余天数，给出红黄绿状态。
支持格式：PDF / JPG / PNG / BMP / TIFF / DOCX
精确报告：在第几页、哪段文字中发现问题日期。
"""
import re
import datetime
from dataclasses import dataclass, field
from typing import List, Optional


DATE_PATTERNS = [
    r'有效期[至到截]?\s*[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
    r'有效期限[至到]?\s*[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
    r'证书有效期[至到]?\s*[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
    r'到期日期\s*[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
    r'有效期[至到截]?\s*[:：]?\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})',
    r'[至到]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
    r'[至到]\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})',
    r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*止',
    r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*止',
    r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
]

EXCLUDE_CONTEXT = ['发证日期', '颁发日期', '注册日期', '申请日期', '成立日期', '登记日期']


@dataclass
class DateHit:
    raw_text: str
    date: datetime.date
    days_remaining: int
    status: str        # "valid" | "expiring_soon" | "expiring_urgent" | "expired"
    color: str
    label: str
    context: str = ""
    location: str = ""   # 精确位置：如"第2页，第3行"


@dataclass
class ValidityResult:
    filename: str
    hits: List[DateHit] = field(default_factory=list)
    total_found: int = 0
    has_urgent: bool = False
    has_expired: bool = False
    summary: str = ""
    problems: List[str] = field(default_factory=list)  # 问题列表（供报告）


def _parse_date(y, m, d) -> Optional[datetime.date]:
    try:
        return datetime.date(int(y), int(m), int(d))
    except ValueError:
        return None


def _classify(date: datetime.date, raw: str, context: str, location: str = "") -> DateHit:
    today = datetime.date.today()
    delta = (date - today).days

    if delta < 0:
        status, color, label = "expired", "darkred", f"❌ 已过期 {abs(delta)} 天"
    elif delta < 30:
        status, color, label = "expiring_urgent", "red", f"🔴 {delta} 天后到期（紧急）"
    elif delta < 90:
        status, color, label = "expiring_soon", "yellow", f"🟡 {delta} 天后到期（关注）"
    else:
        status, color, label = "valid", "green", f"✅ 有效，剩余 {delta} 天"

    return DateHit(
        raw_text=raw, date=date, days_remaining=delta,
        status=status, color=color, label=label,
        context=context[:100], location=location,
    )


def _extract_dates_from_text(text: str, source_label: str = "") -> List[DateHit]:
    hits = []
    seen_dates = set()
    lines = text.splitlines()

    for pattern in DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            start = max(0, m.start() - 15)
            ctx = text[start: m.end() + 20]
            if any(excl in ctx for excl in EXCLUDE_CONTEXT):
                continue

            y, mo, d = m.group(1), m.group(2), m.group(3)
            date = _parse_date(y, mo, d)
            if date is None or date in seen_dates:
                continue
            if date.year < 2000 or date.year > 2040:
                continue
            seen_dates.add(date)

            raw = m.group(0)
            full_ctx = text[max(0, m.start()-40): m.end()+40].replace('\n', ' ')

            # 定位到行号
            pos = m.start()
            line_num = text[:pos].count('\n') + 1
            location = f"{source_label}第{line_num}行" if source_label else f"第{line_num}行"

            hits.append(_classify(date, raw, full_ctx, location))

    return hits


def check_validity_from_file(file_bytes: bytes, filename: str) -> ValidityResult:
    """从任意支持的文件（PDF/图片/Word）提取有效期。"""
    from modules.ocr_helper import extract_text_smart

    full_text, method_desc, pages_data = extract_text_smart(file_bytes, filename)

    if not pages_data:
        return ValidityResult(
            filename=filename, summary=f"⚠️ 无法解析文件（{method_desc}）"
        )

    # 逐页提取，带页码定位
    all_hits = []
    for page_info in pages_data:
        page_num = page_info["page"]
        page_text = page_info["text"]
        label = f"第{page_num}页，"
        hits = _extract_dates_from_text(page_text, label)
        all_hits.extend(hits)

    result = _build_result(filename, all_hits)
    result.summary += f"（来源：{method_desc}）"
    return result


def check_validity_from_pdf(file_bytes: bytes, filename: str = "") -> ValidityResult:
    """兼容旧接口，直接调用通用方法。"""
    return check_validity_from_file(file_bytes, filename)


def check_validity_from_text(text: str, filename: str = "手动输入") -> ValidityResult:
    hits = _extract_dates_from_text(text, "")
    return _build_result(filename, hits)


def _build_result(filename: str, hits: List[DateHit]) -> ValidityResult:
    problems = []
    for h in hits:
        if h.status in ("expired", "expiring_urgent", "expiring_soon"):
            problems.append(
                f"{h.location}：【{h.raw_text}】→ {h.label}（{h.date.strftime('%Y-%m-%d')}）"
            )

    has_urgent  = any(h.status in ("expiring_urgent", "expired") for h in hits)
    has_expired = any(h.status == "expired" for h in hits)

    if not hits:
        summary = "未检测到有效期日期，请确认文件含日期信息或改用「粘贴文本」方式。"
    elif has_expired:
        expired = [h for h in hits if h.status == "expired"]
        summary = f"⚠️ 发现 {len(expired)} 个已过期日期！"
    elif has_urgent:
        urgent = [h for h in hits if h.status == "expiring_urgent"]
        summary = f"🔴 发现 {len(urgent)} 个即将过期（30天内）！"
    else:
        summary = f"✅ 检测到 {len(hits)} 个有效期日期，全部有效。"

    return ValidityResult(
        filename=filename, hits=hits,
        total_found=len(hits), has_urgent=has_urgent, has_expired=has_expired,
        summary=summary, problems=problems,
    )
