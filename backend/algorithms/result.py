"""Tipos de resultado compartilhados pelos algoritmos de caminho minimo."""

import math
from dataclasses import dataclass, field
from typing import Self


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Resultado de uma busca de caminho minimo na rede.

    ``nodes_expanded`` e ``edges_relaxed`` instrumentam o esforco de busca para
    comparar algoritmos (ex.: Dijkstra x A*); ficam fora de ``__eq__``
    (``compare=False``) para que os testes de equivalencia de caminho e custo
    continuem validos independentemente de quanto cada algoritmo explorou.
    Resultados montados fora de uma busca instrumentada (ex.: cada rota
    aceita pelo algoritmo de Yen) mantem o valor padrao 0.
    """

    path: list[str]
    cost: float
    found: bool
    nodes_expanded: int = field(default=0, compare=False)
    edges_relaxed: int = field(default=0, compare=False)

    @classmethod
    def not_found(cls, *, nodes_expanded: int = 0, edges_relaxed: int = 0) -> Self:
        """Cria o resultado de rota inexistente: sem caminho e com custo infinito."""
        return cls(
            path=[],
            cost=math.inf,
            found=False,
            nodes_expanded=nodes_expanded,
            edges_relaxed=edges_relaxed,
        )

    @classmethod
    def from_predecessors(
        cls,
        predecessors: dict[str, str],
        origin: str,
        destination: str,
        cost: float,
        *,
        nodes_expanded: int = 0,
        edges_relaxed: int = 0,
    ) -> Self:
        """Reconstroi o caminho seguindo os predecessores do destino ate a origem.

        Centraliza a montagem do resultado para que Dijkstra, Bellman-Ford e A*
        devolvam exatamente o mesmo formato ao comparar os algoritmos.
        """
        path = [destination]
        while path[-1] != origin:
            path.append(predecessors[path[-1]])
        path.reverse()
        return cls(
            path=path,
            cost=cost,
            found=True,
            nodes_expanded=nodes_expanded,
            edges_relaxed=edges_relaxed,
        )
