"""Configuration loading and validation for novel-to-comic projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_FORMATS = ["txt", "epub"]
TRIM_SIZES = {"B5", "A4", "manga-standard"}
COMPRESSION_MODES = {"essence", "standard", "complete"}
APPROVAL_MODES = {"chapter", "every_n_chapters", "auto_after_first"}
PROJECT_MODES = {"private_experiment", "licensed_commercial", "public_domain"}
TARGET_FORMATS = {"manga_page", "color_comic", "webtoon", "storyboard_only"}
AUTOMATION_LEVELS = {1, 2, 3}
PAGE_COUNT_POLICIES = {"story_first_variable", "fixed_budget", "soft_target"}
FINISHED_PAGE_TEXT_MODES = {"image2_embedded", "deterministic_lettering_fallback"}


def load_preferences(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data


def validate_preferences(preferences: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    project_config = preferences.get("project")
    if not isinstance(project_config, dict):
        errors.append("project must be an object")
    else:
        mode = project_config.get("mode")
        if mode not in PROJECT_MODES:
            errors.append("project.mode must be private_experiment, licensed_commercial, or public_domain")

        target_format = project_config.get("target_format")
        if target_format not in TARGET_FORMATS:
            errors.append("project.target_format must be manga_page, color_comic, webtoon, or storyboard_only")

        automation_level = project_config.get("automation_level")
        if automation_level not in AUTOMATION_LEVELS:
            errors.append("project.automation_level must be 1, 2, or 3")

        human_review = project_config.get("human_review")
        if not isinstance(human_review, bool):
            errors.append("project.human_review must be a boolean")

    input_config = preferences.get("input")
    if not isinstance(input_config, dict):
        errors.append("input must be an object")
    else:
        formats = input_config.get("supported_formats")
        if formats != SUPPORTED_FORMATS:
            errors.append("input.supported_formats must be ['txt', 'epub']")

    comic_config = preferences.get("comic")
    if not isinstance(comic_config, dict):
        errors.append("comic must be an object")
    else:
        trim_size = comic_config.get("trim_size")
        if trim_size not in TRIM_SIZES:
            errors.append("comic.trim_size must be B5, A4, or manga-standard")

        target_pages = comic_config.get("target_pages")
        if not isinstance(target_pages, int) or target_pages < 1:
            errors.append("comic.target_pages must be a positive integer")

        page_count_policy = comic_config.get("page_count_policy")
        if page_count_policy not in PAGE_COUNT_POLICIES:
            errors.append("comic.page_count_policy must be story_first_variable, fixed_budget, or soft_target")

        page_size_px = comic_config.get("page_size_px")
        if not isinstance(page_size_px, dict):
            errors.append("comic.page_size_px must be an object")
        else:
            width = page_size_px.get("width")
            height = page_size_px.get("height")
            if not isinstance(width, int) or not isinstance(height, int) or width < 2048 or height < 2048:
                errors.append("comic.page_size_px width and height must be integers >= 2048")
            elif height <= width:
                errors.append("comic.page_size_px must be portrait orientation")

        minimum_short_edge = comic_config.get("minimum_short_edge_px")
        if not isinstance(minimum_short_edge, int) or minimum_short_edge < 2048:
            errors.append("comic.minimum_short_edge_px must be an integer >= 2048")

        compression_mode = comic_config.get("compression_mode")
        if compression_mode not in COMPRESSION_MODES:
            errors.append("comic.compression_mode must be essence, standard, or complete")

    approvals = preferences.get("approvals")
    if not isinstance(approvals, dict):
        errors.append("approvals must be an object")
    else:
        mode = approvals.get("after_first_chapter")
        if mode not in APPROVAL_MODES:
            errors.append("approvals.after_first_chapter must be chapter, every_n_chapters, or auto_after_first")

    visuals = preferences.get("visuals")
    if not isinstance(visuals, dict):
        errors.append("visuals must be an object")
    else:
        if not isinstance(visuals.get("style_family"), str) or not visuals["style_family"].strip():
            errors.append("visuals.style_family must be a non-empty string")

    image_generation = preferences.get("image_generation")
    if not isinstance(image_generation, dict):
        errors.append("image_generation must be an object")
    else:
        finished_page_text = image_generation.get("finished_page_text")
        if finished_page_text not in FINISHED_PAGE_TEXT_MODES:
            errors.append("image_generation.finished_page_text must be image2_embedded or deterministic_lettering_fallback")

        if image_generation.get("forbid_text_in_finished_pages") is not False:
            errors.append("image_generation.forbid_text_in_finished_pages must be false for finished-page image2 workflow")

        if not isinstance(image_generation.get("fallback_page_art_forbids_text"), bool):
            errors.append("image_generation.fallback_page_art_forbids_text must be a boolean")

    return errors
