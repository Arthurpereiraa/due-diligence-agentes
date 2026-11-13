from conftest import CNPJ_INEXISTENTE, CNPJ_OK, CNPJ_RISCO, HOJE
from due_diligence.orquestrador import Orquestrador

PARECER_BOM = (
    "A Empresa Exemplo opera desde 10/03/2005, com capital social de R$ 500.000,00, e não apresenta alertas "
    "nos dados públicos consultados. O risco geral é baixo.\n\n**Recomendações:**\n- Solicitar certidões negativas."
)
PARECER_RUIM = PARECER_BOM.replace("O risco geral é baixo", "O risco geral é alto")


def test_sem_ia_usa_so_dados_e_regras(mcp):
    orq = Orquestrador(mcp, llm=None, hoje=HOJE)
    [r] = orq.analisar_varios([CNPJ_RISCO])
    assert r.analise.nivel_geral == "alto"
    assert {a.codigo for a in r.analise.alertas} >= {"empresa_muito_nova", "mei", "endereco_inconsistente"}
    md = orq.relatorio([r])
    assert "NOVA SOLUCOES MEI" in md
    assert "🔴 Alto" in md
    assert "### Parecer" not in md
    assert "sem IA" in md


def test_cnpj_invalido_e_inexistente(mcp):
    orq = Orquestrador(mcp, llm=None, hoje=HOJE)
    invalido, inexistente = orq.analisar_varios(["11.222.333/0001-82", CNPJ_INEXISTENTE])
    assert not invalido.ok and "inválido" in invalido.dossie["erro"]
    assert not inexistente.ok and "não encontrado" in inexistente.dossie["erro"]


def test_redator_e_revisor_em_ciclo_ate_aprovar(mcp, fake_llm_cls):
    llm = fake_llm_cls(redator=[PARECER_RUIM, PARECER_BOM])
    orq = Orquestrador(mcp, llm=llm, hoje=HOJE)
    r = orq.analisar(CNPJ_OK)
    assert r.aprovado is True
    assert r.parecer == PARECER_BOM
    assert len(r.rodadas_revisao) == 1
    assert "risco alto" in r.rodadas_revisao[0][0]

    # a segunda chamada ao redator recebeu a versão anterior e os problemas apontados
    pedidos_redator = [c for c in llm.chamadas if c["messages"][0]["content"].startswith("Você é analista")]
    assert "O REVISOR APONTOU" in pedidos_redator[1]["messages"][1]["content"]
    assert "### Parecer" in orq.relatorio([r])


def test_parecer_nunca_aprovado_sai_com_aviso(mcp, fake_llm_cls):
    llm = fake_llm_cls(redator=[PARECER_RUIM] * 3)
    r = Orquestrador(mcp, llm=llm, hoje=HOJE, max_revisoes=2).analisar(CNPJ_OK)
    assert r.aprovado is False
    assert len(r.rodadas_revisao) == 3
    assert "não aprovou totalmente" in r.markdown()


def test_comparativo_com_varios_cnpjs(mcp):
    orq = Orquestrador(mcp, llm=None, hoje=HOJE)
    md = orq.relatorio(orq.analisar_varios([CNPJ_OK, CNPJ_RISCO, "123"]))
    assert "## Comparativo" in md
    assert "EMPRESA EXEMPLO LTDA" in md and "🟢 Baixo" in md
    assert "❌" in md
