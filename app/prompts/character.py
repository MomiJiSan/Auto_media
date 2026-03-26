
# -*- coding: utf-8 -*-
"""
角色视觉相关提示词与构建函数（Step 2.5 / Step 5）
"""
from typing import Optional

from app.core.story_context import build_character_reference_anchor


# ============================================================================
# 角色设计图 prompt 构建
# ============================================================================

def build_character_prompt(name: str, role: str, description: str) -> str:
    """构建标准三视图角色设定图 prompt。"""
    role = role or ""
    description = description or ""
    role_lower = role.lower()
    if any(k in role_lower for k in ("反派", "villain", "antagonist", "boss")):
        role_cue = "villain, sinister expression, dark presence"
    elif any(k in role_lower for k in ("主角", "protagonist", "hero", "主人公")):
        role_cue = "protagonist, determined expression, heroic bearing"
    elif any(k in role_lower for k in ("配角", "supporting", "助手", "sidekick")):
        role_cue = "supporting character, approachable expression"
    else:
        role_cue = f"{role}"
    return (
        f"Standard three-view character turnaround sheet for {name}, {role_cue}, "
        f"character description: {description}, "
        "show front view, side profile, and back view of the same character on one sheet, "
        "full body in all three views, neutral standing pose, clear silhouette, "
        "consistent facial features and costume details across views, clean neutral backdrop, "
        "production-ready character turnaround sheet, costume construction details, fabric texture, "
        "accessories, highly detailed, photorealistic"
    )


# ============================================================================
# 分镜角色参考信息块构建
# ============================================================================
def build_character_section(character_info: Optional[dict]) -> str:
    """构建传给分镜 LLM 的角色参考信息块。"""
    if not character_info:
        return ""
    characters = character_info.get("characters", [])
    character_images = character_info.get("character_images", {})
    if not characters:
        return ""

    lines = ["## Character Reference (maintain consistency across all shots)"]
    for c in characters:
        char_id = c.get("id", "")
        name = c.get("name", "")
        role = c.get("role", "")
        desc = c.get("description", "")
        lines.append(f"- **{name}**（{role}）：{desc}")
        visual_anchor = build_character_reference_anchor(
            character_images,
            name,
            character_id=char_id,
            description=desc,
        )
        if visual_anchor:
            lines.append(f"  Visual DNA: {visual_anchor}")
    return "\n".join(lines)
