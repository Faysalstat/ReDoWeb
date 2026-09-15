import hashlib
import json
import random
import shutil
import time
from pathlib import Path

from ..config import get_settings
from ..services import tier_service
from .design_system_generation import build_fallback_design_system
from .errors import GenerationError, OpenRouterError
from .generation_tools import TOOL_SCHEMAS, make_tool_dispatch
from .openrouter_client import chat_completion
from .postprocess import parse_frontmatter, postprocess_output

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

# Two generation strategies, one per tier -- restored 2026-09-01 at the
# user's explicit request after the AI-generated ("skill-based") design
# system replaced the original hand-authored ("template-based") style
# templates entirely; both are genuinely good and the user wanted both kept
# rather than one replacing the other. "premium" runs the original random
# hand-authored business_*.txt template; every other enabled tier (pro
# today) runs the newer skill-based, AI-resolved design_system.json path.
TEMPLATE_BASED_TIER = "premium"

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

# Distilled from agent/SKILL.md (the "web-design-engineer" Claude Skill) --
# only the pieces that hold regardless of which design system was declared
# below, never a fixed aesthetic opinion (that would fight whatever the
# Design Decisions block below actually calls for). The interactive parts
# of that skill (clarifying questions, stop-and-confirm checkpoints, v0
# review, critique-on-request) don't apply here -- this pipeline runs
# headless with no user turn available, so this block keeps only the
# static craft guidance a single-pass agent can act on directly.
CRAFT_PRINCIPLES = """
You are a senior web design engineer. The Design Decisions block below is
this project's brand spec -- follow it, not a generic default.

Avoid these defaults UNLESS the Design Decisions block below specifically
calls for them (if it does, that's a deliberate brand choice, not a lazy
default, and the block wins):
- Purple-to-pink-to-blue gradients used as decoration with no stated reason.
- Emoji used as icon substitutes -- use inline SVG icons (or a real icon
  set loaded via CDN) instead; a genuinely missing icon is better shown as
  a small labeled placeholder than faked with an emoji.
- Fabricated content -- never invent testimonials, stats, pricing, team
  members, credentials, or client logos that aren't already present in the
  blueprint below; omit that section entirely rather than making one up.
- Purely decorative rounded-card-with-colored-left-border components that
  carry no grouping or selection meaning.

Color implementation: the FIRST rule in style.css must be a `:root { }` block
declaring `--color-primary`, `--color-secondary`, and `--color-accent` set to
the exact hex values given in the Design Decisions block below -- every
other color in the file must reference one of these variables (`var(--color-primary)`
etc.) or derive from one, never a hardcoded or newly-invented hex/oklch value.
Apply the Design Decisions block's stated color derivation rule (hover/muted/
tint states) using real CSS relative color syntax, e.g.
`oklch(from var(--color-primary) calc(l + 0.08) c h)` -- so the browser
computes exact, perceptually-consistent shades from the real base colors
instead of you guessing hex/oklch values by hand or introducing unrelated
new hues.

Craft baseline: CSS Grid/Flexbox for layout, CSS custom properties for
design tokens, clamp() for fluid type, text-wrap: pretty on headings and
paragraphs, and respect prefers-reduced-motion. Cover hover/focus/active/
disabled states on every interactive element. No filler content -- every
section should earn its place given what the blueprint actually contains.
"""


def _google_fonts_link_href(heading: str, body: str) -> str:
    """Builds the exact working Google Fonts CSS2 API URL for the chosen
    heading/body pair, so the model is given a ready-to-paste <link> href
    instead of being trusted to construct (or remember) one itself -- seen
    for real: a run that used hand-written CSS added a Google Fonts <link>
    on its own initiative, but a run using the Tailwind CDN path didn't add
    one at all, so real, validated font names (Nunito/Baloo 2) still never
    actually loaded and silently fell back to whatever's locally installed."""
    families = dict.fromkeys(name for name in (heading, body) if name)  # de-dupes, keeps order
    family_params = "&".join(f"family={name.replace(' ', '+')}:wght@400;600;700" for name in families)
    return f"https://fonts.googleapis.com/css2?{family_params}&display=swap"


