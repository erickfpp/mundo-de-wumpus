"""
Simulador integrado do Mundo de Wumpus.

Este módulo conecta o gerador da Etapa 1 (``ambiente.py``) aos agentes das
Etapas 2, 3 e 4.  Ele implementa as regras de transição, as percepções, a
pontuação da Aula 04 e um runner de episódios.

Convenção de coordenadas
------------------------
``(linha, coluna)``, com ``(0, 0)`` na casa inicial.  Norte aumenta a linha,
Sul diminui, Leste aumenta a coluna e Oeste diminui.  A visualização do
``AmbienteWumpus`` já imprime a linha 0 na parte inferior, então a convenção é
compatível com a do agente v2.

Pontuação (Aula 04, slide 89)
-----------------------------
* ``-1`` por ação;
* ``-10`` por uso da flecha;
* ``-1000`` ao cair em um poço ou ser devorado pelo Wumpus;
* ``+1000`` ao sair da caverna com a barra de ouro.

O bônus opcional por matar o Wumpus é configurável (padrão 0), pois a
especificação detalhada da Aula 04 premia a saída com o ouro, não o abate.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ambiente import AmbienteWumpus, configuracao_padrao, criar_ambiente
from compat import carregar_agente_v1, carregar_agente_v2, carregar_agente_v3

Pos = Tuple[int, int]

# (linha, coluna)
DIRECOES: Dict[str, Pos] = {
    "N": (1, 0),
    "S": (-1, 0),
    "L": (0, 1),
    "O": (0, -1),
}

PERCEPCOES_CURTAS = {
    "brisa": "b",
    "fedor": "f",
    "brilho": "br",
    "impacto": "i",
    "grito": "g",
}

CUSTO_ACAO = -1
CUSTO_FLECHA = -10
PENALIDADE_MORTE = -1000
BONUS_SAIDA_OURO = 1000
BONUS_MATAR_WUMPUS = 0


# --------------------------------------------------------------------------- #
# Normalização de ações e percepções                                          #
# --------------------------------------------------------------------------- #

_ALIAS_DIRECAO = {
    "n": "N", "norte": "N", "north": "N", "cima": "N",
    "s": "S", "sul": "S", "south": "S", "baixo": "S",
    "l": "L", "leste": "L", "east": "L", "direita": "L",
    "o": "O", "oeste": "O", "west": "O", "esquerda": "O",
}


def _direcao(valor: str) -> str:
    chave = valor.strip().lower()
    if chave not in _ALIAS_DIRECAO:
        raise ValueError(f"Direção inválida: {valor!r}")
    return _ALIAS_DIRECAO[chave]


def normalizar_acao(acao: str) -> Tuple[str, Optional[str]]:
    """Converte as notações dos agentes para ``(tipo, direção)``.

    Aceita, por exemplo::

        mov(N), mover_norte, atirar(L), atirar_oeste, pegar, fim, esperar
    """
    if not isinstance(acao, str):
        raise ValueError(f"Ação deve ser string, recebido {type(acao).__name__}")

    texto = acao.strip()
    minusculo = texto.lower()

    if minusculo in {"pegar", "apanhar", "grab"}:
        return "pegar", None
    if minusculo in {"fim", "sair", "exit"}:
        return "fim", None
    if minusculo in {"esperar", "wait", "noop"}:
        return "esperar", None

    casamento = re.fullmatch(r"mov\s*\(\s*([A-Za-z]+)\s*\)", texto)
    if casamento:
        return "mover", _direcao(casamento.group(1))

    casamento = re.fullmatch(r"atirar\s*\(\s*([A-Za-z]+)\s*\)", texto)
    if casamento:
        return "atirar", _direcao(casamento.group(1))

    for prefixo in ("mover_", "mov_", "mover-", "mov-"):
        if minusculo.startswith(prefixo):
            return "mover", _direcao(minusculo[len(prefixo):])

    for prefixo in ("atirar_", "atirar-", "shoot_"):
        if minusculo.startswith(prefixo):
            return "atirar", _direcao(minusculo[len(prefixo):])

    raise ValueError(f"Ação não reconhecida: {acao!r}")


def percepcoes_curtas(percepcoes: Iterable[str]) -> List[str]:
    """Converte percepções canônicas para a notação curta usada pelo agente v1."""
    return sorted(
        PERCEPCOES_CURTAS[p] for p in percepcoes if p in PERCEPCOES_CURTAS
    )


# --------------------------------------------------------------------------- #
# Resultado de um episódio                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class ResultadoEpisodio:
    sucesso: bool
    morreu: bool
    saiu: bool
    pegou_ouro: bool
    pontuacao: int
    acoes: int
    motivo: str
    dist_min_ouro: int = 0
    dist_min_casa: int = 0
    historico: List[Dict[str, Any]] = field(default_factory=list)

    def como_dicionario(self) -> Dict[str, Any]:
        return {
            "sucesso": self.sucesso,
            "morreu": self.morreu,
            "saiu": self.saiu,
            "pegou_ouro": self.pegou_ouro,
            "pontuacao": self.pontuacao,
            "acoes": self.acoes,
            "motivo": self.motivo,
            "dist_min_ouro": self.dist_min_ouro,
            "dist_min_casa": self.dist_min_casa,
        }


# --------------------------------------------------------------------------- #
# Simulador                                                                   #
# --------------------------------------------------------------------------- #

class SimuladorWumpus:
    """Executa as ações de um agente sobre um ambiente gerado pela Etapa 1."""

    def __init__(
        self,
        ambiente: AmbienteWumpus,
        limite_passos: Optional[int] = None,
        registrar_historico: bool = False,
    ) -> None:
        self.ambiente = ambiente
        self.n = ambiente.dimensao
        self.limite_passos = limite_passos or max(100, 10 * self.n * self.n)
        self.registrar_historico = registrar_historico

        # Cópias mutáveis: matar o Wumpus ou pegar o ouro não altera o objeto
        # AmbienteWumpus original (importante para reutilizar a mesma semente).
        self.pocos: Set[Pos] = set(ambiente.pocos)
        self.wumpus: Set[Pos] = set(ambiente.wumpus)
        self.ouro: Set[Pos] = set(ambiente.ouro)

        self.pos: Pos = ambiente.inicio_agente
        self.vivo = True
        self.saiu = False
        self.tem_ouro = False
        self.flecha = True
        self.wumpus_morto = False
        self.pontos = 0
        self.acoes = 0
        self.impacto = False
        self.grito = False
        self.motivo = "em_andamento"

        self.dist_min_ouro = self._distancia_manhattan(self.pos, next(iter(self.ouro))) if self.ouro else 0
        self.dist_min_casa = 0

        self.percepcoes: Set[str] = self._calcular_percepcoes()
        self.historico: List[Dict[str, Any]] = []
        self._registrar("inicio")

    # ---- utilidades ------------------------------------------------------- #
    def _dentro(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.n and 0 <= pos[1] < self.n

    def _vizinhos(self, pos: Pos) -> List[Pos]:
        lin, col = pos
        return [
            (lin + dl, col + dc)
            for dl, dc in DIRECOES.values()
            if self._dentro((lin + dl, col + dc))
        ]

    @staticmethod
    def _distancia_manhattan(a: Pos, b: Pos) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _atualizar_distancias(self) -> None:
        if self.ouro:
            self.dist_min_ouro = min(
                self.dist_min_ouro,
                min(self._distancia_manhattan(self.pos, o) for o in self.ouro),
            )
        if self.tem_ouro:
            self.dist_min_casa = self._distancia_manhattan(
                self.pos, self.ambiente.inicio_agente
            )

    def _calcular_percepcoes(self) -> Set[str]:
        percepcoes: Set[str] = set()
        if any(v in self.pocos for v in self._vizinhos(self.pos)):
            percepcoes.add("brisa")
        if any(v in self.wumpus for v in self._vizinhos(self.pos)):
            percepcoes.add("fedor")
        if self.pos in self.ouro and not self.tem_ouro:
            percepcoes.add("brilho")
        if self.impacto:
            percepcoes.add("impacto")
        if self.grito:
            percepcoes.add("grito")
        return percepcoes

    def _registrar(self, acao: str) -> None:
        if not self.registrar_historico:
            return
        self.historico.append({
            "passo": self.acoes,
            "acao": acao,
            "pos": list(self.pos),
            "percepcoes": sorted(self.percepcoes),
            "pontos": self.pontos,
            "vivo": self.vivo,
            "tem_ouro": self.tem_ouro,
            "flecha": self.flecha,
        })

    # ---- transição -------------------------------------------------------- #
    def executar(self, acao: str) -> Tuple[Set[str], bool]:
        """Executa uma ação e devolve ``(percepções, terminou)``."""
        if not self.vivo or self.saiu:
            return self.percepcoes, True

        self.acoes += 1
        self.pontos += CUSTO_ACAO
        self.impacto = False
        self.grito = False

        tipo, direcao = normalizar_acao(acao)

        if tipo == "mover":
            assert direcao is not None
            dl, dc = DIRECOES[direcao]
            novo = (self.pos[0] + dl, self.pos[1] + dc)
            if not self._dentro(novo):
                self.impacto = True
            else:
                self.pos = novo
                self._atualizar_distancias()
                if self.pos in self.pocos or self.pos in self.wumpus:
                    self.vivo = False
                    self.pontos += PENALIDADE_MORTE
                    self.motivo = "poco" if self.pos in self.pocos else "wumpus"
                    self.percepcoes = set()
                    self._registrar(acao)
                    return self.percepcoes, True

        elif tipo == "atirar":
            assert direcao is not None
            if self.flecha:
                self.flecha = False
                self.pontos += CUSTO_FLECHA
                dl, dc = DIRECOES[direcao]
                atual = (self.pos[0] + dl, self.pos[1] + dc)
                while self._dentro(atual):
                    if atual in self.wumpus:
                        self.wumpus.discard(atual)
                        self.wumpus_morto = True
                        self.grito = True
                        self.pontos += BONUS_MATAR_WUMPUS
                        break
                    atual = (atual[0] + dl, atual[1] + dc)

        elif tipo == "pegar":
            if self.pos in self.ouro and not self.tem_ouro:
                self.ouro.discard(self.pos)
                self.tem_ouro = True
                self._atualizar_distancias()

        elif tipo == "fim":
            if self.pos == self.ambiente.inicio_agente:
                self.saiu = True
                if self.tem_ouro:
                    self.pontos += BONUS_SAIDA_OURO
                    self.motivo = "sucesso"
                else:
                    self.motivo = "desistiu"
                self._registrar(acao)
                return self._calcular_percepcoes(), True
            # ``fim`` fora da casa inicial é uma ação inválida (custa 1 passo).

        elif tipo == "esperar":
            pass

        self.percepcoes = self._calcular_percepcoes()
        self._registrar(acao)

        if self.acoes >= self.limite_passos:
            self.motivo = "limite"
            return self.percepcoes, True

        return self.percepcoes, False

    # ---- resultado -------------------------------------------------------- #
    def resultado(self) -> ResultadoEpisodio:
        sucesso = self.saiu and self.tem_ouro and self.vivo
        if self.motivo == "em_andamento":
            self.motivo = "limite" if not self.saiu else "fim"
        return ResultadoEpisodio(
            sucesso=sucesso,
            morreu=not self.vivo,
            saiu=self.saiu,
            pegou_ouro=self.tem_ouro,
            pontuacao=self.pontos,
            acoes=self.acoes,
            motivo=self.motivo,
            dist_min_ouro=self.dist_min_ouro,
            dist_min_casa=self.dist_min_casa,
            historico=self.historico,
        )


# --------------------------------------------------------------------------- #
# Runner de episódios                                                         #
# --------------------------------------------------------------------------- #

def executar_episodio(
    ambiente: AmbienteWumpus,
    agente: Any,
    limite_passos: Optional[int] = None,
    registrar_historico: bool = False,
) -> ResultadoEpisodio:
    """Executa um episódio completo de ``agente`` no ``ambiente``."""
    simulador = SimuladorWumpus(
        ambiente,
        limite_passos=limite_passos,
        registrar_historico=registrar_historico,
    )
    percepcoes = simulador.percepcoes

    for _ in range(simulador.limite_passos):
        try:
            acao = agente.decidir(percepcoes)
        except Exception as exc:  # pragma: no cover - proteção para agentes externos
            raise RuntimeError(f"Falha ao decidir no agente {type(agente).__name__}: {exc}") from exc

        percepcoes, terminou = simulador.executar(acao)
        if terminou:
            break

    return simulador.resultado()


def criar_agente(
    versao: str,
    n: int,
    seed: Optional[int] = None,
    genoma: Optional[Sequence[int]] = None,
    **kwargs: Any,
) -> Any:
    """Fábrica de agentes integrada ao simulador.

    versao: ``"v1"``, ``"v2"`` ou ``"v3"``.
    """
    versao = versao.lower()
    if versao in {"v1", "1", "agent-v1"}:
        modulo = carregar_agente_v1()
        return modulo.AgenteReativoV1(seed=seed)

    if versao in {"v2", "2", "agent-v2"}:
        modulo = carregar_agente_v2()
        return modulo.AgenteReativoV2(n=n, semente=seed, **kwargs)

    if versao in {"v3", "3", "agent-v3"}:
        modulo = carregar_agente_v3()
        return modulo.AgenteGenetico(n=n, genoma=genoma, seed=seed, **kwargs)

    raise ValueError(f"Versão de agente desconhecida: {versao!r}")


def avaliar_agente(
    versao: str,
    n: int,
    execucoes: int = 30,
    seed_base: int = 0,
    genoma: Optional[Sequence[int]] = None,
    limite_passos: Optional[int] = None,
    config_ambiente: Optional[Dict[str, int]] = None,
    **kwargs: Any,
) -> List[ResultadoEpisodio]:
    """Executa ``execucoes`` episódios com sementes fixas e retorna os resultados."""
    resultados: List[ResultadoEpisodio] = []
    config = config_ambiente or {}
    for i in range(execucoes):
        seed = seed_base + i
        ambiente = criar_ambiente(n, seed=seed, **config)
        agente = criar_agente(versao, n=n, seed=seed, genoma=genoma, **kwargs)
        resultados.append(
            executar_episodio(ambiente, agente, limite_passos=limite_passos)
        )
    return resultados


def resumo(resultados: Sequence[ResultadoEpisodio]) -> Dict[str, float]:
    """Resume uma lista de resultados em métricas agregadas."""
    if not resultados:
        return {}
    return {
        "execucoes": len(resultados),
        "sucessos": sum(r.sucesso for r in resultados),
        "taxa_sucesso": sum(r.sucesso for r in resultados) / len(resultados),
        "mortes": sum(r.morreu for r in resultados),
        "taxa_morte": sum(r.morreu for r in resultados) / len(resultados),
        "pontuacao_media": statistics.mean(r.pontuacao for r in resultados),
        "acoes_medias": statistics.mean(r.acoes for r in resultados),
        "ouro_medio": sum(r.pegou_ouro for r in resultados) / len(resultados),
    }


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def _main() -> None:
    parser = argparse.ArgumentParser(description="Simulador do Mundo de Wumpus")
    parser.add_argument("--agente", default="v2", choices=["v1", "v2", "v3"])
    parser.add_argument("--n", type=int, default=4, help="dimensão do tabuleiro")
    parser.add_argument("--execucoes", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--genoma", type=str, default=None,
                        help="arquivo JSON com o genoma do agente v3")
    parser.add_argument("--json", action="store_true", help="imprime o resultado em JSON")
    args = parser.parse_args()

    genoma = None
    if args.genoma:
        modulo_v3 = carregar_agente_v3()
        genoma = modulo_v3.carregar_genoma(args.genoma)

    resultados = avaliar_agente(
        args.agente, args.n, args.execucoes, seed_base=args.seed, genoma=genoma
    )
    dados = resumo(resultados)

    if args.json:
        print(json.dumps(dados, indent=2, ensure_ascii=False))
        return

    print(f"Agente: {args.agente} | n={args.n} | execuções={args.execucoes}")
    print(f"Sucessos: {int(dados['sucessos'])}/{int(dados['execucoes'])} "
          f"({dados['taxa_sucesso']:.0%})")
    print(f"Mortes:   {int(dados['mortes'])} ({dados['taxa_morte']:.0%})")
    print(f"Pontuação média: {dados['pontuacao_media']:.1f}")
    print(f"Ações médias:    {dados['acoes_medias']:.1f}")


if __name__ == "__main__":
    _main()
