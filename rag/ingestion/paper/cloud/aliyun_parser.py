import json
from pathlib import Path
from typing import Dict, Any

from .aliyun_client import AliyunDocMindClient


class AliyunPaperParser:
    """
    一条完整的阿里云论文解析流水线。

    PDF
    ↓
    Submit
    ↓
    Wait
    ↓
    Get Result
    ↓
    JSON
    """

    def __init__(
        self,
        enable_vlm: bool = True
    ):
        self.enable_vlm = enable_vlm

        self.client = (
            AliyunDocMindClient()
        )

    def parse(
        self,
        pdf_path: str
    ) -> Dict[str, Any]:

        pdf_path = Path(
            pdf_path
        )

        print()
        print("#" * 70)
        print("Aliyun Cloud Paper Parser")
        print("#" * 70)

        # ============================
        # 1. 提交PDF
        # ============================

        task_id = (
            self.client.submit_pdf(
                str(pdf_path),
                enable_vlm=self.enable_vlm,
            )
        )

        # ============================
        # 2. 等待阿里云解析完成
        # ============================

        status = (
            self.client.wait_until_complete(
                task_id
            )
        )

        # ============================
        # 3. 下载所有Layout
        # ============================

        layouts = (
            self.client.get_all_layouts(
                task_id
            )
        )

        # ============================
        # 4. 保存原始信息
        # ============================

        result = {
            "source": str(pdf_path),
            "parser": "aliyun_docmind",
            "task_id": task_id,
            "status": status,
            "layout_count": len(
                layouts
            ),
            "layouts": layouts,
        }

        return result

    def save_json(
        self,
        result: Dict[str, Any],
        output_path: str
    ):

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                result,
                f,
                ensure_ascii=False,
                indent=2
            )

        print()
        print(
            f"阿里云解析结果已经保存："
        )

        print(
            output_path
        )