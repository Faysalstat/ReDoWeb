# Landing Page Agent (standalone)

A specialized, standalone AI agent for landing-page design. Takes an
already-scraped blueprint (`content/design.md`, same format ReDoWebs'
pipeline produces, plus an optional `content/style.md` style reference)
and generates a static landing page (`index.html` + `styles.css` +
`script.js` + `images/`) using a fixed `skill.md` as its design
instructions.

Independent of the main ReDoWebs backend -- own dependencies, own `.env`,
never imports from `backend/app/`.

## Setup

```
cd backend/standalone_agents/landing_agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `LANDING_AGENT_OPENROUTER_API_KEY` in `.env`.

Replace `skill.md` with your landing-page design instructions.

## Blueprint input

The blueprint is read from a fixed location, `content/`, inside this app
(no `--blueprint` flag -- edit these files directly between runs, same as
`skill.md`):

- `content/design.md` (required) -- YAML frontmatter + page content
  blueprint, same shape `blueprint_extractor.py` produces.
- `content/style.md` (optional) -- a style/design-system reference
  (colors, typography, components, do's/don'ts, etc.) for this run.
  Included in the agent's brief if present.

If `design.md`'s frontmatter has a `logo:` path, it's resolved relative
to `content/` and copied into `<output-dir>/images/`.

## Run

```
python -m landing_agent.cli --output <path-to-output-dir>
```

- Add `--force` to write into a non-empty output directory.
- Add `--model` / `--max-iterations` to override the `.env` defaults for
  one run.

```
python -m landing_agent.cli --output ../../../test_output
```

When it finishes, open `<output-dir>/index.html` directly in a browser.
A full iteration trace is written to `<output-dir>/_debug_trace.json` for
debugging.
