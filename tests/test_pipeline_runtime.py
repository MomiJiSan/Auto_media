import unittest
from unittest.mock import AsyncMock, patch

from fastapi import Request
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.pipeline_runtime import (
    INTEGRATED_FALLBACK_NOTE,
    INTEGRATED_FALLBACK_RUNTIME,
    build_runtime_strategy_metadata,
    resolve_tracking_story_id,
)
from app.main import app
from app.routers.pipeline import (
    concat_videos,
    generate_assets,
    generate_storyboard,
    get_status,
    render_video,
)
from app.schemas.pipeline import ConcatRequest, GenerationStrategy, PipelineStatus, StoryboardRequest
from app.schemas.storyboard import CameraSetup, Shot, VisualElements
from app.services.pipeline_executor import PipelineExecutor
from app.services import story_repository as repo


class PipelineRuntimeHelperTests(unittest.TestCase):
    def test_resolve_tracking_story_id_prefers_story_id(self):
        self.assertEqual(resolve_tracking_story_id("project-1", "story-1"), "story-1")
        self.assertEqual(resolve_tracking_story_id("project-1", ""), "project-1")

    def test_integrated_strategy_metadata_declares_fallback(self):
        metadata = build_runtime_strategy_metadata(GenerationStrategy.INTEGRATED)
        self.assertEqual(metadata["requested_strategy"], "integrated")
        self.assertEqual(metadata["runtime_strategy"], INTEGRATED_FALLBACK_RUNTIME)
        self.assertEqual(metadata["note"], INTEGRATED_FALLBACK_NOTE)
        self.assertFalse(metadata["audio_integrated"])

    def test_app_no_longer_mounts_legacy_projects_router(self):
        paths = {route.path for route in app.router.routes}
        self.assertFalse(any(path.startswith("/api/v1/projects") for path in paths))

    def test_app_no_longer_mounts_placeholder_stitch_route(self):
        paths = {route.path for route in app.router.routes}
        self.assertNotIn("/api/v1/pipeline/{project_id}/stitch", paths)


class PipelineStatusLookupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_status_prefers_story_lookup_when_story_id_is_provided(self):
        async with self.session_factory() as session:
            await repo.save_pipeline(
                session,
                "pipe-db-1",
                "story-123",
                {
                    "status": PipelineStatus.COMPLETE,
                    "progress": 100,
                    "current_step": "done",
                    "generated_files": {"meta": {"note": INTEGRATED_FALLBACK_NOTE}},
                },
            )

            status = await get_status("legacy-project", story_id="story-123", db=session)

        self.assertEqual(status.pipeline_id, "pipe-db-1")
        self.assertEqual(status.story_id, "story-123")
        self.assertEqual(status.status, PipelineStatus.COMPLETE)
        self.assertEqual(status.note, INTEGRATED_FALLBACK_NOTE)

    async def test_status_returns_default_pending_when_no_pipeline_is_persisted(self):
        async with self.session_factory() as session:
            status = await get_status("manual-project", db=session)

        self.assertIsNone(status.pipeline_id)
        self.assertEqual(status.story_id, "manual-project")
        self.assertEqual(status.status, PipelineStatus.PENDING)
        self.assertEqual(status.current_step, "Waiting to start")


