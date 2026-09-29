import json
from dataclasses import asdict
from pathlib import Path

import fitz

from .text_parser import extract_raw_text
from .layout_parser import extract_text_blocks
from .table_parser import extract_tables
from .ocr_parser import OCRAnalyzer
from .figure_parser import (
    render_page,
    extract_figures
)
from .vision_parser import VisionAnalyzer
from .document_builder import (
    build_page,
    build_document
)


class PaperParser:
    """
    论文PDF总解析器。

    负责把：
    Text
    Layout
    Table
    OCR
    Figure
    Vision

    串成完整处理流程。
    """

    def __init__(
        self,
        enable_ocr: bool = True,
        enable_vision: bool = False
    ):
        """
        初始化解析器。

        参数：
            enable_ocr:
                是否开启OCR

            enable_vision:
                是否开启Vision图表理解
        """

        self.enable_ocr = enable_ocr

        self.enable_vision = enable_vision


        # 初始化OCR
        self.ocr = None

        if self.enable_ocr:
            self.ocr = OCRAnalyzer()


        # 初始化Vision
        self.vision = None

        if self.enable_vision:
            self.vision = VisionAnalyzer()


    def find_title(
        self,
        pages
    ) -> str:
        """
        从第一页的TextBlock中寻找论文标题。

        优先：
            block_type == title

        找不到时：
            使用第一页较长的文本块兜底。
        """

        if not pages:
            return ""


        first_page = pages[0]


        title_candidates = []

        for block in first_page.blocks:

            if block.block_type == "title":

                title_candidates.append(
                    block
                )


        if title_candidates:

            # 按字号从大到小排序
            title_candidates.sort(
                key=lambda block:
                block.font_size,

                reverse=True
            )


            return (
                title_candidates[0]
                .text
            )


        # ==========================================
        # fallback
        # ==========================================

        for block in first_page.blocks:

            if len(block.text) > 20:

                return block.text


        return ""


    def parse(
        self,
        pdf_path,
        output_root="data/parsed_documents"
    ):
        """
        解析一整篇论文PDF。

        参数：
            pdf_path:
                PDF路径

            output_root:
                输出根目录

        返回：
            StructuredDocument
        """

        # ==========================================
        # 1. 检查PDF
        # ==========================================

        pdf_path = Path(
            pdf_path
        )


        if not pdf_path.exists():

            raise FileNotFoundError(
                f"PDF文件不存在: {pdf_path}"
            )


        # ==========================================
        # 2. 创建输出目录
        # ==========================================

        output_root = Path(
            output_root
        )


        document_dir = (
            output_root
            / pdf_path.stem
        )


        document_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        page_image_dir = (
            document_dir
            / "pages"
        )


        page_image_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        figure_dir = (
            document_dir
            / "figures"
        )


        figure_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        # ==========================================
        # 3. 打开PDF
        # ==========================================

        print(
            "\n"
            + "=" * 80
        )

        print(
            f"开始解析: {pdf_path.name}"
        )

        print(
            "=" * 80
        )


        doc = fitz.open(
            pdf_path
        )


        structured_pages = []


        # ==========================================
        # 4. 逐页处理
        # ==========================================

        for page_index in range(
            len(doc)
        ):

            page_number = (
                page_index + 1
            )


            print(
                f"正在处理第 "
                f"{page_number}/"
                f"{len(doc)} 页"
            )


            page = doc[
                page_index
            ]


            # ======================================
            # Step 1：普通文本
            # ======================================

            raw_text = (
                extract_raw_text(
                    page
                )
            )


            # ======================================
            # Step 2：Layout
            # ======================================

            blocks = (
                extract_text_blocks(
                    page=page,
                    page_number=page_number
                )
            )


            # ======================================
            # Step 3：Table
            # ======================================

            tables = (
                extract_tables(
                    page=page,

                    page_number=page_number,

                    blocks=blocks
                )
            )


            # ======================================
            # Step 4：整页渲染
            # ======================================

            page_image_path = (
                page_image_dir
                / f"page_{page_number}.png"
            )


            render_page(
                page=page,

                output_path=page_image_path,

                zoom=2.0
            )


            # ======================================
            # Step 5：整页OCR兜底
            # ======================================

            ocr_text = ""


            if (
                self.enable_ocr
                and self.ocr is not None
            ):

                # 如果原生文字很少，
                # 可能是扫描PDF
                if len(raw_text) < 100:

                    print(
                        "  -> 原生文字较少，启动整页OCR"
                    )


                    ocr_text = (
                        self.ocr.analyze(
                            page_image_path
                        )
                    )


            # ======================================
            # Step 6：Figure提取
            # ======================================

            figures = (
                extract_figures(
                    page=page,

                    page_number=page_number,

                    blocks=blocks,

                    output_dir=figure_dir
                )
            )


            # ======================================
            # Step 7：Figure OCR
            # ======================================

            if (
                self.enable_ocr
                and self.ocr is not None
            ):

                for figure in figures:

                    figure.ocr_text = (
                        self.ocr.analyze(
                            figure.image_path
                        )
                    )


            # ======================================
            # Step 8：Vision
            # ======================================

            if (
                self.enable_vision
                and self.vision is not None
                and self.vision.enabled()
            ):

                for figure in figures:

                    print(
                        f"  -> Vision分析 "
                        f"Figure {figure.figure_id}"
                    )


                    figure.vision_description = (
                        self.vision.analyze(
                            image_path=figure.image_path,

                            caption=figure.caption,

                            ocr_text=figure.ocr_text
                        )
                    )


            # ======================================
            # Step 9：组装PageData
            # ======================================

            page_data = (
                build_page(
                    page_number=page_number,

                    width=float(
                        page.rect.width
                    ),

                    height=float(
                        page.rect.height
                    ),

                    raw_text=raw_text,

                    blocks=blocks,

                    tables=tables,

                    figures=figures,

                    ocr_text=ocr_text
                )
            )


            structured_pages.append(
                page_data
            )


        # ==========================================
        # 5. 关闭PDF
        # ==========================================

        doc.close()


        # ==========================================
        # 6. 找论文标题
        # ==========================================

        title = self.find_title(
            structured_pages
        )


        # ==========================================
        # 7. 组装StructuredDocument
        # ==========================================

        document = (
            build_document(
                source=pdf_path.name,

                title=title,

                pages=structured_pages
            )
        )


        # ==========================================
        # 8. 保存JSON
        # ==========================================

        output_json = (
            document_dir
            / "document.json"
        )


        with open(
            output_json,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                asdict(
                    document
                ),

                file,

                ensure_ascii=False,

                indent=2
            )


        # ==========================================
        # 9. 输出结果
        # ==========================================

        print(
            "\n解析完成"
        )

        print(
            f"文件: {pdf_path.name}"
        )

        print(
            f"标题: {document.title}"
        )

        print(
            f"总页数: {document.total_pages}"
        )

        print(
            f"JSON: {output_json}"
        )


        return document