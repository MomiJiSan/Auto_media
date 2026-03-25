from __future__ import annotations

from typing import Any, Mapping


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def get_character_asset_entry(character_images: Mapping[str, Any] | None, name: str) -> dict[str, Any]:
    if not isinstance(character_images, Mapping) or not name:
        return {}
    entry = character_images.get(name) or {}
    return dict(entry) if isinstance(entry, Mapping) else {}


def get_character_visual_dna(character_images: Mapping[str, Any] | None, name: str) -> str:
    entry = get_character_asset_entry(character_images, name)
    return _normalize_text(entry.get("visual_dna", ""))


def get_character_design_prompt(character_images: Mapping[str, Any] | None, name: str) -> str:
    entry = get_character_asset_entry(character_images, name)
    return _normalize_text(entry.get("design_prompt") or entry.get("prompt", ""))


def build_character_asset_record(
    *,
    image_url: str,
    image_path: str,
    prompt: str,
    existing: Mapping[str, Any] | None = None,
    visual_dna: str = "",
) -> dict[str, Any]:
    record = dict(existing or {})
    record.update(
        {
            "image_url": image_url,
            "image_path": image_path,
            "prompt": prompt,
            "design_prompt": prompt,
            "asset_kind": "character_sheet",
            "framing": "full_body",
        }
    )
    if visual_dna:
        record["visual_dna"] = _normalize_text(visual_dna)
    return record
