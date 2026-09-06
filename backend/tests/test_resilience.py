import pytest

from backend.graph import Network
from backend.resilience import CascadeStrategy, simulate_cascade


def _complete_graph(size: int) -> Network:
    graph = Network()
    nodes = [f"n{index}" for index in range(size)]
    for node in nodes:
        graph.add_node(node)
    for index, origin in enumerate(nodes):
        for destination in nodes[index + 1 :]:
            graph.add_edge(origin, destination, 1)
    return graph


def _star_graph(size: int = 5) -> Network:
    graph = Network()
    graph.add_node("center")
    for index in range(size - 1):
        leaf = f"leaf-{index}"
        graph.add_node(leaf)
        graph.add_edge("center", leaf, index + 1)
    return graph


def test_same_seed_produces_exactly_the_same_removal_sequence():
    graph = _complete_graph(8)

    first = simulate_cascade(graph, "aleatoria", 8, seed=2026)
    second = simulate_cascade(graph, "aleatoria", 8, seed=2026)

    assert [point.removed_node for point in first.points] == [
        point.removed_node for point in second.points
    ]
    assert first == second


def test_simulation_does_not_change_nodes_or_edges_in_original_network():
    graph = _star_graph()
    graph.set_node_down("leaf-3")
    graph.set_edge_down("center", "leaf-2")
    node_states = [(node.id, node.is_up) for node in graph.nodes()]
    edge_states = [
        (origin, edge.destination, edge.is_up) for origin, edge in graph.edges()
    ]

    result = simulate_cascade(graph, "articulacao", 4, seed=7)

    assert result.initial_nodes == 4
    assert "leaf-3" not in {point.removed_node for point in result.points}
    assert [(node.id, node.is_up) for node in graph.nodes()] == node_states
    assert [
        (origin, edge.destination, edge.is_up) for origin, edge in graph.edges()
    ] == edge_states


def test_complete_graph_stays_connected_until_the_last_removal():
    result = simulate_cascade(_complete_graph(5), "grau", 5)

    assert [point.largest_component_fraction for point in result.points] == [
        1.0,
        0.8,
        0.6,
        0.4,
        0.2,
        0.0,
    ]
    # A maior componente sempre contem todos os sobreviventes: nao existe
    # degradacao adicional por fragmentacao antes da remocao final.
    assert all(
        point.largest_component_fraction == point.active_nodes / result.initial_nodes
        for point in result.points
    )
    assert result.points[-1].largest_component_fraction == 0.0
    assert result.points[-1].reachable_pairs_fraction == 0.0


@pytest.mark.parametrize("strategy", ["grau", "articulacao"])
def test_directed_attack_removes_star_center_and_collapses_pairs(strategy: CascadeStrategy):
    result = simulate_cascade(_star_graph(), strategy, 1)

    after_attack = result.points[1]
    assert after_attack.removed_node == "center"
    assert after_attack.largest_component_fraction == 0.2
    assert after_attack.reachable_pairs_fraction == 0.0
    assert after_attack.average_route_cost is None


def test_metrics_include_average_shortest_route_cost():
    graph = Network()
    for node in ("a", "b", "c"):
        graph.add_node(node)
    graph.add_edge("a", "b", 1)
    graph.add_edge("b", "c", 1)

    result = simulate_cascade(graph, "articulacao", 1)

    assert result.points[0].average_route_cost == pytest.approx(4 / 3)
    assert result.points[1].removed_node == "b"
    assert result.points[1].reachable_pairs_fraction == 0.0


@pytest.mark.parametrize("steps", [-1, -10])
def test_negative_steps_are_rejected(steps: int):
    with pytest.raises(ValueError, match="non-negative"):
        simulate_cascade(_star_graph(), "grau", steps)
