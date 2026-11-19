from due_diligence.agentes import Revisor
from due_diligence.agentes.revisor import verificar_fatos, verificar_formato
from due_diligence.llm import LLMError
from due_diligence.relatorio import brl, data_br
from due_diligence.risco import analisar
from test_risco import HOJE, empresa

DOSSIE = {**empresa(capital_social=500000, data_inicio_atividade="2010-01-01"), "cnpj": "11.222.333/0001-81"}
ANALISE = analisar(DOSSIE, HOJE)

BOM = (
    "A empresa está ativa desde 01/01/2010 e possui capital social de R$ 500.000,00, compatível com o porte informado. "
    "Não foram encontrados alertas nos dados públicos, e o risco geral é baixo.\n\n"
    "**Recomendações:**\n- Solicitar as certidões negativas antes de contratar.\n"
    "- Consultar protestos e processos judiciais em nome da empresa."
)


def test_formatadores():
    assert brl(500000) == "R$ 500.000,00"
    assert brl(1234.5) == "R$ 1.234,50"
    assert brl(None) == "não informado"
    assert data_br("2010-01-01") == "01/01/2010"


def test_parecer_fiel_passa():
    assert verificar_fatos(BOM, DOSSIE, ANALISE) == []


def test_detecta_data_inventada():
    problemas = verificar_fatos(BOM.replace("01/01/2010", "15/03/2012"), DOSSIE, ANALISE)
    assert any("15/03/2012" in p for p in problemas)


def test_detecta_valor_e_cnpj_inventados():
    texto = BOM + " O faturamento anual é de R$ 2.000.000,00 e há uma filial 99.999.999/0001-99."
    problemas = verificar_fatos(texto, DOSSIE, ANALISE)
    assert any("R$ 2.000.000,00" in p for p in problemas)
    assert any("99.999.999/0001-99" in p for p in problemas)


def test_detecta_nivel_de_risco_alterado():
    problemas = verificar_fatos(BOM.replace("o risco geral é baixo", "o risco geral é alto"), DOSSIE, ANALISE)
    assert any("risco alto" in p for p in problemas)


def test_detecta_texto_vazio():
    assert verificar_fatos("ok", DOSSIE, ANALISE)


def test_revisor_soma_problemas_do_llm(fake_llm_cls):
    llm = fake_llm_cls(revisor=['{"aprovado": false, "problemas": ["Afirma que a empresa tem 50 funcionários."]}'])
    revisao = Revisor(llm).revisar(BOM, DOSSIE, ANALISE)
    assert revisao.aprovado is False
    assert revisao.problemas == ["Afirma que a empresa tem 50 funcionários."]
    assert llm.chamadas[0]["json_mode"] is True


def test_revisor_tolera_json_com_texto_em_volta(fake_llm_cls):
    llm = fake_llm_cls(revisor=['Claro! {"aprovado": false, "problemas": ["X"]} Espero ter ajudado.'])
    assert Revisor(llm).revisar(BOM, DOSSIE, ANALISE).problemas == ["X"]


def test_revisor_ignora_resposta_invalida_e_falha_do_llm():
    class Quebrado:
        nome = "quebrado"

        def chat(self, *a, **k):
            raise LLMError("offline")

    assert Revisor(Quebrado()).revisar(BOM, DOSSIE, ANALISE).aprovado is True


# Trecho real gerado pelo llama3.2:3b no primeiro teste com o Banco do Brasil (13/11/2026).
GERADO_PELO_3B = (
    "**Parecer de Due Diligence de Fornecedor**\n\n"
    "A análise dos dados públicos não apresentou nenhum alerta significativo. O nível de risco geral calculado é baixo, "
    "considerando a estabilidade financeira e a longa história da empresa.\n\n"
    "**Recomendações:**\n\n"
    "* Verificar a transparência e a clareza nas contas financeiras da empresa.\n"
    "* Analisar a diversificação da carteira comercial e a gestão de riscos.\n"
    "* Avaliar a eficácia da gestão de recursos humanos e a motivação dos funcionários.\n"
    "* Verificar a conformidade da empresa com as normas e regulamentações aplicáveis.\n"
    "* Considerar a possibilidade de auditorias adicionais."
)


