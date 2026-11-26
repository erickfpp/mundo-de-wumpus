"""
Mundo de Wumpus - Etapa 3: Agente Reativo (versão 2)
Inteligência Computacional (FECOMP-UFPA) - Projeto de Desenvolvimento
Integrante 3: Camille Vitória Vieira de Souza

Esta versão engloba a versão 1 (regras do tipo  Se <percepções> então <ação>)
e acrescenta, conforme o slide 24:

  1. ESTRUTURA DE MEMÓRIA: uma matriz-réplica do ambiente (grade mental),
     implementada como dicionário {(x, y): Celula}, com as anotações feitas
     pelo agente (visitada, brisa, fedor, ausência/certeza de poço e de Wumpus).
  2. CONHECIMENTO REGISTRADO NA MEMÓRIA usado na escolha da regra: inferência
     lógica de perigo (propagação de restrições até o ponto fixo) e
     planejamento de caminho (busca em largura sobre as casas provadamente seguras).
  3. MECANISMO MAIS INTELIGENTE PARA ESCOLHA DA REGRA: as regras são avaliadas
     por prioridade e, quando a regra escolhida admite várias ações possíveis
     (várias casas-alvo), a decisão é tomada por uma heurística de utilidade
     (custo do caminho, ganho de informação e risco estimado) no lugar da
     escolha aleatória da versão 1.

Classificação (estrutura de agentes): agente reativo baseado em modelo, isto é,
agente com estado interno (slide "Agentes com Estado Interno ou baseados em
Modelos"). Justificativa completa no relatório da Etapa 3.

CONTRATO DE INTEGRAÇÃO COM O AMBIENTE (ambiente.py / Etapa 1)
-------------------------------------------------------------
  * Coordenadas (x, y): x = coluna (cresce para L), y = linha (cresce para N);
    a casa é (0, 0), canto inferior esquerdo da matriz n x n.
  * A cada passo o ambiente chama  acao = agente.decidir(percepcoes).
  * percepcoes: conjunto/lista de strings entre
        "brisa" ("b"), "fedor" ("f"), "brilho" ("br"), "impacto" ("i"), "grito" ("g")
    (também é aceito um dict {"brisa": True, ...}).
  * acao devolvida (mesma notação da Aula 04):
        "mov(N)", "mov(S)", "mov(L)", "mov(O)", "atirar(N|S|L|O)", "pegar", "fim"
  * Ao receber "impacto" depois de um mov(d), o agente entende que não saiu do lugar.
  * O agente NÃO precisa conhecer n (descobre as paredes pelo "impacto"); se o
    ambiente quiser informar, basta  AgenteReativoV2(n=n).
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Constantes                                                                  #
# --------------------------------------------------------------------------- #

DIRECOES = {"N": (0, 1), "S": (0, -1), "L": (1, 0), "O": (-1, 0)}
ORDEM_DIRECOES = ("N", "L", "S", "O")
CASA = (0, 0)

ALIAS_PERCEPCOES = {
    "b": "brisa", "brisa": "brisa",
    "f": "fedor", "fedor": "fedor",
    "br": "brilho", "brilho": "brilho",
    "i": "impacto", "impacto": "impacto",
    "g": "grito", "grito": "grito",
}

PRIORI_POCO = 0.20        # risco-base de poço em casa sem evidência
PRIORI_WUMPUS = 0.10      # risco-base de Wumpus em casa sem evidência
LIMIAR_TIRO = 0.50        # probabilidade mínima para gastar a flecha em uma casa
PESO_INFORMACAO = 0.50    # quanto cada vizinha desconhecida "compensa" de custo de caminho
ALCANCE_MAXIMO = 20       # alcance usado para marcar a trajetória da flecha quando n é desconhecido


# --------------------------------------------------------------------------- #
# Memória: grade mental do agente                                             #
# --------------------------------------------------------------------------- #

@dataclass
class Celula:
    """Anotações que o agente guarda sobre uma casa."""
    visitada: bool = False
    brisa: bool = False
    fedor: bool = False
    fedor_valido: bool = True    # falso quando o fedor pode ter sido causado por um Wumpus já morto
    sem_poco: bool = False       # provado: não há poço aqui
    sem_wumpus: bool = False     # provado: não há Wumpus aqui
    poco_certo: bool = False     # provado: há poço aqui
    wumpus_certo: bool = False   # provado: há Wumpus aqui


class MemoriaMundo:
    """Matriz-réplica do ambiente, construída pelo agente durante a exploração."""

    def __init__(self, n: int | None = None,
                 prior_poco: float = PRIORI_POCO,
                 prior_wumpus: float = PRIORI_WUMPUS):
        self.celulas: dict[tuple[int, int], Celula] = {}
        self.limite_x = self.limite_y = (n - 1) if n else None
        self.prior_poco = prior_poco
        self.prior_wumpus = prior_wumpus

    # ---- acesso básico ---------------------------------------------------- #
    def cel(self, pos):
        c = self.celulas.get(pos)
        if c is None:
            c = self.celulas[pos] = Celula()
        return c

    def dentro(self, pos) -> bool:
        x, y = pos
        if x < 0 or y < 0:
            return False
        if self.limite_x is not None and x > self.limite_x:
            return False
        if self.limite_y is not None and y > self.limite_y:
            return False
        return True

    def vizinhas(self, pos):
        return [
            (pos[0] + dx, pos[1] + dy)
            for dx, dy in (DIRECOES[d] for d in ORDEM_DIRECOES)
            if self.dentro((pos[0] + dx, pos[1] + dy))
        ]

    def segura(self, pos) -> bool:
        c = self.cel(pos)
        return c.sem_poco and c.sem_wumpus

    # ---- registro de fatos ------------------------------------------------ #
    def registrar_visita(self, pos, brisa: bool, fedor: bool):
        c = self.cel(pos)
        c.visitada = True
        c.sem_poco = c.sem_wumpus = True
        c.poco_certo = c.wumpus_certo = False
        c.brisa, c.fedor, c.fedor_valido = brisa, fedor, True

    def registrar_parede(self, pos, direcao: str):
        """O agente bateu na parede ao tentar sair de `pos` na direção dada."""
        if direcao == "L":
            self.limite_x = pos[0]
        elif direcao == "N":
            self.limite_y = pos[1]

    def raio(self, pos, direcao: str):
        """Casas atravessadas por uma flecha disparada de `pos`."""
        dx, dy = DIRECOES[direcao]
        casas, atual = [], (pos[0] + dx, pos[1] + dy)
        while self.dentro(atual) and len(casas) < ALCANCE_MAXIMO:
            casas.append(atual)
            atual = (atual[0] + dx, atual[1] + dy)
        return casas

    def registrar_tiro(self, pos, direcao: str, grito: bool):
        """
        A flecha atinge o PRIMEIRO Wumpus da linha. Logo, a casa adjacente fica
        livre de Wumpus em qualquer desfecho (ou ele morreu ali, ou estava mais
        adiante, ou não havia nenhum). Sem grito, toda a trajetória está livre.
        """
        trajeto = self.raio(pos, direcao)
        if not trajeto:
            return
        if not grito:
            for casa in trajeto:
                c = self.cel(casa)
                c.sem_wumpus, c.wumpus_certo = True, False
            return
        c = self.cel(trajeto[0])
        c.sem_wumpus, c.wumpus_certo = True, False
        # Um Wumpus morreu: fedores observados perto da trajetória podem ter
        # vindo dele e deixam de ser evidência confiável.
        for casa in trajeto:
            for viz in self.vizinhas(casa):
                v = self.cel(viz)
                if v.visitada:
                    v.fedor_valido = False
        for c in self.celulas.values():
            c.wumpus_certo = False  # será reconstruído só com evidências válidas

    # ---- inferência lógica de perigo -------------------------------------- #
    def inferir(self):
        """Propaga as regras do mundo até não haver mais fatos novos.

          R-a  casa visitada sem brisa  -> vizinhas sem poço
          R-b  casa visitada sem fedor  -> vizinhas sem Wumpus
          R-c  casa visitada com brisa  -> se só resta uma vizinha possível, ela tem poço
          R-d  casa visitada com fedor  -> se só resta uma vizinha possível, ela tem Wumpus
        """
        mudou = True
        while mudou:
            mudou = False
            for pos, c in list(self.celulas.items()):
                if not c.visitada:
                    continue
                viz = self.vizinhas(pos)
                if not c.brisa:
                    for v in viz:
                        vc = self.cel(v)
                        if not vc.sem_poco:
                            vc.sem_poco, vc.poco_certo, mudou = True, False, True
                else:
                    cand = [v for v in viz if not self.cel(v).sem_poco]
                    if len(cand) == 1 and not self.cel(cand[0]).poco_certo:
                        self.cel(cand[0]).poco_certo, mudou = True, True
                if not c.fedor:
                    for v in viz:
                        vc = self.cel(v)
                        if not vc.sem_wumpus:
                            vc.sem_wumpus, vc.wumpus_certo, mudou = True, False, True
                elif c.fedor_valido:
                    cand = [v for v in viz if not self.cel(v).sem_wumpus]
                    if len(cand) == 1 and not self.cel(cand[0]).wumpus_certo:
                        self.cel(cand[0]).wumpus_certo, mudou = True, True

    # ---- estimativa de risco (heurística) --------------------------------- #
    def p_poco(self, pos) -> float:
        c = self.cel(pos)
        if c.poco_certo:
            return 1.0
        if c.sem_poco:
            return 0.0
        melhor = 0.0
        for v in self.vizinhas(pos):
            vc = self.cel(v)
            if vc.visitada and vc.brisa:
                k = sum(1 for w in self.vizinhas(v) if not self.cel(w).sem_poco)
                melhor = max(melhor, 1.0 / max(k, 1))
        return melhor if melhor > 0 else self.prior_poco

    def p_wumpus(self, pos) -> float:
        c = self.cel(pos)
        if c.wumpus_certo:
            return 1.0
        if c.sem_wumpus:
            return 0.0
        melhor = 0.0
        for v in self.vizinhas(pos):
            vc = self.cel(v)
            if vc.visitada and vc.fedor and vc.fedor_valido:
                k = sum(1 for w in self.vizinhas(v) if not self.cel(w).sem_wumpus)
                melhor = max(melhor, 1.0 / max(k, 1))
        return melhor if melhor > 0 else self.prior_wumpus

    def risco(self, pos) -> float:
        return 1.0 - (1.0 - self.p_poco(pos)) * (1.0 - self.p_wumpus(pos))

    # ---- planejamento: busca em largura sobre casas seguras ---------------- #
    def bfs(self, origem):
        dist, pai = {origem: 0}, {}
        fila = deque([origem])
        while fila:
            atual = fila.popleft()
            for v in self.vizinhas(atual):
                if v not in dist and self.segura(v):
                    dist[v], pai[v] = dist[atual] + 1, atual
                    fila.append(v)
        return dist, pai

    # ---- visualização ------------------------------------------------------ #
    def mapa(self, pos_agente=None) -> str:
        """Texto da grade mental. A=agente  .=visitada  s=segura  P=poço  W=Wumpus  ?=incerta  ' '=desconhecida."""
        if not self.celulas:
            return ""
        xs = [p[0] for p in self.celulas] + [pos_agente[0] if pos_agente else 0]
        ys = [p[1] for p in self.celulas] + [pos_agente[1] if pos_agente else 0]
        xmax = self.limite_x if self.limite_x is not None else max(xs)
        ymax = self.limite_y if self.limite_y is not None else max(ys)
        linhas = []
        for y in range(ymax, -1, -1):
            linha = []
            for x in range(xmax + 1):
                c = self.celulas.get((x, y))
                if (x, y) == pos_agente:
                    s = "A"
                elif c is None:
                    s = " "
                elif c.poco_certo:
                    s = "P"
                elif c.wumpus_certo:
                    s = "W"
                elif c.visitada:
                    s = "."
                elif c.sem_poco and c.sem_wumpus:
                    s = "s"
                else:
                    s = "?"
                linha.append(s)
            linhas.append(f"{y:>2} " + " ".join(linha))
        linhas.append("   " + " ".join(str(x % 10) for x in range(xmax + 1)))
        return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# Agente                                                                      #
# --------------------------------------------------------------------------- #

class AgenteReativoV2:
    """
    Estrutura linear do agente (Sensores -> Modelo -> Regras -> Atuadores):

        decidir(percepcoes):
            1. atualizar o estado interno com a percepção e com o efeito da última ação
            2. inferir perigo a partir da memória
            3. escolher a regra aplicável de maior prioridade
            4. devolver a ação da regra

    Base de regras (prioridade decrescente):

        R1  Se [brilho] e sem ouro                        então pegar
        R2  Se na casa (0,0) e (com ouro ou desistiu)     então fim
        R3  Se com ouro ou desistiu                       então mov(passo do caminho seguro até a casa)
        R4  Se existe casa segura ainda não visitada      então mov(passo até a melhor delas)
        R5  Se resta flecha e há casa com Wumpus provável então (ir até casa adjacente a ela e) atirar
        R6  Se existe casa de risco aceitável             então mov(passo até a de menor risco)
        R7  Caso contrário                                então desistir (voltar para a casa e fim)
    """

    def __init__(self, n: int | None = None, flechas: int = 1,
                 tolerancia_risco: float = 0.4, semente: int | None = None,
                 max_passos: int | None = None, registrar_log: bool = False,
                 prior_poco: float = PRIORI_POCO,
                 prior_wumpus: float = PRIORI_WUMPUS,
                 peso_informacao: float = PESO_INFORMACAO,
                 limiar_tiro: float = LIMIAR_TIRO):
        """
        n                 tamanho do ambiente, se o ambiente quiser informar (opcional)
        flechas           quantidade de flechas (a especificação do projeto usa 1)
        tolerancia_risco  risco máximo aceito para entrar em casa não provada segura
                          (0 = nunca arrisca; padrão 0.4 = risco moderado, que
                          permite explorar quando não há casas provadamente seguras)
        semente           semente do desempate aleatório entre alvos de mesma utilidade
        max_passos        trava de segurança contra ciclos (padrão: 8 * n^2, ou 800 sem n)
        prior_poco        risco-base de poço em casa sem evidência (usado pela heurística)
        prior_wumpus      risco-base de Wumpus em casa sem evidência
        peso_informacao   peso do ganho de informação na escolha da casa a explorar
        limiar_tiro       probabilidade mínima para gastar a flecha em uma casa
        """
        self.memoria = MemoriaMundo(n, prior_poco=prior_poco, prior_wumpus=prior_wumpus)
        self.pos = CASA
        self.flechas = flechas
        self.tolerancia_risco = tolerancia_risco
        self.peso_informacao = peso_informacao
        self.limiar_tiro = limiar_tiro
        self.rng = random.Random(semente)
        self.semente = semente
        self.n = n
        self.max_passos = max_passos or (8 * n * n if n else 800)
        self.tem_ouro = False
        self.desistiu = False
        self.passos = 0
        self.ultima_acao: str | None = None
        self.ultima_regra: str | None = None
        self.brilho = False
        self.registrar_log = registrar_log
        self.log: list[dict] = []
        self.regras = [
            ("R1-pegar", self._r1_pegar),
            ("R2-fim", self._r2_fim),
            ("R3-voltar", self._r3_voltar),
            ("R4-explorar-seguro", self._r4_explorar_seguro),
            ("R5-atirar", self._r5_atirar),
            ("R6-arriscar", self._r6_arriscar),
            ("R7-desistir", self._r7_desistir),
        ]

    # ---- interface com o ambiente ----------------------------------------- #
    def decidir(self, percepcoes) -> str:
        p = self._normalizar(percepcoes)
        self._atualizar_modelo(p)
        self.memoria.inferir()
        acao = self._escolher_regra()
        self._registrar_acao(acao)
        if self.registrar_log:
            self.log.append({"passo": self.passos, "pos": self.pos, "percepcoes": sorted(p),
                             "regra": self.ultima_regra, "acao": acao})
        return acao

    @property
    def posicao(self):
        return self.pos

    def mapa_mental(self) -> str:
        return self.memoria.mapa(self.pos)

    # ---- 1. atualização do estado interno --------------------------------- #
    @staticmethod
    def _normalizar(percepcoes) -> set[str]:
        if not percepcoes:
            return set()
        if isinstance(percepcoes, dict):
            percepcoes = [k for k, v in percepcoes.items() if v]
        elif isinstance(percepcoes, str):
            percepcoes = [percepcoes]
        return {ALIAS_PERCEPCOES[str(p).lower()] for p in percepcoes if str(p).lower() in ALIAS_PERCEPCOES}

    def _atualizar_modelo(self, p: set[str]):
        a = self.ultima_acao
        if a and a.startswith("mov("):
            d = a[4]
            if "impacto" in p:
                self.memoria.registrar_parede(self.pos, d)
            else:
                dx, dy = DIRECOES[d]
                self.pos = (self.pos[0] + dx, self.pos[1] + dy)
        elif a and a.startswith("atirar("):
            self.memoria.registrar_tiro(self.pos, a[7], "grito" in p)
        self.brilho = "brilho" in p
        self.memoria.registrar_visita(self.pos, "brisa" in p, "fedor" in p)

    def _registrar_acao(self, acao: str):
        self.ultima_acao = acao
        self.passos += 1
        if acao.startswith("atirar("):
            self.flechas -= 1
        elif acao == "pegar":
            self.tem_ouro = True

    # ---- 3. mecanismo de escolha da regra --------------------------------- #
    def _escolher_regra(self) -> str:
        if self.passos >= self.max_passos:
            self.desistiu = True
        for nome, regra in self.regras:
            acao = regra()
            if acao is not None:
                self.ultima_regra = nome
                return acao
        self.ultima_regra = "R7-desistir"
        return "fim"

    # ---- utilitários de navegação ----------------------------------------- #
    @staticmethod
    def _direcao(origem, destino) -> str:
        delta = (destino[0] - origem[0], destino[1] - origem[1])
        return next(d for d, v in DIRECOES.items() if v == delta)

    def _primeiro_passo(self, pai, alvo) -> str:
        atual = alvo
        while pai[atual] != self.pos:
            atual = pai[atual]
        return f"mov({self._direcao(self.pos, atual)})"

    def _ir_para(self, alvo, dist, pai):
        """Um passo em direção a `alvo` (casa alcançável por casas seguras)."""
        if alvo == self.pos:
            return None
        return self._primeiro_passo(pai, alvo)

    # ---- regras ------------------------------------------------------------ #
    def _r1_pegar(self):
        if self.brilho and not self.tem_ouro:
            return "pegar"

    def _r2_fim(self):
        if self.pos == CASA and (self.tem_ouro or self.desistiu):
            return "fim"

    def _r3_voltar(self):
        if self.tem_ouro or self.desistiu:
            dist, pai = self.memoria.bfs(self.pos)
            return self._ir_para(CASA, dist, pai)

    def _r4_explorar_seguro(self):
        """Escolhe a casa segura ainda não visitada de menor custo ajustado:
        custo = distância - peso_informacao * (vizinhas ainda desconhecidas)."""
        m = self.memoria
        dist, pai = m.bfs(self.pos)
        candidatos = [c for c in dist if c != self.pos and not m.cel(c).visitada]
        if not candidatos:
            return None

        def custo(c):
            desconhecidas = sum(1 for v in m.vizinhas(c)
                                if not m.cel(v).visitada and not m.segura(v))
            return dist[c] - self.peso_informacao * desconhecidas

        melhor = min(custo(c) for c in candidatos)
        alvo = self.rng.choice([c for c in candidatos if custo(c) == melhor])
        return self._ir_para(alvo, dist, pai)

    def _r5_atirar(self):
        """Gasta a flecha em casa onde o Wumpus é certo ou 50% provável. O tiro
        também é informativo: sempre libera a casa adjacente de Wumpus."""
        if self.flechas <= 0:
            return None
        m = self.memoria
        dist, pai = m.bfs(self.pos)
        melhor = None
        for pos, c in list(m.celulas.items()):
            if c.visitada or c.sem_wumpus or c.poco_certo or not m.dentro(pos):
                continue
            pw = m.p_wumpus(pos)
            if pw < self.limiar_tiro:
                continue
            for atirador in m.vizinhas(pos):
                if atirador in dist:
                    chave = (-pw, dist[atirador])
                    if melhor is None or chave < melhor[0]:
                        melhor = (chave, pos, atirador)
        if melhor is None:
            return None
        _, alvo, atirador = melhor
        if atirador == self.pos:
            return f"atirar({self._direcao(self.pos, alvo)})"
        return self._ir_para(atirador, dist, pai)

    def _r6_arriscar(self):
        """Sem casa segura para explorar, aceita o menor risco estimado, desde
        que não passe da tolerância e que a casa não seja perigosa com certeza."""
        m = self.memoria
        dist, pai = m.bfs(self.pos)
        melhor = None
        for pos, c in list(m.celulas.items()):
            if c.visitada or m.segura(pos) or c.poco_certo or c.wumpus_certo or not m.dentro(pos):
                continue
            r = m.risco(pos)
            if r > self.tolerancia_risco:
                continue
            for base in m.vizinhas(pos):
                if base in dist:
                    chave = (r, dist[base])
                    if melhor is None or chave < melhor[0]:
                        melhor = (chave, pos, base)
        if melhor is None:
            return None
        _, alvo, base = melhor
        if base == self.pos:
            return f"mov({self._direcao(self.pos, alvo)})"
        return self._ir_para(base, dist, pai)

    def _r7_desistir(self):
        self.desistiu = True
        if self.pos == CASA:
            return "fim"
        dist, pai = self.memoria.bfs(self.pos)
        return self._ir_para(CASA, dist, pai) or "fim"


if __name__ == "__main__":
    # Demonstração mínima: o agente em uma casa sem percepções.
    ag = AgenteReativoV2(n=4, registrar_log=True)
    print(ag.decidir([]), ag.ultima_regra)
    print(ag.mapa_mental())
