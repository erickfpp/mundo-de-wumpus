"""
Mundo de Wumpus — Etapa 2: agente reativo simples (versão 1).

O agente não possui memória: a cada passo ele escolhe uma ação apenas com base
nas percepções atuais. As regras são avaliadas por prioridade e, quando mais de
uma ação é possível, a escolha é aleatória — exatamente como pede a Etapa 2.

Regras (notação da Aula 04):
    Se [brilho]                 então pegar
    Se [fedor] e tem flecha     então mov(N|S|L|O) ou atirar(N|S|L|O)
    Caso contrário              então mov(N|S|L|O) e, se não houver percepção,
                                           também pode escolher fim

O agente aceita percepções curtas ("b", "f", "br", "i", "g") ou longas
("brisa", "fedor", "brilho", "impacto", "grito"), o que facilita a integração
com o simulador.
"""

from __future__ import annotations

import random
from typing import Iterable, List, Optional, Set

ALIAS_PERCEPCOES = {
    "b": "b",
    "brisa": "b",
    "f": "f",
    "fedor": "f",
    "br": "br",
    "brilho": "br",
    "i": "i",
    "impacto": "i",
    "g": "g",
    "grito": "g",
}


class AgenteReativoV1:
    """Agente reativo sem estado interno (a escolha entre ações é aleatória)."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.tem_flecha = True
        self.rng = random.Random(seed)

    @staticmethod
    def _normalizar(percepcoes: Iterable[str] | str | None) -> Set[str]:
        if not percepcoes:
            return set()
        if isinstance(percepcoes, str):
            percepcoes = [percepcoes]
        return {
            ALIAS_PERCEPCOES[p.lower()]
            for p in percepcoes
            if str(p).lower() in ALIAS_PERCEPCOES
        }

    def escolher_acao(self, percepcoes: Iterable[str] | str | None) -> str:
        p = self._normalizar(percepcoes)
        movimentos = ["mov(N)", "mov(S)", "mov(L)", "mov(O)"]
        disparos = ["atirar(N)", "atirar(S)", "atirar(L)", "atirar(O)"]

        if "br" in p:
            acoes_possiveis: List[str] = ["pegar"]
        elif "f" in p:
            acoes_possiveis = list(movimentos)
            if self.tem_flecha:
                acoes_possiveis.extend(disparos)
        else:
            acoes_possiveis = list(movimentos)
            if not p:
                acoes_possiveis.append("fim")

        acao_escolhida = self.rng.choice(acoes_possiveis)

        if acao_escolhida.startswith("atirar"):
            self.tem_flecha = False

        return acao_escolhida

    # Nome alternativo para manter a mesma interface dos demais agentes.
    decidir = escolher_acao


if __name__ == "__main__":
    agente = AgenteReativoV1(seed=0)
    print(agente.escolher_acao(["brisa", "fedor"]))
