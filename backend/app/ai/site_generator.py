import hashlib
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
- There is no user to ask questions of -- the content below is your complete brief; just build the site.
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


def _compact_resolved_tool_turns(messages: list[dict], before_index: int) -> None:
    """Shrinks previously-resolved write_file arguments and large
    read_file/list_files results in messages[:before_index] down to short
    summaries, in place. Once a write_file call has succeeded the file is
    on disk -- the model doesn't need its exact bytes echoed back into
    context on every later iteration, only proof that it was written (it
    can call read_file again if it genuinely needs the current content).

    Messages are mutated in place and never removed or reordered, so every
    assistant message's tool_calls keep their matching role:"tool" results
    immediately after them -- required by the OpenAI-style tool-calling
    wire format this loop speaks to OpenRouter.
    """
    for message in messages[:before_index]:
        if message.get("role") == "assistant":
            for tool_call in message.get("tool_calls") or []:
                fn = tool_call.get("function") or {}
                if fn.get("name") != "write_file":
                    continue
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    continue
                if not isinstance(args, dict) or args.get("_compacted") or "note" in args:
                    # "_compacted" -- already shrunk; "note" -- this was a
                    # discarded malformed/truncated call (see the discard
                    # markers below), not a real write -- leave it as-is so
                    # the "discarded, not executed" signal isn't overwritten
                    # with a misleading "<written, 0 chars>" marker.
                    continue
                path = args.get("path", "?")
                size = len(args.get("content") or "")
                fn["arguments"] = json.dumps(
                    {"path": path, "content": f"<written, {size} chars>", "_compacted": True}
                )
        elif message.get("role") == "tool":
            content = message.get("content") or ""
            # write_file's own confirmation ("Wrote N characters to X") and
            # short results are already small -- only shrink large
            # read_file/list_files payloads.
            if len(content) > 300 and not content.startswith("(compacted"):
                message["content"] = (
                    f"(compacted -- {len(content)} chars previously returned here; "
                    "call the tool again if you need the current content)"
                )


def _run_agent_loop(
    settings, system_prompt: str, user_message: str, dispatch: dict, trace_path: Path | None = None
):
    caching_enabled = settings.generation_prompt_caching_enabled
    user_content: str | list[dict] = user_message
    if caching_enabled:
        # design.md + image list are 100% static for the whole run, and this
        # is the last block of the static prefix (tools -> system -> this
        # message) -- caching it here covers the entire fixed portion of
        # every iteration's request in one breakpoint.
        user_content = [
            {
                "type": "text",
                "text": user_message,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    trace: list[dict] = []

    session_id = None
    if caching_enabled and trace_path is not None:
        # Stable per generation run (one project + tier) so OpenRouter's
        # sticky routing keeps every iteration on the same upstream
        # provider that holds the warm cache -- without this, cache hits
        # across the loop aren't guaranteed even with correct markers.
        session_id = hashlib.sha256(str(trace_path).encode("utf-8")).hexdigest()

    consecutive_failures = 0
    last_failure_signature: str | None = None

    def _flush_trace():
        if trace_path is not None:
            trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    for iteration in range(1, settings.generation_max_iterations + 1):
        current_iter_start = len(messages)
        # Compact every prior iteration's resolved tool turns, but leave the
        # iteration we're about to append fully intact. This is pure local
        # context hygiene -- independent of whether OpenRouter's upstream
        # cache_control is honored, so it always runs even when
        # caching_enabled is off.
        _compact_resolved_tool_turns(messages, current_iter_start)

        payload = {
            "model": settings.generation_model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "max_tokens": settings.generation_max_tokens,
        }
        if session_id:
            payload["session_id"] = session_id

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
            "cache_usage": usage.get("prompt_tokens_details"),
            "tool_calls": [],
        }

        if not tool_calls:
            trace.append(trace_entry)
            _flush_trace()
            return message.get("content") or "", total_usage, iteration

        iteration_had_success = False
        iteration_failure_signature: str | None = None

        for tool_call in tool_calls:
            fn = tool_call.get("function") or {}
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"

            if choice.get("finish_reason") == "length":
                result = (
                    "Error: your response was cut off before this tool call finished "
                    "(hit the output token limit) -- the call was not executed. Write "
                    "shorter file contents, or split this file's content across a "
                    "smaller first write_file call plus follow-up edits, then retry."
                )
                # Discard the truncated payload immediately (it can be a
                # multi-KB cut-off write_file) instead of letting it linger
                # in context and get resent on every later iteration.
                fn["arguments"] = json.dumps(
                    {"note": "discarded -- response truncated before this call finished"}
                )
                if iteration_failure_signature is None:
                    iteration_failure_signature = f"length:{name}"
            else:
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    result = (
                        f"Error: arguments for {name} were not valid JSON (got: "
                        f"{raw_args[:200]!r}) -- retry with well-formed, complete arguments."
                    )
                    args = None
                    fn["arguments"] = json.dumps(
                        {"note": "discarded -- malformed JSON, not executed"}
                    )
                    if iteration_failure_signature is None:
                        iteration_failure_signature = f"malformed_json:{name}"

                if args is not None:
                    handler = dispatch.get(name)
                    if handler is None:
                        result = f"Unknown tool: {name}"
                        if iteration_failure_signature is None:
                            iteration_failure_signature = f"unknown_tool:{name}"
                    else:
                        try:
                            result = handler(**args)
                            iteration_had_success = True
                        except GenerationError as exc:
                            result = f"Error: {exc}"
                            if iteration_failure_signature is None:
                                iteration_failure_signature = f"error:{name}"
                        except TypeError as exc:
                            result = f"Error: invalid arguments for {name}: {exc}"
                            if iteration_failure_signature is None:
                                iteration_failure_signature = f"bad_args:{name}"

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

        if iteration_had_success:
            consecutive_failures = 0
            last_failure_signature = None
        else:
            signature = iteration_failure_signature or "unknown"
            if signature == last_failure_signature:
                consecutive_failures += 1
            else:
                consecutive_failures = 1
                last_failure_signature = signature

            if consecutive_failures >= settings.generation_max_consecutive_failures:
                raise GenerationError(
                    f"Aborting after {consecutive_failures} consecutive identical "
                    f"failures ({signature}) -- the agent appears stuck and unlikely "
                    "to recover within the remaining iteration budget."
                )

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
