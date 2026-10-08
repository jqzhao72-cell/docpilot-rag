# DocPilot Evaluation

本模块位于 `backend/evaluation/`，遵循后端现有目录布局；不另建仓库根目录 evaluation。评估入口只调用 `rag/`，生产代码不得反向依赖本目录。

## 目录职责

| 目录 | 职责 |
| --- | --- |
| datasets/ | 版本化评估数据；候选集审核通过后才能成为正式冻结测试集 |
| retrieval/ | Dense、BM25、Hybrid 的检索检查及后续 Recall@K、Precision@K、RR、MRR |
| rag/ | 完整答案、faithfulness、citation 的端到端评估 |
| benchmarks/ | Reranker 排序、batch size、candidate_top_k 和耗时基准 |
| reports/ | 自动生成的运行结果，默认不提交 Git |

单元测试继续位于 `backend/tests/`；下载模型、解析/建库、数据库初始化继续位于 `backend/scripts/`。现有 7 个模型依赖型手工检查入口已迁入对应子目录，去掉容易被误认为单元测试的 test_ 前缀。迁移只调整模块位置和导入根路径，不改变 RAG 算法。

## 论文评估集

文件：[`datasets/paper_retrieval_eval.json`](datasets/paper_retrieval_eval.json)。

当前版本为 **0.1.0-candidate，未冻结、全部待审核**。包含 30 条中文问题，每篇论文 10 条；问题指定论文语境，评估的是跨语言论文检索，不代表所有真实用户流量。暂未覆盖无答案问题、引用检索意图、跨论文推理及所有图表，后续另行扩展。

| source | 语料 chunks | Query |
| --- | ---: | ---: |
| s41523-020-00197-2.pdf | 476 | 10 |
| e4343521e6a9c4fddb0438c05deea52f8c3f.pdf | 229 | 10 |
| journal.pone.0297260 (1).pdf | 235 | 10 |
| 合计 | 940 | 30 |

分类：概念事实 4、比较归纳 2、机制解释 5、方法设计 11、结果解读 7、局限性 1。

顶层包含 schema_version、version、status、corpus、annotation_policy 和 queries。每条 queries 包含：

| 字段 | 含义 |
| --- | --- |
| id | 稳定问题 ID，例如 paper-q001 |
| query | 检索问题；不把 source 标签自动传入检索过滤器 |
| source | 原始 PDF 文件名，与 chunks 元数据精确匹配 |
| question_type | 问题主类别 |
| relevant_chunk_ids | 至少支持一个答案要点的真实 Chroma ID，多片段可能需组合 |
| relevant_pages | 已列片段覆盖的 PDF 页码并集，1 起始；不是期刊印刷页码 |
| expected_answer_points | 答案要点列表，仅依据论文，不代表现行医疗建议 |
| review_status | pending / approved / rejected |
| review_notes | 人工审核重点 |

ID 映射为 `paper-{global_chunk_index}`。本轮已只读核对本地 Chroma 集合 `paper_docs_bge_m3` 的 940 个 ID 和全部文本。语料快照 SHA256 固定在 corpus 中。检索结果的 `id` 才是评分键；不能用每篇重复起算的 chunk_index 或页码替代。

**未标注片段是未判断，不是已确认负例。** 当前标签是候选正例，尚不能据此发布正式 Recall/MRR。人工需审查相关性、答案覆盖、重复/重叠片段及遗漏正例；逐条记录 reviewer、reviewed_at，全部 approved 后发布新版本并将 status 改为 frozen。冻结后修改标签应升级版本。调参集与最终测试集应分开，避免用同一 30 题调参与报告最终效果。

逐条审核清单见 [datasets/REVIEW.md](datasets/REVIEW.md)。特别注意跨片段断句、实验时间差异、基因拼写和候选化合物的安全性。本数据仅供论文理解评估，不提供诊疗建议。

### 数据可复现性

940 个片段仍保留在 `backend/data/evaluation/clean_paper_chunks.json`；不移动核心默认读取的语料，也不复制原始论文进 Git。语料、PDF、Chroma 受现有 gitignore 排除，因此 **仅克隆 GitHub 仓库不足以运行评估**。需通过授权渠道取得相同快照并校验哈希；重新解析所得文件不保证相同 ID 或哈希，必须另建版本，禁止直接覆盖已有标注。模型权重、依赖版本、硬件和参数也必须在正式报告中记录。

## 本轮可运行：只校验数据

从仓库根目录进入 backend，使用现有虚拟环境：

```powershell
cd backend
..\.venv\Scripts\python.exe -m evaluation.datasets.validate_paper_dataset
# 可选：核对数据库全部 ID、文本、来源、页码；只读，不实例化检索器
..\.venv\Scripts\python.exe -m evaluation.datasets.validate_paper_dataset --chroma-db chroma_db/chroma.sqlite3
```

校验仅检查结构、唯一性、语料哈希、来源、页码及真实 ID，**不能证明语义标注正确**；不会下载模型、检索、调用 LLM 或计算正式指标。SQLite 核对适配当前本地 Chroma schema，升级数据库后若失败应检查适配，不要忽略错误。

## Retrieval Evaluation

