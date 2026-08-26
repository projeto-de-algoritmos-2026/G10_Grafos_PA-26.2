import math

import pytest

from backend.algorithms import NegativeCycleError, RouteResult, bellman_ford, dijkstra
from backend.graph import Network


def test_finds_the_shortest_path_and_cost(network: Network):
    result = bellman_ford(network, "A", "D")

    assert result == RouteResult(path=["A", "B", "D"], cost=3.0, found=True)


def test_finds_path_in_reverse_on_undirected_network(network: Network):
    result = bellman_ford(network, "D", "A")

    assert result == RouteResult(path=["D", "B", "A"], cost=3.0, found=True)


def test_origin_equal_to_destination_has_zero_cost(network: Network):
    assert bellman_ford(network, "A", "A") == RouteResult(path=["A"], cost=0.0, found=True)


def test_isolated_destination_returns_not_found(network: Network):
    result = bellman_ford(network, "A", "isolated")

    assert result.path == []
    assert math.isinf(result.cost)
    assert not result.found


def test_down_edge_can_partition_the_network():
    graph = Network()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_edge("A", "B", 1)
    graph.set_edge_down("A", "B")

    assert bellman_ford(graph, "A", "B") == RouteResult(path=[], cost=math.inf, found=False)


def test_down_node_forces_route_through_second_best_path(network: Network):
    network.set_node_down("B")

    result = bellman_ford(network, "A", "D")

    assert result == RouteResult(path=["A", "C", "D"], cost=9.0, found=True)


def test_down_edge_forces_route_through_second_best_path(network: Network):
    network.set_edge_down("B", "D")

    result = bellman_ford(network, "A", "D")

    assert result == RouteResult(path=["A", "B", "C", "D"], cost=7.0, found=True)


@pytest.mark.parametrize("down_node", ["A", "D"])
def test_down_endpoint_returns_not_found(network: Network, down_node: str):
    network.set_node_down(down_node)

    assert bellman_ford(network, "A", "D") == RouteResult(path=[], cost=math.inf, found=False)


@pytest.mark.parametrize(
    ("origin", "destination"),
    [("unknown", "A"), ("A", "unknown")],
)
def test_unknown_endpoint_raises_key_error(network: Network, origin: str, destination: str):
    with pytest.raises(KeyError):
        bellman_ford(network, origin, destination)


def test_detects_negative_cycle():
    """Grafo sintetico: em rede nao dirigida um cabo negativo ja e um ciclo negativo."""
    graph = Network()
    for node_id in ("A", "B", "C"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "C", -2)

    with pytest.raises(NegativeCycleError):
        bellman_ford(graph, "A", "C")


def test_negative_cycle_out_of_reach_does_not_block_the_route():
    graph = Network()
    for node_id in ("A", "B", "X", "Y"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("X", "Y", -3)

    assert bellman_ford(graph, "A", "B") == RouteResult(path=["A", "B"], cost=1.0, found=True)


def test_ignores_negative_edge_when_it_is_down():
    graph = Network()
    for node_id in ("A", "B", "C"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "C", -2)
    graph.add_edge("A", "C", 4)
    graph.set_edge_down("B", "C")

    assert bellman_ford(graph, "A", "C") == RouteResult(path=["A", "C"], cost=4.0, found=True)


def test_search_does_not_change_network_state(network: Network):
    nodes_before = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_before = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )

    bellman_ford(network, "A", "D")

    nodes_after = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_after = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )
    assert nodes_after == nodes_before
    assert edges_after == edges_before


def test_consecutive_results_do_not_share_their_paths(network: Network):
    first = bellman_ford(network, "A", "D")
    second = bellman_ford(network, "A", "D")

    first.path.append("modified")

    assert second.path == ["A", "B", "D"]


@pytest.mark.parametrize(
    ("origin", "destination", "down_node", "down_edge"),
    [
        ("A", "D", None, None),
        ("D", "A", None, None),
        ("A", "A", None, None),
        ("C", "B", None, None),
        ("A", "isolated", None, None),
        ("A", "D", "B", None),
        ("A", "D", "C", None),
        ("A", "D", "A", None),
        ("A", "D", "D", None),
        ("A", "D", None, ("B", "D")),
        ("A", "D", None, ("A", "B")),
    ],
)
def test_agrees_with_dijkstra(
    network: Network,
    origin: str,
    destination: str,
    down_node: str | None,
    down_edge: tuple[str, str] | None,
):
    """Criterio de aceite da issue #4: mesmo caminho e mesmo custo do Dijkstra."""
    if down_node is not None:
        network.set_node_down(down_node)
    if down_edge is not None:
        network.set_edge_down(*down_edge)

    assert bellman_ford(network, origin, destination) == dijkstra(network, origin, destination)
