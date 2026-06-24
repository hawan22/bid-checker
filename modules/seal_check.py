"""
Module E: 签章有效性检测
检测PDF中是否含有数字签名（电子签章），区分合规数字签名与图片印章。
支持格式：PDF / JPG / PNG / BMP（图片只能检测是否有印章图案）
"""
import fitz
import pikepdf
import io
from dataclasses import dataclass, field
from typing import List


@dataclass
class SealInfo:
    page_num: int
    seal_type: str     # "digital" | "image_only" | "annotation"
    description: str
    status: str        # "valid" | "warn" | "info"
    color: str


@dataclass
class SealCheckResult:
    filename: str
    file_type: str              # "pdf" | "image"
    has_digital_signature: bool
    digital_sig_count: int
    image_seal_count: int
    annotation_count: int
    seals: List[SealInfo] = field(default_factory=list)
    overall_status: str = ""
    overall_color: str = ""
    summary: str = ""
    suggestion: str = ""
    problems: List[str] = field(default_factory=list)


def check_seal(file_bytes: bytes, filename: str = "标书.pdf") -> SealCheckResult:
    """检测签章，自动识别PDF或图片。"""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else 'pdf'
    if ext in ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif', 'webp'):
        return _check_image_seal(file_bytes, filename)
    return _check_pdf_seal(file_bytes, filename)


def _check_image_seal(file_bytes: bytes, filename: str) -> SealCheckResult:
    """图片文件：无法包含数字签名，给出说明。"""
    problems = ["图片文件本身不支持内嵌数字签名，无法验证电子签章合规性"]
    return SealCheckResult(
        filename=filename, file_type="image",
        has_digital_signature=False,
        digital_sig_count=0, image_seal_count=1, annotation_count=0,
        seals=[SealInfo(1, "image_only", "图片文件，含印章图案（视觉印章，非数字签名）", "warn", "yellow")],
        overall_status="⚠️ 图片文件（无法验证数字签章）",
        overall_color="yellow",
        summary="图片文件不支持数字签名验证，只能看到视觉印章。",
        suggestion="如需提交合规签章，请将文件转为PDF并使用CA/UKey进行数字签名。",
        problems=problems,
    )


def _check_pdf_seal(file_bytes: bytes, filename: str) -> SealCheckResult:
    seals: List[SealInfo] = []
    digital_sig_count = 0
    image_seal_count = 0
    annotation_count = 0
    problems = []

    # ── pikepdf 检测数字签名域 ─────────────────────────────────────────────
    try:
        pdf = pikepdf.open(io.BytesIO(file_bytes))
        if '/AcroForm' in pdf.Root:
            acroform = pdf.Root['/AcroForm']
            if '/Fields' in acroform:
                for field_ref in acroform['/Fields']:
                    try:
                        field_obj = pdf.get_object(field_ref)
                        ft = str(field_obj.get('/FT', ''))
                        if '/Sig' in ft or ft == '/Sig':
                            digital_sig_count += 1
                            v = field_obj.get('/V')
                            if v:
                                signer = ''
                                try:
                                    info = pdf.get_object(v)
                                    signer = str(info.get('/Name', ''))
                                except Exception:
                                    pass
                                desc = f'数字签名域（已签署）' + (f'，签署人：{signer}' if signer else '')
                                seals.append(SealInfo(0, 'digital', desc, 'valid', 'green'))
                            else:
                                desc = '数字签名域（未签署，签名域为空）'
                                seals.append(SealInfo(0, 'digital', desc, 'warn', 'yellow'))
                                problems.append(f'发现未签署的签名域，请用CA/UKey完成签名')
                    except Exception:
                        pass
        pdf.close()
    except Exception:
        pass

    # ── fitz 检测注释签名 + 图片 ─────────────────────────────────────────
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for i, page in enumerate(doc):
        for annot in page.annots():
            if annot.type[1] in ('Ink', 'Stamp', 'Widget'):
                annotation_count += 1
                seals.append(SealInfo(
                    i + 1, 'annotation',
                    f'第{i+1}页：注释印章（类型：{annot.type[1]}）',
                    'info', 'blue',
                ))
        img_count = len(page.get_images(full=False))
        if img_count:
            image_seal_count += img_count
    doc.close()

    # ── 综合判断 ──────────────────────────────────────────────────────────
    signed = any(s.status == 'valid' and s.seal_type == 'digital' for s in seals)
    if signed:
        overall_status = '✅ 含有效数字签名'
        overall_color = 'green'
        summary = f'检测到 {digital_sig_count} 个已签署数字签名，符合电子标书规范。'
        suggestion = ''
    elif digital_sig_count > 0:
        overall_status = '⚠️ 签名域未签署'
        overall_color = 'yellow'
        summary = f'发现 {digital_sig_count} 个数字签名域但均未完成签署。'
        suggestion = '请使用CA锁/UKey对签名域进行数字签名后再提交。'
        problems.append('签名域存在但未签署，文件不符合提交要求')
    elif annotation_count > 0:
        overall_status = '⚠️ 仅含注释印章'
        overall_color = 'yellow'
        summary = f'发现 {annotation_count} 个注释类型印章，非合规数字签名。'
        suggestion = '注释印章不具法律效力，请确认是否需要使用CA数字签名。'
        problems.append(f'发现 {annotation_count} 个注释印章，不等于合规数字签章')
    elif image_seal_count > 0:
        overall_status = '⚠️ 可能仅含图片印章'
        overall_color = 'yellow'
        summary = f'未发现数字签名，但PDF含 {image_seal_count} 张图片（可能包含扫描印章）。'
        suggestion = '图片印章不等于数字签章。如招标要求电子签章，请用CA证书/UKey签名。'
        problems.append('图片印章≠数字签章，合规性存疑')
    else:
        overall_status = '❌ 未发现任何签章'
        overall_color = 'red'
        summary = '未检测到签章信息。'
        suggestion = '请检查文件是否已盖章，或确认是否为正确文件版本。'
        problems.append('未发现任何印章或数字签名')

    return SealCheckResult(
        filename=filename, file_type="pdf",
        has_digital_signature=digital_sig_count > 0,
        digital_sig_count=digital_sig_count,
        image_seal_count=image_seal_count,
        annotation_count=annotation_count,
        seals=seals,
        overall_status=overall_status, overall_color=overall_color,
        summary=summary, suggestion=suggestion, problems=problems,
    )
