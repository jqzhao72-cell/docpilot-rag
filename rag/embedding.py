"""本地 SentenceTransformer Embedding 模型的统一加载入口。"""

import os
from pathlib import Path
from typing import Dict, List

from sentence_transformers import SentenceTransformer


# 默认模型保持不变，现有 ``EmbeddingModel()`` 调用无需调整。
DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# 当前仅开放两个经过项目确认的本地模型，并记录其标准向量维度。
SUPPORTED_MODELS: Dict[str, Dict[str, object]] = {
    DEFAULT_MODEL_NAME: {
        "dimension": 384,
        "path_env": "MINILM_MODEL_PATH",
    },
    "BAAI/bge-m3": {
        "dimension": 1024,
        "path_env": "BGE_M3_MODEL_PATH",
    },
}


class EmbeddingModel:
    """加载并调用项目支持的本地 SentenceTransformer 模型。"""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        normalize_embeddings: bool = True,
    ):
        """初始化 Embedding 模型。

        参数：
            model_name:
                仅支持 MiniLM 和 BGE-M3 的标准 Hugging Face 模型名称。
            normalize_embeddings:
                是否让 ``encode`` 返回 L2 归一化后的向量，默认开启。
        """

        if model_name not in SUPPORTED_MODELS:
            supported = ", ".join(SUPPORTED_MODELS)
            raise ValueError(
                f"不支持的 Embedding 模型: {model_name}。"
                f"当前支持: {supported}"
            )

        # 记录实验配置，便于日志、评估结果和后续向量库隔离使用。
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings
        self.model_path = self._resolve_local_model_path(model_name)

        # 只传入已解析的本地路径，避免运行期间隐式访问模型仓库。
        self.model = SentenceTransformer(str(self.model_path))

        # 优先读取模型实际报告的维度；极端情况下使用已登记的标准维度兜底。
        detected_dimension = self.model.get_sentence_embedding_dimension()
        configured_dimension = SUPPORTED_MODELS[model_name]["dimension"]
        self.embedding_dimension = int(
            detected_dimension
            if detected_dimension is not None
            else configured_dimension
        )

    @staticmethod
    def _valid_model_directory(path: Path) -> bool:
        """判断路径是否包含 SentenceTransformer/Transformers 模型配置。"""

        return path.is_dir() and (
            (path / "modules.json").is_file()
            or (path / "config.json").is_file()
        )

    @classmethod
    def _resolve_local_model_path(cls, model_name: str) -> Path:
        """按环境变量、项目目录、Hugging Face 缓存的顺序查找模型。"""

        model_config = SUPPORTED_MODELS[model_name]
        repository_name = model_name.split("/", 1)[-1]
        cache_name = f"models--{model_name.replace('/', '--')}"
        project_root = Path(__file__).resolve().parents[1]

        candidates: List[Path] = []

        # 显式环境变量拥有最高优先级，适合在不同机器上切换模型目录。
        environment_path = os.getenv(str(model_config["path_env"]))
        if environment_path:
            candidates.append(Path(environment_path).expanduser())

        # 其次检查项目内常见的本地模型目录布局。
        candidates.extend([
            project_root / "models" / repository_name,
            project_root / "models" / model_name.replace("/", "--"),
            project_root / "models" / "models" / model_name.replace("/", "--"),
        ])

        # 最后检查 Hugging Face 已下载的 snapshot，全程不触发网络请求。
        snapshot_root = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "hub"
            / cache_name
            / "snapshots"
        )
        if snapshot_root.is_dir():
            candidates.extend(
                sorted(
                    (path for path in snapshot_root.iterdir() if path.is_dir()),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
            )

        # 某些离线下载工具会保留 ``snapshots/<revision>`` 缓存层级，一并展开。
        expanded_candidates: List[Path] = []
        for candidate in candidates:
            expanded_candidates.append(candidate)
            local_snapshot_root = candidate / "snapshots"
            if local_snapshot_root.is_dir():
                expanded_candidates.extend(
                    sorted(
                        (
                            path
                            for path in local_snapshot_root.iterdir()
                            if path.is_dir()
                        ),
                        key=lambda path: path.stat().st_mtime,
                        reverse=True,
                    )
                )

        for candidate in expanded_candidates:
            candidate = candidate.resolve()
            if cls._valid_model_directory(candidate):
                return candidate

        path_env = model_config["path_env"]
        raise FileNotFoundError(
            f"未找到本地模型 {model_name}。"
            f"请将模型放到 models/{repository_name}，"
            f"或通过环境变量 {path_env} 指定本地目录。"
        )

    def encode(self, texts):
        """生成 Embedding，接口保持不变，并按初始化配置决定是否归一化。"""

        return self.model.encode(
            texts,
            normalize_embeddings=self.normalize_embeddings,
        )
