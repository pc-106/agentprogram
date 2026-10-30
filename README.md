# 扫地机器人智能客服 · Vue 3 + FastAPI 重写版

原项目是一个 Streamlit 单页聊天 Demo。搬迁时原代码未做任何修改，之后由使用者在
`ragagent/` 中继续改造（ChatOpenAI 兼容模式、高德天气/定位、提示词等）；
新版后端通过运行时兼容层适配这些变化，界面重写为 Vue 3 单页应用，后端为 FastAPI。

```
agentprogram/
├── ragagent/          # ← 原工程（搬迁时未改动；后续由使用者改造）
│   ├── app.py         #   原 Streamlit 入口（仍可单独运行）
│   ├── agent/         #   ReAct Agent + 7 个工具（天气/定位走高德）+ 中间件
│   ├── rag/           #   Chroma 向量库 + RAG 总结链
│   ├── model/         #   ChatOpenAI 兼容模式 + DashScope Embedding 工厂
│   ├── prompt/        #   主提示词 / RAG 提示词 / 报告提示词
│   ├── config/        #   *.yml 配置
│   ├── data/          #   6 份知识库文档 + records.csv（120 条使用记录）
│   ├── .env           #   高德 AMAP_API_KEY（使用者配置，不提交）
│   └── utils/         #   配置 / 日志 / 文件 / 路径工具
├── backend/           # ← 新增：FastAPI 后端（复用 ragagent 的 Agent）
│   ├── app/
│   │   ├── core/      #   配置、legacy 兼容层、SSE 事件、工具元信息
│   │   ├── db/        #   SQLite 会话持久化
│   │   ├── services/  #   引擎门面、真实 Agent、离线引擎、BM25 索引、报告生成
│   │   ├── api/       #   chat / sessions / kb / system 路由
│   │   └── main.py    #   应用入口（同时托管前端构建产物）
│   ├── tests/         #   37 项 pytest（检索 / 报告 / API / 事件映射 / 模式降级 / 引用）
│   └── run.py
└── frontend/          # ← 新增：Vue 3 + TypeScript + Vite + Tailwind v4
    └── src/
        ├── views/     #   对话 / 知识库 / 使用报告 / 系统设置
        ├── components/#   消息、工具轨迹、引用、输入框、侧边栏…
        ├── stores/    #   app 状态 + 会话状态（含 SSE 流式处理）
        └── api/       #   fetch 封装 + SSE 解析
```

---

## 1. 快速开始

### 1.1 安装依赖

```powershell
# 后端（必需）
cd backend
pip install -r requirements.txt    # 已含 jieba（可选，缺失时自动退化为二元组分词）

# 前端
cd ../frontend
pnpm install                       # 或 npm install
```

### 1.2 构建前端并启动（单端口）

```powershell
cd frontend
pnpm build                   # 产物输出到 frontend/dist

cd ../backend
python run.py                # http://127.0.0.1:8000
```

FastAPI 会自动托管 `frontend/dist`，所以**只需要访问 `http://127.0.0.1:8000`**。
接口文档在 `http://127.0.0.1:8000/api/docs`。

四种启动方式效果完全一致（`main.py` 被直接执行时会自动转交给 `run.py`）：

| 命令 | 说明 |
|---|---|
| `python backend/run.py` | 推荐，支持 `--host/--port/--reload` |
| `python backend/app/main.py` | IDE 里右键 Run 也不会再报 `relative import` |
| `cd backend && python -m uvicorn app.main:app` | 标准 uvicorn 方式 |
| `cd backend && python -m app.main` | 模块方式 |

端口被占用时会直接提示占用端口与换端口命令，而不是抛 `WinError 10048`。

### 1.3 开发模式（前后端分离热更新）

```powershell
# 终端 1
cd backend && python run.py --reload

# 终端 2
cd frontend && pnpm dev       # http://127.0.0.1:5173，/api 已代理到 8000
```

---

## 2. 双模式：有 Key 走真模型，没 Key 也能用

| | 离线演示模式 | 真实 Agent 模式 |
|---|---|---|
| 触发条件 | 未设置 `DASHSCOPE_API_KEY` | 设置了 `DASHSCOPE_API_KEY` |
| 推理 | 本地 BM25 检索 + 规则模板 | `ragagent` 里的 `ReAct_Agent` + 通义千问（OpenAI 兼容模式） |
| 工具 | 7 个工具全部本地重实现 | 原 `agent_tools.py` 里的 7 个 `@tool`（天气/定位走高德） |
| 报告 | 规则化 Markdown 报告 | 原报告提示词 + 模型撰写 |
| 依赖 | 纯 Python，无 API 调用 | langchain / langgraph / langchain-openai / chroma |

