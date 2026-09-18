"""The simulator's and the judge's model calls (B06, B09).

One thin client over the Gemini SDK against the Vertex express endpoint — the
same endpoint and key the agent uses (D20). Explicit prompts from
``src/prompts/`` (invariant 6: no managed evaluation service), a versioned
header on each, JSON-schema output where a decision is parsed, and token
usage returned with every call so a run can meter its own cost.

The model id is a dated release (invariant 2, D04/D20) and travels in every
result alongside the prompt version, so a score or a simulated turn can
always be traced to what produced it.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from src.config import settings

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_VERSION_RE = re.compile(r"<!--\s*version:\s*([^\s]+)\s*-->")
_MAX_ATTEMPTS = 3
#: Per request, milliseconds. A persona turn or a judgement is seconds of work.
REQUEST_TIMEOUT_MS = 90_000


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    template: str

    def render(self, **values: str) -> str:
        text = self.template
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        left = re.findall(r"\{\{(\w+)\}\}", text)
        if left:
            raise ValueError(f"prompt {self.name}: unfilled placeholders {left}")
        return text


def load_prompt(name: str) -> Prompt:
    """A prompt file with its version header; the header is not sent to the model."""
    path = PROMPTS_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")
    match = _VERSION_RE.search(raw)
    if not match:
        raise ValueError(f"prompt {name} has no version header")
    body = _VERSION_RE.sub("", raw, count=1).lstrip()
    return Prompt(name=name, version=match.group(1), template=body)


@dataclass(frozen=True)
class LlmReply:
    text: str
    parsed: Optional[Any]
    tokens_input: int
    tokens_output: int
    model: str
    retries: int


class Llm(Protocol):
    model: str

    def generate(
        self, system: str, user: str, *, json_schema: Optional[dict] = None, temperature: float = 0.0
    ) -> LlmReply: ...


class Gemini:
    """Vertex express mode: API-key auth, no project or location."""

    def __init__(self, model: str):
        from google import genai

        from google.genai import types

        self.model = model
        # A hard timeout: the SDK's default is none, and one silent hang stalls
        # a whole run (found the first time the runner was left unattended).
        self._client = genai.Client(
            vertexai=True,
            api_key=settings.VERTEX_API_KEY,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )

    def generate(
        self, system: str, user: str, *, json_schema: Optional[dict] = None, temperature: float = 0.0
    ) -> LlmReply:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            **({"response_mime_type": "application/json", "response_json_schema": json_schema} if json_schema else {}),
        )
        retries = 0
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._client.models.generate_content(model=self.model, contents=user, config=config)
                break
            except errors.APIError as exc:
                if attempt == _MAX_ATTEMPTS or exc.code not in (429, 500, 502, 503, 504):
                    raise
                retries += 1
                time.sleep(min(2 ** attempt, 8))
            except (TimeoutError, OSError) as exc:  # the transport gave up
                if attempt == _MAX_ATTEMPTS:
                    raise RuntimeError(f"model call timed out after {_MAX_ATTEMPTS} attempts: {exc}") from exc
                retries += 1
                time.sleep(min(2 ** attempt, 8))
        usage = response.usage_metadata
        text = response.text or ""
        parsed = json.loads(text) if json_schema else None
        return LlmReply(
            text=text,
            parsed=parsed,
            tokens_input=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_output=getattr(usage, "candidates_token_count", 0) or 0,
            model=getattr(response, "model_version", None) or self.model,
            retries=retries,
        )


def simulator_llm() -> Gemini:
    return Gemini(settings.SIMULATOR_MODEL)


def judge_llm() -> Gemini:
    return Gemini(settings.JUDGE_MODEL)
