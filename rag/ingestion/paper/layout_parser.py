import re

import fitz

from .schemas import TextBlock
from .text_parser import clean_text


def detect_block_type(
    text: str,
    bbox,
    page_height: float,
    font_size: float,
    largest_font: float,
    page_number: int
) -> str:
    """
    根据文本内容、位置和字号，
    粗略判断文本块的类型。
    """

    text_clean = text.strip()

    x0, y0, x1, y1 = bbox


    # 1. 页眉
    if y0 < page_height * 0.06:
        return "header"


    # 2. 页脚
    if y1 > page_height * 0.94:
        return "footer"


    # 3. Figure Caption
    if re.match(
        r"^(fig\.?|figure)\s*\d+",
        text_clean,
        re.IGNORECASE
    ):
        return "figure_caption"


    # 4. Table Caption
    if re.match(
        r"^table\s*\d+",
        text_clean,
        re.IGNORECASE
    ):
        return "table_caption"


    # 5. 第一页的大字号文本
    #    可能是论文标题
    if (
        page_number == 1
        and largest_font > 0
        and font_size >= largest_font * 0.85
        and len(text_clean) < 300
    ):
        return "title"


    # 6. 较短 + 字号较大的文本
    #    可能是章节标题
    if (
        len(text_clean) < 150
        and font_size > 10
        and not text_clean.endswith(".")
    ):
        return "heading"


    # 7. 其他默认认为是正文
    return "body"


def detect_column(
    bbox,
    page_width: float
) -> str:
    """
    根据文本块在页面中的横向位置，
    粗略判断它属于左栏、右栏还是跨栏。
    """

    x0, y0, x1, y1 = bbox


    # 文本块完全偏左
    if x1 < page_width * 0.55:
        return "left"


    # 文本块完全偏右
    if x0 > page_width * 0.45:
        return "right"


    # 横跨页面中间
    return "full"


def extract_text_blocks(
    page: fitz.Page,
    page_number: int
):
    """
    从PDF页面中提取结构化文本块。

    返回：
        List[TextBlock]
    """

    # 获取页面结构化信息
    page_dict = page.get_text(
        "dict"
    )


    page_width = page.rect.width
    page_height = page.rect.height


    # =====================================================
    # 第一步：统计本页所有字号
    # =====================================================

    font_sizes = []


    for block in page_dict["blocks"]:

        # type != 0 表示不是文本块
        if block.get("type") != 0:
            continue


        for line in block.get(
            "lines",
            []
        ):

            for span in line.get(
                "spans",
                []
            ):

                font_size = span.get(
                    "size",
                    0
                )

                font_sizes.append(
                    font_size
                )


    # 获取本页最大字号
    if font_sizes:
        largest_font = max(
            font_sizes
        )
    else:
        largest_font = 0


    # =====================================================
    # 第二步：真正处理每一个文本Block
    # =====================================================

    results = []

    block_id = 0


    for block in page_dict["blocks"]:

        # 只处理文字块
        if block.get("type") != 0:
            continue


        block_text_list = []

        block_font_sizes = []


        # 一个Block里面可能包含很多Line
        for line in block.get(
            "lines",
            []
        ):

            line_text_list = []


            # 一个Line里面又有很多Span
            for span in line.get(
                "spans",
                []
            ):

                span_text = span.get(
                    "text",
                    ""
                )


                span_font_size = span.get(
                    "size",
                    0
                )


                line_text_list.append(
                    span_text
                )


                block_font_sizes.append(
                    span_font_size
                )


            # 把当前这一行的Span拼起来
            line_text = "".join(
                line_text_list
            )


            block_text_list.append(
                line_text
            )


        # 把多行拼成一个Block
        text = "\n".join(
            block_text_list
        )


        # 清洗文本
        text = clean_text(
            text
        )


        # 空文本不要
        if not text:
            continue


        # 获取这个Block的位置
        bbox = block.get(
            "bbox",
            [0, 0, 0, 0]
        )


        # 计算Block平均字号
        if block_font_sizes:

            avg_font_size = (
                sum(block_font_sizes)
                / len(block_font_sizes)
            )

        else:

            avg_font_size = 0


        # 判断Block类型
        block_type = detect_block_type(
            text=text,
            bbox=bbox,
            page_height=page_height,
            font_size=avg_font_size,
            largest_font=largest_font,
            page_number=page_number
        )


        # 判断左右栏
        column = detect_column(
            bbox=bbox,
            page_width=page_width
        )


        # 生成TextBlock对象
        text_block = TextBlock(
            block_id=block_id,

            page=page_number,

            text=text,

            x0=float(
                bbox[0]
            ),

            y0=float(
                bbox[1]
            ),

            x1=float(
                bbox[2]
            ),

            y1=float(
                bbox[3]
            ),

            block_type=block_type,

            font_size=float(
                avg_font_size
            ),

            column=column
        )


        results.append(
            text_block
        )


        block_id += 1


    return results