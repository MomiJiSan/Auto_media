# DSPy 与 Generative Feedback Loops 接入实施方案

> 目标：在不推翻现有生成链路的前提下，为项目引入“声明式结构化提取 + 生成后质检闭环”能力。
> 适用范围：`StoryContext`、`PipelineExecutor`、图片/视频生成链路，以及相关设计文档。
> 当前状态：截至 2026-03-26，项目已具备统一 payload 组装基础，但尚未真正接入 DSPy 和 VLM 反馈闭环。
> 实施口径：本文为后续开发主文档，优先定义数据契约、挂载边界、阶段验收与回滚方式，避免不同实现者各自理解。

## 先看这里

如果只想先快速理解这份方案，先记住下面 6 点：

1. 这次改造分成两层：
   - DSPy 负责把角色描述提取成结构化外貌缓存
   - Feedback Loop 负责在图片/视频生成后做检查、反馈、局部重试

2. 三个核心落点固定不变：
   - `app/services/story_context_service.py`：提取并写回外貌缓存
   - `app/core/story_context.py`：消费缓存并组装运行时 payload
   - `app/services/pipeline_executor.py`：执行检查、重试和人工复核标记

3. 角色外貌主数据源统一为：
   - `story.meta["character_appearance_cache"][character_id]`
   - `character_images[character_id]["visual_dna"]` 只保留为兼容投影字段

4. Feedback Loop 不允许直接重写主 prompt：
   - 只允许通过 `shot.extra_instructions` 追加局部纠错指令
   - 只重试当前 shot，不回滚整条 pipeline

5. 默认不做全量强检：
   - 只对关键镜头必检
   - 普通镜头按抽检策略执行
   - 成本控制和重试次数都由统一配置控制

6. 实施顺序固定为：
   - 先固化 schema 与测试
   - 再接 DSPy 提取
   - 再接 feedback loop
   - 最后推广到 auto / manual / transition 全部入口

一句话概括：先把“角色一致性”变成结构化缓存，再把“生成质量”变成可检查、可局部纠错的闭环，而不是继续堆字符串 prompt。

---

## 1. 为什么要单独引入这两层能力

当前项目已经从“纯字符串 prompt 拼接”演进到：

- `app/core/story_context.py` 负责统一构建 `StoryContext`
- `build_generation_payload()` 统一产出 `image_prompt` / `final_video_prompt` / `last_frame_prompt` / `negative_prompt`
- `PipelineExecutor`、`image.py`、`video.py` 已开始围绕统一 payload 工作

但还有两个明显缺口：

1. 角色外貌提取仍不够声明式
   - 当前主要依赖：
     - `Story.meta["character_appearance_cache"]`
     - `character_images[character_id]["visual_dna"]`
     - 启发式回退 `_guess_body_features()` / `_guess_default_clothing()`
   - 这套方案可运行，但不同底层模型下稳定性有限

2. 生成链路仍然是“一次生成直出”
   - 图片生成后没有自动检查是否符合角色锁
   - 视频生成后没有自动检查动作完成度、尾帧状态、角色一致性
   - 出错时只能手动重试，缺少闭环

因此后续最合理的演进方向是：

- 用 DSPy 替代“长字符串提示词提取器”
- 用 Generative Feedback Loops 替代“完全盲生成”

## 1.1 本阶段明确目标

本阶段只做以下四件事：

1. 固化角色外貌结构化提取契约
2. 固化反馈闭环挂载点与重试边界
3. 固化运行期配置与日志字段
4. 固化 auto / manual / transition 三类入口的统一复用方式

## 1.2 本阶段明确非目标

本阶段不做：

- 新增独立数据库表
- 新增前端工作流
- 全量镜头默认 VLM 强检
- provider 内部自行发展独立反馈逻辑
- 按不同视角选择不同角色图资产的复杂路由

---

## 2. 总体架构定位

建议把这次升级明确分成两层：

### 2.1 结构化提取层

目标：

- 从角色描述中稳定提取 `CharacterLock`
- 让输出格式受约束，而不是依赖 prompt 运气

建议挂载点：

