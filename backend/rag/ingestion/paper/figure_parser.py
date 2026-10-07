from pathlib import Path
from typing import List

import fitz

from .schemas import FigureData, TextBlock


def render_page(
    page: fitz.Page,
    output_path,
    zoom: float = 2.0
) -> Path:
    """
    把一个PDF页面渲染成PNG图片。

    参数：
        page:
            PyMuPDF Page对象

        output_path:
            输出图片路径

        zoom:
            放大倍率
            默认2.0，方便OCR和Vision识别

    返回：
        Path:
            生成的图片路径
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    matrix = fitz.Matrix(
        zoom,
        zoom
    )

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    pix.save(
        str(output_path)
    )

    return output_path


def get_figure_captions(
    blocks: List[TextBlock]
) -> List[TextBlock]:
    """
    从当前页面所有TextBlock中，
    找出Figure Caption。

    返回：
        List[TextBlock]
    """

    captions = []

    for block in blocks:

        if (
            block.block_type
            == "figure_caption"
        ):

            captions.append(
                block
            )

    return captions


def build_figure_clip(
    page: fitz.Page,
    caption_block: TextBlock
) -> fitz.Rect:
    """
    根据Figure Caption的位置，
    粗略推测Figure所在区域。

    当前策略：
        Figure通常位于Caption上方。

    所以：
        从Caption向上截取一定范围。

    这是启发式方法，
    后续可以升级成真正的Layout Model。
    """

    page_width = (
        page.rect.width
    )

    page_height = (
        page.rect.height
    )

    caption_y0 = (
        caption_block.y0
    )

    # 从caption向上取页面高度的42%
    clip_top = max(
        0,
        caption_y0
        - page_height * 0.42
    )

    # 底部直接取caption开始的位置
    clip_bottom = min(
        page_height,
        caption_y0
    )

    clip = fitz.Rect(
        0,
        clip_top,
        page_width,
        clip_bottom
    )

    return clip


def extract_figures(
    page: fitz.Page,
    page_number: int,
    blocks: List[TextBlock],
    output_dir
) -> List[FigureData]:
    """
    从一页PDF中提取Figure。

    当前流程：

        TextBlock
            ↓
        找Figure Caption
            ↓
        根据Caption定位Figure区域
            ↓
        裁剪成PNG
            ↓
        FigureData

    注意：
        这里暂时还不做OCR和Vision。
        OCR和Vision会在总流程中调用。
    """

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    figures_result = []

    figure_captions = (
        get_figure_captions(
            blocks
        )
    )

    for figure_id, caption_block in enumerate(
        figure_captions
    ):

        # ==========================================
        # 1. 计算Figure区域
        # ==========================================

        clip = build_figure_clip(
            page=page,
            caption_block=caption_block
        )


        # ==========================================
        # 2. 设置输出路径
        # ==========================================

        image_path = (
            output_dir
            / (
                f"page_{page_number}"
                f"_figure_{figure_id}.png"
            )
        )


        # ==========================================
        # 3. 渲染并裁剪Figure
        # ==========================================

        matrix = fitz.Matrix(
            2.0,
            2.0
        )

        pix = page.get_pixmap(
            matrix=matrix,
            clip=clip,
            alpha=False
        )

        pix.save(
            str(image_path)
        )


        # ==========================================
        # 4. 保存为FigureData
        # ==========================================

        figure_data = FigureData(
            figure_id=figure_id,

            page=page_number,

            image_path=str(
                image_path
            ),

            caption=caption_block.text,

            ocr_text="",

            vision_description=""
        )


        figures_result.append(
            figure_data
        )


    return figures_result 