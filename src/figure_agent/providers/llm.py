from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class LLMProvider(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


class UnavailableLLM:
    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("no LLM provider is configured")


@dataclass
class MockLLM:
    response: dict[str, Any]

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return dict(self.response)


@dataclass
class OpenAICompatibleLLM:
    base_url: str
    api_key: str
    model: str
    timeout: float = 60.0

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        result = json.loads(content) if isinstance(content, str) else content
        if not isinstance(result, dict):
            raise ValueError("LLM response must be a JSON object")
        _validate_contract_shape(result, schema)
        return result


def _validate_contract_shape(value: dict[str, Any], schema: dict[str, Any]) -> None:
    required = schema.get("required", [])
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError(f"LLM response is missing required fields: {', '.join(missing)}")
