"""LLM provider abstraction.

Priority: an explicit LLM_PROVIDER choice, else auto-detect (Ollama local
first, then an OpenAI-compatible endpoint). Privacy defaults to local-only:
when no provider is reachable the pipeline runs in deterministic mode and no
data ever leaves the machine.
"""
from __future__ import annotations
import json
import re

import httpx

from ..config import settings

SYSTEM_GUARDRAIL = (
    "You are a CV tailoring assistant. ABSOLUTE RULES, no exceptions: never add "
    "a skill, tool, technology, certification, language, company, job title, "
    "date, metric, number, percentage or outcome that is not present in the "
    "source material provided. Never modify companies, titles or dates. Only "
    "rephrase, reorder, select subsets, and mirror JD vocabulary when the user "
    "genuinely has equivalent experience. Preserve the user's voice and typical "
    "sentence length. Output only what is asked, no commentary."
)


class LlmUnavailable(Exception):
    pass


class BaseProvider:
    name = "base"
    local = True

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        raise NotImplementedError

    def complete_json(self, system: str, user: str):
        text = self.complete(system, user, json_mode=True)
        return _extract_json(text)


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"[{\[]", text)
        if match:
            return json.loads(text[match.start():text.rfind("}") + text.rfind("]") + 2])
        raise


class OllamaProvider(BaseProvider):
    name = "ollama"
    local = True

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "options": {"temperature": 0.2},
        }
        if json_mode:
            payload["format"] = "json"
        r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"]


class OpenAICompatProvider(BaseProvider):
    """Any OpenAI-compatible endpoint (cloud or local like LM Studio / vLLM).

    For cloud use, configure a no-training / enterprise endpoint; the UI
    discloses which provider mode is active.
    """
    name = "openai-compatible"
    local = False

    def __init__(self):
        self.base_url = settings.OPENAI_BASE_URL.rstrip("/")
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

    def available(self) -> bool:
        return bool(self.base_url and self.model)

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json=body, timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


_provider: BaseProvider | None = None


def get_provider() -> BaseProvider | None:
    global _provider
    if _provider is not None:
        return _provider
    choice = settings.LLM_PROVIDER.lower()
    candidates: list[BaseProvider] = []

    def register(cls, *args, **kwargs):
        try:
            p = cls(*args, **kwargs)
            if p.available():
                candidates.append(p)
        except Exception:  # noqa: BLE001
            pass
        return None

    if choice in ("ollama", "auto"):
        register(OllamaProvider)
    if choice in ("openai", "auto") and not any(isinstance(c, OpenAICompatProvider) for c in candidates):
        register(OpenAICompatProvider)
    if choice == "none":
        _provider = None
        return None
    _provider = candidates[0] if candidates else None
    return _provider


def reset_provider():
    global _provider
    _provider = None


def provider_status() -> dict:
    p = get_provider()
    if p is None:
        return {"mode": "deterministic", "name": None,
                "note": "No LLM configured — running fully local deterministic tailoring. "
                        "Vocabulary mirroring is conservative and traceable."}
    return {"mode": "local" if p.local else "cloud",
            "name": p.name,
            "note": "Local LLM — your data never leaves this machine." if p.local
                    else settings.NO_TRAINING_NOTE}
