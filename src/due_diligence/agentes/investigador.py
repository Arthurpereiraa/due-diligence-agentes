"""Agente investigador: responde perguntas livres decidindo sozinho quais ferramentas do mcp-brasil usar.

É o padrão clássico de agente com ferramentas (tool calling): o modelo pede uma ferramenta,
o programa executa, devolve o resultado e repete até o modelo responder.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from due_diligence.llm import LLM, ferramentas_mcp_para_llm
from due_diligence.mcp_client import McpClient, McpError

SISTEMA = """Você é um assistente que responde perguntas sobre empresas e dados públicos do Brasil.
Hoje é {hoje}.

- Use as ferramentas disponíveis para buscar dados; nunca invente CNPJs, valores, datas ou nomes.
- Se uma ferramenta retornar erro, explique o problema ao usuário.
- Para prazos e dias úteis, use as ferramentas de calendário em vez de contar manualmente.
- Responda em português do Brasil, de forma direta."""

MAX_RESULTADO = 6000  # caracteres por resultado de ferramenta, para não estourar o contexto de modelos locais


@dataclass
class Chamada:
    ferramenta: str
    argumentos: dict[str, Any]
    ok: bool


@dataclass
class RespostaAgente:
    texto: str
    chamadas: list[Chamada] = field(default_factory=list)


class Investigador:
    def __init__(
        self,
        mcp: McpClient,
        llm: LLM,
        hoje: date,
        max_passos: int = 8,
        log: Callable[[str], None] = lambda _: None,
    ) -> None:
        self.mcp = mcp
        self.llm = llm
        self.hoje = hoje
        self.max_passos = max_passos
        self.log = log

    def perguntar(self, pergunta: str) -> RespostaAgente:
        tools = ferramentas_mcp_para_llm(self.mcp.list_tools())
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SISTEMA.format(hoje=self.hoje.strftime("%d/%m/%Y"))},
            {"role": "user", "content": pergunta},
        ]
        chamadas: list[Chamada] = []

        for _ in range(self.max_passos):
            resposta = self.llm.chat(messages, tools=tools)
            if not resposta.tool_calls:
                return RespostaAgente(texto=resposta.content.strip(), chamadas=chamadas)

            messages.append(
                {
                    "role": "assistant",
                    "content": resposta.content,
                    "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}} for c in resposta.tool_calls],
                }
            )
            for call in resposta.tool_calls:
                self.log(f"[investigador] {call.name}({call.arguments})")
                try:
                    resultado, ok = self.mcp.call_tool(call.name, call.arguments), True
                except McpError as exc:
                    resultado, ok = f"ERRO: {exc}", False
                chamadas.append(Chamada(call.name, call.arguments, ok))
                messages.append({"role": "tool", "tool_name": call.name, "content": resultado[:MAX_RESULTADO]})

        return RespostaAgente(
            texto=f"Não consegui concluir a resposta em {self.max_passos} passos. Tente uma pergunta mais específica.",
            chamadas=chamadas,
        )
