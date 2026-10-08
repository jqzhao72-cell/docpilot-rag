# DocPilot FastAPI API Reference

本文档对应 API `2.0.0`。默认地址为 `http://127.0.0.1:8000`，Swagger 位于 `/docs`。

## 认证与 Swagger

除 `GET /`、`POST /register`、`POST /login` 外，业务接口都要求：

```http
Authorization: Bearer <access_token>
```

Swagger 操作：

1. 调用 `POST /login`。
2. 复制 `access_token`。
3. 点击右上角 **Authorize**，只粘贴 token 本身。
4. 调用带锁接口。

Token 有效期 8 小时。注销、角色修改或到期后需要重新登录。

## 权限矩阵

| 功能 | employee | hr | admin |
| --- | ---: | ---: | ---: |
| Chat、自己的会话和历史 | 是 | 是 | 是 |
| 查看 employee / hr / admin 文档 | employee | employee、hr | 全部 |
| 上传/删除文档 | 否 | employee、hr | 全部 |
| 设置文档权限 | 否 | 否 | 是 |
| 用户列表、角色修改、全部历史 | 否 | 否 | 是 |

注册用户固定为 employee。缺少 role 的旧文档按 admin 保护。

## 通用错误

错误响应为 `{"detail":"错误说明"}`。

| 状态码 | 含义 |
| ---: | --- |
| 400 | 文件名等内容非法 |
| 401 | 未登录、Token 无效、过期或被撤销 |
| 403 | 角色权限不足 |
| 404 | 资源不存在、不可见或不属于当前用户 |
| 409 | 用户名/文件名冲突、知识库繁忙或权限变化 |
| 413 | 文件超过 25 MB |
| 415 | 文件格式不支持 |
| 422 | 请求字段、类型或枚举值错误 |
| 503 | RAG、模型或 LLM 暂不可用 |

请求模型禁止额外字段。用户身份只取自 Token，业务请求不能发送身份用途的 `user_id` 或 `operator_user_id`。

## 接口总览

| 方法 | 路径 | 权限 | 功能 |
| --- | --- | --- | --- |
| GET | `/` | public | 服务状态 |
| POST | `/register` | public | 注册 employee |
| POST | `/login` | public | 登录并签发 Token |
| GET | `/users/me` | 登录 | 当前身份 |
| POST | `/logout` | 登录 | 撤销当前 Token |
| GET | `/users` | admin | 用户列表 |
| PUT | `/users/{user_id}/role` | admin | 修改角色 |
| GET | `/conversations` | 本人 | 会话列表 |
| POST | `/conversations` | 本人 | 创建会话 |
| GET | `/conversations/{id}/messages` | 本人 | 会话消息 |
| PATCH | `/conversations/{id}` | 本人 | 重命名 |
| DELETE | `/conversations/{id}` | 本人 | 删除会话 |
| POST | `/chat` | 本人的会话 | RAG 问答 |
| GET | `/history` | 本人 | 个人问答历史 |
| GET | `/admin/history` | admin | 全部历史 |
| GET | `/documents` | 文档 RBAC | 文档列表 |
| POST | `/documents` | hr/admin | 上传企业文档 |
| GET | `/documents/{filename}/content` | 文档 RBAC | 索引正文 |
| GET | `/documents/{filename}/download` | 文档 RBAC | 企业原文件 |
| PUT | `/documents/{filename}/role` | admin | 修改文档权限 |
| DELETE | `/documents/{filename}` | hr/admin | 删除文档 |

## 系统状态

### GET `/`

公开接口。响应：

```json
{"message":"DocPilot API running","version":"2.0.0"}
```

## 认证与用户

### POST `/register`

密码至少 8 个字符；客户端不能指定 role。

```json
{"username":"lisi","password":"password123"}
```

响应 `201`：

```json
{"message":"注册成功","user_id":3,"username":"lisi","role":"employee"}
```

用户名重复返回 `409`，schema 错误返回 `422`。

### POST `/login`

```json
{"username":"lisi","password":"password123"}
```

响应：

```json
{
  "user_id":3,
  "username":"lisi",
  "role":"employee",
  "access_token":"opaque-random-token",
  "token_type":"bearer",
  "expires_in":28800
}
```

凭据错误返回 `401`。

### GET `/users/me`

返回 Token 对应用户：

```json
{"user_id":3,"username":"lisi","role":"employee"}
```

### POST `/logout`

撤销当前 Token。成功返回 `204 No Content`。

### GET `/users`

仅 admin。Query 参数：

| 参数 | 默认 | 限制 |
| --- | ---: | --- |
| `offset` | 0 | ≥ 0 |
| `limit` | 100 | 1–200 |

响应：

```json
{
  "items":[
    {"user_id":1,"username":"zhangsan","role":"admin"},
    {"user_id":2,"username":"admin","role":"hr"}
  ],
  "total":2
}
```

### PUT `/users/{user_id}/role`

仅 admin。修改后撤销目标用户全部 Token。

```json
{"role":"hr"}
```

role 只允许 `employee`、`hr`、`admin`。管理员不能降低自己的权限，否则返回 `409`；用户不存在返回 `404`。

## 会话

### POST `/conversations`

创建当前用户会话：

```json
{"title":"公司年假问题","knowledge_base":"company"}
```

`knowledge_base` 只允许 `company` 或 `paper`，默认 company。知识库创建后不能中途切换。

响应 `201`：

```json
{
  "id":12,
  "user_id":2,
  "title":"公司年假问题",
  "knowledge_base":"company",
  "created_time":"2026-10-08T10:00:00",
  "updated_time":"2026-10-08T10:00:00"
}
```

