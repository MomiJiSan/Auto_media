# 主流程接入过渡视频说明

> 目标：基于项目当前实现，继续优化“过渡片段”接入主流程的设计文档。
> 当前结论：项目已经具备“首尾帧能力”和“链式连续性能力”，但还没有真正落地“运行时手动插入过渡视频”的完整链路。
> 当前迭代范围：先只落前端 UI 展示；后端接口、运行时资产结构、拼接逻辑本轮暂不实施。
> 推荐首期：先把交互入口和展示位置稳定下来，再进入后端接入。

---

## 1. 当前项目真实现状

这次优化文档时，需要先明确：项目不是“完全没有过渡基础能力”，而是“基础能力已具备，但主流程集成还没闭环”。

### 1.1 已有能力

当前后端已经具备以下基础：

1. `Shot` schema 已支持过渡相关字段
   - 文件：`app/schemas/storyboard.py`
   - 已有字段：
     - `image_prompt`
     - `final_video_prompt`
     - `last_frame_prompt`
     - `last_frame_url`
     - `transition_from_previous`

2. 图片生成层已支持尾帧图片生成
   - 文件：`app/services/image.py`
   - `generate_images_batch()` 在 shot 带有 `last_frame_prompt` 时，会额外生成 `${shot_id}_lastframe` 图片，并返回 `last_frame_url`

3. 视频生成层已支持双帧接口参数
   - 文件：`app/services/video.py`
   - `generate_video()` 和 `generate_videos_batch()` 已支持 `last_frame_url`

4. Provider 层已经区分“双帧支持”和“仅兼容字段”
   - `doubao`：真实支持首尾帧
   - `kling` / `minimax`：当前保留 `last_frame_url` 参数，但实际忽略
   - 这和现有文档 `docs/FIRST_LAST_FRAME_UPDATE_SUMMARY.md`、`docs/FIRST_LAST_FRAME_USAGE_GUIDE.md` 的结论一致

5. 主流程三种策略已经接入首尾帧相关字段
   - 文件：`app/services/pipeline_executor.py`
   - `separated` / `integrated`：会把图片阶段产出的 `last_frame_url` 继续传给视频生成阶段
   - `chained`：已经有“场景内串行生成 + 提取上一镜头最后一帧给下一镜头复用”的能力

### 1.2 现在还缺什么

当前项目真正缺的不是“首尾帧 API 能力”，而是以下主流程能力：

1. 没有独立的“过渡视频生成接口”
   - `app/routers/pipeline.py` 目前只有主流程、storyboard、concat 等接口
   - 没有 `transition generate` 之类的独立入口

2. 没有运行时过渡资产模型
   - `app/schemas/pipeline.py` 目前只有 `ShotResult`
   - 没有 `TransitionResult` / `TransitionRequest` 之类的结构

3. 前端没有“在两个镜头之间插入过渡片段”的交互
   - 文件：`frontend/src/views/VideoGeneration.vue`
   - 当前是逐个 shot 生成图片、视频，再整体拼接
   - 还没有“两个相邻 shot card 之间显示一个生成过渡按钮”的展示层

4. 拼接顺序还只认 shot 本身
   - 当前 `concatAllVideos()` 直接按 `shot_id` 排序后拼接
   - 还没有“shot + transition + shot”的统一顺序源

一句话总结：

当前系统已经有“镜头连续性增强能力”，但还没有“用户手动生成并插入过渡片段”的主流程闭环。

---

## 2. 这份文档要解决的问题

第一阶段不是去改 LLM，让它输出 `scene1_trans1`、`scene2_trans3` 这种完整过渡分镜。

完整方案的第一阶段原本要做的是：

1. 主镜头照旧由 storyboard 输出
2. 主流程照旧生成主镜头图片和视频
3. 当两个相邻主镜头视频都准备好后
4. 前端允许用户手动触发一次“过渡视频生成”
5. 后端基于：
   - 前镜头结尾状态
   - 后镜头开头状态
   - 可选补充 prompt
   生成一个独立过渡片段
