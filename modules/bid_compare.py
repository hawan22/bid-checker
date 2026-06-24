"""
多标书比较模块
① 串标/陪标风险检测
② 综合规范性评分
③ 中标优势排名
"""
import re
import io
import difflib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import Counter

try:
    import fitz
    FITZ_OK = True
except ImportError:
    FITZ_OK = False


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class BidInfo:
    filename: str
    text: str
    pages: List[str]               # 按页分割的文本
    metadata: Dict[str, str]       # PDF元数据
    price: Optional[float]         # 自动提取的报价
    company: str                   # 投标公司名
    contact_phone: str             # 联系电话
    contact_person: str            # 联系人
    legal_rep: str                 # 法定代表人


@dataclass
class CollusionFlag:
    flag_type: str        # 联系方式重复/公司名重复/文本雷同/报价规律/元数据相同/用词相同
    risk_level: str       # 高/中/提示
    description: str
    bids_involved: List[str]   # 涉及的标书文件名
    evidence: str


@dataclass
class BidScore:
    filename: str
    company: str
    price: Optional[float]
    # 各维度评分（0~100）
    format_score: int          # 格式规范
    field_score: int           # 字段完整
    price_score: int           # 价格竞争力（越低越高分，但不能低于安全线）
    qualification_score: int   # 资质完整性
    name_consistency_score: int  # 名称一致性
    total_score: int
    rank: int
    strengths: List[str]       # 优势项
    weaknesses: List[str]      # 劣势/风险项
    recommendation: str        # 综合建议


@dataclass
class CompareResult:
    bids: List[BidInfo]
    collusion_flags: List[CollusionFlag]
    scores: List[BidScore]
    winner_recommendation: str
    collusion_risk_level: str   # 无/低/中/高


# ═══════════════════════════════════════════════════════════════
# 信息提取
# ═══════════════════════════════════════════════════════════════

def _extract_price(text: str) -> Optional[float]:
    """从文本提取最大报价金额（优先找合计/总价行）"""
    # 优先找"合计/总价"附近的金额
    priority_patterns = [
        r'(?:投标总价|报价合计|合计|总价)[^\d]{0,10}([\d,，]+(?:\.\d{1,2})?)',
        r'([\d,，]+(?:\.\d{1,2})?)\s*元\s*(?:整|人民币)',
    ]
    for pat in priority_patterns:
        m = re.search(pat, text)
        if m:
            try:
                val = float(m.group(1).replace(',','').replace('，',''))
                if val > 1000:  # 过滤掉无意义小数
                    return val
            except Exception:
                pass

    # fallback: 找最大的数字金额
    amounts = re.findall(r'(\d{4,}(?:\.\d{1,2})?)', text)
    valid = []
    for a in amounts:
        try:
            v = float(a)
            if 1000 < v < 1e12:
                valid.append(v)
        except Exception:
            pass
    return max(valid) if valid else None


