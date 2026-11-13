"""Linha de comando: `diligencia analisar`, `diligencia perguntar` e `diligencia ferramentas`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from due_diligence import __version__
from due_diligence.agentes import Investigador
from due_diligence.llm import MODELO_PADRAO, LLMError, OllamaLLM
from due_diligence.mcp_client import McpClient, McpError
from due_diligence.orquestrador import Orquestrador


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="diligencia",
        description="Due diligence de empresas brasileiras com agentes de IA (Ollama) e dados públicos (mcp-brasil).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("analisar", help="gera o relatório de due diligence de um ou mais CNPJs")
    a.add_argument("cnpjs", nargs="+", metavar="CNPJ")
    a.add_argument("--sem-ia", action="store_true", help="não usa LLM: só dados e regras de risco")
    a.add_argument("--modelo", help=f"modelo do Ollama (padrão: {MODELO_PADRAO} ou $DILIGENCIA_MODELO)")
    a.add_argument("--saida", type=Path, help="grava o relatório neste arquivo .md")
    a.add_argument("--json", action="store_true", help="imprime o resultado em JSON em vez de Markdown")
    a.add_argument("--max-revisoes", type=int, default=2, help="rodadas máximas entre redator e revisor (padrão: 2)")

    q = sub.add_parser("perguntar", help="faz uma pergunta livre; o agente escolhe as ferramentas")
    q.add_argument("pergunta", nargs="+")
    q.add_argument("--modelo", help=f"modelo do Ollama (padrão: {MODELO_PADRAO})")

    sub.add_parser("ferramentas", help="lista as ferramentas do servidor MCP")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # emojis e acentos no console do Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = _parser().parse_args(argv)
    hoje = date.today()

    try:
        with McpClient() as mcp:
            if args.comando == "ferramentas":
                info = mcp.server_info
                print(f"{info.get('name', 'servidor')} {info.get('version', '')}\n")
                for t in mcp.list_tools():
                    print(f"- {t['name']}: {t.get('description', '')}")
                return 0

            if args.comando == "perguntar":
                llm = OllamaLLM(modelo=args.modelo)
                agente = Investigador(mcp, llm, hoje, log=_log)
                resposta = agente.perguntar(" ".join(args.pergunta))
                print(resposta.texto)
                return 0

            llm = None if args.sem_ia else OllamaLLM(modelo=args.modelo)
            orq = Orquestrador(mcp, llm, hoje, max_revisoes=args.max_revisoes, log=_log)
            resultados = orq.analisar_varios(args.cnpjs)

            saida = (
                json.dumps([r.to_dict() for r in resultados], ensure_ascii=False, indent=2)
                if args.json
                else orq.relatorio(resultados)
            )
            if args.saida:
                args.saida.write_text(saida + "\n", encoding="utf-8")
                _log(f"Relatório salvo em {args.saida}")
            else:
                print(saida)
            return 0 if all(r.ok for r in resultados) else 1

    except (McpError, LLMError) as exc:
        _log(f"Erro: {exc}")
        return 2
    except KeyboardInterrupt:
        return 130
