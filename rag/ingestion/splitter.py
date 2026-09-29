"""RAG 文档的 Section/Subsection/Paragraph 识别与 Token-aware 切分。"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from rag.ingestion.paper.schemas import FigureData, StructuredDocument, TableData

try:
    # 正常环境优先使用项目原有的 LangChain 递归文本切分器。
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    # 精简环境没有 LangChain 时，保留相同调用接口以便基础切分仍可运行。
    @dataclass
    class _Document:
        """兼容 LangChain Document 所需的最小字段集合。"""

        page_content: str
        metadata: Dict

    class RecursiveCharacterTextSplitter:
        """项目缺少 LangChain splitter 时使用的 Token-aware 最小兼容实现。"""

        def __init__(
            self,
            chunk_size: int,
            chunk_overlap: int,
            separators: List[str],
            add_start_index: bool = False,
            length_function: Callable[[str], int] = len,
        ) -> None:
            # 保存与 LangChain RecursiveCharacterTextSplitter 对齐的核心参数。
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.separators = separators
            self.add_start_index = add_start_index
            self.length_function = length_function

        def _max_token_end(self, text: str, start: int) -> int:
            """用二分搜索找到 token 数不超过 chunk_size 的最远字符位置。"""

            low = start + 1
            high = len(text)
            best = low
            while low <= high:
                middle = (low + high) // 2
                if self.length_function(text[start:middle]) <= self.chunk_size:
                    best = middle
                    low = middle + 1
                else:
                    high = middle - 1
            return best

        def _token_overlap_start(self, text: str, start: int, end: int) -> int:
            """找到保留不超过 chunk_overlap 个 token 的后缀起点。"""

            if self.chunk_overlap == 0:
                return end

            low = start
            high = end
            best = end
            while low <= high:
                middle = (low + high) // 2
                if self.length_function(text[middle:end]) <= self.chunk_overlap:
                    best = middle
                    high = middle - 1
                else:
                    low = middle + 1
            return best

        def create_documents(self, texts: List[str]) -> List[_Document]:
            """按 token 上限生成兼容 LangChain Document 结构的文本块。"""

            documents: List[_Document] = []
            for text in texts:
                start = 0
                while start < len(text):
                    # 先按 token 上限找到硬边界，再尽量回退到自然分隔符。
                    hard_end = self._max_token_end(text, start)
                    end = hard_end
                    if hard_end < len(text):
                        for separator in self.separators:
                            if not separator:
                                continue
                            boundary = text.rfind(separator, start + 1, hard_end + 1)
                            if boundary > start:
                                end = boundary + len(separator)
                                break

                    raw_chunk = text[start:end]
                    leading_space = len(raw_chunk) - len(raw_chunk.lstrip())
                    chunk = raw_chunk.strip()
                    if chunk:
                        metadata = {}
                        if self.add_start_index:
                            metadata["start_index"] = start + leading_space
                        documents.append(_Document(chunk, metadata))

                    if end >= len(text):
                        break

                    # overlap 同样以 token 为单位；过短块不回退，避免无法前进。
                    if self.length_function(text[start:end]) <= self.chunk_overlap:
                        next_start = end
                    else:
                        next_start = self._token_overlap_start(text, start, end)
                    start = next_start
            return documents


# Tokenizer 优先复用项目 embedding 模型的本地 Hugging Face tokenizer；
# 如果本机没有该模型，则退回项目内已有的 BGE tokenizer。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_EMBEDDING_TOKENIZER_ROOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
    / "snapshots"
)
_PROJECT_TOKENIZER_PATH = _PROJECT_ROOT / "models" / "bge-reranker-base" / "tokenizer.json"


@lru_cache(maxsize=1)
def _get_tokenizer():
    """只从本地加载已有 tokenizer，不进行网络下载。"""

    try:
        from tokenizers import Tokenizer
    except ImportError:
        return None

    # 优先选择与项目 EmbeddingModel 一致的 multilingual MiniLM tokenizer。
    candidates = sorted(_EMBEDDING_TOKENIZER_ROOT.glob("*/tokenizer.json"))
    if _PROJECT_TOKENIZER_PATH.is_file():
        candidates.append(_PROJECT_TOKENIZER_PATH)

    for tokenizer_path in candidates:
        try:
            return Tokenizer.from_file(str(tokenizer_path))
        except (OSError, ValueError):
            continue
    return None


def _count_tokens(text: str) -> int:
    """计算文本 token 数；无本地 tokenizer 时使用轻量正则 tokenizer 兜底。"""

    tokenizer = _get_tokenizer()
    if tokenizer is not None:
        # 不计模型自动添加的 CLS/SEP，chunk_size 只约束正文 token。
        return len(tokenizer.encode(text, add_special_tokens=False).ids)

    # 轻量兜底：中文逐字、英文逐词、数字和标点分别计为 token。
    fallback_tokens = re.findall(
        r"[\u3400-\u9fff]|[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\s]",
        text,
    )
    return len(fallback_tokens)


# MiniLM 的 SentenceTransformer 配置优先于 tokenizer_config：前者记录了
# SentenceTransformer 实际采用的截断长度，后者的模型原始上限可能更大。
def _read_model_max_seq_length() -> int:
    """从本地模型配置读取最大序列长度，读取失败时回退到已知值 128。"""

    sentence_transformer_configs = sorted(
        _EMBEDDING_TOKENIZER_ROOT.glob("*/sentence_bert_config.json")
    )
    tokenizer_configs = sorted(
        _EMBEDDING_TOKENIZER_ROOT.glob("*/tokenizer_config.json")
    )

    # 按优先级依次读取 SentenceTransformer 和底层 tokenizer 配置。
    config_candidates = [
        (path, "max_seq_length")
        for path in sentence_transformer_configs
    ]
    config_candidates.extend(
        (path, "model_max_length")
        for path in tokenizer_configs
    )

    for config_path, field_name in config_candidates:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            value = int(config[field_name])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            continue

        # 排除 Hugging Face 用超大整数表达“未设置上限”的占位值。
        if 0 < value < 1_000_000:
            return value

    # 当前 embedding 模型 paraphrase-multilingual-MiniLM-L12-v2 的已知上限。
    return 128


# 为模型自动添加的特殊 token 预留 2 tokens，并为标题上下文预留 6 tokens。
MODEL_MAX_SEQ_LENGTH = _read_model_max_seq_length()
SPECIAL_TOKEN_RESERVE = 2
TITLE_TOKEN_RESERVE = 6
CHUNK_TOKEN_RESERVE = SPECIAL_TOKEN_RESERVE + TITLE_TOKEN_RESERVE

# 默认正文 chunk 上限为 128 - 8 = 120 tokens。
DEFAULT_CHUNK_SIZE = MODEL_MAX_SEQ_LENGTH - CHUNK_TOKEN_RESERVE

# Paragraph overlap 无法完整复用时，最多保留 20 tokens 的尾部上下文。
DEFAULT_CHUNK_OVERLAP = 20

# 完整复用的 paragraph 最多占 chunk_size 的四分之一，避免大面积重复。
PARAGRAPH_OVERLAP_MAX_RATIO = 0.25


# 无编号时可直接判定为一级 Section 的中英文论文常见标题。
_MAIN_HEADINGS = {
    "abstract", "summary", "background", "introduction", "related work",
    "literature review", "materials and methods", "material and methods",
    "methods", "methodology", "results", "discussion", "conclusion",
    "conclusions", "references", "bibliography", "acknowledgements",
    "acknowledgments", "appendix", "摘要", "引言", "绪论", "相关工作",
    "材料与方法", "研究方法", "实验方法", "结果", "讨论", "结论",
    "参考文献", "致谢", "附录",
}

# 无编号时可直接判定为二级 Subsection 的中英文论文常见标题。
_SUB_HEADINGS = {
    "objective", "objectives", "study design", "study population",
    "participants", "data acquisition", "data collection",
    "data preprocessing", "experimental setup", "statistical analysis",
    "limitations", "研究目的", "研究对象", "数据采集", "数据预处理",
    "实验设计", "统计分析", "局限性",
}

# 以下正则分别覆盖数字编号、中文章/节、中文序号、罗马数字和字母编号标题。
_NUMBERED_HEADING_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*)(?P<trailing_dot>\.)?"
    r"(?:\s+(?P<title>\S.*))?$"
)
_CHINESE_CHAPTER_RE = re.compile(
    r"^第[一二三四五六七八九十百千万零〇两\d]+(?P<unit>章|篇|部分|节)(?:\s*[:：、.]?\s*.*)?$"
)
_CHINESE_SECTION_RE = re.compile(
    r"^(?P<number>[一二三四五六七八九十百]+)[、．]\s*\S.*$"
)
_CHINESE_SUBSECTION_RE = re.compile(
    r"^[（(](?P<number>[一二三四五六七八九十百]+|\d+)[）)]\s*\S.*$"
)
_ARABIC_PUNCT_HEADING_RE = re.compile(r"^\d+[、．]\s*\S.*$")
_ROMAN_HEADING_RE = re.compile(r"^[IVXLCDM]+\.\s+\S.*$", re.IGNORECASE)
_LETTER_SUBHEADING_RE = re.compile(r"^[A-Z]\.\s+\S.*$")
_TRAILING_SENTENCE_PUNCTUATION = ("。", "！", "？", ".", "!", "?", ";", "；")


def _clean_heading(line: str) -> str:
    """去掉 Markdown 标题标记，保留编号和可读标题。"""

    return re.sub(r"^#{1,6}\s+", "", line.strip()).strip()


def detect_heading_level(line: str) -> Optional[int]:
    """返回标题层级：1 为 section，2 及以上为 subsection。"""

    # 标题匹配前统一清除行首尾空白；空行永远不是标题。
    stripped = line.strip()
    if not stripped:
        return None

    # Markdown 的井号数量天然表示标题层级。
    markdown_match = re.match(r"^(#{1,6})\s+\S", stripped)
    if markdown_match:
        return 1 if len(markdown_match.group(1)) == 1 else len(markdown_match.group(1))

    # 中文“章/篇/部分”作为 Section，“节”作为 Subsection。
    chapter_match = _CHINESE_CHAPTER_RE.match(stripped)
    if chapter_match:
        return 2 if chapter_match.group("unit") == "节" else 1

    # 阿拉伯数字中的点号数量决定标题层级。
    numbered_match = _NUMBERED_HEADING_RE.match(stripped)
    if numbered_match:
        has_nested_number = "." in numbered_match.group("number")
        has_heading_marker = numbered_match.group("trailing_dot") is not None
        has_title = numbered_match.group("title") is not None
        if not (has_nested_number or has_heading_marker or has_title):
            return None
        if has_title and numbered_match.group("title").endswith(_TRAILING_SENTENCE_PUNCTUATION):
            return None
        # 1 / 1. 为 section，1.1 / 1.1.1 为 subsection。
        return numbered_match.group("number").count(".") + 1

    # 继续识别其他常见的一级、二级编号样式。
    if _ARABIC_PUNCT_HEADING_RE.match(stripped) or _ROMAN_HEADING_RE.match(stripped):
        return 1
    if _LETTER_SUBHEADING_RE.match(stripped):
        return 2
    if _CHINESE_SECTION_RE.match(stripped):
        return 1
    if _CHINESE_SUBSECTION_RE.match(stripped):
        return 2

    # 最后处理无编号但名称固定的论文标题。
    normalized = re.sub(r"\s+", " ", stripped).lower().rstrip(":：")
    if normalized in _MAIN_HEADINGS:
        return 1
    if normalized in _SUB_HEADINGS:
        return 2
    return None


def detect_heading(line: str) -> bool:
    """兼容原接口：判断一行是不是可识别的章节标题。"""

    return detect_heading_level(line) is not None


def _looks_like_standalone_heading(line: str) -> bool:
    """保守识别没有编号、但排版独立的英文标题。"""

    # 独立标题应较短，且通常不以完整句子的结束符收尾。
    stripped = line.strip().rstrip(":：")
    if not stripped or len(stripped) > 100 or stripped.endswith(_TRAILING_SENTENCE_PUNCTUATION):
        return False

    # 限制英文单词数量，避免把较长的正文句子当成标题。
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", stripped)
    if not words or len(words) > 12:
        return False

    # 全大写或大部分单词采用 Title Case 时，视为标题候选。
    is_upper = stripped.upper() == stripped and any(char.isalpha() for char in stripped)
    title_words = sum(word[0].isupper() for word in words)
    return is_upper or title_words / len(words) >= 0.8


def _heading_level_with_context(lines: List[str], index: int) -> Optional[int]:
    """结合相邻空行识别没有显式编号的独立标题。"""

    # 显式格式能识别时直接采用，不再执行启发式判断。
    level = detect_heading_level(lines[index])
    if level is not None:
        return level

    # 普通 Title Case 只在前后存在段落边界时识别，降低正文误判率。
    previous_blank = index == 0 or not lines[index - 1].strip()
    next_blank = index == len(lines) - 1 or not lines[index + 1].strip()
    if previous_blank and next_blank and _looks_like_standalone_heading(lines[index]):
        return 1
    return None


def _lines_to_paragraphs(lines: List[str]) -> List[str]:
    """以空行为 paragraph 边界，并保留段内原有换行。"""

    # current 收集同一段落内的连续非空行。
    paragraphs: List[str] = []
    current: List[str] = []
    for line in lines:
        stripped = line.strip()
        # 空行出现时结束当前 paragraph；段内换行保持不变。
        if stripped:
            current.append(stripped)
        elif current:
            paragraphs.append("\n".join(current))
            current = []

    # 文本末尾没有空行时，补充保存最后一个 paragraph。
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def _lines_to_paragraphs_with_pages(
    lines: List[str],
    line_pages: List[int],
) -> Tuple[List[str], List[Tuple[int, int]]]:
    """在生成 paragraphs 的同时保留每个 paragraph 的真实页码范围。"""

    paragraphs: List[str] = []
    paragraph_pages: List[Tuple[int, int]] = []
    current_lines: List[str] = []
    current_pages: List[int] = []

    for line, page in zip(lines, line_pages):
        stripped = line.strip()
        if stripped:
            current_lines.append(stripped)
            current_pages.append(page)
        elif current_lines:
            paragraphs.append("\n".join(current_lines))
            paragraph_pages.append((current_pages[0], current_pages[-1]))
            current_lines = []
            current_pages = []

    if current_lines:
        paragraphs.append("\n".join(current_lines))
        paragraph_pages.append((current_pages[0], current_pages[-1]))

    return paragraphs, paragraph_pages


def _structured_document_lines(
    document: StructuredDocument,
) -> Tuple[List[str], List[int]]:
    """从 StructuredDocument 提取正文行，并同步传递 PageData/TextBlock 页码。"""

    lines: List[str] = []
    line_pages: List[int] = []

    def append_text(text: str, page: int) -> None:
        """追加一段带明确来源页码的文本，并用空行维持 block 边界。"""

        if not text or not text.strip():
            return
        if lines and lines[-1].strip():
            lines.append("")
            line_pages.append(page)
        for line in text.splitlines():
            lines.append(line)
            line_pages.append(page)

    for page_data in document.pages:
        page_has_blocks = False

        # TextBlock 已携带 parser 生成的页码，优先作为正文及标题的来源。
        for block in page_data.blocks:
            if not block.text or not block.text.strip():
                continue
            append_text(block.text, block.page)
            page_has_blocks = True

        # 没有 layout blocks 时才使用同一 PageData 的原始文本或 OCR 文本兜底。
        if not page_has_blocks:
            page_text = page_data.raw_text or page_data.ocr_text
            append_text(page_text, page_data.page)

    # 移除末尾空行，保证重新拼接后 splitlines() 与页码数组严格对齐。
    while lines and not lines[-1].strip():
        lines.pop()
        line_pages.pop()

    return lines, line_pages


def _new_section(title: str) -> Dict:
    """创建字段结构统一的空 Section。"""

    return {"title": title, "content": "", "paragraphs": [], "subsections": []}


def split_by_section(
    text: str,
    _line_pages: Optional[List[int]] = None,
) -> List[Dict]:
    """将文本解析为 ``section -> subsection -> paragraph`` 层级。

    ``title`` 和 ``content`` 字段继续保留，因此原先读取 section 的调用仍然可用；
    新增的 ``paragraphs`` 表示 section 标题后的引导段，``subsections`` 中每项也
    包含 ``title``、``content`` 和 ``paragraphs``。
    """

    if not text or not text.strip():
        return []

    lines = text.splitlines()
    track_pages = _line_pages is not None
    line_pages = _line_pages if _line_pages is not None else [0] * len(lines)
    if len(line_pages) != len(lines):
        raise ValueError("line_pages 必须与文本行数一致")

    # Section 保存直属段落和 Subsection；两类行缓冲区分别延迟到边界处结算。
    sections: List[Dict] = []
    current_section = _new_section("")
    section_lines: List[str] = []
    section_line_pages: List[int] = []
    current_subsection: Optional[Dict] = None
    subsection_lines: List[str] = []
    subsection_line_pages: List[int] = []

    def finish_subsection() -> None:
        """将当前 Subsection 行缓冲转换为 paragraphs 并写入 Section。"""

        nonlocal current_subsection, subsection_lines, subsection_line_pages
        if current_subsection is None:
            return
        if track_pages:
            paragraphs, paragraph_pages = _lines_to_paragraphs_with_pages(
                subsection_lines,
                subsection_line_pages,
            )
            current_subsection["_paragraph_pages"] = paragraph_pages
        else:
            paragraphs = _lines_to_paragraphs(subsection_lines)
        current_subsection["paragraphs"] = paragraphs
        current_subsection["content"] = "\n\n".join(paragraphs)
        current_section["subsections"].append(current_subsection)
        current_subsection = None
        subsection_lines = []
        subsection_line_pages = []

    def finish_section() -> None:
        """完成当前 Section，并汇总其直属内容和所有 Subsection 内容。"""

        nonlocal current_section, section_lines, section_line_pages
        finish_subsection()
        if track_pages:
            paragraphs, paragraph_pages = _lines_to_paragraphs_with_pages(
                section_lines,
                section_line_pages,
            )
            current_section["_paragraph_pages"] = paragraph_pages
        else:
            paragraphs = _lines_to_paragraphs(section_lines)
        current_section["paragraphs"] = paragraphs
        # content 字段继续提供扁平正文，以兼容既有调用方。
        content_parts = list(paragraphs)
        content_parts.extend(
            subsection["content"]
            for subsection in current_section["subsections"]
            if subsection["content"]
        )
        current_section["content"] = "\n\n".join(content_parts)

        # 空占位 Section 不输出；有效内容保存后重置所有 Section 状态。
        if current_section["title"] or current_section["content"] or current_section["subsections"]:
            sections.append(current_section)
        current_section = _new_section("")
        section_lines = []
        section_line_pages = []

    # 单次顺序扫描，根据标题层级切换当前 Section 或 Subsection。
    for index, line in enumerate(lines):
        page = line_pages[index]
        level = _heading_level_with_context(lines, index)
        if level == 1:
            finish_section()
            current_section = _new_section(_clean_heading(line))
        elif level is not None and level >= 2:
            finish_subsection()
            current_subsection = {
                "title": _clean_heading(line),
                "level": level,
                "content": "",
                "paragraphs": [],
            }
        elif current_subsection is not None:
            subsection_lines.append(line)
            subsection_line_pages.append(page)
        else:
            section_lines.append(line)
            section_line_pages.append(page)

    # 文档结尾没有后续标题，因此需要显式结算最后一个 Section。
    finish_section()
    return sections


def _paragraph_ranges(content: str, paragraphs: List[str]) -> List[Tuple[int, int]]:
    """计算每个 paragraph 在扁平 content 中的字符范围。"""

    ranges: List[Tuple[int, int]] = []
    cursor = 0
    for paragraph in paragraphs:
        start = content.find(paragraph, cursor)
        if start < 0:
            start = cursor
        end = start + len(paragraph)
        ranges.append((start, end))
        cursor = end
    return ranges


def _paragraph_span(start: int, end: int, ranges: List[Tuple[int, int]]) -> Tuple[int, int]:
    """根据字符范围返回一个 chunk 覆盖的首尾 paragraph 下标。"""

    touched = [
        index
        for index, (paragraph_start, paragraph_end) in enumerate(ranges)
        if paragraph_end > start and paragraph_start < end
    ]
    if not touched:
        return 0, 0
    return touched[0], touched[-1]


def _page_span(
    paragraph_pages: List[Tuple[int, int]],
    paragraph_start: int,
    paragraph_end: int,
) -> Tuple[int, int]:
    """汇总 chunk 所覆盖 paragraphs 的起止页；0 表示旧纯文本没有页信息。"""

    if not paragraph_pages:
        return 0, 0

    covered_pages = paragraph_pages[paragraph_start:paragraph_end + 1]
    return covered_pages[0][0], covered_pages[-1][1]


def _pack_paragraphs(
    paragraphs: List[str],
    chunk_size: int,
    chunk_overlap: int,
    splitter: RecursiveCharacterTextSplitter,
) -> List[Tuple[str, int, int]]:
    """按 token 数顺序装入完整 paragraph，仅递归切分单个超长 paragraph。"""

    # 每个结果保存：chunk 文本、起始 paragraph 下标、结束 paragraph 下标。
    packed_chunks: List[Tuple[str, int, int]] = []
    current_paragraphs: List[str] = []
    current_start = 0

    def flush_current(paragraph_end: int) -> None:
        """输出当前已装箱的完整 paragraphs，并清空装箱缓冲区。"""

        nonlocal current_paragraphs
        if not current_paragraphs:
            return
        packed_chunks.append((
            "\n\n".join(current_paragraphs),
            current_start,
            paragraph_end,
        ))
        current_paragraphs = []

    for paragraph_index, paragraph in enumerate(paragraphs):
        # 只有单个 paragraph 自身超限时，才使用递归 splitter 兜底。
        if _count_tokens(paragraph) > chunk_size:
            flush_current(paragraph_index - 1)
            for document in splitter.create_documents([paragraph]):
                chunk = document.page_content.strip()
                if chunk:
                    packed_chunks.append((chunk, paragraph_index, paragraph_index))
            continue

        # 对拼接后的完整候选文本重新分词，避免把字符数或可变长度 token 相加。
        candidate_paragraphs = [*current_paragraphs, paragraph]
        candidate_text = "\n\n".join(candidate_paragraphs)
        candidate_token_count = _count_tokens(candidate_text)

        # 候选超限时先保存已有 chunk，当前 paragraph 放入新的 chunk。
        if current_paragraphs and candidate_token_count > chunk_size:
            flush_current(paragraph_index - 1)

        if not current_paragraphs:
            current_start = paragraph_index
        current_paragraphs.append(paragraph)

    # 循环结束后保存最后一组尚未输出的 paragraphs。
    flush_current(len(paragraphs) - 1)

    # 基础装箱完成后再增加上下文，避免 overlap 参与后续装箱而逐块累积。
    return _apply_paragraph_overlap(
        packed_chunks,
        paragraphs,
        chunk_size,
        chunk_overlap,
    )


def _token_suffix(text: str, token_budget: int) -> str:
    """取得不超过 token_budget 的最长文本后缀，供小粒度 overlap 兜底。"""

    if token_budget <= 0 or not text:
        return ""

    # 后缀越短 token 数通常越少，二分查找满足预算的最早字符位置。
    low = 0
    high = len(text)
    best = len(text)
    while low <= high:
        middle = (low + high) // 2
        if _count_tokens(text[middle:]) <= token_budget:
            best = middle
            high = middle - 1
        else:
            low = middle + 1

    suffix = text[best:].strip()

    # 个别子词边界可能不完全单调，最终再收紧一次确保不超过预算。
    while suffix and _count_tokens(suffix) > token_budget:
        suffix = suffix[1:].lstrip()
    return suffix


def _apply_paragraph_overlap(
    packed_chunks: List[Tuple[str, int, int]],
    paragraphs: List[str],
    chunk_size: int,
    token_overlap: int,
) -> List[Tuple[str, int, int]]:
    """优先复用完整 paragraph，不合适时使用较小 token overlap。"""

    if len(packed_chunks) < 2:
        return packed_chunks

    overlapped_chunks = [packed_chunks[0]]
    paragraph_overlap_limit = max(1, int(chunk_size * PARAGRAPH_OVERLAP_MAX_RATIO))

    # 始终以未叠加 overlap 的基础块作为上下文来源，防止重复内容不断累积。
    for previous_chunk, current_chunk in zip(packed_chunks, packed_chunks[1:]):
        previous_text, _, previous_end = previous_chunk
        current_text, current_start, current_end = current_chunk

        # 同一超长 paragraph 的递归切片已由 splitter 应用 token overlap。
        if previous_end == current_start:
            overlapped_chunks.append(current_chunk)
            continue

        overlap_text = ""
        last_paragraph = paragraphs[previous_end]
        paragraph_candidate = f"{last_paragraph}\n\n{current_text}"

        # 正常情况优先完整复用上一块最后一个较短 paragraph。
        if (
            previous_text.endswith(last_paragraph)
            and _count_tokens(last_paragraph) <= paragraph_overlap_limit
            and _count_tokens(paragraph_candidate) <= chunk_size
        ):
            overlap_text = last_paragraph
        else:
            # 完整 paragraph 不合适时，仅使用较小的 token 后缀作为兜底。
            remaining_budget = chunk_size - _count_tokens(current_text)
            fallback_budget = min(token_overlap, max(0, remaining_budget))
            overlap_text = _token_suffix(previous_text, fallback_budget)

        if overlap_text:
            overlapped_text = f"{overlap_text}\n\n{current_text}"
            # 最终按完整候选重新计数，确保加入上下文后仍不超过安全上限。
            if _count_tokens(overlapped_text) <= chunk_size:
                current_chunk = (
                    overlapped_text,
                    min(previous_end, current_start),
                    current_end,
                )

        overlapped_chunks.append(current_chunk)

    return overlapped_chunks


def _build_figure_text(figure: FigureData) -> str:
    """按 caption、OCR、Vision 的优先顺序组合 Figure 文本并跳过空字段。"""

    parts = [
        value.strip()
        for value in (
            figure.caption,
            figure.ocr_text,
            figure.vision_description,
        )
        if value and value.strip()
    ]
    return "\n\n".join(parts)


def _figure_section_context(
    page: int,
    text_chunks: List[Dict],
) -> Tuple[str, str]:
    """同页正文只有唯一层级时复用其 Section/Subsection，否则返回空值。"""

    contexts = {
        (
            chunk["metadata"].get("section", ""),
            chunk["metadata"].get("subsection", ""),
        )
        for chunk in text_chunks
        if (
            chunk["metadata"].get("page_start", 0)
            <= page
            <= chunk["metadata"].get("page_end", 0)
        )
    }
    if len(contexts) == 1:
        return next(iter(contexts))
    return "", ""


def _append_figure_chunks(
    document: StructuredDocument,
    final_chunks: List[Dict],
    splitter: RecursiveCharacterTextSplitter,
) -> None:
    """将 StructuredDocument 中每张非空 Figure 转换为独立 figure chunk。"""

    # Figure 关联只参考正文 chunk，避免已添加的 Figure 反向影响后续关联。
    text_chunks = list(final_chunks)

    for page_data in document.pages:
        for figure in page_data.figures:
            figure_text = _build_figure_text(figure)
            if not figure_text:
                continue

            section, subsection = _figure_section_context(figure.page, text_chunks)

            # 使用正文相同的 tokenizer、120-token 上限和递归切分兜底。
            for figure_document in splitter.create_documents([figure_text]):
                chunk = figure_document.page_content.strip()
                if not chunk:
                    continue

                final_chunks.append({
                    "text": chunk,
                    "metadata": {
                        "section": section,
                        "subsection": subsection,
                        "chunk_type": "figure",
                        "page_start": figure.page,
                        "page_end": figure.page,
                        "figure_id": figure.figure_id,
                        "chunk_index": len(final_chunks),
                    },
                })


def _table_lines(table: TableData) -> Tuple[str, str, List[str]]:
    """将 TableData 规范化为 caption、header 和按原顺序排列的数据行。"""

    caption = table.caption.strip() if table.caption else ""
    rendered_rows: List[str] = []

    for row in table.rows:
        # 空单元格不输出；完全为空的行也不会制造无意义空行。
        cells = [
            str(cell).strip()
            for cell in row
            if cell is not None and str(cell).strip()
        ]
        if cells:
            rendered_rows.append(" | ".join(cells))

    # 当前 TableData 没有独立 header 字段，因此首个非空行作为表头。
    header = rendered_rows[0] if rendered_rows else ""
    data_rows = rendered_rows[1:]
    return caption, header, data_rows


def _compose_table_text(caption: str, header: str, rows: List[str]) -> str:
    """按 caption、header、rows 顺序组合表格文本，并跳过空字段。"""

    return "\n".join(part for part in (caption, header, *rows) if part)


def _split_oversized_table_row(
    row: str,
    prefix_token_count: int,
    chunk_size: int,
) -> List[str]:
    """极端单行超限时，在保留表格前缀预算后递归切分该行。"""

    # 额外预留 1 token 给前缀与行片段之间的换行边界。
    row_budget = chunk_size - prefix_token_count - 1
    if row_budget <= 0:
        return []

    row_splitter = RecursiveCharacterTextSplitter(
        chunk_size=row_budget,
        chunk_overlap=0,
        add_start_index=True,
        length_function=_count_tokens,
        separators=["\n", "; ", "；", ", ", "，", " ", ""],
    )
    return [
        document.page_content.strip()
        for document in row_splitter.create_documents([row])
        if document.page_content.strip()
    ]


def _build_table_chunk_texts(
    table: TableData,
    chunk_size: int,
    splitter: RecursiveCharacterTextSplitter,
) -> List[str]:
    """小表整体输出；大表重复 caption/header 并按完整数据行分组。"""

    caption, header, data_rows = _table_lines(table)
    complete_text = _compose_table_text(caption, header, data_rows)
    if not complete_text:
        return []

    # 小表保持完整，不引入不必要的拆分。
    if _count_tokens(complete_text) <= chunk_size:
        return [complete_text]

    prefix_text = _compose_table_text(caption, header, [])
    prefix_token_count = _count_tokens(prefix_text)

    # 没有数据行，或前缀自身已经占满预算时，使用现有递归切分器兜底。
    if not data_rows or prefix_token_count >= chunk_size:
        return [
            document.page_content.strip()
            for document in splitter.create_documents([complete_text])
            if document.page_content.strip()
        ]

    table_chunks: List[str] = []
    current_rows: List[str] = []

    def flush_rows() -> None:
        """输出当前按完整行装箱的 table chunk。"""

        nonlocal current_rows
        if current_rows:
            table_chunks.append(_compose_table_text(caption, header, current_rows))
            current_rows = []

    for row in data_rows:
        candidate = _compose_table_text(caption, header, [*current_rows, row])
        if _count_tokens(candidate) <= chunk_size:
            current_rows.append(row)
            continue

        flush_rows()
        single_row_text = _compose_table_text(caption, header, [row])
        if _count_tokens(single_row_text) <= chunk_size:
            current_rows.append(row)
            continue

        # 单行本身过长时，只切分该行，并在每个片段前重复 caption/header。
        for row_part in _split_oversized_table_row(
            row,
            prefix_token_count,
            chunk_size,
        ):
            table_chunks.append(_compose_table_text(caption, header, [row_part]))

    flush_rows()
    return table_chunks


def _append_table_chunks(
    document: StructuredDocument,
    final_chunks: List[Dict],
    splitter: RecursiveCharacterTextSplitter,
    chunk_size: int,
) -> None:
    """将 StructuredDocument 中每张非空 Table 转换为独立 table chunk。"""

    # Section/Subsection 关联仅参考正文，规则与 Figure 完全一致。
    text_chunks = [
        chunk
        for chunk in final_chunks
        if "chunk_type" not in chunk["metadata"]
    ]

    for page_data in document.pages:
        for table in page_data.tables:
            section, subsection = _figure_section_context(table.page, text_chunks)

            for chunk in _build_table_chunk_texts(table, chunk_size, splitter):
                final_chunks.append({
                    "text": chunk,
                    "metadata": {
                        "section": section,
                        "subsection": subsection,
                        "chunk_type": "table",
                        "table_id": table.table_id,
                        "page_start": table.page,
                        "page_end": table.page,
                        "chunk_index": len(final_chunks),
                    },
                })


def split_text(
    text: Union[str, StructuredDocument],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict]:
    """按 section/subsection 边界切分，subsection 内按 token 装箱 paragraph。

    输入可为旧版纯文本，也可为携带真实页码的 StructuredDocument。
    chunk 不会跨越 subsection；超长 paragraph 才会继续按句子和字符递归切分。
    相邻 chunk 优先复用完整 paragraph，不合适时才使用较小 token overlap。
    StructuredDocument 中的 FigureData 会在正文之后生成独立 figure chunk。
    StructuredDocument 中的 TableData 会再按整表或完整数据行生成独立 table chunk。
    ``chunk_size`` 和 ``chunk_overlap`` 均以 tokenizer 产生的 token 数为单位。
    返回结构兼容当前 V2 基线，并在 metadata 中保留段落范围和页面范围。
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须大于等于 0 且小于 chunk_size")

    # StructuredDocument 直接使用 PageData/TextBlock 页码；纯文本旧接口继续兼容。
    structured_document: Optional[StructuredDocument] = None
    if isinstance(text, StructuredDocument):
        structured_document = text
        document_lines, line_pages = _structured_document_lines(text)
        sections = split_by_section("\n".join(document_lines), line_pages)
    elif isinstance(text, str):
        sections = split_by_section(text)
    else:
        raise TypeError("text 必须是 str 或 StructuredDocument")

    # 递归 splitter 只处理超长单段；长度函数使其参数单位同步变为 token。
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        length_function=_count_tokens,
        separators=["\n\n", "\n", ". ", "。", "！", "？", "; ", "；", ", ", "，", " ", ""],
    )
    final_chunks: List[Dict] = []

    for section in sections:
        # Section 标题后的直属 paragraphs 作为空标题单元参与同一装箱流程。
        units = [{
            "title": "",
            "content": "\n\n".join(section["paragraphs"]),
            "paragraphs": section["paragraphs"],
            "_paragraph_pages": section.get(
                "_paragraph_pages",
                [(0, 0)] * len(section["paragraphs"]),
            ),
        }]
        # 每个 Subsection 都是独立装箱边界，chunk 不会跨 Subsection 合并。
        units.extend(section["subsections"])

        for unit in units:
            paragraphs = unit["paragraphs"]
            if not paragraphs:
                continue
            paragraph_pages = unit.get(
                "_paragraph_pages",
                [(0, 0)] * len(paragraphs),
            )

            # Paragraph Packing 返回精确的首尾 paragraph 下标供 metadata 使用。
            for chunk, paragraph_start, paragraph_end in _pack_paragraphs(
                paragraphs,
                chunk_size,
                chunk_overlap,
                splitter,
            ):
                page_start, page_end = _page_span(
                    paragraph_pages,
                    paragraph_start,
                    paragraph_end,
                )
                # 保持既有 text/metadata 返回结构和全局递增 chunk_index 不变。
                final_chunks.append({
                    "text": chunk,
                    "metadata": {
                        "section": section["title"],
                        "subsection": unit["title"],
                        "paragraph_start": paragraph_start,
                        "paragraph_end": paragraph_end,
                        "page_start": page_start,
                        "page_end": page_end,
                        "chunk_index": len(final_chunks),
                    },
                })

    # 仅 StructuredDocument 带有 FigureData；纯文本旧接口不会生成 Figure chunk。
    if structured_document is not None:
        _append_figure_chunks(structured_document, final_chunks, splitter)
        _append_table_chunks(
            structured_document,
            final_chunks,
            splitter,
            chunk_size,
        )

    return final_chunks