class PipelineStoryContextFallbackTests(unittest.IsolatedAsyncioTestCase):
    def _make_shot(self) -> Shot:
        return Shot(
            shot_id="scene1_shot1",
            storyboard_description="Li Ming pauses at the doorway.",
            camera_setup=CameraSetup(shot_size="MS", camera_angle="Eye-level", movement="Static"),
            visual_elements=VisualElements(
                subject_and_clothing="Li Ming in a dark robe",
                action_and_expression="pauses before entering",
                environment_and_props="wooden doorway",
                lighting_and_color="soft overcast light",
            ),
            image_prompt="Medium shot. Li Ming pauses at the doorway.",
            final_video_prompt="Medium shot. Static camera. Li Ming opens the door.",
        )

    async def test_pipeline_executor_uses_constructor_story_id_when_call_arg_missing(self):
        executor = PipelineExecutor("legacy-project", "pipe-ctx-1", db=None, story_id="story-from-constructor")

        with (
            patch("app.services.pipeline_executor.prepare_story_context", new=AsyncMock(return_value=({}, None))) as prepare_mock,
            patch("app.services.pipeline_executor.parse_script_to_storyboard", new=AsyncMock(return_value=([self._make_shot()], {}))),
            patch.object(PipelineExecutor, "_run_separated_strategy", new=AsyncMock(return_value=None)),
            patch.object(PipelineExecutor, "_stitch_videos", new=AsyncMock(return_value=None)),
            patch("app.services.pipeline_executor.repo.save_pipeline", new=AsyncMock()),
        ):
            await executor.run_full_pipeline(
                script="scene script",
                strategy=GenerationStrategy.SEPARATED,
                provider="openai",
                model="gpt-test",
                voice="zh-CN-XiaoxiaoNeural",
                image_model="flux",
                video_model="wan",
                base_url="http://localhost:8000",
                llm_api_key="test-key",
                story_id=None,
            )

        self.assertEqual(prepare_mock.await_args.args[1], "story-from-constructor")

    async def test_generate_storyboard_loads_context_from_tracking_story_id(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        request = Request({"type": "http", "headers": []})
        req = StoryboardRequest(script="scene script", provider="openai", model="gpt-test")

        try:
            async with session_factory() as session:
                with (
                    patch("app.routers.pipeline._load_story_context", new=AsyncMock(return_value=({}, None))) as load_mock,
                    patch(
                        "app.routers.pipeline.parse_script_to_storyboard",
                        new=AsyncMock(return_value=([self._make_shot()], {"prompt_tokens": 1, "completion_tokens": 1})),
                    ),
                ):
                    result = await generate_storyboard(
                        "story-from-route",
                        request,
                        req,
                        llm={"provider": "openai", "model": "gpt-test", "api_key": "test-key", "base_url": "https://example.com/v1"},
                        db=session,
                    )
        finally:
            await engine.dispose()

        self.assertEqual(load_mock.await_args.args[1], "story-from-route")
        self.assertEqual(len(result.shots), 1)


class ManualPipelineMainlineTests(unittest.IsolatedAsyncioTestCase):
    def _make_request(self) -> Request:
        return Request(
            {
                "type": "http",
                "headers": [],
                "scheme": "http",
                "server": ("testserver", 80),
                "root_path": "",
                "path": "/",
            }
        )

    def _make_shot(self) -> Shot:
        return Shot(
            shot_id="scene1_shot1",
            storyboard_description="Li Ming pauses at the doorway.",
            camera_setup=CameraSetup(shot_size="MS", camera_angle="Eye-level", movement="Static"),
            visual_elements=VisualElements(
                subject_and_clothing="Li Ming in a dark robe",
                action_and_expression="pauses before entering",
                environment_and_props="wooden doorway",
                lighting_and_color="soft overcast light",
            ),
            image_prompt="Medium shot. Li Ming pauses at the doorway.",
            final_video_prompt="Medium shot. Static camera. Li Ming opens the door.",
        )

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_manual_pipeline_mainline_reuses_pipeline_and_accumulates_outputs(self):
        project_id = "manual-project"
        story_id = "story-mainline"
        request = self._make_request()
        shot = self._make_shot()

        async with self.session_factory() as session:
            with (
                patch("app.routers.pipeline._load_story_context", new=AsyncMock(return_value=({}, None))),
                patch(
                    "app.routers.pipeline.parse_script_to_storyboard",
                    new=AsyncMock(return_value=([shot], {"prompt_tokens": 1, "completion_tokens": 1})),
                ),
                patch(
                    "app.services.tts.generate_tts_batch",
                    new=AsyncMock(
                        return_value=[
                            {
                                "shot_id": shot.shot_id,
                                "audio_url": "/media/audio/scene1_shot1.mp3",
                                "duration_seconds": 1.5,
                            }
                        ]
                    ),
                ),
                patch(
                    "app.services.image.generate_images_batch",
                    new=AsyncMock(
                        return_value=[
                            {
                                "shot_id": shot.shot_id,
                                "image_url": "/media/images/scene1_shot1.png",
                            }
                        ]
                    ),
                ),
                patch(
                    "app.services.video.generate_videos_batch",
                    new=AsyncMock(
                        return_value=[
                            {
                                "shot_id": shot.shot_id,
                                "video_url": "/media/videos/scene1_shot1.mp4",
                            }
                        ]
                    ),
                ),
                patch("app.services.ffmpeg.concat_videos", new=AsyncMock(return_value="media/videos/episode_manual-project.mp4")),
            ):
                storyboard = await generate_storyboard(
                    project_id,
                    request,
                    StoryboardRequest(
                        script="scene script",
                        provider="openai",
                        model="gpt-test",
                        story_id=story_id,
                    ),
                    llm={
                        "provider": "openai",
                        "model": "gpt-test",
                        "api_key": "test-key",
                        "base_url": "https://example.com/v1",
                    },
                    db=session,
                )

                self.assertEqual(storyboard.story_id, story_id)
                self.assertIsNotNone(storyboard.pipeline_id)

                tts_response = await generate_assets(
                    project_id=project_id,
                    request=request,
                    storyboard=storyboard,
                    image_config={"image_api_key": "image-key", "image_base_url": "https://image.example/v1"},
                    llm={
                        "provider": "openai",
                        "model": "gpt-test",
                        "api_key": "test-key",
                        "base_url": "https://example.com/v1",
                    },
                    pipeline_id=storyboard.pipeline_id,
                    generate_tts=True,
                    generate_images=False,
                    voice="zh-CN-XiaoxiaoNeural",
                    image_model="flux-test",
                    story_id=storyboard.story_id,
                    background_tasks=None,
                    db=session,
                )
                self.assertEqual(tts_response.pipeline_id, storyboard.pipeline_id)

                status_after_tts = await get_status(
                    project_id,
                    pipeline_id=storyboard.pipeline_id,
                    story_id=storyboard.story_id,
                    db=session,
                )
                self.assertIn("tts", status_after_tts.generated_files)
                self.assertNotIn("images", status_after_tts.generated_files)

                images_response = await generate_assets(
                    project_id=project_id,
                    request=request,
                    storyboard=storyboard,
                    image_config={"image_api_key": "image-key", "image_base_url": "https://image.example/v1"},
                    llm={
                        "provider": "openai",
                        "model": "gpt-test",
                        "api_key": "test-key",
                        "base_url": "https://example.com/v1",
                    },
                    pipeline_id=storyboard.pipeline_id,
                    generate_tts=False,
                    generate_images=True,
                    voice="zh-CN-XiaoxiaoNeural",
                    image_model="flux-test",
                    story_id=storyboard.story_id,
                    background_tasks=None,
                    db=session,
                )
                self.assertEqual(images_response.pipeline_id, storyboard.pipeline_id)

                status_after_images = await get_status(
                    project_id,
                    pipeline_id=storyboard.pipeline_id,
                    story_id=storyboard.story_id,
                    db=session,
                )
                self.assertIn("tts", status_after_images.generated_files)
                self.assertIn("images", status_after_images.generated_files)

                image_url = status_after_images.generated_files["images"][shot.shot_id]["image_url"]
                video_response = await render_video(
                    project_id=project_id,
                    request=request,
                    shots_data=[{**storyboard.shots[0].model_dump(), "image_url": image_url}],
                    video_config={
                        "video_api_key": "video-key",
                        "video_base_url": "https://video.example/v1",
                        "video_provider": "dashscope",
                    },
                    llm={
                        "provider": "openai",
                        "model": "gpt-test",
                        "api_key": "test-key",
                        "base_url": "https://example.com/v1",
                    },
                    base_url="http://testserver",
                    video_model="wan-test",
                    pipeline_id=storyboard.pipeline_id,
                    story_id=storyboard.story_id,
                    background_tasks=None,
                    db=session,
                )
                self.assertEqual(video_response.pipeline_id, storyboard.pipeline_id)

                status_after_video = await get_status(
                    project_id,
                    pipeline_id=storyboard.pipeline_id,
                    story_id=storyboard.story_id,
                    db=session,
                )
                self.assertIn("tts", status_after_video.generated_files)
                self.assertIn("images", status_after_video.generated_files)
                self.assertIn("videos", status_after_video.generated_files)

                concat_response = await concat_videos(
                    project_id=project_id,
                    req=ConcatRequest(
                        video_urls=[status_after_video.generated_files["videos"][shot.shot_id]["video_url"]]
                    ),
                    request=request,
                    pipeline_id=storyboard.pipeline_id,
                    story_id=storyboard.story_id,
                    db=session,
                )

                final_status = await get_status(
                    project_id,
                    pipeline_id=storyboard.pipeline_id,
                    story_id=storyboard.story_id,
                    db=session,
                )

        self.assertEqual(concat_response.pipeline_id, storyboard.pipeline_id)
        self.assertEqual(final_status.status, PipelineStatus.COMPLETE)
        self.assertIn("tts", final_status.generated_files)
        self.assertIn("images", final_status.generated_files)
        self.assertIn("videos", final_status.generated_files)
        self.assertEqual(final_status.generated_files["final_video_url"], concat_response.video_url)
