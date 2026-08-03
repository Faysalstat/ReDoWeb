import json
import random
import shutil
from pathlib import Path

from ..config import get_settings
from ..services import tier_service
from .errors import GenerationError, OpenRouterError
from .generation_tools import TOOL_SCHEMAS, make_tool_dispatch
from .openrouter_client import chat_completion
from .postprocess import parse_frontmatter, postprocess_output

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

TECH_CONSTRAINTS = """

---

IMPORTANT project-specific constraints (these override anything above that conflicts):
- There is no existing codebase and no build tooling. Do NOT scaffold React, Next.js, Vue, or any framework/bundler.
- Build a plain static website: one .html file per page, a single shared style.css, and an optional shared script.js. Use the write_file tool for every file you create.
- You may use Tailwind CSS via its CDN script tag, Bootstrap via its CDN link, or hand-written CSS in style.css -- whichever best expresses the design system above. Do not run any build step; everything must work as plain static files.
- An images/ folder already exists in the output directory with the site's real logo and photos, downloaded from the original site. Do not invent placeholder images -- reference only the exact filenames listed in the user message, e.g. <img src="images/...">.
- Skip the questions you would normally ask a user about tech stack or scope -- there is no user to ask right now. The content below is your complete brief; just build the site.
- When completely finished, respond with a final plain-text summary of the pages and files you created, and do not request any more tool calls.
"""


def generate_site(project_root: Path, tier_key: str) -> dict:
    if not tier_service.is_tier_enabled(tier_key):
        raise GenerationError(f"Tier '{tier_key}' is not currently enabled")

    design_md_path = project_root / "blueprint" / "design.md"
    if not design_md_path.exists():
        raise GenerationError("No blueprint found for this project -- run blueprint extraction first")
    design_md = design_md_path.read_text(encoding="utf-8")

    metadata = json.loads((project_root / "metadata.json").read_text(encoding="utf-8"))
    assets = metadata.get("assets") or []

    settings = get_settings()

    output_dir = project_root / "generated" / tier_key
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_names = _copy_images(project_root, output_dir, assets)
    (output_dir / "design.md").write_text(design_md, encoding="utf-8")

    template_path = _select_template()
    system_prompt = template_path.read_text(encoding="utf-8") + TECH_CONSTRAINTS
    user_message = _build_user_message(design_md, image_names)

    dispatch = make_tool_dispatch(output_dir)
    trace_path = output_dir / "_debug_trace.json"
    summary_text, total_usage, iterations_used = _run_agent_loop(
        settings, system_prompt, user_message, dispatch, trace_path=trace_path
    )

    frontmatter = parse_frontmatter(design_md)
    postprocess_report = postprocess_output(output_dir, frontmatter)

    written_files = sorted(
        p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file()
    )

    return {
        "tier": tier_key,
        "postprocess": postprocess_report,
        "template_used": template_path.name,
        "output_dir": output_dir.relative_to(project_root).as_posix(),
        "files": written_files,
        "summary": summary_text,
        "usage": total_usage,
        "iterations": iterations_used,
    }


def _run_agent_loop(
    settings, system_prompt: str, user_message: str, dispatch: dict, trace_path: Path | None = None
):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    trace: list[dict] = []

    def _flush_trace():
        if trace_path is not None:
            trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    for iteration in range(1, settings.generation_max_iterations + 1):
        payload = {
            "model": settings.generation_model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "max_tokens": settings.generation_max_tokens,
        }
        data = chat_completion(payload, timeout=180.0)

        usage = data.get("usage") or {}
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as exc:
            raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc

        messages.append(message)
        tool_calls = message.get("tool_calls") or []

        trace_entry = {
            "iteration": iteration,
            "finish_reason": choice.get("finish_reason"),
            "assistant_content": message.get("content"),
            "tool_calls": [],
        }

        if not tool_calls:
            trace.append(trace_entry)
            _flush_trace()
            return message.get("content") or "", total_usage, iteration

        for tool_call in tool_calls:
            fn = tool_call.get("function", {})
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"

            if choice.get("finish_reason") == "length":
                result = (
                    "Error: your response was cut off before this tool call finished "
                    "(hit the output token limit) -- the call was not executed. Write "
                    "shorter file contents, or split this file's content across a "
                    "smaller first write_file call plus follow-up edits, then retry."
                )
            else:
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    result = (
                        f"Error: arguments for {name} were not valid JSON (got: "
                        f"{raw_args[:200]!r}) -- retry with well-formed, complete arguments."
                    )
                    args = None

                if args is not None:
                    handler = dispatch.get(name)
                    if handler is None:
                        result = f"Unknown tool: {name}"
                    else:
                        try:
                            result = handler(**args)
                        except GenerationError as exc:
                            result = f"Error: {exc}"
                        except TypeError as exc:
                            result = f"Error: invalid arguments for {name}: {exc}"

            trace_entry["tool_calls"].append(
                {"name": name, "arguments": raw_args, "result": str(result)[:500]}
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "content": str(result),
                }
            )

        trace.append(trace_entry)
        _flush_trace()

    raise GenerationError(
        f"Agent did not finish within {settings.generation_max_iterations} iterations"
    )


def _select_template() -> Path:
    templates = sorted(PROMPTS_DIR.glob("*.txt"))
    if not templates:
        raise GenerationError(f"No design-strategy templates found in {PROMPTS_DIR}")
    return random.choice(templates)


def _copy_images(project_root: Path, output_dir: Path, assets: list[dict]) -> list[str]:
    images_out = output_dir / "images"
    images_out.mkdir(parents=True, exist_ok=True)
    copied = []
    for asset in assets:
        if asset.get("asset_type") not in ("image", "icon"):
            continue
        src = project_root / asset["storage_path"]
        if not src.exists():
            continue
        dest = images_out / src.name
        dest.write_bytes(src.read_bytes())
        copied.append(src.name)
    return copied


def _build_user_message(design_md: str, image_names: list[str]) -> str:
    image_list = "\n".join(f"- images/{name}" for name in image_names) or "(no images available)"
    return (
        "Here is the business content and brand blueprint to build the site from "
        "(YAML frontmatter + page content):\n\n"
        f"{design_md}\n\n"
        "Available image files already in the output directory's images/ folder "
        "(reference these exact paths, do not invent new ones):\n"
        f"{image_list}\n\n"
        "Build the complete website now."
    )