6. 前端把这个片段插入两镜头之间展示和拼接

但就当前迭代来说，范围进一步收缩为：

1. 前端先展示相邻镜头之间的 transition slot
2. 只呈现“可生成 / 待就绪”的状态文案
3. 暂不发起后端请求
4. 暂不改动 concat / pipeline / schema

这样可以先验证 UI 位置、交互节奏和信息密度，再进入后端实现。

---

## 3. 和现有三种策略的关系

### 3.1 separated

当前路径：

```text
storyboard -> TTS -> image -> video -> ffmpeg stitch
```

特点：

- 已支持 `last_frame_prompt -> last_frame_url -> last_frame_url 传给视频层`
- 适合先落地“手动生成额外过渡片段”
- 因为每个 shot 的 image/video 资产都比较清晰，最容易在 UI 层中间插一个 transition

### 3.2 integrated

当前路径：

```text
storyboard -> image -> video
```

特点：

- 当前实现仍然是“先生成图片，再复用现有图生视频接口”
- 也支持 `last_frame_url`
- 但因为没有单独音频合成环节，过渡片段更适合作为“纯视频片段”插入

### 3.3 chained

当前路径：

```text
storyboard -> TTS -> scene 内串行视频生成 -> extract_last_frame -> 下一镜头复用
```

特点：

- `app/services/video.py` 中的 `generate_videos_chained()` 已经会：
  - 场景首镜头独立生图
  - 后续镜头复用上一镜头最后一帧
  - 对每个生成好的视频提取最后一帧
- 这解决的是“场景内镜头连续性”
- 它并不等于“独立过渡片段”

因此要明确区分：

- `chained`：让后一个主镜头更像前一个主镜头的延续
- `transition asset`：在两个主镜头之间额外插入一个可单独重试、可单独删除的片段

---

## 4. 第一阶段推荐方案

### 4.1 不改 storyboard 主结构

第一阶段不要要求 LLM 输出专门的过渡镜头。

保持现状即可：

- `Shot` 继续作为主镜头 schema
- `transition_from_previous` 继续只承担“叙事/视觉衔接说明”
- `last_frame_prompt` 继续只承担“结束状态控制”

原因：

1. 当前 `app/prompts/storyboard.py` 已经比较复杂
2. 项目已经在 `last_frame_prompt` 路径上有实现基础
3. 如果一上来就让 LLM 输出大量过渡镜头，会明显增加 shot 数量、TTS 数量、生成时长和 UI 复杂度

### 4.2 新增“运行时过渡资产”而不是“分镜内过渡镜头”

推荐把过渡视频定义为运行时新增资源，例如：

```json
{
  "transition_id": "transition_scene1_shot1__scene1_shot2",
  "from_shot_id": "scene1_shot1",
  "to_shot_id": "scene1_shot2",
  "prompt": "Smooth transition that carries pose, identity, clothing, lighting, and camera continuity into the next shot.",
  "video_url": "/media/videos/transition_scene1_shot1__scene1_shot2.mp4"
}
```

这样做的好处：

1. 不污染原始 storyboard
2. 可以单独失败、单独重试
3. 不影响已经生成完成的主镜头
4. 后续可以删除某个 transition，而不需要回滚整条 pipeline

---

## 5. 后端接入设计（本轮仅更新文档，不落代码）

### 5.1 后端

建议关注以下文件：

- `app/services/video.py`
- `app/services/ffmpeg.py`
- `app/routers/pipeline.py`
- `app/schemas/pipeline.py`

注意：

- 本节内容当前仅作为后续实现设计保留
- 本轮不新增接口
- 本轮不修改 schema
- 本轮不改 `video.py` / `pipeline.py` / `ffmpeg.py`

后续推荐增加的后端能力：

1. 请求结构

