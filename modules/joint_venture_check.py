# -*- coding: utf-8 -*-
"""
联合体协议完整性检测
当标书提及"联合体"投标时，核查：
1. 是否有联合体协议（联合投标协议书）
2. 是否明确了牵头人（主办方）
3. 是否列出了所有成员单位
4. 是否所有成员单位都有签字/盖章页
5. 是否超出法规限制（超过2家联合限制等，仅提示）
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class JVIssue:
    issue_type: str
    description: str
    risk_level: str   # 高/中/低
    suggestion: str


@dataclass
class JVResult:
    is_joint_venture: bool        # 是否联合体投标
    members: List[str]            # 识别到的联合体成员
    has_agreement: bool           # 是否有联合协议
    has_lead_member: bool         # 是否有牵头人
    issues: List[JVIssue]
    score: int
    summary: str


# ── 联合体识别关键词 ─────────────────────────────────────────
_JV_TRIGGER = [
    "联合体", "联合投标", "联合体协议", "联合投标协议",
    "joint venture", "consortium",
]
_AGREEMENT_KW = [
    "联合体协议书", "联合投标协议书", "联合体投标协议",
    "联合协议", "联合体合同", "联合协议书",
]
_LEAD_KW = [
    "牵头人", "牵头单位", "主办方", "领衔单位",
    "联合体牵头", "lead member", "主体单位",
]
_MEMBER_PATTERN = re.compile(
    r'(?:联合体成员|成员单位|参与方|联合方)[：:]\s*(.+?)(?:\n|；|;|，和|$)',
    re.IGNORECASE
)
# 常见公司/机构后缀，用来捞成员名
_COMPANY_PAT = re.compile(
    r'[（(]?(?:[\u4e00-\u9fff]{2,15}(?:公司|集团|研究院|设计院|工程局|建设局|有限|股份|事业部|中心)){1}[）)]?'
)


def _find_members(text: str) -> List[str]:
    members = []
    for m in _MEMBER_PATTERN.finditer(text):
        raw = m.group(1).strip()
        parts = re.split(r'[，,、；;]+', raw)
        for p in parts:
            p = p.strip()
            if 2 <= len(p) <= 30:
                members.append(p)
    return list(dict.fromkeys(members))  # 去重保序


def _check_signatures_for_members(text: str, members: List[str]) -> List[str]:
    """检查每个成员单位是否有对应的签字/盖章上下文"""
    missing = []
    for member in members:
        # 查该成员名附近是否有"签字/盖章/法定代表人"字样
        pattern = re.compile(
            re.escape(member) + r'.{0,80}(?:签字|盖章|法定代表|授权代表|签名)',
            re.DOTALL
        )
        pattern2 = re.compile(
            r'(?:签字|盖章|法定代表|授权代表).{0,80}' + re.escape(member),
            re.DOTALL
        )
        if not pattern.search(text) and not pattern2.search(text):
            missing.append(member)
    return missing


def check_joint_venture(file_bytes: bytes, filename: str,
                         text: str, pages: list) -> JVResult:
    full_text = text or "\n".join(pages) if pages else ""
    if not full_text:
        return JVResult(False, [], False, False, [], 80,
                        "ℹ️ 无文本内容，跳过联合体检测")

    # ── 是否联合体投标 ────────────────────────────────────────
    is_jv = any(kw in full_text for kw in _JV_TRIGGER)
    if not is_jv:
        return JVResult(False, [], False, False, [], 100,
                        "✅ 未检测到联合体投标，无需核查联合体协议")

    issues: List[JVIssue] = []

    # ── 联合体协议 ────────────────────────────────────────────
    has_agreement = any(kw in full_text for kw in _AGREEMENT_KW)
    if not has_agreement:
        issues.append(JVIssue(
            "缺少联合体协议书",
            "文档中提到联合体投标，但未找到联合体协议书/联合投标协议书",
            "高",
            "联合体投标必须附《联合投标协议书》，并由所有成员盖章，否则废标"
        ))

    # ── 牵头人 ────────────────────────────────────────────────
    has_lead = any(kw in full_text for kw in _LEAD_KW)
    if not has_lead:
        issues.append(JVIssue(
            "未明确联合体牵头人",
            "未在文档中找到牵头人/主办方的明确表述",
            "高",
            "联合体协议须明确牵头人（主办方），由其代表联合体递交投标文件并签订合同"
        ))

    # ── 识别成员 ─────────────────────────────────────────────
    members = _find_members(full_text)
    if not members:
        # 降级：用公司名模式捞
        members = list(dict.fromkeys(
            m.group(0).strip() for m in _COMPANY_PAT.finditer(full_text)
            if len(m.group(0)) >= 5
        ))[:6]  # 最多取6个

    # ── 签字/盖章核查 ─────────────────────────────────────────
    if members:
        missing_sig = _check_signatures_for_members(full_text, members)
        if missing_sig:
            ms_str = "、".join(missing_sig[:3])
            issues.append(JVIssue(
                "成员单位签字/盖章不完整",
                f"以下成员未找到对应签字/盖章记录：{ms_str}",
                "高",
                "所有联合体成员均须在协议书及投标函上签字盖章"
            ))
    else:
        issues.append(JVIssue(
            "无法识别联合体成员",
            "未能从文档中提取联合体成员单位名称",
            "中",
            "请确认联合体成员列表已在协议书中明确列出"
        ))

    # ── 成员数量提示 ─────────────────────────────────────────
    if len(members) > 3:
        issues.append(JVIssue(
            "联合体成员数量提示",
            f"识别到 {len(members)} 个成员，部分招标文件限制联合体成员不超过2家",
            "中",
            "请核对招标文件中对联合体成员数量的限制条款"
        ))

    # ── 评分 ─────────────────────────────────────────────────
    high_cnt = sum(1 for i in issues if i.risk_level == "高")
    if not issues:
        score = 95
        summary = f"✅ 联合体协议完整（识别成员 {len(members)} 家，牵头人已明确）"
    elif high_cnt >= 2:
        score = 30
        summary = f"🔴 联合体协议存在 {high_cnt} 处严重缺失，废标风险极高"
    elif high_cnt == 1:
        score = 55
        summary = f"🟠 联合体协议存在关键缺项，请补充完善"
    else:
        score = 75
        summary = f"⚠️ 联合体协议有 {len(issues)} 处提示，建议核查"

    return JVResult(True, members, has_agreement, has_lead, issues, score, summary)
