# Weather Atlas · 实时天气信息面板

一个完整的全栈天气面板：输入城市后由 Python 后端完成地理编码和实时天气聚合，React 前端负责可视化展示，MongoDB 记录最常查询的城市。

## 功能

- 城市搜索：限定中国城市，支持中文或拼音城市名，自动匹配城市坐标和时区。
- 实时天气：温度、体感、天气状况、湿度、风速/风向、气压、云量、降水。
- 趋势查看：未来 24 小时逐小时趋势和未来 7 天预报。
- 日照信息：日出、日落、UV 指数。
- 常查城市：每次成功搜索自动累加查询次数，按热度展示。
- 账号登录：注册、登录、退出，登录后常查城市按用户隔离保存。
- 天气助手：登录后可询问最近查询城市的天气问题，使用 OpenAI 兼容接口。
- 今日新闻：城市天气返回当天可验证新闻的标题、来源、发布时间和原文链接。
- 数据源：Open-Meteo，无需申请 API Key。
- 本地体验：MongoDB 不可用时后端自动使用内存存储，不影响查看天气和体验 UI；接入 MongoDB 后自动持久化。

## 技术栈

- 前端：React 18 + Vite + lucide-react
- 后端：Python 3.9+ + FastAPI + httpx
- 数据库：MongoDB + PyMongo
- 天气服务：Open-Meteo Forecast API / Geocoding API

## 快速开始

### 1. 启动 MongoDB（推荐）

已安装 Docker Desktop 时，在项目根目录执行：

```bash
docker compose up -d mongodb
```

### 2. 启动后端

PowerShell：

```powershell
python -m venv .venv
\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
python -m uvicorn backend.app.main:app --reload --port 8000
```

后端地址：`http://localhost:8000`，接口文档：`http://localhost:8000/docs`。

### 3. 启动前端

新开一个终端：

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

打开 `http://localhost:5173`。

也可以在根目录安装 `concurrently` 后使用：

```powershell
npm install
npm run dev
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务和数据库状态 |
| GET | `/api/weather?city=上海` | 查询城市天气并记录热度 |
| GET | `/api/cities?limit=6` | 获取常查城市 |
| POST | `/api/auth/register` | 注册并登录 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 退出登录 |
| GET | `/api/auth/me` | 获取当前用户 |
| POST | `/api/assistant/chat` | 向天气助手提问 |

## 环境变量

后端环境变量放在 `backend/.env`：

```env
MONGO_URL=mongodb://localhost:27017
MONGO_DB=weather_atlas
FRONTEND_ORIGIN=http://localhost:5173
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=你的API Key
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_BASE_URL` 可以替换为兼容 OpenAI Chat Completions 格式的服务地址。API Key 只放在 `backend/.env`，不要提交到 Git。今日新闻默认使用 Google News RSS，不需要额外新闻 API Key。

前端环境变量放在 `frontend/.env`：

```env
VITE_API_BASE_URL=http://localhost:8000
```
