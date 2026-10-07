from typing import List

from .schemas import (
    PageData,
    StructuredDocument,
    TextBlock,
    TableData,
    FigureData
)


def build_page(
    page_number: int,
    width: float,
    height: float,
    raw_text: str,
    blocks: List[TextBlock],
    tables: List[TableData],
    figures: List[FigureData],
    ocr_text: str = ""
) -> PageData:
    """
    把当前页面已经解析出来的所有结果，
    统一组装成 PageData。
    """

    return PageData(
        page=page_number,
        width=width,
        height=height,
        raw_text=raw_text,
        blocks=blocks,
        tables=tables,
        figures=figures,
        ocr_text=ocr_text
    )


def build_document(
    source: str,
    title: str,
    pages: List[PageData]
) -> StructuredDocument:
    """
    把所有 PageData 统一组装成 StructuredDocument。
    """

    return StructuredDocument(
        source=source,
        title=title,
        total_pages=len(pages),
        pages=pages
    )