### GET `/conversations`

返回当前用户的会话数组，按最近更新时间倒序排列。

### GET `/conversations/{conversation_id}/messages`

只允许会话所有者。返回：

```json
[
  {
    "id":25,
    "conversation_id":12,
    "role":"user",
    "content":"员工一年有多少天年假？",
    "sources":[],
    "created_time":"2026-10-08T10:01:00"
  }
]
```

其他用户访问返回 `404`，避免泄漏会话存在性。

### PATCH `/conversations/{conversation_id}`

只允许会话所有者：

```json
{"title":"年休假制度"}
```

返回更新后的会话。

### DELETE `/conversations/{conversation_id}`

删除自己的会话和消息。成功返回 `204`。

## RAG Chat

### POST `/chat`

必须先创建会话：

```json
{"question":"员工一年有多少天年假？","conversation_id":12}
```

调用链：

```text
身份 → 会话所有权 → 会话绑定知识库 → 文档权限过滤
→ Dense + BM25 → RRF → Reranker → 二阶段融合
→ Prompt + 最近 6 条消息 → DeepSeek
→ 再次验证 Token/角色 → 一个事务保存两条 Message
```

响应：

```json
{
  "conversation_id":12,
  "question":"员工一年有多少天年假？",
  "answer":"根据年休假制度……[1]",
  "sources":[{
    "index":1,
    "id":"chunk-id",
    "source":"员工带薪年休假管理办法.pdf",
    "page":"3",
    "page_start":3,
    "page_end":3,
    "section":"年休假天数",
    "chunk_type":"text",
    "text":"员工累计工作……",
    "knowledge_base":"company"
  }],
  "timings":{
    "retrieval_ms":120.0,
    "reranker_ms":300.0,
    "deepseek_api_ms":1500.0,
    "total_ms":1920.0
  }
}
```

没有可见片段时返回说明性答案和空 sources。RAG/LLM 异常返回 `503`，不保存半条消息。生成期间 Token 被撤销或角色变化时也不会保存答案。

## 历史

### GET `/history`

返回当前用户的问答历史。历史由 Conversation/Message 派生，不再双写旧 ChatHistory。

```json
[{
  "id":26,
  "conversation_id":12,
  "user_id":2,
  "question":"员工一年有多少天年假？",
  "answer":"根据制度……[1]",
  "sources":[],
  "created_time":"2026-10-08T10:01:03"
}]
```

### GET `/admin/history`

仅 admin。未传参数时返回全部用户历史；可用 `?user_id=2` 过滤目标用户。

## 文档

`knowledge_base` 只允许：

- `company`：`company_docs` + MiniLM，支持网页上传和原文件下载。
- `paper`：`paper_docs_bge_m3` + BGE-M3，通过既有离线论文流程导入。

### GET `/documents`

例如：

```http
GET /documents?knowledge_base=company
GET /documents?knowledge_base=paper
```

响应：

```json
[{"filename":"年休假办法.pdf","chunks":8,"role":"employee","knowledge_base":"company"}]
```

只返回当前角色能访问整份文档的记录。任一同名片段权限过高时，整份文档都不显示。

### POST `/documents`

仅 hr/admin，且只允许 `company`。请求为 `multipart/form-data`：

| 字段 | 说明 |
| --- | --- |
| `file` | PDF、DOCX、TXT，最大 25 MB |
| `role` | employee、hr 或 admin |
| `knowledge_base` | company |

HR 只能上传 employee/hr 文档；Admin 可上传全部级别。同名返回 `409`，不会覆盖文件或追加向量。

响应 `201`：

```json
{
  "filename":"年休假办法.pdf",
  "chunks":8,
  "role":"employee",
  "knowledge_base":"company",
  "message":"文档已入库，可直接用于企业知识库问答"
}
```

### GET `/documents/{filename}/content`

返回 company 或 paper 的索引正文：

```json
{
  "filename":"年休假办法.pdf",
  "knowledge_base":"company",
  "chunks":[{
    "text":"员工累计工作……",
    "section":"年休假天数",
    "page_start":3,
    "page_end":3
  }]
}
```

中文文件名应进行 URL 编码。

### GET `/documents/{filename}/download`

只下载 company 中保留的原文件。论文库或原文件不存在返回 `404`，仍可使用 `/content`。

### PUT `/documents/{filename}/role`

仅 admin。Query 指定 `knowledge_base=company` 或 `paper`：

```json
{"role":"hr"}
```

它会统一修改该文件所有 chunks 的权限。旧论文缺少 role 时按 admin 保护，可通过此接口明确开放。

### DELETE `/documents/{filename}`

HR/Admin 按角色删除文档，Query 指定 knowledge_base。成功返回 `204`。企业原文件先移入 `data/documents/.trash`；向量删除失败时文件会移回。

## 已移除的旧接口

| 旧接口 | 替代接口 |
| --- | --- |
| `POST /upload` | `POST /documents` |
| `GET /history/user/{user_id}` | `GET /history` |
| `GET /conversations/user/{user_id}` | `GET /conversations` |

## 自动文档

| URL | 功能 |
| --- | --- |
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |
| `/openapi.json` | OpenAPI schema |

## 最短调用流程

```text
POST /login → Swagger Authorize → POST /conversations
→ POST /chat → GET /history → POST /logout
```

配置新 HR：

```text
管理员 POST /login → Authorize → GET /users
→ PUT /users/{目标ID}/role {"role":"hr"}
→ 目标用户重新登录
```
