"""Orquestrador: coordena os agentes no fluxo de due diligence.

    coletor ──► analista ──► redator ⇄ revisor ──► relatório
    (MCP)       (regras)     (LLM)     (regras + LLM)

O redator e o revisor conversam em ciclo: se o revisor encontra problemas, o redator reescreve,
até `max_revisoes` vezes. Se o texto ainda não for aprovado, o relatório sai com um aviso.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from due_diligence import relatorio
from due_diligence.agentes import Analista, Coletor, Redator, Revisor
from due_diligence.llm import LLM
from due_diligence.mcp_client import McpClient
from due_diligence.risco import AnaliseRisco


@dataclass
class Resultado:
    dossie: dict[str, Any]
    analise: AnaliseRisco | None = None
    parecer: str | None = None
    rodadas_revisao: list[list[str]] = field(default_factory=list)
    aprovado: bool = True

    @property
    def ok(self) -> bool:
        return self.analise is not None

    def markdown(self) -> str:
        if self.analise is None:
            return relatorio.parecer_erro(self.dossie)
        partes = [relatorio.parecer_modelo(self.dossie, self.analise)]
        if self.parecer:
            partes.append("### Parecer\n\n" + self.parecer)
            if not self.aprovado and self.rodadas_revisao:
                pendentes = "\n".join(f"> - {p}" for p in self.rodadas_revisao[-1])
                partes.append("> ⚠️ **A revisão automática não aprovou totalmente este texto.** Pontos pendentes:\n" + pendentes)
        return "\n\n".join(partes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dossie": self.dossie,
            "analise": self.analise.to_dict() if self.analise else None,
            "parecer": self.parecer,
            "aprovado": self.aprovado,
            "rodadas_revisao": self.rodadas_revisao,
        }


class Orquestrador:
    def __init__(
        self,
        mcp: McpClient,
        llm: LLM | None,
        hoje: date,
        max_revisoes: int = 2,
        log: Callable[[str], None] = lambda _: None,
    ) -> None:
        self.llm = llm
        self.hoje = hoje
        self.max_revisoes = max_revisoes
        self.log = log
        self.coletor = Coletor(mcp, log)
        self.analista = Analista(hoje)
        self.redator = Redator(llm) if llm else None
        self.revisor = Revisor(llm)

    def analisar(self, cnpj: str) -> Resultado:
        dossie = self.coletor.coletar(cnpj)
        if "erro" in dossie:
            self.log(f"[orquestrador] {dossie['erro']}")
            return Resultado(dossie=dossie, aprovado=False)

        analise = self.analista.analisar(dossie)
        self.log(f"[analista] risco {analise.nivel_geral_nome} ({len(analise.alertas)} alerta(s))")
        resultado = Resultado(dossie=dossie, analise=analise)
        if self.redator is None:
            return resultado

        parecer, problemas = None, None
        for rodada in range(1, self.max_revisoes + 2):
            self.log(f"[redator] escrevendo o parecer (versão {rodada})…")
            parecer = self.redator.escrever(dossie, analise, parecer, problemas)
            revisao = self.revisor.revisar(parecer, dossie, analise)
            if revisao.aprovado:
                self.log("[revisor] aprovado")
                resultado.aprovado = True
                break
            self.log(f"[revisor] {len(revisao.problemas)} problema(s) encontrado(s)")
            resultado.rodadas_revisao.append(revisao.problemas)
            resultado.aprovado = False
            problemas = revisao.problemas

        resultado.parecer = parecer
        return resultado

    def analisar_varios(self, cnpjs: list[str]) -> list[Resultado]:
        return [self.analisar(c) for c in cnpjs]

    def relatorio(self, resultados: list[Resultado]) -> str:
        modo = f"modelo {self.llm.nome}" if self.llm else "sem IA (somente regras)"
        cabecalho = f"# Relatório de due diligence\n\n_Gerado em {self.hoje.strftime('%d/%m/%Y')} · {modo}_"
        blocos = [cabecalho, *(r.markdown() for r in resultados)]
        if len(resultados) > 1:
            blocos.append(relatorio.tabela_comparativa(resultados))
        blocos.append(relatorio.AVISO_FINAL)
        return "\n\n---\n\n".join(blocos)
