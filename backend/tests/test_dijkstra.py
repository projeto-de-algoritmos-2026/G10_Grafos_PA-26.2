import math

import pytest

from backend.algorithms import RouteResult, dijkstra
from backend.graph import Network


@pytest.fixture
def network() -> Network:
    graph = Network()
    for node_id in ("A", "B", "C", "D", "isolated"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "D", 2)
    graph.add_edge("A", "C", 4)
    graph.add_edge("B", "C", 1)
    graph.add_edge("C", "D", 5)
    return graph


def test_finds_the_shortest_path_and_cost(network: Network):
    result = dijkstra(network, "A", "D")

    assert result == RouteResult(path=["A", "B", "D"], cost=3.0, found=True)


def test_finds_path_in_reverse_on_undirected_network(network: Network):
    result = dijkstra(network, "D", "A")

    assert result == RouteResult(path=["D", "B", "A"], cost=3.0, found=True)


def test_origin_equal_to_destination_has_zero_cost(network: Network):
    assert dijkstra(network, "A", "A") == RouteResult(path=["A"], cost=0.0, found=True)


def test_isolated_destination_returns_not_found(network: Network):
    result = dijkstra(network, "A", "isolated")

    assert result.path == []
    assert math.isinf(result.cost)
    assert not result.found


def test_down_edge_can_partition_the_network():
    graph = Network()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_edge("A", "B", 1)
    graph.set_edge_down("A", "B")

    assert dijkstra(graph, "A", "B") == RouteResult(path=[], cost=math.inf, found=False)


def test_down_node_forces_route_through_second_best_path(network: Network):
    network.set_node_down("B")

    result = dijkstra(network, "A", "D")

    assert result == RouteResult(path=["A", "C", "D"], cost=9.0, found=True)


def test_down_edge_forces_route_through_second_best_path(network: Network):
    network.set_edge_down("B", "D")

    result = dijkstra(network, "A", "D")

    assert result == RouteResult(path=["A", "B", "C", "D"], cost=7.0, found=True)


@pytest.mark.parametrize("down_node", ["A", "D"])
def test_down_endpoint_returns_not_found(network: Network, down_node: str):
    network.set_node_down(down_node)

    assert dijkstra(network, "A", "D") == RouteResult(path=[], cost=math.inf, found=False)


@pytest.mark.parametrize(
    ("origin", "destination"),
    [("unknown", "A"), ("A", "unknown")],
)
def test_unknown_endpoint_raises_key_error(network: Network, origin: str, destination: str):
    with pytest.raises(KeyError):
        dijkstra(network, origin, destination)


def test_rejects_active_negative_edge():
    graph = Network()
    for node_id in ("A", "B", "C"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "C", -2)

    with pytest.raises(ValueError, match="negative"):
        dijkstra(graph, "A", "C")


def test_ignores_negative_edge_when_it_is_down():
    graph = Network()
    for node_id in ("A", "B", "C"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "C", -2)
    graph.add_edge("A", "C", 4)
    graph.set_edge_down("B", "C")

    assert dijkstra(graph, "A", "C") == RouteResult(path=["A", "C"], cost=4.0, found=True)


def test_search_does_not_change_network_state(network: Network):
    nodes_before = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_before = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )

    dijkstra(network, "A", "D")

    nodes_after = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_after = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )
    assert nodes_after == nodes_before
    assert edges_after == edges_before


def test_consecutive_results_do_not_share_their_paths(network: Network):
    first = dijkstra(network, "A", "D")
    second = dijkstra(network, "A", "D")

    first.path.append("modified")

    assert second.path == ["A", "B", "D"]
