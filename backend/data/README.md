# Data Directory

本目录保存 DocPilot 的本地输入、处理中间产物和评估数据。除本说明外，数据默认不提交 Git。

## 当前目录

```text
data/
├── documents/          # 企业知识库原始文档
├── papers/             # 论文 PDF 原件
├── evaluation/         # clean chunks、评估问题和评估输入
├── parsed_documents/   # 本地论文解析后的结构化结果
├── aliyun_results/     # 阿里云 Document Mind 解析结果
└── pdf_text_output/    # PDF 文本提取输出
```

向量索引和业务数据库目前独立放在：

```text
backend/chroma_db/      # Chroma collections
backend/app.db          # 用户、会话和历史记录
backend/models/         # 本地 Embedding/Reranker 模型
```

## 数据生命周期

| 类型 | 目录 | 处理原则 |
| --- | --- | --- |
| 原始企业文档 | `documents/` | 不应由清理脚本自动删除 |
| 原始论文 | `papers/` | 保留原件，解析失败时用于重试 |
| 正式评估输入 | `evaluation/` | 与临时输出区分，不参与普通上传 |
| 解析中间产物 | `parsed_documents/`、`aliyun_results/` | 可以复用，删除后可能需要重新解析或调用云服务 |
| 文本导出 | `pdf_text_output/` | 调试产物，不作为正式索引的唯一来源 |
| Chroma | `../chroma_db/` | 删除后必须重新构建向量索引 |
| SQLite | `../app.db` | 删除会丢失用户、会话和历史记录 |
| 模型 | `../models/` | 本地大文件，不提交 Git |

参考项目使用 `raw/processed/vector_db/outputs` 的统一生命周期目录。DocPilot 暂时保留现有数据路径，因为这些路径已被解析、测试、Chroma 和回归脚本使用；后续若迁移，应单独完成路径配置集中化、数据移动和索引完整性校验，不能只改目录名。
