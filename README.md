# Mundo de Wumpus 🏹

Implementação do projeto da disciplina **Inteligência Computacional** (FECOMP/UFPA):
o clássico **Mundo de Wumpus** com gerador de ambientes, simulador pontuado e três
versões de agentes — do agente reativo simples ao **agente de aprendizagem com
Algoritmos Genéticos** (Etapa 4).

O repositório também inclui a infraestrutura da **Etapa 5**: execução dos agentes
nos tamanhos `n = 4, 5, 10, 15, 20`, 30 execuções por configuração, exportação de
resultados em CSV/JSON e geração de gráficos de desempenho e evolução do fitness.

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Licença" src="https://img.shields.io/badge/licen%C3%A7a-MIT-green">
  <img alt="Testes" src="https://img.shields.io/badge/testes-pytest-0A9EDC?logo=pytest&logoColor=white">
</p>

---

## Índice

- [Visão geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Requisitos e instalação](#requisitos-e-instalação)
- [Como usar](#como-usar)
- [Regras do ambiente](#regras-do-ambiente)
- [Pontuação oficial](#pontuação-oficial)
- [Agentes](#agentes)
- [Agente v3: Algoritmo Genético](#agente-v3-algoritmo-genético)
- [Experimentos da Etapa 5](#experimentos-da-etapa-5)
- [Testes](#testes)
- [Fluxo de Git](#fluxo-de-git)
- [Licença](#licença)

---

## Visão geral

O projeto evolui em etapas:

| Etapa | Entrega | Implementação |
| :---: | :--- | :--- |
| 1 | Gerador do ambiente e percepções | [`ambiente.py`](ambiente.py) |
| 2 | Agente reativo simples (v1) | [`agent-v1.py`](agent-v1.py) |
| 3 | Agente reativo baseado em modelo (v2) | [`agent-v2.py`](agent-v2.py) |
| 4 | Agente de aprendizagem com Algoritmos Genéticos (v3) | [`agent-v3.py`](agent-v3.py) |
| 5 | Experimentos, tabelas e gráficos | [`experimento.py`](experimento.py) |

O simulador ([`simulador.py`](simulador.py)) é a camada de integração: aplica as
ações, calcula percepções, controla a pontuação e executa episódios completos com
qualquer um dos três agentes.

---

## Funcionalidades

- 🗺️ **Gerador reprodutível** de ambientes `n × n` com poços, Wumpus e ouro,
  usando sementes (`seed`) para experimentos comparáveis.
- 🎯 **Simulador completo** com movimentos, paredes, tiros, coleta de ouro,
  morte por poço/Wumpus, saída e pontuação oficial.
- 🤖 **Três agentes** com a mesma interface `decidir(percepcoes) -> acao`.
- 🧠 **Agente v2** com memória, inferência lógica de perigo, busca em largura e
  heurística de utilidade.
- 🧬 **Agente v3** que aprende um plano de ação com Algoritmo Genético
  (torneio, cruzamento uniforme, mutação e elitismo).
- 📊 **Experimentos automatizados** com CSV, JSON, histórico por geração e
  gráficos em PNG.
- ✅ **Testes de integração** com `pytest`.

---

## Estrutura do repositório

```text
mundo-de-wumpus/
├── ambiente.py              # Gerador do ambiente e percepções (Etapa 1)
├── agent-v1.py              # Agente reativo simples (Etapa 2)
├── agent-v2.py              # Agente reativo baseado em modelo (Etapa 3)
├── agent-v3.py              # Agente de aprendizagem com AG (Etapa 4)
├── simulador.py             # Simulador, pontuação e fábrica de agentes
├── experimento.py           # Experimentos e gráficos da Etapa 5
├── compat.py                # Carregamento dos módulos com hífen no nome
├── tests/
│   ├── conftest.py
│   ├── test_integracao.py
│   └── teste_manual_v2.py   # Teste manual independente do agente v2
├── docs/rascunhos/
│   └── agente_objetivos.py  # Rascunho não oficial preservado
├── genomas/                 # Genomas treinados (JSON)
├── resultados/              # CSV, JSON e gráficos gerados
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── LICENSE
```

> Os arquivos `agent-v1.py`, `agent-v2.py` e `agent-v3.py` mantêm os nomes
> originais do projeto. Como hífen não é válido em nomes de módulos Python, o
> [`compat.py`](compat.py) centraliza o carregamento via `importlib`.

---

## Requisitos e instalação

- **Python 3.10+** (o projeto usa anotações modernas como `int | None`).
- O núcleo funciona apenas com a **biblioteca padrão**.
- `matplotlib` é opcional, mas necessário para gerar os gráficos da Etapa 5.

### Criando o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

pip install -r requirements-dev.txt
```

Se você só quer executar os agentes, sem gerar gráficos nem rodar testes:

```bash
pip install -r requirements.txt
```

---

## Como usar

### 1. Visualizar um ambiente

```bash
python ambiente.py
```

O gerador cria um tabuleiro com a casa `(0, 0)` vazia, poços, um Wumpus e o
ouro, e imprime as percepções de cada casa.

### 2. Executar um agente no simulador

```bash
# v1, v2 ou v3
python simulador.py --agente v2 --n 4 --execucoes 30 --seed 0

# saída em JSON
python simulador.py --agente v2 --n 10 --execucoes 30 --json
```

### 3. Treinar o agente v3

```bash
# treino completo (parâmetros da Etapa 5)
python agent-v3.py treinar --n 4 --geracoes 1000 --populacao 50 \
    --saida genomas/v3_n4.json

# treino rápido para demonstração
python agent-v3.py treinar --n 4 --rapido --saida genomas/v3_n4_rapido.json
```

### 4. Avaliar um genoma salvo

```bash
python agent-v3.py avaliar --n 4 --genoma genomas/v3_n4.json --execucoes 30
```

### 5. Demonstração completa do v3

```bash
python agent-v3.py demo --n 4
```

### 6. Rodar os experimentos da Etapa 5

```bash
# configuração completa
python experimento.py --execucoes 30 --geracoes 1000 --populacao 50

# demonstração rápida
python experimento.py --rapido
```

Os arquivos são gravados em `resultados/`:

```text
resultados/
├── resultados.csv          # uma linha por execução
├── resumo.csv              # médias por agente e tamanho
├── historico_v3_n4.csv     # fitness por geração (melhor/média/pior)
├── ...
├── genomas/v3_n4.json      # melhor genoma de cada tamanho
└── graficos/
    ├── sucesso_por_tamanho.png
    ├── pontuacao_por_tamanho.png
    └── fitness_v3_n4.png
```

---

## Regras do ambiente

### Coordenadas

O projeto adota a convenção **(linha, coluna)**:

- `(0, 0)` é o canto **inferior esquerdo** da matriz;
- **N** aumenta a linha, **S** diminui a linha;
- **L** aumenta a coluna, **O** diminui a coluna.

### Ações

| Ação | Efeito |
| :--- | :--- |
| `mov(N)`, `mov(S)`, `mov(L)`, `mov(O)` | move uma casa na direção indicada |
| `atirar(N)`, `atirar(S)`, `atirar(L)`, `atirar(O)` | gasta a flecha na direção indicada |
| `pegar` | coleta o ouro se estiver na mesma casa |
| `fim` | encerra o episódio; só é sucesso em `(0, 0)` com o ouro |

O simulador também aceita aliases como `mover_norte`, `atirar_oeste` etc.

### Percepções

| Percepção | Significado |
| :--- | :--- |
| `brisa` (`b`) | há poço em uma casa vizinha |
| `fedor` (`f`) | há Wumpus em uma casa vizinha |
| `brilho` (`br`) | há ouro na casa atual |
| `impacto` (`i`) | o movimento bateu na parede |
| `grito` (`g`) | o tiro matou o Wumpus |

### Dinâmica

- A casa `(0, 0)` começa vazia e é a saída.
- Pisar em poço ou Wumpus encerra o episódio com morte.
- O Wumpus pode ser morto com a única flecha.
- O ouro só pode ser coletado com `pegar` na casa onde há `brilho`.
- O episódio termina com `fim` em `(0, 0)`; se o agente tiver o ouro, é sucesso.

---

## Pontuação oficial

Conforme a Aula 04:

| Evento | Pontos |
| :--- | ---: |
| Cada ação executada | **−1** |
| Cada flecha disparada | **−10** |
| Morte por poço ou Wumpus | **−1000** |
| Sair de `(0, 0)` com o ouro | **+1000** |

Exemplo: sair com o ouro em 4 ações e 0 tiros → `-4 + 1000 = 996` pontos.

---

## Agentes

| Versão | Arquivo | Estratégia | Memória | Aprendizado |
| :---: | :--- | :--- | :---: | :---: |
| v1 | `agent-v1.py` | Reativo simples: regras por prioridade e escolha aleatória | ❌ | ❌ |
| v2 | `agent-v2.py` | Reativo baseado em modelo: inferência de perigo + BFS + utilidade | ✅ | ❌ |
| v3 | `agent-v3.py` | Plano de ação evoluído por Algoritmo Genético | ✅ (retorno) | ✅ |

Todos implementam:

```python
acao = agente.decidir(percepcoes)
```

### Agente v1

- Sem estado interno.
- Regras: `brilho → pegar`; `fedor → mover ou atirar`; caso contrário, mover.
- A escolha entre ações válidas é aleatória (com semente opcional).

### Agente v2

- Mantém uma **grade mental** com casas visitadas, brisa, fedor, poços e Wumpus.
- Propaga restrições para inferir casas seguras e perigosas.
- Usa **BFS** para navegar apenas por casas provadamente seguras.
- Quando não há casas seguras, aceita um risco limitado configurável
  (`tolerancia_risco`).
- Retorna para casa assim que pega o ouro.

---

## Agente v3: Algoritmo Genético

O agente v3 aprende um **plano de ação** (cromossomo) e o executa no ambiente.
A implementação segue os parâmetros da Etapa 5.

### Codificação

Cada gene é um índice entre 9 ações primitivas:

```text
N, S, L, O, pegar, atirar_N, atirar_S, atirar_L, atirar_O
```

O cromossomo é uma sequência desses genes. O comprimento padrão é
`max(30, n² + 2n)`.

### Operadores

| Parâmetro | Valor padrão |
| :--- | ---: |
| População | 50 |
| Gerações | 1000 |
| Taxa de cruzamento | 85% |
| Taxa de mutação | 5% por gene |
| Elitismo | 2 indivíduos |
| Seleção | torneio (tamanho 3) |
| Cruzamento | uniforme |

A população inicial combina:

- um cromossomo **snake** (varredura em zigue-zague);
- um cromossomo **espiral**;
- cromossomos de movimento puro em cada direção;
- indivíduos aleatórios para diversidade.

### Fitness

O fitness de treino combina a pontuação oficial com termos de *shaping*:

```text
fitness = pontuação oficial
        + 200 × progresso até o ouro
        + 250 × (pegou o ouro)
        + 250 × (sucesso)
        + 100 × progresso de volta para casa
```

A pontuação oficial continua sendo reportada separadamente nos experimentos.

### Comportamentos de segurança

Além do plano aprendido, o agente possui duas rotinas determinísticas:

1. **Coleta automática**: ao perceber `brilho`, executa `pegar`.
2. **Retorno seguro**: após pegar o ouro, refaz o caminho de movimentos
   bem-sucedidos até `(0, 0)`. Como o caminho já foi percorrido, o retorno é
   seguro.

Quando o cromossomo termina, o agente continua explorando com uma política
determinística simples para não ficar parado.

### Persistência

O treino pode salvar o resultado em JSON:

```json
{
  "n": 4,
  "genoma": [0, 2, 1, 4, ...],
  "fitness": 1794.0,
  "pontuacao_media": 994.0,
  "taxa_sucesso": 1.0,
  "historico": [
    {"geracao": 1, "melhor": 1794.0, "media": 1530.1, "pior": -851.3}
  ],
  "parametros": {"tamanho_populacao": 50, "geracoes": 1000}
}
```

---

## Experimentos da Etapa 5

O script [`experimento.py`](experimento.py) executa os três agentes nos tamanhos
`4, 5, 10, 15, 20`, com **30 execuções** por agente/tamanho e a configuração
fixa de **3 poços, 1 Wumpus e 1 ouro**.

### Modos de avaliação do v3

| Modo | Treino | Avaliação | Quando usar |
| :--- | :--- | :--- | :--- |
| `fixo` (padrão) | mesmo ambiente avaliado | 30 execuções nesse ambiente | mede se o AG encontrou um plano para aquele ambiente |
| `generalizacao` | 5 ambientes | 30 ambientes inéditos | mede o quanto o plano generaliza |

```bash
# modo padrão
python experimento.py --execucoes 30 --geracoes 1000 --populacao 50

# generalização
python experimento.py --modo-v3 generalizacao --treino-ambientes 5
```

### Saídas

- `resultados/resultados.csv` — uma linha por execução;
- `resultados/resumo.csv` — taxa de sucesso, mortes, pontuação e ações médias;
- `resultados/historico_v3_n*.csv` — melhor, média e pior fitness por geração;
- `resultados/genomas/v3_n*.json` — melhor genoma por tamanho;
- `resultados/graficos/*.png` — gráficos comparativos.

### Exemplo de execução rápida

Saída de `python experimento.py --rapido` (5 execuções, 50 gerações,
população 30, modo fixo):

| n | Agente | Sucesso | Mortes | Pontuação média | Ações médias |
| ---: | :---: | ---: | ---: | ---: | ---: |
| 4 | v1 | 0% | 80% | −806,2 | 4,2 |
| 4 | v2 | 0% | 0% | −5,0 | 5,0 |
| 4 | v3 | **100%** | 0% | **994,0** | 6,0 |
| 5 | v1 | 0% | 100% | −1007,2 | 7,2 |
| 5 | v2 | 0% | 0% | −1,0 | 1,0 |
| 5 | v3 | **100%** | 0% | **988,0** | 12,0 |
| 10 | v1 | 0% | 60% | −663,6 | 63,6 |
| 10 | v2 | 100% | 0% | 916,8 | 83,2 |
| 10 | v3 | **100%** | 0% | **965,0** | 25,0 |

> Os números acima são apenas uma demonstração rápida. Para os resultados
> oficiais, execute a configuração completa (30 execuções, 1000 gerações,
> população 50) e consulte `resultados/resumo.csv`.

---

## Testes

```bash
# suíte de integração
pytest

# teste manual independente do agente v2
python tests/teste_manual_v2.py
```

A suíte cobre:

- geração correta do ambiente e das percepções;
- normalização de ações e percepções;
- pontuação, morte, paredes, tiros e sucesso;
- interface e treino curto do agente v3;
- fábrica de agentes e resumo estatístico.

---

## Fluxo de Git

O repositório usa um fluxo simples baseado em branches:

```text
main
└── develop
    └── feature/etapa-4-agente-genetico
```

- `main`: versões estáveis.
- `develop`: integração das etapas.
- `feature/*`: desenvolvimento de cada entrega.

Commits seguem o padrão Conventional Commits:

```text
feat: adiciona agente genético da Etapa 4
fix: corrige cálculo de percepções vizinhas
docs: atualiza README e instruções de execução
test: adiciona testes de integração
```

---

## Licença

Distribuído sob a licença **MIT**. Consulte [`LICENSE`](LICENSE).

---

<p align="center">
  Desenvolvido para a disciplina de Inteligência Computacional — FECOMP/UFPA.
</p>