```python
class TransitionGenerateRequest(BaseModel):
    from_shot_id: str
    to_shot_id: str
    from_video_url: str
    to_image_url: str | None = None
    to_video_url: str | None = None
    transition_prompt: str | None = None
```

2. 返回结构

```python
class TransitionResult(BaseModel):
    transition_id: str
    from_shot_id: str
    to_shot_id: str
    prompt: str | None = None
    video_url: str
```

3. 独立服务方法

```python
async def generate_transition_video(...):
    ...
```

### 5.2 后续生成逻辑

等前端 UI 方案确认稳定后，第一版后端建议逻辑如下：

1. 把 `from_video_url` 转成本地文件路径
2. 从前一个视频提取最后一帧
3. 取后一个镜头的首帧图作为目标尾帧
   - 优先 `to_image_url`
   - 如果没有，再考虑从 `to_video_url` 提取第一帧
4. 如果 provider 支持双帧：
   - `first_frame = 前镜尾帧`
   - `last_frame = 后镜首帧`
5. 如果 provider 不支持双帧：
   - 退化为单帧 I2V
   - prompt 中保留“向下一镜头自然过渡”的描述

这里可以直接复用当前已有的 `extract_last_frame()` 能力，不需要先重构整条链式策略。

但这部分目前仍停留在设计层，不属于本轮改动。

### 5.3 后续 Provider 策略

基于当前真实实现，推荐写死以下判断：

```python
supports_dual_frame = video_provider == "doubao"
```

原因：

- 这是和项目当前 provider 实现一致的最稳方案
- `kling` / `minimax` 目前虽然接受 `last_frame_url` 参数，但实际不会按双帧模式工作
- 文档不应该对未实现能力做过度承诺

当前文档口径应明确为：

- `doubao` 是未来后端接入时的首选双帧 provider
- 但当前前端 UI 版不会真正调用任何 provider

---

## 6. 前端应该如何接入

主要修改文件：

- `frontend/src/views/VideoGeneration.vue`
- 如有需要，再补 `frontend/src/api/story.js`

### 6.1 当前前端实际情况

`VideoGeneration.vue` 当前已经支持：

1. 单个 shot 生成 TTS
2. 单个 shot 生成图片
3. 单个 shot 生成视频
4. 汇总所有 `shot.video_url` 进行拼接

但还没有：

1. 邻接镜头之间的插槽 UI
2. transition loading/error 状态
3. transition 结果缓存
4. 按“主镜头 + 过渡片段”输出最终拼接顺序

### 6.2 当前 UI 版建议

在两个相邻镜头之间增加一个轻量插槽：

```text
[scene1_shot1]
   ↓
[生成过渡视频]
   ↓
[scene1_shot2]
```

按钮显示条件：

1. 这两个 shot 在当前 storyboard 顺序中相邻
2. `fromShot.video_url` 已存在
3. `toShot.video_url` 已存在，或至少 `toShot.image_url` 已存在
4. 当前这对 shot 之间还没有 transition 结果

当前按钮点击后：

1. 仅显示“后端暂未接入”的提示
2. 不发起 transition generate 请求
3. 不写入 transition 结果
4. 只保留后续真实接入的位置感和状态感

### 6.3 拼接逻辑要改

当前 `concatAllVideos()` 是：

```text
shots.filter(video_url).sort(shot_id)
```

这对 transition 来说不够。

完整接入后应该改成：

1. 以 storyboard 原始 shot 顺序为准
2. 遍历 shot 列表
3. 每输出一个主 shot 后，检查它和下一个 shot 之间是否存在 transition
4. 如果存在，把 transition 的 `video_url` 插进去
5. 最后把这个线性列表传给 concat 接口

也就是说，最终拼接顺序来源不应该只是 `shot_id` 排序，而应该是“显示顺序”。

但当前前端 UI 版暂不修改拼接逻辑，仍保持现状。

---

## 7. 当前时序与后续时序

