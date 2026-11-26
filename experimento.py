"""
Experimento da Etapa 5 — validação e resultados.

Executa os agentes v1, v2 e v3 nos tamanhos de ambiente pedidos pela
especificação (4, 5, 10, 15 e 20), com uma configuração fixa de objetos
(3 poços, 1 Wumpus e 1 ouro), e gera:

* tabela CSV com o resultado de cada execução;
* resumo por agente/tamanho;
* histórico do Algoritmo Genético (melhor, pior e média por geração);
* gráficos de sucesso, pontuação e fitness (quando matplotlib está instalado).

Dois modos de avaliação do v3 estão disponíveis:

``fixo`` (padrão)
    O agente v3 treina e é avaliado no mesmo ambiente fixo de cada tamanho.
    É o modo mais direto para demonstrar o aprendizado do plano.

``generalizacao``
    O agente v3 treina em um conjunto de ambientes e é avaliado em outros.
    Serve para medir o quanto o plano aprendido generaliza.

Uso rápido::

    python experimento.py --rapido

Uso completo (configuração da Etapa 5)::

    python experimento.py --execucoes 30 --geracoes 1000 --populacao 50
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ambiente import criar_ambiente
from compat import carregar_agente_v3
from simulador import (
    ResultadoEpisodio,
    criar_agente,
    executar_episodio,
    resumo,
)

CONFIG_AMBIENTE = {"qtd_pocos": 3, "qtd_wumpus": 1, "qtd_ouro": 1}
TAMANHOS_PADRAO = (4, 5, 10, 15, 20)
AGENTES = ("v1", "v2", "v3")


def _resultado_para_linha(
    n: int,
    execucao: int,
    agente: str,
    resultado: ResultadoEpisodio,
) -> Dict[str, Any]:
    return {
        "n": n,
        "execucao": execucao,
        "agente": agente,
        "sucesso": int(resultado.sucesso),
        "morreu": int(resultado.morreu),
        "saiu": int(resultado.saiu),
        "pegou_ouro": int(resultado.pegou_ouro),
        "pontuacao": resultado.pontuacao,
        "acoes": resultado.acoes,
        "motivo": resultado.motivo,
        "dist_min_ouro": resultado.dist_min_ouro,
        "dist_min_casa": resultado.dist_min_casa,
    }


def _executar_no_ambiente_fixo(
    versao: str,
    n: int,
    seed_ambiente: int,
    seed_agente: int,
    genoma: Optional[Sequence[int]] = None,
) -> ResultadoEpisodio:
    ambiente = criar_ambiente(n, seed=seed_ambiente, **CONFIG_AMBIENTE)
    agente = criar_agente(versao, n=n, seed=seed_agente, genoma=genoma)
    return executar_episodio(ambiente, agente)


def _treinar_v3(
    n: int,
    geracoes: int,
    populacao: int,
    seed: int,
    modo: str,
    treino_seeds: Sequence[int],
    taxa_cruzamento: float,
    taxa_mutacao: float,
    log_a_cada: int = 0,
) -> Any:
    modulo = carregar_agente_v3()
    params = modulo.ParametrosGA(
        tamanho_populacao=populacao,
        geracoes=geracoes,
        taxa_cruzamento=taxa_cruzamento,
        taxa_mutacao=taxa_mutacao,
        seed=seed,
        n_treino=len(treino_seeds),
        config_ambiente=CONFIG_AMBIENTE,
    )
    if modo == "fixo":
        seeds = [treino_seeds[0]]
    else:
        seeds = list(treino_seeds)
    return modulo.treinar(
        n,
        parametros=params,
        seeds_treino=seeds,
        log_a_cada=log_a_cada,
    )


def _salvar_csv(caminho: Path, linhas: Sequence[Dict[str, Any]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not linhas:
        return
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
        escritor.writeheader()
        escritor.writerows(linhas)


def _salvar_historico(caminho: Path, historico: Sequence[Dict[str, Any]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(historico[0].keys()))
        escritor.writeheader()
        escritor.writerows(historico)


def _graficos(
    resumos: Sequence[Dict[str, Any]],
    historicos: Dict[int, Sequence[Dict[str, Any]]],
    pasta: Path,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("[aviso] matplotlib não instalado; gráficos não serão gerados.")
        return

    pasta.mkdir(parents=True, exist_ok=True)

    # 1. Taxa de sucesso por tamanho e agente.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    largura = 0.25
    for i, agente in enumerate(AGENTES):
        dados = [r for r in resumos if r["agente"] == agente]
        xs = [r["n"] for r in dados]
        ys = [r["taxa_sucesso"] for r in dados]
        ax.bar([x + (i - 1) * largura for x in xs], ys, width=largura, label=agente)
    ax.set_xlabel("Tamanho do ambiente (n)")
    ax.set_ylabel("Taxa de sucesso")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(sorted({r["n"] for r in resumos}))
    ax.set_title("Mundo de Wumpus — taxa de sucesso por agente")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(pasta / "sucesso_por_tamanho.png", dpi=160)
    plt.close(fig)

    # 2. Pontuação média.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for agente in AGENTES:
        dados = [r for r in resumos if r["agente"] == agente]
        ax.plot(
            [r["n"] for r in dados],
            [r["pontuacao_media"] for r in dados],
            marker="o",
            label=agente,
        )
    ax.set_xlabel("Tamanho do ambiente (n)")
    ax.set_ylabel("Pontuação média")
    ax.set_title("Mundo de Wumpus — pontuação média")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(pasta / "pontuacao_por_tamanho.png", dpi=160)
    plt.close(fig)

    # 3. Evolução do fitness do v3.
    for n, historico in historicos.items():
        fig, ax = plt.subplots(figsize=(8, 4.5))
        geracoes = [h["geracao"] for h in historico]
        ax.plot(geracoes, [h["melhor"] for h in historico], label="melhor")
        ax.plot(geracoes, [h["media"] for h in historico], label="média")
        ax.plot(geracoes, [h["pior"] for h in historico], label="pior")
        ax.set_xlabel("Geração")
        ax.set_ylabel("Fitness")
        ax.set_title(f"Agente v3 — evolução do fitness (n={n})")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(pasta / f"fitness_v3_n{n}.png", dpi=160)
        plt.close(fig)


def executar_experimento(args: argparse.Namespace) -> None:
    inicio = time.time()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "genomas").mkdir(parents=True, exist_ok=True)

    linhas: List[Dict[str, Any]] = []
    resumos: List[Dict[str, Any]] = []
    historicos: Dict[int, Sequence[Dict[str, Any]]] = {}

    print(f"Configuração do ambiente: {CONFIG_AMBIENTE}")
    print(f"Modo do v3: {args.modo_v3} | execuções: {args.execucoes} | "
          f"gerações: {args.geracoes} | população: {args.populacao}")

    for n in args.tamanhos:
        seed_fixo = args.seed + 1000 + n
        seed_teste_base = args.seed + 10_000 + 100 * n
        if args.modo_v3 == "fixo":
            treino_seeds = [seed_fixo]
        else:
            treino_seeds = [
                args.seed + 20_000 + 100 * n + i
                for i in range(args.treino_ambientes)
            ]

        print(f"\n=== n = {n} ===")
        if args.modo_v3 == "fixo":
            print(f"  ambiente fixo: seed={seed_fixo}")
        else:
            print(f"  treino: {treino_seeds} | teste: seeds "
                  f"{seed_teste_base}..{seed_teste_base + args.execucoes - 1}")

        # Treina o v3 uma ou mais vezes.
        genomas: List[Sequence[int]] = []
        for t in range(max(1, args.v3_treinos)):
            print(f"  treinando v3 ({t + 1}/{max(1, args.v3_treinos)})...")
            resultado = _treinar_v3(
                n=n,
                geracoes=args.geracoes,
                populacao=args.populacao,
                seed=args.seed + t,
                modo=args.modo_v3,
                treino_seeds=treino_seeds,
                taxa_cruzamento=args.taxa_cruzamento,
                taxa_mutacao=args.taxa_mutacao,
                log_a_cada=args.log_a_cada,
            )
            genomas.append(resultado.genoma)
            historicos[n] = resultado.historico
            if t == 0:
                modulo = carregar_agente_v3()
                modulo.salvar_resultado(
                    saida / "genomas" / f"v3_n{n}.json", resultado
                )
                _salvar_historico(
                    saida / f"historico_v3_n{n}.csv", resultado.historico
                )
            print(f"    fitness={resultado.fitness:.1f} | "
                  f"pontuação={resultado.pontuacao_media:.1f} | "
                  f"sucesso={resultado.taxa_sucesso:.0%}")

        # Avalia os três agentes.
        for i in range(args.execucoes):
            if args.modo_v3 == "fixo":
                seed_amb = seed_fixo
                seed_agente = seed_fixo + i
                genoma = genomas[i % len(genomas)]
                for agente in AGENTES:
                    resultado = _executar_no_ambiente_fixo(
                        agente, n, seed_amb, seed_agente, genoma
                    )
                    linhas.append(_resultado_para_linha(n, i + 1, agente, resultado))
            else:
                seed_amb = seed_teste_base + i
                genoma = genomas[i % len(genomas)]
                for agente in AGENTES:
                    ambiente = criar_ambiente(n, seed=seed_amb, **CONFIG_AMBIENTE)
                    instancia = criar_agente(
                        agente, n=n, seed=seed_amb, genoma=genoma
                    )
                    resultado = executar_episodio(ambiente, instancia)
                    linhas.append(_resultado_para_linha(n, i + 1, agente, resultado))

        # Resumo por agente.
        for agente in AGENTES:
            resultados = [
                r for r in linhas if r["n"] == n and r["agente"] == agente
            ]
            dados = resumo([
                ResultadoEpisodio(
                    sucesso=bool(r["sucesso"]),
                    morreu=bool(r["morreu"]),
                    saiu=bool(r["saiu"]),
                    pegou_ouro=bool(r["pegou_ouro"]),
                    pontuacao=r["pontuacao"],
                    acoes=r["acoes"],
                    motivo=r["motivo"],
                    dist_min_ouro=r["dist_min_ouro"],
                    dist_min_casa=r["dist_min_casa"],
                )
                for r in resultados
            ])
            resumos.append({"n": n, "agente": agente, **dados})
            print(f"  {agente}: sucesso={dados['taxa_sucesso']:.0%} | "
                  f"mortes={dados['taxa_morte']:.0%} | "
                  f"pontos={dados['pontuacao_media']:.0f} | "
                  f"ações={dados['acoes_medias']:.0f}")

    _salvar_csv(saida / "resultados.csv", linhas)
    _salvar_csv(saida / "resumo.csv", resumos)
    _graficos(resumos, historicos, saida / "graficos")

    duracao = time.time() - inicio
    print(f"\nResultados salvos em {saida.resolve()}")
    print(f"Tempo total: {duracao:.1f}s")
    print("\nResumo geral:")
    print(f"{'n':>3} {'agente':>7} {'sucesso':>8} {'mortes':>7} "
          f"{'pontos':>9} {'ações':>7}")
    for r in resumos:
        print(f"{r['n']:>3} {r['agente']:>7} {r['taxa_sucesso']:>7.0%} "
              f"{r['taxa_morte']:>7.0%} {r['pontuacao_media']:>9.1f} "
              f"{r['acoes_medias']:>7.1f}")


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Experimento da Etapa 5 do Mundo de Wumpus"
    )
    parser.add_argument("--tamanhos", type=int, nargs="+", default=list(TAMANHOS_PADRAO))
    parser.add_argument("--execucoes", type=int, default=30)
    parser.add_argument("--geracoes", type=int, default=1000)
    parser.add_argument("--populacao", type=int, default=50)
    parser.add_argument("--taxa-cruzamento", type=float, default=0.85)
    parser.add_argument("--taxa-mutacao", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--treino-ambientes", type=int, default=5)
    parser.add_argument("--v3-treinos", type=int, default=1,
                        help="número de treinamentos independentes do v3 por n")
    parser.add_argument("--modo-v3", choices=["fixo", "generalizacao"], default="fixo")
    parser.add_argument("--saida", type=str, default="resultados")
    parser.add_argument("--log-a-cada", type=int, default=0)
    parser.add_argument("--rapido", action="store_true",
                        help="preset curto para demonstração")
    args = parser.parse_args()

    if args.rapido:
        args.tamanhos = [4, 5, 10]
        args.execucoes = min(args.execucoes, 5)
        args.geracoes = min(args.geracoes, 50)
        args.populacao = min(args.populacao, 30)
        args.v3_treinos = 1
        args.log_a_cada = 10

    executar_experimento(args)


if __name__ == "__main__":
    _main()
