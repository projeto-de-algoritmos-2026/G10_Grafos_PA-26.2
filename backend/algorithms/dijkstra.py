"""Implementacao do algoritmo de Dijkstra."""

import heapq
import math

from backend.algorithms.result import RouteResult
from backend.graph import Network


def dijkstra(network: Network, origin: str, destination: str) -> RouteResult:
    """Calcula o caminho de menor custo entre dois nos disponiveis.

    A fila de prioridade de ``heapq`` permite selecionar o proximo no em tempo
    logaritmico, resultando em O((V + E) log V) com a lista de adjacencia da
    ``Network``. Uma busca linear pelo menor custo levaria a O(V²), menos
    adequada para as redes maiores usadas nos benchmarks do projeto.

    Raises:
        KeyError: se a origem ou o destino nao existir.
        ValueError: se uma aresta utilizavel tiver peso negativo.
    """
    origin_is_up = network.is_node_up(origin)
    destination_is_up = network.is_node_up(destination)

    if not origin_is_up or not destination_is_up:
        return _not_found()
    if origin == destination:
        return RouteResult(path=[origin], cost=0.0, found=True)

    _validate_active_edge_weights(network)

    distances = dict.fromkeys(network.node_ids(), math.inf)
    distances[origin] = 0.0
    predecessors: dict[str, str] = {}
    queue: list[tuple[float, str]] = [(0.0, origin)]

    while queue:
        current_cost, current = heapq.heappop(queue)
        if current_cost > distances[current]:
            continue
        if current == destination:
            return RouteResult(
                path=_reconstruct_path(predecessors, origin, destination),
                cost=current_cost,
                found=True,
            )

        for edge in network.neighbors(current):
            new_cost = current_cost + edge.weight
            if new_cost < distances[edge.destination]:
                distances[edge.destination] = new_cost
                predecessors[edge.destination] = current
                heapq.heappush(queue, (new_cost, edge.destination))

    return _not_found()


def _validate_active_edge_weights(network: Network) -> None:
    for origin, edge in network.edges():
        if (
            edge.is_up
            and network.is_node_up(origin)
            and network.is_node_up(edge.destination)
            and edge.weight < 0
        ):
            raise ValueError("Dijkstra does not support negative edge weights")


def _reconstruct_path(predecessors: dict[str, str], origin: str, destination: str) -> list[str]:
    path = [destination]
    current = destination
    while current != origin:
        current = predecessors[current]
        path.append(current)
    path.reverse()
    return path


def _not_found() -> RouteResult:
    return RouteResult(path=[], cost=math.inf, found=False)
