from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from due_diligence.llm import Resposta
from due_diligence.mcp_client import McpClient

FAKE_SERVER = Path(__file__).with_name("fake_mcp_server.py")
FAKE_SERVER_CMD = [sys.executable, str(FAKE_SERVER)]
HOJE = date(2026, 11, 13)

CNPJ_OK = "11.222.333/0001-81"
CNPJ_RISCO = "98.765.432/0001-98"
CNPJ_INEXISTENTE = "12.345.678/0001-95"


@pytest.fixture
def mcp():
    with McpClient(FAKE_SERVER_CMD, timeout=10) as client:
        yield client


class FakeLLM:
    """LLM roteirizado. Separa as respostas do redator e do revisor pelo prompt de sistema."""

    nome = "fake/teste"

    def __init__(
        self,
        redator: list[str] | None = None,
        revisor: list[str] | None = None,
        geral: list[Resposta | Callable[[list[dict[str, Any]]], Resposta]] | None = None,
    ) -> None:
        self.redator = list(redator or [])
        self.revisor = list(revisor or [])
        self.geral = list(geral or [])
        self.chamadas: list[dict[str, Any]] = []

    def chat(self, messages, tools=None, json_mode=False):
        self.chamadas.append({"messages": [dict(m) for m in messages], "tools": tools, "json_mode": json_mode})
        sistema = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        if sistema.startswith("Você revisa"):
            return Resposta(self.revisor.pop(0) if self.revisor else '{"aprovado": true, "problemas": []}')
        if sistema.startswith("Você é analista"):
            return Resposta(self.redator.pop(0))
        item = self.geral.pop(0)
        return item(messages) if callable(item) else item


@pytest.fixture
def fake_llm_cls():
    return FakeLLM
