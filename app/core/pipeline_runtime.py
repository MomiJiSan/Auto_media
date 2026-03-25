from app.schemas.pipeline import GenerationStrategy


INTEGRATED_FALLBACK_RUNTIME = "integrated_image_to_video_fallback"
INTEGRATED_FALLBACK_NOTE = "当前 integrated 策略会降级为图生视频 fallback，不包含语音一体化生成。"


def resolve_tracking_story_id(route_project_id: str, story_id: str | None) -> str:
    normalized_story_id = (story_id or "").strip()
    return normalized_story_id or route_project_id


def uses_integrated_fallback(strategy: GenerationStrategy) -> bool:
    return strategy == GenerationStrategy.INTEGRATED


def get_runtime_strategy_name(strategy: GenerationStrategy) -> str:
    if uses_integrated_fallback(strategy):
        return INTEGRATED_FALLBACK_RUNTIME
    return strategy.value


def get_runtime_strategy_note(strategy: GenerationStrategy) -> str:
    if uses_integrated_fallback(strategy):
        return INTEGRATED_FALLBACK_NOTE
    return ""


def build_runtime_strategy_metadata(strategy: GenerationStrategy) -> dict[str, object]:
    metadata: dict[str, object] = {
        "requested_strategy": strategy.value,
        "runtime_strategy": get_runtime_strategy_name(strategy),
    }
    note = get_runtime_strategy_note(strategy)
    if note:
        metadata["note"] = note
    if uses_integrated_fallback(strategy):
        metadata["audio_integrated"] = False
    return metadata
