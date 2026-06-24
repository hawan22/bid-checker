# -*- coding: utf-8 -*-
"""
字体/字号规范检查（Word 文档）
常见要求：
  正文   → 仿宋_GB2312 / 宋体，小四(12pt) / 三号(16pt)
  标题   → 黑体 / 方正小标宋，小二(18pt) / 三号(16pt)
  页眉   → 宋体，小五(9pt)
允许用户自定义预设；默认给出常见政府招标模板的规范建议。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ── 常见规范字体白名单 ────────────────────────────────────────
NORMAL_FONTS = {
    "仿宋", "仿宋_gb2312", "仿宋gb2312",
    "宋体", "simsun",
    "黑体", "simhei",
    "楷体", "楷体_gb2312", "kaiti",
    "微软雅黑", "microsoft yahei",
    "方正小标宋简体", "方正仿宋简体",
    "times new roman", "arial", "calibri",
}

# 正文推荐字号（磅值），常见：小四=12pt，三号=16pt，四号=14pt
BODY_FONT_SIZES_PT = {9, 10, 10.5, 11, 12, 14, 16}

# 明显异常字号（太大或太小用在正文里）
SUSPICIOUS_BODY_SIZE_THRESHOLD_LOW  = 8    # pt
SUSPICIOUS_BODY_SIZE_THRESHOLD_HIGH = 26   # pt（标题除外）


@dataclass
class FontIssue:
    issue_type: str        # "非标字体" / "字号异常" / "混用字体"
    description: str
    location: str          # "第N段" / "正文" 等
    suggestion: str
    risk_level: str = "低"  # 高/中/低


@dataclass
class FontCheckResult:
    font_stats: Dict[str, int]       # 字体 → 出现次数
    size_stats: Dict[str, int]       # 字号描述 → 出现次数
    issues: List[FontIssue]
    score: int
    summary: str


def _pt_to_desc(pt: float) -> str:
    mapping = {
        36: "一号", 32: "小一", 28: "二号", 24: "小二",
        21: "三号", 18: "小三", 16: "四号", 14: "小四",
        12: "五号", 10.5: "小五", 9: "六号", 7.5: "小六",
    }
    if pt is None:
        return "未知"
    # 找最近的
    closest = min(mapping.keys(), key=lambda k: abs(k - pt))
    if abs(closest - pt) < 1:
        return mapping[closest]
    return f"{pt:.1f}pt"


def _normalize_font(name: str) -> str:
    if not name:
        return ""
    return name.lower().replace(" ", "").replace("-", "")


def check_fonts(file_bytes: bytes, filename: str,
                text: str, pages: list) -> FontCheckResult:
    if not filename:
        filename = ""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in ("docx", "doc") or not file_bytes:
        return FontCheckResult(
            {}, {}, [],
            80,
            "ℹ️ 字体/字号规范检查仅支持 Word（.docx）文件"
        )

    try:
        import io
        from docx import Document
        from docx.shared import Pt
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        return FontCheckResult({}, {}, [], 60, f"❌ 无法解析 Word 文件：{e}")

    font_stats: Dict[str, int] = {}
    size_stats: Dict[str, int] = {}
    issues: List[FontIssue] = []

    non_std_fonts = set()
    suspicious_sizes = []   # (para_idx, size_pt, desc)
    mixed_font_paras = []   # 段落内字体混用

    for para_idx, para in enumerate(doc.paragraphs):
        if not para.text.strip():
            continue

        para_fonts = set()
        para_sizes = set()

        for run in para.runs:
            if not run.text.strip():
                continue
            fn = (run.font.name or para.style.font.name or "")
            fs = run.font.size  # EMU，转 pt
            fs_pt = (fs / 12700) if fs else None

            fn_norm = _normalize_font(fn)
            if fn:
                font_stats[fn] = font_stats.get(fn, 0) + 1
                para_fonts.add(fn_norm)
                if fn_norm and fn_norm not in NORMAL_FONTS:
                    non_std_fonts.add(fn)

            if fs_pt:
                desc = _pt_to_desc(fs_pt)
                size_stats[desc] = size_stats.get(desc, 0) + 1
                para_sizes.add(fs_pt)

                # 正文（非标题）字号异常
                style_name = (para.style.name or "").lower()
                is_heading = "heading" in style_name or "标题" in style_name
                if not is_heading:
                    if fs_pt < SUSPICIOUS_BODY_SIZE_THRESHOLD_LOW:
                        suspicious_sizes.append((para_idx + 1, fs_pt, desc))
                    elif fs_pt > SUSPICIOUS_BODY_SIZE_THRESHOLD_HIGH:
                        suspicious_sizes.append((para_idx + 1, fs_pt, desc))

        # 同一段落出现3种以上不同字体 → 混用
        if len(para_fonts) >= 3:
            mixed_font_paras.append((para_idx + 1, list(para_fonts)[:4]))

    # ── 生成 issues ──────────────────────────────────────────
    if non_std_fonts:
        fonts_str = "、".join(list(non_std_fonts)[:5])
        issues.append(FontIssue(
            "非标字体",
            f"使用了非常用字体：{fonts_str}",
            "全文",
            "政府招标文件建议使用仿宋、宋体、黑体等标准字体；特殊字体在其他电脑可能无法正确显示",
            "中"
        ))

    # 汇总可疑字号（去重按段落）
    if suspicious_sizes:
        unique_bad = {}
        for pidx, pt_val, desc in suspicious_sizes:
            unique_bad[desc] = unique_bad.get(desc, 0) + 1
        bad_str = "、".join(f"{d}({cnt}处)" for d, cnt in list(unique_bad.items())[:4])
        issues.append(FontIssue(
            "字号异常",
            f"正文中出现不常见字号：{bad_str}",
            "正文各处",
            "正文通常使用小四(12pt)或三号(16pt)，请检查是否存在格式混乱",
            "低"
        ))

    if mixed_font_paras:
        para_list = "、".join(f"第{p}段" for p, _ in mixed_font_paras[:3])
        issues.append(FontIssue(
            "同段混用字体",
            f"{para_list} 等出现3种以上字体混用，影响版式整洁",
            para_list,
            "统一同一段落的字体，避免复制粘贴带入异字体",
            "低"
        ))

    # ── 评分 ─────────────────────────────────────────────────
    if not issues:
        score = 100
        summary = f"✅ 字体规范（识别 {len(font_stats)} 种字体，无明显异常）"
    elif any(i.risk_level == "中" for i in issues):
        score = 75
        cnt = len(non_std_fonts)
        summary = f"⚠️ 含非标字体 {cnt} 种，建议替换后重新生成"
    else:
        score = 88
        summary = f"💡 字体规范有 {len(issues)} 项轻微提示，建议整理格式"

    return FontCheckResult(font_stats, size_stats, issues, score, summary)
