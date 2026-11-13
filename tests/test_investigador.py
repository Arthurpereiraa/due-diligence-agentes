from conftest import CNPJ_INEXISTENTE, HOJE
from due_diligence.agentes import Investigador
from due_diligence.llm import Resposta, ToolCall


def test_chama_ferramenta_e_responde_com_o_resultado(mcp, fake_llm_cls):
    def responder(messages):
        resultado = messages[-1]
        assert resultado["role"] == "tool" and resultado["tool_name"] == "calcular_prazo"
        assert "2026-11-26" in resultado["content"]
        return Resposta("O vencimento é quinta-feira, 26/11/2026.")

    llm = fake_llm_cls(
        geral=[
            Resposta("", [ToolCall("calcular_prazo", {"data_inicio": "2026-11-18", "dias": 5})]),
            responder,
        ]
    )
    r = Investigador(mcp, llm, HOJE).perguntar("Qual o vencimento de 5 dias úteis a partir de 18/11/2026?")
    assert r.texto == "O vencimento é quinta-feira, 26/11/2026."
    assert [(c.ferramenta, c.ok) for c in r.chamadas] == [("calcular_prazo", True)]

    primeira = llm.chamadas[0]
    assert "13/11/2026" in primeira["messages"][0]["content"]
    assert {t["function"]["name"] for t in primeira["tools"]} >= {"consultar_cnpj", "calcular_prazo"}


def test_erro_de_ferramenta_volta_para_o_modelo(mcp, fake_llm_cls):
    llm = fake_llm_cls(
        geral=[
            Resposta("", [ToolCall("consultar_cnpj", {"cnpj": CNPJ_INEXISTENTE})]),
            lambda msgs: Resposta("Não encontrei esse CNPJ." if msgs[-1]["content"].startswith("ERRO") else "?"),
        ]
    )
    r = Investigador(mcp, llm, HOJE).perguntar("Quem é a empresa 12.345.678/0001-95?")
    assert r.texto == "Não encontrei esse CNPJ."
    assert r.chamadas[0].ok is False


def test_limite_de_passos(mcp, fake_llm_cls):
    loop = Resposta("", [ToolCall("calcular_prazo", {})])
    r = Investigador(mcp, fake_llm_cls(geral=[loop] * 3), HOJE, max_passos=3).perguntar("?")
    assert "3 passos" in r.texto
    assert len(r.chamadas) == 3
