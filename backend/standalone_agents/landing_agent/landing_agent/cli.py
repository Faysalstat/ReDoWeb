import argparse
import sys
from pathlib import Path

from .agent_loop import run_agent_loop
from .blueprint_loader import load_blueprint
from .config import CONTENT_DIR, SKILL_PATH, get_settings
from .errors import GenerationError, OpenRouterError
from .postprocess import postprocess_output
from .tools import make_tool_dispatch

TECH_CONSTRAINTS = """

---

IMPORTANT project-specific constraints (these override anything above that conflicts):
- Build exactly one landing page: index.html, a single styles.css, and an optional script.js. Do NOT create multiple HTML pages, and do NOT scaffold React, Next.js, Vue, or any framework/bundler.
- Use the write_file tool for every file you create.
- You may use Tailwind CSS via its CDN script tag, Bootstrap via its CDN link, or hand-written CSS in styles.css -- whichever best expresses the design system above. No build step; everything must work as plain static files opened directly in a browser.
- An images/ folder already exists in the output directory with the site's real logo (if one was available). Do not invent placeholder images -- reference only the exact filenames listed in the user message, e.g. <img src="images/...">.
- There is no user to ask questions of -- the content below is your complete brief; just build the page.
- When completely finished, respond with a final plain-text summary of the files you created, and do not request any more tool calls.
"""


def _load_skill_prompt() -> str:
    if not SKILL_PATH.exists():
        raise GenerationError(
            f"skill.md not found at {SKILL_PATH} -- create it with the agent's "
            "landing-page design instructions before running."
        )
    text = SKILL_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise GenerationError(f"skill.md at {SKILL_PATH} is empty.")
    return text


def _prepare_output_dir(output_dir: Path, force: bool) -> None:
    if output_dir.exists():
        has_content = any(output_dir.iterdir())
        if has_content and not force:
            raise GenerationError(
                f"Output directory {output_dir} already exists and is not empty. "
                "Pass --force to write into it anyway, or choose a different --output."
            )
    output_dir.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default stdout/stderr to a legacy codepage (e.g.
    # cp1252), which raises UnicodeEncodeError on arrows/em-dashes/etc. that
    # models commonly use in plain-text summaries. Force UTF-8 with lossy
    # fallback so a cosmetic print never crashes a successful run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Generate a landing page from the fixed content/ blueprint using a fixed design skill."
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Directory to write the generated landing page into.",
    )
    parser.add_argument("--model", default=None, help="Override the configured generation model.")
    parser.add_argument("--max-iterations", type=int, default=None, dest="max_iterations")
    parser.add_argument(
        "--force", action="store_true",
        help="Allow writing into a non-empty output directory.",
    )
    args = parser.parse_args(argv)

    blueprint_dir: Path = CONTENT_DIR
    output_dir: Path = args.output

    if not blueprint_dir.is_dir():
        print(f"Error: content/ directory not found at {blueprint_dir}", file=sys.stderr)
        return 1

    try:
        settings = get_settings()
        overrides = {}
        if args.model:
            overrides["generation_model"] = args.model
        if args.max_iterations:
            overrides["generation_max_iterations"] = args.max_iterations
        if overrides:
            settings = settings.model_copy(update=overrides)

        skill_prompt = _load_skill_prompt()
        _prepare_output_dir(output_dir, args.force)

        blueprint = load_blueprint(blueprint_dir, output_dir)
        (output_dir / "design.md").write_text(blueprint["content_blueprint"], encoding="utf-8")
        if blueprint["style_reference"]:
            (output_dir / "style.md").write_text(blueprint["style_reference"], encoding="utf-8")

        system_prompt = skill_prompt + TECH_CONSTRAINTS
        dispatch = make_tool_dispatch(output_dir)
        trace_path = output_dir / "_debug_trace.json"

        print(f"Generating landing page from {blueprint_dir} -> {output_dir}")
        print(f"Model: {settings.generation_model} | max iterations: {settings.generation_max_iterations}")
        if blueprint["style_reference"]:
            print("Style reference: style.md found, included in the brief.")
        if blueprint["image_names"]:
            print(f"Logo copied: {blueprint['image_names']}")

        summary_text, usage, iterations = run_agent_loop(
            settings, system_prompt, blueprint["user_message"], dispatch, trace_path=trace_path
        )

        report = postprocess_output(output_dir, blueprint["frontmatter"])

        written_files = sorted(
            p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file()
        )

        print("\n--- Done ---")
        print(f"Iterations used: {iterations}")
        print(f"Token usage: {usage}")
        print(f"Files written: {written_files}")
        if report["contrast_warnings"]:
            print("Contrast warnings:")
            for warning in report["contrast_warnings"]:
                print(f"  - {warning}")
        print(f"\nAgent summary:\n{summary_text}")
        print(f"\nOpen {(output_dir / 'index.html').resolve()} in a browser to review.")
        return 0

    except (GenerationError, OpenRouterError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
