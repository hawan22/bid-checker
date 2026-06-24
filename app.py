"""
标书CT扫描仪 v1.2
=====================
支持格式：PDF / JPG / PNG / BMP / TIFF（拍照上传）/ DOCX
所有处理在本地完成，文件不上传任何服务器。

运行：streamlit run app.py
"""
import streamlit as st
import pandas as pd
import datetime
import io

# ─── 页面配置 ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="标书CT扫描仪",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-title { font-size: 2.1rem; font-weight: 700; color: #1a1a2e; }
.sub-title  { font-size: 1rem; color: #666; margin-bottom: 1rem; }
.result-box { padding: 0.9rem 1.1rem; border-radius: 8px; margin: 0.4rem 0; line-height: 1.5; }
.result-green   { background: #d4edda; border-left: 4px solid #28a745; }
.result-yellow  { background: #fff3cd; border-left: 4px solid #ffc107; }
.result-red     { background: #f8d7da; border-left: 4px solid #dc3545; }
.result-darkred { background: #f5c2c7; border-left: 4px solid #842029; }
.result-gray    { background: #e2e3e5; border-left: 4px solid #6c757d; }
.result-blue    { background: #cce5ff; border-left: 4px solid #004085; }
.problem-list   { background: #fff3cd; border-radius: 6px; padding: 0.8rem 1rem; margin: 0.4rem 0; }
.problem-item   { margin: 0.3rem 0; font-size: 0.9rem; }
.badge          { display: inline-block; padding: 0.25rem 0.7rem; border-radius: 12px;
                  font-size: 0.8rem; font-weight: 600; margin: 0.1rem; }
.badge-green    { background: #d4edda; color: #155724; }
.badge-red      { background: #f8d7da; color: #721c24; }
.badge-yellow   { background: #fff3cd; color: #856404; }
.privacy        { background: #e8f5e9; border: 1px solid #a5d6a7; padding: 0.35rem 0.7rem;
                  border-radius: 16px; font-size: 0.82rem; color: #2e7d32; }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────
c1, c2 = st.columns([6, 2])
with c1:
    st.markdown('<div class="main-title">🔬 标书CT扫描仪</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">上传标书（PDF / Word / 拍照图片），一键扫描错误与不规范项</div>',
                unsafe_allow_html=True)
with c2:
    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<span class="privacy">🔒 全程本地，文件不上传网络</span>', unsafe_allow_html=True)

st.divider()

# 支持格式常量
PDF_TYPES   = ["pdf"]
IMAGE_TYPES = ["jpg", "jpeg", "png", "bmp", "tiff", "tif"]
WORD_TYPES  = ["docx"]
ALL_DOC     = PDF_TYPES + IMAGE_TYPES + WORD_TYPES
EXCEL_TYPES = ["xlsx", "xls"]


# ─── 工具函数 ─────────────────────────────────────────────────────────────────
def color_box(text: str, color: str):
    """渲染带颜色的结果框。"""
    cls = f"result-{color}"
    st.markdown(f'<div class="result-box {cls}">{text}</div>', unsafe_allow_html=True)


def show_problems(problems: list, title: str = "⚠️ 发现的问题"):
    """渲染问题列表。"""
    if not problems:
        return
    items = "".join(f'<div class="problem-item">• {p}</div>' for p in problems)
    st.markdown(
        f'<div class="problem-list"><b>{title}（共{len(problems)}项）</b>{items}</div>',
        unsafe_allow_html=True
    )


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📄 PDF可复制性",
    "📅 资质有效期",
    "📊 技术参数比对",
    "💰 价格大小写",
    "🔏 签章检测",
    "🚨 废标风险扫描",
    "📋 格式规范检查",
    "🔍 多标书比较",
    "📊 综合诊断报告",
])


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — PDF可复制性检测
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("📄 PDF文字可复制性检测")
    st.caption("检测标书PDF是否有文字层可提取，还是纯扫描图片版。"
               "**支持：PDF / 拍照JPG/PNG/BMP/TIFF**")

    uploaded = st.file_uploader(
        "上传文件（PDF 或 拍照图片）",
        type=PDF_TYPES + IMAGE_TYPES,
        key="pdf_check",
        help="支持拍照上传：JPG/PNG/BMP/TIFF"
    )

    if uploaded:
        with st.spinner(f"分析 {uploaded.name}…"):
            from modules.pdf_check import check_pdf_text
            result = check_pdf_text(uploaded.read(), uploaded.name)

        color_box(f"<b>{result.overall_status}</b>", result.overall_color)

        if result.file_type == "pdf":
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("总页数", result.total_pages)
            c2.metric("✅ 文字页", result.text_pages)
            c3.metric("❌ 图片页", result.image_pages,
                      delta=f"-{result.image_pages}" if result.image_pages else None,
                      delta_color="inverse")
            c4.metric("总字符数", f"{result.total_chars:,}")

        if result.suggestion:
            st.info(result.suggestion)

        if result.problems:
            show_problems(result.problems, "📍 具体问题页码")

        if result.file_type == "pdf" and result.pages:
            with st.expander(f"📋 逐页详情（{result.total_pages}页）"):
                status_map = {"text": "✅ 文字", "image": "❌ 图片", "mixed": "⚠️ 少量文字"}
                df = pd.DataFrame([
                    {"页码": p.page_num,
                     "状态": status_map.get(p.status, p.status),
                     "字符数": p.char_count,
                     "详情": p.note,
                     "问题说明": p.problem or "—"}
                    for p in result.pages
                ])

                def hl(row):
                    if "❌" in str(row["状态"]):
                        return ["background:#f8d7da"] * len(row)
                    elif "⚠️" in str(row["状态"]):
                        return ["background:#fff3cd"] * len(row)
                    return [""] * len(row)

                st.dataframe(df.style.apply(hl, axis=1),
                             use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — 资质有效期检查
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("📅 资质文件有效期检查")
    st.caption("自动提取证件有效期，红/黄/绿分级提示。"
               "**支持：PDF / 拍照图片（JPG/PNG）/ Word(.docx) / 粘贴文本**")

    from modules.validity_check import check_validity_from_file, check_validity_from_text, _build_result

    input_method = st.radio("输入方式", ["上传文件", "粘贴文本"], horizontal=True, key="val_method")
    val_result = None

    if input_method == "上传文件":
        val_files = st.file_uploader(
            "上传资质文件（支持多文件批量检查）",
            type=PDF_TYPES + IMAGE_TYPES + WORD_TYPES,
            accept_multiple_files=True,
            key="val_files",
            help="PDF / 拍照图片 / Word 均可，多个文件一起上传"
        )
        if val_files and st.button("🔍 开始检查", key="val_btn", type="primary"):
            all_hits = []
            all_problems = []
            for f in val_files:
                with st.spinner(f"解析 {f.name}…"):
                    r = check_validity_from_file(f.read(), f.name)
                    all_hits.extend(r.hits)
                    all_problems.extend(r.problems)
            val_result = _build_result("合并结果", all_hits)
            val_result.problems = all_problems
    else:
        text_input = st.text_area(
            "粘贴含有效期的文本",
            height=150,
            placeholder="例：\n营业执照有效期至：2030年06月15日\n安全生产许可证 有效期 2025.03.01 至 2028.03.01",
            key="val_text"
        )
        if text_input and st.button("🔍 开始检查", key="val_text_btn", type="primary"):
            val_result = check_validity_from_text(text_input)

    if val_result:
        color = "red" if val_result.has_expired else ("yellow" if val_result.has_urgent else "green")
        color_box(f"<b>{val_result.summary}</b>", color)

        if val_result.problems:
            show_problems(val_result.problems, "📍 需关注的具体日期（含精确位置）")

        if val_result.hits:
            rows = []
            for h in val_result.hits:
                rows.append({
                    "📍 位置": h.location or "—",
                    "到期日期": h.date.strftime("%Y-%m-%d"),
                    "剩余天数": h.days_remaining,
                    "状态": h.label,
                    "识别原文": h.raw_text,
                    "上下文片段": h.context[:60] + "…" if len(h.context) > 60 else h.context,
                })
            df = pd.DataFrame(rows).sort_values("剩余天数")

            def hl_row(row):
                days = row["剩余天数"]
                if days < 0:   return ["background:#f5c2c7"] * len(row)
                if days < 30:  return ["background:#f8d7da"] * len(row)
                if days < 90:  return ["background:#fff3cd"] * len(row)
                return ["background:#d4edda"] * len(row)

            st.dataframe(df.style.apply(hl_row, axis=1),
                         use_container_width=True, hide_index=True)
        else:
            st.warning("未识别到日期，建议改用「粘贴文本」方式，或确认文件含明确有效期字段。")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — 技术参数响应比对
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("📊 技术参数响应表比对")
    st.caption("上传招标参数要求表 + 投标响应表，逐行对比，精确标注哪一行参数存在问题。"
               "**支持：Excel(.xlsx) / Word(.docx)**")

    c_a, c_b = st.columns(2)
    with c_a:
        st.markdown("**📋 招标参数要求表**")
        tender_file = st.file_uploader("上传招标方参数表",
                                       type=EXCEL_TYPES + WORD_TYPES, key="tender",
                                       help="需含：参数名称列 + 招标要求列")
        st.caption("支持 .xlsx / .docx，列名自动识别")
    with c_b:
        st.markdown("**📝 投标响应表**")
        bid_file = st.file_uploader("上传投标方响应表",
                                    type=EXCEL_TYPES + WORD_TYPES, key="bid",
                                    help="需含：参数名称列 + 投标响应列")
        st.caption("支持 .xlsx / .docx，列名自动识别")

    if tender_file and bid_file:
        with st.expander("⚙️ 高级：手动指定列名（留空则自动识别）"):
            c1, c2, c3, c4 = st.columns(4)
            t_name = c1.text_input("招标：参数名列", key="tn")
            t_req  = c2.text_input("招标：要求列",   key="tr")
            b_name = c3.text_input("投标：参数名列", key="bn")
            b_resp = c4.text_input("投标：响应列",   key="br")

        if st.button("🔍 开始比对", key="param_btn", type="primary"):
            with st.spinner("对比中…"):
                from modules.param_compare import compare_params
                r = compare_params(
                    tender_file.read(), tender_file.name,
                    bid_file.read(), bid_file.name,
                    t_name or "", t_req or "",
                    b_name or "", b_resp or "",
                )

            # 总览
            overall_color = "green" if (r.failed == 0 and r.missing == 0) else "red"
            color_box(f"<b>{r.summary}</b>", overall_color)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("总计", r.total)
            c2.metric("✅ 通过", r.passed)
            c3.metric("⚠️ 待核查", r.warned)
            c4.metric("❌ 不满足", r.failed)
            c5.metric("⬜ 缺失响应", r.missing)

            # 精确问题列表
            fail_problems = [
                f"第{row.index}项「{row.name}」: {row.reason}（要求：{row.requirement[:30]}，响应：{row.response[:30]}）"
                for row in r.rows if row.result in ("FAIL", "MISSING")
            ]
            if fail_problems:
                show_problems(fail_problems, "📍 需重点核查的参数（逐项说明原因）")

            # 完整结果表
            STATUS_ICON = {"PASS": "✅ 通过", "WARN": "⚠️ 待核查", "FAIL": "❌ 不满足", "MISSING": "⬜ 缺失"}
            rows = [{"#": row.index, "参数名称": row.name,
                     "招标要求": row.requirement, "投标响应": row.response,
                     "结果": STATUS_ICON.get(row.result, row.result),
                     "原因说明": row.reason}
                    for row in r.rows]
            df = pd.DataFrame(rows)

            def hl_param(row):
                t = str(row["结果"])
                if "❌" in t: return ["background:#f8d7da"] * len(row)
                if "⚠️" in t: return ["background:#fff3cd"] * len(row)
                if "⬜" in t: return ["background:#e2e3e5"] * len(row)
                return ["background:#d4edda"] * len(row)

            st.dataframe(df.style.apply(hl_param, axis=1),
                         use_container_width=True, hide_index=True)

            out = io.BytesIO()
            df.to_excel(out, index=False)
            st.download_button(
                "⬇️ 下载比对结果Excel",
                data=out.getvalue(),
                file_name=f"参数比对_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4 — 价格大小写校验
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("💰 价格大小写一致性校验")
    st.caption("输入小写数字金额与大写金额，立即验证是否一致，精确定位差异字符。")

    c_num, c_cn = st.columns(2)
    with c_num:
        st.markdown("**小写金额（数字）**")
        num_input = st.text_input(
            "金额（元）",
            placeholder="如：1234567.89  或  1,234,567.89",
            key="price_num"
        )
        st.caption('支持逗号分隔符，支持"万"单位缩写（如 123万）')

    with c_cn:
        st.markdown("**大写金额（中文）**")
        cn_input = st.text_input(
            "中文大写",
            placeholder="如：壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分",
            key="price_cn"
        )
        st.caption("壹贰叁/一二三均可，自动规范化后对比")

    # 实时预览转换结果
    if num_input:
        from modules.price_check import to_chinese_upper
        try:
            clean = num_input.replace(",","").replace("，","").replace(" ","").replace("¥","").replace("￥","")
            amt = float(clean.replace("万","")) * 10000 if "万" in clean else float(clean)
            st.success(f"📝 正确大写：**{to_chinese_upper(amt)}**")
        except Exception:
            st.error(f"无法解析金额：{num_input}")

    if num_input and cn_input:
        if st.button("✅ 验证一致性", key="price_btn", type="primary"):
            from modules.price_check import check_price
            r = check_price(num_input, cn_input)
            color_box(f"<b>{r.status}</b><br/>{r.note.replace(chr(10),'<br/>')}", r.color)
            if not r.is_match:
                show_problems(r.problems)

    st.divider()
    st.markdown("#### 📉 异常低价预警")
    st.caption("根据《招标投标法》：报价低于成本价可判废标；实务中低于行业均价15%即面临质疑。")

    c_avg, c_self = st.columns(2)
    with c_avg:
        avg_price = st.number_input(
            "行业平均价 / 招标控制价（元）",
            min_value=0.0, step=10000.0, format="%.2f",
            key="avg_price",
            help="输入本项目的招标控制价或同类项目的市场均价"
        )
    with c_self:
        self_price = st.number_input(
            "本次报价（元）",
            min_value=0.0, step=10000.0, format="%.2f",
            key="self_price",
            help="投标报价合计金额"
        )

    if avg_price > 0 and self_price > 0:
        ratio = self_price / avg_price
        diff_pct = (1 - ratio) * 100
        if self_price > avg_price * 1.0:
            color_box(
                f"🔴 <b>超出控制价</b>：报价 ¥{self_price:,.2f} 超出控制价 ¥{avg_price:,.2f}"
                f"（高出 {-diff_pct:.1f}%），将被判废标",
                "red"
            )
        elif diff_pct >= 20:
            color_box(
                f"🔴 <b>异常低价警告</b>：报价 ¥{self_price:,.2f} 低于均价 {diff_pct:.1f}%（超过20%阈值）"
                f"<br>⚠️ 极高废标风险，评标委员会有权要求说明成本构成",
                "red"
            )
        elif diff_pct >= 15:
            color_box(
                f"🟠 <b>低价预警</b>：报价 ¥{self_price:,.2f} 低于均价 {diff_pct:.1f}%（接近15%警戒线）"
                f"<br>建议准备成本说明材料备用",
                "yellow"
            )
        else:
            color_box(
                f"✅ <b>报价合理</b>：报价 ¥{self_price:,.2f}，低于均价 {diff_pct:.1f}%，在正常范围内",
                "green"
            )

    st.divider()
    st.markdown("#### 💹 利润测算")
    st.caption("根据投标价和成本构成，测算本次投标的利润率，评估是否存在亏损风险。")

    profit_mode = st.radio("输入方式", ["简单版（总成本）", "详细版（分项成本）"], horizontal=True, key="profit_mode")

    p_bid = st.number_input(
        "含税投标总价（元）",
        min_value=0.0, step=10000.0, format="%.2f",
        key="p_bid",
        help="投标文件中报价合计（含增值税）"
    )

    # 税率选项
    tax_rate_pct = st.selectbox(
        "增值税率",
        options=[9, 6, 13, 3, 0],
        format_func=lambda x: f"{x}%（{'建筑工程' if x==9 else '服务业' if x==6 else '货物' if x==13 else '小规模' if x==3 else '免税'}）",
        key="p_tax_rate",
    )
    tax_rate = tax_rate_pct / 100.0

    if profit_mode == "简单版（总成本）":
        p_cost = st.number_input(
            "预估总成本（元，不含税）",
            min_value=0.0, step=10000.0, format="%.2f",
            key="p_cost_simple",
            help="含直接费+管理费+规费等所有费用，不含增值税"
        )
        if p_bid > 0 and p_cost >= 0:
            excl_tax = p_bid / (1 + tax_rate)     # 不含税收入
            tax_amt  = p_bid - excl_tax             # 税金
            profit   = excl_tax - p_cost
            margin   = profit / excl_tax * 100 if excl_tax > 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("含税收入", f"¥{p_bid:,.0f}")
            c2.metric("不含税收入", f"¥{excl_tax:,.0f}")
            c3.metric("增值税", f"¥{tax_amt:,.0f}")
            c4.metric("利润", f"¥{profit:,.0f}", delta=f"{margin:.1f}%", delta_color="normal")

            if margin < 0:
                color_box(f"🔴 <b>亏损</b>：利润率 {margin:.2f}%，成本超过不含税收入 ¥{-profit:,.2f}<br>"
                          "⚠️ 低于成本价投标可被判废标（《招投标法》第33条）", "red")
            elif margin < 3:
                color_box(f"🟠 <b>高风险低利润</b>：利润率 {margin:.2f}%（行业安全线通常 ≥3%）<br>"
                          "建议重审成本，或准备成本说明材料以防异常低价质疑", "yellow")
            elif margin < 8:
                color_box(f"✅ <b>利润合理</b>：利润率 {margin:.2f}%（行业正常范围 3%~8%）", "green")
            else:
                color_box(f"💚 <b>利润较高</b>：利润率 {margin:.2f}%，盈利空间充裕", "green")

    else:  # 详细版
        st.caption("按工程造价标准五费拆分填写（均为**不含税**金额）：")
        c1, c2 = st.columns(2)
        with c1:
            p_direct   = st.number_input("① 直接费（人工+材料+机械）", min_value=0.0, step=10000.0, format="%.2f", key="p_direct")
            p_overhead = st.number_input("② 管理费（企业管理费）",      min_value=0.0, step=1000.0,  format="%.2f", key="p_overhead")
            p_statutory= st.number_input("③ 规费（社保/公积金等）",      min_value=0.0, step=1000.0,  format="%.2f", key="p_statutory")
        with c2:
            p_other    = st.number_input("④ 其他费用（安全文明/措施费）", min_value=0.0, step=1000.0,  format="%.2f", key="p_other")
            p_profit_preset = st.number_input("⑤ 预设利润（元，可为0）",  min_value=0.0, step=1000.0,  format="%.2f", key="p_profit_preset",
                                              help="若招标方规定了利润率则在此填入，否则留0由系统推算")

        if p_bid > 0:
            excl_tax   = p_bid / (1 + tax_rate)
            tax_amt    = p_bid - excl_tax
            total_cost = p_direct + p_overhead + p_statutory + p_other
            actual_profit = excl_tax - total_cost - p_profit_preset if p_profit_preset > 0 else excl_tax - total_cost
            if p_profit_preset > 0:
                # 用户填了预设利润：把它算进去显示，再看剩余
                actual_profit = excl_tax - total_cost
            margin = actual_profit / excl_tax * 100 if excl_tax > 0 else 0

            st.markdown("##### 📊 测算结果")
            col_r = st.columns(5)
            col_r[0].metric("不含税收入", f"¥{excl_tax:,.0f}")
            col_r[1].metric("直接+间接费合计", f"¥{total_cost:,.0f}")
            col_r[2].metric("增值税",     f"¥{tax_amt:,.0f}")
            col_r[3].metric("实际利润",   f"¥{actual_profit:,.0f}")
            col_r[4].metric("利润率",     f"{margin:.2f}%",
                            delta="合理" if 3<=margin<=8 else ("亏损" if margin<0 else "偏低" if margin<3 else "较高"),
                            delta_color="normal" if 3<=margin<=8 else "inverse")

            # 费用结构饼图数据
            if total_cost > 0:
                import json
                cost_labels = ["直接费", "管理费", "规费", "其他费", "利润", "增值税"]
                cost_values = [p_direct, p_overhead, p_statutory, p_other,
                               max(0, actual_profit), tax_amt]
                cost_data = pd.DataFrame({"费用项": cost_labels, "金额（元）": cost_values})
                cost_data = cost_data[cost_data["金额（元）"] > 0]
                st.bar_chart(cost_data.set_index("费用项"), use_container_width=True, height=220)

            # 风险判断
            if margin < 0:
                color_box(f"🔴 <b>亏损</b>：利润率 {margin:.2f}%，成本超出不含税收入 ¥{-actual_profit:,.2f}<br>"
                          "⚠️ 低于成本价投标违法，评标委员会有权废标并要求成本说明", "red")
            elif margin < 3:
                color_box(f"🟠 <b>高风险低利润</b>：利润率 {margin:.2f}%<br>"
                          "建议检查成本是否漏项，或准备成本构成说明以应对质疑", "yellow")
            elif margin < 8:
                color_box(f"✅ <b>利润合理</b>：利润率 {margin:.2f}%（行业正常范围 3%~8%）", "green")
            else:
                color_box(f"💚 <b>利润较高</b>：利润率 {margin:.2f}%，竞争力可能偏弱，视项目情况评估", "green")

            # 导出明细
            export_data = pd.DataFrame([
                {"项目": "含税投标总价", "金额（元）": p_bid, "备注": ""},
                {"项目": "不含税收入",   "金额（元）": round(excl_tax, 2), "备注": f"÷(1+{tax_rate_pct}%)"},
                {"项目": "增值税",       "金额（元）": round(tax_amt, 2),  "备注": f"{tax_rate_pct}%"},
                {"项目": "直接费",       "金额（元）": p_direct,           "备注": "人工+材料+机械"},
                {"项目": "管理费",       "金额（元）": p_overhead,         "备注": ""},
                {"项目": "规费",         "金额（元）": p_statutory,        "备注": "社保/公积金等"},
                {"项目": "其他费用",     "金额（元）": p_other,            "备注": "安全文明/措施费"},
                {"项目": "合计成本",     "金额（元）": round(total_cost, 2),"备注": ""},
                {"项目": "实际利润",     "金额（元）": round(actual_profit, 2), "备注": f"利润率 {margin:.2f}%"},
            ])
            out = io.BytesIO()
            export_data.to_excel(out, index=False)
            st.download_button(
                "⬇️ 导出利润测算表",
                data=out.getvalue(),
                file_name=f"利润测算_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="profit_export"
            )

    st.divider()
    st.markdown("#### 🧮 批量转换（多个金额快速查看大写）")
    batch = st.text_area("每行一个金额", placeholder="1000000\n256800.50\n99999.99",
                         height=100, key="batch")
    if batch:
        from modules.price_check import to_chinese_upper
        rows = []
        for line in [l.strip() for l in batch.strip().splitlines() if l.strip()]:
            try:
                clean = line.replace(",","").replace("，","").replace("¥","").replace("￥","")
                amt = float(clean.replace("万","")) * 10000 if "万" in clean else float(clean)
                rows.append({"数字金额": f"¥ {amt:,.2f}", "中文大写": to_chinese_upper(amt)})
            except Exception:
                rows.append({"数字金额": line, "中文大写": "❌ 无法解析"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 5 — 签章检测
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("🔏 签章有效性检测")
    st.caption("检测PDF是否含合规数字签名（CA/UKey）。"
               "**支持：PDF / 拍照图片（图片只能看视觉印章，无法验证数字签名）**")

    seal_file = st.file_uploader(
        "上传盖章页文件",
        type=PDF_TYPES + IMAGE_TYPES,
        key="seal",
        help="PDF可检测数字签名域；图片只能判断是否有视觉印章"
    )

    if seal_file:
        with st.spinner("检测中…"):
            from modules.seal_check import check_seal
            r = check_seal(seal_file.read(), seal_file.name)

        color_box(f"<b>{r.overall_status}</b><br/>{r.summary}", r.overall_color)

        if r.suggestion:
            st.warning(r.suggestion)

        if r.problems:
            show_problems(r.problems, "📍 发现的签章问题")

        if r.file_type == "pdf":
            c1, c2, c3 = st.columns(3)
            c1.metric("数字签名域", r.digital_sig_count,
                      help="使用CA/UKey签署的合规电子签名")
            c2.metric("注释印章", r.annotation_count,
                      help="Ink/Stamp注释，不具备法律效力")
            c3.metric("PDF内图片", r.image_seal_count,
                      help="嵌入图片（可能含扫描印章）")

        if r.seals:
            with st.expander(f"🔍 签章详情（{len(r.seals)}项）"):
                for s in r.seals:
                    page_info = f"第{s.page_num}页 · " if s.page_num else ""
                    color_box(f"{page_info}{s.description}", s.color)

        with st.expander("📘 什么是合规电子签章？"):
            st.markdown("""
| 类型 | 合规性 | 说明 |
|------|--------|------|
| CA数字签名（UKey/USB-Key） | ✅ 合规 | 符合《电子招标投标办法》 |
| 电子印章平台（含CA证书） | ✅ 合规 | 如天印、签章宝等正规平台 |
| 扫描纸质印章插入PDF | ❌ 通常不合规 | 仅视觉印章，无法防篡改 |
| 截图/图片印章粘贴 | ❌ 不合规 | 无任何安全保障 |

**如何签署合规数字签章：**
1. 向CA机构申请企业证书（中证信、CFCA、天威诚信等）
2. 购买 UKey 硬件存储私钥
3. 用 Adobe Acrobat 或招标平台客户端对PDF签署
""")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 6 — 废标风险综合扫描
# ══════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("🚨 废标风险综合扫描")
    st.caption(
        "一次上传，同时完成 4 项高频废标检查：\n"
        "**① 文件命名** · **② 废标关键词** · **③ 日期逻辑** · **④ 名称一致性**\n\n"
        "📊 真实数据：98%的废标集中在前10类，签章/资质/格式三项占54%"
    )

    risk_file = st.file_uploader(
        "上传标书文件（PDF / Word / 拍照图片）",
        type=PDF_TYPES + IMAGE_TYPES + WORD_TYPES,
        key="risk_scan",
        help="支持 PDF / DOCX / JPG / PNG / BMP / TIFF"
    )

    if risk_file:
        if st.button("🚨 一键废标风险扫描", key="risk_btn", type="primary"):
            from modules.naming_check import check_filename
            from modules.keyword_scan import scan_keywords
            from modules.date_logic import analyze_date_logic
            from modules.name_consistency import check_name_consistency
            from modules.ocr_helper import extract_text_smart

            # ── 1. 文件命名 ───────────────────────────────────────────
            st.markdown("---")
            st.markdown("### ① 文件命名检查")
            nm = check_filename(risk_file.name)
            if nm.is_safe:
                color_box(f"✅ 文件名「{nm.filename}」命名规范，无违规字符", "green")
            else:
                color_box(
                    f"🔴 文件名「{nm.filename}」存在问题：<br>"
                    + "<br>".join(f"• {p}" for p in nm.problems),
                    "red"
                )
                if nm.suggestions:
                    st.info("💡 建议：" + "；".join(nm.suggestions))

            # ── 提取全文（后续三项共用）──────────────────────────────
            with st.spinner("提取文本中…"):
                raw_bytes = risk_file.read()
                full_text, method, pages = extract_text_smart(raw_bytes, risk_file.name)

            st.caption(f"📄 文本提取方式：{method}，共 {len(pages)} 页，{len(full_text):,} 字符")

            # ── 2. 废标关键词 ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("### ② 废标关键词扫描")
            if full_text.strip():
                kw = scan_keywords(full_text, pages)
                scan_color = "red" if kw.high_risk > 0 else ("yellow" if kw.medium_risk > 0 else "green")
                color_box(f"<b>{kw.summary}</b>（共扫描 {len(full_text):,} 字符）", scan_color)

                if kw.hits:
                    risk_order = {"高": 0, "中": 1, "提示": 2}
                    sorted_hits = sorted(kw.hits, key=lambda h: risk_order.get(h.risk_level, 3))
                    rows = [{
                        "风险": "🔴 高" if h.risk_level=="高" else ("🟠 中" if h.risk_level=="中" else "🔵 提示"),
                        "命中词": h.keyword,
                        "类别": h.category,
                        "位置": h.location,
                        "上下文": h.context[:80] + ("…" if len(h.context)>80 else ""),
                    } for h in sorted_hits]
                    df_kw = pd.DataFrame(rows)

                    def hl_kw(row):
                        r_val = str(row["风险"])
                        if "🔴" in r_val: return ["background:#f8d7da"]*len(row)
                        if "🟠" in r_val: return ["background:#fff3cd"]*len(row)
                        return ["background:#cce5ff"]*len(row)

                    with st.expander(f"查看全部命中词（{len(kw.hits)}项）"):
                        st.dataframe(df_kw.style.apply(hl_kw, axis=1),
                                     use_container_width=True, hide_index=True)
            else:
                color_box("⚠️ 未能提取文本，跳过关键词扫描（图片文件建议使用OCR）", "gray")

            # ── 3. 日期逻辑 ───────────────────────────────────────────
            st.markdown("---")
            st.markdown("### ③ 日期逻辑一致性")
            if full_text.strip():
                dl = analyze_date_logic(full_text, pages)
                dl_color = "red" if any(i.risk_level=="高" for i in dl.issues) else \
                           ("yellow" if dl.issues else "green")
                color_box(f"<b>{dl.summary}</b>", dl_color)

                if dl.issues:
                    for issue in dl.issues:
                        icon = "🔴" if issue.risk_level == "高" else "🟠"
                        color_box(
                            f"{icon} {issue.description}<br>"
                            f"<small>📍 {issue.date_a.location} vs {issue.date_b.location}</small>",
                            "red" if issue.risk_level == "高" else "yellow"
                        )

                if dl.entries:
                    with st.expander(f"📅 提取的全部日期（{len(dl.entries)}个）"):
                        rows_d = [{
                            "日期": e.parsed.strftime("%Y-%m-%d"),
                            "推断角色": e.role,
                            "位置": e.location,
                            "原文": e.raw,
                            "上下文": e.context[:60] + ("…" if len(e.context)>60 else ""),
                        } for e in sorted(dl.entries, key=lambda x: x.parsed)]
                        st.dataframe(pd.DataFrame(rows_d),
                                     use_container_width=True, hide_index=True)
            else:
                color_box("⚠️ 未能提取文本，跳过日期检查", "gray")

            # ── 4. 名称一致性 ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("### ④ 名称一致性扫描")
            if full_text.strip():
                nc = check_name_consistency(full_text, pages)
                nc_color = "red" if any(i.risk_level=="高" for i in nc.issues) else \
                           ("yellow" if nc.issues else "green")
                color_box(f"<b>{nc.summary}</b>", nc_color)

                if nc.issues:
                    for issue in nc.issues:
                        icon = "🔴" if issue.risk_level == "高" else "🟠"
                        desc_html = issue.description.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
                        color_box(
                            f"{icon} {desc_html}",
                            "red" if issue.risk_level == "高" else "yellow"
                        )

                if nc.entities:
                    with st.expander(f"📋 提取的实体（{len(nc.entities)}项）"):
                        rows_n = [{
                            "类型": e.entity_type,
                            "名称": e.value,
                            "位置": e.location,
                            "上下文": e.context[:60] + ("…" if len(e.context)>60 else ""),
                        } for e in nc.entities]
                        st.dataframe(pd.DataFrame(rows_n),
                                     use_container_width=True, hide_index=True)
            else:
                color_box("⚠️ 未能提取文本，跳过名称一致性检查", "gray")

            # ── 5. 模板残留 & 修订痕迹 ─────────────────────────────
            st.markdown("---")
            st.markdown("### ⑤ 模板残留 & 修订痕迹检测")
            from modules.template_check import check_template_and_revisions
            with st.spinner("检测模板占位符和修订痕迹…"):
                tr = check_template_and_revisions(raw_bytes, risk_file.name, full_text, pages)

            tr_color = ("red" if any(h.risk_level=="高" for h in
                        tr.placeholder_hits + tr.revision_hits + tr.annotation_hits)
                        else ("yellow" if tr.problems else "green"))
            color_box(f"<b>{tr.summary}</b>", tr_color)

            if tr.placeholder_hits:
                with st.expander(f"🔴 模板占位符未替换（{len(tr.placeholder_hits)}处）"):
                    for h in tr.placeholder_hits:
                        color_box(
                            f"{'🔴' if h.risk_level=='高' else '🟠'} "
                            f"<b>{h.location}</b>：「{h.content}」<br>"
                            f"<small>💡 {h.suggestion}</small>",
                            "red" if h.risk_level=="高" else "yellow"
                        )

            if tr.revision_hits:
                for h in tr.revision_hits:
                    color_box(
                        f"🔴 <b>修订痕迹</b>：{h.content}<br>"
                        f"<small>💡 {h.suggestion}</small>",
                        "red"
                    )

            if tr.annotation_hits:
                for h in tr.annotation_hits:
                    color_box(
                        f"🟠 <b>PDF批注残留</b>：{h.content}<br>"
                        f"<small>💡 {h.suggestion}</small>",
                        "yellow"
                    )

            st.markdown("---")
            st.markdown("### ⑥ 联合体协议完整性")
            from modules.joint_venture_check import check_joint_venture
            with st.spinner("检测联合体协议…"):
                jv_r = check_joint_venture(raw_bytes, risk_file.name, full_text, pages)
            if not jv_r.is_joint_venture:
                color_box(f"<b>{jv_r.summary}</b>", "green")
            else:
                jv_color = "red" if any(i.risk_level=="高" for i in jv_r.issues) else \
                           "yellow" if jv_r.issues else "green"
                color_box(f"<b>{jv_r.summary}</b>", jv_color)
                if jv_r.members:
                    st.markdown(f"**识别联合体成员（{len(jv_r.members)}家）：** " +
                                "、".join(jv_r.members[:5]))
                for issue in jv_r.issues:
                    icon = "🔴" if issue.risk_level=="高" else "🟠"
                    color_box(
                        f"{icon} <b>{issue.issue_type}</b><br>{issue.description}<br>"
                        f"<small>💡 {issue.suggestion}</small>",
                        "red" if issue.risk_level=="高" else "yellow"
                    )

            st.markdown("---")
            st.markdown("### ⑦ 投标函金额与报价单交叉核对")
            from modules.amount_cross_check import check_amount_cross
            with st.spinner("提取并交叉核对金额…"):
                am_r = check_amount_cross(raw_bytes, risk_file.name, full_text, pages)
            am_color = ("red" if any(i.risk_level=="高" for i in am_r.issues)
                        else ("yellow" if am_r.issues else "green"))
            color_box(f"<b>{am_r.summary}</b>", am_color)
            if am_r.issues:
                for issue in am_r.issues:
                    icon = "🔴" if issue.risk_level=="高" else "🟠"
                    color_box(
                        f"{icon} <b>{issue.issue_type}</b><br>{issue.description}<br>"
                        f"<small>💡 {issue.suggestion}</small>",
                        "red" if issue.risk_level=="高" else "yellow"
                    )
            if am_r.all_amounts:
                with st.expander(f"💰 识别到的金额记录（{len(am_r.all_amounts)}条）"):
                    from modules.amount_cross_check import _fmt_amount
                    rows_am = [{
                        "章节": a.source_section,
                        "金额": _fmt_amount(a.amount),
                        "原文": a.raw_text[:30],
                        "类型": "大写" if a.is_cny_upper else "数字",
                        "位置": a.page_hint,
                    } for a in am_r.all_amounts[:20]]
                    st.dataframe(pd.DataFrame(rows_am),
                                 use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 7 — 格式规范检查
# ══════════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.subheader("📋 格式规范检查")
    st.caption("检查标书的格式合规性：**① 印章清晰度** · **② 标点规范** · **③ 日期格式统一** · **④ 关键字段完整**")

    fmt_input = st.radio("输入方式", ["上传文件", "粘贴文本"], horizontal=True, key="fmt_method")

    fmt_text = ""
    fmt_file_bytes = None
    fmt_filename = ""

    if fmt_input == "上传文件":
        fmt_file = st.file_uploader(
            "上传标书（PDF / Word / 图片）",
            type=PDF_TYPES + IMAGE_TYPES + WORD_TYPES,
            key="fmt_file",
        )
        if fmt_file:
            fmt_file_bytes = fmt_file.read()
            fmt_filename = fmt_file.name
            with st.spinner("提取文本…"):
                from modules.ocr_helper import extract_text_smart
                fmt_text, _, _ = extract_text_smart(fmt_file_bytes, fmt_filename)
    else:
        fmt_text = st.text_area("粘贴标书文本内容", height=200, key="fmt_text_input",
                                placeholder="粘贴标书正文或摘录…")

    if st.button("📋 开始格式规范检查", key="fmt_btn", type="primary",
                 disabled=(not fmt_text and not fmt_file_bytes)):

        # ── ① 印章清晰度（需要图片文件）────────────────────────────────
        st.markdown("---")
        st.markdown("### 🔍 ① 印章/证书清晰度")
        if fmt_file_bytes and fmt_filename:
            with st.spinner("分析图片清晰度…"):
                from modules.clarity_check import check_clarity
                cr = check_clarity(fmt_file_bytes, fmt_filename)
            color_box(f"<b>清晰度评分：{cr.overall_score:.0f}</b> — {cr.overall_label}", cr.overall_color)
            if cr.suggestion:
                st.warning(f"💡 {cr.suggestion}")
            if cr.problems:
                show_problems(cr.problems, "📍 模糊页面")
            if cr.pages and len(cr.pages) > 1:
                with st.expander(f"逐页清晰度（{len(cr.pages)}页）"):
                    df_cl = pd.DataFrame([{
                        "页码": p.page_num,
                        "清晰度评分": p.score,
                        "状态": p.label,
                        "说明": p.note,
                    } for p in cr.pages])
                    def hl_cl(row):
                        lbl = str(row["状态"])
                        if "非常模糊" in lbl or "❌" in lbl: return ["background:#f8d7da"]*len(row)
                        if "模糊" in lbl or "⚠️" in lbl:     return ["background:#fff3cd"]*len(row)
                        return ["background:#d4edda"]*len(row)
                    st.dataframe(df_cl.style.apply(hl_cl, axis=1),
                                 use_container_width=True, hide_index=True)
        else:
            color_box("ℹ️ 清晰度检测需上传图片或PDF文件（文本粘贴不适用）", "gray")

        # ── ② 标点符号 ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📝 ② 标点符号规范性")
        if fmt_text:
            from modules.format_check import check_punctuation
            pr = check_punctuation(fmt_text)
            p_color = "red" if any(i.risk_level=="中" for i in pr.issues) else \
                      ("yellow" if pr.issues else "green")
            color_box(f"<b>{pr.summary}</b>", p_color)
            if pr.issues:
                rows_p = [{
                    "问题类型": i.issue_type,
                    "风险": "🟠 需修正" if i.risk_level=="中" else "🔵 提示",
                    "出现次数": i.count,
                    "说明": i.description[:60],
                    "示例": "、".join(str(e) for e in i.examples[:2]),
                } for i in pr.issues]
                st.dataframe(pd.DataFrame(rows_p), use_container_width=True, hide_index=True)
        else:
            color_box("ℹ️ 需有文本内容才能检查标点", "gray")

        # ── ③ 日期格式统一性 ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📅 ③ 日期格式统一性")
        if fmt_text:
            from modules.format_check import check_date_format
            dfr = check_date_format(fmt_text)
            df_color = "green" if dfr.is_consistent else "yellow"
            color_box(f"<b>{dfr.summary}</b>", df_color)
            if dfr.formats_found:
                df_fmt = pd.DataFrame([
                    {"日期格式": fmt, "出现次数": cnt,
                     "是否主流": "✅ 主流" if fmt == dfr.dominant_format else "⚠️ 少数"}
                    for fmt, cnt in sorted(dfr.formats_found.items(), key=lambda x: -x[1])
                ])
                st.dataframe(df_fmt, use_container_width=True, hide_index=True)
            if dfr.problems:
                show_problems(dfr.problems, "📍 格式统一建议")
        else:
            color_box("ℹ️ 需有文本内容才能检查日期格式", "gray")

        # ── ④ 关键字段完整性 ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📋 ④ 关键字段完整性")
        if fmt_text:
            from modules.format_check import check_field_completeness
            fcr = check_field_completeness(fmt_text)
            fc_color = "red" if fcr.missing_high > 0 else ("yellow" if fcr.missing_mid > 0 else "green")
            color_box(f"<b>{fcr.summary}</b>", fc_color)
            if fcr.problems:
                show_problems(fcr.problems, "⚠️ 缺失字段")
            rows_fc = [{
                "字段": item.field_name,
                "状态": "✅ 已找到" if item.is_present else
                        ("🔴 缺失" if item.risk_level=="高" else
                         "🟠 缺失" if item.risk_level=="中" else "🔵 缺失"),
                "风险": item.risk_level,
                "证据/说明": item.evidence[:50] if item.is_present else "—",
            } for item in fcr.items]
            def hl_fc(row):
                s = str(row["状态"])
                if "🔴" in s: return ["background:#f8d7da"]*len(row)
                if "🟠" in s: return ["background:#fff3cd"]*len(row)
                if "🔵" in s: return ["background:#cce5ff"]*len(row)
                return ["background:#d4edda"]*len(row)
            st.dataframe(pd.DataFrame(rows_fc).style.apply(hl_fc, axis=1),
                         use_container_width=True, hide_index=True)
        else:
            color_box("ℹ️ 需有文本内容才能检查字段完整性", "gray")

        # ── ⑤ 目录完整性 ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📑 ⑤ 目录完整性核查")
        if fmt_text or fmt_file_bytes:
            with st.spinner("核查目录结构…"):
                from modules.toc_check import check_toc
                _, _, fmt_pages = (
                    extract_text_smart(fmt_file_bytes, fmt_filename)
                    if fmt_file_bytes and 'extract_text_smart' in dir()
                    else (fmt_text, "", [fmt_text] if fmt_text else [])
                )
                toc_r = check_toc(
                    fmt_file_bytes or b'', fmt_filename or "text.txt",
                    fmt_text, [fmt_text] if fmt_text and not fmt_file_bytes else fmt_pages
                )
            toc_color = ("red" if toc_r.missing_required
                         else ("yellow" if toc_r.orphan_entries or toc_r.missing_suggested
                               else "green"))
            color_box(f"<b>{toc_r.summary}</b>", toc_color)

            if toc_r.missing_required:
                show_problems(
                    [f"🔴 必填章节缺失：「{s.name}」（{s.category}标）" for s in toc_r.missing_required],
                    "缺失的必填章节"
                )
            if toc_r.orphan_entries:
                show_problems(
                    [f"🟡 目录有「{e.title}」但正文未找到" for e in toc_r.orphan_entries[:5]],
                    "目录与正文不对应"
                )
            if toc_r.toc_entries:
                with st.expander(f"📑 识别到的目录结构（{len(toc_r.toc_entries)}项）"):
                    rows_toc = [{
                        "层级": "一级" if e.level==1 else "二级",
                        "章节标题": e.title,
                        "页码": e.page_ref or "—",
                        "正文对应": "✅" if e.found_in_body else "❓",
                    } for e in toc_r.toc_entries]
                    def hl_toc(row):
                        return ["background:#fff3cd"]*len(row) if row["正文对应"]=="❓" else [""]*len(row)
                    st.dataframe(pd.DataFrame(rows_toc).style.apply(hl_toc, axis=1),
                                 use_container_width=True, hide_index=True)
        else:
            color_box("ℹ️ 需上传文件才能核查目录完整性", "gray")

        # ── ⑥ 页眉页脚一致性 ────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📄 ⑥ 页眉页脚一致性")
        if fmt_file_bytes:
            with st.spinner("检查页眉/页脚…"):
                from modules.header_footer_check import check_header_footer
                hf_pages = fmt_pages if 'fmt_pages' in dir() else []
                hf_r = check_header_footer(fmt_file_bytes, fmt_filename, fmt_text, hf_pages)
            hf_color = ("red" if any(i.risk_level=="高" for i in hf_r.issues)
                        else ("yellow" if hf_r.issues else "green"))
            color_box(f"<b>{hf_r.summary}</b>", hf_color)
            if hf_r.issues:
                for issue in hf_r.issues:
                    icon = "🔴" if issue.risk_level=="高" else "🟠"
                    color_box(
                        f"{icon} <b>{issue.issue_type}</b><br>"
                        f"{issue.description.replace(chr(10),'<br>')}<br>"
                        f"<small>💡 {issue.suggestion}</small>",
                        "red" if issue.risk_level=="高" else "yellow"
                    )
            all_hf = hf_r.headers + hf_r.footers
            if all_hf:
                with st.expander(f"🔍 提取的页眉/页脚内容（{len(all_hf)}处）"):
                    for hf in all_hf:
                        st.markdown(f"**{hf.location}**：`{hf.content[:80]}`")
        else:
            color_box("ℹ️ 页眉页脚检测需上传 Word 或 PDF 文件", "gray")

        # ── ⑦ 页码连续性 ──────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🔢 ⑦ 页码连续性检测")
        if fmt_file_bytes:
            with st.spinner("扫描页码…"):
                from modules.page_number_check import check_page_numbers
                pn_r = check_page_numbers(fmt_file_bytes, fmt_filename, fmt_text,
                                          fmt_pages if 'fmt_pages' in dir() else [])
            pn_color = ("red" if any(i.risk_level=="高" for i in pn_r.issues)
                        else ("yellow" if pn_r.issues else "green"))
            color_box(f"<b>{pn_r.summary}</b>", pn_color)
            for issue in pn_r.issues:
                icon = "🔴" if issue.risk_level=="高" else "🟠"
                color_box(
                    f"{icon} <b>{issue.issue_type}</b>：{issue.description}<br>"
                    f"<small>💡 {issue.suggestion}</small>",
                    "red" if issue.risk_level=="高" else "yellow"
                )
            if pn_r.detected_numbers:
                found_cnt = sum(1 for p in pn_r.detected_numbers if p is not None)
                st.caption(f"共扫描 {len(pn_r.detected_numbers)} 页，成功识别页码 {found_cnt} 页")
        else:
            color_box("ℹ️ 页码连续性检测需上传 PDF 文件", "gray")

        # ── ⑧ 字体/字号规范 ────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🔤 ⑧ 字体/字号规范检查")
        if fmt_file_bytes:
            with st.spinner("检查字体规范…"):
                from modules.font_check import check_fonts
                fc_r = check_fonts(fmt_file_bytes, fmt_filename, fmt_text,
                                   fmt_pages if 'fmt_pages' in dir() else [])
            fc_font_color = ("yellow" if fc_r.issues else "green")
            color_box(f"<b>{fc_r.summary}</b>", fc_font_color)
            for issue in fc_r.issues:
                color_box(
                    f"{'🟠' if issue.risk_level=='中' else '💡'} <b>{issue.issue_type}</b>："
                    f"{issue.description}<br><small>💡 {issue.suggestion}</small>",
                    "yellow" if issue.risk_level=="中" else "blue"
                )
            if fc_r.font_stats:
                with st.expander(f"🔤 字体使用统计（{len(fc_r.font_stats)}种）"):
                    fs_rows = [{"字体": k, "出现次数": v}
                               for k, v in sorted(fc_r.font_stats.items(),
                                                  key=lambda x: -x[1])[:10]]
                    st.dataframe(pd.DataFrame(fs_rows),
                                 use_container_width=True, hide_index=True)
        else:
            color_box("ℹ️ 字体/字号检查需上传 Word（.docx）文件", "gray")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 8 — 多标书比较（串标检测 + 中标优势排名）
# ══════════════════════════════════════════════════════════════════════════════
with tabs[7]:
    st.subheader("🔍 多标书比较分析")
    st.caption(
        "同时上传多份标书，自动完成：\n"
        "**① 串标/陪标风险检测** · **② 综合评分** · **③ 中标优势排名**\n\n"
        "⚠️ 串标检测仅供内部辅助参考，不构成法律认定依据"
    )

    compare_files = st.file_uploader(
        "上传多份标书（2~10份，PDF / Word / 图片，每份代表一个投标方）",
        type=PDF_TYPES + IMAGE_TYPES + WORD_TYPES,
        accept_multiple_files=True,
        key="compare_files",
        help="上传数量越多，比较越准确。建议每份命名为投标方名称.pdf"
    )

    if compare_files and len(compare_files) >= 2:
        st.info(f"已上传 {len(compare_files)} 份标书，点击开始分析")
        if st.button("🔍 开始多标书比较", key="compare_btn", type="primary"):
            from modules.ocr_helper import extract_text_smart
            from modules.bid_compare import compare_bids

            bid_data = []
            progress = st.progress(0, text="正在提取文本…")
            for idx, f in enumerate(compare_files):
                progress.progress((idx+1)/len(compare_files),
                                   text=f"提取 {f.name}…（{idx+1}/{len(compare_files)}）")
                raw = f.read()
                text, _, pages = extract_text_smart(raw, f.name)
                bid_data.append((raw, f.name, text, pages))
            progress.empty()

            with st.spinner("分析中…"):
                result = compare_bids(bid_data)

            # ── 串标风险总览 ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("### ⚠️ 串标/陪标风险检测")
            risk_colors = {"无": "green", "低": "yellow", "中": "yellow", "高": "red"}
            risk_icons  = {"无": "✅", "低": "🟡", "中": "🟠", "高": "🔴"}
            col_risk = result.collusion_risk_level
            color_box(
                f"{risk_icons[col_risk]} <b>串标风险：{col_risk}</b>"
                + (f"（发现 {len(result.collusion_flags)} 项风险信号）"
                   if result.collusion_flags else "（未发现明显串标信号）"),
                risk_colors[col_risk]
            )

            if result.collusion_flags:
                for flag in result.collusion_flags:
                    icon = "🔴" if flag.risk_level=="高" else ("🟠" if flag.risk_level=="中" else "🔵")
                    involved = "、".join(f"「{f}」" for f in flag.bids_involved)
                    color_box(
                        f"{icon} <b>{flag.flag_type}</b>（{flag.risk_level}风险）<br>"
                        f"涉及：{involved}<br>"
                        f"说明：{flag.description}<br>"
                        f"<small>证据：{flag.evidence}</small>",
                        "red" if flag.risk_level=="高" else "yellow"
                    )
            else:
                st.success("✅ 未发现联系方式重复、文本雷同、报价规律等串标信号")

            # ── 综合评分排名 ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("### 🏆 综合评分与中标优势排名")

            MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}
            for s in result.scores:
                medal = MEDAL.get(s.rank, f"#{s.rank}")
                score_color = "green" if s.total_score >= 80 else \
                              ("yellow" if s.total_score >= 60 else "red")
                strengths_html = " ".join(f'<span style="background:#d4edda;padding:2px 8px;border-radius:10px;font-size:0.82rem">{x}</span>' for x in s.strengths)
                weaknesses_html = " ".join(f'<span style="background:#f8d7da;padding:2px 8px;border-radius:10px;font-size:0.82rem">{x}</span>' for x in s.weaknesses)
                price_str = f"¥{s.price:,.0f}" if s.price else "未识别"
                color_box(
                    f"<b>{medal} 第{s.rank}名：{s.filename}</b>（{s.company}）<br>"
                    f"综合得分：<b>{s.total_score}</b>/100 &nbsp;|&nbsp; 报价：{price_str}<br>"
                    f"{strengths_html} {weaknesses_html}<br>"
                    f"<small>建议：{s.recommendation}</small>",
                    score_color
                )

            # 雷达图数据表
            with st.expander("📊 各维度评分对比表"):
                df_score = pd.DataFrame([{
                    "标书": s.filename,
                    "综合": s.total_score,
                    "价格竞争力": s.price_score,
                    "字段完整": s.field_score,
                    "资质": s.qualification_score,
                    "格式规范": s.format_score,
                    "名称一致": s.name_consistency_score,
                    "建议": s.recommendation,
                } for s in result.scores])
                st.dataframe(df_score, use_container_width=True, hide_index=True)
                st.bar_chart(df_score.set_index("标书")[
                    ["价格竞争力","字段完整","资质","格式规范","名称一致"]
                ], height=280)

            # ── 最终推荐 ─────────────────────────────────────────────
            st.markdown("---")
            st.markdown("### 🎯 最终推荐")
            color_box(result.winner_recommendation.replace("\n", "<br>"),
                      "green" if result.collusion_risk_level == "无" else "yellow")

            # 导出报告
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df_score.to_excel(writer, sheet_name="综合评分", index=False)
                if result.collusion_flags:
                    pd.DataFrame([{
                        "风险类型": f.flag_type, "风险等级": f.risk_level,
                        "说明": f.description, "涉及标书": "、".join(f.bids_involved),
                        "证据": f.evidence,
                    } for f in result.collusion_flags]).to_excel(
                        writer, sheet_name="串标风险", index=False)
            st.download_button(
                "⬇️ 导出比较报告Excel",
                data=out.getvalue(),
                file_name=f"多标书比较_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="compare_export"
            )
    elif compare_files and len(compare_files) == 1:
        st.warning("请至少上传 **2 份**标书才能进行比较分析")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 9 — 综合诊断报告
# ══════════════════════════════════════════════════════════════════════════════
with tabs[8]:
    st.subheader("📊 综合诊断报告")
    st.caption(
        "一次上传，自动运行全部检查，生成完整的优缺点报告。\n"
        "支持 **全局视图**（总体评分+优先建议）和 **细节视图**（逐项精确定位）"
    )

    rpt_file = st.file_uploader(
        "上传标书文件（PDF / Word / 图片）",
        type=PDF_TYPES + IMAGE_TYPES + WORD_TYPES,
        key="rpt_file",
    )

    if rpt_file:
        if st.button("📊 生成综合诊断报告", key="rpt_btn", type="primary"):
            from modules.ocr_helper import extract_text_smart
            from modules.report_generator import generate_report

            raw_bytes = rpt_file.read()
            with st.spinner("提取文本中…"):
                full_text, method, pages = extract_text_smart(raw_bytes, rpt_file.name)

            with st.spinner("运行全部检查（约15~30秒）…"):
                rpt = generate_report(raw_bytes, rpt_file.name, full_text, pages)

            # ── 总分仪表盘 ───────────────────────────────────────────
            score_color = "green" if rpt.total_score >= 80 else \
                          ("yellow" if rpt.total_score >= 60 else "red")

            # 评级徽章
            if rpt.total_score >= 90:   grade, grade_color = "A  优秀", "#28a745"
            elif rpt.total_score >= 80: grade, grade_color = "B  良好", "#5cb85c"
            elif rpt.total_score >= 70: grade, grade_color = "C  待改进", "#ffc107"
            elif rpt.total_score >= 60: grade, grade_color = "D  问题较多", "#fd7e14"
            else:                       grade, grade_color = "E  需大改", "#dc3545"

            c_score, c_grade, c_s, c_h, c_m = st.columns([2, 2, 2, 2, 2])
            c_score.metric("综合得分", f"{rpt.total_score} / 100")
            c_grade.markdown(f"<div style='text-align:center;margin-top:8px'>"
                             f"<span style='background:{grade_color};color:white;padding:4px 16px;"
                             f"border-radius:20px;font-weight:700;font-size:1.1rem'>{grade}</span></div>",
                             unsafe_allow_html=True)
            c_s.metric("✅ 优势项", len(rpt.strengths))
            c_h.metric("🔴 高风险", len(rpt.issues_high))
            c_m.metric("🟠 中风险", len(rpt.issues_mid))

            color_box(f"<b>诊断摘要：</b>{rpt.summary_text}", score_color)

            # ── 维度评分条形图 ────────────────────────────────────────
            if rpt.score_breakdown:
                with st.expander("📈 各维度评分详情", expanded=True):
                    df_bd = pd.DataFrame([
                        {"维度": k, "得分": v,
                         "状态": "✅ 良好" if v>=80 else ("⚠️ 一般" if v>=60 else "❌ 需改进")}
                        for k, v in sorted(rpt.score_breakdown.items(), key=lambda x: -x[1])
                    ])
                    def hl_bd(row):
                        v = row["得分"]
                        if v >= 80: return ["background:#d4edda"]*len(row)
                        if v >= 60: return ["background:#fff3cd"]*len(row)
                        return ["background:#f8d7da"]*len(row)
                    st.dataframe(df_bd.style.apply(hl_bd, axis=1),
                                 use_container_width=True, hide_index=True)
                    st.bar_chart(df_bd.set_index("维度")["得分"], height=200)

            # ── 视图切换 ──────────────────────────────────────────────
            st.markdown("---")
            view_mode = st.radio("查看模式", ["🌐 全局视图（优先建议）", "🔬 细节视图（逐项问题）"],
                                 horizontal=True, key="rpt_view")

            # ═════════════════════════════════════════════════════════
            # 全局视图
            # ═════════════════════════════════════════════════════════
            if "全局" in view_mode:
                # 优先改进建议
                if rpt.top_suggestions:
                    st.markdown("### 🎯 最优先改进建议")
                    st.caption("按严重程度排序，从第1条开始改起")
                    for i, s in enumerate(rpt.top_suggestions, 1):
                        color_box(f"<b>第{i}优先：</b>{s}", "red" if i <= 2 else "yellow")

                # 优势汇总
                if rpt.strengths:
                    st.markdown("### 💪 标书优势（保持）")
                    cols = st.columns(min(3, len(rpt.strengths)))
                    for i, item in enumerate(rpt.strengths):
                        with cols[i % len(cols)]:
                            st.markdown(
                                f'<div style="background:#d4edda;border-radius:10px;padding:12px;'
                                f'margin:4px 0;text-align:center">'
                                f'<div style="font-size:1.4rem">{item.icon}</div>'
                                f'<div style="font-weight:600;font-size:0.9rem">{item.title}</div>'
                                f'<div style="font-size:0.78rem;color:#555;margin-top:4px">{item.detail[:50]}</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                # 问题汇总（仅显示高+中，折叠低）
                all_issues = rpt.issues_high + rpt.issues_mid
                if all_issues:
                    st.markdown("### ⚠️ 需改进的问题（按严重度）")
                    for item in all_issues:
                        sev_color = "red" if item.severity == "高" else "yellow"
                        sev_icon  = "🔴" if item.severity == "高" else "🟠"
                        color_box(
                            f"{sev_icon} <b>[{item.category}] {item.title}</b><br>"
                            f"<small>💡 建议：{item.suggestion}</small>",
                            sev_color
                        )

                if rpt.issues_low:
                    with st.expander(f"🔵 提示性问题（{len(rpt.issues_low)}项，可酌情处理）"):
                        for item in rpt.issues_low:
                            color_box(f"🔵 [{item.category}] {item.title}：{item.detail[:60]}", "blue")

            # ═════════════════════════════════════════════════════════
            # 细节视图
            # ═════════════════════════════════════════════════════════
            else:
                st.markdown("### 🔬 逐项问题详情（含精确位置）")
                st.caption("点击每行展开查看完整说明和修改建议")

                all_issues = rpt.issues_high + rpt.issues_mid + rpt.issues_low
                if not all_issues:
                    st.success("🎉 未发现任何问题！")
                else:
                    for item in all_issues:
                        sev_icon = {"高": "🔴", "中": "🟠", "低": "🔵"}.get(item.severity, "⚪")
                        with st.expander(
                            f"{sev_icon} [{item.category}] {item.title}  ·  📍{item.location}"
                        ):
                            c_d, c_s = st.columns([3, 2])
                            with c_d:
                                st.markdown(f"**问题详情：**")
                                st.markdown(item.detail)
                                st.markdown(f"**📍 位置：** `{item.location}`")
                            with c_s:
                                st.markdown(f"**💡 修改建议：**")
                                st.info(item.suggestion if item.suggestion else "参见对应检查Tab")

                if rpt.strengths:
                    with st.expander(f"✅ 优势项（{len(rpt.strengths)}项）"):
                        for item in rpt.strengths:
                            color_box(f"{item.icon} <b>{item.title}</b>：{item.detail}", "green")

            # ── 导出报告 ──────────────────────────────────────────────
            st.markdown("---")
            st.markdown("### ⬇️ 导出完整报告")

            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                # 总览 Sheet
                pd.DataFrame([{
                    "文件名": rpt.filename, "扫描日期": rpt.scan_date,
                    "综合得分": rpt.total_score, "评级": grade.strip(),
                    "摘要": rpt.summary_text,
                }]).to_excel(writer, sheet_name="总览", index=False)

                # 维度得分
                pd.DataFrame([{"维度": k, "得分": v} for k, v in rpt.score_breakdown.items()]
                              ).to_excel(writer, sheet_name="维度评分", index=False)

                # 优先建议
                pd.DataFrame([{"优先级": i+1, "建议": s}
                               for i, s in enumerate(rpt.top_suggestions)]
                              ).to_excel(writer, sheet_name="改进建议", index=False)

                # 全部问题
                all_rows = []
                for item in rpt.issues_high + rpt.issues_mid + rpt.issues_low:
                    all_rows.append({
                        "严重度": item.severity, "类别": item.category,
                        "问题": item.title, "详情": item.detail,
                        "位置": item.location, "建议": item.suggestion,
                    })
                if all_rows:
                    pd.DataFrame(all_rows).to_excel(writer, sheet_name="问题清单", index=False)

                # 优势
                if rpt.strengths:
                    pd.DataFrame([{"类别": i.category, "优势": i.title, "说明": i.detail}
                                   for i in rpt.strengths]
                                 ).to_excel(writer, sheet_name="优势项", index=False)

            st.download_button(
                "⬇️ 下载完整诊断报告（Excel）",
                data=out.getvalue(),
                file_name=f"标书诊断报告_{rpt.filename}_{rpt.scan_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rpt_export"
            )


# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<div style='text-align:center;color:#aaa;font-size:0.8rem'>"
    "标书CT扫描仪 v1.7 · 结果仅供辅助参考，最终以人工审核为准 · "
    "所有文件本地处理，不上传任何服务器"
    "</div>",
    unsafe_allow_html=True,
)
