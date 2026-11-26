"""
Testes manuais do Agente Reativo v2 (Etapa 3) com um simulador mínimo e
independente.

Serve para verificar a correção do agente (memória, inferência e decisão) antes
da integração com o ambiente.py da equipe. Os números aqui NÃO são os
resultados oficiais da Etapa 5 (que usa o gerador da Etapa 1, configuração fixa
por tamanho e 30 execuções por ambiente).

Este script é executado manualmente, não pelo pytest:

    python tests/teste_manual_v2.py
"""

import sys
import random
import statistics
from collections import deque
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compat import carregar_agente_v2

agent_v2 = carregar_agente_v2()
AgenteReativoV2 = agent_v2.AgenteReativoV2

DIRS = {"N": (0, 1), "S": (0, -1), "L": (1, 0), "O": (-1, 0)}


class MundoSimples:
    """Gerador e simulador conforme o slide 22 (casa (0,0) vazia; ouro e Wumpus fora dos poços)."""

    def __init__(self, n, n_pocos=None, n_wumpus=1, semente=None):
        rng = random.Random(semente)
        self.n = n
        casas = [(x, y) for x in range(n) for y in range(n) if (x, y) != (0, 0)]
        n_pocos = round(0.2 * len(casas)) if n_pocos is None else n_pocos
        rng.shuffle(casas)
        self.pocos = set(casas[:n_pocos])
        livres = casas[n_pocos:]
        self.ouro = livres[0]
        self.wumpus = set(livres[1:1 + n_wumpus])
        self.pos = (0, 0)
        self.tem_ouro = False
        self.vivo = True
        self.saiu = False
        self.pontos = 0
        self.acoes = 0
        self.flechas_usadas = 0

    def vizinhas(self, p):
        return [(p[0] + dx, p[1] + dy) for dx, dy in DIRS.values()
                if 0 <= p[0] + dx < self.n and 0 <= p[1] + dy < self.n]

    def percepcoes(self, impacto=False, grito=False):
        p = set()
        if any(v in self.pocos for v in self.vizinhas(self.pos)):
            p.add("brisa")
        if any(v in self.wumpus for v in self.vizinhas(self.pos)):
            p.add("fedor")
        if self.pos == self.ouro and not self.tem_ouro:
            p.add("brilho")
        if impacto:
            p.add("impacto")
        if grito:
            p.add("grito")
        return p

    def solucionavel(self):
        """Existe caminho (0,0) -> ouro sem poço nem Wumpus?"""
        proibidas = self.pocos | self.wumpus
        vistos, fila = {(0, 0)}, deque([(0, 0)])
        while fila:
            a = fila.popleft()
            if a == self.ouro:
                return True
            for v in self.vizinhas(a):
                if v not in vistos and v not in proibidas:
                    vistos.add(v)
                    fila.append(v)
        return False

    def executar(self, acao):
        """Executa a ação; devolve (percepções, terminou)."""
        self.acoes += 1
        self.pontos -= 1
        impacto = grito = False
        if acao.startswith("mov("):
            dx, dy = DIRS[acao[4]]
            novo = (self.pos[0] + dx, self.pos[1] + dy)
            if not (0 <= novo[0] < self.n and 0 <= novo[1] < self.n):
                impacto = True
            else:
                self.pos = novo
                if self.pos in self.pocos or self.pos in self.wumpus:
                    self.vivo = False
                    self.pontos -= 1000
                    return set(), True
        elif acao.startswith("atirar("):
            self.flechas_usadas += 1
            self.pontos -= 10
            dx, dy = DIRS[acao[7]]
            atual = (self.pos[0] + dx, self.pos[1] + dy)
            while 0 <= atual[0] < self.n and 0 <= atual[1] < self.n:
                if atual in self.wumpus:
                    self.wumpus.discard(atual)
                    grito = True
                    break
                atual = (atual[0] + dx, atual[1] + dy)
        elif acao == "pegar":
            if self.pos == self.ouro:
                self.tem_ouro = True
        elif acao == "fim":
            if self.pos == (0, 0):
                self.saiu = True
                if self.tem_ouro:
                    self.pontos += 1000
                return set(), True
        return self.percepcoes(impacto, grito), False


def episodio(mundo, agente, limite=5000):
    percepcoes = mundo.percepcoes()
    for _ in range(limite):
        acao = agente.decidir(percepcoes)
        percepcoes, fim = mundo.executar(acao)
        if fim:
            break
    return mundo


def teste_seguranca(qtd=1500):
    """Com tolerância de risco 0 o agente só pisa em casas provadas seguras:
    qualquer morte indicaria erro na inferência."""
    mortes = 0
    for i in range(qtd):
        n = random.Random(i).choice([4, 5, 6, 8, 10])
        mundo = MundoSimples(n, n_wumpus=1 + i % 3, semente=i)
        ag = AgenteReativoV2(n=n if i % 2 else None, tolerancia_risco=0.0, semente=i)
        episodio(mundo, ag)
        mortes += not mundo.vivo
        assert mundo.saiu or not mundo.vivo, f"episódio {i} não terminou"
    assert mortes == 0, f"{mortes} mortes com tolerância 0"
    print(f"[ok] segurança: {qtd} ambientes (1 a 3 Wumpus, n conhecido ou não), 0 mortes com tolerância 0")


def teste_exemplo_aula04():
    """Ambiente 4x4 da Aula 04 (slide 95), em coordenadas de 0 a 3."""
    m = MundoSimples(4, n_pocos=0, n_wumpus=0, semente=0)
    m.pocos = {(0, 3), (1, 2), (3, 0)}
    m.wumpus = {(2, 2)}
    m.ouro = (3, 3)
    ag = AgenteReativoV2(n=4, semente=0, registrar_log=True)
    episodio(m, ag)
    print(f"[ok] exemplo da Aula 04: ouro={m.tem_ouro} vivo={m.vivo} saiu={m.saiu} pontos={m.pontos} ações={m.acoes}")
    print(ag.mapa_mental())
    return m, ag


def estatisticas(tamanhos=(4, 5, 10, 15, 20), execucoes=30):
    print(f"\n{'n':>3} {'sucesso':>8} {'mortes':>7} {'solucionáveis':>14} {'sucesso/solucionáveis':>22} {'pontos':>9} {'ações':>7}")
    for n in tamanhos:
        res = []
        for k in range(execucoes):
            mundo = MundoSimples(n, semente=1000 * n + k)
            ag = AgenteReativoV2(n=n, semente=k)
            sol = mundo.solucionavel()
            episodio(mundo, ag)
            res.append((mundo.saiu and mundo.tem_ouro, not mundo.vivo, sol, mundo.pontos, mundo.acoes))
        suc = sum(r[0] for r in res)
        mor = sum(r[1] for r in res)
        sol = sum(r[2] for r in res)
        suc_sol = sum(r[0] for r in res if r[2])
        print(f"{n:>3} {suc:>5}/{execucoes} {mor:>7} {sol:>14} {suc_sol:>16}/{sol:<5} "
              f"{statistics.mean(r[3] for r in res):>9.1f} {statistics.mean(r[4] for r in res):>7.1f}")


if __name__ == "__main__":
    teste_seguranca()
    teste_exemplo_aula04()
    estatisticas()
