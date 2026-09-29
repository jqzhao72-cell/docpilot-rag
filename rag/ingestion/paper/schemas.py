from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TextBlock:
    """
    表示PDF页面中的一个文本块。
    """

    block_id: int
    page: int

    text: str

    x0: float
    y0: float
    x1: float
    y1: float

    block_type: str = "body"

    font_size: float = 0.0

    column: str = "unknown"


@dataclass
class TableData:
    """
    表示PDF页面中的一个表格。
    """

    table_id: int
    page: int

    bbox: List[float]

    rows: List[List[Optional[str]]]

    caption: str = ""


@dataclass
class FigureData:
    """
    表示PDF页面中的一张图片或图表。
    """

    figure_id: int
    page: int

    image_path: str

    caption: str = ""

    ocr_text: str = ""

    vision_description: str = ""


@dataclass
class PageData:
    """
    表示PDF中的一整页。
    """

    page: int

    width: float
    height: float

    raw_text: str

    blocks: List[TextBlock] = field(
        default_factory=list
    )

    tables: List[TableData] = field(
        default_factory=list
    )

    figures: List[FigureData] = field(
        default_factory=list
    )

    ocr_text: str = ""


@dataclass
class StructuredDocument:
    """
    表示解析完成的一整篇论文。
    """

    source: str

    title: str = ""

    total_pages: int = 0

    pages: List[PageData] = field(
        default_factory=list
    )