"""仅重建三篇指定学术论文的 text、figure、table chunks。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


# 支持从项目根目录直接执行 ``python scripts/rebuild_clean_paper_chunks.py``。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.ingestion.paper.paper_parser import PaperParser
from rag.ingestion.splitter import DEFAULT_CHUNK_SIZE, split_text
from scripts.rebuild_clean_chunks import (
    SAFE_TOKEN_LIMIT,
    detect_mojibake,
    missing_required_fields,
    normalize_chunk,
)


# 固定白名单确保本轮不会误处理 data/documents 下的企业制度 PDF。
PAPER_PATHS = (
    Path("data/papers/s41523-020-00197-2.pdf"),
    Path("data/papers/e4343521e6a9c4fddb0438c05deea52f8c3f.pdf"),
    Path("data/papers/journal.pone.0297260 (1).pdf"),
)

CORE_REQUIRED_FIELDS = (
    "text",
    "source",
    "chunk_index",
    "chunk_type",
    "section",
    "subsection",
    "page_start",
    "page_end",
)


def parse_args() -> argparse.Namespace:
    """读取输出路径和 Parser 可选项。"""

    parser = argparse.ArgumentParser(
        description="仅使用最新 PaperParser 和 splitter 重建三篇指定论文。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/evaluation/clean_paper_chunks.json"),
        help="论文 chunks JSON 输出路径。",
    )
    parser.add_argument(
        "--parser-output",
        type=Path,
        default=Path("data/evaluation/parsed_papers"),
        help="PaperParser 页面、图片和 StructuredDocument 输出目录。",
    )
    parser.add_argument(
        "--disable-ocr",
        action="store_true",
        help="关闭 Parser 默认 OCR；正式重建默认保持 OCR 开启。",
    )
    return parser.parse_args()


def validate_paper_paths(paths: Sequence[Path]) -> None:
    """确保三篇白名单论文都存在，且没有混入其他输入。"""

    if len(paths) != 3:
        raise ValueError(f"论文白名单必须恰好包含 3 个文件，当前为 {len(paths)} 个")

    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"论文文件不存在: {missing}")

    non_pdf = [str(path) for path in paths if path.suffix.lower() != ".pdf"]
    if non_pdf:
        raise ValueError(f"输入不是 PDF: {non_pdf}")


def promote_type_specific_ids(record: Dict[str, Any]) -> None:
    """把 Figure/Table 标识从 splitter metadata 提升到统一记录顶层。"""

    metadata = record["metadata"]
    if "figure_id" in metadata:
        record["figure_id"] = metadata["figure_id"]
    if "table_id" in metadata:
        record["table_id"] = metadata["table_id"]


def severe_pdf_text_corruption(text: str) -> Dict[str, Any] | None:
    """识别 PDF 自定义字体映射产生的高密度不可见控制码。"""

    invalid_characters = [
        character
        for character in text
        if (
            ord(character) < 32
            and character not in "\n\r\t"
        ) or 0x7F <= ord(character) <= 0x9F
    ]
    invalid_count = len(invalid_characters)
    invalid_ratio = invalid_count / max(len(text), 1)

    # 至少 3 个且占比不低于 1%，避免因单个偶发控制符误删正常正文。
    if invalid_count >= 3 and invalid_ratio >= 0.01:
        return {
            "reason": "high_density_pdf_control_characters",
            "invalid_character_count": invalid_count,
            "invalid_character_ratio": round(invalid_ratio, 4),
        }
    return None


def paper_metadata_issues(record: Dict[str, Any]) -> List[str]:
    """检查公共字段，并要求 figure/table chunk 拥有对应 ID。"""

    missing = missing_required_fields(record)
    for field_name in CORE_REQUIRED_FIELDS:
        if field_name not in record and field_name not in missing:
            missing.append(field_name)

    if record["chunk_type"] == "figure" and record.get("figure_id") is None:
        missing.append("figure_id")
    if record["chunk_type"] == "table" and record.get("table_id") is None:
        missing.append("table_id")
    return missing


def build_paper_statistics(
    chunks: Sequence[Dict[str, Any]],
    excluded_chunks: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """为单篇论文统计类型、token、空文本、乱码和 metadata 完整性。"""

    type_counts = Counter(chunk["chunk_type"] for chunk in chunks)
    token_counts = [chunk["token_count"] for chunk in chunks]
    over_limit = [
        chunk["global_chunk_index"]
        for chunk in chunks
        if chunk["token_count"] > SAFE_TOKEN_LIMIT
    ]
    empty_chunks = [
        chunk["global_chunk_index"]
        for chunk in chunks
        if not chunk["text"]
    ]
    mojibake_chunks = [
        {
            "global_chunk_index": chunk["global_chunk_index"],
            "issue_types": detect_mojibake(chunk["text"]),
        }
        for chunk in chunks
        if detect_mojibake(chunk["text"])
    ]
    metadata_issues = [
        {
            "global_chunk_index": chunk["global_chunk_index"],
            "missing_fields": missing,
        }
        for chunk in chunks
        if (missing := paper_metadata_issues(chunk))
    ]
    excluded_type_counts = Counter(
        chunk["chunk_type"]
        for chunk in excluded_chunks
    )

    return {
        "total_chunks": len(chunks),
        "text_chunks": type_counts.get("text", 0),
        "figure_chunks": type_counts.get("figure", 0),
        "table_chunks": type_counts.get("table", 0),
        "other_chunk_types": {
            chunk_type: count
            for chunk_type, count in sorted(type_counts.items())
            if chunk_type not in {"text", "figure", "table"}
        },
        "average_token_count": round(
            sum(token_counts) / len(token_counts),
            2,
        ) if token_counts else 0.0,
        "max_token_count": max(token_counts, default=0),
        "token_limit": SAFE_TOKEN_LIMIT,
        "splitter_default_chunk_size": DEFAULT_CHUNK_SIZE,
        "has_chunks_over_token_limit": bool(over_limit),
        "chunks_over_token_limit": len(over_limit),
        "over_token_limit_indexes": over_limit,
        "has_empty_chunks": bool(empty_chunks),
        "empty_chunk_count": len(empty_chunks),
        "empty_chunk_indexes": empty_chunks,
        "has_obvious_mojibake": bool(mojibake_chunks),
        "obvious_mojibake_chunk_count": len(mojibake_chunks),
        "mojibake_issues": mojibake_chunks,
        "has_metadata_issues": bool(metadata_issues),
        "metadata_issue_count": len(metadata_issues),
        "metadata_issues": metadata_issues,
        "excluded_corrupt_chunks": len(excluded_chunks),
        "excluded_corrupt_chunks_by_type": dict(sorted(excluded_type_counts.items())),
    }


def select_previews(chunks: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按要求选择单篇论文的 text/figure/table 人工检查样本。"""

    return {
        "text": [chunk for chunk in chunks if chunk["chunk_type"] == "text"][:5],
        "figure": [chunk for chunk in chunks if chunk["chunk_type"] == "figure"][:2],
        "table": [chunk for chunk in chunks if chunk["chunk_type"] == "table"][:2],
    }