- `app/services/story_context_service.py`

建议职责：

- 读取 `story.characters`
- 调用 DSPy 提取结构化外貌
- 写回 `Story.meta["character_appearance_cache"]`
- 构建运行时 `StoryContext.character_locks`

### 2.2 生成后反馈层

目标：

- 在图片/视频生成之后，自动检查是否满足关键约束
- 不满足则增强 prompt 并有限次重试

建议挂载点：

- `app/services/pipeline_executor.py`

建议职责：

- 在图片生成节点插入 VLM 质检
- 在视频生成节点插入 VLM 质检
- 只在关键镜头或抽检镜头启用
- 不通过时仅重试当前 shot，不回滚整个 pipeline

---

## 3. 与当前代码的边界关系

### 3.1 已经可以复用的基础

当前仓库里，下面这些能力已经足够作为新方案的落点：

- `build_story_context()`：统一汇总角色锁、风格、负面约束
- `build_generation_payload()`：统一生成图片/视频 payload
- `build_image_generation_prompt()` / `build_video_generation_prompt()` / `build_last_frame_generation_prompt()`：已完成分字段 prompt 组装
- `PipelineExecutor`：已经是自动生成主链路的稳定编排点
- `last_frame_prompt` / `last_frame_url`：已具备过渡和终态控制基础

实施时，下面这些文件应作为唯一主落点：

- `app/services/story_context_service.py`
- `app/core/story_context.py`
- `app/services/pipeline_executor.py`

### 3.2 不建议再新增的新中心

这次改造不建议：

- 再造一个新的 prompt builder 模块
- 把 DSPy 逻辑塞进 router
- 把 VLM 质检散落到 provider 实现里
- 为 transition、manual mode、auto mode 各写一套不同一致性规则

推荐保持两个稳定中心：

1. `story_context.py`
2. `pipeline_executor.py`

### 3.3 具体职责划分

`app/services/story_context_service.py`

- 负责调用 DSPy 提取器或其编译结果
- 负责把结构化外貌缓存写回 `story.meta["character_appearance_cache"][character_id]`
- 负责把 `body` 兼容投影回 `character_images[character_id]["visual_dna"]`
- 不负责运行时 prompt 拼装

`app/core/story_context.py`

- 负责定义 `CharacterLock` 与 `StoryContext`
- 负责从缓存、投影字段、描述回退中组装运行时一致性数据
- 负责把 `extra_instructions` 合并进最终 payload
- 不负责数据库写入，不负责重试循环

`app/services/pipeline_executor.py`

- 负责在图片和视频节点插入检查
- 负责控制是否重试、最多重试几次、是否标记人工复核
- 负责记录单 shot 的反馈状态
- 不负责定义新的 prompt builder 或角色缓存 schema

### 3.4 明确禁止事项

实施时不允许：

- 在 router 中直接调用 DSPy 提取器
- 在 provider 内部偷偷加检查与重试循环
- 为手动、自动、transition 三条链路分别维护三套规则
- 让 feedback 直接重写 `image_prompt` / `final_video_prompt` / `last_frame_prompt` 主体

---

## 4. DSPy 接入方案

### 4.1 目标数据结构

当前项目运行时结构：

```python
@dataclass
class CharacterLock:
    body_features: str = ""
    default_clothing: str = ""
    negative_prompt: str = ""
```

建议 DSPy 输出结构保持一一对应：

```python
import dspy
from pydantic import BaseModel, Field


class CharacterAppearance(BaseModel):
    body: str = Field(description="immutable traits: age, hair, eyes, build. Max 25 words.")
    clothing: str = Field(description="default outfit description. Max 15 words.")
    negative_prompt: str = Field(default="", description="optional contamination exclusions. Max 12 words.")


class ExtractCharacterLock(dspy.Signature):
    """Extract structured physical appearance for image generation."""

    character_id = dspy.InputField()
    character_name = dspy.InputField()
    character_description = dspy.InputField()
    output: CharacterAppearance = dspy.OutputField()
```

映射关系：

- `output.body -> CharacterLock.body_features`
- `output.clothing -> CharacterLock.default_clothing`
- `output.negative_prompt -> CharacterLock.negative_prompt`

