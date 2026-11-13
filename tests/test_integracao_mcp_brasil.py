"""Integração com o mcp-brasil de verdade (via npx ou MCP_BRASIL_CMD).

Só roda com INTEGRACAO_MCP=1, porque precisa do Node.js e, com npx, de acesso ao npm.
Usa apenas ferramentas offline, para não depender da BrasilAPI no CI.
"""

import os

import pytest

from due_diligence.mcp_client import McpClient, ToolError

pytestmark = pytest.mark.skipif(os.environ.get("INTEGRACAO_MCP") != "1", reason="defina INTEGRACAO_MCP=1")


def test_mcp_brasil_real():
    with McpClient(timeout=120) as mcp:
        assert mcp.server_info["name"] == "mcp-brasil"
        nomes = {t["name"] for t in mcp.list_tools()}
        assert {"consultar_cnpj", "validar_documento", "calcular_prazo"} <= nomes

        assert mcp.call_json("validar_documento", {"documento": "12.ABC.345/01DE-35"})["valido"] is True
        with pytest.raises(ToolError):
            mcp.call_tool("consultar_cep", {"cep": "123"})
