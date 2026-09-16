import hashlib
import json
import random
import shutil
import time
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
- Build ONLY the home page for this run -- a single index.html plus style.css (and an optional script.js). If the content below describes more than one page, use only the home page's content; ignore the rest (additional pages are a separate, later generation pass, not part of this run).
"""


def _select_template(override: str | None = None) -> Path:
    """Picks one of PROMPTS_DIR's static business_*.txt design-strategy
    files at random -- the sole generation strategy for every tier."""
    if override:
        prompts_root = PROMPTS_DIR.resolve()
        template_path = (PROMPTS_DIR / override).resolve()
        if not template_path.is_relative_to(prompts_root) or not template_path.exists():
            raise GenerationError(f"Template not found: {override}")
        return template_path

    templates = sorted(PROMPTS_DIR.glob("*.txt"))
    if not templates:
        raise GenerationError(f"No design-strategy templates found in {PROMPTS_DIR}")
    return random.choice(templates)


def _rmtree_with_retry(path: Path, attempts: int = 5, delay_seconds: float = 1.0) -> None:
    """Empties `path` (deletes everything inside it) rather than removing
    the directory object itself, then retries briefly on Windows
    PermissionError (WinError 32) for individual entries.

    On Windows, a file watcher (an editor, a search indexer, antivirus)
    commonly holds a directory handle open purely for change-notification
    purposes (ReadDirectoryChangesW) -- this blocks removing/renaming the
    directory itself but does NOT block creating, writing, or deleting
    files inside it. shutil.rmtree(path) fails on that outer handle even
    though every individual delete would succeed, so this clears contents
    one entry at a time (each with its own short retry) and leaves the
    directory in place instead of trying to remove it.
    """
    last_error: OSError | None = None
    for entry in path.iterdir():
        for attempt in range(attempts):
            try:
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(delay_seconds)
        if last_error is not None:
            raise last_error


def generate_site(
    project_root: Path,
    tier_key: str,
    template_override: str | None = None,
    generation_model: str | None = None,
) -> dict:
    """Builds the tier's home page from project_root/blueprint/design.md --
    which the blueprint pipeline (blueprint_pipeline.run_blueprint_pipeline)
    renders from the reviewed blueprint.json via blueprint_legacy_compat, so
    this already reflects the structured-JSON pipeline's output without
    needing to read blueprint.json directly here. Scoped to one page (the
    home page) per docs/blueprint-json-pipeline-plan.md -- additional pages
    are a separate, later generation pass, not built by this function.

    Every tier uses the same template-based strategy (removed 2026-09-16,
    at the user's explicit request, after the AI-generated recipe-anchor/
    design-system path -- previously used by every tier but "premium" --
    caused real confusion: a project generating only one tier still paid
    for the design-system AI call, and its resolved recipe_anchor surfaced
    in places that made it look like it had been used for generation when
    it hadn't been). One of PROMPTS_DIR's static hand-authored
    business_*.txt files is picked at random (or via `template_override`,
    path-traversal-checked -- real callers never pass this; it exists for
    repeatable manual testing of one specific template) + TECH_CONSTRAINTS.

    `generation_model` is the resolved OpenRouter model id for this run's
    agent loop -- real callers (tasks_generate.py) resolve it per-tier via
    model_config_service.get_generation_model() (DB-backed, swappable
    without a rebuild) and pass it in; this function stays DB-free and
    falls back to config.py's static default when it's omitted (debug
    routes rely on that default).
    """
    if not tier_service.is_tier_enabled(tier_key):
        raise GenerationError(f"Tier '{tier_key}' is not currently enabled")

    design_md_path = project_root / "blueprint" / "design.md"
    if not design_md_path.exists():
        raise GenerationError("No blueprint found for this project -- run blueprint extraction first")
    design_md = design_md_path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(design_md)

    metadata = json.loads((project_root / "metadata.json").read_text(encoding="utf-8"))
    assets = metadata.get("assets") or []

    settings = get_settings()
    generation_model = generation_model or settings.generation_model

    output_dir = project_root / "generated" / tier_key
    if output_dir.exists():
        _rmtree_with_retry(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_names = _copy_images(project_root, output_dir, assets)
    (output_dir / "design.md").write_text(design_md, encoding="utf-8")
    blueprint_json_path = project_root / "blueprint" / "blueprint.json"
    if blueprint_json_path.exists():
        (output_dir / "blueprint.json").write_text(
            blueprint_json_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    template_path = _select_template(template_override)
    system_prompt = template_path.read_text(encoding="utf-8") + TECH_CONSTRAINTS
    strategy_used = template_path.name

    user_message = _build_user_message(design_md, image_names)

    dispatch = make_tool_dispatch(output_dir)
    trace_path = output_dir / "_debug_trace.json"
    summary_text, total_usage, iterations_used = _run_agent_loop(
        settings, generation_model, system_prompt, user_message, dispatch, trace_path=trace_path
    )

    postprocess_report = postprocess_output(output_dir, frontmatter)

    written_files = sorted(
        p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file()
    )

    return {
        "tier": tier_key,
        "postprocess": postprocess_report,
        "template_used": strategy_used,
        "output_dir": output_dir.relative_to(project_root).as_posix(),
        "files": written_files,
        "summary": summary_text,
        "usage": total_usage,
        "iterations": iterations_used,
        "model": generation_model,
    }


def _compact_resolved_tool_turns(messages: list[dict], before_index: int) -> None:
    """Shrinks large read_file/list_files results in messages[:before_index]
    down to short summaries, in place, leaving assistant tool_calls
    (including write_file's) completely untouched.

    write_file calls used to have their arguments rewritten to a compacted
    placeholder here. That was removed: regardless of the placeholder's
    exact shape (tried both a fake {"path","content"} object and a
    {"note": ...} marker), some models will echo their own visible history
    back verbatim as a new tool call -- so the moment history contains
    ANYTHING that looks like a prior write_file call, it risks being
    replayed and failing dispatch, burning the iteration budget on repeats
    of the identical error. Leaving real write_file calls (and their
    genuinely small "Wrote N characters..." results) alone in history
    avoids giving the model anything synthetic to latch onto; only
    read_file/list_files results are compacted here, since those are
    unmodified data the model retrieved, not calls it might reissue.

    Messages are mutated in place and never removed or reordered, so every
    assistant message's tool_calls keep their matching role:"tool" results
    immediately after them -- required by the OpenAI-style tool-calling
    wire format this loop speaks to OpenRouter.
    """
    for message in messages[:before_index]:
        if message.get("role") != "tool":
            continue
        content = message.get("content") or ""
        if len(content) > 300 and not content.startswith("(compacted"):
            message["content"] = (
                f"(compacted -- {len(content)} chars previously returned here; "
                "call the tool again if you need the current content)"
            )


# Per TECH_CONSTRAINTS: a single index.html plus a single shared style.css
# for this run's one page -- script.js is explicitly optional there, so it
# is deliberately not checked here.
REQUIRED_OUTPUT_FILES = ("index.html", "style.css")


def _missing_required_output_files(trace_path: Path | None) -> list[str]:
    """Checks REQUIRED_OUTPUT_FILES against the actual output directory
    (trace_path.parent -- trace_path is always output_dir/_debug_trace.json,
    see generate_site()). Returns [] (never blocking) when trace_path is
    None, since that only happens if a caller opts out of tracing."""
    if trace_path is None:
        return []
    output_dir = trace_path.parent
    return [name for name in REQUIRED_OUTPUT_FILES if not (output_dir / name).exists()]


def _run_agent_loop(
    settings,
    model_name: str,
    system_prompt: str,
    user_message: str,
    dispatch: dict,
    trace_path: Path | None = None,
):
    caching_enabled = settings.generation_prompt_caching_enabled
    system_content: str | list[dict] = system_prompt
    user_content: str | list[dict] = user_message
    if caching_enabled:
        # The design-strategy template + TECH_CONSTRAINTS is the largest
        # static block in the request (2.4K-6K tokens) and is byte-identical
        # on every iteration -- this is the first and biggest cache
        # breakpoint, separate from the user-turn breakpoint below so both
        # get cached independently of each other.
        system_content = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
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
        {"role": "system", "content": system_content},
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

    # Counts total occurrences of each distinct failure signature across the
    # whole run, NOT reset on an unrelated success -- a run that alternates
    # fail/fail/fail/succeed-on-something-irrelevant/fail/... never trips a
    # strictly-consecutive counter but is just as stuck, and would otherwise
    # burn the entire iteration budget without making real progress.
    failure_counts: dict[str, int] = {}

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
            "model": model_name,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "max_tokens": settings.generation_max_tokens,
        }
        if session_id:
            payload["session_id"] = session_id

        data = chat_completion(payload, timeout=settings.generation_call_timeout_seconds)

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
            if choice.get("finish_reason") == "length":
                # Cut off before producing a single tool call or any content --
                # NOT a legitimate "I'm done" signal, just an empty response
                # that happens to also have zero tool_calls. Treating this as
                # completion (the old behavior) let generation "succeed" with
                # no files ever written. Retry instead, same as the
                # truncated-mid-tool-call handling below.
                trace.append(trace_entry)
                _flush_trace()
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your last response was cut off before producing any "
                            "tool call or final message (hit the output token "
                            "limit with no progress). Start immediately with a "
                            "write_file call for the first page -- do not spend "
                            "the response on planning or reasoning text first."
                        ),
                    }
                )
                signature = "length:no_tool_calls"
                failure_counts[signature] = failure_counts.get(signature, 0) + 1
                if failure_counts[signature] >= settings.generation_max_consecutive_failures:
                    raise GenerationError(
                        f"Aborting after {failure_counts[signature]} responses cut off "
                        "before any tool call or content -- the model appears unable to "
                        "produce output within generation_max_tokens."
                    )
                continue

            missing_files = _missing_required_output_files(trace_path)
            if missing_files:
                # The model believes it's done (finish_reason != "length",
                # no more tool calls), but a required file from an earlier
                # failed write_file call was never actually retried -- seen
                # for real: one write_file in a multi-call iteration failed
                # (malformed tool-call JSON from the model), the other
                # succeeded, so the per-iteration failure tracking below
                # never triggered (that iteration still counted as a
                # success), and the model's own final summary confidently
                # described the missing file as created anyway. Treat a
                # missing required deliverable the same way a truncated
                # response is treated -- not a legitimate completion signal.
                trace.append(trace_entry)
                _flush_trace()
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You reported finishing, but these required files "
                            f"were never actually written: {', '.join(missing_files)}. "
                            "Call write_file now for each missing file -- do not "
                            "explain or apologize first."
                        ),
                    }
                )
                signature = f"premature_stop:missing:{','.join(missing_files)}"
                failure_counts[signature] = failure_counts.get(signature, 0) + 1
                if failure_counts[signature] >= settings.generation_max_consecutive_failures:
                    raise GenerationError(
                        f"Aborting: the model repeatedly claimed completion without "
                        f"actually writing required file(s) {', '.join(missing_files)}."
                    )
                continue

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

        if not iteration_had_success:
            signature = iteration_failure_signature or "unknown"
            failure_counts[signature] = failure_counts.get(signature, 0) + 1

            if failure_counts[signature] >= settings.generation_max_consecutive_failures:
                raise GenerationError(
                    f"Aborting after the same failure recurred {failure_counts[signature]} "
                    f"times ({signature}) -- the agent appears stuck and unlikely to "
                    "recover within the remaining iteration budget."
                )

    raise GenerationError(
        f"Agent did not finish within {settings.generation_max_iterations} iterations"
    )


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
