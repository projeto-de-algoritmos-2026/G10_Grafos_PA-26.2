"""Tipos de resultado compartilhados pelos algoritmos de caminho minimo."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Resultado de uma busca de caminho minimo na rede."""

    path: list[str]
    cost: float
    found: bool
