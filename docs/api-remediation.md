# DocPilot 前后端整改记录

## 身份与权限

登录返回 opaque Bearer token（非 JWT），有效期 8 小时。服务端只存 SHA-256 token 摘要，用户密码使用带随机 salt 的 scrypt。前端把 token 保存在 sessionStorage，每次导航通过 GET /users/me 校验身份。旧 localStorage 用户信息自动清除。注销使服务端 token 立即失效；角色修改使目标用户所有 token 失效。

公开接口仅限 GET /、POST /register、POST /login 和 FastAPI 文档。Swagger 在 /login 获取 access_token 后可通过 Authorize 使用 Bearer。业务请求不再接受用于证明身份的 user_id/operator_user_id；管理员查询过滤参数及目标用户资源 ID 不是身份凭据。

employee 可读 employee 文档；hr 可读/上传/删除 employee、hr 文档；admin 可操作全部正常角色文档及用户角色。用户私有会话始终只允许本人访问；admin 的跨用户问答审计通过 /admin/history 单独提供。

## 正式接口与前端对应

| 方法 | 接口 | 前端调用 | 权限 |
|---|---|---|---|
| POST | /register | auth.register | public，新用户固定 employee |
| POST | /login | auth.login | public |
| POST | /logout | auth.logout | 登录 |
| GET | /users/me | auth.getCurrentUser | 登录 |
| GET | /users | users.listUsers | admin，offset/limit 分页 |
| PUT | /users/{id}/role | users.updateUserRole | admin，不允许自降级 |
| GET/POST | /conversations | conversations.getUserConversations/createConversation | 本人 |
| PATCH/DELETE | /conversations/{id} | conversations.renameConversation/deleteConversation | 本人 |
| GET | /conversations/{id}/messages | conversations.getConversationMessages | 本人 |
| POST | /chat | chat.askQuestion | 本人的会话 |
| GET | /history | history.getUserHistory | 本人 |
| GET | /admin/history | history.getAllHistory | admin |
| GET/POST | /documents | documents.listDocuments/uploadDocument | 文档 RBAC |
| GET | /documents/{filename}/content | documents.viewDocument | 文档 RBAC |
| GET | /documents/{filename}/download | documents.downloadDocument | 文档 RBAC，企业库原文件 |
| PUT | /documents/{filename}/role | documents.setDocumentRole | admin |
| DELETE | /documents/{filename} | documents.deleteDocument | 文档 RBAC |

旧 /upload、/history/user/{id}、/conversations/user/{id} 不再注册。GET /history 的语义已改为当前用户。角色修改请求只允许 role。会话创建允许 title、knowledge_base；Chat 只允许 question、conversation_id。其他 JSON 字段返回 422。sources 在 Chat、消息和历史响应中统一为数组；时间由 FastAPI 输出 ISO 8601，不再手工 str(datetime)。请求/响应模型见 app/schemas.py。

## 知识库和数据流

- company：使用现有 company_docs + MiniLM；在线上传、列表、删除、正文、下载与 Chat 使用同一 collection。
- paper：使用现有 paper_docs_bge_m3 + BGE-M3；论文仍由既有离线论文流程导入。文档页可以查看正文、调整权限和删除，Chat 可选择该库。
- BM25 从当前 Chroma 内容构建，不再让在线 Chat 读取固定 evaluation JSON。命令行研究脚本的默认 BM25 行为保持兼容。
- 无 role 的旧内容按 admin 处理，不擅自公开。管理员通过文档页权限选项明确发布为 employee/hr。同名混合角色文档按所有片段都可访问的规则处理。
- 未使用的 company_docs_bge_m3 保留为旧索引；不在正式 API 中使用，也不自动删除用户数据。
- 会话绑定知识库，新建会话时选择；发送中禁止切换会话，消息加载完成前禁止发送。
- 数据流为：认证 → 会话所有权 → 授权文档快照 → Dense/BM25 → 原 RRF/精排/Prompt/LLM → 再次验证登录 → 一个事务写两条 Message 和会话更新时间 → History 从消息派生。
- Python RLock + FileLock 协调同一部署的 Chat、索引变更和会话删除；当前是串行安全实现，尚未改为分布式队列。

## 文档写入与恢复

允许 PDF、DOCX、TXT，最大 25 MB。同名文件返回 409，不覆盖原文件也不追加重复向量。先使用临时文件解析和向量化；索引写入失败会补偿清理本次向量与文件。删除时原文件移入 data/documents/.trash；Chroma 删除失败则移回。SQLite、文件和 Chroma 不是跨系统事务：进程硬中断或存储故障仍需要从备份恢复，当前补偿覆盖请求中可捕获的失败。

## SQLite 迁移

FastAPI startup 与 python -m scripts.init_db 使用同一幂等迁移，迁移前备份到 backend/backups/app-*.sqlite3。备份包含旧数据，应和原数据库一样限制访问。

迁移会：哈希原密码（密码本身不变）；user 角色归一为 employee；旧会话标记为 paper；从 ChatHistory 导入未在 Message 中出现的问答；以计数匹配保留真实重复问答；保留原 ChatHistory 作为只读旧档；新增迁移标记。无所属用户的旧历史不对外暴露，原记录仍在旧档中。

新库使用外键；旧 SQLite 表用等效 insert/update/delete triggers 补上父引用检查与级联删除，避免丢弃重建旧表。迁移不自动删除已有孤儿记录，也不猜测缺失文档的公开权限。

## 验证方式

在 backend 执行：

```powershell
..\.venv\Scripts\python.exe -m unittest tests.test_permissions tests.test_knowledge_api -v
```

覆盖真实 HTTP 认证/授权、严格请求字段、Swagger、会话所有权、管理员列表/改角色、过期/注销/撤销、Chat 失败不落库、历史单一数据源、旧库幂等迁移、文档权限、路径检查、上传/删除实时检索、同名冲突、部分写入补偿、Prompt 不包含越权证据。

前端执行 npm run build。模型与外部 LLM 在自动化测试中使用替身；这些测试不声称验证 DeepSeek 在线服务可用性。