### 4.1.1 标准输入输出契约

实施时统一使用以下输入：

```json
{
  "character_id": "char_li_ming",
  "character_name": "李明",
  "role": "主角",
  "description": "25岁青年男子，黑色短发，身形清瘦，穿着深蓝长衫。"
}
```

统一要求 DSPy 或等价提取器返回：

```json
{
  "characters": [
    {
      "id": "char_li_ming",
      "body": "young man, short black hair, slim build",
      "clothing": "dark blue robe",
      "negative_prompt": "modern clothing"
    }
  ]
}
```

硬约束：

- `characters` 必须是数组
- 主键统一用 `id`
- 不再使用按角色名 keyed object
- `body` 只保留稳定体貌
- `clothing` 只保留默认服装
- `negative_prompt` 只保留污染排除词

### 4.2 模块形态

```python
class AppearanceModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extractor = dspy.TypedPredictor(ExtractCharacterLock)

    def forward(self, character_id: str, name: str, description: str):
        return self.extractor(
            character_id=character_id,
            character_name=name,
            character_description=description,
        )
```

### 4.3 运行策略

建议分成两种环境：

1. 开发/离线环境
   - 用黄金样本集编译 DSPy 模块
   - 导出编译结果到 JSON 或等价配置文件

2. 生产环境
   - 只加载编译结果
   - 不在 FastAPI 请求链路里实时 compile

补充约束：

- 不允许在 FastAPI 请求链路中临时 compile
- 不允许在不同 provider 下使用不同 schema
- DSPy 不可用时只回退实现，不回退数据契约

### 4.4 写入位置

建议保持当前缓存口径不变：

```python
Story.meta["character_appearance_cache"][character_id] = {
    "body": "...",
    "clothing": "...",
    "negative_prompt": "...",
    "source": "dspy_compiled_v1",
    "schema_version": "appearance_cache_v1",
    "updated_at": "2026-03-26T12:00:00Z",
}
```

这样有几个好处：

- 不破坏现有 `StoryContext` 的消费方式
- 运行时可按既定回退顺序降级
- 文档与数据库口径更统一

补充要求：

- `source` 用于区分 `heuristic`、`llm_prompt`、`dspy_compiled_v1`
- `schema_version` 用于后续 schema 升级
- `updated_at` 用于调试和缓存新鲜度判断
- `character_images[character_id]["visual_dna"]` 仅作为兼容投影字段保留，且只投影 `body`

### 4.5 回退策略

如果 DSPy 不可用，保留当前顺序回退：

1. `meta["character_appearance_cache"][character_id]`
2. `character_images[character_id]["visual_dna"]`
3. `_guess_body_features()` / `_guess_default_clothing()`

注意：

- 运行时允许回退
- 新写缓存不允许回退到旧 schema
- 新写入统一保持 `character_id + appearance_cache_v1`

---

## 5. Generative Feedback Loops 接入方案

### 5.1 目标

生成不是一次性“盲投”，而是：

1. 生成
2. 检查
3. 反馈
4. 局部重试

### 5.2 建议流程

```python
async def generate_with_feedback(shot, context, max_retries=2):
    last_result = None

    for attempt in range(max_retries + 1):
        payload = build_generation_payload(shot, context)

        image_result = await image_service.generate_image(
            visual_prompt=payload["image_prompt"],
            negative_prompt=payload.get("negative_prompt", ""),
        )
        last_result = image_result

        judge = await vlm_service.check_image_consistency(
            image_url=image_result["image_url"],
            expected_character_lock=context.character_locks,
            shot=shot,
        )

        if judge["passed"]:
            return image_result

        shot.extra_instructions = judge["feedback"]

    return last_result
```

这段伪代码在实际实现时必须满足：

- 每次重试前重新调用 `build_generation_payload()`
- `shot.extra_instructions` 采用覆盖式更新，不做无限拼接
- 每次尝试记录 `attempt`、`issue_codes`、`feedback_summary`
- `judge["should_retry"]` 只是建议，最终是否重试由 `PipelineExecutor` 决定

