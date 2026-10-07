from pathlib import Path

from rag.ingestion.paper.cloud.aliyun_parser import (
    AliyunPaperParser
)


PDF_PATH = Path(
    "data/papers/journal.pone.0297260 (1).pdf"
)

OUTPUT_PATH = Path(
    "data/aliyun_results/journal_pone_0297260.json"
)


def main():

    parser = AliyunPaperParser(
        enable_vlm=True
    )

    result = parser.parse(
        str(PDF_PATH)
    )

    parser.save_json(
        result,
        str(OUTPUT_PATH)
    )

    print()
    print("=" * 60)
    print("测试结束")
    print("=" * 60)

    print(
        f"Layout数量: "
        f"{result['layout_count']}"
    )


if __name__ == "__main__":
    main()
