"""
综合诊断报告生成器
一次扫描，汇总所有检查模块结果
输出：总分 + 优势 + 问题（按严重度排序）+ 改进建议
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import date


# ─── 数据结构 ──────────────────────────────────────────────────

@dataclass
class ReportItem:
    category: str        # 所属类别（签章/资质/格式/报价/…）
    severity: str        # 严重: 高/中/低/优势
    title: str           # 简短标题
    detail: str          # 详细说明
    location: str        # 精确位置（第N页/行，或"全文"）
    suggestion: str      # 针对这一项的修改建议
    icon: str            # 显示图标


@dataclass
class DiagnosticReport:
    filename: str
    scan_date: str
    total_score: int          # 0~100
    score_breakdown: Dict[str, int]  # 维度 → 分数
    strengths: List[ReportItem]
    issues_high: List[ReportItem]
    issues_mid: List[ReportItem]
    issues_low: List[ReportItem]
    top_suggestions: List[str]   # 最优先要改的3~5条
    summary_text: str            # 一句话总结


# ─── 主函数 ───────────────────────────────────────────────────

def generate_report(
    file_bytes: bytes,
    filename: str,
    text: str,
    pages: List[str],
) -> DiagnosticReport:
    """运行所有检查模块，汇总为诊断报告"""

    items: List[ReportItem] = []
    score_breakdown = {}

    # ── 1. 文件命名 ──────────────────────────────────────────
    try:
        from modules.naming_check import check_filename
        nm = check_filename(filename)
        if nm.is_safe:
            items.append(ReportItem("文件命名", "优势", "✅ 文件命名规范",
                f"文件名「{nm.filename}」无非法字符，符合电子招标平台要求",
                "文件名", "", "📂"))
            score_breakdown["文件命名"] = 100
        else:
            for p in nm.problems:
                items.append(ReportItem("文件命名", "高", "文件命名不规范",
                    p, "文件名",
                    "；".join(nm.suggestions) if nm.suggestions else "修改文件名",
                    "📂"))
            score_breakdown["文件命名"] = max(0, 100 - len(nm.problems) * 30)
    except Exception:
        pass

    # ── 2. 废标关键词 ────────────────────────────────────────
    if text.strip():
        try:
            from modules.keyword_scan import scan_keywords
            kw = scan_keywords(text, pages)
            score_breakdown["废标关键词"] = max(0, 100 - kw.high_risk * 25 - kw.medium_risk * 10)
            if kw.total_hits == 0:
                items.append(ReportItem("废标关键词", "优势", "✅ 未命中废标关键词",
                    "全文未出现联合体/图片章/CA证书过期/串通投标等高频废标触发词",
                    "全文", "", "🔑"))
            else:
                for h in kw.hits[:10]:  # 最多取10条
                    sev = "高" if h.risk_level == "高" else "中"
                    items.append(ReportItem("废标关键词", sev,
                        f"关键词「{h.keyword}」（{h.category}）",
                        h.context[:80],
                        h.location,
                        f"核查「{h.keyword}」相关内容，确认是否符合招标要求",
                        "🔑"))
        except Exception:
            pass

    # ── 3. 资质有效期 ────────────────────────────────────────
    if text.strip():
        try:
            from modules.validity_check import check_validity_from_text
            val = check_validity_from_text(text)
            if val.has_expired:
                score_breakdown["资质有效期"] = 30
                for h in val.hits:
                    if h.days_remaining < 0:
                        items.append(ReportItem("资质有效期", "高",
                            f"证件已过期：{h.raw_text}",
                            f"{h.location}，过期 {-h.days_remaining} 天（到期：{h.date}）",
                            h.location,
                            "立即更新该证件，或在开标前取得有效期内的新证",
                            "📅"))
                for h in val.hits:
                    if 0 <= h.days_remaining < 90:
                        items.append(ReportItem("资质有效期", "中",
                            f"证件即将过期：{h.raw_text}",
                            f"{h.location}，剩余 {h.days_remaining} 天（到期：{h.date}）",
                            h.location,
                            "开标前核查证件有效期是否覆盖合同履约期",
                            "📅"))
            elif val.has_urgent:
                score_breakdown["资质有效期"] = 70
                items.append(ReportItem("资质有效期", "中", "部分证件即将过期",
                    f"共发现 {val.total_found} 个日期，有效期不足90天",
                    "见有效期Tab", "提前续签证件", "📅"))
            else:
                score_breakdown["资质有效期"] = 100
                if val.total_found > 0:
                    items.append(ReportItem("资质有效期", "优势", "✅ 资质证件有效",
                        f"共检查 {val.total_found} 个日期，均在有效期内",
                        "全文", "", "📅"))
        except Exception:
            pass

    # ── 4. 日期逻辑 ──────────────────────────────────────────
    if text.strip():
        try:
            from modules.date_logic import analyze_date_logic
            dl = analyze_date_logic(text, pages)
            if dl.issues:
                score_breakdown["日期逻辑"] = max(0, 100 - len(dl.issues) * 30)
                for issue in dl.issues:
                    items.append(ReportItem("日期逻辑", issue.risk_level,
                        issue.description.split("】")[0].lstrip("【") if "】" in issue.description else issue.description[:30],
                        issue.description,
                        f"{issue.date_a.location} & {issue.date_b.location}",
                        "核查并修正相关日期，确保授权日期≤开标日期，证件有效期≥开标日期",
                        "🗓️"))
            else:
                score_breakdown["日期逻辑"] = 100
                if dl.entries:
                    items.append(ReportItem("日期逻辑", "优势", "✅ 日期逻辑无矛盾",
                        f"提取 {len(dl.entries)} 个日期，授权/截止/有效期时序正确",
                        "全文", "", "🗓️"))
        except Exception:
            pass

    # ── 5. 名称一致性 ────────────────────────────────────────
    if text.strip():
        try:
            from modules.name_consistency import check_name_consistency
            nc = check_name_consistency(text, pages)
            if nc.issues:
                score_breakdown["名称一致性"] = max(0, 100 - len(nc.issues) * 25)
                for issue in nc.issues:
                    items.append(ReportItem("名称一致性", issue.risk_level,
                        f"{issue.entity_type}前后不一致",
                        issue.description,
                        "见名称一致性检查",
                        f"统一全文{issue.entity_type}写法，以营业执照为准",
                        "🏷️"))
            else:
                score_breakdown["名称一致性"] = 100
                if nc.entities:
                    items.append(ReportItem("名称一致性", "优势", "✅ 名称前后一致",
                        f"公司名/法人/项目名全文一致（共 {len(nc.entities)} 处）",
                        "全文", "", "🏷️"))
        except Exception:
            pass

    # ── 6. 标点与格式 ────────────────────────────────────────
    if text.strip():
        try:
            from modules.format_check import check_punctuation, check_date_format, check_field_completeness
            pr = check_punctuation(text)
            fmt_score = max(0, 100 - sum(20 if i.risk_level=="中" else 5 for i in pr.issues))
            dfr = check_date_format(text)
            if not dfr.is_consistent:
                fmt_score = max(0, fmt_score - 10)
            score_breakdown["格式规范"] = fmt_score

            if not pr.issues and dfr.is_consistent:
                items.append(ReportItem("格式规范", "优势", "✅ 格式标准规范",
                    "标点符号、日期格式均符合规范", "全文", "", "📝"))
            else:
                for issue in pr.issues:
                    if issue.risk_level == "中":
                        items.append(ReportItem("格式规范", "中",
                            f"标点问题：{issue.issue_type}",
                            issue.description,
                            "全文",
                            f"建议：{issue.description.split('（建议')[1].rstrip('）') if '（建议' in issue.description else '参见格式检查Tab'}",
                            "📝"))
                    else:
                        items.append(ReportItem("格式规范", "低",
                            f"格式提示：{issue.issue_type}",
                            issue.description, "全文", "可酌情修改", "📝"))
                if not dfr.is_consistent and len(dfr.formats_found) > 1:
                    minority = [f for f in dfr.formats_found if f != dfr.dominant_format]
                    items.append(ReportItem("格式规范", "低",
                        f"日期格式混用（{len(dfr.formats_found)}种）",
                        f"主流格式「{dfr.dominant_format}」，另有「{'、'.join(minority[:2])}」",
                        "全文",
                        f"统一使用「{dfr.dominant_format}」",
                        "📝"))

            # 关键字段
            fcr = check_field_completeness(text)
            field_score = int(sum(1 for i in fcr.items if i.is_present) / len(fcr.items) * 100)
            score_breakdown["关键字段"] = field_score
            missing_high = [i for i in fcr.items if not i.is_present and i.risk_level == "高"]
            missing_mid  = [i for i in fcr.items if not i.is_present and i.risk_level == "中"]
            if missing_high:
                for item in missing_high:
                    hint = next((h for n,_,_,h in __import__('modules.format_check', fromlist=['REQUIRED_FIELDS']).REQUIRED_FIELDS if n == item.field_name), "")
                    items.append(ReportItem("关键字段", "高",
                        f"缺少「{item.field_name}」",
                        hint, "全文",
                        f"在标书相应位置补充「{item.field_name}」",
                        "📋"))
            elif missing_mid:
                for item in missing_mid:
                    items.append(ReportItem("关键字段", "中",
                        f"建议补充「{item.field_name}」",
                        "未识别到该字段，可能缺失", "全文",
                        f"建议在标书中明确填写「{item.field_name}」",
                        "📋"))
            else:
                items.append(ReportItem("关键字段", "优势", "✅ 关键字段完整",
                    "项目编号/法人/报价合计等关键字段均已找到",
                    "全文", "", "📋"))
        except Exception:
            pass

    # ── 7. 签章 ──────────────────────────────────────────────
    if file_bytes and filename.lower().endswith('.pdf'):
        try:
            from modules.seal_check import check_seal
            sr = check_seal(file_bytes, filename)
            if sr.digital_sig_count and sr.digital_sig_count > 0:
                score_breakdown["签章"] = 100
                items.append(ReportItem("签章", "优势", f"✅ 含 {sr.digital_sig_count} 个数字签名",
                    "检测到合规CA数字签名域", "PDF签名域", "", "🔏"))
            else:
                score_breakdown["签章"] = 50
                items.append(ReportItem("签章", "中", "未检测到CA数字签名",
                    "PDF中无合规数字签名域，若平台要求CA签章则可能废标",
                    "全文", "使用CA证书/UKey对PDF进行数字签章", "🔏"))
        except Exception:
            pass

    # ── 8. 模板残留 & 修订痕迹 ──────────────────────────────
    try:
        from modules.template_check import check_template_and_revisions
        tr = check_template_and_revisions(file_bytes, filename, text, pages)
        total_tr = len(tr.placeholder_hits) + len(tr.revision_hits) + len(tr.annotation_hits)
        score_breakdown["模板残留"] = max(0, 100 - total_tr * 20)
        if total_tr == 0:
            items.append(ReportItem("模板残留", "优势", "✅ 无模板残留/修订痕迹",
                "未发现占位符、修订痕迹或批注遗留", "全文", "", "📝"))
        else:
            for h in tr.placeholder_hits[:5]:
                items.append(ReportItem("模板残留", h.risk_level,
                    f"模板占位符未替换：「{h.content[:25]}」",
                    f"{h.location} 发现未替换的占位符",
                    h.location, h.suggestion, "📝"))
            for h in tr.revision_hits:
                items.append(ReportItem("模板残留", "高",
                    f"修订痕迹遗留：{h.content[:40]}",
                    "评标方可看到修改过程，影响专业形象，存在信息泄露风险",
                    h.location, h.suggestion, "✏️"))
            for h in tr.annotation_hits:
                items.append(ReportItem("模板残留", "中",
                    f"PDF批注未清除：{h.content[:40]}",
                    "批注中可能含有不应公开的内部备注",
                    h.location, h.suggestion, "💬"))
    except Exception:
        pass

    # ── 9. 目录完整性 ────────────────────────────────────────
    try:
        from modules.toc_check import check_toc
        toc_r = check_toc(file_bytes, filename, text, pages)
        score_breakdown["目录完整性"] = toc_r.score
        if not toc_r.missing_required and not toc_r.orphan_entries:
            if toc_r.toc_entries:
                items.append(ReportItem("目录完整性", "优势", "✅ 目录结构完整",
                    f"识别到 {len(toc_r.toc_entries)} 个章节，必填项均已包含",
                    "全文", "", "📑"))
        else:
            for sec in toc_r.missing_required:
                items.append(ReportItem("目录完整性", "高",
                    f"必填章节缺失：「{sec.name}」",
                    f"{sec.category}标中「{sec.name}」是必要组成部分",
                    "全文", f"补充「{sec.name}」章节及相关材料", "📑"))
            for entry in toc_r.orphan_entries[:3]:
                items.append(ReportItem("目录完整性", "中",
                    f"目录与正文不对应：「{entry.title}」",
                    "目录中列出该章节但正文未找到对应内容",
                    "目录页", "核查并补全正文对应章节，或删除目录中多余条目", "📑"))
    except Exception:
        pass

    # ── 10. 页眉页脚一致性 ────────────────────────────────────
    try:
        from modules.header_footer_check import check_header_footer
        hf_r = check_header_footer(file_bytes, filename, text, pages)
        score_breakdown["页眉页脚"] = hf_r.score
        if not hf_r.issues:
            if hf_r.headers or hf_r.footers:
                items.append(ReportItem("页眉页脚", "优势", "✅ 页眉页脚内容一致",
                    "各节页眉/页脚与正文内容吻合，无公司名/项目名不符",
                    "全文", "", "📄"))
        else:
            for issue in hf_r.issues:
                items.append(ReportItem("页眉页脚", issue.risk_level,
                    issue.issue_type,
                    issue.description[:80],
                    "、".join(issue.locations[:2]),
                    issue.suggestion, "📄"))
    except Exception:
        pass

    # ── 11. 联合体协议完整性 ──────────────────────────────────
    try:
        from modules.joint_venture_check import check_joint_venture
        jv_r = check_joint_venture(file_bytes, filename, text, pages)
        if jv_r.is_joint_venture:
            score_breakdown["联合体协议"] = jv_r.score
            if not jv_r.issues:
                items.append(ReportItem("联合体协议", "优势", "✅ 联合体协议完整",
                    f"识别成员 {len(jv_r.members)} 家，牵头人及签章齐全",
                    "联合体协议书", "", "🤝"))
            else:
                for issue in jv_r.issues:
                    items.append(ReportItem("联合体协议", issue.risk_level,
                        issue.issue_type, issue.description,
                        "联合体协议书", issue.suggestion, "🤝"))
    except Exception:
        pass

    # ── 12. 金额交叉核对 ─────────────────────────────────────
    try:
        from modules.amount_cross_check import check_amount_cross
        am_r = check_amount_cross(file_bytes, filename, text, pages)
        score_breakdown["金额一致性"] = am_r.score
        if not am_r.issues and am_r.all_amounts:
            items.append(ReportItem("金额一致性", "优势", "✅ 金额核对通过",
                f"识别 {len(am_r.all_amounts)} 条金额，未发现不一致",
                "全文", "", "💰"))
        for issue in am_r.issues:
            items.append(ReportItem("金额一致性", issue.risk_level,
                issue.issue_type, issue.description,
                "、".join(issue.locations), issue.suggestion, "💰"))
    except Exception:
        pass

    # ── 13. 页码连续性 ───────────────────────────────────────
    try:
        from modules.page_number_check import check_page_numbers
        pn_r = check_page_numbers(file_bytes, filename, text, pages)
        if pn_r.detected_numbers:  # 有实际检测结果
            score_breakdown["页码连续性"] = pn_r.score
            if not pn_r.issues:
                items.append(ReportItem("页码连续性", "优势", "✅ 页码连续无跳断",
                    f"识别 {sum(1 for p in pn_r.detected_numbers if p)} 页页码，连续完整",
                    "全文", "", "🔢"))
            else:
                for issue in pn_r.issues:
                    items.append(ReportItem("页码连续性", issue.risk_level,
                        issue.issue_type, issue.description,
                        ", ".join(f"第{p}页" for p in issue.pages[:3]),
                        issue.suggestion, "🔢"))
    except Exception:
        pass

    # ── 14. 字体/字号规范 ────────────────────────────────────
    try:
        from modules.font_check import check_fonts
        fn_r = check_fonts(file_bytes, filename, text, pages)
        if fn_r.font_stats:  # 有实际检测到字体（Word文档）
            score_breakdown["字体规范"] = fn_r.score
            if not fn_r.issues:
                items.append(ReportItem("字体规范", "优势", "✅ 字体使用规范",
                    f"共 {len(fn_r.font_stats)} 种字体，均为标准字体",
                    "全文", "", "🔤"))
            else:
                for issue in fn_r.issues:
                    items.append(ReportItem("字体规范", issue.risk_level,
                        issue.issue_type, issue.description,
                        issue.location, issue.suggestion, "🔤"))
    except Exception:
        pass

    # ── 计算总分 ─────────────────────────────────────────────
    if score_breakdown:
        # 加权平均（总权重=1）
        weights = {
            "文件命名": 0.06, "废标关键词": 0.14, "资质有效期": 0.14,
            "日期逻辑": 0.10, "名称一致性": 0.08, "格式规范": 0.05,
            "关键字段": 0.08, "签章": 0.04, "模板残留": 0.08,
            "目录完整性": 0.06, "页眉页脚": 0.04,
            "联合体协议": 0.04, "金额一致性": 0.06,
            "页码连续性": 0.02, "字体规范": 0.01,
        }
        total = 0
        total_weight = 0
        for k, w in weights.items():
            if k in score_breakdown:
                total += score_breakdown[k] * w
                total_weight += w
        total_score = int(total / total_weight) if total_weight > 0 else 60
    else:
        total_score = 60

    # ── 分类整理 ─────────────────────────────────────────────
    strengths     = [i for i in items if i.severity == "优势"]
    issues_high   = [i for i in items if i.severity == "高"]
    issues_mid    = [i for i in items if i.severity == "中"]
    issues_low    = [i for i in items if i.severity == "低"]

    # ── 优先建议（最多5条，优先取高风险）───────────────────
    top_suggestions = []
    for issue in issues_high[:3]:
        if issue.suggestion:
            top_suggestions.append(f"【{issue.category}】{issue.suggestion}")
    for issue in issues_mid[:2]:
        if issue.suggestion and len(top_suggestions) < 5:
            top_suggestions.append(f"【{issue.category}】{issue.suggestion}")

    # ── 一句话总结 ────────────────────────────────────────────
    if total_score >= 90:
        summary = f"标书质量优秀（{total_score}分），发现 {len(issues_high)} 项高风险、{len(issues_mid)} 项中风险问题，整体可提交。"
    elif total_score >= 75:
        summary = f"标书质量良好（{total_score}分），有 {len(issues_high)} 项高风险问题需修复后提交。"
    elif total_score >= 60:
        summary = f"标书存在较多问题（{total_score}分），{len(issues_high)} 项高风险须修复，建议重点检查后再提交。"
    else:
        summary = f"标书存在严重问题（{total_score}分），{len(issues_high)} 项高风险，强烈建议全面修订后再提交。"

    return DiagnosticReport(
        filename=filename,
        scan_date=str(date.today()),
        total_score=total_score,
        score_breakdown=score_breakdown,
        strengths=strengths,
        issues_high=issues_high,
        issues_mid=issues_mid,
        issues_low=issues_low,
        top_suggestions=top_suggestions,
        summary_text=summary,
    )
