"""Testes de integração do gerador, do simulador e dos três agentes."""

from __future__ import annotations

import pytest

from ambiente import AmbienteWumpus, configuracao_padrao, criar_ambiente
from compat import carregar_agente_v1, carregar_agente_v2, carregar_agente_v3
from simulador import (
    SimuladorWumpus,
    criar_agente,
    executar_episodio,
    normalizar_acao,
    percepcoes_curtas,
    resumo,
)

CONFIG = {"qtd_pocos": 3, "qtd_wumpus": 1, "qtd_ouro": 1}


# --------------------------------------------------------------------------- #
# Ambiente                                                                    #
# --------------------------------------------------------------------------- #

def test_ambiente_respeita_regras_de_geracao():
    for seed in range(50):
        ambiente = AmbienteWumpus(5, qtd_pocos=4, qtd_wumpus=2, qtd_ouro=1, seed=seed)
        assert (0, 0) not in ambiente.pocos
        assert (0, 0) not in ambiente.wumpus
        assert (0, 0) not in ambiente.ouro
        assert len(ambiente.pocos) == 4
        assert len(ambiente.wumpus) == 2
        assert len(ambiente.ouro) == 1
        assert ambiente.pocos.isdisjoint(ambiente.wumpus)
        assert ambiente.pocos.isdisjoint(ambiente.ouro)
        assert ambiente.wumpus.isdisjoint(ambiente.ouro)


def test_ambiente_calcula_percepcoes():
    ambiente = AmbienteWumpus(4, qtd_pocos=0, qtd_wumpus=0, qtd_ouro=0, seed=0)
    ambiente.pocos = {(1, 1)}
    ambiente.wumpus = {(2, 2)}
    ambiente.ouro = {(3, 3)}
    ambiente.percepcoes = {
        (lin, col): set()
        for lin in range(4)
        for col in range(4)
    }
    for p_lin, p_col in ambiente.pocos:
        for v in ambiente.vizinhos(p_lin, p_col):
            ambiente.percepcoes[v].add("brisa")
    for w_lin, w_col in ambiente.wumpus:
        for v in ambiente.vizinhos(w_lin, w_col):
            ambiente.percepcoes[v].add("fedor")
    ambiente.percepcoes[(3, 3)].add("brilho")

    assert "brisa" in ambiente.obter_percepcoes(0, 1)
    assert "fedor" in ambiente.obter_percepcoes(1, 2)
    assert "brilho" in ambiente.obter_percepcoes(3, 3)
    assert ambiente.obter_percepcoes(0, 0) == set()


def test_configuracao_padrao():
    config = configuracao_padrao(10)
    assert config["qtd_pocos"] == round(0.20 * (10 * 10 - 1))
    assert config["qtd_wumpus"] == 1
    assert config["qtd_ouro"] == 1


# --------------------------------------------------------------------------- #
# Simulador                                                                   #
# --------------------------------------------------------------------------- #

def test_normalizar_acoes():
    assert normalizar_acao("mov(N)") == ("mover", "N")
    assert normalizar_acao("mover_norte") == ("mover", "N")
    assert normalizar_acao("atirar(L)") == ("atirar", "L")
    assert normalizar_acao("atirar_oeste") == ("atirar", "O")
    assert normalizar_acao("pegar") == ("pegar", None)
    assert normalizar_acao("fim") == ("fim", None)
    with pytest.raises(ValueError):
        normalizar_acao("dancar")


def test_percepcoes_curtas():
    assert percepcoes_curtas({"brisa", "brilho"}) == ["b", "br"]


def test_simulador_sucesso_e_pontuacao():
    ambiente = AmbienteWumpus(4, qtd_pocos=0, qtd_wumpus=0, qtd_ouro=0, seed=0)
    ambiente.ouro = {(0, 1)}
    simulador = SimuladorWumpus(ambiente)

    percepcoes, terminou = simulador.executar("mov(L)")
    assert not terminou
    assert "brilho" in percepcoes

    _, terminou = simulador.executar("pegar")
    assert not terminou
    assert simulador.tem_ouro

    simulador.executar("mov(O)")
    _, terminou = simulador.executar("fim")
    assert terminou
    resultado = simulador.resultado()
    assert resultado.sucesso
    assert resultado.pontuacao == 996  # 4 ações e +1000 pela saída com ouro


