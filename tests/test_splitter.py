import unittest

from rag.ingestion.splitter import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    CHUNK_TOKEN_RESERVE,
    MODEL_MAX_SEQ_LENGTH,
    _count_tokens,
    _get_tokenizer,
    detect_heading,
    detect_heading_level,
    split_by_section,
    split_text,
)
from rag.ingestion.paper.schemas import (
    FigureData,
    PageData,
    StructuredDocument,
    TableData,
    TextBlock,
)


class HeadingDetectionTests(unittest.TestCase):
    def test_detects_common_heading_styles_and_levels(self):
        cases = {
            "Introduction": 1,
            "1. Introduction": 1,
            "1.1 Data preprocessing": 2,
            "2.3.1 Statistical analysis": 3,
            "第二章 研究方法": 1,
            "第一节 数据采集": 2,
            "一、研究背景": 1,
            "1、研究背景": 1,
            "（一）研究对象": 2,
            "II. Related Work": 1,
            "A. Dataset": 2,
            "# Results": 1,
            "## Ablation Study": 2,
        }
        for heading, expected_level in cases.items():
            with self.subTest(heading=heading):
                self.assertTrue(detect_heading(heading))
                self.assertEqual(detect_heading_level(heading), expected_level)

    def test_does_not_treat_normal_sentence_as_heading(self):
        self.assertFalse(detect_heading("The dataset contains 1,000 patient records."))
        self.assertFalse(detect_heading("1 This is a numbered list item."))
        self.assertFalse(detect_heading("2026"))


