"""Turn the normalized items into a short, friendly English summary using the Anthropic API."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, timedelta

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept `output_config.effort` and the server-side refusal fallback used below.
# For any other model (set via ANTHROPIC_MODEL) the request is sent without those two options.
MODELS_WITH_EFFORT_AND_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"}

NOTHING_AT_ALL = "Nothing due tomorrow, and nothing on the planner for the coming week."

SYSTEM_PROMPT = """\
You write a short evening message for a parent about their child's school work, based only on \
data exported from the school's planner (Smartschool, a Belgian school platform). The data is \
often in Dutch or French; write the message in plain, friendly English.

Structure:
1. "Tomorrow (<weekday> <day> <month>)": every item due tomorrow. If there is none, say so in one line.
2. "Coming up this week": the remaining items, grouped by day, kept brief.

For each item give: the subject, what exactly is required, and what to prepare or bring.
- Items of type "test" are tests: start that line with "⚠️ TEST" so they stand out.
- Items of type "bring" mean something must be brought to class.
- Translate the teacher's text faithfully. Keep page numbers, exercise numbers, chapter numbers \
and names exactly as given. If a phrase is unclear, quote the original in parentheses.
- Never invent or guess details (materials, page numbers, topics, times) that are not in the data. \
"What to prepare or bring" must come from the item's own text; if the text doesn't say, don't add advice.
- If the title is short and the description is null, add "(no further details given)".

Format: plain text for a Telegram chat, no Markdown syntax (no *, #, or backticks). Use short lines \
and "•" bullets. No greeting or sign-off beyond one short friendly opening line."""


def build_user_message(items, today: date) -> str:
    tomorrow = today + timedelta(days=1)
    payload = {
        "today": f"{today:%A %Y-%m-%d}",
        "tomorrow": f"{tomorrow:%A %Y-%m-%d}",
        "due_tomorrow": [_item_dict(i) for i in items if i.due == tomorrow],
        "later_this_week": [_item_dict(i) for i in items if i.due > tomorrow],
    }
    return "Planner data (JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _item_dict(item) -> dict:
    d = asdict(item)
    d["due"] = f"{item.due:%A %Y-%m-%d}"
    return d


def explain(items, today: date, settings: dict[str, str]) -> str:
    if not items:
        return NOTHING_AT_ALL

    import anthropic

    api_key = settings.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing setting: ANTHROPIC_API_KEY")
    model = settings.get("ANTHROPIC_MODEL") or DEFAULT_MODEL

    client = anthropic.Anthropic(api_key=api_key)
    request = {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": build_user_message(items, today)}],
    }
    if model in MODELS_WITH_EFFORT_AND_FALLBACK:
        response = client.beta.messages.create(
            **request,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    else:
        response = client.messages.create(**request)

    if response.stop_reason == "refusal":
        raise RuntimeError("The model declined to write the summary (stop_reason=refusal)")
    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(f"The model returned no text (stop_reason={response.stop_reason})")

    log.info("Summary generated with %s (%d chars)", response.model, len(text))
    return text