def _extract_company(text: str) -> str:
    patterns = [
        r'([\u4e00-\u9fa5a-zA-Z0-9（）]{2,25}(?:有限公司|股份有限公司|集团有限公司|有限责任公司))',
        r'投标(?:人|方|单位)[：:：\s]*([\u4e00-\u9fa5a-zA-Z0-9（）]{2,25})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return ""


def _extract_phone(text: str) -> str:
    patterns = [
        r'1[3-9]\d{9}',
        r'0\d{2,3}[\-\s]\d{7,8}',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return ""


def _extract_contact(text: str) -> str:
    m = re.search(r'联系人[：:：\s]*([\u4e00-\u9fa5]{2,4})', text)
    return m.group(1) if m else ""


def _extract_legal_rep(text: str) -> str:
    m = re.search(r'法定代表人[：:：\s]*([\u4e00-\u9fa5]{2,4})', text)
    return m.group(1) if m else ""


def _get_pdf_metadata(file_bytes: bytes) -> Dict[str, str]:
    if not FITZ_OK:
        return {}
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        meta = doc.metadata or {}
        return {k: str(v) for k, v in meta.items() if v}
    except Exception:
        return {}


def extract_bid_info(file_bytes: bytes, filename: str, text: str, pages: List[str]) -> BidInfo:
    meta = _get_pdf_metadata(file_bytes) if filename.lower().endswith('.pdf') else {}
    return BidInfo(
        filename=filename,
        text=text,
        pages=pages,
        metadata=meta,
        price=_extract_price(text),
        company=_extract_company(text),
        contact_phone=_extract_phone(text),
        contact_person=_extract_contact(text),
        legal_rep=_extract_legal_rep(text),
    )


# ═══════════════════════════════════════════════════════════════
# 串标检测
# ═══════════════════════════════════════════════════════════════

def _text_similarity(a: str, b: str) -> float:
    """返回两段文本的相似度 0~1"""
    # 取前3000字符做比较（避免超长文本耗时）
    a_sample = a[:3000].strip()
    b_sample = b[:3000].strip()
    if not a_sample or not b_sample:
        return 0.0
    return difflib.SequenceMatcher(None, a_sample, b_sample).ratio()


def _find_unique_phrases(text: str, min_len: int = 8) -> set:
    """提取文本中长度≥min_len的不常见短语（用于雷同性检测）"""
    # 按标点分句
    sentences = re.split(r'[。！？；\n]', text)
    phrases = set()
    for s in sentences:
        s = s.strip()
        if min_len <= len(s) <= 60:  # 适中长度的句子
            phrases.add(s)
    return phrases


def detect_collusion(bids: List[BidInfo]) -> List[CollusionFlag]:
    flags: List[CollusionFlag] = []
    n = len(bids)
    if n < 2:
        return flags

    # ── 1. 联系电话重复 ──────────────────────────────────────
    phone_map: Dict[str, List[str]] = {}
    for b in bids:
        if b.contact_phone:
            phone_map.setdefault(b.contact_phone, []).append(b.filename)
    for phone, files in phone_map.items():
        if len(files) > 1:
            flags.append(CollusionFlag(
                flag_type="联系电话重复",
                risk_level="高",
                description=f"以下 {len(files)} 份标书使用相同联系电话「{phone}」",
                bids_involved=files,
                evidence=f"联系电话：{phone}",
            ))

    # ── 2. 联系人重复 ────────────────────────────────────────
    person_map: Dict[str, List[str]] = {}
    for b in bids:
        if b.contact_person:
            person_map.setdefault(b.contact_person, []).append(b.filename)
    for person, files in person_map.items():
        if len(files) > 1:
            flags.append(CollusionFlag(
                flag_type="联系人重复",
                risk_level="高",
                description=f"以下 {len(files)} 份标书联系人均为「{person}」",
                bids_involved=files,
                evidence=f"联系人：{person}",
            ))

    # ── 3. 法定代表人重复（不同公司却同一法人）───────────────
    rep_map: Dict[str, List[str]] = {}
    for b in bids:
        if b.legal_rep:
            rep_map.setdefault(b.legal_rep, []).append(b.filename)
    for rep, files in rep_map.items():
        if len(files) > 1:
            flags.append(CollusionFlag(
                flag_type="法定代表人重复",
                risk_level="高",
                description=f"以下 {len(files)} 份标书法定代表人均为「{rep}」",
                bids_involved=files,
                evidence=f"法定代表人：{rep}",
            ))

    # ── 4. PDF元数据作者/创建工具相同 ────────────────────────
    author_map: Dict[str, List[str]] = {}
    creator_map: Dict[str, List[str]] = {}
    for b in bids:
        if b.metadata.get('author'):
            author_map.setdefault(b.metadata['author'], []).append(b.filename)
        if b.metadata.get('creator'):
            creator_map.setdefault(b.metadata['creator'], []).append(b.filename)
    for author, files in author_map.items():
        if len(files) > 1 and author.strip():
            flags.append(CollusionFlag(
                flag_type="PDF作者元数据相同",
                risk_level="中",
                description=f"以下 {len(files)} 份PDF的「作者」元数据均为「{author}」，疑似同一电脑制作",
                bids_involved=files,
                evidence=f"PDF Author: {author}",
            ))

    # ── 5. 文本高度相似（两两对比）───────────────────────────
    for i in range(n):
        for j in range(i+1, n):
            sim = _text_similarity(bids[i].text, bids[j].text)
            if sim >= 0.85:
                flags.append(CollusionFlag(
                    flag_type="文本高度雷同",
                    risk_level="高",
                    description=f"「{bids[i].filename}」与「{bids[j].filename}」文本相似度 {sim:.0%}（≥85%），疑似同一模板修改",
                    bids_involved=[bids[i].filename, bids[j].filename],
                    evidence=f"相似度：{sim:.1%}",
                ))
            elif sim >= 0.65:
                flags.append(CollusionFlag(
                    flag_type="文本相似度偏高",
                    risk_level="中",
                    description=f"「{bids[i].filename}」与「{bids[j].filename}」文本相似度 {sim:.0%}（正常竞争对手标书通常<50%）",
                    bids_involved=[bids[i].filename, bids[j].filename],
                    evidence=f"相似度：{sim:.1%}",
                ))

    # ── 6. 独特用词/句式相同 ──────────────────────────────────
    phrase_bid_map: Dict[str, List[str]] = {}
    for b in bids:
        for phrase in _find_unique_phrases(b.text, min_len=12):
            phrase_bid_map.setdefault(phrase, []).append(b.filename)
    shared_phrases = [(ph, files) for ph, files in phrase_bid_map.items() if len(files) > 1]
    if len(shared_phrases) >= 3:
        examples = [ph for ph, _ in shared_phrases[:3]]
        all_involved = list(set(f for _, files in shared_phrases for f in files))
        flags.append(CollusionFlag(
            flag_type="相同特征句式",
            risk_level="中",
            description=f"多份标书共享 {len(shared_phrases)} 处相同句式（≥12字），疑似共用模板",
            bids_involved=all_involved,
            evidence="如：" + "；".join(f'「{e[:20]}…」' for e in examples),
        ))

    # ── 7. 报价规律性（陪标特征：价格间隔固定比例）────────────
    prices = [(b.filename, b.price) for b in bids if b.price and b.price > 0]
    if len(prices) >= 3:
        sorted_prices = sorted(prices, key=lambda x: x[1])
        ratios = []
        for k in range(1, len(sorted_prices)):
            ratio = sorted_prices[k][1] / sorted_prices[k-1][1]
            ratios.append(ratio)
        # 若所有相邻报价比例相近（差值<5%），高度疑似设计好的价格梯度
        if ratios and max(ratios) - min(ratios) < 0.05 and abs(sum(ratios)/len(ratios) - 1.05) < 0.08:
            price_strs = ", ".join(f"¥{p:,.0f}" for _, p in sorted_prices)
            flags.append(CollusionFlag(
                flag_type="报价梯度规律",
                risk_level="高",
                description=f"各标书报价呈均匀梯度分布（{price_strs}），陪标特征明显",
                bids_involved=[f for f, _ in sorted_prices],
                evidence=f"价格比例：{', '.join(f'{r:.3f}' for r in ratios)}",
            ))

    return flags


# ═══════════════════════════════════════════════════════════════
# 综合评分 & 中标优势排名
# ═══════════════════════════════════════════════════════════════

def _score_fields(text: str) -> int:
    """关键字段完整性得分（0~100）"""
    from modules.format_check import check_field_completeness
    r = check_field_completeness(text)
    total = len(r.items)
    present = sum(1 for i in r.items if i.is_present)
    return int(present / total * 100) if total else 50


def _score_format(text: str) -> int:
    """格式规范性得分"""
    from modules.format_check import check_punctuation
    r = check_punctuation(text)
    deduct = sum(
        20 if i.risk_level == "中" else 5
        for i in r.issues
    )
    return max(0, 100 - deduct)


def _score_name_consistency(text: str) -> int:
    """名称一致性得分"""
    from modules.name_consistency import check_name_consistency
    r = check_name_consistency(text)
    if not r.issues:
        return 100
    deduct = sum(30 if i.risk_level == "高" else 15 for i in r.issues)
    return max(0, 100 - deduct)


def _score_qualification(text: str) -> int:
    """资质/有效期得分（基于是否含到期/过期词）"""
    from modules.validity_check import check_validity_from_text
    r = check_validity_from_text(text)
    if r.has_expired:
        return 30
    if r.has_urgent:
        return 70
    if r.total_found > 0:
        return 95
    return 80  # 未找到日期，中性


def _score_price_competitiveness(price: Optional[float], all_prices: List[float]) -> int:
    """价格竞争力得分：最低价得分最高，但需在合理范围内"""
    if not price or not all_prices:
        return 50
    valid = [p for p in all_prices if p > 0]
    if not valid:
        return 50
    min_p, max_p = min(valid), max(valid)
    if max_p == min_p:
        return 80
    # 价格排名：最低价100分，最高价20分（线性插值）
    rank_score = int(100 - (price - min_p) / (max_p - min_p) * 80)
    return max(10, min(100, rank_score))


def score_bids(bids: List[BidInfo]) -> List[BidScore]:
    all_prices = [b.price for b in bids if b.price]
    scored: List[BidScore] = []

    for b in bids:
        fs  = _score_fields(b.text)
        fmt = _score_format(b.text)
        ps  = _score_price_competitiveness(b.price, all_prices)
        qs  = _score_qualification(b.text)
        ns  = _score_name_consistency(b.text)

        # 加权总分：价格35% + 字段完整25% + 资质20% + 格式10% + 名称10%
        total = int(ps * 0.35 + fs * 0.25 + qs * 0.20 + fmt * 0.10 + ns * 0.10)

        strengths, weaknesses = [], []
        if ps >= 80:  strengths.append("💰 报价有竞争优势")
        elif ps < 40: weaknesses.append("💰 报价偏高，竞争力不足")
        if fs >= 90:  strengths.append("📋 关键字段完整")
        elif fs < 70: weaknesses.append("📋 关键字段缺失较多")
        if qs >= 90:  strengths.append("✅ 资质证件完善")
        elif qs < 60: weaknesses.append("⚠️ 资质存在过期或缺失")
        if fmt >= 90: strengths.append("📝 格式规范")
        elif fmt < 70: weaknesses.append("📝 格式问题较多")
        if ns == 100: strengths.append("🏷️ 名称前后一致")
        elif ns < 70:  weaknesses.append("🏷️ 公司名/法人前后不一致")

        if total >= 80:
            rec = "强烈推荐提交"
        elif total >= 65:
            rec = "建议修改后提交"
        elif total >= 50:
            rec = "需重点优化后提交"
        else:
            rec = "存在重大问题，建议全面修订"

        scored.append(BidScore(
            filename=b.filename,
            company=b.company or "（未识别）",
            price=b.price,
            format_score=fmt,
            field_score=fs,
            price_score=ps,
            qualification_score=qs,
            name_consistency_score=ns,
            total_score=total,
            rank=0,  # 后面排序后赋值
            strengths=strengths,
            weaknesses=weaknesses,
            recommendation=rec,
        ))

    # 按总分排序，赋 rank
    scored.sort(key=lambda s: s.total_score, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1

    return scored


def compare_bids(bid_data: List[Tuple[bytes, str, str, List[str]]]) -> CompareResult:
    """
    bid_data: list of (file_bytes, filename, extracted_text, pages_list)
    """
    bids = [extract_bid_info(fb, fn, txt, pages)
            for fb, fn, txt, pages in bid_data]

    collusion_flags = detect_collusion(bids)
    scores = score_bids(bids)

    # 确定串标风险等级
    high_flags = sum(1 for f in collusion_flags if f.risk_level == "高")
    mid_flags  = sum(1 for f in collusion_flags if f.risk_level == "中")
    if high_flags >= 2:
        collusion_risk = "高"
    elif high_flags >= 1 or mid_flags >= 2:
        collusion_risk = "中"
    elif mid_flags >= 1 or collusion_flags:
        collusion_risk = "低"
    else:
        collusion_risk = "无"

    # 冠军建议
    if scores:
        winner = scores[0]
        if collusion_risk in ("高", "中"):
            winner_rec = (f"⚠️ 注意：检测到串标/陪标风险信号，建议在提交前彻底核查。\n"
                          f"若排除串标风险，综合评分最高的标书为「{winner.filename}」（{winner.total_score}分）")
        else:
            winner_rec = (f"综合评分最高：「{winner.filename}」（{winner.total_score}分）\n"
                          f"公司：{winner.company}，报价：{'¥'+f'{winner.price:,.0f}' if winner.price else '未识别'}\n"
                          f"建议：{winner.recommendation}")
    else:
        winner_rec = "暂无足够数据作出推荐"

    return CompareResult(
        bids=bids,
        collusion_flags=collusion_flags,
        scores=scores,
        winner_recommendation=winner_rec,
        collusion_risk_level=collusion_risk,
    )