现有手工入口（后续自行执行，本轮未运行）：

```powershell
..\.venv\Scripts\python.exe -m evaluation.retrieval.paper_dense --top-k 5
..\.venv\Scripts\python.exe -m evaluation.retrieval.paper_hybrid
```

它们使用内置的旧 5 条冒烟 Query，**尚未接入新 30 题**，输出排名而非正式指标。正式 runner 本轮未实现，不提供虚假的运行命令。下一阶段接入冻结数据，分别比较 Dense、BM25、Hybrid、Reranker，按以下统一定义报告：

- Recall@K = Top-K 与相关集合交集数量 / 相关集合数量。
- Precision@K = 交集数量 / K（不足 K 仍以 K 为分母，并记录返回数量）。
- RR@K = 首个相关片段名次的倒数；Top-K 无相关片段则为 0。
- MRR@K = 所有 Query 的 RR@K 平均值。
- 先按 ID 去重再评分，报告 K、相关集合版本、按 Query 结果及宏平均。单个命中指标称 Hit@K，不冒充 Recall@K。
- 固定 940-chunk 语料基线；用户权限过滤需另建可访问语料协议并单独报告，不能与全库结果混算。

`retrieval/legacy/` 保留旧企业制度脚本，其 source/keyword 判定、content/chunk_id 字段及默认检索集合不适配新论文协议，且顶层有模型初始化和执行代码。**仅归档参考，不导入、不直接执行，不将其结果作为新基准。** 历史数据在 `datasets/legacy/`，未删除。

## Reranker Benchmark

```powershell
..\.venv\Scripts\python.exe -m evaluation.benchmarks.paper_reranker
..\.venv\Scripts\python.exe -m evaluation.benchmarks.second_stage_reranker
..\.venv\Scripts\python.exe -m evaluation.benchmarks.intent_reference_penalty
..\.venv\Scripts\python.exe -m evaluation.benchmarks.diagnose_paper_reranker
```

以上为现有手工比较：重排、二阶段融合、reference penalty、batch size/输入诊断；可能加载本地模型和访问索引。当前主要固定 20 个候选，**没有 candidate_top_k 网格扫描入口**。后续在本目录新增基准 runner，固定 Query、候选语料、模型版本、batch size 和随机种子，比较例如 candidate_top_k=10/20/40/80；分别记录模型冷启动、预热后 retrieval/rerank/总耗时、p50/p95、重复次数、CPU/GPU 与内存/显存，以及同配置质量结果。不能把一次运行耗时当稳定性能结论。

## End-to-End RAG Evaluation

```powershell
..\.venv\Scripts\python.exe -m evaluation.rag.paper_pipeline
```

该旧手工入口输出 5 条内置 Query 的最终答案、sources 和阶段耗时，**会调用真实 LLM，可能产生费用**，本轮未运行。后续 runner 再接入冻结数据并评估：

- Answer quality：expected_answer_points 覆盖、正确性、必要限定条件。
- Faithfulness：每个主张能否由实际检索上下文支持；不等同答案要点命中。
- Citation：引用 ID 有效性、source/page 对应、引用是否支撑主张及引用覆盖。
- 记录原始答案、检索/重排 ID、提示词版本、生成模型及参数、裁判模型/人工评分协议。抽样人工复核裁判评分，增加无答案和权限隔离用例。

## Reports 与迁移说明

自动输出放 reports，建议每次运行独立目录，包含 run.json、per_query.jsonl、summary.json，记录 git commit + dirty 状态、数据/语料哈希、依赖和模型版本、全部检索参数、时间与硬件。当前手工脚本只输出 stdout；结构化自动报告能力属于下一阶段，需实现后才宣称支持。本轮仅校验数据，不生成 Recall/MRR 或性能报告。

旧入口迁移：

| 原 backend/ 路径 | 新 backend/ 路径 |
| --- | --- |
| evaluation/rag_eval.json | evaluation/datasets/legacy/rag_eval.json |
| evaluation/test_questions.json | evaluation/datasets/legacy/test_questions.json |
| evaluation/evaluate_retrieval.py | evaluation/retrieval/legacy/evaluate_retrieval.py |
| evaluation/analyze_chunk_failures.py | evaluation/retrieval/legacy/analyze_chunk_failures.py |
| scripts/test_paper_retrieval.py | evaluation/retrieval/paper_dense.py |
| scripts/test_hybrid_retrieval.py | evaluation/retrieval/paper_hybrid.py |
| scripts/test_paper_reranker.py | evaluation/benchmarks/paper_reranker.py |
| scripts/test_second_stage_reranker.py | evaluation/benchmarks/second_stage_reranker.py |
| scripts/test_intent_reference_penalty.py | evaluation/benchmarks/intent_reference_penalty.py |
| scripts/diagnose_paper_reranker.py | evaluation/benchmarks/diagnose_paper_reranker.py |
| scripts/test_paper_rag_pipeline.py | evaluation/rag/paper_pipeline.py |

旧入口不再保留；请将本地快捷命令更新为上述模块命令。所有模型依赖入口从 backend 运行，不直接运行子目录脚本，避免 evaluation/rag 与核心 rag 包重名引发导入歧义。
