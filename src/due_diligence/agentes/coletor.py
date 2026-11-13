"""Agente coletor: reúne os dados públicos da empresa usando as ferramentas do mcp-brasil.

É determinístico de propósito: buscar dados não exige criatividade, e modelos locais menores
erram com frequência ao decidir sozinhos quais ferramentas chamar.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from due_diligence.mcp_client import McpClient, ToolError


class Coletor:
    def __init__(self, mcp: McpClient, log: Callable[[str], None] = lambda _: None) -> None:
        self.mcp = mcp
        self.log = log

    def coletar(self, cnpj: str) -> dict[str, Any]:
        validacao = self.mcp.call_json("validar_documento", {"documento": cnpj, "tipo": "cnpj"})
        if not validacao.get("valido"):
            return {"cnpj": cnpj, "erro": f"CNPJ inválido: {validacao.get('motivo', 'dígitos verificadores não conferem')}"}

        formatado = validacao["formatado"]
        self.log(f"[coletor] consultando {formatado} na Receita…")
        try:
            empresa = self.mcp.call_json("consultar_cnpj", {"cnpj": formatado})
        except ToolError as exc:
            return {"cnpj": formatado, "erro": f"Não foi possível consultar o CNPJ: {exc}"}

        dossie: dict[str, Any] = {"cnpj": formatado, "empresa": empresa, "avisos": []}

        # Cruzamento de fontes: o CEP da Receita bate com o município informado?
        if cep := empresa.get("cep"):
            self.log(f"[coletor] conferindo o CEP {cep}…")
            try:
                dossie["endereco_cep"] = self.mcp.call_json("consultar_cep", {"cep": str(cep)})
            except ToolError as exc:
                dossie["avisos"].append(f"Não foi possível conferir o CEP {cep}: {exc}")

        return dossie