```text
当前时序：
Step 1: storyboard 只生成主镜头
Step 2: 主流程照常生成主镜头 image/video
Step 3: 前端检查相邻镜头是否满足展示条件
Step 4: 在两个主镜头之间显示 transition slot
Step 5: 用户点击按钮时，仅提示“后端暂未接入”

后续完整时序：
Step 6: 新增 transition generate 接口
Step 7: 后端提取前镜尾帧，并获取后镜首帧
Step 8: 调用视频 provider 生成独立过渡片段
Step 9: 前端将 transition card 插入两个主镜头之间
Step 10: concat 时按显示顺序拼接主镜头和 transition 片段
```

---

## 8. 第一阶段最小实现清单

如果目标是“和当前代码改动保持一致”，本轮范围应控制在以下几项：

1. 前端在相邻 shot card 之间显示 transition slot
2. 根据前后镜头素材状态显示“可生成 / 待就绪”
3. 点击按钮仅提示“后端暂未接入”
4. 不新增后端接口
5. 不新增运行时 transition schema
6. 不修改 concat 排序逻辑
7. 保留后端设计说明，等待下一阶段实现

这 7 项做完，就是一个边界清晰的 UI 预演版本。

---

## 9. 验收标准

当前这版文档对应的验收标准，至少要满足：

1. 现有 storyboard 输出不被破坏
2. `separated` / `integrated` / `chained` 三种主镜头生成路径不受影响
3. 相邻镜头之间可以展示 transition slot
4. slot 能根据前后镜头素材状态显示不同文案
5. 点击按钮不会触发真实后端请求
6. 现有视频生成与导出逻辑保持不变
7. 后端设计在文档中保留，但不会被误读为“本轮已实现”

---

## 10. 明确不建议的做法

当前阶段不建议：

1. 直接把 LLM 自动过渡分镜作为第一阶段
2. 把 `transition_from_previous` 误当成独立 transition asset
3. 把 `chained` 的“连续性增强”误写成“已经支持独立过渡片段”
4. 在所有 provider 上宣称都支持双帧过渡
5. 在文档里把后端设计写成“已经进入当前开发范围”
6. 继续沿用“纯 `shot_id` 排序后拼接”的逻辑来处理未来的 transition，但又不在文档里标注这是后续项

---

## 11. 推荐结论

结合当前项目代码，最合理的文档结论应该是：

1. 项目已经具备首尾帧和链式连续性基础能力
2. 当前完整缺口仍然是“运行时过渡片段”的接口、状态、展示和排序
3. 但本轮只推进前端 UI 展示，不推进后端实现
4. 后端部分只保留设计说明，等待下一阶段接入
5. 后续真正落后端时，优先只对 `doubao` 开启双帧过渡，其他 provider 做兼容降级

这样文档范围和当前代码状态是一致的，不会造成“文档已承诺、代码未进入”的落差。

---

## 12. 与 DSPy / Generative Feedback Loops 的关系

后续如果项目引入 DSPy 和 Generative Feedback Loops，这份过渡方案的口径建议保持一致：

1. `transition asset` 不单独发明第三套角色一致性逻辑，继续复用 `StoryContext` / `build_generation_payload()` 的统一角色锁与负面约束
2. 过渡片段的首尾状态描述，仍优先来自已有的 `last_frame_prompt`、相邻 shot 首帧/尾帧资产，以及运行时补充 prompt，而不是把更多负担压回 storyboard
3. 如果后续接入 VLM 质检，transition 应只做“关键过渡抽检”，例如人物是否接上、服装是否延续、镜头方向是否冲突，不建议默认对每段过渡都全量重试
4. 如果后续用 DSPy 结构化提取 `CharacterLock`，transition 生成也只消费结构化结果，不应再次拼接旧式 portrait prompt 大段文本

换句话说，transition 方案应该成为主生成链路的一部分，而不是 DSPy / 反馈闭环之外的旁路系统。