class HierarchicalSplittingTests(unittest.TestCase):
    TEXT = """Abstract

Abstract paragraph.

1 Introduction

Section opening paragraph.

1.1 Background

Background paragraph one.

Background paragraph two.

1.2 Contributions

Contribution paragraph.

2 Methods

2.1 Data preprocessing

Method paragraph.
"""

    def test_builds_section_subsection_paragraph_hierarchy(self):
        sections = split_by_section(self.TEXT)

        self.assertEqual(
            [section["title"] for section in sections],
            ["Abstract", "1 Introduction", "2 Methods"],
        )
        introduction = sections[1]
        self.assertEqual(introduction["paragraphs"], ["Section opening paragraph."])
        self.assertEqual(
            [subsection["title"] for subsection in introduction["subsections"]],
            ["1.1 Background", "1.2 Contributions"],
        )
        self.assertEqual(
            introduction["subsections"][0]["paragraphs"],
            ["Background paragraph one.", "Background paragraph two."],
        )

    def test_chunks_do_not_cross_subsection_boundaries(self):
        chunks = split_text(self.TEXT)
        pairs = {
            (chunk["metadata"]["section"], chunk["metadata"]["subsection"])
            for chunk in chunks
        }

        self.assertIn(("1 Introduction", "1.1 Background"), pairs)
        self.assertIn(("1 Introduction", "1.2 Contributions"), pairs)
        self.assertIn(("2 Methods", "2.1 Data preprocessing"), pairs)
        self.assertEqual(
            [chunk["metadata"]["chunk_index"] for chunk in chunks],
            list(range(len(chunks))),
        )

        background_chunks = [
            chunk
            for chunk in chunks
            if chunk["metadata"]["subsection"] == "1.1 Background"
        ]
        self.assertEqual(len(background_chunks), 1)
        self.assertEqual(background_chunks[0]["metadata"]["paragraph_start"], 0)
        self.assertEqual(background_chunks[0]["metadata"]["paragraph_end"], 1)
        self.assertNotIn("Contribution paragraph.", background_chunks[0]["text"])

    def test_default_chunk_limit_reserves_model_capacity(self):
        self.assertEqual(MODEL_MAX_SEQ_LENGTH, 128)
        self.assertEqual(CHUNK_TOKEN_RESERVE, 8)
        self.assertEqual(DEFAULT_CHUNK_SIZE, 120)
        self.assertEqual(DEFAULT_CHUNK_OVERLAP, 20)

    def test_embedding_chunks_do_not_exceed_safe_token_limit(self):
        text = (
            "1 Introduction\n\n"
            "1.1 Long context\n\n"
            + "multilingual token-aware content " * 200
        )

        chunks = split_text(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(
            _count_tokens(chunk["text"]) <= DEFAULT_CHUNK_SIZE
            for chunk in chunks
        ))

        tokenizer = _get_tokenizer()
        if tokenizer is not None:
            self.assertTrue(all(
                len(tokenizer.encode(chunk["text"], add_special_tokens=True).ids)
                <= MODEL_MAX_SEQ_LENGTH
                for chunk in chunks
            ))

    def test_rejects_invalid_chunk_parameters(self):
        with self.assertRaises(ValueError):
            split_text("Introduction\n\nText", chunk_size=100, chunk_overlap=100)

    def test_long_paragraph_is_split_inside_its_subsection(self):
        text = (
            "1 Introduction\n\n"
            "1.1 Long context\n\n"
            + "word " * 80
            + "\n\n1.2 Next context\n\n"
            + "next " * 20
        )
        chunks = split_text(text, chunk_size=30, chunk_overlap=5)

        self.assertTrue(all(_count_tokens(chunk["text"]) <= 30 for chunk in chunks))
        self.assertGreater(
            sum(chunk["metadata"]["subsection"] == "1.1 Long context" for chunk in chunks),
            1,
        )
        self.assertTrue(all(
            "next" not in chunk["text"]
            for chunk in chunks
            if chunk["metadata"]["subsection"] == "1.1 Long context"
        ))

    def test_paragraph_packing_uses_token_count(self):
        paragraph_one = "alpha " * 6
        paragraph_two = "beta " * 6
        paragraph_three = "gamma " * 6
        packed_pair = f"{paragraph_one.strip()}\n\n{paragraph_two.strip()}"
        chunk_size = _count_tokens(packed_pair)
        text = (
            "1 Introduction\n\n"
            "1.1 Token packing\n\n"
            f"{paragraph_one}\n\n"
            f"{paragraph_two}\n\n"
            f"{paragraph_three}"
        )

        chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=0)

        self.assertEqual(chunks[0]["text"], packed_pair)
        self.assertEqual(chunks[0]["metadata"]["paragraph_start"], 0)
        self.assertEqual(chunks[0]["metadata"]["paragraph_end"], 1)
        self.assertEqual(chunks[1]["text"], paragraph_three.strip())
        self.assertTrue(all(_count_tokens(chunk["text"]) <= chunk_size for chunk in chunks))
        self.assertGreater(len(chunks[0]["text"]), chunk_size)

    def test_overlap_reuses_last_complete_paragraph(self):
        paragraph_one = ("alpha " * 50).strip()
        context_paragraph = ("context " * 15).strip()
        paragraph_three = ("gamma " * 90).strip()
        text = (
            "1 Introduction\n\n"
            "1.1 Paragraph overlap\n\n"
            f"{paragraph_one}\n\n"
            f"{context_paragraph}\n\n"
            f"{paragraph_three}"
        )

        chunks = split_text(text)

        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0]["text"].endswith(context_paragraph))
        self.assertTrue(chunks[1]["text"].startswith(f"{context_paragraph}\n\n"))
        self.assertEqual(chunks[1]["metadata"]["paragraph_start"], 1)
        self.assertEqual(chunks[1]["metadata"]["paragraph_end"], 2)
        self.assertTrue(all(
            _count_tokens(chunk["text"]) <= DEFAULT_CHUNK_SIZE
            for chunk in chunks
        ))

    def test_large_paragraph_uses_small_token_overlap(self):
        paragraph_one = ("alpha " * 20).strip()
        large_context = ("context " * 50).strip()
        paragraph_three = ("gamma " * 70).strip()
        text = (
            "1 Introduction\n\n"
            "1.1 Fallback overlap\n\n"
            f"{paragraph_one}\n\n"
            f"{large_context}\n\n"
            f"{paragraph_three}"
        )

        chunks = split_text(text)
        overlap_prefix = chunks[1]["text"].split("\n\n", 1)[0]

        self.assertEqual(len(chunks), 2)
        self.assertNotEqual(overlap_prefix, large_context)
        self.assertLessEqual(_count_tokens(overlap_prefix), DEFAULT_CHUNK_OVERLAP)
        self.assertGreater(_count_tokens(overlap_prefix), 0)
        self.assertTrue(all(
            _count_tokens(chunk["text"]) <= DEFAULT_CHUNK_SIZE
            for chunk in chunks
        ))

    def test_structured_document_single_page_metadata(self):
        document = StructuredDocument(
            source="single-page.pdf",
            total_pages=1,
            pages=[PageData(
                page=7,
                width=600,
                height=800,
                raw_text="",
                blocks=[
                    TextBlock(0, 7, "1 Introduction", 0, 0, 100, 20, "heading"),
                    TextBlock(1, 7, "Single page paragraph.", 0, 30, 500, 80),
                ],
            )],
        )

        chunks = split_text(document)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["metadata"]["page_start"], 7)
        self.assertEqual(chunks[0]["metadata"]["page_end"], 7)

    def test_structured_document_cross_page_metadata(self):
        document = StructuredDocument(
            source="cross-page.pdf",
            total_pages=2,
            pages=[
                PageData(
                    page=1,
                    width=600,
                    height=800,
                    raw_text="",
                    blocks=[
                        TextBlock(0, 1, "1 Introduction", 0, 0, 100, 20, "heading"),
                        TextBlock(1, 1, "First-page paragraph.", 0, 30, 500, 80),
                    ],
                ),
                PageData(
                    page=2,
                    width=600,
                    height=800,
                    raw_text="",
                    blocks=[
                        TextBlock(0, 2, "Second-page paragraph.", 0, 0, 500, 50),
                    ],
                ),
            ],
        )

        chunks = split_text(document)

        self.assertEqual(len(chunks), 1)
        self.assertIn("First-page paragraph.", chunks[0]["text"])
        self.assertIn("Second-page paragraph.", chunks[0]["text"])
        self.assertEqual(chunks[0]["metadata"]["page_start"], 1)
        self.assertEqual(chunks[0]["metadata"]["page_end"], 2)

    def test_caption_only_figure_chunk(self):
        document = StructuredDocument(
            source="caption-figure.pdf",
            total_pages=1,
            pages=[PageData(
                page=4,
                width=600,
                height=800,
                raw_text="",
                figures=[FigureData(
                    figure_id=12,
                    page=4,
                    image_path="figure_12.png",
                    caption="Figure 12. Model architecture.",
                )],
            )],
        )

        chunks = split_text(document)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], "Figure 12. Model architecture.")
        self.assertEqual(chunks[0]["metadata"]["chunk_type"], "figure")
        self.assertEqual(chunks[0]["metadata"]["figure_id"], 12)
        self.assertEqual(chunks[0]["metadata"]["page_start"], 4)
        self.assertEqual(chunks[0]["metadata"]["page_end"], 4)

    def test_figure_combines_caption_ocr_and_vision_without_empty_lines(self):
        document = StructuredDocument(
            source="multimodal-figure.pdf",
            total_pages=1,
            pages=[PageData(
                page=2,
                width=600,
                height=800,
                raw_text="",
                figures=[FigureData(
                    figure_id=3,
                    page=2,
                    image_path="figure_3.png",
                    caption="Figure 3. Survival curve.",
                    ocr_text="Overall survival",
                    vision_description="The treatment curve remains above control.",
                )],
            )],
        )

        chunks = split_text(document)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(
            chunks[0]["text"],
            "Figure 3. Survival curve.\n\n"
            "Overall survival\n\n"
            "The treatment curve remains above control.",
        )

    def test_long_figure_description_uses_safe_recursive_splitting(self):
        document = StructuredDocument(
            source="long-figure.pdf",
            total_pages=1,
            pages=[PageData(
                page=9,
                width=600,
                height=800,
                raw_text="",
                figures=[FigureData(
                    figure_id=8,
                    page=9,
                    image_path="figure_8.png",
                    caption="Figure 8.",
                    vision_description=("multimodal observation " * 200).strip(),
                )],
            )],
        )

        chunks = split_text(document)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(
            chunk["metadata"]["chunk_type"] == "figure"
            and chunk["metadata"]["figure_id"] == 8
            and chunk["metadata"]["page_start"] == 9
            and chunk["metadata"]["page_end"] == 9
            and _count_tokens(chunk["text"]) <= DEFAULT_CHUNK_SIZE
            for chunk in chunks
        ))

    def test_small_table_is_one_chunk_with_caption_header_and_rows(self):
        document = StructuredDocument(
            source="small-table.pdf",
            total_pages=1,
            pages=[PageData(
                page=5,
                width=600,
                height=800,
                raw_text="",
                tables=[TableData(
                    table_id=6,
                    page=5,
                    bbox=[0, 0, 500, 300],
                    caption="Table 6. Cohort summary.",
                    rows=[
                        ["Group", "Patients"],
                        ["Treatment", "42"],
                        ["Control", "38"],
                    ],
                )],
            )],
        )

        chunks = split_text(document)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(
            chunks[0]["text"],
            "Table 6. Cohort summary.\n"
            "Group | Patients\n"
            "Treatment | 42\n"
            "Control | 38",
        )
        self.assertEqual(chunks[0]["metadata"]["chunk_type"], "table")
        self.assertEqual(chunks[0]["metadata"]["table_id"], 6)
        self.assertEqual(chunks[0]["metadata"]["page_start"], 5)
        self.assertEqual(chunks[0]["metadata"]["page_end"], 5)
        self.assertIn("section", chunks[0]["metadata"])
        self.assertIn("subsection", chunks[0]["metadata"])

    def test_large_table_splits_by_rows_and_repeats_caption_and_header(self):
        caption = "Table 9. Gene expression results."
        header = "Gene | Expression"
        data_rows = [
            [f"Gene-{index}", ("value " * 20).strip()]
            for index in range(12)
        ]
        document = StructuredDocument(
            source="large-table.pdf",
            total_pages=1,
            pages=[PageData(
                page=8,
                width=600,
                height=800,
                raw_text="",
                tables=[TableData(
                    table_id=9,
                    page=8,
                    bbox=[0, 0, 500, 700],
                    caption=caption,
                    rows=[["Gene", "Expression"], *data_rows],
                )],
            )],
        )

        chunks = split_text(document)
        expected_rows = [" | ".join(row) for row in data_rows]
        actual_rows = []

        for chunk in chunks:
            lines = chunk["text"].splitlines()
            self.assertGreaterEqual(len(lines), 3)
            self.assertEqual(lines[0], caption)
            self.assertEqual(lines[1], header)
            actual_rows.extend(lines[2:])
            self.assertEqual(chunk["metadata"]["chunk_type"], "table")
            self.assertEqual(chunk["metadata"]["table_id"], 9)
            self.assertEqual(chunk["metadata"]["page_start"], 8)
            self.assertEqual(chunk["metadata"]["page_end"], 8)
            self.assertLessEqual(_count_tokens(chunk["text"]), DEFAULT_CHUNK_SIZE)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(actual_rows, expected_rows)


if __name__ == "__main__":
    unittest.main()