def _render_system_prompt(design_system: dict) -> str:
    """Pure formatting, no AI call -- turns the per-project design-system
    spec (from design_system_generation.py, already resolved once for the
    whole project) into the skill's Step 3 "Design Decisions" declaration
    shape as plain text."""
    colors = design_system.get("colors") or {}
    typography = design_system.get("typography") or {}
    heading_font = typography.get("heading") or ""
    body_font = typography.get("body") or ""
    font_link_line = ""
    if heading_font or body_font:
        href = _google_fonts_link_href(heading_font, body_font)
        font_link_line = (
            "- Font loading (REQUIRED): add this exact tag to <head> so the "
            f'fonts above actually load: <link rel="stylesheet" href="{href}">\n'
        )
    return (
        "\n\n---\n\n"
        "Design Decisions for this project (resolve every visual choice "
        "through these, not generic defaults):\n"
        f"- Anchor recipe: {design_system.get('recipe_anchor', '(none)')}\n"
        f"- Visual language: {design_system.get('visual_language', '')}\n"
        f"- Colors: primary={colors.get('primary')}, secondary={colors.get('secondary')}, "
        f"accent={colors.get('accent')}\n"
        f"- Color derivation rule: {colors.get('derivation_rule', '')}\n"
        f"- Typography (AUTHORITATIVE -- use exactly these font names; the "
        f"blueprint content below may separately mention the site's original "
        f"fonts, ignore those in favor of these): heading={heading_font}, "
        f"body={body_font} -- {typography.get('notes', '')}\n"
        f"{font_link_line}"
        f"- Spacing scale: {design_system.get('spacing_scale', '')}\n"
        f"- Radius strategy: {design_system.get('radius_strategy', '')}\n"
        f"- Shadow style: {design_system.get('shadow_style', '')}\n"
        f"- Motion style: {design_system.get('motion_style', '')}\n"
        f"- Layout guidance: {design_system.get('layout_guidance', '')}\n"
    )


def _select_template(override: str | None = None) -> Path:
    """The original, hand-authored template-based strategy: picks one of
    PROMPTS_DIR's static business_*.txt design-strategy files. Restored
    (2026-09-01) for TEMPLATE_BASED_TIER alongside the newer skill-based
    path -- both are kept as distinct, deliberate strategies, not one
    superseding the other."""
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


def generate_site(project_root: Path, tier_key: str, template_override: str | None = None) -> dict:
    """Builds the tier's home page from project_root/blueprint/design.md --
    which the blueprint pipeline (blueprint_pipeline.run_blueprint_pipeline)
    renders from the reviewed blueprint.json via blueprint_legacy_compat, so
    this already reflects the structured-JSON pipeline's output without
    needing to read blueprint.json directly here. Scoped to one page (the
    home page) per docs/blueprint-json-pipeline-plan.md -- additional pages
    are a separate, later generation pass, not built by this function.

    Two system-prompt strategies, chosen by tier (see TEMPLATE_BASED_TIER):
    - template-based (TEMPLATE_BASED_TIER, "premium" today): one of
      PROMPTS_DIR's static hand-authored business_*.txt files, picked at
      random (or via `template_override`, path-traversal-checked -- real
      callers never pass this; it exists for repeatable manual testing of
      one specific template) + TECH_CONSTRAINTS. No design_system.json
      involved at all for this strategy.
    - skill-based (every other enabled tier, "pro" today): CRAFT_PRINCIPLES
      (static) + project_root/blueprint/design_system.json (the per-project
      design system resolved once, up front, by design_system_generation.py)
      + TECH_CONSTRAINTS. If design_system.json is missing for any reason, a
      deterministic fallback spec is built here from the real colors/fonts
      already in design.md's frontmatter, so generation never hard-fails
      for lack of one.

    Both strategies are deliberately kept side by side, not one replacing
    the other -- restored 2026-09-01 at the user's explicit request.
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

    if tier_key == TEMPLATE_BASED_TIER:
        template_path = _select_template(template_override)
        system_prompt = template_path.read_text(encoding="utf-8") + TECH_CONSTRAINTS
        strategy_used = template_path.name
    else:
        design_system_path = project_root / "blueprint" / "design_system.json"
        if design_system_path.exists():
            design_system = json.loads(design_system_path.read_text(encoding="utf-8"))
        else:
            design_system = build_fallback_design_system(
                colors=frontmatter.get("colors") or {},
                fonts=frontmatter.get("fonts") or {},
                tone=frontmatter.get("tone") or "",
            )
        (output_dir / "design_system.json").write_text(
            json.dumps(design_system, indent=2), encoding="utf-8"
        )
        system_prompt = CRAFT_PRINCIPLES + _render_system_prompt(design_system) + TECH_CONSTRAINTS
        strategy_used = design_system.get("recipe_anchor")

    user_message = _build_user_message(design_md, image_names)

    dispatch = make_tool_dispatch(output_dir)
    trace_path = output_dir / "_debug_trace.json"
    summary_text, total_usage, iterations_used = _run_agent_loop(
        settings, system_prompt, user_message, dispatch, trace_path=trace_path
    )

    postprocess_report = postprocess_output(output_dir, frontmatter)

    written_files = sorted(
        p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file()
    )

    return {
        "tier": tier_key,
        "postprocess": postprocess_report,
        # Kept as "template_used" (not renamed to e.g. "design_system_used")
        # because it's a real, still-in-use field -- a non-nullable DB
        # column (generation_outputs.template_used) plus three response
        # schemas and the real product routes/queue task handler all read this
        # exact key. There's no more literal template file to name, so the
        # value holds either a literal template filename (template-based
        # strategy) or the resolved recipe anchor (skill-based strategy) --
        # see the strategy_used assignment above.
        "template_used": strategy_used,
        "output_dir": output_dir.relative_to(project_root).as_posix(),
        "files": written_files,
        "summary": summary_text,
        "usage": total_usage,
        "iterations": iterations_used,
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
    settings, system_prompt: str, user_message: str, dispatch: dict, trace_path: Path | None = None
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
