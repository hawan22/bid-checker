"""
废标关键词扫描模块
基于真实废标案例的高频触发词库，全文搜索并标注风险等级
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class KeywordHit:
    keyword: str
    category: str
    risk_level: str        # 高/中/提示
    context: str           # 命中的上下文片段
    location: str          # 第N页/行 或 "全文"


@dataclass
class KeywordScanResult:
    total_hits: int
    high_risk: int
    medium_risk: int
    hits: List[KeywordHit] = field(default_factory=list)
    summary: str = ""


# ============================================================
# 废标关键词词库
# 格式：(关键词, 类别说明, 风险等级, 扫描提示)
# ============================================================
KEYWORD_DB: List[Tuple[str, str, str, str]] = [
    # ---- 形式核验（高风险）----
    ("未加盖公章",    "签章缺失",   "高", "全文检查是否明确要求加盖公章却有此提示"),
    ("未签字",        "签字缺失",   "高", "检查是否存在应签字而未签字的描述"),
    ("盖章无效",      "签章问题",   "高", "印章可能为图片章，非CA数字签名"),
    ("图片章",        "签章问题",   "高", "部分平台明确不接受扫描盖章图片，须CA数字签名"),
    ("未使用CA",      "电子签名",   "高", "电子标书必须使用CA证书签章"),
    ("CA证书过期",    "电子签名",   "高", "CA证书失效导致加解密失败，常见废标原因"),
    ("联合体",        "联合投标",   "高", "联合体投标须提交联合体协议，否则废标"),
    ("联合体协议",    "联合投标",   "高", "联合体协议须在投标截止前提交原件"),
    ("不接受联合体",  "联合投标",   "高", "招标文件明确不接受联合体，出现此词须警惕"),
    ("不接受备选方案","备选方案",   "高", "招标文件不接受备选方案，若投标含备选内容则废标"),
    ("备选报价",      "备选方案",   "高", "备选报价可能被判定为备选方案触发废标"),

    # ---- 资质与业绩（高风险）----
    ("资质证书过期",  "资质问题",   "高", "过期资质等同无效资质"),
    ("营业执照过期",  "资质问题",   "高", "营业执照过期直接废标"),
    ("安全生产许可证过期", "资质问题", "高", "安全类资质过期是高频废标原因"),
    ("业绩证明不足",  "业绩要求",   "高", "业绩不满足最低要求"),
    ("业绩造假",      "虚假材料",   "高", "提供虚假业绩列入黑名单"),
    ("虚假材料",      "虚假材料",   "高", "提供虚假材料废标并可能被列入黑名单"),
    ("不满足资格条件","资质要求",   "高", "明确标注不满足资格条件"),

    # ---- 报价问题（高风险）----
    ("大小写不一致",  "报价矛盾",   "高", "报价大小写不一致导致废标"),
    ("报价超预算",    "报价超限",   "高", "报价超出招标控制价"),
    ("超出最高限价",  "报价超限",   "高", "超出最高限价即废标"),
    ("低于成本价",    "异常低价",   "高", "低于成本价的报价可能被判定为异常低价"),
    ("不平衡报价",    "报价风险",   "中", "不平衡报价影响评分并可能引发投诉"),

    # ---- 日期/逻辑矛盾（中风险）----
    ("授权日期",      "日期逻辑",   "中", "检查授权日期是否早于开标日期"),
    ("有效期不足",    "有效期",     "中", "投标有效期须满足招标文件要求"),
    ("投标有效期",    "有效期",     "中", "注意投标有效期是否覆盖评标及合同签署时间"),
    ("逾期送达",      "时间问题",   "高", "逾期送达的投标文件不予受理"),
    ("截止时间",      "时间问题",   "中", "核查递交截止时间"),

    # ---- 名称/主体问题（中风险）----
    ("名称不一致",    "名称矛盾",   "中", "公司名称/法人前后不一致"),
    ("法定代表人",    "签字主体",   "中", "检查法人签字是否与营业执照一致"),
    ("授权委托书",    "授权文件",   "中", "授权委托书须符合格式且在有效期内"),

    # ---- 合规词汇提示（提示级）----
    ("串通投标",      "违法行为",   "高", "若文件中出现相关表述须立即核查"),
    ("陪标",          "违法行为",   "高", "陪标属违法，若出现相关描述须警惕"),
    ("泄露标底",      "违法行为",   "高", "泄露标底导致废标及法律责任"),
    ("重新招标",      "流程问题",   "提示", "文件中出现此词，说明本次可能面临重标风险"),
    ("否决投标",      "废标提示",   "提示", "注意否决投标的具体条款"),
    ("不予受理",      "废标提示",   "高", "明确的不予受理表述"),
]


def _get_line_context(text: str, match_start: int, window: int = 80) -> str:
    """取命中位置前后的上下文片段"""
    start = max(0, match_start - window // 2)
    end = min(len(text), match_start + window // 2)
    snippet = text[start:end].replace('\n', ' ').strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def _get_page_location(pages: List[str], match_start: int) -> str:
    """根据字符偏移量定位到第几页"""
    if not pages:
        return "全文"
    cumlen = 0
    for i, pg in enumerate(pages):
        if cumlen + len(pg) >= match_start:
            return f"第{i+1}页"
        cumlen += len(pg)
    return f"第{len(pages)}页"


def scan_keywords(text: str, pages: List[str] = None) -> KeywordScanResult:
    """
    扫描全文废标关键词
    pages: 按页分割的文本列表（用于精确定位）
    """
    hits: List[KeywordHit] = []

    for kw, category, risk, tip in KEYWORD_DB:
        for m in re.finditer(re.escape(kw), text):
            loc = _get_page_location(pages or [], m.start()) if pages else "全文"
            ctx = _get_get_context(text, m.start())
            hits.append(KeywordHit(
                keyword=kw,
                category=category,
                risk_level=risk,
                context=ctx,
                location=loc,
            ))

    # 去重：同一关键词在同一页只报一次
    seen = set()
    unique_hits = []
    for h in hits:
        key = (h.keyword, h.location)
        if key not in seen:
            seen.add(key)
            unique_hits.append(h)

    high = sum(1 for h in unique_hits if h.risk_level == "高")
    mid = sum(1 for h in unique_hits if h.risk_level == "中")

    summary_parts = []
    if high:
        summary_parts.append(f"🔴 高风险 {high} 项")
    if mid:
        summary_parts.append(f"🟠 中风险 {mid} 项")
    tips = sum(1 for h in unique_hits if h.risk_level == "提示")
    if tips:
        summary_parts.append(f"🔵 提示 {tips} 项")

    summary = "、".join(summary_parts) if summary_parts else "✅ 未命中废标关键词"

    return KeywordScanResult(
        total_hits=len(unique_hits),
        high_risk=high,
        medium_risk=mid,
        hits=unique_hits,
        summary=summary,
    )


def _get_get_context(text: str, match_start: int, window: int = 80) -> str:
    start = max(0, match_start - window // 2)
    end = min(len(text), match_start + window // 2)
    snippet = text[start:end].replace('\n', ' ').strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet
