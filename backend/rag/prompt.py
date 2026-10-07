"""Prompt construction for grounded DocPilot answers."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _page_label(doc: Mapping[str, Any]) -> str:
    page_start = doc.get("page_start")
    page_end = doc.get("page_end")
    if page_start is None and page_end is None:
        return "unknown"
    if page_end is None or page_start == page_end:
        return str(page_start)
    if page_start is None:
        return str(page_end)
    return f"{page_start}-{page_end}"


def build_prompt(
    question: str,
    retrieved_docs: Sequence[Mapping[str, Any]],
    history_text: str = "",
) -> str:
    """Build a grounded prompt whose context numbering matches source citations."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    context_blocks: list[str] = []
    for index, doc in enumerate(retrieved_docs, start=1):
        text = doc.get("text", doc.get("content", ""))
        context_blocks.append(
            "\n".join(
                (
                    f"[{index}]",
                    f"source: {doc.get('source') or 'unknown'}",
                    f"page: {_page_label(doc)}",
                    f"section: {doc.get('section') or 'unknown'}",
                    f"chunk_type: {doc.get('chunk_type') or 'unknown'}",
                    "text:",
                    str(text or ""),
                )
            )
        )

    context_text = "\n\n---\n\n".join(context_blocks) or "No context was retrieved."
    history_section = history_text.strip() if history_text else "None"

    return f"""You are DocPilot, a document-grounded question-answering assistant.

Instructions:
1. Answer the user's question using only the numbered contexts below.
2. Cite supporting contexts inline using exactly [1], [2], and so on. Never write [Context 1]. A citation number must match the corresponding context number.
3. Do not invent facts, citations, page numbers, sections, or sources.
4. If the contexts do not contain enough evidence, explicitly say that the answer cannot be determined from the provided context and state what evidence is missing.
5. Keep the answer focused and use the same language as the user's question.
6. Conversation history may clarify the question, but it is not evidence and must not be cited.

Conversation history:
{history_section}

Retrieved contexts:
{context_text}

User question:
{question.strip()}

Answer:"""
