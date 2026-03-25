# DSPy 与 Generative Feedback Loops 接入方案

> 目标：在不推翻现有生成链路的前提下，为项目引入“声明式结构化提取 + 生成后质检闭环”能力。
> 适用范围：`StoryContext`、`PipelineExecutor`、图片/视频生成链路，以及相关设计文档。
> 当前状态：截至 2026-03-25，项目已具备统一 payload 组装基础，但尚未真正接入 DSPy 和 VLM 反馈闭环。

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
     - `character_images[name]["visual_dna"]`
     - 启发式回退 `_guess_body_features()` / `_guess_default_clothing()`
   - 这套方案可运行，但不同底层模型下稳定性有限

2. 生成链路仍然是“一次生成直出”
   - 图片生成后没有自动检查是否符合角色锁
   - 视频生成后没有自动检查动作完成度、尾帧状态、角色一致性
   - 出错时只能手动重试，缺少闭环

因此后续最合理的演进方向是：

- 用 DSPy 替代“长字符串提示词提取器”
- 用 Generative Feedback Loops 替代“完全盲生成”

---

## 2. 总体架构定位

建议把这次升级明确分成两层：

### 2.1 结构化提取层

目标：

- 从角色描述中稳定提取 `CharacterLock`
- 让输出格式受约束，而不是依赖 prompt 运气

建议挂载点：

- `app/core/story_context.py`

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

### 3.2 不建议再新增的新中心

这次改造不建议：

- 再造一个新的 prompt builder 模块
- 把 DSPy 逻辑塞进 router
- 把 VLM 质检散落到 provider 实现里
- 为 transition、manual mode、auto mode 各写一套不同一致性规则

推荐保持两个稳定中心：

1. `story_context.py`
2. `pipeline_executor.py`

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


class ExtractCharacterLock(dspy.Signature):
    """Extract structured physical appearance for image generation."""

    character_name = dspy.InputField()
    character_description = dspy.InputField()
    output: CharacterAppearance = dspy.OutputField()
```

映射关系：

- `output.body -> CharacterLock.body_features`
- `output.clothing -> CharacterLock.default_clothing`

### 4.2 模块形态

```python
class AppearanceModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extractor = dspy.TypedPredictor(ExtractCharacterLock)

    def forward(self, name: str, description: str):
        return self.extractor(
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

### 4.4 写入位置

建议保持当前缓存口径不变：

```python
Story.meta["character_appearance_cache"][character_name] = {
    "body": "...",
    "clothing": "...",
    "negative_prompt": "...",
    "source": "dspy_compiled_v1",
}
```

这样有几个好处：

- 不破坏现有 `StoryContext` 的消费方式
- 旧逻辑可以继续回退
- 文档与数据库口径更统一

### 4.5 回退策略

如果 DSPy 不可用，保留当前顺序回退：

1. `meta["character_appearance_cache"]`
2. `character_images[name]["visual_dna"]`
3. `_guess_body_features()` / `_guess_default_clothing()`

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

### 5.5 重试原则

建议限制：

- 单镜头最多 1-2 次重试
- 只重试当前镜头
- 失败后保留最后结果并标记人工复核

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

### Phase 2：接入 DSPy

- 新增 DSPy 提取模块
- 构建黄金样本集
- 离线编译并导出
- 在 `build_story_context()` 中消费编译结果

### Phase 3：接入反馈闭环

- 增加图片质检
- 增加视频质检
- 加入重试控制与人工复核标记

### Phase 4：推广到全部入口

需要覆盖：

- 自动一键生成
- 手动批量素材生成
- 手动单镜头图片生成
- 手动单镜头视频生成
- 后续 transition 资产生成

否则会出现自动模式和手动模式行为不一致的问题。

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

## 10. 推荐结论

对当前项目来说，最稳的落地方式不是大改，而是增量演进：

1. 保持 `StoryContext` 作为统一一致性入口
2. 用 DSPy 替代角色外貌提取中的长 prompt 与启发式主路径
3. 用 VLM 反馈闭环替代“一次生成直出”
4. 只对关键镜头和抽检镜头启用闭环
5. 始终保证 auto / manual / transition 三条链路复用同一套规则

这样升级后的系统会从“字符串驱动的 prompt 工程”逐步变成“结构化约束 + 可验证反馈”的生成系统。