### 5.2.1 Judge 输出契约

图片和视频检查器统一返回以下结构：

```json
{
  "passed": false,
  "score": 0.62,
  "issues": [
    {
      "code": "character_clothing_drift",
      "severity": "high",
      "message": "Main character is missing the dark blue robe."
    }
  ],
  "feedback": "CRITICAL FIX: restore the same dark blue robe and keep single-subject composition.",
  "should_retry": true
}
```

推荐问题码枚举：

- `character_identity_mismatch`
- `character_clothing_drift`
- `character_count_error`
- `scene_anchor_missing`
- `action_incomplete`
- `last_frame_state_mismatch`
- `orientation_conflict`

### 5.3 两个检查点

#### A. 图片生成后检查

建议检查：

- 主角色是否正确
- 服装是否延续
- 主体数量是否异常
- 关键环境锚点是否存在

#### B. 视频生成后检查

建议检查：

- 起始状态是否接上首帧
- 动作是否完成
- 角色外貌是否漂移
- `last_frame_prompt` 对应终态是否到位

### 5.4 反馈写回方式

不建议直接重写原 prompt 主体内容。

建议采用“增量纠错”的方式：

```python
shot.extra_instructions = (
    "CRITICAL FIX: maintain same hairstyle and clothing; "
    "subject count must remain one; final pose must match target ending state."
)
```

后续由 `build_generation_payload()` 在末尾合并：

- 原始 shot prompt
- CharacterLock
- scene style
- negative prompt
- retry feedback

建议 runtime 字段统一挂在 shot 上，但不持久化到剧本文本主体：

```python
shot.extra_instructions: str
shot.feedback_attempt: int
shot.feedback_issues: list[dict]
```

### 5.5 重试原则

建议限制：

- 单镜头最多 1-2 次重试
- 只重试当前镜头
- 失败后保留最后结果并标记人工复核

停止条件：

- `judge["passed"] is True`
- 达到 `max_retries`
- `judge["should_retry"] is False`
- 连续两次命中不可自动修复类问题，例如角色身份错误

---

## 6. 抽检策略与成本控制

反馈闭环绝对不要默认全量开。

建议策略：

### 必检

- 新角色首次登场
- 大跨度换装
- 关键情绪特写
- 依赖 `last_frame_prompt` 的过渡镜头

### 抽检

- 同场景连续镜头每 3-5 镜抽检一次

### 可跳过

- 同构重复镜头
- 成本敏感的低优先级草稿生成

推荐把这块做成配置项，例如：

```python
FeedbackPolicy(
    enable_image_check=True,
    enable_video_check=True,
    sample_every_n_shots=4,
    max_retries=2,
    image_pass_threshold=0.75,
    video_pass_threshold=0.75,
    required_issue_codes_for_retry={"character_clothing_drift", "action_incomplete"},
)
```

### 6.1 配置统一要求

这类配置后续不要散落在函数参数中，建议集中为单一配置结构，例如：

```python
ConsistencyConfig(
    enable_dspy_extractor=True,
    enable_feedback_loop=True,
    appearance_cache_schema_version="appearance_cache_v1",
    feedback_policy=FeedbackPolicy(...),
    judge_provider="openai",
    judge_model="gpt-4.1-mini",
)
```

---

## 7. 对现有文档的影响范围

后续如果正式推进，建议统一在文档中补充以下两项：

### 7.1 提示词工程演进

建议统一表述为：

- 角色外貌提取从硬编码 prompt 演进到 DSPy `TypedPredictor`
- `CharacterLock` 成为统一结构化契约
- 编译结果在离线环境生成，在生产环境加载

### 7.2 闭环纠错逻辑

建议统一表述为：

- 在 `PipelineExecutor` 的图片/视频节点增加 VLM 检查点
- 失败后把反馈回写为局部纠错指令
- 对关键镜头执行必检，对普通镜头执行抽检

---

## 8. 分阶段实施建议

### Phase 1：接口与数据契约稳定

- 固化 `CharacterLock` 数据结构
- 给 `Story.meta["character_appearance_cache"]` 补统一 schema
- 让 `build_generation_payload()` 支持合并 `extra_instructions`

