"""
Module D: 价格大小写一致性校验
将阿拉伯数字金额转换为中文大写，与用户输入/OCR识别的大写进行对比。
纯Python实现，无额外依赖。
"""
import re
from dataclasses import dataclass
from typing import Optional


CN_NUMS = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']


def _convert_section(n: int) -> str:
    """将 0-9999 转换为中文大写（4位块），0 返回空字符串。"""
    if n == 0:
        return ''
    digits = [n // 1000 % 10, n // 100 % 10, n // 10 % 10, n % 10]
    units  = ['仟', '佰', '拾', '']
    result = ''
    need_zero = False
    for digit, unit in zip(digits, units):
        if digit:
            if need_zero:
                result += '零'
                need_zero = False
            result += CN_NUMS[digit] + unit
        elif result:
            need_zero = True
    return result


def to_chinese_upper(amount: float) -> str:
    """
    将金额（元）转换为中文大写。
    例如：123456.78 → 壹拾贰万叁仟肆佰伍拾陆元柒角捌分
    """
    if amount < 0:
        prefix = '负'
        amount = -amount
    else:
        prefix = ''

    # 用整数避免浮点误差
    amount_cents = round(amount * 100)
    fen  = amount_cents % 10
    jiao = (amount_cents // 10) % 10
    int_part = amount_cents // 100

    if int_part == 0 and jiao == 0 and fen == 0:
        return '零元整'

    # 分解万亿级别
    yi   = int_part // 100_000_000
    wan  = int_part % 100_000_000 // 10_000
    ge   = int_part % 10_000

    int_result = ''
    if yi:
        int_result += _convert_section(yi) + '亿'
    if wan:
        if int_result and wan < 1000:
            int_result += '零'
        int_result += _convert_section(wan) + '万'
    if ge:
        if int_result and ge < 1000:
            int_result += '零'
        int_result += _convert_section(ge)

    int_result = int_result or '零'
    result = prefix + int_result + '元'

    if jiao == 0 and fen == 0:
        result += '整'
    elif jiao == 0:
        result += '零' + CN_NUMS[fen] + '分'
    elif fen == 0:
        result += CN_NUMS[jiao] + '角整'
    else:
        result += CN_NUMS[jiao] + '角' + CN_NUMS[fen] + '分'

    return result


# 规范化映射（处理用户可能用的简写/异体字）
NORMALIZE_MAP = {
    '一': '壹', '二': '贰', '三': '叁', '四': '肆', '五': '伍',
    '六': '陆', '七': '柒', '八': '捌', '九': '玖', '十': '拾',
    '百': '佰', '千': '仟', '万': '万', '亿': '亿', '元': '元',
    '圆': '元', '０': '零', '整': '整', '正': '整',
}


def normalize_cn_amount(text: str) -> str:
    """规范化大写金额文本，替换异体字。"""
    for k, v in NORMALIZE_MAP.items():
        text = text.replace(k, v)
    # 移除空格和多余符号
    text = re.sub(r'[,，\s¥￥]', '', text)
    return text.strip()


@dataclass
class PriceCheckResult:
    input_number: float
    input_cn_raw: str          # 用户输入的大写
    converted_cn: str          # 程序转换的大写
    input_cn_normalized: str   # 规范化后的用户输入
    is_match: bool
    status: str
    color: str
    note: str


def check_price(number_str: str, cn_text: str) -> PriceCheckResult:
    """
    检验阿拉伯数字金额与中文大写是否一致。
    number_str: 如 "1234567.89" 或 "1,234,567.89" 或 "123万4567.89"
    cn_text: 如 "壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分"
    """
    # 清洗数字输入
    clean_num = number_str.replace(',', '').replace('，', '').replace(' ', '').replace('¥', '').replace('￥', '')
    # 处理"万"单位缩写
    if '万' in clean_num:
        clean_num = clean_num.replace('万', '')
        try:
            amount = float(clean_num) * 10000
        except ValueError:
            return PriceCheckResult(0, cn_text, '', cn_text, False, '❌ 数字格式无效', 'red', f'无法解析：{number_str}')
    else:
        try:
            amount = float(clean_num)
        except ValueError:
            return PriceCheckResult(0, cn_text, '', cn_text, False, '❌ 数字格式无效', 'red', f'无法解析：{number_str}')

    converted = to_chinese_upper(amount)
    normalized_input = normalize_cn_amount(cn_text)
    normalized_converted = normalize_cn_amount(converted)

    is_match = normalized_input == normalized_converted

    if is_match:
        status = '✅ 大小写一致'
        color = 'green'
        note = f'数字 {amount:,.2f} 元 ↔ {converted}'
    else:
        status = '❌ 大小写不一致'
        color = 'red'
        # 找出差异点
        diff_note = _find_diff(normalized_input, normalized_converted)
        note = f'正确大写应为：【{converted}】\n您输入：【{cn_text}】\n{diff_note}'

    return PriceCheckResult(
        input_number=amount,
        input_cn_raw=cn_text,
        converted_cn=converted,
        input_cn_normalized=normalized_input,
        is_match=is_match,
        status=status,
        color=color,
        note=note,
    )


def _find_diff(a: str, b: str) -> str:
    """简单差异说明。"""
    if len(a) != len(b):
        return f'字符数不同（输入 {len(a)} 字 vs 正确 {len(b)} 字），可能漏写或多写了单位'
    diffs = [(i, a[i], b[i]) for i in range(len(a)) if a[i] != b[i]]
    if diffs:
        parts = [f'第{i+1}位："{x}"→应为"{y}"' for i, x, y in diffs[:3]]
        return '差异：' + '；'.join(parts)
    return ''


def parse_price_from_text(text: str) -> list:
    """从文本中提取所有金额（数字+大写配对），返回候选列表。"""
    results = []
    # 匹配"投标报价：1,234,567.89元（大写：壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分）"类型
    pattern = r'([0-9,.，万千百]+\.?\d*)\s*[元万]?\s*[（(【\[]?\s*大写[：:]\s*([^）)】\]\n]{5,40})\s*[）)】\]]?'
    for m in re.finditer(pattern, text):
        results.append((m.group(1).strip(), m.group(2).strip()))
    return results
