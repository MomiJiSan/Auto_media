import unittest

from app.prompts.character import build_character_prompt, build_character_section


class CharacterPromptTests(unittest.TestCase):
    def test_build_character_prompt_uses_standard_three_view_sheet(self):
        prompt = build_character_prompt("李明", "主角", "青年男子，黑色短发，身形清瘦，穿着深蓝长衫。")

        self.assertIn("Standard three-view character turnaround sheet for 李明", prompt)
        self.assertIn("front view, side profile, and back view", prompt)
        self.assertIn("full body in all three views", prompt)

    def test_build_character_section_prefers_visual_dna(self):
        section = build_character_section(
            {
                "characters": [
                    {"id": "char_li_ming", "name": "李明", "role": "主角", "description": "青年男子，黑色短发。"},
                ],
                "character_images": {
                    "char_li_ming": {
                        "visual_dna": "young man, short black hair, slim build",
                        "design_prompt": "Standard three-view character turnaround sheet for 李明, dark blue robe",
                        "character_id": "char_li_ming",
                        "character_name": "李明",
                    }
                },
            }
        )

        self.assertIn("Visual DNA: young man, short black hair, slim build", section)
        self.assertNotIn("Standard three-view character turnaround sheet", section)

    def test_build_character_section_visual_dna_keeps_clothing_fallback(self):
        section = build_character_section(
            {
                "characters": [
                    {"id": "char_li_ming", "name": "李明", "role": "主角", "description": "青年男子，黑色短发，穿着深蓝长衫。"},
                ],
                "character_images": {
                    "char_li_ming": {
                        "visual_dna": "young man, short black hair, slim build",
                        "design_prompt": (
                            "Standard three-view character turnaround sheet for 李明, protagonist, determined expression, heroic bearing, "
                            "character description: 青年男子，黑色短发，穿着深蓝长衫。, "
                            "show front view, side profile, and back view of the same character on one sheet"
                        ),
                        "character_id": "char_li_ming",
                        "character_name": "李明",
                    }
                },
            }
        )

        self.assertIn("Visual DNA: young man, short black hair, slim build; 穿着深蓝长衫", section)

    def test_build_character_section_falls_back_to_design_prompt(self):
        section = build_character_section(
            {
                "characters": [
                    {"id": "char_li_ming", "name": "李明", "role": "主角", "description": "青年男子，黑色短发，穿着深蓝长衫。"},
                ],
                "character_images": {
                    "char_li_ming": {
                        "design_prompt": (
                            "Standard three-view character turnaround sheet for 李明, protagonist, determined expression, heroic bearing, "
                            "character description: 青年男子，黑色短发，穿着深蓝长衫。, "
                            "show front view, side profile, and back view of the same character on one sheet, "
                            "full body in all three views, neutral standing pose, clear silhouette, "
                            "consistent facial features and costume details across views, clean neutral backdrop, "
                            "production-ready character turnaround sheet, costume construction details, fabric texture, "
                            "accessories, highly detailed, photorealistic"
                        ),
                        "character_id": "char_li_ming",
                        "character_name": "李明",
                    }
                },
            }
        )

        self.assertIn("Visual DNA: 青年男子, 黑色短发, 穿着深蓝长衫", section)
        self.assertNotIn("front view", section)
        self.assertNotIn("turnaround sheet", section)

    def test_build_character_section_falls_back_to_legacy_prompt(self):
        section = build_character_section(
            {
                "characters": [
                    {"id": "char_li_ming", "name": "李明", "role": "主角", "description": "青年男子，黑色短发，穿着深蓝长衫。"},
                ],
                "character_images": {
                    "char_li_ming": {
                        "prompt": "Legacy character turnaround prompt for 李明, dark blue robe",
                        "character_id": "char_li_ming",
                        "character_name": "李明",
                    }
                },
            }
        )

        self.assertIn("Visual DNA: 青年男子, 黑色短发, 穿着深蓝长衫", section)


if __name__ == "__main__":
    unittest.main()
