from pathlib import Path

from rag.ingestion.paper.paper_parser import PaperParser
from rag.ingestion.paper.quality_checker import (
    evaluate_figure,
    evaluate_table,
)


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

    print("\n")
    print("#" * 100)
    print(f"开始质量测试: {filename}")
    print("#" * 100)

    pdf_path = PAPER_DIR / filename

    try:
        document = parser.parse(
            pdf_path=pdf_path,
            output_root="data/parsed_documents"
        )

    except Exception as e:
        print(f"解析失败: {type(e).__name__}: {e}")
        continue


    # ==========================================================
    # Figure质量
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("FIGURE QUALITY")
    print("=" * 100)

    figure_count = 0
    cloud_figure_count = 0

    for page in document.pages:

        for figure in page.figures:

            figure_count += 1

            result = evaluate_figure(
                figure=figure,
                page_width=page.width,
                page_height=page.height
            )

            print(
                f"\nPage {page.page} | "
                f"Figure {figure.figure_id}"
            )

            print(
                f"score = {result.score:.2f}"
            )

            print(
                f"level = {result.level}"
            )

            print(
                f"use_cloud = {result.use_cloud}"
            )

            if result.reasons:

                print("reasons:")

                for reason in result.reasons:
                    print(f"  - {reason}")

            else:
                print("reasons: 无明显问题")

            if result.use_cloud:
                cloud_figure_count += 1


    if figure_count == 0:
        print("没有检测到Figure")


    # ==========================================================
    # Table质量
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("TABLE QUALITY")
    print("=" * 100)

    table_count = 0
    cloud_table_count = 0

    for page in document.pages:

        for table in page.tables:

            table_count += 1

            result = evaluate_table(
                table=table
            )

            print(
                f"\nPage {page.page} | "
                f"Table {table.table_id}"
            )

            print(
                f"score = {result.score:.2f}"
            )

            print(
                f"level = {result.level}"
            )

            print(
                f"use_cloud = {result.use_cloud}"
            )

            if result.reasons:

                print("reasons:")

                for reason in result.reasons:
                    print(f"  - {reason}")

            else:
                print("reasons: 无明显问题")

            if result.use_cloud:
                cloud_table_count += 1


    if table_count == 0:
        print("没有检测到Table")


    # ==========================================================
    # 文档汇总
    # ==========================================================

    print("\n")
    print("=" * 100)
    print("QUALITY SUMMARY")
    print("=" * 100)

    print(
        f"Figure总数: {figure_count}"
    )

    print(
        f"需要云端处理的Figure: "
        f"{cloud_figure_count}"
    )

    print(
        f"Table总数: {table_count}"
    )

    print(
        f"需要云端处理的Table: "
        f"{cloud_table_count}"
    )


    if figure_count > 0:

        figure_cloud_ratio = (
            cloud_figure_count
            / figure_count
        )

        print(
            f"Figure云端触发比例: "
            f"{figure_cloud_ratio:.2%}"
        )


    if table_count > 0:

        table_cloud_ratio = (
            cloud_table_count
            / table_count
        )

        print(
            f"Table云端触发比例: "
            f"{table_cloud_ratio:.2%}"
        )


print("\n")
print("=" * 100)
print("质量检测全部完成")
print("=" * 100)