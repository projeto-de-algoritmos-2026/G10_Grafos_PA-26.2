"""Implementacao do algoritmo de Bellman-Ford."""

import math

from backend.algorithms.result import RouteResult
from backend.graph import Network

type Arc = tuple[str, str, float]


class NegativeCycleError(ValueError):
    """Sinaliza um ciclo de custo negativo alcancavel a partir da origem."""


def bellman_ford(network: Network, origin: str, destination: str) -> RouteResult:
    """Calcula o caminho de menor custo relaxando todas as arestas a cada rodada.

    Um caminho minimo tem no maximo V-1 arestas, entao V-1 rodadas de relaxamento
    sobre as E arestas bastam para estabilizar os custos: O(V*E), mais lento que
    Dijkstra em troca de aceitar peso negativo. A rodada extra ao final detecta
    ciclo negativo -- se ainda houver aresta relaxavel, nao existe caminho minimo
    bem definido. Como a rede e nao dirigida, qualquer aresta negativa ativa e por
    si so um ciclo negativo (ida e volta pelo mesmo cabo).

    O relaxamento para assim que uma rodada nao altera nenhum custo; nesse caso a
    busca ja convergiu e nao ha ciclo negativo alcancavel.

    Raises:
        KeyError: se a origem ou o destino nao existir.
        NegativeCycleError: se houver ciclo negativo alcancavel pela origem.
    """
    if not network.is_node_up(origin) or not network.is_node_up(destination):
        return RouteResult.not_found()
    if origin == destination:
        return RouteResult(path=[origin], cost=0.0, found=True)

    arcs = _usable_arcs(network)
    distances = dict.fromkeys(network.node_ids(), math.inf)
    distances[origin] = 0.0
    predecessors: dict[str, str] = {}

    for _ in range(len(distances) - 1):
        if not _relax_all(arcs, distances, predecessors):
            break
    else:
        if _has_relaxable_arc(arcs, distances):
            raise NegativeCycleError(f"Negative cycle reachable from {origin!r}")

    if math.isinf(distances[destination]):
        return RouteResult.not_found()
    return RouteResult.from_predecessors(predecessors, origin, destination, distances[destination])


def _usable_arcs(network: Network) -> tuple[Arc, ...]:
    """Lista os dois sentidos de cada cabo utilizavel.

    ``neighbors`` ja descarta no indisponivel e cabo fora do ar, garantindo o
    mesmo recorte da rede usado pelo Dijkstra.
    """
    return tuple(
        (node_id, edge.destination, edge.weight)
        for node_id in network.node_ids()
        for edge in network.neighbors(node_id)
    )


def _relax_all(
    arcs: tuple[Arc, ...],
    distances: dict[str, float],
    predecessors: dict[str, str],
) -> bool:
    """Executa uma rodada de relaxamento e informa se algum custo mudou."""
    changed = False
    for origin, destination, weight in arcs:
        if math.isinf(distances[origin]):
            continue
        new_cost = distances[origin] + weight
        if new_cost < distances[destination]:
            distances[destination] = new_cost
            predecessors[destination] = origin
            changed = True
    return changed


def _has_relaxable_arc(arcs: tuple[Arc, ...], distances: dict[str, float]) -> bool:
    return any(
        not math.isinf(distances[origin]) and distances[origin] + weight < distances[destination]
        for origin, destination, weight in arcs
    )