def test_simulador_morte_em_poco():
    ambiente = AmbienteWumpus(4, qtd_pocos=0, qtd_wumpus=0, qtd_ouro=0, seed=0)
    ambiente.pocos = {(0, 1)}
    simulador = SimuladorWumpus(ambiente)
    _, terminou = simulador.executar("mov(L)")
    assert terminou
    resultado = simulador.resultado()
    assert resultado.morreu
    assert resultado.motivo == "poco"
    assert resultado.pontuacao == -1001


def test_simulador_parede_gera_impacto():
    ambiente = AmbienteWumpus(4, qtd_pocos=0, qtd_wumpus=0, qtd_ouro=0, seed=0)
    simulador = SimuladorWumpus(ambiente)
    percepcoes, terminou = simulador.executar("mov(O)")
    assert not terminou
    assert "impacto" in percepcoes
    assert simulador.pos == (0, 0)
    assert simulador.acoes == 1


def test_simulador_tiro_mata_wumpus():
    ambiente = AmbienteWumpus(4, qtd_pocos=0, qtd_wumpus=0, qtd_ouro=0, seed=0)
    ambiente.wumpus = {(0, 2)}
    simulador = SimuladorWumpus(ambiente)
    percepcoes, _ = simulador.executar("atirar(L)")
    assert "grito" in percepcoes
    assert not simulador.wumpus
    assert simulador.pontos == -11  # ação (-1) + flecha (-10)


# --------------------------------------------------------------------------- #
# Agentes                                                                     #
# --------------------------------------------------------------------------- #

def test_agente_v1_aceita_percepcoes_longas_e_curtas():
    modulo = carregar_agente_v1()
    agente = modulo.AgenteReativoV1(seed=0)
    validas = {
        "mov(N)", "mov(S)", "mov(L)", "mov(O)",
        "atirar(N)", "atirar(S)", "atirar(L)", "atirar(O)",
        "pegar", "fim",
    }
    assert agente.decidir({"brilho"}) == "pegar"
    for _ in range(20):
        assert agente.decidir({"brisa", "fedor"}) in validas
        assert agente.decidir(["b"]) in validas


def test_agente_v2_nao_morre_com_tolerancia_zero():
    modulo = carregar_agente_v2()
    for seed in range(20):
        ambiente = AmbienteWumpus(4, seed=seed, **CONFIG)
        agente = modulo.AgenteReativoV2(n=4, semente=seed, tolerancia_risco=0.0)
        resultado = executar_episodio(ambiente, agente)
        assert not resultado.morreu


def test_agente_v3_interface_e_treino_curto():
    modulo = carregar_agente_v3()
    params = modulo.ParametrosGA(
        tamanho_populacao=10,
        geracoes=8,
        seed=0,
        config_ambiente=CONFIG,
    )
    resultado = modulo.treinar(
        4, parametros=params, seeds_treino=[0], log_a_cada=0
    )
    assert len(resultado.genoma) > 0
    assert len(resultado.historico) == 8
    assert resultado.historico[-1]["melhor"] >= resultado.historico[0]["melhor"]

    agente = modulo.AgenteGenetico(n=4, genoma=resultado.genoma, seed=0)
    acao = agente.decidir(set())
    assert acao.startswith("mov(") or acao in {"pegar", "fim", "esperar"}


def test_fabrica_de_agentes():
    for versao in ("v1", "v2", "v3"):
        agente = criar_agente(versao, 4, seed=0, genoma=[0, 1, 2, 3])
        assert hasattr(agente, "decidir")


def test_resumo():
    ambiente = AmbienteWumpus(4, qtd_pocos=0, qtd_wumpus=0, qtd_ouro=0, seed=0)
    ambiente.ouro = {(0, 1)}
    agente = carregar_agente_v1().AgenteReativoV1(seed=0)
    resultado = executar_episodio(ambiente, agente)
    dados = resumo([resultado])
    assert dados["execucoes"] == 1
    assert 0 <= dados["taxa_sucesso"] <= 1
