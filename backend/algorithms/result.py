"""Tipos de resultado compartilhados pelos algoritmos de caminho minimo."""

import math
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Resultado de uma busca de caminho minimo na rede."""

    path: list[str]
    cost: float
    found: bool

    @classmethod
    def not_found(cls) -> Self:
        """Cria o resultado de rota inexistente: sem caminho e com custo infinito."""
        return cls(path=[], cost=math.inf, found=False)

    @classmethod
    def from_predecessors(
        cls,
        predecessors: dict[str, str],
        origin: str,
        destination: str,
        cost: float,
    ) -> Self:
        """Reconstroi o caminho seguindo os predecessores do destino ate a origem.

        Centraliza a montagem do resultado para que Dijkstra e Bellman-Ford
        devolvam exatamente o mesmo formato ao comparar os dois algoritmos.
        """
        path = [destination]
        while path[-1] != origin:
            path.append(predecessors[path[-1]])
        path.reverse()
        return cls(path=path, cost=cost, found=True)
