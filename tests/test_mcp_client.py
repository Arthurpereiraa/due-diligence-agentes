import sys

import pytest

from conftest import CNPJ_INEXISTENTE, CNPJ_OK
from due_diligence.mcp_client import McpClient, McpError, ToolError, comando_padrao


def test_handshake_e_lista_de_ferramentas(mcp):
    assert mcp.server_info["name"] == "fake-mcp-brasil"
    nomes = [t["name"] for t in mcp.list_tools()]
    assert "consultar_cnpj" in nomes


def test_call_json_devolve_dados(mcp):
    dados = mcp.call_json("validar_documento", {"documento": CNPJ_OK})
    assert dados == {"tipo": "cnpj", "valido": True, "formatado": CNPJ_OK}


def test_erro_da_ferramenta_vira_tool_error(mcp):
    with pytest.raises(ToolError, match="não encontrado"):
        mcp.call_tool("consultar_cnpj", {"cnpj": CNPJ_INEXISTENTE})


def test_comando_inexistente_da_erro_claro():
    with pytest.raises(McpError, match="Não encontrei o comando"), McpClient(["comando-que-nao-existe-123"]):
        pass


def test_servidor_que_morre_no_handshake():
    with pytest.raises(McpError, match="encerrou"), McpClient([sys.executable, "-c", "pass"], timeout=5):
        pass


def test_comando_padrao_respeita_variavel(monkeypatch):
    monkeypatch.setenv("MCP_BRASIL_CMD", "node ../mcp-brasil/dist/index.js")
    assert comando_padrao() == ["node", "../mcp-brasil/dist/index.js"]
    monkeypatch.delenv("MCP_BRASIL_CMD")
    assert comando_padrao()[-2:] == ["-y", "mcp-brasil@0"]


SERVIDOR_CP1252 = r"""
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"serverInfo": {"name": "cp1252"}}
    else:
        result = {"content": [{"type": "text", "text": "não encontrado"}], "isError": True}
    out = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(out.encode("cp1252"))
    sys.stdout.buffer.flush()
"""


def test_saida_em_cp1252_nao_trava_o_cliente():
    """Regressão: no Windows, um servidor que escreve em cp1252 derrubava a thread de leitura."""
    with McpClient([sys.executable, "-c", SERVIDOR_CP1252], timeout=5) as client, pytest.raises(ToolError, match="encontrado"):
        client.call_tool("qualquer")
