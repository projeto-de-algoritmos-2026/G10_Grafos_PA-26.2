"""Testes baseados em propriedades para os algoritmos de menor caminho."""

from itertools import combinations

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from backend.algorithms import bellman_ford, dijkstra
from backend.graph import Network


@st.composite
def networks(draw) -> Network:
    """Gera redes simples com pesos positivos e possíveis partições."""
    node_count = draw(st.integers(min_value=1, max_value=30))
    graph = Network()
    node_ids = tuple(f"N{index}" for index in range(node_count))
    for node_id in node_ids:
        graph.add_node(node_id)

    pairs = list(combinations(range(node_count), 2))
    if not pairs:
        return graph
    selected = draw(
        st.sets(
            st.integers(min_value=0, max_value=len(pairs) - 1),
            max_size=min(len(pairs), 80),
        )
    )
    for pair_index in selected:
        origin_index, destination_index = pairs[pair_index]
        graph.add_edge(
            node_ids[origin_index],
            node_ids[destination_index],
            draw(st.integers(min_value=1, max_value=100)),
        )
    return graph


def _path_weight(network: Network, path: list[str]) -> float:
    """Soma os pesos consultando as arestas da rede, sem usar estado interno."""
    weight = 0.0
    for origin, destination in zip(path, path[1:]):
        edge = next(edge for edge in network.neighbors(origin) if edge.destination == destination)
        weight += edge.weight
    return weight


def _assert_valid_path(network: Network, origin: str, destination: str, result) -> None:
    if not result.found:
        assert result.path == []
        return
    assert result.path[0] == origin
    assert result.path[-1] == destination
    assert len(result.path) == len(set(result.path))
    assert all(network.is_edge_up(left, right) for left, right in zip(result.path, result.path[1:]))
    assert _path_weight(network, result.path) == pytest.approx(result.cost)


@settings(max_examples=25, deadline=None, database=None)
@seed(38038)
@given(network=networks())
def test_dijkstra_e_bellman_ford_concordam_em_todos_os_pares(network: Network):
    """Os dois algoritmos devolvem o mesmo custo e alcançabilidade."""
    node_ids = network.node_ids()
    for origin in node_ids:
        for destination in node_ids:
            dijkstra_result = dijkstra(network, origin, destination)
            bellman_result = bellman_ford(network, origin, destination)
            assert dijkstra_result.found == bellman_result.found
            assert dijkstra_result.cost == pytest.approx(bellman_result.cost)
            _assert_valid_path(network, origin, destination, dijkstra_result)
            _assert_valid_path(network, origin, destination, bellman_result)


@settings(max_examples=25, deadline=None, database=None)
@seed(38039)
@given(network=networks())
def test_derrotar_no_nao_reduz_custo_minimo(network: Network):
    """Remover um intermediario nunca cria um caminho mais barato."""
    node_ids = network.node_ids()
    if len(node_ids) < 3:
        return
    origin, destination, removed = node_ids[:3]
    baseline = dijkstra(network, origin, destination)

    network.set_node_down(removed)
    after_failure = dijkstra(network, origin, destination)
    network.set_node_up(removed)

    if not baseline.found:
        assert not after_failure.found
    elif after_failure.found:
        assert after_failure.cost >= baseline.cost