def test_pega_os_problemas_do_parecer_real_do_modelo_3b():
    problemas = " | ".join(verificar_fatos(GERADO_PELO_3B, DOSSIE, ANALISE))
    assert "estabilidade financeira" in problemas
    assert "carteira comercial" in problemas
    assert "recursos humanos" in problemas
    assert "começa com um título" in problemas
    assert "5 recomendações" in problemas


def test_termo_permitido_quando_esta_nos_fatos_ou_sugestoes():
    # O alerta de MEI e a recomendação sugerida falam em "faturamento", então o redator pode usar a palavra.
    dossie_mei = {**empresa(opcao_pelo_mei=True), "cnpj": "11.222.333/0001-81"}
    analise_mei = analisar(dossie_mei, HOJE)
    texto = BOM.replace("o risco geral é baixo", "o risco geral é médio") + "\nAtenção ao limite de faturamento do MEI."
    assert not any("faturamento" in p for p in verificar_fatos(texto, dossie_mei, analise_mei))
    assert any("faturamento" in p for p in verificar_fatos(BOM + " O faturamento é alto.", DOSSIE, ANALISE))


def test_formato_das_recomendacoes():
    assert verificar_formato(BOM) == []
    assert any("Falta a seção" in p for p in verificar_formato("Texto sem recomendações. " * 5))
    um_item = BOM.split("- Consultar")[0]
    assert any("1 recomendações" in p for p in verificar_formato(um_item))
    numeradas = BOM.replace("- Solicitar", "1. Solicitar").replace("- Consultar", "2) Consultar")
    assert verificar_formato(numeradas) == []


def test_titulo_no_inicio():
    assert any("título" in p for p in verificar_formato("# Parecer\n\n" + BOM))
    assert any("título" in p for p in verificar_formato("**Parecer de Due Diligence**\n\n" + BOM))
    assert not any("título" in p for p in verificar_formato("**A empresa** está ativa.\n\n" + BOM))


# Parecer real gerado pelo llama3.2:3b na v0.1.1 (já sem termos financeiros, mas prolixo).
GERADO_V011 = (
    "Banco do Brasil S.A.\n\n"
    "O Banco do Brasil S.A. apresenta uma situação geral de baixo nível de risco, considerando a duração de sua existência.\n\n"
    "A empresa tem uma longa história de operações. É fundamental realizar uma análise mais aprofundada para identificar riscos.\n\n"
    "A recomendação de solicitar as certidões negativas é particularmente importante para identificar dívidas.\n\n"
    "É importante lembrar que a análise de risco é um processo contínuo e que a situação pode mudar.\n\n"
    "**Recomendações:**\n"
    "- Solicitar as certidões negativas de débitos (CND federal, FGTS e trabalhista).\n"
    "- Consultar protestos e processos judiciais em nome da empresa.\n"
    "- Realizar uma análise regular para garantir que continue a ser uma boa opção para investidores e clientes."
)


def test_pega_os_problemas_do_parecer_real_da_v011():
    problemas = " | ".join(verificar_fatos(GERADO_V011, DOSSIE, ANALISE))
    assert "começa com um título" in problemas
    assert "4 parágrafos" in problemas
    assert "investidores" in problemas
    assert "processo continuo" in problemas
    assert "analise mais aprofundada" in problemas


def test_paragrafos_dentro_do_limite_passam():
    tres = (
        "Primeiro parágrafo com conteúdo.\n\nSegundo parágrafo.\n\nTerceiro parágrafo.\n\n" + BOM.split("**Recomendações:**")[1]
    )
    tres = tres.replace("\n- Solicitar", "**Recomendações:**\n- Solicitar", 1)
    assert not any("parágrafos" in p for p in verificar_formato(tres))


def test_titulo_simples_com_nome_da_empresa():
    assert any("título" in p for p in verificar_formato("Banco do Brasil S.A.\n\n" + BOM))
    assert any("título" in p for p in verificar_formato("Análise do fornecedor\n\n" + BOM))
