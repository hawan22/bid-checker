"""
文件命名检查模块
电子招投标平台常见拦截原因：文件名含空格、特殊字符、过长
"""
import re
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class NamingCheckResult:
    filename: str
    is_safe: bool
    problems: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# 电子招投标平台普遍不允许的字符
ILLEGAL_CHARS = r'[ <>:"/\\|?*\x00-\x1f（）【】「」『』]'
# 平台一般建议不超过 100 个字符（含扩展名）
MAX_LEN = 100
# 高风险字符（部分平台加解密后文件名变异）
RISKY_CHARS = r'[&%#@!^~`]'

# 常见合法字符白名单范围（中文、字母、数字、下划线、连字符、点）
SAFE_PATTERN = re.compile(r'^[\u4e00-\u9fa5a-zA-Z0-9_\-\.]+$')


def check_filename(filename: str) -> NamingCheckResult:
    name = os.path.basename(filename)
    problems = []
    suggestions = []

    # 1. 空格
    if ' ' in name:
        problems.append(f"文件名含空格（共 {name.count(' ')} 处），部分平台上传后解压失败")
        suggestions.append('将空格替换为下划线 "_"')

    # 2. 非法字符
    illegals = re.findall(ILLEGAL_CHARS, name)
    if illegals:
        unique = list(dict.fromkeys(illegals))
        problems.append(f"含非法字符：{''.join(unique)} — 多数招标平台会拦截")
        suggestions.append("只使用中文、字母、数字、下划线_、连字符-、英文点.")

    # 3. 高风险字符
    risky = re.findall(RISKY_CHARS, name)
    if risky:
        unique = list(dict.fromkeys(risky))
        problems.append(f"含高风险字符：{''.join(unique)} — 加解密后文件名可能变异")
        suggestions.append("删除 & % # @ ! ^ ~ ` 等特殊符号")

    # 4. 长度
    if len(name) > MAX_LEN:
        problems.append(f"文件名过长（{len(name)} 字符），建议 ≤{MAX_LEN} 字符")
        suggestions.append(f"缩短文件名至 {MAX_LEN} 字符以内")

    # 5. 以点或连字符开头（部分系统报错）
    stem = os.path.splitext(name)[0]
    if stem.startswith('.') or stem.startswith('-'):
        problems.append("文件名以 '.' 或 '-' 开头，部分系统会报错")
        suggestions.append("文件名改为以字母、数字或中文开头")

    # 6. 没有扩展名
    ext = os.path.splitext(name)[1]
    if not ext:
        problems.append("文件无扩展名，系统可能无法识别文件类型")

    is_safe = len(problems) == 0
    return NamingCheckResult(
        filename=name,
        is_safe=is_safe,
        problems=problems,
        suggestions=suggestions,
    )


def check_filenames(filenames: List[str]) -> List[NamingCheckResult]:
    return [check_filename(f) for f in filenames]