配置方式：DashScope Key 只从**系统环境变量**读取，后端自身不需要 `.env` 文件；
`ragagent/.env` 仅用于高德 `AMAP_API_KEY`（可选，后端会顺带读取）。

```powershell
# 设置后重启后端；没有设置则自动走离线模式
$env:DASHSCOPE_API_KEY="sk-xxxx"

# 可选：强制模式（默认 auto，一般不用设）
$env:AGENT_MODE="auto"   # auto | real | demo
```

* `auto`：有 Key 走真实 Agent；**没有 Key 或调用失败时，先在对话里提示用户，再自动切到离线模式把问题答完**；
* `real`：强制真实模式，没有 Key 或调用失败都直接报错（便于排查 Key / 模型名）；
* `demo`：强制离线演示，即使有 Key。

> 自动切换不是静默的：助手消息里会出现一条米色提示（如「未检测到 DASHSCOPE_API_KEY，
> 已自动切换到离线模式回答」/「调用真实模型失败，已自动切换到离线模式继续回答」），
> 下面才是离线模式的回答；同时右上角徽标会从「Agent 线上模式」变成「离线模式」。

### 2.1 模型与 Key 均由项目原有配置决定

本版**不修改、不覆盖**真实模式使用的模型：实际调用的是
`ragagent/config/rag.yml` 里的 `chat_model_name` / `embedding_model_name`。

Key 只从**系统环境变量**读取，后端不要求任何 `.env` 文件：

```powershell
$env:DASHSCOPE_API_KEY="sk-xxxx"   # 设完重启后端
```

> 真实模式仍然需要 DashScope Key：聊天模型要调用它，查询向量化（embedding）也要调用它。
> 离线模式则完全不需要 Key。

### 2.2 真实模式会把检索结果一起返回

`ragagent` 的 `rag_summarize` 原本只返回"总结后的字符串"，检索到的 chunk 不对外暴露。
新版在不改原码的前提下包装了 `RagSummarizeService.retriever_docs`，把本次命中的文档
以 `citations` 事件回传：

- 前端回答下方显示「知识库引用 · N 条」，点任意一条可展开**检索原文**；
- 事件流顺序：`tool_call(rag_summarize)` → `tool_result` → `citations` → `delta…`；
- 引用同时写入消息 meta，刷新页面后仍然可见。

高德服务同理：`get_weather` / `get_user_location` 直接使用 `ragagent/agent/tools/agent_tools.py`
里的高德实现，Key 放在 `ragagent/.env` 的 `AMAP_API_KEY`（后端会自动加载）。

### 2.3 向量库由使用方自行建立

新版不包含、也不执行任何建库逻辑，`ragagent/chroma_db` 完全交给原工程的流程维护。
真实模式的 `rag_summarize` 直接读这个库；库为空时检索结果为空（模型只能凭自身知识回答）。

> 提醒：原工程按 `md5.text` 做文件级去重。若要**重建**，先删掉/清空
> `ragagent/md5.text`，否则 `load_document()` 会认为所有文件都处理过而直接跳过。
> 知识库页会显示 Chroma 当前片段数，可用来确认建库结果。

> 离线模式用的是本地 BM25 索引（771 段），不依赖 Chroma；两套索引都读同一份
> `ragagent/data`，只是切块方式不同。

> 离线模式不是"假回答"：它读取同一份 `ragagent/data` 知识库和 `records.csv`，
> 只是把"检索 + 总结"换成了 BM25 + 模板。前端的事件流（思考 / 工具调用 / 工具结果 /
> 正文增量 / 引用）与真实模式完全一致。

---

## 3. 功能覆盖对照

