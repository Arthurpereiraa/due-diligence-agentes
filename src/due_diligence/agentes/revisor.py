"""Agente revisor: confere se o parecer do redator é fiel aos fatos.

Duas camadas:
1. Verificação determinística: todo CNPJ, data e valor em R$ citado no texto precisa existir nos fatos,
   e o nível de risco mencionado precisa ser o calculado.
2. Revisão por LLM: pede ao modelo que aponte afirmações sem respaldo nos fatos (resposta em JSON).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from due_diligence.agentes.redator import montar_contexto
from due_diligence.llm import LLM, LLMError
from due_diligence.risco import AnaliseRisco

SISTEMA = """Você revisa pareceres de due diligence. Compare o PARECER com os FATOS fornecidos.

Aponte somente problemas reais:
- afirmações que não estão nos fatos ou que os contradizem;
- nível de risco diferente do informado;
- acusações de fraude ou juízo de intenção.

Responda apenas com JSON no formato: {"aprovado": true ou false, "problemas": ["descrição curta de cada problema"]}
Se não houver problemas, responda {"aprovado": true, "problemas": []}."""

RE_CNPJ = re.compile(r"\b[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}\b")
RE_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_REAIS = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")
RE_NIVEL = re.compile(r"risco(?:\s+geral)?\s*(?:é|e|:|de|foi\s+classificado\s+como|classificado\s+como)?\s*(baixo|medio|alto)\b")


@dataclass
class Revisao:
    aprovado: bool
    problemas: list[str] = field(default_factory=list)


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


def verificar_fatos(parecer: str, dossie: dict[str, Any], analise: AnaliseRisco) -> list[str]:
    fonte = montar_contexto(dossie, analise)
    problemas: list[str] = []

    if len(parecer.strip()) < 80:
        problemas.append("O parecer está vazio ou curto demais.")

    for cnpj in set(RE_CNPJ.findall(parecer)):
        if cnpj not in fonte:
            problemas.append(f"O CNPJ {cnpj} citado no parecer não corresponde aos fatos.")

    for data in set(RE_DATA.findall(parecer)):
        if data not in fonte:
            problemas.append(f"A data {data} citada no parecer não aparece nos fatos.")

    fonte_reais = {v.replace(" ", "") for v in RE_REAIS.findall(fonte)} | {"R$10.000", "R$10.000,00"}
    for valor in set(RE_REAIS.findall(parecer)):
        if valor.replace(" ", "") not in fonte_reais:
            problemas.append(f"O valor {valor} citado no parecer não aparece nos fatos.")

    esperado = _sem_acento(analise.nivel_geral_nome)
    for citado in set(RE_NIVEL.findall(_sem_acento(parecer))):
        if citado != esperado:
            problemas.append(f"O parecer menciona risco {citado}, mas o risco geral calculado é {analise.nivel_geral_nome}.")

    return problemas


def _extrair_json(texto: str) -> dict[str, Any] | None:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio >= 0 and fim > inicio:
            try:
                return json.loads(texto[inicio : fim + 1])
            except json.JSONDecodeError:
                return None
    return None


class Revisor:
    def __init__(self, llm: LLM | None) -> None:
        self.llm = llm

    def revisar(self, parecer: str, dossie: dict[str, Any], analise: AnaliseRisco) -> Revisao:
        problemas = verificar_fatos(parecer, dossie, analise)

        if self.llm is not None:
            pedido = f"FATOS:\n{montar_contexto(dossie, analise)}\n\nPARECER:\n{parecer}"
            try:
                resposta = self.llm.chat(
                    [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}], json_mode=True
                )
                dados = _extrair_json(resposta.content)
                if dados and dados.get("aprovado") is False:
                    problemas.extend(str(p) for p in dados.get("problemas") or [] if str(p).strip())
            except LLMError:
                pass  # sem revisão por LLM, a verificação determinística continua valendo

        # remove duplicados mantendo a ordem
        problemas = list(dict.fromkeys(problemas))
        return Revisao(aprovado=not problemas, problemas=problemas)
