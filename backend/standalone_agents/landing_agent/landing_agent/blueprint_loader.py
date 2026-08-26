"""Reads the fixed content/ blueprint directory and assembles the agent's
user message.

Naming convention (matches the main ReDoWebs backend's blueprint/design.md
convention):
  - design.md  (required)  -- YAML frontmatter + page content blueprint,
                               same shape blueprint_extractor.py produces.
  - style.md   (optional)  -- a style/design-system reference (colors,
                               typography, components, do's/don'ts, etc.)
                               for this specific run.
A logo referenced in design.md's frontmatter (`logo:` path, relative to
the blueprint directory) is copied into the output directory's images/.
"""

from pathlib import Path

from .errors import GenerationError
from .postprocess import parse_frontmatter


def load_content_blueprint(blueprint_dir: Path) -> str:
    design_md_path = blueprint_dir / "design.md"
    if not design_md_path.exists():
        raise GenerationError(f"No design.md found in {blueprint_dir}")
    return design_md_path.read_text(encoding="utf-8")


def load_style_reference(blueprint_dir: Path) -> str | None:
    style_md_path = blueprint_dir / "style.md"
    if not style_md_path.exists():
        return None
    return style_md_path.read_text(encoding="utf-8")


def copy_logo(blueprint_dir: Path, output_dir: Path, frontmatter: dict) -> list[str]:
    """Copies the frontmatter's logo image (path relative to blueprint_dir)
    into <output_dir>/images/, if present. Missing/absent logos are skipped
    with a warning rather than a hard failure -- a blueprint isn't
    guaranteed to have a resolvable asset on disk (e.g. a hand-edited
    design.md with no accompanying snapshot/ folder).
    """
    images_out = output_dir / "images"
    images_out.mkdir(parents=True, exist_ok=True)

    logo_rel_path = frontmatter.get("logo")
    if not logo_rel_path:
        return []

    src = blueprint_dir / logo_rel_path
    if not src.exists():
        print(f"[warning] logo referenced in frontmatter not found: {src}")
        return []

    dest = images_out / src.name
    dest.write_bytes(src.read_bytes())
    return [src.name]


def build_user_message(content_blueprint: str, style_reference: str | None, image_names: list[str]) -> str:
    image_list = "\n".join(f"- images/{name}" for name in image_names) or "(no images available)"

    parts = [
        "Here is the business content and brand blueprint to build the landing "
        "page from (YAML frontmatter + page content):\n\n"
        f"{content_blueprint}",
    ]

    if style_reference:
        parts.append(
            "Here is the style/design-system reference to follow for this "
            f"specific run:\n\n## Style Reference\n\n{style_reference}"
        )

    parts.append(
        "Available image files already in the output directory's images/ "
        "folder (reference these exact paths, do not invent new ones):\n"
        f"{image_list}"
    )
    parts.append("Build the complete landing page now.")

    return "\n\n".join(parts)


def load_blueprint(blueprint_dir: Path, output_dir: Path) -> dict:
    content_blueprint = load_content_blueprint(blueprint_dir)
    style_reference = load_style_reference(blueprint_dir)
    frontmatter = parse_frontmatter(content_blueprint)
    image_names = copy_logo(blueprint_dir, output_dir, frontmatter)
    user_message = build_user_message(content_blueprint, style_reference, image_names)

    return {
        "content_blueprint": content_blueprint,
        "style_reference": style_reference,
        "frontmatter": frontmatter,
        "image_names": image_names,
        "user_message": user_message,
    }
