"""Servidor MCP falso para os testes: responde como o mcp-brasil, com dados fixos e sem internet."""

import json
import sys

EMPRESAS = {
    # Empresa antiga, ativa e regular → risco baixo
    "11222333000181": {
        "cnpj": "11222333000181",
        "razao_social": "EMPRESA EXEMPLO LTDA",
        "nome_fantasia": "EXEMPLO",
        "descricao_situacao_cadastral": "ATIVA",
        "data_situacao_cadastral": "2005-03-10",
        "data_inicio_atividade": "2005-03-10",
        "natureza_juridica": "Sociedade Empresária Limitada",
        "porte": "DEMAIS",
        "capital_social": 500000,
        "cnae_fiscal": 6201501,
        "cnae_fiscal_descricao": "Desenvolvimento de programas de computador sob encomenda",
        "opcao_pelo_simples": False,
        "opcao_pelo_mei": False,
        "logradouro": "AVENIDA PAULISTA",
        "numero": "1000",
        "bairro": "BELA VISTA",
        "municipio": "SAO PAULO",
        "uf": "SP",
        "cep": "01310100",
        "ddd_telefone_1": "1133334444",
        "email": "contato@exemplo.com.br",
        "cnpj_formatado": "11.222.333/0001-81",
        "socios": [
            {"nome_socio": "FULANO DE TAL", "qualificacao_socio": "Sócio-Administrador", "data_entrada_sociedade": "2005-03-10"}
        ],
    },
    # Empresa nova, MEI, sem contato e com CEP de outra cidade → risco alto
    "98765432000198": {
        "cnpj": "98765432000198",
        "razao_social": "NOVA SOLUCOES MEI",
        "descricao_situacao_cadastral": "ATIVA",
        "data_situacao_cadastral": "2026-09-01",
        "data_inicio_atividade": "2026-09-01",
        "natureza_juridica": "Empresário (Individual)",
        "porte": "MICRO EMPRESA",
        "capital_social": 1000,
        "cnae_fiscal": 7319002,
        "cnae_fiscal_descricao": "Promoção de vendas",
        "opcao_pelo_simples": True,
        "opcao_pelo_mei": True,
        "logradouro": "RUA A",
        "numero": "1",
        "bairro": "CENTRO",
        "municipio": "CAMPINAS",
        "uf": "SP",
        "cep": "01310100",
        "cnpj_formatado": "98.765.432/0001-98",
        "socios": [],
    },
}

CEPS = {"01310100": {"cep": "01310100", "state": "SP", "city": "São Paulo", "street": "Avenida Paulista"}}

TOOLS = [
    {"name": n, "description": f"Ferramenta {n} (falsa)", "inputSchema": {"type": "object", "properties": {}}}
    for n in ["validar_documento", "consultar_cnpj", "consultar_cep", "calcular_prazo"]
]


def cnpj_valido(c: str) -> bool:
    c = "".join(ch for ch in c.upper() if ch.isalnum())
    if len(c) != 14 or len(set(c)) == 1:
        return False

    def dv(base, pesos):
        s = sum((ord(ch) - 48) * p for ch, p in zip(base, pesos, strict=False))
        r = s % 11
        return 0 if r < 2 else 11 - r

    d1 = dv(c[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = dv(c[:12] + str(d1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return c[12:] == f"{d1}{d2}"


def fmt(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def call(name, args):
    if name == "validar_documento":
        c = "".join(ch for ch in str(args.get("documento", "")).upper() if ch.isalnum())
        ok = cnpj_valido(c)
        return {
            "tipo": "cnpj",
            "valido": ok,
            "formatado": fmt(c) if ok else None,
            **({} if ok else {"motivo": "Os dígitos verificadores não conferem."}),
        }, False
    if name == "consultar_cnpj":
        c = "".join(ch for ch in str(args.get("cnpj", "")) if ch.isalnum())
        return (EMPRESAS[c], False) if c in EMPRESAS else ("CNPJ não encontrado na base da Receita.", True)
    if name == "consultar_cep":
        cep = "".join(ch for ch in str(args.get("cep", "")) if ch.isdigit())
        return (CEPS[cep], False) if cep in CEPS else ("CEP não encontrado.", True)
    if name == "calcular_prazo":
        return {"data_final": "2026-11-26", "dia_semana": "quinta-feira"}, False
    return f"Ferramenta desconhecida: {name}", True


sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

for line in sys.stdin:
    if not line.strip():
        continue
    msg = json.loads(line)
    if "id" not in msg:
        continue
    method = msg["method"]
    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake-mcp-brasil", "version": "0.0.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        data, is_error = call(msg["params"]["name"], msg["params"].get("arguments") or {})
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        result = {"content": [{"type": "text", "text": text}], **({"isError": True} if is_error else {})}
    else:
        print(
            json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Método não suportado"}}),
            flush=True,
        )
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}, ensure_ascii=False), flush=True)
