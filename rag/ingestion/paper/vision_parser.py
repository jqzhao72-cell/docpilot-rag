import base64
import os
from pathlib import Path

import requests


class VisionAnalyzer:
    """
    论文Figure / Chart视觉理解模块。
    """

    def __init__(self):
        """
        从环境变量读取Vision模型配置。
        """

        self.api_base = os.getenv(
            "VISION_API_BASE",
            ""
        ).rstrip("/")

        self.api_key = os.getenv(
            "VISION_API_KEY",
            ""
        )

        self.model = os.getenv(
            "VISION_MODEL",
            ""
        )


    def enabled(self) -> bool:
        """
        判断Vision配置是否完整。
        """

        return bool(
            self.api_base
            and self.api_key
            and self.model
        )


    def image_to_base64(
        self,
        image_path
    ) -> str:
        """
        把图片转换成Base64字符串。
        """

        image_path = Path(
            image_path
        )

        if not image_path.exists():

            raise FileNotFoundError(
                f"Vision图片不存在: {image_path}"
            )


        with open(
            image_path,
            "rb"
        ) as file:

            image_bytes = file.read()


        image_base64 = (
            base64.b64encode(
                image_bytes
            )
            .decode("utf-8")
        )


        return image_base64


    def build_prompt(
        self,
        caption: str = "",
        ocr_text: str = ""
    ) -> str:
        """
        构造Vision提示词。
        """

        prompt = """
你正在分析一篇科研论文中的Figure或Chart。

请严格根据图片内容分析，不要编造图片中不存在的信息。

请完成以下任务：

1. 判断图片类型
   例如：
   - 柱状图
   - 折线图
   - 散点图
   - 热图
   - UMAP
   - t-SNE
   - 生存曲线
   - 流程图
   - 显微镜图
   - 示意图
   - 多面板Figure
   - 其他

2. 提取图片中的关键信息
   包括：
   - 横轴
   - 纵轴
   - 图例
   - 分组
   - 变量
   - 基因名称
   - 时间点
   - 重要数值

3. 如果图片包含多个子图，
   请尽量分别说明A、B、C等子图。

4. 总结图片体现的主要趋势或关系。

5. 给出适合RAG检索使用的简洁语义描述。

请使用中文输出。
"""


        if caption:

            prompt += (
                "\n\n论文原始Figure Caption：\n"
                + caption
            )


        if ocr_text:

            prompt += (
                "\n\nOCR识别出的图中文字：\n"
                + ocr_text
            )


        return prompt


    def analyze(
        self,
        image_path,
        caption: str = "",
        ocr_text: str = ""
    ) -> str:
        """
        调用Vision模型分析Figure。
        """

        if not self.enabled():

            print(
                "[Vision] 未配置Vision模型，跳过分析"
            )

            return ""


        image_base64 = (
            self.image_to_base64(
                image_path
            )
        )


        prompt = self.build_prompt(
            caption=caption,
            ocr_text=ocr_text
        )


        payload = {

            "model": self.model,

            "messages": [
                {
                    "role": "user",

                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },

                        {
                            "type": "image_url",

                            "image_url": {
                                "url":
                                "data:image/png;base64,"
                                + image_base64
                            }
                        }
                    ]
                }
            ],

            "temperature": 0
        }


        headers = {

            "Authorization":
            f"Bearer {self.api_key}",

            "Content-Type":
            "application/json"
        }


        try:

            response = requests.post(
                f"{self.api_base}/chat/completions",

                headers=headers,

                json=payload,

                timeout=120
            )


            response.raise_for_status()


            result = response.json()


            content = (
                result["choices"][0]
                ["message"]
                ["content"]
            )


            return content


        except Exception as e:

            print(
                f"[Vision] 图像分析失败: {e}"
            )

            return ""