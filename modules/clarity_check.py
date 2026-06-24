"""
印章/证书图片清晰度检测模块
方法：拉普拉斯方差（Laplacian Variance）— 业界标准模糊度评估
原理：清晰图片边缘锐利，拉普拉斯方差大；模糊图片边缘平滑，方差小
"""
import io
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from PIL import Image, ImageFilter
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import fitz  # PyMuPDF
    FITZ_OK = True
except ImportError:
    FITZ_OK = False


@dataclass
class PageClarity:
    page_num: int
    score: float           # 拉普拉斯方差，越大越清晰
    label: str             # 清晰/轻微模糊/模糊/非常模糊
    color: str             # green/yellow/red/darkred
    note: str


@dataclass
class ClarityResult:
    file_type: str         # pdf / image
    pages: List[PageClarity] = field(default_factory=list)
    overall_score: float = 0.0
    overall_label: str = ""
    overall_color: str = "gray"
    problems: List[str] = field(default_factory=list)
    suggestion: str = ""


# ─── 阈值（实验值，印章图片通常300dpi扫描时方差>200为清晰）─────────────
THRESHOLDS = [
    (500,  "✅ 清晰",     "green",   ""),
    (200,  "⚠️ 轻微模糊", "yellow",  "印章细节可辨认，但建议重新扫描（≥300dpi）"),
    (80,   "❌ 模糊",     "red",     "印章文字难以辨认，可能被评标委员会质疑"),
    (0,    "🔴 非常模糊", "darkred", "印章几乎不可辨认，须重新加盖并扫描"),
]


def _laplacian_variance(img: "Image.Image") -> float:
    """计算灰度图像的拉普拉斯方差"""
    gray = img.convert("L")
    # 用3×3拉普拉斯核卷积
    lap = gray.filter(ImageFilter.Kernel(
        size=3,
        kernel=[-1, -1, -1,
                -1,  8, -1,
                -1, -1, -1],
        scale=1, offset=128
    ))
    import statistics
    pixels = list(lap.getdata())
    mean = sum(pixels) / len(pixels)
    variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
    return variance


def _classify(score: float) -> tuple:
    for threshold, label, color, note in THRESHOLDS:
        if score >= threshold:
            return label, color, note
    return THRESHOLDS[-1][1], THRESHOLDS[-1][2], THRESHOLDS[-1][3]


def _check_pil_image(img_bytes: bytes, page_num: int = 1) -> PageClarity:
    img = Image.open(io.BytesIO(img_bytes))
    score = _laplacian_variance(img)
    label, color, note = _classify(score)
    return PageClarity(
        page_num=page_num,
        score=round(score, 1),
        label=label,
        color=color,
        note=note or f"清晰度评分 {score:.0f}",
    )


def check_clarity(file_bytes: bytes, filename: str) -> ClarityResult:
    if not PIL_OK:
        return ClarityResult(file_type="unknown", overall_label="PIL未安装，无法检测",
                             overall_color="gray", suggestion="请安装Pillow: pip install Pillow")

    ext = filename.rsplit(".", 1)[-1].lower()

    # ── 图片文件 ─────────────────────────────────────────────
    if ext in ("jpg", "jpeg", "png", "bmp", "tiff", "tif"):
        try:
            pc = _check_pil_image(file_bytes)
            problems = []
            if pc.color != "green":
                problems.append(f"图片清晰度不足（评分 {pc.score:.0f}）：{pc.note}")
            suggestion = _make_suggestion(pc.color)
            return ClarityResult(
                file_type="image",
                pages=[pc],
                overall_score=pc.score,
                overall_label=pc.label,
                overall_color=pc.color,
                problems=problems,
                suggestion=suggestion,
            )
        except Exception as e:
            return ClarityResult(file_type="image", overall_label=f"检测失败：{e}", overall_color="gray")

    # ── PDF文件：逐页渲染后检测 ───────────────────────────────
    if ext == "pdf" and FITZ_OK:
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages: List[PageClarity] = []
            for i, page in enumerate(doc):
                # 渲染为 150dpi 图像（快速检测用）
                mat = fitz.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes_pg = pix.tobytes("png")
                pc = _check_pil_image(img_bytes_pg, page_num=i+1)
                pages.append(pc)

            if not pages:
                return ClarityResult(file_type="pdf", overall_label="PDF无页面", overall_color="gray")

            avg_score = sum(p.score for p in pages) / len(pages)
            worst = min(pages, key=lambda p: p.score)
            overall_label, overall_color, _ = _classify(avg_score)

            problems = [
                f"第{p.page_num}页清晰度不足（评分 {p.score:.0f}）：{p.note}"
                for p in pages if p.color not in ("green",)
            ]
            suggestion = _make_suggestion(overall_color)

            return ClarityResult(
                file_type="pdf",
                pages=pages,
                overall_score=round(avg_score, 1),
                overall_label=overall_label,
                overall_color=overall_color,
                problems=problems,
                suggestion=suggestion,
            )
        except Exception as e:
            return ClarityResult(file_type="pdf", overall_label=f"检测失败：{e}", overall_color="gray")

    return ClarityResult(file_type=ext, overall_label="不支持此文件格式", overall_color="gray")


def _make_suggestion(color: str) -> str:
    if color == "green":
        return ""
    if color == "yellow":
        return "建议：用平板扫描仪以300dpi或以上重新扫描，勿用手机斜拍"
    if color == "red":
        return "必须重新扫描！建议：① 使用平板扫描仪 ② 分辨率≥300dpi ③ 页面平整无阴影 ④ 避免手持拍摄"
    return "严重模糊，该文件可能被评标委员会直接否决，必须重新获取清晰版本"
