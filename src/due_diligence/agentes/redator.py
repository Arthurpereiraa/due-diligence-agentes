"""Agente redator (LLM): escreve a parte interpretativa do parecer a partir dos fatos e alertas."""

from __future__ import annotations

from typing import Any

from due_diligence import relatorio
from due_diligence.llm import LLM
from due_diligence.risco import AnaliseRisco

SISTEMA = """Você é analista de compliance e escreve pareceres de due diligence de fornecedores brasileiros.

Escreva APENAS a seção de parecer, que vai abaixo de uma tabela de fatos que o leitor já tem.

Regras obrigatórias:
- Use somente as informações fornecidas. Não invente números, datas, nomes, CNPJs nem fatos.
- O nível de risco geral já foi calculado e NÃO pode ser alterado; mencione-o exatamente como informado.
- Não repita a tabela de fatos. Interprete: o que os alertas significam na prática para quem vai contratar.
- Formato: 2 a 3 parágrafos curtos, seguidos de uma lista "**Recomendações:**" com 2 a 4 itens objetivos.
- Não acuse a empresa de fraude nem faça juízo de intenção; descreva riscos.
- Escreva em português do Brasil, em tom profissional. Não use títulos (#)."""


def montar_contexto(dossie: dict[str, Any], analise: AnaliseRisco) -> str:
    return (
        f"EMPRESA: {relatorio.nome_empresa(dossie)}\n\n"
        f"FATOS:\n{relatorio.bloco_fatos(dossie, analise)}\n\n"
        f"ALERTAS:\n{relatorio.bloco_alertas(analise)}\n\n"
        f"QUADRO SOCIETÁRIO:\n{relatorio.bloco_socios(dossie)}\n\n"
        f"NÍVEL DE RISCO GERAL: {analise.nivel_geral_nome}"
    )


class Redator:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def escrever(
        self,
        dossie: dict[str, Any],
        analise: AnaliseRisco,
        versao_anterior: str | None = None,
        problemas: list[str] | None = None,
    ) -> str:
        pedido = montar_contexto(dossie, analise)
        if versao_anterior and problemas:
            pedido += (
                "\n\nSUA VERSÃO ANTERIOR:\n"
                + versao_anterior
                + "\n\nO REVISOR APONTOU ESTES PROBLEMAS:\n"
                + "\n".join(f"- {p}" for p in problemas)
                + "\n\nReescreva o parecer corrigindo todos os problemas."
            )
        else:
            pedido += "\n\nEscreva o parecer."
        resposta = self.llm.chat([{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}])
        return resposta.content.strip()