完成标准：

- 新的 `appearance_cache_v1` schema 已落地
- 相关单元测试覆盖 `character_id` 主键与 `extra_instructions` 合并
- 文档口径全部统一到 `character_id`

### Phase 2：接入 DSPy

- 新增 DSPy 提取模块
- 构建黄金样本集
- 离线编译并导出
- 在 `build_story_context()` 中消费编译结果

完成标准：

- 在不开 feedback loop 时，DSPy 可以稳定写入结构化外貌缓存
- DSPy 不可用时可回退到现有 heuristic 主路径
- 生产环境无实时 compile

### Phase 3：接入反馈闭环

- 增加图片质检
- 增加视频质检
- 加入重试控制与人工复核标记

完成标准：

- 单镜头可独立检查和局部重试
- 失败后有可读 issue code 与人工复核标记
- 关闭 feedback 时不影响基础链路

### Phase 4：推广到全部入口

需要覆盖：

- 自动一键生成
- 手动批量素材生成
- 手动单镜头图片生成
- 手动单镜头视频生成
- 后续 transition 资产生成

否则会出现自动模式和手动模式行为不一致的问题。

完成标准：

- auto / manual / transition 三类入口共用同一套 `FeedbackPolicy`
- 不存在单个入口自行维护独立纠错 prompt 的情况

---

## 9. 风险与注意事项

### 9.1 不要实时编译 DSPy

这是最容易踩的坑。

编译过程会明显增加 token 消耗和时延，应只在开发环境离线完成。

### 9.2 不要把反馈闭环做成全量强依赖

如果每个镜头都先生成再检查再重试，成本和耗时会快速失控。

### 9.3 不要让反馈器直接替代生成器

VLM 反馈的职责是指出偏差，不是重写整条 prompt。

### 9.4 不要制造旁路系统

DSPy 和反馈闭环应接在已有 `StoryContext` / `PipelineExecutor` 边界上，而不是形成第四套生成逻辑。

---

## 10. 验收标准

### 10.1 数据契约验收

- `character_appearance_cache` 主键统一为 `character_id`
- `source` 与 `schema_version` 字段存在
- `visual_dna` 只作为兼容投影字段保留

### 10.2 功能验收

- 角色首次登场镜头可稳定注入结构化外貌锁
- 含 `last_frame_prompt` 的镜头可以执行终态检查
- feedback 失败不会回滚整条 pipeline

### 10.3 成本验收

- 默认配置下不是全量镜头检查
- 单镜头重试次数受控
- 关闭 feedback 后，主链路耗时与成本无显著上升

### 10.4 可观测性验收

- 可看到每个 shot 是否被检查
- 可看到问题码、是否 retry、是否人工复核

---

## 11. 可观测性与日志要求

最低建议日志字段：

- `story_id`
- `pipeline_id`
- `shot_id`
- `feedback_enabled`
- `feedback_attempt`
- `judge_passed`
- `judge_score`
- `issue_codes`
- `retry_applied`
- `final_review_required`

建议日志打点位置：

- DSPy 提取成功或回退时
- 图片检查前后
- 视频检查前后
- retry 应用前后

---

## 12. 回滚策略

若上线后出现质量或成本问题，按以下顺序回滚：

1. 先关闭 feedback loop，只保留 DSPy 提取
2. 若 DSPy 提取质量不稳，再切回当前 heuristic 提取主路径
3. 保留新的 schema 与日志字段，不回退数据库口径

---

## 13. 推荐结论

对当前项目来说，最稳的落地方式不是大改，而是增量演进：

1. 保持 `StoryContext` 作为统一一致性入口
2. 用 DSPy 替代角色外貌提取中的长 prompt 与启发式主路径
3. 用 VLM 反馈闭环替代“一次生成直出”
4. 只对关键镜头和抽检镜头启用闭环
5. 始终保证 auto / manual / transition 三条链路复用同一套规则

这样升级后的系统会从“字符串驱动的 prompt 工程”逐步变成“结构化约束 + 可验证反馈”的生成系统。
