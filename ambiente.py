"""
Mundo de Wumpus — Etapa 1: gerador aleatório de ambientes.

Convenção de coordenadas usada em todo o projeto
-----------------------------------------------
* A grade é ``n x n`` e as posições são ``(linha, coluna)``.
* ``(0, 0)`` é a casa inicial do agente (canto inferior esquerdo na
  visualização do tabuleiro).
* Norte aumenta a linha, Sul diminui a linha, Leste aumenta a coluna e
  Oeste diminui a coluna.  Essa é a mesma convenção usada pelo agente v2
  (que chama a linha de ``y`` e a coluna de ``x``).

O gerador segue as regras da Etapa 1:
* a casa ``(0, 0)`` nunca recebe poço, Wumpus ou ouro;
* poços não podem compartilhar a casa com Wumpus ou ouro;
* Wumpus e ouro também não compartilham a mesma casa;
* as percepções (brisa, fedor e brilho) são calculadas a partir dos objetos.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]


def configuracao_padrao(dimensao: int) -> Dict[str, int]:
    """Configuração automática usada nos experimentos da Etapa 5.

    A quantidade de poços cresce com a área do tabuleiro (20% das casas,
    excluindo a casa inicial), mantendo um Wumpus e uma barra de ouro.
    """
    if dimensao < 3:
        raise ValueError("A dimensão da grade deve ser n >= 3")
    casas = dimensao * dimensao - 1
    return {
        "qtd_pocos": max(1, round(0.20 * casas)),
        "qtd_wumpus": 1,
        "qtd_ouro": 1,
    }


class AmbienteWumpus:
    """Gerador aleatório do Mundo de Wumpus (Etapa 1)."""

    def __init__(
        self,
        dimensao: int = 4,
        qtd_pocos: int = 3,
        qtd_wumpus: int = 1,
        qtd_ouro: int = 1,
        seed: Optional[int] = None,
    ) -> None:
        if dimensao < 3:
            raise ValueError("A dimensao da grade deve ser n >= 3")
        if min(qtd_pocos, qtd_wumpus, qtd_ouro) < 0:
            raise ValueError("As quantidades de objetos devem ser >= 0")

        self.dimensao = dimensao
        self.inicio_agente: Pos = (0, 0)
        self.seed = seed
        self.rng = random.Random(seed)

        self.qtd_pocos = qtd_pocos
        self.qtd_wumpus = qtd_wumpus
        self.qtd_ouro = qtd_ouro

        # Conjuntos para consulta eficiente.
        self.pocos: Set[Pos] = set()
        self.wumpus: Set[Pos] = set()
        self.ouro: Set[Pos] = set()

        # Dicionário que mapeia cada célula para o seu conjunto de percepções.
        self.percepcoes: Dict[Pos, Set[str]] = {
            (lin, col): set()
            for lin in range(dimensao)
            for col in range(dimensao)
        }

        self._gerar_mundo()

    # ------------------------------------------------------------------
    # Geração
    # ------------------------------------------------------------------
    def vizinhos(self, lin: int, col: int) -> List[Pos]:
        """Retorna as casas vizinhas ortogonais válidas (N, S, L, O)."""
        vizinhos: List[Pos] = []
        for d_lin, d_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nova_lin, nova_col = lin + d_lin, col + d_col
            if 0 <= nova_lin < self.dimensao and 0 <= nova_col < self.dimensao:
                vizinhos.append((nova_lin, nova_col))
        return vizinhos

    # Compatibilidade com o nome usado na primeira versão do arquivo.
    _obter_vizinhos = vizinhos

    def _gerar_mundo(self) -> None:
        """Sorteia os objetos e calcula as percepções."""
        casas_disponiveis: List[Pos] = [
            (lin, col)
            for lin in range(self.dimensao)
            for col in range(self.dimensao)
            if (lin, col) != self.inicio_agente
        ]
        self.rng.shuffle(casas_disponiveis)

        # 1. Poços.
        qtd_pocos = min(self.qtd_pocos, len(casas_disponiveis))
        self.qtd_pocos = qtd_pocos
        self.pocos = set(casas_disponiveis[:qtd_pocos])

        # 2. Wumpus (sem poços).
        casas_livres = [c for c in casas_disponiveis if c not in self.pocos]
        qtd_wumpus = min(self.qtd_wumpus, len(casas_livres))
        self.qtd_wumpus = qtd_wumpus
        self.wumpus = set(self.rng.sample(casas_livres, qtd_wumpus)) if qtd_wumpus else set()

        # 3. Ouro (sem poços e sem Wumpus).
        casas_livres = [c for c in casas_livres if c not in self.wumpus]
        qtd_ouro = min(self.qtd_ouro, len(casas_livres))
        self.qtd_ouro = qtd_ouro
        self.ouro = set(self.rng.sample(casas_livres, qtd_ouro)) if qtd_ouro else set()

        # 4. Percepções.
        for p_lin, p_col in self.pocos:
            for v_lin, v_col in self.vizinhos(p_lin, p_col):
                self.percepcoes[(v_lin, v_col)].add("brisa")

        for w_lin, w_col in self.wumpus:
            for v_lin, v_col in self.vizinhos(w_lin, w_col):
                self.percepcoes[(v_lin, v_col)].add("fedor")

        for o_lin, o_col in self.ouro:
            self.percepcoes[(o_lin, o_col)].add("brilho")

    # ------------------------------------------------------------------
    # Consultas (interface para os agentes)
    # ------------------------------------------------------------------
    def obter_percepcoes(self, lin: int, col: int) -> Set[str]:
        """Retorna as percepções sentidas na coordenada informada."""
        return self.percepcoes.get((lin, col), set()).copy()

    def tem_poco(self, lin: int, col: int) -> bool:
        return (lin, col) in self.pocos

    def tem_wumpus(self, lin: int, col: int) -> bool:
        return (lin, col) in self.wumpus

    def tem_ouro(self, lin: int, col: int) -> bool:
        return (lin, col) in self.ouro

    def para_dicionario(self) -> Dict[str, Any]:
        """Exporta o ambiente para os agentes e rotinas de teste."""
        return {
            "dimensao": self.dimensao,
            "inicio_agente": list(self.inicio_agente),
            "pocos": [list(p) for p in sorted(self.pocos)],
            "wumpus": [list(w) for w in sorted(self.wumpus)],
            "ouro": [list(o) for o in sorted(self.ouro)],
            "percepcoes": {
                f"{lin},{col}": sorted(percs)
                for (lin, col), percs in self.percepcoes.items()
                if percs
            },
        }

    # ------------------------------------------------------------------
    # Visualização
    # ------------------------------------------------------------------
    def exibir_tabuleiro(self) -> None:
        """Imprime a grade no terminal (linha 0 na parte inferior)."""
        print(f"\n--- Mundo de Wumpus ({self.dimensao}x{self.dimensao}) ---")
        for lin in range(self.dimensao - 1, -1, -1):
            linha_str = []
            for col in range(self.dimensao):
                conteudo = []
                if (lin, col) == self.inicio_agente:
                    conteudo.append("A")
                if (lin, col) in self.pocos:
                    conteudo.append("P")
                if (lin, col) in self.wumpus:
                    conteudo.append("W")
                if (lin, col) in self.ouro:
                    conteudo.append("O")

                percs = "".join(
                    {
                        "brisa": "B",
                        "fedor": "F",
                        "brilho": "R",
                        "impacto": "I",
                        "grito": "G",
                    }.get(p, p[0].upper())
                    for p in sorted(self.percepcoes[(lin, col)])
                )
                marcador = ",".join(conteudo)
                rotulo = f"[{marcador}|{percs}]" if marcador or percs else "[   ]"
                linha_str.append(f"{rotulo:^10}")
            print(f"{lin} | " + " ".join(linha_str))

        print("    " + "-" * (11 * self.dimensao))
        print("      " + " ".join([f"{col:^10}" for col in range(self.dimensao)]))
        print(
            "Legenda: A=Agente, P=Poco, W=Wumpus, O=Ouro | "
            "B=Brisa, F=Fedor, R=bRilho\n"
        )


def criar_ambiente(
    dimensao: int,
    seed: Optional[int] = None,
    *,
    qtd_pocos: Optional[int] = None,
    qtd_wumpus: Optional[int] = None,
    qtd_ouro: Optional[int] = None,
) -> AmbienteWumpus:
    """Cria um ambiente com a configuração padrão ou com quantidades explícitas."""
    padrao = configuracao_padrao(dimensao)
    return AmbienteWumpus(
        dimensao=dimensao,
        qtd_pocos=padrao["qtd_pocos"] if qtd_pocos is None else qtd_pocos,
        qtd_wumpus=padrao["qtd_wumpus"] if qtd_wumpus is None else qtd_wumpus,
        qtd_ouro=padrao["qtd_ouro"] if qtd_ouro is None else qtd_ouro,
        seed=seed,
    )


if __name__ == "__main__":
    ambiente = criar_ambiente(4, seed=42)
    ambiente.exibir_tabuleiro()
