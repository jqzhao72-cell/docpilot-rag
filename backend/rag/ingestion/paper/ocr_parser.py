from pathlib import Path
from typing import List, Dict, Any

from rapidocr_onnxruntime import RapidOCR


class OCRAnalyzer:
    """
    OCR解析器。

    主要用途：
    1. 识别扫描PDF页面中的文字
    2. 识别论文Figure中的文字
    3. 为后续Vision模型提供辅助文本
    """

    def __init__(self):
        """
        初始化OCR模型。
        """

        self.engine = RapidOCR()


    def analyze(
        self,
        image_path
    ) -> str:
        """
        对一张图片进行OCR识别。

        参数：
            image_path:
                图片文件路径

        返回：
            str:
                OCR识别后的完整文本
        """

        image_path = Path(
            image_path
        )


        if not image_path.exists():
            raise FileNotFoundError(
                f"OCR图片不存在: {image_path}"
            )


        try:

            result, elapsed = self.engine(
                str(image_path)
            )

        except Exception as e:

            print(
                f"[OCR] 识别失败: {e}"
            )

            return ""


        if not result:
            return ""


        texts = []


        for item in result:

            # RapidOCR通常返回：
            #
            # [
            #   box,
            #   text,
            #   score
            # ]

            if len(item) < 2:
                continue


            text = item[1]


            if text:

                texts.append(
                    str(text).strip()
                )


        return "\n".join(
            texts
        )


    def analyze_with_details(
        self,
        image_path
    ) -> List[Dict[str, Any]]:
        """
        OCR详细模式。

        除了文字，
        还保留：
        - bbox
        - score

        后面如果要做图表结构理解，
        这些信息会有用。
        """

        image_path = Path(
            image_path
        )


        if not image_path.exists():
            raise FileNotFoundError(
                f"OCR图片不存在: {image_path}"
            )


        try:

            result, elapsed = self.engine(
                str(image_path)
            )

        except Exception as e:

            print(
                f"[OCR] 识别失败: {e}"
            )

            return []


        if not result:
            return []


        ocr_results = []


        for item in result:

            if len(item) < 3:
                continue


            box = item[0]

            text = item[1]

            score = item[2]


            ocr_results.append(
                {
                    "text": str(
                        text
                    ).strip(),

                    "score": float(
                        score
                    ),

                    "bbox": box
                }
            )


        return ocr_results