"""Agente redator (LLM): escreve a parte interpretativa do parecer a partir dos fatos e alertas."""

from __future__ import annotations

from typing import Any

from due_diligence import relatorio
from due_diligence.llm import LLM
from due_diligence.risco import AnaliseRisco, recomendacoes

SISTEMA = """Você é analista de compliance e escreve pareceres de due diligence de fornecedores brasileiros.

Escreva APENAS a seção de parecer, que vai abaixo de uma tabela de fatos que o leitor já tem.

Formato obrigatório:
- Comece direto no primeiro parágrafo. NÃO escreva título, cabeçalho nem frase em negrito no início.
- 2 parágrafos curtos interpretando os alertas: o que eles significam na prática para quem vai contratar.
- Depois, a linha "**Recomendações:**" seguida de 2 a 4 itens com "- ", escolhidos e adaptados da lista
  RECOMENDAÇÕES SUGERIDAS. Não crie recomendações genéricas fora dessa lista.

Regras de conteúdo:
- Use somente as informações fornecidas. Não invente números, datas, nomes, CNPJs nem fatos.
- Os dados NÃO trazem informação sobre saúde financeira, faturamento, lucro, funcionários, reputação,
  qualidade dos serviços nem posição de mercado. NÃO comente nada disso.
- O nível de risco geral já foi calculado e NÃO pode ser alterado; mencione-o exatamente como informado.
- Não acuse a empresa de fraude nem faça juízo de intenção; descreva riscos.
- Português do Brasil, tom profissional e objetivo."""


def montar_contexto(dossie: dict[str, Any], analise: AnaliseRisco) -> str:
    return (
        f"EMPRESA: {relatorio.nome_empresa(dossie)}\n\n"
        f"FATOS:\n{relatorio.bloco_fatos(dossie, analise)}\n\n"
        f"ALERTAS:\n{relatorio.bloco_alertas(analise)}\n\n"
        f"QUADRO SOCIETÁRIO:\n{relatorio.bloco_socios(dossie)}\n\n"
        f"NÍVEL DE RISCO GERAL: {analise.nivel_geral_nome}"
    )


def montar_pedido(dossie: dict[str, Any], analise: AnaliseRisco) -> str:
    sugestoes = "\n".join(f"- {r}" for r in recomendacoes(analise))
    return f"{montar_contexto(dossie, analise)}\n\nRECOMENDAÇÕES SUGERIDAS:\n{sugestoes}"


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
        pedido = montar_pedido(dossie, analise)
        if versao_anterior and problemas:
            pedido += (
                "\n\nSUA VERSÃO ANTERIOR:\n"
                + versao_anterior
                + "\n\nO REVISOR APONTOU ESTES PROBLEMAS:\n"
                + "\n".join(f"- {p}" for p in problemas)
                + "\n\nReescreva o parecer corrigindo todos os problemas e seguindo o formato obrigatório."
            )
        else:
            pedido += "\n\nEscreva o parecer."
        resposta = self.llm.chat([{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}])
        return resposta.content.strip()
