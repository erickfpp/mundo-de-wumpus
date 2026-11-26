"""Carregadores para os módulos cujos nomes usam hífen.

Os arquivos ``agent-v1.py``, ``agent-v2.py`` e ``agent-v3.py`` mantêm os nomes
originais do projeto, mas nomes com hífen não podem ser importados diretamente
com ``import``. Este módulo centraliza o carregamento via ``importlib`` para que
o simulador, os experimentos e os testes usem sempre o mesmo caminho.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parent


def carregar_modulo(nome: str, arquivo: str | Path) -> ModuleType:
    """Carrega (ou reaproveita) um módulo Python a partir de um arquivo."""
    if nome in sys.modules:
        return sys.modules[nome]

    caminho = Path(arquivo)
    if not caminho.is_absolute():
        caminho = RAIZ / caminho

    especificacao = importlib.util.spec_from_file_location(nome, caminho)
    if especificacao is None or especificacao.loader is None:
        raise ImportError(f"Não foi possível carregar o módulo {caminho}")

    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[nome] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


def carregar_agente_v1() -> ModuleType:
    return carregar_modulo("agent_v1", "agent-v1.py")


def carregar_agente_v2() -> ModuleType:
    return carregar_modulo("agent_v2", "agent-v2.py")


def carregar_agente_v3() -> ModuleType:
    return carregar_modulo("agent_v3", "agent-v3.py")
