from datetime import date

from due_diligence.risco import analisar, idade_por_extenso, meses_entre

HOJE = date(2026, 11, 13)


def empresa(**campos):
    base = {
        "descricao_situacao_cadastral": "ATIVA",
        "data_inicio_atividade": "2010-01-01",
        "data_situacao_cadastral": "2010-01-01",
        "natureza_juridica": "Sociedade Empresária Limitada",
        "porte": "DEMAIS",
        "capital_social": 100000,
        "opcao_pelo_mei": False,
        "municipio": "SAO PAULO",
        "uf": "SP",
        "email": "a@b.com",
        "socios": [{"nome_socio": "X"}],
    }
    return {"cnpj": "11.222.333/0001-81", "empresa": {**base, **campos}}


def codigos(dossie):
    return [a.codigo for a in analisar(dossie, HOJE).alertas]


def test_empresa_regular_tem_risco_baixo():
    r = analisar(empresa(), HOJE)
    assert r.nivel_geral == "baixo"
    assert r.alertas == []
    assert r.idade_meses == 202


def test_situacao_irregular_e_alto():
    r = analisar(empresa(descricao_situacao_cadastral="BAIXADA"), HOJE)
    assert r.nivel_geral == "alto"
    assert r.alertas[0].codigo == "situacao_irregular"


def test_idade_da_empresa():
    assert "empresa_muito_nova" in codigos(empresa(data_inicio_atividade="2026-08-01", data_situacao_cadastral="2026-08-01"))
    assert "empresa_nova" in codigos(empresa(data_inicio_atividade="2025-06-01", data_situacao_cadastral="2025-06-01"))
    assert codigos(empresa(data_inicio_atividade="2020-01-01")) == []


def test_mudanca_recente_de_situacao():
    assert "situacao_mudou" in codigos(empresa(data_situacao_cadastral="2026-10-01"))


def test_mei_e_capital_baixo():
    assert "mei" in codigos(empresa(opcao_pelo_mei=True))
    assert "capital_baixo" in codigos(empresa(capital_social=5000))
    assert "capital_baixo" not in codigos(empresa(capital_social=5000, porte="MICRO EMPRESA"))


def test_endereco_inconsistente_compara_sem_acento():
    ok = {**empresa(), "endereco_cep": {"city": "São Paulo", "state": "SP"}}
    ruim = {**empresa(), "endereco_cep": {"city": "Campinas", "state": "SP"}}
    assert "endereco_inconsistente" not in codigos(ok)
    assert "endereco_inconsistente" in codigos(ruim)


def test_alertas_informativos_nao_elevam_o_risco():
    r = analisar(empresa(email=None, socios=[]), HOJE)
    assert {a.codigo for a in r.alertas} == {"sem_contato", "sem_socios"}
    assert r.nivel_geral == "baixo"


def test_empresario_individual_sem_socios_nao_gera_alerta():
    assert "sem_socios" not in codigos(empresa(natureza_juridica="Empresário (Individual)", socios=[]))


def test_alertas_ordenados_por_gravidade():
    r = analisar(empresa(descricao_situacao_cadastral="INAPTA", opcao_pelo_mei=True, email=None), HOJE)
    assert [a.nivel for a in r.alertas] == ["alto", "medio", "info"]


def test_datas_auxiliares():
    assert meses_entre(date(2026, 1, 31), date(2026, 2, 28)) == 0
    assert meses_entre(date(2025, 11, 13), date(2026, 11, 13)) == 12
    assert idade_por_extenso(0) == "0 meses"
    assert idade_por_extenso(13) == "1 ano e 1 mês"
    assert idade_por_extenso(24) == "2 anos"
