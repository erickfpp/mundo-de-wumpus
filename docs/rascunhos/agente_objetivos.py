
"""
RASCUNHO NÃO OFICIAL — agente baseado em objetivos/utilitário.

Este arquivo preserva um rascunho de ``AgenteV4`` que chegou a ser escrito
para a Etapa 4. Ele **não** corresponde à especificação do trabalho: a Etapa 4
pede um **agente de aprendizagem (versão 3) com Algoritmos Genéticos**, que é a
implementação oficial em ``agent-v3.py``.

O código abaixo usa a convenção de coordenadas com (0, 0) no canto superior
esquerdo, diferente da convenção adotada no restante do repositório. Ele é
mantido apenas como registro histórico/alternativa de projeto e não é
importado por nenhum módulo do projeto.

agent-v4.py — Mundo de Wumpus
Etapa 4 (proposta): Agente baseado em objetivos/utilitário, com memória,
inferência e planejamento.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

Pos = Tuple[int, int]

# Convenção: (linha, coluna), com (0,0) no canto superior esquerdo.
# Norte diminui a linha; Sul aumenta a linha.
DIRECOES: Dict[str, Pos] = {
    "norte": (-1, 0),
    "sul": (1, 0),
    "leste": (0, 1),
    "oeste": (0, -1),
}

ACOES_MOVER: Dict[str, str] = {
    "norte": "mover_norte",
    "sul": "mover_sul",
    "leste": "mover_leste",
    "oeste": "mover_oeste",
}


@dataclass
class CelulaMemoria:
    visitada: bool = False

    # Conhecimento negativo: "já sei que não tem poço/Wumpus"
    sem_poco: bool = False
    sem_wumpus: bool = False

    # Conhecimento positivo
    poco: bool = False
    wumpus: bool = False
    ouro: bool = False

    # Percepções registradas
    brisa: bool = False
    fedor: bool = False

    # Suspeitas
    possivel_poco: bool = False
    possivel_wumpus: bool = False


class AgenteV4:
    def __init__(self, tamanho: int = 4, seed: Optional[int] = None):
        self.n = tamanho
        self.rng = random.Random(seed)

        self.memoria: Dict[Pos, CelulaMemoria] = {}
        self.posicao: Pos = (0, 0)

        self.tem_ouro = False
        self.flecha = True
        self.wumpus_morto = False
        self.saiu = False

        # A posição inicial é sempre segura.
        self._marcar_seguro((0, 0))
        self._celula((0, 0)).visitada = True

    # ------------------------------------------------------------------
    # Utilitários de memória
    # ------------------------------------------------------------------
    def _celula(self, pos: Pos) -> CelulaMemoria:
        if pos not in self.memoria:
            self.memoria[pos] = CelulaMemoria()
        return self.memoria[pos]

    def _dentro(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.n and 0 <= pos[1] < self.n

    def _vizinhos(self, pos: Pos) -> List[Pos]:
        vizinhos = []
        for dx, dy in DIRECOES.values():
            p = (pos[0] + dx, pos[1] + dy)
            if self._dentro(p):
                vizinhos.append(p)
        return vizinhos

    def _marcar_seguro(self, pos: Pos) -> None:
        c = self._celula(pos)
        if not c.poco and not c.wumpus:
            c.sem_poco = True
            c.sem_wumpus = True
            c.possivel_poco = False
            c.possivel_wumpus = False

    def _marcar_sem_poco(self, pos: Pos) -> None:
        c = self._celula(pos)
        if not c.poco:
            c.sem_poco = True
            c.possivel_poco = False

    def _marcar_sem_wumpus(self, pos: Pos) -> None:
        c = self._celula(pos)
        if not c.wumpus:
            c.sem_wumpus = True
            c.possivel_wumpus = False

    def _marcar_perigo(self, pos: Pos, tipo: str) -> None:
        c = self._celula(pos)
        if tipo == "poco":
            c.poco = True
            c.sem_poco = False
            c.possivel_poco = False
            # Poço e Wumpus não ocupam a mesma casa.
            c.sem_wumpus = True
        else:
            c.wumpus = True
            c.sem_wumpus = False
            c.possivel_wumpus = False
            # Wumpus e poço não ocupam a mesma casa.
            c.sem_poco = True

    def _transitavel(self, pos: Pos) -> bool:
        c = self.memoria.get(pos)
        if c is None:
            return False
        if c.poco or c.wumpus:
            return False
        return c.visitada or (c.sem_poco and c.sem_wumpus)

    # ------------------------------------------------------------------
    # Atualização da memória e inferência
    # ------------------------------------------------------------------
    def atualizar_memoria(self, percepcoes: dict, posicao: Pos) -> None:
        self.posicao = posicao
        c = self._celula(posicao)
        c.visitada = True
        c.sem_poco = True
        c.sem_wumpus = True

        c.brisa = bool(percepcoes.get("brisa", False))
        c.fedor = bool(percepcoes.get("fedor", False))

        if percepcoes.get("brilho", False):
            c.ouro = True

        if percepcoes.get("grito", False):
            self.wumpus_morto = True
            for cc in self.memoria.values():
                cc.possivel_wumpus = False
                cc.sem_wumpus = True

        adj = self._vizinhos(posicao)

        # Ausência de brisa => vizinhos não têm poço.
        if not c.brisa:
            for a in adj:
                self._marcar_sem_poco(a)
        else:
            for a in adj:
                ca = self._celula(a)
                if not ca.visitada and not ca.sem_poco and not ca.poco:
                    ca.possivel_poco = True

        # Ausência de fedor => vizinhos não têm Wumpus.
        if (not c.fedor) or self.wumpus_morto:
            for a in adj:
                self._marcar_sem_wumpus(a)
        else:
            for a in adj:
                ca = self._celula(a)
                if not ca.visitada and not ca.sem_wumpus and not ca.wumpus:
                    ca.possivel_wumpus = True

        self._inferir()

    def _inferir(self) -> None:
        """
        Inferência simples:
        - Se uma casa visitada não tem brisa, seus vizinhos não têm poço.
        - Se uma casa visitada não tem fedor, seus vizinhos não têm Wumpus.
        - Se uma casa com brisa/fedor tem apenas um vizinho possível,
          esse vizinho é poço/Wumpus.
        """
        mudou = True
        while mudou:
            mudou = False

            for pos, c in list(self.memoria.items()):
                if not c.visitada:
                    continue

                adj = self._vizinhos(pos)

                if not c.brisa:
                    for a in adj:
                        ca = self._celula(a)
                        if not ca.sem_poco:
                            ca.sem_poco = True
                            ca.possivel_poco = False
                            mudou = True
                else:
                    candidatos = [
                        a for a in adj
                        if not self._celula(a).sem_poco
                        and not self._celula(a).poco
                    ]
                    if len(candidatos) == 1:
                        a = candidatos[0]
                        if not self._celula(a).poco:
                            self._marcar_perigo(a, "poco")
                            mudou = True

                if (not c.fedor) or self.wumpus_morto:
                    for a in adj:
                        ca = self._celula(a)
                        if not ca.sem_wumpus:
                            ca.sem_wumpus = True
                            ca.possivel_wumpus = False
                            mudou = True
                else:
                    candidatos = [
                        a for a in adj
                        if not self._celula(a).sem_wumpus
                        and not self._celula(a).wumpus
                    ]
                    if len(candidatos) == 1:
                        a = candidatos[0]
                        if not self._celula(a).wumpus:
                            self._marcar_perigo(a, "wumpus")
                            mudou = True

    # ------------------------------------------------------------------
    # Planejamento
    # ------------------------------------------------------------------
    def _bfs(
        self,
        inicio: Pos,
        objetivos: Set[Pos],
        permitir_desconhecido: bool = False,
    ) -> Optional[List[Pos]]:
        """
        Retorna o caminho (sem incluir o início) até o objetivo mais próximo.
        Se permitir_desconhecido=False, só passa por casas seguras.
        Se permitir_desconhecido=True, pode passar por casas desconhecidas,
        mas nunca por poço/Wumpus conhecidos.
        """
        if inicio in objetivos:
            return []

        fila = deque([(inicio, [])])
        vistos = {inicio}

        while fila:
            atual, caminho = fila.popleft()

            for direcao, (dx, dy) in DIRECOES.items():
                prox = (atual[0] + dx, atual[1] + dy)

                if not self._dentro(prox) or prox in vistos:
                    continue

                c = self._celula(prox)

                if not permitir_desconhecido:
                    if not self._transitavel(prox):
                        continue
                else:
                    # Mesmo explorando desconhecido, não entra em perigo conhecido.
                    if c.poco or c.wumpus:
                        continue

                novo_caminho = caminho + [prox]

                if prox in objetivos:
                    return novo_caminho

                vistos.add(prox)
                fila.append((prox, novo_caminho))

        return None

    def _acao_mover(self, origem: Pos, destino: Pos) -> str:
        delta = (destino[0] - origem[0], destino[1] - origem[1])
        for direcao, d in DIRECOES.items():
            if d == delta:
                return ACOES_MOVER[direcao]
        return "esperar"

    def _direcao_wumpus_potencial(self) -> Optional[str]:
        """
        Verifica se há suspeita de Wumpus na mesma linha/coluna.
        Retorna a direção para atirar.
        """
        if not self.flecha or self.wumpus_morto:
            return None

        for pos, c in self.memoria.items():
            if c.wumpus or c.possivel_wumpus:
                if pos[0] == self.posicao[0]:
                    return "leste" if pos[1] > self.posicao[1] else "oeste"
                if pos[1] == self.posicao[1]:
                    return "sul" if pos[0] > self.posicao[0] else "norte"
        return None

    def _fronteiras_desconhecidas(self) -> Set[Pos]:
        fronteiras = set()
        for pos, c in self.memoria.items():
            if not c.visitada:
                continue
            for a in self._vizinhos(pos):
                ca = self._celula(a)
                if not ca.visitada and not ca.poco and not ca.wumpus:
                    fronteiras.add(a)
        return fronteiras

    # ------------------------------------------------------------------
    # Decisão
    # ------------------------------------------------------------------
    def escolher_acao(self, percepcoes: dict, posicao: Optional[Pos] = None) -> str:
        if posicao is None:
            posicao = self.posicao

        self.atualizar_memoria(percepcoes, posicao)

        # 1. Se está no ouro, pega.
        if percepcoes.get("brilho", False) and not self.tem_ouro:
            self.tem_ouro = True
            return "pegar"

        # 2. Se já tem o ouro, volta para (0,0) e sai.
        if self.tem_ouro:
            if self.posicao == (0, 0):
                return "sair"

            caminho = self._bfs(self.posicao, {(0, 0)}, permitir_desconhecido=False)
            if caminho is None:
                caminho = self._bfs(self.posicao, {(0, 0)}, permitir_desconhecido=True)

            if caminho:
                return self._acao_mover(self.posicao, caminho[0])
            return "esperar"

        # 3. Se conhece a posição do ouro, vai até ele.
        alvos_ouro = {
            p for p, c in self.memoria.items()
            if c.ouro and not c.poco and not c.wumpus
        }
        if alvos_ouro:
            caminho = self._bfs(self.posicao, alvos_ouro, permitir_desconhecido=False)
            if caminho:
                return self._acao_mover(self.posicao, caminho[0])

        # 4. Explora casas seguras ainda não visitadas.
        alvos_seguros = {
            p for p, c in self.memoria.items()
            if c.sem_poco and c.sem_wumpus and not c.visitada
            and not c.poco and not c.wumpus
        }
        caminho = self._bfs(self.posicao, alvos_seguros, permitir_desconhecido=False)
        if caminho:
            return self._acao_mover(self.posicao, caminho[0])

        # 5. Se há suspeita de Wumpus alinhado, tenta atirar.
        direcao = self._direcao_wumpus_potencial()
        if direcao:
            self.flecha = False
            return f"atirar_{direcao}"

        # 6. Último recurso: explorar fronteira desconhecida com risco.
        fronteiras = self._fronteiras_desconhecidas()
        caminho = self._bfs(self.posicao, fronteiras, permitir_desconhecido=True)
        if caminho:
            return self._acao_mover(self.posicao, caminho[0])

        return "esperar"

    # ------------------------------------------------------------------
    # Opcional: confirmação de ações pelo ambiente
    # ------------------------------------------------------------------
    def confirmar_acao(self, acao: str, sucesso: bool = True) -> None:
        if not sucesso:
            return
        if acao == "pegar":
            self.tem_ouro = True
        elif acao == "sair":
            self.saiu = True