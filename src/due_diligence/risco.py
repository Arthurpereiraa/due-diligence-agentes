"""Regras de risco determinísticas.

O nível de risco é calculado por código, e não pelo modelo de linguagem: assim ele é reproduzível,
testável e não depende de o modelo "acertar a conta". O LLM entra depois, para explicar os achados em texto.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Literal

Nivel = Literal["alto", "medio", "info"]
ORDEM = {"alto": 0, "medio": 1, "info": 2}
NOME_NIVEL_GERAL = {"alto": "Alto", "medio": "Médio", "baixo": "Baixo"}


@dataclass
class Alerta:
    nivel: Nivel
    codigo: str
    mensagem: str


@dataclass
class AnaliseRisco:
    nivel_geral: Literal["alto", "medio", "baixo"]
    alertas: list[Alerta] = field(default_factory=list)
    idade_meses: int | None = None

    @property
    def nivel_geral_nome(self) -> str:
        return NOME_NIVEL_GERAL[self.nivel_geral]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "nivel_geral_nome": self.nivel_geral_nome}


def _data(valor: Any) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def meses_entre(inicio: date, fim: date) -> int:
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month) - (1 if fim.day < inicio.day else 0)


def idade_por_extenso(meses: int) -> str:
    anos, resto = divmod(max(meses, 0), 12)
    partes = []
    if anos:
        partes.append(f"{anos} ano{'s' if anos != 1 else ''}")
    if resto or not anos:
        partes.append(f"{resto} {'mês' if resto == 1 else 'meses'}")
    return " e ".join(partes)


def _normalizar(texto: Any) -> str:
    sem_acento = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def analisar(dossie: dict[str, Any], hoje: date) -> AnaliseRisco:
    empresa: dict[str, Any] = dossie.get("empresa") or {}
    alertas: list[Alerta] = []

    situacao = str(empresa.get("descricao_situacao_cadastral") or "").upper()
    if situacao and situacao != "ATIVA":
        alertas.append(Alerta("alto", "situacao_irregular", f"Situação cadastral {situacao} na Receita Federal."))

    idade = None
    if inicio := _data(empresa.get("data_inicio_atividade")):
        idade = meses_entre(inicio, hoje)
        if idade < 6:
            alertas.append(Alerta("alto", "empresa_muito_nova", f"Empresa aberta há {idade_por_extenso(idade)}."))
        elif idade < 24:
            alertas.append(Alerta("medio", "empresa_nova", f"Empresa aberta há {idade_por_extenso(idade)} (menos de 2 anos)."))

    if (mudanca := _data(empresa.get("data_situacao_cadastral"))) and inicio and mudanca > inicio:
        dias = (hoje - mudanca).days
        if 0 <= dias <= 90:
            alertas.append(Alerta("medio", "situacao_mudou", f"A situação cadastral mudou há {dias} dias."))

    if empresa.get("opcao_pelo_mei") is True:
        alertas.append(
            Alerta(
                "medio",
                "mei",
                "Optante pelo MEI: há limite anual de faturamento; contratos de valor alto podem ser incompatíveis.",
            )
        )

    capital = empresa.get("capital_social")
    porte = _normalizar(empresa.get("porte"))
    if isinstance(capital, (int, float)) and capital < 10_000 and porte == "DEMAIS":
        alertas.append(Alerta("medio", "capital_baixo", "Capital social abaixo de R$ 10.000 para uma empresa de porte DEMAIS."))

    endereco = dossie.get("endereco_cep") or {}
    cidade_receita, uf_receita = _normalizar(empresa.get("municipio")), _normalizar(empresa.get("uf"))
    cidade_cep, uf_cep = _normalizar(endereco.get("city")), _normalizar(endereco.get("state"))
    if cidade_receita and cidade_cep and (cidade_receita != cidade_cep or (uf_receita and uf_cep and uf_receita != uf_cep)):
        alertas.append(
            Alerta(
                "medio",
                "endereco_inconsistente",
                f"O CEP cadastrado pertence a {endereco.get('city')}/{endereco.get('state')}, "
                f"mas o município informado na Receita é {empresa.get('municipio')}/{empresa.get('uf')}.",
            )
        )

    if not empresa.get("email") and not empresa.get("ddd_telefone_1"):
        alertas.append(Alerta("info", "sem_contato", "Nenhum e-mail ou telefone cadastrado na Receita."))

    natureza = _normalizar(empresa.get("natureza_juridica"))
    individual = "INDIVIDUAL" in natureza or empresa.get("opcao_pelo_mei") is True
    if empresa and not empresa.get("socios") and not individual:
        alertas.append(Alerta("info", "sem_socios", "Nenhum sócio listado no quadro societário."))

    alertas.sort(key=lambda a: ORDEM[a.nivel])
    niveis = {a.nivel for a in alertas}
    geral = "alto" if "alto" in niveis else "medio" if "medio" in niveis else "baixo"
    return AnaliseRisco(nivel_geral=geral, alertas=alertas, idade_meses=idade)