def print_paper_result(paper_result: Dict[str, Any]) -> None:
    """分别输出每篇论文的统计和三类 chunk 预览。"""

    print("\n" + "=" * 100)
    print(f"论文: {paper_result['source']}")
    print("统计:")
    print(json.dumps(paper_result["statistics"], ensure_ascii=False, indent=2))

    previews = paper_result["previews"]
    print("\n前 5 个 text chunks:")
    print(json.dumps(previews["text"], ensure_ascii=False, indent=2))
    print("\n前 2 个 figure chunks:")
    print(json.dumps(previews["figure"], ensure_ascii=False, indent=2))
    print("\n前 2 个 table chunks:")
    print(json.dumps(previews["table"], ensure_ascii=False, indent=2))


def build_overall_statistics(papers: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总三篇论文的 chunk 数量与整体质量状态。"""

    statistics = [paper["statistics"] for paper in papers]
    return {
        "papers_processed": len(papers),
        "total_chunks": sum(item["total_chunks"] for item in statistics),
        "text_chunks": sum(item["text_chunks"] for item in statistics),
        "figure_chunks": sum(item["figure_chunks"] for item in statistics),
        "table_chunks": sum(item["table_chunks"] for item in statistics),
        "excluded_corrupt_chunks": sum(
            item["excluded_corrupt_chunks"] for item in statistics
        ),
        "has_chunks_over_token_limit": any(
            item["has_chunks_over_token_limit"] for item in statistics
        ),
        "has_empty_chunks": any(item["has_empty_chunks"] for item in statistics),
        "has_obvious_mojibake": any(
            item["has_obvious_mojibake"] for item in statistics
        ),
        "has_metadata_issues": any(
            item["has_metadata_issues"] for item in statistics
        ),
    }


def main() -> int:
    """重新解析三篇论文、切分、检查并写入统一 JSON。"""

    args = parse_args()
    validate_paper_paths(PAPER_PATHS)
    parser = PaperParser(
        enable_ocr=not args.disable_ocr,
        enable_vision=False,
    )

    all_chunks: List[Dict[str, Any]] = []
    paper_results = []

    for paper_path in PAPER_PATHS:
        print(f"\n重新解析论文: {paper_path}")
        document = parser.parse(
            pdf_path=paper_path,
            output_root=args.parser_output,
        )
        raw_chunks = split_text(document)
        paper_chunks = []
        excluded_chunks = []

        for raw_chunk in raw_chunks:
            record = normalize_chunk(
                chunk=raw_chunk,
                source=document.source or paper_path.name,
                global_chunk_index=len(all_chunks),
            )
            promote_type_specific_ids(record)

            corruption = severe_pdf_text_corruption(record["text"])
            if corruption is not None:
                excluded_chunks.append({
                    "source": record["source"],
                    "chunk_index": record["chunk_index"],
                    "chunk_type": record["chunk_type"],
                    "page_start": record["page_start"],
                    "page_end": record["page_end"],
                    "figure_id": record.get("figure_id"),
                    "table_id": record.get("table_id"),
                    **corruption,
                })
                continue

            # 被剔除记录不占用统一 JSON 的全局索引。
            record["global_chunk_index"] = len(all_chunks)
            paper_chunks.append(record)
            all_chunks.append(record)

        paper_result = {
            "source": document.source or paper_path.name,
            "title": document.title,
            "total_pages": document.total_pages,
            "statistics": build_paper_statistics(
                paper_chunks,
                excluded_chunks,
            ),
            "excluded_corrupt_chunks": excluded_chunks,
            "previews": select_previews(paper_chunks),
        }
        paper_results.append(paper_result)
        print_paper_result(paper_result)

    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper_paths": [str(path) for path in PAPER_PATHS],
        "parser_output_directory": str(args.parser_output),
        "parser": {
            "class": "PaperParser",
            "structured_document_first": True,
            "ocr_enabled": not args.disable_ocr,
            "vision_enabled": False,
        },
        "overall_statistics": build_overall_statistics(paper_results),
        "papers": paper_results,
        "chunks": all_chunks,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\n三篇论文总计:")
    print(json.dumps(payload["overall_statistics"], ensure_ascii=False, indent=2))
    print(f"\n已保存: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    # Windows 中文终端显式使用 UTF-8，避免预览发生二次乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
