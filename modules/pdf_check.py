"""
Module C: PDF文字可复制性检测
判断上传的PDF/图片是否为文字版（可提取文本），还是图片扫描版（不可识别）。
支持格式：PDF / JPG / PNG / BMP / TIFF
逐页给出精确问题位置与原因。
"""
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from typing import List


@dataclass
class PageResult:
    page_num: int
    char_count: int
    status: str        # "text" | "image" | "mixed"
    note: str = ""
    problem: str = ""  # 具体问题说明（用于错误报告）


@dataclass
class PdfCheckResult:
    filename: str
    file_type: str          # "pdf" | "image"
    total_pages: int
    total_chars: int
    text_pages: int
    image_pages: int
    overall_status: str
    overall_color: str      # "green" | "yellow" | "red"
    pages: List[PageResult] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)   # 精确问题列表
    suggestion: str = ""


def check_pdf_text(file_bytes: bytes, filename: str = "标书.pdf") -> PdfCheckResult:
    """检测PDF或图片文件是否含有可提取的文字层。"""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else 'pdf'

    if ext in ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif', 'webp'):
        return _check_image(file_bytes, filename)
    else:
        return _check_pdf(file_bytes, filename)


def _check_image(file_bytes: bytes, filename: str) -> PdfCheckResult:
    """图片文件：直接判定为图片型，给出说明。"""
    from modules.ocr_helper import tesseract_available, ocr_image_bytes
    problems = []

    if tesseract_available():
        text = ocr_image_bytes(file_bytes)
        char_count = len(text)
        if char_count >= 50:
            note = f"OCR识别出 {char_count} 个字符，内容可通过OCR提取"
            status = "mixed"
            overall_status = "⚠️ 图片文件（OCR可识别）"
            overall_color = "yellow"
            problems.append("第1页：图片格式，非PDF文字版，依赖OCR识别（精度有限）")
        else:
            note = f"OCR仅识别出 {char_count} 个字符，文字密度低"
            status = "image"
            overall_status = "❌ 图片文件（OCR识别效果差）"
            overall_color = "red"
            problems.append(f"第1页：图片清晰度不足或版式复杂，OCR仅识别 {char_count} 字")
        suggestion = "图片文件不符合电子标书要求，请提交文字版PDF。"
    else:
        note = "图片格式，Tesseract未安装，无法评估内容"
        status = "image"
        overall_status = "⚠️ 图片文件（无OCR支持）"
        overall_color = "yellow"
        problems.append("第1页：图片文件，无法评估可复制性")
        suggestion = "图片文件不符合电子标书要求，请提交文字版PDF。"

    page = PageResult(1, len(file_bytes) // 100, status, note, problems[0] if problems else "")
    return PdfCheckResult(
        filename=filename, file_type="image",
        total_pages=1, total_chars=page.char_count,
        text_pages=0, image_pages=1,
        overall_status=overall_status, overall_color=overall_color,
        pages=[page], problems=problems, suggestion=suggestion,
    )


def _check_pdf(file_bytes: bytes, filename: str) -> PdfCheckResult:
    """PDF文件逐页检测。"""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    total_pages = len(doc)
    pages = []
    total_chars = 0
    problems = []

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        char_count = len(text)
        total_chars += char_count
        img_list = page.get_images(full=False)

        if char_count >= 50:
            status = "text"
            note = f"{char_count} 个可提取字符"
            problem = ""
        elif char_count > 0:
            status = "mixed"
            note = f"仅 {char_count} 个字符（可能只有页眉页脚）"
            problem = f"第{i+1}页：仅提取到 {char_count} 字，内容以图片为主，建议核查"
            problems.append(problem)
        else:
            status = "image"
            note = f"无可提取文字，含 {len(img_list)} 张嵌入图片"
            problem = f"第{i+1}页：纯图片页，0字符可提取——需OCR才能识别内容"
            problems.append(problem)

        pages.append(PageResult(i + 1, char_count, status, note, problem))

    text_pages  = sum(1 for p in pages if p.status == "text")
    image_pages = sum(1 for p in pages if p.status == "image")
    ratio = text_pages / total_pages if total_pages else 0

    if ratio >= 0.9:
        overall_status = "✅ 可复制（文字版PDF）"
        overall_color = "green"
        suggestion = "PDF含完整文字层，可直接复制内容，符合电子标书要求。"
    elif ratio >= 0.5:
        overall_status = "⚠️ 部分可复制（混合版PDF）"
        overall_color = "yellow"
        suggestion = (
            f"共 {total_pages} 页，其中 {image_pages} 页为扫描图片，无法直接复制。\n"
            "建议：图片页使用 Adobe Acrobat「识别文字」功能，或用原文档重新导出PDF。"
        )
    else:
        overall_status = "❌ 不可复制（扫描图片型PDF）"
        overall_color = "red"
        suggestion = (
            "该PDF为扫描件，无文字层。\n"
            "解决方法：\n"
            "① 用原始Word/Excel另存为PDF；\n"
            "② 或用Adobe Acrobat→工具→识别文字（OCR）转换。"
        )

    doc.close()
    return PdfCheckResult(
        filename=filename, file_type="pdf",
        total_pages=total_pages, total_chars=total_chars,
        text_pages=text_pages, image_pages=image_pages,
        overall_status=overall_status, overall_color=overall_color,
        pages=pages, problems=problems, suggestion=suggestion,
    )
