# 项目整理记录

## 分类原则

应用代码放在 app/ 和 rag/；管理工具放在 scripts/；打印结果、依赖本地模型或调用外部 API 的手动示例放在 examples/；带断言的自动化测试放在 tests/。论文解析虽未接入主流程，仍是独立学习成果，予以保留。

## 删除文件

| 原文件 | 原因 |
| --- | --- |
| evaluation/evaluate.py | 空文件；实际评估在 evaluate_retrieval.py |
| rag/vector_story.py | 无引用的旧实现，使用不同集合且没有来源元数据；主流程使用 vector_store.py |
| test_pdf_loader.py | 引用不存在的 rag.ingestion.pdf_loader，依赖已失效的逐页返回格式和三个固定文件；当前 PDF 加载在 rag/ingestion/loader.py |
| delete_chroma_file.py | 一次性删除固定文件的脚本；文档删除已有后端接口和前端入口 |

删除脚本时没有执行其中的数据库操作。

## 移动文件

| 原位置 | 新位置 |
| --- | --- |
| 根目录 check_*.py（五个） | scripts/diagnostics/，保留各自诊断用途 |
| ingest.py、init_db.py、set_admin.py、download_reranker.py、download_reranker_modelscope.py | scripts/ |
| chroma_demo.py | examples/embedding_search.py |
| rag/chroma_rag.py | examples/chroma_search.py |
| tests/test_loader.py | examples/document_loading.py |
| tests/test_splitter.py | examples/text_splitting.py |
| tests/test_model.py | examples/model_loading.py |
| tests/test_prompt.py | examples/prompt_building.py |
| tests/test_rag.py | examples/rag_pipeline.py |
| tests/test_reranker.py | examples/reranking.py |
| tests/test_retrieval.py | examples/retrieval.py |

共移动 19 个文件。Chroma 示例改用 learning_demo 集合；Prompt 示例改为当前接口要求的字典数据。其余迁移脚本保留原逻辑。

原有 app.* 和 rag.* 导入路径保持有效。迁移后的脚本通过根目录 python -m 命令运行，数据路径不变。新增包标记明确目录职责。

## 保留内容

保留 .env、虚拟环境、数据库、原始文档、评估数据和模型，没有重置用户原有 Git 修改。新增忽略规则只防止运行产物进入版本控制，不删除实体文件。原有重排序实现问题和依赖限制记在 README 中。

权限测试在导入 app.documents 时模拟 Chroma 客户端，避免自动化测试连接真实知识库。
