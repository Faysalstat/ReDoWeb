import hashlib
import json
from pathlib import Path

from .errors import GenerationError, OpenRouterError
from .openrouter_client import chat_completion
from .tools import TOOL_SCHEMAS


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
                if not isinstance(args, dict) or "note" in args:
                    continue
                path = args.get("path", "?")
                size = len(args.get("content") or "")
                fn["arguments"] = json.dumps(
                    {
                        "note": (
                            f"{path} was already written earlier this run ({size} "
                            "chars) -- do not re-send this call. Call read_file if "
                            "you need its current content."
                        )
                    }
                )
        elif message.get("role") == "tool":
            content = message.get("content") or ""
            if len(content) > 300 and not content.startswith("(compacted"):
                message["content"] = (
                    f"(compacted -- {len(content)} chars previously returned here; "
                    "call the tool again if you need the current content)"
                )


def run_agent_loop(
    settings, system_prompt: str, user_message: str, dispatch: dict, trace_path: Path | None = None
):
    caching_enabled = settings.generation_prompt_caching_enabled
    system_content: str | list[dict] = system_prompt
    user_content: str | list[dict] = user_message
    if caching_enabled:
        system_content = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
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
        session_id = hashlib.sha256(str(trace_path).encode("utf-8")).hexdigest()

    # Counts total occurrences of each distinct failure signature across the
    # whole run, NOT reset on an unrelated success.
    failure_counts: dict[str, int] = {}

    def _flush_trace():
        if trace_path is not None:
            trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    for iteration in range(1, settings.generation_max_iterations + 1):
        current_iter_start = len(messages)
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
                trace.append(trace_entry)
                _flush_trace()
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your last response was cut off before producing any "
                            "tool call or final message (hit the output token "
                            "limit with no progress). Start immediately with a "
                            "write_file call -- do not spend the response on "
                            "planning or reasoning text first."
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
