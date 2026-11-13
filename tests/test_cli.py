import pytest

from conftest import CNPJ_OK, CNPJ_RISCO, FAKE_SERVER_CMD
from due_diligence import cli
from due_diligence.cli import main
from due_diligence.mcp_client import McpClient


@pytest.fixture(autouse=True)
def servidor_falso(monkeypatch):
    monkeypatch.setattr(cli, "McpClient", lambda: McpClient(FAKE_SERVER_CMD, timeout=10))


def test_analisar_sem_ia(capsys):
    assert main(["analisar", CNPJ_OK, CNPJ_RISCO, "--sem-ia"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Relatório de due diligence")
    assert "## Comparativo" in out


def test_analisar_grava_arquivo_e_json(tmp_path, capsys):
    destino = tmp_path / "relatorio.md"
    assert main(["analisar", CNPJ_OK, "--sem-ia", "--saida", str(destino)]) == 0
    assert "EMPRESA EXEMPLO LTDA" in destino.read_text(encoding="utf-8")

    assert main(["analisar", CNPJ_OK, "--sem-ia", "--json"]) == 0
    assert '"nivel_geral": "baixo"' in capsys.readouterr().out


def test_codigo_de_saida_1_quando_algum_cnpj_falha():
    assert main(["analisar", "123", "--sem-ia"]) == 1


def test_ferramentas(capsys):
    assert main(["ferramentas"]) == 0
    assert "consultar_cnpj" in capsys.readouterr().out


def test_ollama_desligado_retorna_2(monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    assert main(["analisar", CNPJ_OK]) == 2
    assert "Ollama" in capsys.readouterr().err
