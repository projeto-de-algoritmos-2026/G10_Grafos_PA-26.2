"""Analise reprodutivel da degradacao da rede sob remocao progressiva de nos."""

import heapq
import random
from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from backend.algorithms import find_critical_points
from backend.graph import Network

type CascadeStrategy = Literal["aleatoria", "grau", "articulacao"]

_STRATEGIES = frozenset(("aleatoria", "grau", "articulacao"))


@dataclass(frozen=True, slots=True)
class CascadePoint:
    """Metricas da rede apos uma quantidade de remocoes."""

    step: int
    removed_node: str | None
    active_nodes: int
    removed_fraction: float
    largest_component_fraction: float
    reachable_pairs_fraction: float
    average_route_cost: float | None


@dataclass(frozen=True, slots=True)
class CascadeResult:
    """Serie completa de uma estrategia de falha progressiva."""

    strategy: CascadeStrategy
    seed: int
    initial_nodes: int
    points: list[CascadePoint]


def simulate_cascade(
    network: Network,
    strategy: CascadeStrategy,
    steps: int,
    seed: int = 42,
) -> CascadeResult:
    """Remove nos progressivamente e mede a conectividade a cada passo.

    A funcao trabalha sobre uma copia integral da ``Network`` para que uma
    analise nunca altere o estado compartilhado pela API. Somente nos ativos no
    inicio participam da cascata; cabos e nos previamente indisponiveis
    continuam indisponiveis na copia.

    Estrategias dirigidas sao adaptativas: ``grau`` recalcula o maior grau
    ativo antes de cada remocao, e ``articulacao`` recalcula os pontos de
    articulacao, escolhendo entre eles o de maior grau. Quando nao existe ponto
    de articulacao, essa ultima estrategia usa maior grau como desempate de
    continuidade. Empates sao resolvidos pelo ID, garantindo determinismo.

    A maior componente e normalizada pela quantidade inicial de nos, e a fracao
    de pares usa todos os pares origem-destino existentes no inicio. Essa
    referencia fixa evita recuperacoes artificiais da curva quando restam
    poucos nos. O ponto zero descreve a rede antes das falhas.

    Raises:
        ValueError: para estrategia desconhecida ou quantidade negativa de passos.
    """
    if strategy not in _STRATEGIES:
        supported = ", ".join(sorted(_STRATEGIES))
        raise ValueError(f"Unsupported cascade strategy: {strategy!r}. Supported: {supported}")
    if steps < 0:
        raise ValueError("Cascade steps must be non-negative")

    working = _copy_network(network)
    candidates = sorted(node_id for node_id in working.node_ids() if working.is_node_up(node_id))
    initial_nodes = len(candidates)
    random_order = candidates.copy()
    random.Random(seed).shuffle(random_order)

    points = [_measure(working, step=0, removed_node=None, initial_nodes=initial_nodes)]
    for step in range(1, min(steps, initial_nodes) + 1):
        removed_node = _select_node(working, strategy, random_order)
        working.set_node_down(removed_node)
        points.append(
            _measure(
                working,
                step=step,
                removed_node=removed_node,
                initial_nodes=initial_nodes,
            )
        )

    return CascadeResult(
        strategy=strategy,
        seed=seed,
        initial_nodes=initial_nodes,
        points=points,
    )


def _copy_network(network: Network) -> Network:
    """Copia topologia, metadados e flags sem expor a estrutura interna."""
    copied = Network()
    for node in network.nodes():
        copied.add_node(node.id, name=node.name, lat=node.lat, lon=node.lon)
    for origin, edge in network.edges():
        copied.add_edge(
            origin,
            edge.destination,
            edge.weight,
            cable=edge.cable,
            source_ids=edge.source_ids,
        )
        if not edge.is_up:
            copied.set_edge_down(origin, edge.destination)
    for node in network.nodes():
        if not node.is_up:
            copied.set_node_down(node.id)
    return copied


def _select_node(
    network: Network,
    strategy: CascadeStrategy,
    random_order: list[str],
) -> str:
    """Seleciona o proximo no ativo segundo a estrategia solicitada."""
    if strategy == "aleatoria":
        return next(node_id for node_id in random_order if network.is_node_up(node_id))

    active_nodes = [node_id for node_id in network.node_ids() if network.is_node_up(node_id)]
    candidates = active_nodes
    if strategy == "articulacao":
        articulation_points = find_critical_points(network).articulation_points
        if articulation_points:
            candidates = articulation_points

    return min(candidates, key=lambda node_id: (-len(network.neighbors(node_id)), node_id))


def _measure(
    network: Network,
    *,
    step: int,
    removed_node: str | None,
    initial_nodes: int,
) -> CascadePoint:
    """Calcula as tres metricas pedidas sobre o recorte ativo atual."""
    active_nodes = [node_id for node_id in network.node_ids() if network.is_node_up(node_id)]
    active_count = len(active_nodes)
    if active_count == 0:
        removed_fraction = step / initial_nodes if initial_nodes else 0.0
        return CascadePoint(step, removed_node, 0, removed_fraction, 0.0, 0.0, None)

    components = _connected_components(network, active_nodes)
    largest_fraction = max(map(len, components)) / initial_nodes
    initial_pairs = initial_nodes * (initial_nodes - 1) // 2
    if initial_pairs == 0:
        reachable_fraction = 1.0
    else:
        reachable_pairs = sum(
            len(component) * (len(component) - 1) // 2 for component in components
        )
        reachable_fraction = reachable_pairs / initial_pairs

    return CascadePoint(
        step=step,
        removed_node=removed_node,
        active_nodes=active_count,
        removed_fraction=step / initial_nodes if initial_nodes else 0.0,
        largest_component_fraction=largest_fraction,
        reachable_pairs_fraction=reachable_fraction,
        average_route_cost=_average_route_cost(network, active_nodes),
    )


def _connected_components(network: Network, active_nodes: list[str]) -> list[set[str]]:
    """Particiona os nos ativos em componentes por busca em profundidade."""
    remaining = set(active_nodes)
    components: list[set[str]] = []
    while remaining:
        start = min(remaining)
        component = {start}
        stack = [start]
        remaining.remove(start)
        while stack:
            node = stack.pop()
            for edge in network.neighbors(node):
                if edge.destination in remaining:
                    remaining.remove(edge.destination)
                    component.add(edge.destination)
                    stack.append(edge.destination)
        components.append(component)
    return components


def _average_route_cost(network: Network, active_nodes: list[str]) -> float | None:
    """Calcula a media dos menores custos entre pares ainda alcancaveis."""
    costs: list[float] = []
    for index, source in enumerate(active_nodes):
        distances = _shortest_distances(network, source)
        costs.extend(
            distances[destination]
            for destination in active_nodes[index + 1 :]
            if destination in distances
        )
    return fmean(costs) if costs else None


def _shortest_distances(network: Network, source: str) -> dict[str, float]:
    """Executa Dijkstra uma vez para obter custos da origem a todos os nos."""
    distances = {source: 0.0}
    queue = [(0.0, source)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distances[node]:
            continue
        for edge in network.neighbors(node):
            if edge.weight < 0:
                raise ValueError("Cascade route metrics require non-negative edge weights")
            candidate = cost + edge.weight
            if candidate < distances.get(edge.destination, float("inf")):
                distances[edge.destination] = candidate
                heapq.heappush(queue, (candidate, edge.destination))
    return distances
