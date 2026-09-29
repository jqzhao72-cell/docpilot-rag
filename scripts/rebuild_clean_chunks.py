"""从原始 PDF 重建可复用的干净 chunk 数据并执行质量检查。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

# 支持从项目根目录直接执行 ``python scripts/rebuild_clean_chunks.py``。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.ingestion.paper.paper_parser import PaperParser
from rag.ingestion.splitter import DEFAULT_CHUNK_SIZE, _count_tokens, split_text


# 正式评测要求所有送入 embedding 的文本最多为 120 tokens。
SAFE_TOKEN_LIMIT = 120

# 这些模式只标记高置信度乱码；普通中英文、公式和特殊符号不会被判为乱码。
MOJIBAKE_PATTERNS = {
    "replacement_character": re.compile("\ufffd"),
    "utf8_decoded_as_latin1": re.compile(r"(?:Ã.|Â.|â€|ðŸ)"),
    "common_gbk_artifact": re.compile(r"(?:锟斤拷|烫烫烫|屯屯屯)"),
    "unexpected_control_character": re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"),
}

REQUIRED_FIELDS = (
    "text",
    "chunk_index",
    "chunk_type",
    "section",
    "subsection",
    "page_start",
    "page_end",
    "source",
)


def parse_args() -> argparse.Namespace:
    """读取命令行参数，并提供适合当前项目目录结构的默认值。"""

    parser = argparse.ArgumentParser(
        description="使用最新 PaperParser 和 splitter 重建、检查统一 chunks JSON。",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/documents"),
        help="原始 PDF 所在目录，默认 data/documents。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/evaluation/clean_chunks.json"),
        help="统一 chunks JSON 输出路径。",
    )
    parser.add_argument(
        "--parser-output",
        type=Path,
        default=Path("data/evaluation/parsed_documents"),
        help="PaperParser 中间产物输出目录。",
    )
    parser.add_argument(
        "--disable-ocr",
        action="store_true",
        help="关闭 Parser 默认 OCR；正常重建默认保持 OCR 开启。",
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=10,
        help="终端输出的 chunk 预览数量，默认 10。",
    )
    return parser.parse_args()


def find_source_pdfs(input_dir: Path) -> List[Path]:
    """按文件名稳定排序读取原始 PDF，不读取任何既有解析或 Chroma 数据。"""

    if not input_dir.is_dir():
        raise FileNotFoundError(f"原始文档目录不存在: {input_dir}")

    pdf_paths = sorted(
        (path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    if not pdf_paths:
        raise FileNotFoundError(f"原始文档目录中没有 PDF: {input_dir}")
    return pdf_paths


def detect_mojibake(text: str) -> List[str]:
    """返回文本命中的高置信度乱码类型。"""

    return [
        issue_name
        for issue_name, pattern in MOJIBAKE_PATTERNS.items()
        if pattern.search(text)
    ]


def missing_required_fields(record: Dict[str, Any]) -> List[str]:
    """检查字段是否缺失；section/subsection 允许因无法可靠关联而为空。"""

    missing = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in record or record[field_name] is None:
            missing.append(field_name)

    # 正文可以为空标题上下文，但正文、来源和页码必须有有效值。
    if not str(record.get("source", "")).strip() and "source" not in missing:
        missing.append("source")
    if record.get("page_start") == 0 and "page_start" not in missing:
        missing.append("page_start")
    if record.get("page_end") == 0 and "page_end" not in missing:
        missing.append("page_end")
    return missing


def normalize_chunk(
    chunk: Dict[str, Any],
    source: str,
    global_chunk_index: int,
) -> Dict[str, Any]:
    """把 splitter 返回结构整理为统一、扁平且保留原 metadata 的记录。"""

    metadata = dict(chunk.get("metadata") or {})
    text = str(chunk.get("text") or "").strip()
    chunk_type = str(metadata.get("chunk_type") or "text")

    record = {
        "text": text,
        "chunk_index": metadata.get("chunk_index"),
        "global_chunk_index": global_chunk_index,
        "chunk_type": chunk_type,
        "section": str(metadata.get("section") or ""),
        "subsection": str(metadata.get("subsection") or ""),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "source": source,
        "token_count": _count_tokens(text),
        "metadata": metadata,
    }
    return record


def build_quality_report(
    chunks: Sequence[Dict[str, Any]],
    document_names: Sequence[str],
) -> Dict[str, Any]:
    """汇总 chunk 类型、长度、乱码、空文本和 metadata 完整性。"""

    type_counts = Counter(chunk["chunk_type"] for chunk in chunks)
    empty_chunks = []
    replacement_chunks = []
    mojibake_chunks = []
    over_limit_chunks = []
    metadata_issues = []
    missing_by_field: Dict[str, int] = defaultdict(int)

    for chunk in chunks:
        issue_identity = {
            "global_chunk_index": chunk["global_chunk_index"],
            "chunk_index": chunk["chunk_index"],
            "source": chunk["source"],
        }

        if not chunk["text"]:
            empty_chunks.append(issue_identity)

        mojibake_types = detect_mojibake(chunk["text"])
        if "replacement_character" in mojibake_types:
            replacement_chunks.append(issue_identity)
        if mojibake_types:
            mojibake_chunks.append({
                **issue_identity,
                "issue_types": mojibake_types,
            })

        if chunk["token_count"] > SAFE_TOKEN_LIMIT:
            over_limit_chunks.append({
                **issue_identity,
                "token_count": chunk["token_count"],
            })

        missing_fields = missing_required_fields(chunk)
        if missing_fields:
            metadata_issues.append({
                **issue_identity,
                "missing_fields": missing_fields,
            })
            for field_name in missing_fields:
                missing_by_field[field_name] += 1

    token_counts = [chunk["token_count"] for chunk in chunks]
    return {
        "documents_processed": len(document_names),
        "document_names": list(document_names),
        "total_chunks": len(chunks),
        "text_chunks": type_counts.get("text", 0),
        "figure_chunks": type_counts.get("figure", 0),
        "table_chunks": type_counts.get("table", 0),
        "other_chunk_types": {
            chunk_type: count
            for chunk_type, count in sorted(type_counts.items())
            if chunk_type not in {"text", "figure", "table"}
        },
        "empty_chunk_count": len(empty_chunks),
        "contains_replacement_character": bool(replacement_chunks),
        "replacement_character_chunk_count": len(replacement_chunks),
        "contains_obvious_mojibake": bool(mojibake_chunks),
        "obvious_mojibake_chunk_count": len(mojibake_chunks),
        "safe_token_limit": SAFE_TOKEN_LIMIT,
        "splitter_default_chunk_size": DEFAULT_CHUNK_SIZE,
        "max_token_count": max(token_counts, default=0),
        "chunks_over_token_limit": len(over_limit_chunks),
        "metadata_issue_count": len(metadata_issues),
        "missing_metadata_by_field": dict(sorted(missing_by_field.items())),
        "issues": {
            "empty_chunks": empty_chunks,
            "replacement_character_chunks": replacement_chunks,
            "obvious_mojibake_chunks": mojibake_chunks,
            "over_token_limit_chunks": over_limit_chunks,
            "metadata_issues": metadata_issues,
        },
    }


def print_preview(chunks: Iterable[Dict[str, Any]], preview_count: int) -> None:
    """输出前 N 个 chunk 的关键字段，方便人工检查。"""

    preview = list(chunks)[: max(preview_count, 0)]
    print(f"\n前 {len(preview)} 个 chunks：")
    print(json.dumps(preview, ensure_ascii=False, indent=2))


def main() -> int:
    """从原始 PDF 完成 Parser、splitter、质量报告和 JSON 落盘。"""

    args = parse_args()
    source_paths = find_source_pdfs(args.input_dir)
    parser = PaperParser(
        enable_ocr=not args.disable_ocr,
        enable_vision=False,
    )

    all_chunks: List[Dict[str, Any]] = []
    document_summaries = []

    for source_path in source_paths:
        print(f"\n重建原始文档: {source_path.name}")
        document = parser.parse(
            pdf_path=source_path,
            output_root=args.parser_output,
        )
        raw_chunks = split_text(document)

        start_index = len(all_chunks)
        for chunk in raw_chunks:
            all_chunks.append(
                normalize_chunk(
                    chunk=chunk,
                    source=document.source or source_path.name,
                    global_chunk_index=len(all_chunks),
                )
            )

        document_summaries.append({
            "source": document.source or source_path.name,
            "title": document.title,
            "total_pages": document.total_pages,
            "chunk_count": len(all_chunks) - start_index,
        })

    quality_report = build_quality_report(
        chunks=all_chunks,
        document_names=[path.name for path in source_paths],
    )
    output_payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(args.input_dir),
        "parser_output_directory": str(args.parser_output),
        "parser": {
            "class": "PaperParser",
            "ocr_enabled": not args.disable_ocr,
            "vision_enabled": False,
        },
        "documents": document_summaries,
        "quality_report": quality_report,
        "chunks": all_chunks,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n质量检查汇总：")
    print(json.dumps(
        {key: value for key, value in quality_report.items() if key != "issues"},
        ensure_ascii=False,
        indent=2,
    ))
    print_preview(all_chunks, args.preview_count)
    print(f"\n已保存: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    # Windows 中文终端下显式使用 UTF-8，确保人工预览不产生二次乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
