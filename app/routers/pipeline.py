from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
from app.schemas.pipeline import (
    PipelineStatusResponse,
    PipelineStatus,
    AutoGenerateRequest,
    AutoGenerateResponse,
    GenerationStrategy,
    StoryboardRequest,
)
from app.schemas.storyboard import Storyboard
from app.services.storyboard import parse_script_to_storyboard
from app.services.pipeline_executor import PipelineExecutor

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

# 全局流水线状态存储
_pipeline: dict = {}


def _get_or_create(project_id: str) -> dict:
    """获取或创建流水线状态"""
    if project_id not in _pipeline:
        _pipeline[project_id] = {
            "status": PipelineStatus.PENDING,
            "progress": 0,
            "current_step": "等待开始",
            "error": None,
            "progress_detail": None,
            "generated_files": None,
        }
    return _pipeline[project_id]


@router.post("/{project_id}/auto-generate", response_model=AutoGenerateResponse)
async def auto_generate(
    project_id: str,
    req: AutoGenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    一键生成完整视频 - 自动执行全流程

    支持两种策略：
    - separated: TTS → 图片 → 图生视频 → FFmpeg 合成
    - integrated: 图片 → 视频语音一体生成
    """
    state = _get_or_create(project_id)

    # 重置状态
    state.update(
        status=PipelineStatus.PENDING,
        progress=0,
        current_step="准备开始",
        error=None,
        progress_detail=None,
        generated_files=None,
    )

    async def _run_pipeline():
        """后台执行流水线"""
        executor = PipelineExecutor(project_id, state)
        await executor.run_full_pipeline(
            script=req.script,
            strategy=req.strategy,
            provider=req.provider,
            model=req.model,
            voice=req.voice,
            image_model=req.image_model,
            video_model=req.video_model,
            base_url=req.base_url,
        )

    background_tasks.add_task(_run_pipeline)

    return AutoGenerateResponse(
        project_id=project_id,
        message=f"自动化流水线已启动（策略：{req.strategy.value}）",
        strategy=req.strategy,
    )


@router.post("/{project_id}/storyboard", response_model=Storyboard)
async def generate_storyboard(
    project_id: str,
    request: StoryboardRequest = Body(...),
):
    """手动触发：分镜解析"""
    state = _get_or_create(project_id)
    state.update(status=PipelineStatus.STORYBOARD, progress=10, current_step="解析分镜中")

    try:
        shots, usage = await parse_script_to_storyboard(
            request.script,
            provider=request.provider or "claude",
            model=request.model
        )
    except Exception as e:
        state.update(status=PipelineStatus.FAILED, error=str(e))
        raise HTTPException(status_code=500, detail=f"分镜解析失败: {e}") from e

    state.update(progress=30, current_step="分镜解析完成")
    return Storyboard(
        shots=shots,
        usage={
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
    )


@router.post("/{project_id}/generate-assets")
async def generate_assets(
    project_id: str,
    storyboard: Storyboard,
    voice: str = Query("zh-CN-XiaoxiaoNeural", description="TTS 语音"),
    image_model: str = Query("black-forest-labs/FLUX.1-schnell", description="图片生成模型"),
    background_tasks: BackgroundTasks = None,
):
    """
    手动触发：生成 TTS 和图片资产

    参数：
    - storyboard: 分镜数据（从 storyboard 接口获取）
    - voice: TTS 语音（默认：晓晓）
    - image_model: 图片生成模型（默认：FLUX.1-schnell）
    """
    from app.services import tts, image

    state = _get_or_create(project_id)
    state.update(
        status=PipelineStatus.GENERATING_ASSETS,
        progress=30,
        current_step="生成 TTS 和图片中",
    )

    shots = storyboard.shots
    total = len(shots)

    async def _generate():
        """后台生成任务"""
        try:
            # TTS
            state["progress_detail"] = {"step": "tts", "current": 0, "total": total, "message": "生成语音..."}
            tts_results = await tts.generate_tts_batch(
                shots=[{"shot_id": s.shot_id, "dialogue": s.dialogue} for s in shots],
                voice=voice,
            )

            # 图片
            state["progress_detail"] = {"step": "image", "current": 0, "total": total, "message": "生成图片..."}
            image_results = await image.generate_images_batch(
                shots=[{"shot_id": s.shot_id, "visual_prompt": s.visual_prompt} for s in shots],
                model=image_model,
            )

            # 保存结果
            state.update(
                progress=60,
                current_step=f"资产生成完成（TTS: {len(tts_results)}, 图片: {len(image_results)}）",
                generated_files={
                    "tts": {r["shot_id"]: r for r in tts_results},
                    "images": {r["shot_id"]: r for r in image_results},
                },
            )
        except Exception as e:
            state.update(status=PipelineStatus.FAILED, error=str(e))

    if background_tasks:
        background_tasks.add_task(_generate)
        return {"project_id": project_id, "message": "资产生成任务已启动"}
    else:
        await _generate()
        return {"project_id": project_id, "message": "资产生成完成", "state": state}


@router.post("/{project_id}/render-video")
async def render_video(
    project_id: str,
    shots_data: list[dict],
    base_url: str = Query("http://localhost:8000", description="服务器地址"),
    video_model: str = Query("wan2.6-i2v-flash", description="视频生成模型"),
    background_tasks: BackgroundTasks = None,
):
    """
    手动触发：图生视频

    参数：
    - shots_data: 镜头数据列表，每个包含 shot_id, image_url, visual_prompt, camera_motion
    - base_url: 服务器地址（用于拼接本地图片 URL）
    - video_model: 视频生成模型（默认：wan2.6-i2v-flash）
    """
    from app.services import video

    state = _get_or_create(project_id)
    state.update(
        status=PipelineStatus.RENDERING_VIDEO,
        progress=65,
        current_step="图生视频中",
    )

    async def _render():
        """后台渲染任务"""
        try:
            total = len(shots_data)
            state["progress_detail"] = {"step": "video", "current": 0, "total": total, "message": "生成视频..."}

            video_results = await video.generate_videos_batch(
                shots=shots_data,
                base_url=base_url,
                model=video_model,
            )

            state.update(
                progress=85,
                current_step=f"视频渲染完成（{len(video_results)} 个）",
                generated_files={"videos": {r["shot_id"]: r for r in video_results}},
            )
        except Exception as e:
            state.update(status=PipelineStatus.FAILED, error=str(e))

    if background_tasks:
        background_tasks.add_task(_render)
        return {"project_id": project_id, "message": "视频渲染任务已启动"}
    else:
        await _render()
        return {"project_id": project_id, "message": "视频渲染完成", "state": state}


@router.get("/{project_id}/status", response_model=PipelineStatusResponse)
async def get_status(project_id: str):
    """获取流水线状态"""
    state = _get_or_create(project_id)
    return PipelineStatusResponse(
        project_id=project_id,
        status=state["status"],
        progress=state["progress"],
        current_step=state["current_step"],
        error=state.get("error"),
        progress_detail=state.get("progress_detail"),
        generated_files=state.get("generated_files"),
    )


@router.post("/{project_id}/stitch")
async def stitch_video(
    project_id: str,
    shots_data: list[dict],
    background_tasks: BackgroundTasks = None,
):
    """
    手动触发：FFmpeg 合成音视频

    参数：
    - shots_data: 镜头数据列表，每个包含 shot_id, video_url, audio_url（可选）
    """
    state = _get_or_create(project_id)
    state.update(status=PipelineStatus.STITCHING, progress=90, current_step="FFmpeg 合成中")

    async def _stitch():
        """后台合成任务"""
        try:
            # TODO: 实现真实的 FFmpeg 合成逻辑
            # 目前先模拟
            import asyncio
            await asyncio.sleep(2)

            state.update(
                status=PipelineStatus.COMPLETE,
                progress=100,
                current_step="视频合成完成",
            )
        except Exception as e:
            state.update(status=PipelineStatus.FAILED, error=str(e))

    if background_tasks:
        background_tasks.add_task(_stitch)
        return {"project_id": project_id, "message": "视频合成任务已启动"}
    else:
        await _stitch()
        return {"project_id": project_id, "message": "视频合成完成", "state": state}
