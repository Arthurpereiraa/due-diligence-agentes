"""Formatação em pt-BR e o parecer em modelo fixo (usado com --sem-ia ou como base factual para o redator)."""

from __future__ import annotations

from datetime import date
from typing import Any

from due_diligence.risco import AnaliseRisco, idade_por_extenso

ICONE_NIVEL = {"alto": "🔴", "medio": "🟡", "info": "⚪"}
ICONE_GERAL = {"alto": "🔴", "medio": "🟡", "baixo": "🟢"}


def brl(valor: Any) -> str:
    if not isinstance(valor, (int, float)):
        return "não informado"
    inteiro, centavos = f"{valor:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def data_br(valor: Any) -> str:
    try:
        return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "não informada"


def sim_nao(valor: Any) -> str:
    return "sim" if valor is True else "não" if valor is False else "não informado"


def endereco(empresa: dict[str, Any]) -> str:
    partes = [
        " ".join(p for p in [str(empresa.get("logradouro") or ""), str(empresa.get("numero") or "")] if p).strip(),
        str(empresa.get("bairro") or ""),
        "/".join(p for p in [str(empresa.get("municipio") or ""), str(empresa.get("uf") or "")] if p),
        f"CEP {empresa['cep']}" if empresa.get("cep") else "",
    ]
    return ", ".join(p for p in partes if p) or "não informado"


def nome_empresa(dossie: dict[str, Any]) -> str:
    empresa = dossie.get("empresa") or {}
    return str(empresa.get("razao_social") or dossie.get("cnpj") or "Empresa")


def fatos(dossie: dict[str, Any], analise: AnaliseRisco) -> list[tuple[str, str]]:
    """Os fatos da empresa já formatados: a mesma tabela serve ao parecer em modelo fixo e ao redator."""
    e = dossie.get("empresa") or {}
    abertura = data_br(e.get("data_inicio_atividade"))
    if analise.idade_meses is not None:
        abertura += f" ({idade_por_extenso(analise.idade_meses)})"
    return [
        ("CNPJ", str(dossie.get("cnpj"))),
        (
            "Situação",
            f"{e.get('descricao_situacao_cadastral') or 'não informada'} desde {data_br(e.get('data_situacao_cadastral'))}",
        ),
        ("Abertura", abertura),
        ("Porte / natureza", f"{e.get('porte') or 'não informado'} · {e.get('natureza_juridica') or 'não informada'}"),
        ("Capital social", brl(e.get("capital_social"))),
        ("Regime", f"Simples: {sim_nao(e.get('opcao_pelo_simples'))} · MEI: {sim_nao(e.get('opcao_pelo_mei'))}"),
        (
            "Atividade principal",
            f"{e.get('cnae_fiscal') or ''} – {e.get('cnae_fiscal_descricao') or 'não informada'}".strip(" –"),
        ),
        ("Endereço", endereco(e)),
    ]


def bloco_fatos(dossie: dict[str, Any], analise: AnaliseRisco) -> str:
    linhas = ["| Item | Valor |", "|---|---|", *(f"| {k} | {v} |" for k, v in fatos(dossie, analise))]
    return "\n".join(linhas)


def bloco_alertas(analise: AnaliseRisco) -> str:
    if not analise.alertas:
        return "- Nenhum alerta encontrado nos dados públicos."
    return "\n".join(f"- {ICONE_NIVEL[a.nivel]} {a.mensagem}" for a in analise.alertas)


def bloco_socios(dossie: dict[str, Any]) -> str:
    socios = (dossie.get("empresa") or {}).get("socios") or []
    if not socios:
        return "- Nenhum sócio listado."
    return "\n".join(
        f"- {s.get('nome_socio', '?')} – {s.get('qualificacao_socio', 'qualificação não informada')}"
        + (f" (desde {data_br(s['data_entrada_sociedade'])})" if s.get("data_entrada_sociedade") else "")
        for s in socios
    )


def titulo(dossie: dict[str, Any], analise: AnaliseRisco) -> str:
    e = dossie.get("empresa") or {}
    fantasia = f" ({e['nome_fantasia']})" if e.get("nome_fantasia") else ""
    return (
        f"## {nome_empresa(dossie)}{fantasia}\n"
        f"**CNPJ:** {dossie.get('cnpj')} · **Risco geral:** {ICONE_GERAL[analise.nivel_geral]} {analise.nivel_geral_nome}"
    )


def parecer_modelo(dossie: dict[str, Any], analise: AnaliseRisco) -> str:
    """Parecer sem IA: só fatos e alertas, sem texto interpretativo."""
    return "\n\n".join(
        [
            titulo(dossie, analise),
            bloco_fatos(dossie, analise),
            "### Alertas\n" + bloco_alertas(analise),
            "### Quadro societário\n" + bloco_socios(dossie),
        ]
    )


def parecer_erro(dossie: dict[str, Any]) -> str:
    return f"## {dossie.get('cnpj')}\n\n❌ {dossie.get('erro')}"


def tabela_comparativa(resultados: list[Any]) -> str:
    linhas = ["## Comparativo", "", "| Empresa | Situação | Abertura | Porte | Risco |", "|---|---|---|---|---|"]
    for r in resultados:
        if r.analise is None:
            linhas.append(f"| {r.dossie.get('cnpj')} | ❌ {r.dossie.get('erro')} | – | – | – |")
            continue
        e = r.dossie.get("empresa") or {}
        linhas.append(
            f"| {nome_empresa(r.dossie)} | {e.get('descricao_situacao_cadastral') or '–'} | "
            f"{data_br(e.get('data_inicio_atividade'))} | {e.get('porte') or '–'} | "
            f"{ICONE_GERAL[r.analise.nivel_geral]} {r.analise.nivel_geral_nome} |"
        )
    return "\n".join(linhas)


AVISO_FINAL = (
    "> Dados públicos da Receita Federal obtidos via BrasilAPI (servidor MCP mcp-brasil); podem ter alguns dias de atraso. "
    "Esta análise não substitui certidões negativas (CND federal, FGTS, trabalhista) nem consultas a protestos e processos judiciais."
)
