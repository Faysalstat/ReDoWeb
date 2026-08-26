# Architecture Brief — Fix Iterative Website-Generation Agent (OpenRouter + Claude)

## Context for the agent reading this

This repo implements an agent that:
- Takes a **blueprint** (JSON site structure) and **design instructions** as input
- Runs multiple iterations/steps, generating website code and writing it to disk
- Keeps looping until the site is "done"
- Calls a Claude model via the **OpenRouter API**

**Problem:** token cost is very high. Root cause is a combination of (a) no prompt caching, and (b) the full blueprint/instructions/history being re-sent as live tokens on every iteration instead of being cached or compacted. Your job is to restructure the request/loop architecture per the plan below — not just to prompt-engineer around it.

---

## 1. Root causes to look for in the current code

1. **Same static prompt resent every call.** System instructions, coding standards, design guidelines, and possibly the blueprint itself are being re-sent verbatim on every iteration with no caching.
2. **OpenRouter request format is likely OpenAI-compatible (`chat/completions`), not Anthropic-native.** This matters a lot: OpenRouter's Anthropic-native caching only activates when the request uses the native message shape with explicit `cache_control` blocks. If the client library is sending `{"role": "system", "content": "..."}` inside a flat `messages[]` array (the OpenAI-compatible shape), `cache_control` is silently ignored and every call is billed at full price — this is a known gotcha, not a hypothetical.
3. **No bounded/structured "done" signal.** If completion is detected by string-matching model output rather than a structured tool call, the loop can run longer than necessary and re-read growing context each time.
4. **Full history probably resent per step**, including previously generated file contents, rather than compacting or referencing by path.

---

## 2. Target architecture

### 2.1 Use the Anthropic-native request shape through OpenRouter

Do **not** use an OpenAI-compatible client (e.g. `openai` Python SDK pointed at OpenRouter's base URL) for this agent. Use the native Anthropic Messages format:

- Top-level `system` field (not a `system` role inside `messages[]`), as an array of content blocks.
- Explicit `cache_control: {"type": "ephemeral"}` on the last block of:
  - The system prompt / coding standards / design guidelines (static, identical every call)
  - The blueprint, if it doesn't change during the run (mark it cached once per session)
  - Any few-shot examples of "good" generated code
- Model string should be the `anthropic/...` OpenRouter route so it hits Anthropic's cache-aware backend.
- After each call, **read `usage.cache_creation_input_tokens` and `usage.cache_read_input_tokens` from the response** and log them. This is the only reliable way to confirm caching is actually active — don't assume it from config alone.

### 2.2 Real conversation state, not prompt reconstruction

Maintain a persistent `messages[]` list for the run:

```
[system: cached instructions + blueprint]
messages = [
  user: "Generate index.html per blueprint section 1",
  assistant: tool_use(write_file, path="index.html", content="..."),
  user: tool_result(...),
  assistant: tool_use(write_file, path="styles.css", ...),
  ...
]
```

Append to this list each iteration — never rebuild the prompt string from scratch. Everything before the newest turn stays byte-identical, which is what makes it cacheable.

### 2.3 File writes as tool calls, not parsed text

Define a `write_file(path, content)` tool. Have the model call it directly instead of emitting code in a text block that your code then regex-parses out. This:
- Removes fragile parsing logic
- Makes each step's *output* small (a tool call), while the *cached* instructions stay large — the expensive part shrinks over time relative to the cached part
- Gives you a clean structured log of what changed per iteration

### 2.4 Structured completion signal

Add a `mark_complete(summary)` tool (or a required JSON field in the final response) instead of detecting "done" from free text. Stop the loop only on that explicit signal, with a hard `max_iterations` ceiling as a safety net regardless.

### 2.5 Context compaction across iterations

Once a file has been written and verified (see 2.6), don't keep resending its full content in context on later iterations. Replace it in the running transcript with a short manifest entry:

```
Generated: index.html (142 lines) — hero section, nav, CTA
Generated: styles.css (89 lines) — design tokens, layout grid
```

Only re-include a file's full content in context if the current step needs to edit that specific file. This caps context growth as the site grows to many files/pages instead of letting it grow linearly-to-quadratically with iteration count.

### 2.6 Cheap verification loop

After each `write_file`, run a fast local check (HTML/CSS lint, or a headless render check) in your own code — not via another model call. Only feed the model an error message if something failed. Don't re-send the blueprint or design instructions to "remind" the model each step; they're already in the cached system block from 2.1.

---

## 3. Concrete implementation checklist

- [ ] Switch OpenRouter client to native Anthropic message format (verify via raw request body, not just SDK docs)
- [ ] Move system prompt + design guidelines + blueprint into `system` array with `cache_control` on the last static block
- [ ] Replace "rebuild full prompt each call" with append-only `messages[]`
- [ ] Implement `write_file` tool; remove text-parsing-based file writes
- [ ] Implement `mark_complete` tool; remove string-matching completion detection
- [ ] Implement manifest-based compaction for previously-written files
- [ ] Log `cache_read_input_tokens` / `cache_creation_input_tokens` per call; assert cache hit rate is high after step 1 of each run
- [ ] Add `max_iterations` hard cap

## 4. Acceptance criteria

- After the first iteration of a run, `cache_read_input_tokens` should be non-zero and roughly equal to the static prompt size on every subsequent call.
- Per-iteration billed input tokens should grow slowly (manifest entries), not track total generated code size.
- Loop termination is driven only by `mark_complete`, never by output text matching.