| 原能力（Streamlit 版） | 新版落点 | 说明 |
|---|---|---|
| 标题 + 聊天记录回放 | 对话页 | 多会话 + 历史消息持久化（SQLite） |
| 输入框提问 | 底部输入框 | Enter 发送 / Shift+Enter 换行 / 流式渲染 / 可中止 |
| `st.spinner("智能客服思考中…")` | 思考状态 + 工具轨迹 | 实时展示"思考 → 工具调用 → 观察"的完整链路 |
| `execute_stream` 流式输出 | SSE + `delta` 事件 | 真实模式按 token 流；**离线模式也按 10 字/12ms 逐块下发**，都带光标动画 |
| 模式状态 | 右上角模式徽标 | **「离线模式」/「Agent 线上模式」**，降级时实时切换 |
| RAG 检索（`rag_summarize`） | 工具轨迹 + 知识库引用 | 引用显示来源文件与相关度 |
| 7 个工具 | 工具清单 / 轨迹面板 | 参数、耗时、结果预览全部可见 |
| 报告生成（提示词切换） | 独立「使用报告」页 | 选用户/月份 → 一键生成 → 复制 / 下载 .md |
| 外部使用记录（records.csv） | 报告页数据目录 | 10 用户 × 12 月 = 120 条 |
| 知识库（Chroma + data 目录） | 「知识库」页 | 文档清单、片段统计、检索测试、本地 BM25 索引重建（Chroma 由原工程建） |
| 提示词 | 「系统设置」页 | 三份提示词原文可查看 |
| 原工程配置 | 「系统设置」页 | 模型名、切块参数、召回条数、路径 |

新增能力：多会话与重命名/置顶/删除、暗色模式、移动端适配、请求中止、报告下载、
检索测试、工具调用耗时统计、原工程兼容层自检、离线模式模拟流式、实时模式徽标。

### 3.1 流式输出与模式徽标

- **流式**：后端统一发 `delta` 事件，前端逐块追加并显示光标。
  真实模式是模型 token 流；离线模式没有 token，按 `10 字 / 12ms` 节流下发
  （可用 `DEMO_STREAM_CHUNK` / `DEMO_STREAM_DELAY` 调整），视觉上同样是“一个字一个字出来”。
- **模式徽标**：对话页、知识库、报告页、设置页的**右上角**都会显示当前模式：
  - 绿色圆点 + **「Agent 线上模式」**：走真实模型；
  - 琥珀色圆点 + **「离线模式」**：本地检索/模板回答。
  真实调用失败自动降级时，徽标会在同一轮对话内从线上切换为离线。

---

## 4. 为什么需要兼容层（重要）

原工程直接 `python app.py` 会失败，存在三处「配置与文件不一致」：

| # | 原代码里的内容 | 实际文件 |
|---|---|---|
| 1 | `from utils.path_tools import get_abs_path` | `utils/path_tool.py`（拼写错误） |
| 2 | 读取 `config/rag.yaml` 等 | `config/*.yml` |
| 3 | 提示词路径 `prompts/main_prompt.txt` | `prompt/main_prompt.txt` |

兼容层在 `backend/app/core/legacy.py` 里以运行时注入完成适配：

* `sys.modules["utils.path_tools"] = utils.path_tool`（模块别名）；
* `sys.modules["utils.config_handler"]` 替换为读取 `*.yml`、并把 `prompts/` 修正为
  `prompt/` 的替代模块；
* Chroma 的 `persist_directory` / `data_path` / `md5_hex_store` 改为绝对路径，
  避免从 `backend/` 启动时把向量库建到错误位置；
* 加载 `ragagent/.env`（复刻原 `config_handler.py` 的 `load_dotenv` 行为，
  高德 `AMAP_API_KEY` 继续生效；文件不存在时跳过）；
* 原工程 logger 的文件输出重定向到 `backend/data/logs/`，不再往 `ragagent/logs/`
  追加内容（控制台输出保持原格式）。

搬迁时 37 个文件哈希一致；之后使用者改造了 `model/factory.py`（ChatOpenAI 兼容模式）、
`agent_tools.py`（高德天气/定位）、`config_handler.py`、提示词与 `.env`，因此当前内容
已不等于搬迁快照。兼容层只做运行时适配，**不回写任何原工程文件**。

---

## 5. 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 运行模式、知识库统计、会话数 |
| GET | `/api/system/config` | 模型、路径、工具、提示词、兼容层状态 |
| POST | `/api/chat` | **SSE 流式对话**；`{message, session_id?, intent}` |
| GET/POST | `/api/sessions` | 会话列表 / 新建 |
| GET/PATCH/DELETE | `/api/sessions/{id}` | 详情（含消息）/ 重命名置顶 / 删除 |
| GET | `/api/kb/status` | 索引状态与配置 |
| GET | `/api/kb/documents` | 文档清单（含跳过原因） |
| POST | `/api/kb/search` | 检索测试 `{query, k}`（本地 BM25） |
| POST | `/api/kb/reindex` | 重建本地 BM25 索引（不动 Chroma 向量库） |
| GET | `/api/kb/records` | 报告页用户/月份目录 |

SSE 事件：`meta` → `status` / `notice` / `think` / `tool_call` / `tool_result` /
`citations` / `delta` → `done`，异常时 `error`。前端用 `fetch` + `ReadableStream`
消费（`EventSource` 不支持 POST）。

