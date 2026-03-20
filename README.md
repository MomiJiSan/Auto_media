# AutoMedia

AI 驱动的短视频自动生成平台。输入一个故事创意，经过访谈问答、剧本生成、分镜解析、TTS、图片生成、图生视频、FFmpeg 合成，输出一条完整短视频。

---

## 项目结构

```
automedia/
├── .env.example              # 环境变量模板
├── pyproject.toml            # Python 依赖（uv）
├── start.py                  # 一键启动脚本
├── frontend/                 # Vue 3 前端
│   └── src/
│       ├── views/            # Step1~4 页面
│       ├── stores/           # Pinia 状态管理
│       ├── api/story.js      # 后端 API 封装
│       └── components/       # UI 组件
└── app/                      # FastAPI 后端
    ├── main.py               # 应用入口
    ├── core/
    │   ├── config.py         # 全局配置（读取 .env）
    │   └── database.py       # SQLAlchemy async 引擎
    ├── models/
    │   └── project.py        # ORM 模型
    ├── schemas/
    │   ├── story.py          # 故事创作 Pydantic 模型
    │   ├── storyboard.py     # 分镜 Pydantic 模型
    │   └── pipeline.py       # 流水线状态 Pydantic 模型
    ├── routers/
    │   ├── story.py          # Phase 1 API（故事创作）
    │   └── pipeline.py       # Phase 2 API（分镜 + 资产 + 视频）
    └── services/
        ├── store.py          # 内存存储（story_id → 数据）
        ├── story_llm.py      # 故事生成服务（mock / 真实 LLM）
        ├── story_mock.py     # Mock 数据
        ├── storyboard.py     # 分镜解析服务（LLM Prompt）
        └── llm/
            ├── base.py       # 抽象接口
            ├── factory.py    # Provider 工厂
            ├── claude.py     # Anthropic Claude
            ├── openai.py     # OpenAI / 兼容接口
            ├── qwen.py       # 阿里云 Qwen
            ├── zhipu.py      # 智谱 GLM
            └── gemini.py     # Google Gemini
```

---

## 快速开始

### 1. 环境要求

- Python 3.12+
- Node.js 16+
- （可选）FFmpeg — 模块 E 合成视频时需要

### 2. 一键启动

```bash
python start.py
```

后端运行在 `http://localhost:8000`，前端运行在 `http://localhost:5173`。

### 3. 手动启动

```bash
# 后端
uvicorn app.main:app --reload

# 前端（另开终端）
cd frontend && npm install && npm run dev
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入 API Key：

```env
DEFAULT_LLM_PROVIDER=claude

ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
QWEN_API_KEY=...
ZHIPU_API_KEY=...
GEMINI_API_KEY=...
```

---

## 完整数据流

```
前端 Step1  输入创意 + 选风格
    ↓ POST /api/v1/story/analyze-idea
前端 Step2  选故事设定，与 AI 对话
    ↓ POST /api/v1/story/generate-outline
前端 Step3  查看大纲 + 人物关系图，流式生成剧本
    ↓ POST /api/v1/story/generate-script（SSE）
前端 Step4  预览剧本，导出 JSON
    ↓ POST /api/v1/story/{id}/finalize        ← 两阶段桥接点
    ↓ POST /api/v1/pipeline/{id}/storyboard   ← 剧本 → 分镜 JSON
    ↓ POST /api/v1/pipeline/{id}/generate-assets
    ↓ POST /api/v1/pipeline/{id}/render-video
    ↓ GET  /api/v1/pipeline/{id}/status（轮询）
    ↓ POST /api/v1/pipeline/{id}/stitch
      最终视频文件
```

---

## API 概览

### Phase 1 — 故事创作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/story/analyze-idea` | 分析创意，返回故事设定选项 |
| POST | `/api/v1/story/generate-outline` | 生成大纲、人物、人物关系 |
| POST | `/api/v1/story/chat` | 与 AI 实时对话（SSE） |
| POST | `/api/v1/story/generate-script` | 流式生成剧本场景（SSE） |
| POST | `/api/v1/story/{id}/finalize` | 序列化剧本，供第二阶段使用 |

### Phase 2 — 视频流水线

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/pipeline/{id}/storyboard` | 剧本 → 分镜 JSON（调用 LLM） |
| POST | `/api/v1/pipeline/{id}/generate-assets` | 触发 TTS + 图片生成 |
| POST | `/api/v1/pipeline/{id}/render-video` | 触发图生视频（异步队列） |
| GET  | `/api/v1/pipeline/{id}/status` | 轮询渲染进度 |
| POST | `/api/v1/pipeline/{id}/stitch` | FFmpeg 合成最终视频 |

---

## 模块进度

| 模块 | 说明 | 状态 |
|------|------|------|
| Phase 1 | 故事创作（访谈、大纲、剧本） | ✅ 完成 |
| 模块 A | 分镜引擎（LLM 解析脚本） | ✅ 完成 |
| 模块 B | TTS 语音生成（Edge TTS） | ✅ 完成 |
| 模块 C | 关键帧图片生成（FLUX.1） | ✅ 完成 |
| 模块 D | 图生视频（通义万象） | ✅ 完成 |
| 模块 E | FFmpeg 合成 | 🔲 待开发 |
| 自动化流水线 | 一键生成 + 双策略支持 | ✅ 完成 |

### Phase 2 新特性

- ✅ **一键生成**：`POST /api/v1/pipeline/{id}/auto-generate` - 自动执行全流程
- ✅ **双策略支持**：
  - **分离式（separated）**：TTS → 图片 → 图生视频 → FFmpeg 合成
  - **一体式（integrated）**：图片 → 视频语音一体生成
- ✅ **真实实现**：所有服务均已实现，不再是 mock
- ✅ **实时进度追踪**：详细的步骤状态和进度信息

详见 [PIPELINE_API.md](./PIPELINE_API.md)

---

## LLM Provider 切换

前端通过设置页配置 API Key 和 provider，无需重启后端。后端也支持通过 `.env` 设置默认 provider：

```env
DEFAULT_LLM_PROVIDER=qwen  # claude / openai / qwen / zhipu / gemini
```

支持中转站：每个 provider 都有独立的 `*_BASE_URL` 配置项，直接替换为中转地址即可。
