import random
from typing import Set, Tuple, Dict, List, Any

class AmbienteWumpus:
    # Etapa 1 - Gerador Aleatorio de Ambientes do Mundo de Wumpus
    def __init__(self, dimensao: int = 4, qtd_pocos: int = 3, qtd_wumpus: int = 1, qtd_ouro = 1):
        if dimensao < 3:
            raise ValueError ("A dimensao da grade deve ser n >= 3")

        self.dimensao = dimensao
        self.inicio_agente = (0,0)

        self.qtd_pocos = qtd_pocos
        self.qtd_wumpus = qtd_wumpus
        self.qtd_ouro = qtd_ouro

        # Cordenadas de cordenadas p busca eficiente {(linha, coluna)}
        self.pocos: Set[Tuple[int, int]] = set()
        self.wumpus: Set[Tuple[int, int]] =set()
        self.ouro: Set[Tuple[int, int]] = set()
