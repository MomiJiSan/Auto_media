# API Key 管理指南

## 概述

AutoMedia 支持多个 LLM 提供商，并提供了灵活的 API key 管理机制。系统支持**两种配置方式**，可以根据使用场景选择。

## 配置方式

### 方式一：后端静态配置（推荐用于生产环境）

在项目根目录的 `.env` 文件中配置 API keys：

```bash
# .env 文件示例

# 默认使用的 LLM provider: claude / openai / qwen / zhipu / gemini
DEFAULT_LLM_PROVIDER=claude

# Anthropic Claude
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1

# 阿里云 Qwen (DashScope)
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 智谱 GLM
ZHIPU_API_KEY=your_zhipu_api_key
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# 硅基流动 (图片生成)
SILICONFLOW_API_KEY=your_siliconflow_api_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
```

**优点**：
- 配置集中管理
- 适合生产环境
- 支持所有功能模块（剧本生成、分镜解析、图片生成等）

**缺点**：
- 修改需要重启服务
- 不够灵活

### 方式二：前端动态配置（推荐用于开发/测试）

在前端设置页面配置 API keys：

1. 打开应用，进入"设置"页面
2. 填写以下字段：
   - **Backend URL**: 后端服务地址（如 `http://localhost:8000`）
   - **Provider**: 选择 LLM 提供商（Claude/OpenAI/Qwen/智谱/Gemini/自定义）
   - **Base URL**: API 中转地址（可选，用于自定义 endpoint）
   - **API Key**: 你的 API key

3. 点击"保存设置"

**优点**：
- 无需重启服务
- 支持多个用户使用不同的 API keys
- 方便测试和调试

**缺点**：
- 仅支持 LLM 相关功能（剧本生成、大纲生成、分镜解析）
- 图片生成等其他服务仍需在 `.env` 配置

## 工作原理

### 优先级机制

前端动态配置**优先级高于**后端静态配置：

```
前端 Headers → 后端 Settings → 默认值
```

具体流程：
1. 前端在请求时通过 headers 发送配置：
   - `X-LLM-API-Key`: API key
   - `X-LLM-Base-URL`: Base URL
   - `X-LLM-Provider`: Provider 名称

2. 后端接口从 headers 提取配置：
   ```python
   api_key = request.headers.get("X-LLM-API-Key", "")
   base_url = request.headers.get("X-LLM-Base-URL", "")
   provider = request.headers.get("X-LLM-Provider", "claude")
   ```

3. 传递给 LLM Provider Factory：
   ```python
   llm = get_llm_provider(
       provider=provider,
       model=model,
       api_key=api_key,  # 优先使用传入的值
       base_url=base_url
   )
   ```

4. Factory 优先使用传入的值，否则使用 settings：
   ```python
   def get_llm_provider(provider, model=None, api_key="", base_url=""):
       return ClaudeProvider(
           api_key=api_key or settings.anthropic_api_key,
           base_url=base_url or settings.anthropic_base_url,
           model=model
       )
   ```

### 支持的功能

| 功能 | 前端配置支持 | 后端配置支持 |
|------|------------|------------|
| 剧本分析 | ✅ | ✅ |
| 大纲生成 | ✅ | ✅ |
| 剧本生成 | ✅ | ✅ |
| AI 对话 | ✅ | ✅ |
| 分镜解析 | ✅ | ✅ |
| 图片生成 | ❌ | ✅ |
| TTS 语音 | ❌ | ✅ |
| 视频生成 | ❌ | ✅ |

## 故障排查

### 1. 500 错误：分镜解析失败

**可能原因**：
- API key 未配置或无效
- Provider 不支持
- Base URL 错误

**解决方法**：
1. 检查前端设置页面的 API key 是否正确
2. 确认选择的 Provider 与 API key 匹配
3. 如果使用自定义 Base URL，确保地址正确
4. 查看后端日志获取详细错误信息

### 2. API Key 无效提示

**可能原因**：
- API key 格式错误
- API key 过期
- 权限不足

**解决方法**：
1. 重新检查 API key 格式
2. 在 Provider 官网验证 API key 是否有效
3. 确认 API key 有足够的权限

### 3. Mock 模式（未配置 API key）

如果前端未配置 API key，系统会自动使用 mock 模式：
- 返回预设的示例数据
- 不会调用真实的 LLM API
- 适合测试 UI 流程

## 最佳实践

### 开发环境

推荐使用**前端动态配置**：
- 快速切换不同的 provider
- 测试不同的 API keys
- 无需重启服务

### 生产环境

推荐使用**后端静态配置**：
- 配置集中管理
- 更安全（API keys 不会暴露在前端）
- 支持所有功能模块

### 团队协作

- 将 `.env.example` 提交到代码仓库
- 每个开发者创建自己的 `.env` 文件（添加到 `.gitignore`）
- 使用环境变量或密钥管理服务管理敏感信息

## 支持的 LLM Providers

| Provider | ID | 默认模型 | Base URL |
|----------|----|----------|-----------|
| Anthropic Claude | `claude` | claude-sonnet-4-6 | https://api.anthropic.com |
| OpenAI | `openai` | gpt-4o | https://api.openai.com/v1 |
| 阿里云 Qwen | `qwen` | qwen-plus | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| 智谱 GLM | `zhipu` | glm-4 | https://open.bigmodel.cn/api/paas/v4/ |
| Google Gemini | `gemini` | gemini-2.0-flash | https://generativelanguage.googleapis.com/v1beta/openai/ |

## 常见问题

### Q: 可以同时使用多个 provider 吗？

A: 可以。前端可以在设置页面切换 provider，后端支持所有配置的 provider。

### Q: API key 会保存到哪里？

A:
- 后端配置：保存在 `.env` 文件中
- 前端配置：保存在浏览器 localStorage 中

### Q: 如何使用中转服务？

A: 在前端设置页面的 "Base URL" 字段填写中转服务地址，或修改 `.env` 文件中的 `*_BASE_URL` 配置。

### Q: 为什么图片生成不能使用前端配置？

A: 图片生成使用的是独立的图片生成服务（如 SiliconFlow），不是 LLM 服务。目前需要在 `.env` 文件中配置 `SILICONFLOW_API_KEY`。

## 相关文件

- `app/core/config.py` - 配置管理
- `app/services/llm/factory.py` - LLM Provider Factory
- `app/routers/story.py` - Story API（支持前端配置）
- `app/routers/pipeline.py` - Pipeline API（支持前端配置）
- `frontend/src/stores/settings.js` - 前端设置 Store
- `frontend/src/views/SettingsView.vue` - 设置页面
