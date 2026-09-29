from pathlib import Path

from rag.ingestion.paper.paper_parser import PaperParser


PAPER_DIR = Path(
    "data/papers"
)


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

    pdf_path = (
        PAPER_DIR
        / filename
    )

    print(
        "\n"
        + "#" * 100
    )

    print(
        f"准备测试: {pdf_path}"
    )

    print(
        "#" * 100
    )

    try:

        document = parser.parse(
            pdf_path=pdf_path,
            output_root="data/parsed_documents"
        )


        print(
            "\n测试成功"
        )

        print(
            f"论文标题: {document.title}"
        )

        print(
            f"总页数: {document.total_pages}"
        )


        # ==========================================
        # 输出前几页的基本统计信息
        # ==========================================

        for page in document.pages[:3]:

            print(
                "\n"
                + "-" * 80
            )

            print(
                f"Page {page.page}"
            )

            print(
                f"普通文本长度: "
                f"{len(page.raw_text)}"
            )

            print(
                f"TextBlock数量: "
                f"{len(page.blocks)}"
            )

            print(
                f"Table数量: "
                f"{len(page.tables)}"
            )

            print(
                f"Figure数量: "
                f"{len(page.figures)}"
            )

            print(
                f"OCR文本长度: "
                f"{len(page.ocr_text)}"
            )


            # 打印前3个Block
            print(
                "\n前3个TextBlock:"
            )

            for block in page.blocks[:3]:

                print(
                    f"\nBlock {block.block_id}"
                )

                print(
                    f"type = {block.block_type}"
                )

                print(
                    f"column = {block.column}"
                )

                print(
                    f"font_size = "
                    f"{block.font_size:.2f}"
                )

                print(
                    f"bbox = "
                    f"({block.x0:.1f}, "
                    f"{block.y0:.1f}, "
                    f"{block.x1:.1f}, "
                    f"{block.y1:.1f})"
                )

                print(
                    "text = "
                    + block.text[:200]
                )


    except Exception as e:

        print(
            "\n测试失败"
        )

        print(
            f"错误类型: "
            f"{type(e).__name__}"
        )

        print(
            f"错误信息: {e}"
        )


print(
    "\n"
    + "=" * 100
)

print(
    "三篇论文测试结束"
)

print(
    "=" * 100
)