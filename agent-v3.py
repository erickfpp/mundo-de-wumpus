"""
Mundo de Wumpus — Etapa 4: agente de aprendizagem (versão 3).

Esta versão implementa um **agente que aprende um plano de ação** com um
Algoritmo Genético (AG), conforme a Etapa 4 do projeto:

* **Codificação**: o cromossomo é uma sequência de genes; cada gene representa
  uma ação primitiva (mover em uma direção, pegar o ouro ou atirar em uma
  direção).
* **Seleção**: torneio (tamanho configurável).
* **Cruzamento**: uniforme, com taxa de 85% (valor padrão da Etapa 5).
* **Mutação**: substituição aleatória de genes, com taxa de 5% por gene.
* **Elitismo**: os melhores indivíduos passam intactos para a próxima geração.
* **Função de avaliação (fitness)**: pontuação oficial do episódio (Aula 04)
  acrescida de termos de *shaping* que orientam o aprendizado (aproximação do
  ouro, coleta e retorno). A pontuação oficial continua sendo reportada
  separadamente nos experimentos.

Além do plano aprendido, o agente tem dois comportamentos determinísticos de
segurança, que não são evoluídos:

1. **Coleta automática**: ao perceber brilho, ele executa ``pegar``.
2. **Retorno seguro**: depois de pegar o ouro, ele volta para ``(0, 0)``
   revertendo o caminho de movimentos bem-sucedidos. Como o ambiente é
   estático e o caminho já foi percorrido, o retorno é seguro e não depende de
   o AG redescobrir a rota.

Isso mantém o foco do AG no problema realmente difícil — explorar o labirinto,
evitar poços/Wumpus e encontrar o ouro — e garante que, uma vez encontrado o
ouro, o agente consiga voltar para casa.

Integração
----------
O agente segue a mesma interface do agente v2: ``decidir(percepcoes) -> acao``.
As ações retornadas usam a notação ``mov(N)``, ``atirar(L)``, ``pegar`` e
``fim``, aceita pelo ``simulador.py``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]

# (linha, coluna): Norte aumenta a linha; Leste aumenta a coluna.
DIRECOES: Dict[str, Pos] = {
    "N": (1, 0),
    "S": (-1, 0),
    "L": (0, 1),
    "O": (0, -1),
}

# Cada gene é um índice nesta lista.
ACOES_GENOMA: Tuple[str, ...] = (
    "N",
    "S",
    "L",
    "O",
    "pegar",
    "atirar_N",
    "atirar_S",
    "atirar_L",
    "atirar_O",
)

ALIAS_PERCEPCOES = {
    "b": "brisa",
    "brisa": "brisa",
    "f": "fedor",
    "fedor": "fedor",
    "br": "brilho",
    "brilho": "brilho",
    "i": "impacto",
    "impacto": "impacto",
    "g": "grito",
    "grito": "grito",
}

GENOMA = List[int]


# --------------------------------------------------------------------------- #
# Utilidades de percepção e ação                                              #
# --------------------------------------------------------------------------- #

def normalizar_percepcoes(percepcoes: Iterable[str] | str | Dict[str, Any] | None) -> Set[str]:
    if not percepcoes:
        return set()
    if isinstance(percepcoes, dict):
        percepcoes = [k for k, v in percepcoes.items() if v]
    elif isinstance(percepcoes, str):
        percepcoes = [percepcoes]
    return {
        ALIAS_PERCEPCOES[str(p).lower()]
        for p in percepcoes
        if str(p).lower() in ALIAS_PERCEPCOES
    }


def _tipo_acao(acao: str) -> Tuple[str, Optional[str]]:
    """Interpreta uma ação do genoma (sem depender do simulador)."""
    if acao == "pegar":
        return "pegar", None
    if acao.startswith("atirar_"):
        return "atirar", acao.split("_", 1)[1]
    return "mover", acao


def _acao_para_texto(gene: int) -> str:
    nome = ACOES_GENOMA[gene % len(ACOES_GENOMA)]
    if nome == "pegar":
        return "pegar"
    if nome.startswith("atirar_"):
        return f"atirar({nome.split('_', 1)[1]})"
    return f"mov({nome})"


# --------------------------------------------------------------------------- #
# Agente                                                                      #
# --------------------------------------------------------------------------- #

class AgenteGenetico:
    """Agente que executa um plano (cromossomo) aprendido por um AG."""

    def __init__(
        self,
        n: int = 4,
        genoma: Optional[Sequence[int]] = None,
        seed: Optional[int] = None,
        comprimento: Optional[int] = None,
        auto_pegar: bool = True,
        fallback_exploracao: bool = True,
    ) -> None:
        self.n = n
        self.rng = random.Random(seed)
        self.comprimento = comprimento or max(30, n * n + 2 * n)
        self.auto_pegar = auto_pegar
        self.fallback_exploracao = fallback_exploracao

        if genoma is None:
            self.genoma = gerar_genoma_aleatorio(self.comprimento, self.rng)
        else:
            self.genoma = [int(g) % len(ACOES_GENOMA) for g in genoma]
            if len(self.genoma) < self.comprimento:
                self.genoma.extend(
                    gerar_genoma_aleatorio(self.comprimento - len(self.genoma), self.rng)
                )
            elif len(self.genoma) > self.comprimento:
                self.genoma = self.genoma[:self.comprimento]

        self.reiniciar()

    # ---- estado ----------------------------------------------------------- #
    def reiniciar(self) -> None:
        self.pos: Pos = (0, 0)
        self.caminho: List[Pos] = [(0, 0)]
        self.indice_gene = 0
        self.tem_ouro = False
        self.flecha = True
        self.wumpus_morto = False
        self.retornando = False
        self.indice_retorno: Optional[int] = None
        self.ultima_acao: Optional[str] = None
        self.ultima_direcao: Optional[str] = None
        self.tentando_pegar = False
        self.saiu = False
        self.passos = 0
        self.historico: List[Dict[str, Any]] = []

    # ---- interface com o simulador --------------------------------------- #
    def decidir(self, percepcoes: Iterable[str] | str | Dict[str, Any] | None) -> str:
        p = normalizar_percepcoes(percepcoes)
        self._aplicar_efeito_ultima_acao(p)

        if self.saiu:
            return "fim"

        # 1. Retorno seguro para casa depois de pegar o ouro.
        if self.retornando:
            acao = self._proximo_passo_retorno()
            self._definir_ultima_acao(acao)
            return acao

        # 2. Coleta automática do ouro.
        if self.auto_pegar and "brilho" in p and not self.tem_ouro:
            self.tentando_pegar = True
            self._definir_ultima_acao("pegar")
            return "pegar"

        # 3. Executa o próximo gene válido do plano aprendido.
        acao = self._proxima_acao_do_genoma(p)
        if acao is not None:
            self._definir_ultima_acao(acao)
            return acao

        # 4. Plano esgotado: continua explorando para não ficar parado.
        if self.fallback_exploracao:
            acao = self._acao_fallback()
            self._definir_ultima_acao(acao)
            return acao

        return "esperar"

    # ---- efeitos da ação anterior ---------------------------------------- #
    def _aplicar_efeito_ultima_acao(self, percepcoes: Set[str]) -> None:
        acao = self.ultima_acao
        if acao is None:
            return

        if acao == "pegar":
            # Se o brilho desapareceu, a coleta foi concluída pelo simulador.
            if "brilho" not in percepcoes:
                self.tem_ouro = True
                self.tentando_pegar = False
                self.retornando = True
                self.indice_retorno = len(self.caminho) - 2
            else:
                self.tentando_pegar = False

        elif acao.startswith("mov(") and self.ultima_direcao is not None:
            if "impacto" not in percepcoes:
                dl, dc = DIRECOES[self.ultima_direcao]
                self.pos = (self.pos[0] + dl, self.pos[1] + dc)
                if self.retornando:
                    if self.indice_retorno is not None:
                        self.indice_retorno -= 1
                else:
                    self.caminho.append(self.pos)

        elif acao.startswith("atirar("):
            self.flecha = False
            if "grito" in percepcoes:
                self.wumpus_morto = True

        self.ultima_acao = None
        self.ultima_direcao = None

    def _definir_ultima_acao(self, acao: str) -> None:
        self.ultima_acao = acao
        self.ultima_direcao = None
        if acao.startswith("mov("):
            self.ultima_direcao = acao[4]
        elif acao.startswith("atirar("):
            self.ultima_direcao = acao[7]
            self.flecha = False
        self.passos += 1

    # ---- retorno seguro --------------------------------------------------- #
    def _proximo_passo_retorno(self) -> str:
        if self.pos == (0, 0):
            self.saiu = True
            return "fim"

        if self.indice_retorno is None:
            self.indice_retorno = len(self.caminho) - 2

        # Pula posições já alcançadas (por exemplo, se o caminho tinha laços).
        while (
            self.indice_retorno is not None
            and self.indice_retorno >= 0
            and self.caminho[self.indice_retorno] == self.pos
        ):
            self.indice_retorno -= 1

        if self.indice_retorno is None or self.indice_retorno < 0:
            self.saiu = self.pos == (0, 0)
            return "fim" if self.saiu else "esperar"

        alvo = self.caminho[self.indice_retorno]
        direcao = self._direcao(self.pos, alvo)
        if direcao is None:
            # Caminho inconsistente: descarta o alvo e tenta o anterior.
            self.indice_retorno -= 1
            return "esperar"
        return f"mov({direcao})"

    @staticmethod
    def _direcao(origem: Pos, destino: Pos) -> Optional[str]:
        delta = (destino[0] - origem[0], destino[1] - origem[1])
        for nome, valor in DIRECOES.items():
            if valor == delta:
                return nome
        return None

    # ---- plano aprendido -------------------------------------------------- #
    def _proxima_acao_do_genoma(self, percepcoes: Set[str]) -> Optional[str]:
        while self.indice_gene < len(self.genoma):
            gene = self.genoma[self.indice_gene]
            self.indice_gene += 1
            nome = ACOES_GENOMA[gene % len(ACOES_GENOMA)]
            tipo, direcao = _tipo_acao(nome)

            if tipo == "mover":
                assert direcao is not None
                dl, dc = DIRECOES[direcao]
                destino = (self.pos[0] + dl, self.pos[1] + dc)
                if not (0 <= destino[0] < self.n and 0 <= destino[1] < self.n):
                    continue
                return f"mov({direcao})"

            if tipo == "atirar":
                if not self.flecha:
                    continue
                assert direcao is not None
                return f"atirar({direcao})"

            if tipo == "pegar":
                if "brilho" in percepcoes and not self.tem_ouro:
                    self.tentando_pegar = True
                    return "pegar"
                continue

        return None

    def _acao_fallback(self) -> str:
        """Exploração simples e determinística quando o cromossomo termina.

        A ordem fixa (N, S, L, O) garante que o mesmo genoma produza sempre o
        mesmo episódio no mesmo ambiente, independentemente da semente usada
        para o agente. Isso é importante para comparar treino e avaliação.
        """
        visitadas = set(self.caminho)
        direcoes = ("N", "S", "L", "O")

        # Prefere casas ainda não visitadas e dentro do tabuleiro.
        for direcao in direcoes:
            dl, dc = DIRECOES[direcao]
            destino = (self.pos[0] + dl, self.pos[1] + dc)
            if (
                0 <= destino[0] < self.n
                and 0 <= destino[1] < self.n
                and destino not in visitadas
            ):
                return f"mov({direcao})"

        # Se todas as vizinhas já foram visitadas, escolhe uma direção válida.
        for direcao in direcoes:
            dl, dc = DIRECOES[direcao]
            destino = (self.pos[0] + dl, self.pos[1] + dc)
            if 0 <= destino[0] < self.n and 0 <= destino[1] < self.n:
                return f"mov({direcao})"

        return "esperar"

    # ---- persistência ----------------------------------------------------- #
    def salvar_genoma(self, caminho: str | Path) -> None:
        Path(caminho).write_text(
            json.dumps({"n": self.n, "genoma": self.genoma}, indent=2),
            encoding="utf-8",
        )


# --------------------------------------------------------------------------- #
# Algoritmo Genético                                                          #
# --------------------------------------------------------------------------- #

@dataclass
class ParametrosGA:
    tamanho_populacao: int = 50
    geracoes: int = 1000
    taxa_cruzamento: float = 0.85
    taxa_mutacao: float = 0.05
    elitismo: int = 2
    tamanho_torneio: int = 3
    comprimento_genoma: Optional[int] = None
    limite_passos: Optional[int] = None
    seed: Optional[int] = None
    n_treino: int = 1
    config_ambiente: Optional[Dict[str, int]] = None

    def como_dicionario(self) -> Dict[str, Any]:
        return {
            "tamanho_populacao": self.tamanho_populacao,
            "geracoes": self.geracoes,
            "taxa_cruzamento": self.taxa_cruzamento,
            "taxa_mutacao": self.taxa_mutacao,
            "elitismo": self.elitismo,
            "tamanho_torneio": self.tamanho_torneio,
            "comprimento_genoma": self.comprimento_genoma,
            "limite_passos": self.limite_passos,
            "seed": self.seed,
            "n_treino": self.n_treino,
            "config_ambiente": self.config_ambiente,
        }


@dataclass
class ResultadoTreinamento:
    n: int
    genoma: GENOMA
    fitness: float
    pontuacao_media: float
    taxa_sucesso: float
    historico: List[Dict[str, float]] = field(default_factory=list)
    parametros: Dict[str, Any] = field(default_factory=dict)

    def como_dicionario(self) -> Dict[str, Any]:
        return {
            "n": self.n,
            "genoma": self.genoma,
            "fitness": self.fitness,
            "pontuacao_media": self.pontuacao_media,
            "taxa_sucesso": self.taxa_sucesso,
            "historico": self.historico,
            "parametros": self.parametros,
        }


def gerar_genoma_aleatorio(comprimento: int, rng: random.Random) -> GENOMA:
    return [rng.randrange(len(ACOES_GENOMA)) for _ in range(comprimento)]


def _indice_acao(nome: str) -> int:
    return ACOES_GENOMA.index(nome)


def genoma_snake(n: int, comprimento: int, rng: random.Random) -> GENOMA:
    """Cromossomo-semente que percorre o tabuleiro em zigue-zague (snake)."""
    genes: GENOMA = []
    for lin in range(n):
        cols = range(n) if lin % 2 == 0 else range(n - 1, -1, -1)
        anterior: Optional[int] = None
        for col in cols:
            if anterior is not None:
                genes.append(_indice_acao("L" if col > anterior else "O"))
            anterior = col
        if lin < n - 1:
            genes.append(_indice_acao("N"))

    if len(genes) < comprimento:
        genes.extend(gerar_genoma_aleatorio(comprimento - len(genes), rng))
    return genes[:comprimento]


def genoma_espiral(n: int, comprimento: int, rng: random.Random) -> GENOMA:
    """Cromossomo-semente em espiral (diversidade para a população inicial)."""
    visitadas: Set[Pos] = {(0, 0)}
    pos = (0, 0)
    genes: GENOMA = []
    ordem = ["L", "N", "O", "S"]
    indice = 0
    while len(visitadas) < n * n:
        moveu = False
        for _ in range(4):
            direcao = ordem[indice % 4]
            dl, dc = DIRECOES[direcao]
            while True:
                destino = (pos[0] + dl, pos[1] + dc)
                if not (0 <= destino[0] < n and 0 <= destino[1] < n):
                    break
                if destino in visitadas:
                    break
                genes.append(_indice_acao(direcao))
                pos = destino
                visitadas.add(pos)
                moveu = True
            indice += 1
            if moveu:
                break
        if not moveu:
            break

    if len(genes) < comprimento:
        genes.extend(gerar_genoma_aleatorio(comprimento - len(genes), rng))
    return genes[:comprimento]


def populacao_inicial(
    n: int,
    tamanho: int,
    comprimento: int,
    rng: random.Random,
) -> List[GENOMA]:
    populacao: List[GENOMA] = [
        genoma_snake(n, comprimento, rng),
        genoma_espiral(n, comprimento, rng),
    ]
    for direcao in ("N", "S", "L", "O"):
        populacao.append(
            [_indice_acao(direcao)] * comprimento
        )
    while len(populacao) < tamanho:
        populacao.append(gerar_genoma_aleatorio(comprimento, rng))
    return populacao[:tamanho]


def selecao_torneio(
    populacao: Sequence[GENOMA],
    fitness: Sequence[float],
    tamanho_torneio: int,
    rng: random.Random,
) -> GENOMA:
    indices = rng.sample(range(len(populacao)), min(tamanho_torneio, len(populacao)))
    melhor = max(indices, key=lambda i: fitness[i])
    return list(populacao[melhor])


def cruzamento(
    pai1: GENOMA,
    pai2: GENOMA,
    taxa: float,
    rng: random.Random,
) -> GENOMA:
    if rng.random() >= taxa:
        return list(pai1)
    filho: GENOMA = []
    for gene1, gene2 in zip(pai1, pai2):
        filho.append(gene1 if rng.random() < 0.5 else gene2)
    return filho


def mutacao(genoma: GENOMA, taxa: float, rng: random.Random) -> GENOMA:
    for i in range(len(genoma)):
        if rng.random() < taxa:
            genoma[i] = rng.randrange(len(ACOES_GENOMA))
    return genoma


def _fitness(resultado: Any, n: int) -> float:
    """Fitness de treinamento: pontuação oficial + shaping pedagógico."""
    max_dist = max(1, 2 * (n - 1))
    progresso_ouro = 1.0 - min(resultado.dist_min_ouro, max_dist) / max_dist
    fitness = float(resultado.pontuacao)
    fitness += 200.0 * progresso_ouro
    if resultado.pegou_ouro:
        fitness += 250.0
    if resultado.sucesso:
        fitness += 250.0
        progresso_casa = 1.0 - min(resultado.dist_min_casa, max_dist) / max_dist
        fitness += 100.0 * progresso_casa
    return fitness


def avaliar_genoma(
    genoma: Sequence[int],
    n: int,
    seeds_treino: Sequence[int],
    limite_passos: Optional[int] = None,
    config_ambiente: Optional[Dict[str, int]] = None,
) -> Tuple[float, float, float]:
    """Avalia um genoma em um conjunto fixo de ambientes de treino.

    Retorna ``(fitness_media, pontuacao_media, taxa_sucesso)``.
    """
    # Importação tardia para evitar ciclo com simulador.py.
    from ambiente import criar_ambiente
    from simulador import executar_episodio

    config = config_ambiente or {}
    fitness: List[float] = []
    pontuacoes: List[float] = []
    sucessos = 0

    for seed in seeds_treino:
        ambiente = criar_ambiente(n, seed=seed, **config)
        agente = AgenteGenetico(n=n, genoma=genoma, seed=seed)
        resultado = executar_episodio(
            ambiente, agente, limite_passos=limite_passos
        )
        fitness.append(_fitness(resultado, n))
        pontuacoes.append(resultado.pontuacao)
        sucessos += int(resultado.sucesso)

    return (
        sum(fitness) / len(fitness),
        sum(pontuacoes) / len(pontuacoes),
        sucessos / len(seeds_treino),
    )


def treinar(
    n: int,
    parametros: Optional[ParametrosGA] = None,
    seeds_treino: Optional[Sequence[int]] = None,
    log: Optional[Callable[[str], None]] = None,
    log_a_cada: int = 0,
) -> ResultadoTreinamento:
    """Executa o Algoritmo Genético e devolve o melhor cromossomo."""
    params = parametros or ParametrosGA()
    if not seeds_treino:
        seed_base = params.seed if params.seed is not None else 0
        seeds_treino = [seed_base + i for i in range(max(1, params.n_treino))]

    rng = random.Random(params.seed)
    comprimento = params.comprimento_genoma or max(30, n * n + 2 * n)

    populacao = populacao_inicial(
        n=n,
        tamanho=params.tamanho_populacao,
        comprimento=comprimento,
        rng=rng,
    )

    historico: List[Dict[str, float]] = []
    melhor_genoma: GENOMA = list(populacao[0])
    melhor_fitness = -math.inf
    melhor_pontuacao = -math.inf
    melhor_taxa = 0.0

    for geracao in range(1, params.geracoes + 1):
        avaliacoes = [
            avaliar_genoma(
                genoma,
                n=n,
                seeds_treino=seeds_treino,
                limite_passos=params.limite_passos,
                config_ambiente=params.config_ambiente,
            )
            for genoma in populacao
        ]
        fitness = [a[0] for a in avaliacoes]
        pontuacoes = [a[1] for a in avaliacoes]
        taxas = [a[2] for a in avaliacoes]

        ordem = sorted(range(len(populacao)), key=lambda i: fitness[i], reverse=True)
        melhor_idx = ordem[0]

        if fitness[melhor_idx] > melhor_fitness:
            melhor_fitness = fitness[melhor_idx]
            melhor_genoma = list(populacao[melhor_idx])
            melhor_pontuacao = pontuacoes[melhor_idx]
            melhor_taxa = taxas[melhor_idx]

        media = sum(fitness) / len(fitness)
        pior = min(fitness)
        historico.append({
            "geracao": geracao,
            "melhor": round(fitness[melhor_idx], 3),
            "pior": round(pior, 3),
            "media": round(media, 3),
            "pontuacao_melhor": round(pontuacoes[melhor_idx], 3),
            "taxa_sucesso_melhor": round(taxas[melhor_idx], 3),
        })

        if log and (log_a_cada > 0 and (geracao % log_a_cada == 0 or geracao == 1)):
            log(
                f"geração {geracao:>4}/{params.geracoes} | "
                f"melhor={fitness[melhor_idx]:>9.1f} | "
                f"média={media:>9.1f} | pior={pior:>9.1f}"
            )

        # Elitismo.
        elite = [list(populacao[i]) for i in ordem[:max(0, params.elitismo)]]
        nova_populacao: List[GENOMA] = elite

        while len(nova_populacao) < params.tamanho_populacao:
            pai1 = selecao_torneio(
                populacao, fitness, params.tamanho_torneio, rng
            )
            pai2 = selecao_torneio(
                populacao, fitness, params.tamanho_torneio, rng
            )
            filho = cruzamento(pai1, pai2, params.taxa_cruzamento, rng)
            filho = mutacao(filho, params.taxa_mutacao, rng)
            nova_populacao.append(filho)

        populacao = nova_populacao

    return ResultadoTreinamento(
        n=n,
        genoma=melhor_genoma,
        fitness=melhor_fitness,
        pontuacao_media=melhor_pontuacao,
        taxa_sucesso=melhor_taxa,
        historico=historico,
        parametros={
            **params.como_dicionario(),
            "seeds_treino": list(seeds_treino),
            "comprimento_genoma": comprimento,
        },
    )


# --------------------------------------------------------------------------- #
# Persistência e CLI                                                          #
# --------------------------------------------------------------------------- #

def salvar_resultado(caminho: str | Path, resultado: ResultadoTreinamento) -> None:
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(resultado.como_dicionario(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def carregar_genoma(caminho: str | Path) -> GENOMA:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if isinstance(dados, dict):
        dados = dados.get("genoma", [])
    if not isinstance(dados, list):
        raise ValueError(f"Genoma inválido em {caminho}")
    return [int(g) for g in dados]


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Agente de aprendizagem do Mundo de Wumpus (Etapa 4)"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    treino = sub.add_parser("treinar", help="treina um cromossomo com AG")
    treino.add_argument("--n", type=int, default=4)
    treino.add_argument("--geracoes", type=int, default=1000)
    treino.add_argument("--populacao", type=int, default=50)
    treino.add_argument("--taxa-cruzamento", type=float, default=0.85)
    treino.add_argument("--taxa-mutacao", type=float, default=0.05)
    treino.add_argument("--elitismo", type=int, default=2)
    treino.add_argument("--torneio", type=int, default=3)
    treino.add_argument("--seed", type=int, default=0)
    treino.add_argument("--comprimento", type=int, default=None)
    treino.add_argument("--treino-seeds", type=str, default=None,
                        help="sementes separadas por vírgula (padrão: seed)")
    treino.add_argument("--pocos", type=int, default=3)
    treino.add_argument("--wumpus", type=int, default=1)
    treino.add_argument("--ouro", type=int, default=1)
    treino.add_argument("--log-a-cada", type=int, default=50)
    treino.add_argument("--saida", type=str, default=None)
    treino.add_argument("--rapido", action="store_true",
                        help="preset curto para demonstração")

    avaliacao = sub.add_parser("avaliar", help="avalia um genoma salvo")
    avaliacao.add_argument("--n", type=int, default=4)
    avaliacao.add_argument("--genoma", type=str, required=True)
    avaliacao.add_argument("--execucoes", type=int, default=30)
    avaliacao.add_argument("--seed", type=int, default=0)

    demo = sub.add_parser("demo", help="treino curto + avaliação")
    demo.add_argument("--n", type=int, default=4)

    args = parser.parse_args()

    if args.comando == "treinar":
        if args.rapido:
            args.geracoes = min(args.geracoes, 50)
            args.populacao = min(args.populacao, 30)
            args.log_a_cada = min(args.log_a_cada, 10)

        seeds = None
        if args.treino_seeds:
            seeds = [int(s) for s in args.treino_seeds.split(",") if s.strip()]

        params = ParametrosGA(
            tamanho_populacao=args.populacao,
            geracoes=args.geracoes,
            taxa_cruzamento=args.taxa_cruzamento,
            taxa_mutacao=args.taxa_mutacao,
            elitismo=args.elitismo,
            tamanho_torneio=args.torneio,
            comprimento_genoma=args.comprimento,
            seed=args.seed,
            n_treino=len(seeds) if seeds else 1,
            config_ambiente={
                "qtd_pocos": args.pocos,
                "qtd_wumpus": args.wumpus,
                "qtd_ouro": args.ouro,
            },
        )
        resultado = treinar(
            args.n,
            parametros=params,
            seeds_treino=seeds,
            log=print,
            log_a_cada=args.log_a_cada,
        )
        print(
            f"\nMelhor fitness: {resultado.fitness:.1f} | "
            f"pontuação média: {resultado.pontuacao_media:.1f} | "
            f"sucesso: {resultado.taxa_sucesso:.0%}"
        )
        if args.saida:
            salvar_resultado(args.saida, resultado)
            print(f"Resultado salvo em {args.saida}")

    elif args.comando == "avaliar":
        from simulador import avaliar_agente, resumo

        genoma = carregar_genoma(args.genoma)
        resultados = avaliar_agente(
            "v3", args.n, args.execucoes, seed_base=args.seed, genoma=genoma
        )
        dados = resumo(resultados)
        print(json.dumps(dados, indent=2, ensure_ascii=False))

    elif args.comando == "demo":
        params = ParametrosGA(
            tamanho_populacao=30,
            geracoes=60,
            seed=0,
            n_treino=1,
            config_ambiente={"qtd_pocos": 3, "qtd_wumpus": 1, "qtd_ouro": 1},
        )
        resultado = treinar(
            args.n, parametros=params, log=print, log_a_cada=10
        )
        from simulador import avaliar_agente, resumo

        dados = resumo(
            avaliar_agente(
                "v3", args.n, 10, seed_base=1000, genoma=resultado.genoma
            )
        )
        print(json.dumps(dados, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
