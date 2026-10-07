# DocPilot Frontend

正式前端使用 Vue 3、Vite、JavaScript、Vue Router、Pinia、Axios 和 CSS。它只负责交互与状态展示，业务数据全部来自 FastAPI。

## 启动

先在另一个终端启动后端：

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

再从仓库根目录运行：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。

## 环境变量

开发默认值在 `.env.development`。部署时通过环境文件或部署平台设置：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Vue 组件不保存后端地址，所有请求统一经过 `src/api/client.js`。

## 构建

```powershell
npm run build
```

## 目录职责

- `src/api/`：FastAPI 请求封装。
- `src/components/`：布局和来源证据等复用组件。
- `src/router/`：页面路由与登录保护。
- `src/stores/`：Pinia 用户状态。
- `src/views/`：登录、问答、知识库、文档和历史页面。
- `src/styles/`：全局企业知识库视觉样式。
