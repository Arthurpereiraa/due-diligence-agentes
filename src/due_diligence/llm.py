"""Interface com o modelo de linguagem. A implementação padrão usa o Ollama (local e gratuito) pela API HTTP.

Qualquer objeto com o método `chat` serve como LLM, o que permite trocar de provedor
ou usar um LLM falso nos testes.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

MODELO_PADRAO = "qwen2.5:7b"


class LLMError(RuntimeError):
    pass


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class Resposta:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLM(Protocol):
    nome: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> Resposta: ...


def ferramentas_mcp_para_llm(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte a lista `tools/list` do MCP para o formato de function calling do Ollama/OpenAI."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


class OllamaLLM:
    def __init__(
        self,
        modelo: str | None = None,
        host: str | None = None,
        temperature: float = 0.2,
        timeout: float = 600.0,
    ) -> None:
        self.modelo = modelo or os.environ.get("DILIGENCIA_MODELO") or MODELO_PADRAO
        self.host = (host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        if not self.host.startswith("http"):
            self.host = f"http://{self.host}"
        self.temperature = temperature
        self.timeout = timeout

    @property
    def nome(self) -> str:
        return f"ollama/{self.modelo}"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> Resposta:
        payload: dict[str, Any] = {
            "model": self.modelo,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if tools:
            payload["tools"] = tools
        if json_mode:
            payload["format"] = "json"

        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code == 404 or "not found" in detail.lower():
                raise LLMError(f"Modelo {self.modelo!r} não encontrado no Ollama. Rode: ollama pull {self.modelo}") from exc
            raise LLMError(f"Ollama respondeu HTTP {exc.code}: {detail[:300]}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise LLMError(
                f"Não consegui falar com o Ollama em {self.host}. Ele está aberto? (rode `ollama serve` ou abra o app)"
            ) from exc

        message = body.get("message") or {}
        calls = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):  # alguns modelos devolvem os argumentos como texto JSON
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(name=fn.get("name", ""), arguments=args))
        return Resposta(content=message.get("content", "") or "", tool_calls=calls)
