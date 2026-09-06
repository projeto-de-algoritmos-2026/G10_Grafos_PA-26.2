"""Fluxo maximo e corte minimo entre dois roteadores da malha."""

from collections import deque
from dataclasses import dataclass

from backend.graph import Network


@dataclass(frozen=True, slots=True)
class MinCutResult:
    """Capacidade e cabos que formam um corte minimo entre dois nos."""

    capacity: int
    edges: list[tuple[str, str]]


def minimum_edge_cut(network: Network, source: str, sink: str) -> MinCutResult:
    """Calcula um corte minimo de cabos com Edmonds-Karp.

    Pelo teorema de Menger, o numero maximo de caminhos ``source``-``sink``
    disjuntos em arestas e igual ao menor numero de cabos cuja remocao separa
    os dois vertices. Por isso cada cabo bidirecional entra na rede residual
    como dois arcos, um por sentido, ambos com capacidade **unitaria**: o peso
    da aresta representa distancia em quilometros e nao capacidade de trafego.

    Edmonds-Karp escolhe cada caminho aumentante com BFS. Ao terminar, os nos
    ainda alcancaveis a partir da origem na rede residual definem um lado da
    particao; os cabos ativos que cruzam essa particao formam o corte minimo.
    Nos e cabos fora do ar nao entram na rede residual.

    Complexidade O(V * E^2), pelo limite de O(VE) aumentos, cada um encontrado
    por uma BFS O(E).

    Raises:
        KeyError: se algum extremo nao existir.
        ValueError: se origem e destino forem o mesmo no.
    """
    source_is_up = network.is_node_up(source)
    sink_is_up = network.is_node_up(sink)
    if source == sink:
        raise ValueError("Origin and destination must be different")
    if not source_is_up or not sink_is_up:
        return MinCutResult(capacity=0, edges=[])

    active_nodes = {node_id for node_id in network.node_ids() if network.is_node_up(node_id)}
    residual: dict[str, dict[str, int]] = {node_id: {} for node_id in active_nodes}

    for origin, edge in network.edges():
        destination = edge.destination
        if not edge.is_up or origin not in active_nodes or destination not in active_nodes:
            continue
        # Um cabo nao dirigido admite uma unidade em cada sentido. As entradas
        # tambem acumulam a capacidade residual reversa durante os aumentos.
        residual[origin][destination] = 1
        residual[destination][origin] = 1

    maximum_flow = 0
    while (parents := _augmenting_path(residual, source, sink)) is not None:
        bottleneck = min(
            residual[parents[node]][node]
            for node in _path_nodes(parents, source, sink)
        )
        node = sink
        while node != source:
            parent = parents[node]
            residual[parent][node] -= bottleneck
            residual[node][parent] = residual[node].get(parent, 0) + bottleneck
            node = parent
        maximum_flow += bottleneck

    reachable = _reachable_nodes(residual, source)
    cut_edges = [
        (origin, edge.destination)
        for origin, edge in network.edges()
        if edge.is_up
        and origin in active_nodes
        and edge.destination in active_nodes
        and ((origin in reachable) != (edge.destination in reachable))
    ]
    return MinCutResult(capacity=maximum_flow, edges=cut_edges)


def _augmenting_path(
    residual: dict[str, dict[str, int]], source: str, sink: str
) -> dict[str, str] | None:
    """Encontra por BFS os predecessores de um caminho residual aumentante."""
    parents: dict[str, str] = {}
    visited = {source}
    queue = deque([source])

    while queue:
        node = queue.popleft()
        for neighbor, capacity in residual[node].items():
            if capacity <= 0 or neighbor in visited:
                continue
            parents[neighbor] = node
            if neighbor == sink:
                return parents
            visited.add(neighbor)
            queue.append(neighbor)
    return None


def _path_nodes(parents: dict[str, str], source: str, sink: str) -> list[str]:
    """Retorna os nos posteriores a ``source`` no caminho descrito por pais."""
    reversed_path: list[str] = []
    node = sink
    while node != source:
        reversed_path.append(node)
        node = parents[node]
    return list(reversed(reversed_path))


def _reachable_nodes(residual: dict[str, dict[str, int]], source: str) -> set[str]:
    """Percorre os arcos com capacidade residual positiva a partir da origem."""
    reachable = {source}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for neighbor, capacity in residual[node].items():
            if capacity > 0 and neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)
    return reachable
