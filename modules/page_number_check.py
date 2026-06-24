# -*- coding: utf-8 -*-
"""
页码连续性检测
- PDF: 提取每页底部/顶部的数字，判断页码是否连续
- Word: python-docx 目前无法直接读取域代码页码，仅作提示
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PageNumIssue:
    issue_type: str       # "页码跳断" / "页码重复" / "页码缺失" / "无页码"
    description: str
    pages: List[int]      # 涉及的物理页（1-based）
    suggestion: str
    risk_level: str = "中"  # 高/中/低


@dataclass
class PageNumResult:
    detected_numbers: List[Optional[int]]  # 每页识别到的逻辑页码（None=未识别）
    issues: List[PageNumIssue]
    score: int
    summary: str


def _strip_numbers(text: str) -> List[int]:
    """从一段文本中提取所有纯数字（1–999），过滤干扰词"""
    # 去掉常见非页码前缀（年份4位、邮编等）
    nums = re.findall(r'(?<!\d)(\d{1,3})(?!\d)', text)
    return [int(n) for n in nums if 1 <= int(n) <= 999]


def _extract_page_number_from_strip(text: str) -> Optional[int]:
    """
    从页面顶部或底部 strip 的文本里猜测页码。
    返回最可能的页码，无法判断返回 None。
    """
    text = text.strip()
    # 匹配 "第N页" 或 "- N -" 或 "N / M" 或行末/行首孤立数字
    for pat in [
        r'第\s*(\d{1,3})\s*页',
        r'[－\-]\s*(\d{1,3})\s*[－\-]',
        r'(\d{1,3})\s*/\s*\d{1,3}',  # "3/20"
        r'(?:^|\n)\s*(\d{1,3})\s*(?:\n|$)',  # 独占一行
        r'Page\s+(\d{1,3})',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    # 最后尝试：整个 strip 就是一个数字
    nums = _strip_numbers(text)
    if len(nums) == 1:
        return nums[0]
    return None


def _check_pdf(file_bytes: bytes) -> PageNumResult:
    import fitz  # PyMuPDF
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    n_pages = len(doc)
    if n_pages == 0:
        return PageNumResult([], [], 60, "PDF 无页面")

    detected: List[Optional[int]] = []
    for i, page in enumerate(doc):
        rect = page.rect
        # 先试底部15%，再试顶部10%
        strips = [
            fitz.Rect(rect.x0, rect.y1 * 0.85, rect.x1, rect.y1),
            fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + rect.height * 0.10),
        ]
        pn = None
        for strip in strips:
            clip_text = page.get_text("text", clip=strip).strip()
            pn = _extract_page_number_from_strip(clip_text)
            if pn is not None:
                break
        detected.append(pn)

    issues: List[PageNumIssue] = []

    # 统计识别率
    found = [p for p in detected if p is not None]
    recognition_rate = len(found) / n_pages if n_pages else 0

    if recognition_rate < 0.3:
        issues.append(PageNumIssue(
            "无页码",
            f"仅在 {len(found)}/{n_pages} 页识别到页码，可能未添加页码或页码为图片",
            [],
            "建议在 Word 中插入自动页码域后重新生成 PDF",
            "低"
        ))
        score = 75
        summary = f"⚠️ 页码识别率低（{len(found)}/{n_pages} 页），可能无页码或图片页码"
        return PageNumResult(detected, issues, score, summary)

    # 找连续段（只看能识别的页码）
    indexed = [(i + 1, pn) for i, pn in enumerate(detected) if pn is not None]
    gaps, duplicates = [], []
    for k in range(1, len(indexed)):
        phys_prev, num_prev = indexed[k - 1]
        phys_curr, num_curr = indexed[k]
        diff = num_curr - num_prev
        if diff == 0:
            duplicates.append((phys_prev, phys_curr, num_curr))
        elif diff < 0:
            gaps.append((phys_prev, phys_curr, num_prev, num_curr))
        elif diff > 2:  # 允许中间有1页不可识别
            gaps.append((phys_prev, phys_curr, num_prev, num_curr))

    if duplicates:
        for p1, p2, num in duplicates:
            issues.append(PageNumIssue(
                "页码重复",
                f"第 {p1} 页和第 {p2} 页逻辑页码均为 {num}",
                [p1, p2],
                "检查是否有章节重置页码或插入了重复节",
                "高"
            ))
    if gaps:
        for p1, p2, n1, n2 in gaps:
            issues.append(PageNumIssue(
                "页码跳断",
                f"第 {p1} 页页码={n1}，第 {p2} 页页码={n2}，中间跳过 {n2-n1-1} 个编号",
                [p1, p2],
                "检查是否删除了页面或分节导致页码不连续",
                "中"
            ))

    if not issues:
        score = 100
        summary = f"✅ 页码连续（识别 {len(found)}/{n_pages} 页，无跳断或重复）"
    else:
        score = max(40, 100 - len(issues) * 20)
        summary = f"⚠️ 发现 {len(issues)} 处页码异常（共识别 {len(found)}/{n_pages} 页）"

    return PageNumResult(detected, issues, score, summary)


def check_page_numbers(file_bytes: bytes, filename: str,
                        text: str, pages: list) -> PageNumResult:
    if not filename:
        filename = ""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf" and file_bytes:
        return _check_pdf(file_bytes)

    if ext in ("docx", "doc"):
        # python-docx 无法直接读取域码页码值，给出通用建议
        return PageNumResult(
            [], [],
            80,
            "ℹ️ Word 文件页码连续性需转为 PDF 后检测（当前仅支持 PDF）"
        )

    return PageNumResult([], [], 80, "ℹ️ 页码连续性检测仅支持 PDF 文件")
