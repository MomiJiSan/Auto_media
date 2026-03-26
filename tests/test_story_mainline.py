import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.story_assets import build_character_asset_record
from app.routers.story import finalize_script
from app.services import story_repository as repo
from app.services.story_llm import analyze_idea, generate_outline, generate_script, world_building_start, world_building_turn


class StoryMainlineFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_analyze_idea_persists_seed_story(self):
        async with self.session_factory() as session:
            result = await analyze_idea(
                "失意书生在雨夜古镇捡到一块会说话的玉佩。",
                "古风",
                "沉稳",
                db=session,
                api_key="",
            )
            story = await repo.get_story(session, result["story_id"])

        self.assertEqual(story["idea"], "失意书生在雨夜古镇捡到一块会说话的玉佩。")
        self.assertEqual(story["genre"], "古风")
        self.assertEqual(story["tone"], "沉稳")
        self.assertGreaterEqual(len(result["suggestions"]), 1)

    async def test_world_building_outline_script_and_finalize_run_in_order(self):
        async with self.session_factory() as session:
            start = await world_building_start("古镇茶馆中的命运重逢", db=session, api_key="")
            story_id = start["story_id"]

            turn = start
            for idx in range(6):
                turn = await world_building_turn(
                    story_id,
                    answer=f"第{idx + 1}轮选择",
                    db=session,
                    api_key="",
                )

            self.assertEqual(turn["status"], "complete")
            self.assertTrue(turn["world_summary"])

            outline = await generate_outline(
                story_id,
                selected_setting=turn["world_summary"],
                db=session,
                api_key="",
            )
            self.assertEqual(outline["story_id"], story_id)
            self.assertGreaterEqual(len(outline["characters"]), 1)
            self.assertGreaterEqual(len(outline["outline"]), 1)
            self.assertTrue(all(character.get("id") for character in outline["characters"]))
            self.assertTrue(
                all(
                    relationship.get("source_id") and relationship.get("target_id")
                    for relationship in outline["relationships"]
                )
            )

            generated_scenes = []
            async for item in generate_script(story_id, db=session, api_key=""):
                generated_scenes.append(item)
            await repo.save_story(
                session,
                story_id,
                {"scenes": generated_scenes},
            )

            persisted_story = await repo.get_story(session, story_id)
            first_character = persisted_story["characters"][0]
            await repo.save_story(
                session,
                story_id,
                {
                    "character_images": {
                        first_character["id"]: build_character_asset_record(
                            image_url="/media/characters/mainline.png",
                            image_path="media/characters/mainline.png",
                            prompt=f"Standard three-view character turnaround sheet for {first_character['name']}",
                            visual_dna="young woman, long dark hair, cream blouse, charcoal skirt",
                            character_id=first_character["id"],
                            character_name=first_character["name"],
                        )
                    }
                },
            )

            finalized = await finalize_script(story_id, db=session)

        self.assertIn("# 角色信息", finalized["script"])
        self.assertIn("Visual DNA:", finalized["script"])
        self.assertIn("【环境】", finalized["script"])
        self.assertIn("【画面】", finalized["script"])
        self.assertIn("【", finalized["script"])
        self.assertEqual(finalized["story_id"], story_id)


if __name__ == "__main__":
    unittest.main()