---

## 6. 测试

```powershell
cd backend
python -m pytest tests -q
# 37 passed

cd ../frontend
pnpm build                     # vue-tsc 类型检查 + 生产构建
```

覆盖内容：BM25 检索命中率（含长句、同义句型）、问答切块边界、CSV 转义还原、
报告结构与指标解读、SSE 事件顺序与会话落库、LangChain 流式消息到前端事件的映射
（用构造消息验证，不需要 API Key），以及**无 Key / 调用失败时的提示与自动降级**。

---

## 7. 验收记录

搬迁时的校验（改造前）：

```
搬迁前：FILES=37  BYTES=390809  SHA256(合并)=447056BF7ED3D53EB6608C543F0270266450A391A6EAF79FFEE959060CF8295B
搬迁后：FILES=37  DIFF=0        SHA256(合并)=447056BF7ED3D53EB6608C543F0270266450A391A6EAF79FFEE959060CF8295B
```

> 之后由使用者自行改造了 `ragagent` 的模型工厂、高德工具、配置加载与提示词，
> 并自行维护向量库；因此当前 `ragagent` 的内容已不等于搬迁时快照，
> 上面的哈希只作为"搬迁未改动"的记录。新版后端通过兼容层适配这些变化，未回写原工程文件。

---

## 8. 常见问题

**Q：后端还需要单独配 Key 吗？**
A：不需要任何文件。Key 只从系统环境变量读取（`DASHSCOPE_API_KEY`），后端没有 `.env` 模板也不需要 `.env`；
真实模式仍需要它（聊天 + 查询向量化），离线模式完全不需要。

**Q：高德 Key 放哪？**
A：原工程 `ragagent/.env` 里的 `AMAP_API_KEY`（如果存在，后端会顺带加载，仅补缺）；
也可以直接设成系统环境变量。`get_weather` / `get_user_location` 使用原工程的高德实现。

**Q：RAG 检索返回空？**
A：先确认 `ragagent/chroma_db` 里是否有数据（知识库页会显示 Chroma 片段数）。
如果要重建，注意先清空 `ragagent/md5.text`，否则原工程的去重逻辑会跳过所有文件。

**Q：直接运行 `app/main.py` 报 `attempted relative import with no known parent package`？**
A：已修复。`main.py` 顶部检测到 `__package__` 为空时，会先把 `backend/` 加入 `sys.path`
再转交 `run.py` 用 import string 启动，所以 `python backend/app/main.py`、IDE 右键 Run 都能用。

**Q：报 `WinError 10048 / 通常每个套接字地址只允许使用一次`？**
A：8000 端口已被另一个后端实例占用。新版会在启动前检测并给出提示：

```powershell
netstat -ano | findstr :8000      # 找 PID
taskkill /PID <PID> /F            # 结束旧实例
python run.py --port 8001         # 或直接换端口
```

**Q：真实模式报 `InvalidParameter: url error, please check url`？**
A：旧版用 `ChatTongyi` SDK 调 `qwen3.8-omni-flash` 会报这个错；改成
`ChatOpenAI` 兼容模式（`base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`）
后实测可用。若仍报错，检查 `ragagent/model/factory.py` 里的 base_url / model 是否匹配，
以及 Key 是否属于该账号。

**Q：真实模式首字要等很久？**
A：模型首 token 延迟（常见 5~15 秒）属于上游推理耗时；等待期间界面会显示
「正在生成回答…」，首 token 到达后逐字渲染。离线模式按 10 字/12ms 模拟流式，首字几乎立即出现。

**Q：真实模式报 "Did not find dashscope_api_key"？**
A：没读到 Key。`DASHSCOPE_API_KEY` 只从系统环境变量读取（后端不读 `.env` 里的 DashScope Key）；
设置后重启后端。`ragagent/.env` 仅用于高德 `AMAP_API_KEY`。

**Q：真实模式报 Chroma / 向量库为空？**
A：`ragagent` 的向量库需要先建：原工程 `rag/vector_store.py` 的 `load_document()` 会读取
`data/` 并写入 `chroma_db/`（依赖 DashScope Embedding）。新版离线模式不依赖它。
建库前真实模式的 RAG 会返回空上下文，模型只能凭自身知识回答。

**Q：PDF 能检索吗？**
A：能。`扫地机器人100问.pdf` 可正常提取中文正文；索引页会显示每份文档的片段数与跳过原因。

**Q：会话存在哪？**
A：`backend/data/app.db`（SQLite）。删除该文件会清空所有会话。
