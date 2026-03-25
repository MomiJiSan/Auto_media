import logging

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.services.video import generate_videos_batch, DEFAULT_MODEL
from app.core.api_keys import video_config_dep, get_art_style, llm_config_dep
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.story_context import build_generation_payload
from app.services.story_context_service import prepare_story_context

router = APIRouter(prefix="/api/v1/video", tags=["video"])
logger = logging.getLogger(__name__)


class VideoRequest(BaseModel):
    shots: List[dict]
    model: Optional[str] = DEFAULT_MODEL
    story_id: Optional[str] = None


class VideoResult(BaseModel):
    shot_id: str
    video_url: str


@router.post("/{project_id}/generate", response_model=List[VideoResult])
async def generate_videos(
    project_id: str,
    request: Request,
    body: VideoRequest,
    video_config: dict = Depends(video_config_dep),
    llm: dict = Depends(llm_config_dep),
    db: AsyncSession = Depends(get_db),
):
    base_url = str(request.base_url).rstrip("/")
    art_style = get_art_style(request)
    try:
        story_context = None
        if body.story_id:
            _, story_context = await prepare_story_context(
                db,
                body.story_id,
                provider=llm["provider"],
                model=llm["model"],
                api_key=llm["api_key"],
                base_url=llm["base_url"],
            )
        prepared_shots = []
        for shot in body.shots:
            payload = build_generation_payload(shot, story_context, art_style=art_style)
            prepared_shots.append(
                {
                    **shot,
                    "final_video_prompt": payload["final_video_prompt"],
                    "negative_prompt": payload.get("negative_prompt", ""),
                }
            )
        results = await generate_videos_batch(
            prepared_shots,
            base_url=base_url,
            model=body.model or DEFAULT_MODEL,
            art_style=art_style,
            **video_config,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Video generation failed for project=%s story_id=%s", project_id, body.story_id)
        detail = str(e).strip() or repr(e) or e.__class__.__name__
        raise HTTPException(status_code=500, detail=f"视频生成失败: {detail}") from e
    return results
