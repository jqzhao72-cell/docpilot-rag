import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

from alibabacloud_docmind_api20220711.client import (
    Client as DocMindClient
)
from alibabacloud_docmind_api20220711 import (
    models as docmind_models
)
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models


# 自动读取项目根目录中的 .env
load_dotenv()


class AliyunDocMindClient:
    """
    阿里云 Document Mind 客户端。

    当前职责：
    1. 提交本地 PDF
    2. 查询任务状态
    3. 等待任务完成
    4. 分批获取解析结果

    暂时不负责：
    - 转 StructuredDocument
    - Chunk
    - Embedding
    """

    def __init__(
        self,
        endpoint: str = "docmind-api.cn-hangzhou.aliyuncs.com"
    ):
        self.endpoint = endpoint

        access_key_id = os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_ID"
        )

        access_key_secret = os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET"
        )

        if not access_key_id:
            raise ValueError(
                "没有找到环境变量 "
                "ALIBABA_CLOUD_ACCESS_KEY_ID"
            )

        if not access_key_secret:
            raise ValueError(
                "没有找到环境变量 "
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET"
            )

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )

        config.endpoint = self.endpoint

        # PDF可能处理时间比较长
        config.connect_timeout = 60000
        config.read_timeout = 60000

        self.client = DocMindClient(config)

    def submit_pdf(
        self,
        file_path: str,
        enable_vlm: bool = True
    ) -> str:
        """
        上传本地 PDF，并提交 Document Mind 解析任务。

        Args:
            file_path:
                PDF文件路径

            enable_vlm:
                是否启用 VLM 增强。
                True = 使用视觉大模型增强
                False = 不使用VLM增强

        Returns:
            task_id
        """

        pdf_path = Path(file_path)

        if not pdf_path.exists():
            raise FileNotFoundError(
                f"PDF文件不存在: {pdf_path}"
            )

        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(
                f"当前测试只允许PDF文件: {pdf_path}"
            )

        print("=" * 60)
        print("开始提交阿里云 Document Mind 解析任务")
        print(f"文件: {pdf_path}")
        print(f"VLM增强: {enable_vlm}")
        print("=" * 60)

        file_object = open(pdf_path, "rb")

        try:
            request_args = {
                "file_url_object": file_object,
                "file_name": pdf_path.name,
                "file_name_extension": "pdf",
            }

            if enable_vlm:
                request_args["llm_enhancement"] = True
                request_args["enhancement_mode"] = "VLM"

            request = (
                docmind_models
                .SubmitDocParserJobAdvanceRequest(
                    **request_args
                )
            )

            runtime = util_models.RuntimeOptions(
                connect_timeout=60000,
                read_timeout=60000,
            )

            response = (
                self.client
                .submit_doc_parser_job_advance(
                    request,
                    runtime
                )
            )

            if (
                response.body is None
                or response.body.data is None
                or response.body.data.id is None
            ):
                raise RuntimeError(
                    "阿里云没有返回 task_id"
                )

            task_id = response.body.data.id

            print()
            print("任务提交成功")
            print(f"task_id: {task_id}")

            return task_id

        finally:
            file_object.close()

    def query_status(
        self,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        查询解析任务状态。
        """

        request = (
            docmind_models
            .QueryDocParserStatusRequest(
                id=task_id
            )
        )

        response = (
            self.client
            .query_doc_parser_status(
                request
            )
        )

        if (
            response.body is None
            or response.body.data is None
        ):
            return None

        return response.body.data.to_map()

    def wait_until_complete(
        self,
        task_id: str,
        poll_interval: int = 5,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """
        不断查询任务状态，直到成功或者失败。

        Args:
            task_id:
                阿里云任务ID

            poll_interval:
                每隔多少秒查询一次

            timeout:
                最长等待时间，默认10分钟
        """

        print()
        print("开始等待阿里云解析...")
        print()

        start_time = time.time()

        while True:

            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"任务等待超过 {timeout} 秒"
                )

            status_data = self.query_status(
                task_id
            )

            if not status_data:
                print(
                    "暂时没有获取到状态，"
                    "稍后继续查询..."
                )

                time.sleep(
                    poll_interval
                )

                continue

            status = str(
                status_data.get(
                    "Status",
                    ""
                )
            ).lower()

            progress = status_data.get(
                "Progress",
                status_data.get(
                    "Processing",
                    ""
                )
            )

            page_count = status_data.get(
                "PageCountEstimate",
                ""
            )

            print(
                f"状态: {status}",
                f"进度: {progress}",
                f"预计页数: {page_count}",
            )

            if status == "success":

                print()
                print("阿里云解析完成")

                return status_data

            if status == "failed":

                raise RuntimeError(
                    f"阿里云解析失败: "
                    f"{status_data}"
                )

            time.sleep(
                poll_interval
            )

    def get_result_batch(
        self,
        task_id: str,
        layout_num: int = 0,
        layout_step_size: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """
        获取一批解析结果。

        阿里云不是一次返回所有Layout，
        而是通过 layout_num +
        layout_step_size 分批获取。
        """

        request = (
            docmind_models
            .GetDocParserResultRequest(
                id=task_id,
                layout_num=layout_num,
                layout_step_size=layout_step_size,
            )
        )

        response = (
            self.client
            .get_doc_parser_result(
                request
            )
        )

        if (
            response.body is None
            or response.body.data is None
        ):
            return None

        data = response.body.data

        if hasattr(data, "to_map"):
            return data.to_map()

        return data

    def get_all_layouts(
        self,
        task_id: str,
        layout_step_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取整篇PDF的所有Layout。
        """

        all_layouts = []

        layout_num = 0

        print()
        print("开始下载完整解析结果...")

        while True:

            batch = self.get_result_batch(
                task_id=task_id,
                layout_num=layout_num,
                layout_step_size=layout_step_size,
            )

            if not batch:
                break

            layouts = (
                batch.get("Layouts")
                or batch.get("layouts")
                or []
            )

            if not layouts:
                break

            all_layouts.extend(
                layouts
            )

            print(
                f"已经获取 "
                f"{len(all_layouts)} "
                f"个 Layout Block"
            )

            layout_num += len(
                layouts
            )

            if len(layouts) < layout_step_size:
                break

        print()
        print(
            f"完整结果获取完成，"
            f"共 {len(all_layouts)} 个 Layout"
        )

        return all_layouts