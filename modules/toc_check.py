"""
目录完整性核查模块
① 提取文档目录（Word TOC / PDF 目录页）
② 核查必填章节是否存在
③ 检测目录条目在正文中是否有对应标题
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

try:
    from docx import Document
    from docx.oxml.ns import qn
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

try:
    import fitz
    FITZ_OK = True
except ImportError:
    FITZ_OK = False


# ─── 数据结构 ──────────────────────────────────────────────────

@dataclass
class TocEntry:
    title: str
    level: int          # 1=一级, 2=二级
    page_ref: str       # 目录中的页码引用（可能为空）
    found_in_body: bool = False   # 正文中是否有对应标题


@dataclass
class RequiredSection:
    name: str
    aliases: List[str]  # 可能的其他写法
    required: bool      # True=必填, False=建议
    category: str       # 商务/技术/报价/资质


@dataclass
class TocCheckResult:
    toc_entries: List[TocEntry] = field(default_factory=list)
    missing_required: List[RequiredSection] = field(default_factory=list)
    missing_suggested: List[RequiredSection] = field(default_factory=list)
    orphan_entries: List[TocEntry] = field(default_factory=list)  # 目录有但正文无
    problems: List[str] = field(default_factory=list)
    summary: str = ""
    has_toc: bool = False
    score: int = 100


# ─── 必填章节库（通用招投标）────────────────────────────────────

REQUIRED_SECTIONS: List[RequiredSection] = [
    # 商务标必填
    RequiredSection("投标函",        ["投标函","投标书","投标申请"], True,  "商务"),
    RequiredSection("法定代表人授权书", ["法定代表人授权书","授权委托书","授权书"], True, "商务"),
    RequiredSection("营业执照",       ["营业执照","营业执照副本","企业营业执照"], True, "商务"),
    RequiredSection("报价单/报价表",  ["报价单","报价表","投标报价","价格表","报价汇总"], True, "报价"),
    RequiredSection("投标保证金",     ["投标保证金","保证金","投标担保"], False, "商务"),
    # 资质类（建议）
    RequiredSection("资质证书",       ["资质证书","资质等级证书","建筑业企业资质"], False, "资质"),
    RequiredSection("业绩证明材料",   ["业绩","合同业绩","类似业绩","工程业绩"], False, "资质"),
    RequiredSection("项目负责人",     ["项目负责人","项目经理","项目总监"], False, "资质"),
    # 技术标（建议）
    RequiredSection("技术方案",       ["技术方案","技术响应","技术规格响应表"], False, "技术"),
    RequiredSection("售后服务",       ["售后服务","维保","保修","服务承诺"], False, "技术"),
]


# ─── 目录提取 ─────────────────────────────────────────────────

def _extract_toc_from_word(file_bytes: bytes) -> List[TocEntry]:
    """从 Word 文档提取目录（TOC 域或目录样式段落）"""
    if not DOCX_OK:
        return []
    import io
    try:
        doc = Document(io.BytesIO(file_bytes))
        entries = []
        ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

        for para in doc.paragraphs:
            style = para.style.name if para.style else ""
            text = para.text.strip()
            if not text:
                continue

            # TOC 样式（目录1、目录2、TOC 1、TOC 2等）
            if re.match(r'(目录|TOC)\s*\d', style, re.IGNORECASE):
                level = int(re.search(r'\d', style).group()) if re.search(r'\d', style) else 1
                # 提取页码（通常在tab后面）
                parts = re.split(r'\t', text)
                title = parts[0].strip()
                page_ref = parts[-1].strip() if len(parts) > 1 else ""
                entries.append(TocEntry(title=title, level=level, page_ref=page_ref))

            # 标题样式（Heading 1/2 或 标题1/2）- 也作为结构信息
            elif re.match(r'(Heading|标题)\s*[12]', style, re.IGNORECASE):
                level = 1 if '1' in style else 2
                entries.append(TocEntry(title=text, level=level, page_ref=""))

        return entries
    except Exception:
        return []


def _extract_toc_from_pdf(text: str, pages: List[str]) -> List[TocEntry]:
    """从 PDF 文本中识别目录页"""
    entries = []
    # 目录页特征：行末有数字（页码），行首有章节编号或常见标题词
    toc_line_pattern = re.compile(
        r'^([一二三四五六七八九十\d]+[、.\s]*[\u4e00-\u9fa5a-zA-Z（）]{2,40})\s*[.…\s]*(\d{1,3})\s*$',
        re.MULTILINE
    )
    # 找目录页（含多行"标题 + 页码"格式的页）
    for i, page_text in enumerate(pages[:10]):  # 只看前10页
        matches = toc_line_pattern.findall(page_text)
        if len(matches) >= 3:   # 至少3行才认为是目录页
            for title, page_num in matches:
                title = title.strip()
                level = 1 if re.match(r'^[一二三四五六七八九十\d]+[、.]', title) else 2
                entries.append(TocEntry(title=title, level=level, page_ref=page_num))
            break   # 只取第一个目录页
    return entries


def _extract_toc_from_text(text: str) -> List[TocEntry]:
    """从纯文本中识别章节标题（无明确目录时）"""
    entries = []
    heading_pattern = re.compile(
        r'^(?:第[一二三四五六七八九十百\d]+[章节部分]|[一二三四五六七八九十]+[、.]|\d+\.)\s*'
        r'([\u4e00-\u9fa5a-zA-Z（）]{2,30})',
        re.MULTILINE
    )
    seen = set()
    for m in heading_pattern.finditer(text):
        title = m.group(0).strip()
        if title not in seen:
            seen.add(title)
            entries.append(TocEntry(title=title, level=1, page_ref=""))
    return entries[:50]  # 限制数量


# ─── 核查逻辑 ─────────────────────────────────────────────────

def _check_title_in_body(title: str, body_text: str) -> bool:
    """检查章节标题是否出现在正文中"""
    # 去除数字编号，只比对关键词
    clean = re.sub(r'^[一二三四五六七八九十\d]+[、.\s]*', '', title).strip()
    if len(clean) < 2:
        return True   # 太短无法判断，认为存在
    return clean in body_text


def _check_required_sections(text: str) -> Tuple[List[RequiredSection], List[RequiredSection]]:
    """检查必填/建议章节是否存在"""
    missing_req = []
    missing_sug = []
    for section in REQUIRED_SECTIONS:
        found = any(alias in text for alias in section.aliases)
        if not found:
            if section.required:
                missing_req.append(section)
            else:
                missing_sug.append(section)
    return missing_req, missing_sug


# ─── 主入口 ───────────────────────────────────────────────────

def check_toc(
    file_bytes: bytes,
    filename: str,
    text: str,
    pages: List[str] = None,
) -> TocCheckResult:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    result = TocCheckResult()

    # ① 提取目录
    if ext in ("docx", "doc") and file_bytes and DOCX_OK:
        result.toc_entries = _extract_toc_from_word(file_bytes)
    elif ext == "pdf" and pages:
        result.toc_entries = _extract_toc_from_pdf(text, pages)

    if not result.toc_entries and text:
        result.toc_entries = _extract_toc_from_text(text)

    result.has_toc = len(result.toc_entries) >= 3

    # ② 检查目录条目在正文中是否有对应
    if result.toc_entries and text:
        for entry in result.toc_entries:
            entry.found_in_body = _check_title_in_body(entry.title, text)
        result.orphan_entries = [e for e in result.toc_entries if not e.found_in_body]

    # ③ 检查必填/建议章节
    if text:
        result.missing_required, result.missing_suggested = _check_required_sections(text)

    # ④ 构建问题列表 & 评分
    score = 100
    for sec in result.missing_required:
        result.problems.append(f"🔴 必填章节缺失：「{sec.name}」（{sec.category}）")
        score -= 20
    for sec in result.missing_suggested[:3]:  # 建议类只报前3条
        result.problems.append(f"🟠 建议章节缺失：「{sec.name}」（{sec.category}）")
        score -= 5
    for entry in result.orphan_entries[:5]:
        result.problems.append(f"🟡 目录中有「{entry.title}」但正文未找到对应章节")
        score -= 8
    result.score = max(0, score)

    # ⑤ 生成 summary
    n_req = len(result.missing_required)
    n_sug = len(result.missing_suggested)
    n_orp = len(result.orphan_entries)
    n_toc = len(result.toc_entries)

    if n_req == 0 and n_orp == 0:
        if n_toc == 0:
            result.summary = "⚠️ 未识别到目录结构，建议人工核查章节完整性"
        else:
            result.summary = f"✅ 目录结构完整（{n_toc}个条目），必填章节均已找到"
            if n_sug:
                result.summary += f"，{n_sug}个建议章节缺失"
    else:
        parts = []
        if n_req: parts.append(f"🔴 必填章节缺失 {n_req} 项")
        if n_orp: parts.append(f"🟡 目录与正文不符 {n_orp} 项")
        if n_sug: parts.append(f"🟠 建议章节缺失 {n_sug} 项")
        result.summary = "、".join(parts)

    # ⑥ 附件与目录对应核查
    if text and result.toc_entries:
        attachment_issues = _check_attachments_vs_toc(text, result.toc_entries)
        for ai in attachment_issues:
            result.problems.append(ai)
            result.score = max(0, result.score - 5)

    return result


# ── 附件与目录对应核查 ─────────────────────────────────────────

_ATTACHMENT_KEYWORDS = [
    "附件", "附表", "附录", "附图",
    "Attachment", "Annex", "Appendix",
]
_ATTACHMENT_PAT = re.compile(
    r'(?:附件|附表|附录|附图)\s*[一二三四五六七八九十\d]+\s*[：:、\s]*(.+?)(?:\n|$)',
    re.IGNORECASE
)


def _check_attachments_vs_toc(text: str, toc_entries: List[TocEntry]) -> List[str]:
    """
    从目录中找附件类条目，检查正文中是否有对应内容。
    返回问题描述列表。
    """
    issues = []
    # 找目录里的附件条目
    attachment_entries = [
        e for e in toc_entries
        if any(kw in e.title for kw in _ATTACHMENT_KEYWORDS)
    ]
    for entry in attachment_entries:
        if not entry.found_in_body:
            issues.append(f"🟡 目录附件「{entry.title}」在正文中未找到对应内容")

    # 反向：正文提到的附件，在目录里是否有登记
    for m in _ATTACHMENT_PAT.finditer(text[:8000]):  # 只扫前8000字符
        name = m.group(1).strip()[:30]
        if name and not any(name in e.title or e.title in name
                            for e in toc_entries):
            issues.append(f"💡 正文提到附件「{name}」但目录中未单独列出")

    return issues[:5]  # 最多报5条
