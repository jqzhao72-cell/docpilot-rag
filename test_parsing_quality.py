from pathlib import Path

from rag.ingestion.paper.paper_parser import PaperParser


PAPER_DIR = Path("data/papers")

PDF_FILES = [
    "s41523-020-00197-2.pdf",
    "e4343521e6a9c4fddb0438c05deea52f8c3f.pdf",
    "journal.pone.0297260 (1).pdf",
]


parser = PaperParser(
    enable_ocr=True,
    enable_vision=False
)


for filename in PDF_FILES:

    pdf_path = PAPER_DIR / filename

    print("\n")
    print("#" * 100)
    print(f"开始审计: {filename}")
    print("#" * 100)

    try:

        document = parser.parse(
            pdf_path=pdf_path,
            output_root="data/parsed_documents"
        )

    except Exception as e:

        print("\n解析失败")

        print(
            f"错误类型: {type(e).__name__}"
        )

        print(
            f"错误信息: {e}"
        )

        continue


    # ==========================================================
    # 1. 文档级统计
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("文档级统计")
    print("=" * 100)

    print(
        f"标题: {document.title}"
    )

    print(
        f"总页数: {document.total_pages}"
    )


    total_blocks = 0
    total_tables = 0
    total_figures = 0
    total_figure_ocr_chars = 0


    for page in document.pages:

        total_blocks += len(
            page.blocks
        )

        total_tables += len(
            page.tables
        )

        total_figures += len(
            page.figures
        )


        for figure in page.figures:

            total_figure_ocr_chars += len(
                figure.ocr_text
            )


    print(
        f"总TextBlock数: {total_blocks}"
    )

    print(
        f"总Table数: {total_tables}"
    )

    print(
        f"总Figure数: {total_figures}"
    )

    print(
        f"Figure OCR总字符数: "
        f"{total_figure_ocr_chars}"
    )


    # ==========================================================
    # 2. Layout审计
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("LAYOUT审计")
    print("=" * 100)


    important_types = {
        "title",
        "heading",
        "header",
        "footer",
        "figure_caption",
        "table_caption",
    }


    for page in document.pages:

        page_has_special_block = False


        for block in page.blocks:

            if block.block_type in important_types:

                if not page_has_special_block:

                    print(
                        f"\n[Page {page.page}]"
                    )

                    page_has_special_block = True


                print(
                    f"type={block.block_type}"
                    f" | column={block.column}"
                    f" | font={block.font_size:.2f}"
                )

                print(
                    f"bbox="
                    f"({block.x0:.1f}, "
                    f"{block.y0:.1f}, "
                    f"{block.x1:.1f}, "
                    f"{block.y1:.1f})"
                )

                print(
                    "text="
                    + block.text[:500]
                )

                print(
                    "-" * 80
                )


    # ==========================================================
    # 3. Table审计
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("TABLE审计")
    print("=" * 100)


    found_table = False


    for page in document.pages:

        if not page.tables:
            continue


        found_table = True


        print(
            f"\n[Page {page.page}]"
        )


        for table in page.tables:

            print(
                f"\nTable ID: "
                f"{table.table_id}"
            )

            print(
                f"Caption: "
                f"{table.caption}"
            )

            print(
                f"BBox: "
                f"{table.bbox}"
            )

            print(
                f"行数: "
                f"{len(table.rows)}"
            )


            if table.rows:

                column_count = max(
                    len(row)
                    for row in table.rows
                )

            else:

                column_count = 0


            print(
                f"最大列数: "
                f"{column_count}"
            )


            print(
                "\n前5行:"
            )


            for row_index, row in enumerate(
                table.rows[:5]
            ):

                print(
                    f"Row {row_index}: {row}"
                )


            print(
                "-" * 80
            )


    if not found_table:

        print(
            "没有检测到任何Table"
        )


    # ==========================================================
    # 4. Figure审计
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("FIGURE审计")
    print("=" * 100)


    found_figure = False


    for page in document.pages:

        if not page.figures:
            continue


        found_figure = True


        print(
            f"\n[Page {page.page}]"
        )


        for figure in page.figures:

            print(
                f"\nFigure ID: "
                f"{figure.figure_id}"
            )

            print(
                f"图片路径: "
                f"{figure.image_path}"
            )

            print(
                f"Caption: "
                f"{figure.caption}"
            )

            print(
                f"OCR字符数: "
                f"{len(figure.ocr_text)}"
            )


            if figure.ocr_text:

                print(
                    "\nOCR前500字符:"
                )

                print(
                    figure.ocr_text[:500]
                )

            else:

                print(
                    "OCR结果为空"
                )


            print(
                "-" * 80
            )


    if not found_figure:

        print(
            "没有检测到任何Figure"
        )


    # ==========================================================
    # 5. 整页OCR审计
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("整页OCR审计")
    print("=" * 100)


    found_page_ocr = False


    for page in document.pages:

        if not page.ocr_text:
            continue


        found_page_ocr = True


        print(
            f"\nPage {page.page}"
        )

        print(
            f"OCR字符数: "
            f"{len(page.ocr_text)}"
        )

        print(
            page.ocr_text[:500]
        )


    if not found_page_ocr:

        print(
            "没有触发整页OCR"
        )

        print(
            "这通常说明PDF本身已经存在可提取的文本层。"
        )


    print("\n")
    print("#" * 100)

    print(
        f"{filename} 审计结束"
    )

    print("#" * 100)


print("\n")
print("=" * 100)
print("三篇论文解析质量审计完成")
print("=" * 100)