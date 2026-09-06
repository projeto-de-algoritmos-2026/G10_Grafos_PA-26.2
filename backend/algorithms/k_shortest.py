"""Algoritmo de Yen: k caminhos minimos simples entre dois nos."""

import heapq
from collections.abc import Iterator
from contextlib import contextmanager

from backend.algorithms.dijkstra import dijkstra
from backend.algorithms.result import RouteResult
from backend.graph import Network


def k_shortest_paths(network: Network, origin: str, destination: str, k: int) -> list[RouteResult]:
    """Calcula ate ``k`` caminhos simples entre ``origin`` e ``destination``.

    Implementa o algoritmo de Yen reaproveitando ``dijkstra`` como sub-rotina
    para os caminhos de desvio (spur paths): a cada iteracao, os nos e arestas
    que uma rota candidata precisa evitar sao marcados temporariamente como
    indisponiveis com o mesmo mecanismo usado pela simulacao de falhas
    (``set_node_down``/``set_edge_down``) e restaurados logo em seguida, mesmo
    se ``dijkstra`` levantar excecao. Isso reusa a rede real em vez de copia-la,
    mas significa que o resultado nao e seguro sob chamadas concorrentes na
    mesma ``Network``.

    O resultado vem ordenado por custo nao decrescente e sem caminhos
    repetidos; quando existem menos de ``k`` rotas simples possiveis, devolve
    apenas as que existem. Rede particionada (sem nenhum caminho) devolve lista
    vazia.

    Raises:
        ValueError: se ``k`` for menor que 1, ou se propagado por ``dijkstra``
            (peso negativo em aresta ativa).
        KeyError: se a origem ou o destino nao existir.
    """
    if k < 1:
        raise ValueError("k must be at least 1")

    first = dijkstra(network, origin, destination)
    if not first.found:
        return []

    accepted: list[RouteResult] = [first]
    accepted_keys: set[tuple[str, ...]] = {tuple(first.path)}
    candidates: list[tuple[float, list[str]]] = []
    candidate_keys: set[tuple[str, ...]] = set()

    while len(accepted) < k:
        previous_path = accepted[-1].path
        prefix_costs = _prefix_costs(network, previous_path)

        for index in range(len(previous_path) - 1):
            spur_node = previous_path[index]
            root_path = previous_path[: index + 1]

            with _spur_isolation(network, accepted, root_path, index):
                spur_result = dijkstra(network, spur_node, destination)

            if not spur_result.found:
                continue

            total_path = root_path[:-1] + spur_result.path
            path_key = tuple(total_path)
            if path_key in accepted_keys or path_key in candidate_keys:
                continue

            candidate_keys.add(path_key)
            heapq.heappush(candidates, (prefix_costs[index] + spur_result.cost, total_path))

        if not candidates:
            break

        next_cost, next_path = heapq.heappop(candidates)
        candidate_keys.discard(tuple(next_path))
        accepted.append(RouteResult(path=next_path, cost=next_cost, found=True))
        accepted_keys.add(tuple(next_path))

    return accepted


def _prefix_costs(network: Network, path: list[str]) -> list[float]:
    """Custo acumulado de cada prefixo de ``path``, com ``prefix_costs[0] == 0``."""
    costs = [0.0]
    for origin, destination in zip(path, path[1:], strict=False):
        costs.append(costs[-1] + _edge_weight(network, origin, destination))
    return costs


def _edge_weight(network: Network, origin: str, destination: str) -> float:
    for edge in network.neighbors(origin):
        if edge.destination == destination:
            return edge.weight
    raise KeyError(f"Edge does not exist: {origin!r} - {destination!r}")


@contextmanager
def _spur_isolation(
    network: Network,
    accepted: list[RouteResult],
    root_path: list[str],
    index: int,
) -> Iterator[None]:
    """Remove temporariamente o que uma rota candidata em ``index`` deve evitar.

    Derruba a aresta seguinte ao no de desvio em toda rota ja aceita que
    compartilha o mesmo prefixo (para nao repetir uma rota ja encontrada) e os
    nos do prefixo anteriores ao no de desvio (para manter o caminho simples).
    Restaura exatamente o que este bloco derrubou, preservando quedas reais da
    simulacao.
    """
    removed_edges: list[tuple[str, str]] = []
    removed_nodes: list[str] = []
    try:
        for result in accepted:
            path = result.path
            if len(path) > index + 1 and path[: index + 1] == root_path:
                origin, destination = path[index], path[index + 1]
                if network.is_edge_up(origin, destination):
                    network.set_edge_down(origin, destination)
                    removed_edges.append((origin, destination))

        for node in root_path[:-1]:
            if network.is_node_up(node):
                network.set_node_down(node)
                removed_nodes.append(node)

        yield
    finally:
        for origin, destination in removed_edges:
            network.set_edge_up(origin, destination)
        for node in removed_nodes:
            network.set_node_up(node)
