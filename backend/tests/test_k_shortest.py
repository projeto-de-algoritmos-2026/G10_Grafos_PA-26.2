import pytest

from backend.algorithms import RouteResult, dijkstra, k_shortest_paths
from backend.graph import Network


def test_k_equal_one_matches_dijkstra(network: Network):
    assert k_shortest_paths(network, "A", "D", 1) == [dijkstra(network, "A", "D")]


def test_returns_the_four_simple_paths_ordered_by_non_decreasing_cost(network: Network):
    """A rede de teste tem exatamente 4 caminhos simples de A a D: 3, 7, 7 e 9."""
    result = k_shortest_paths(network, "A", "D", 4)

    assert [route.path for route in result] == [
        ["A", "B", "D"],
        ["A", "B", "C", "D"],
        ["A", "C", "B", "D"],
        ["A", "C", "D"],
    ]
    assert [route.cost for route in result] == [3.0, 7.0, 7.0, 9.0]
    assert all(route.found for route in result)


def test_paths_are_strictly_non_decreasing_in_cost(network: Network):
    result = k_shortest_paths(network, "A", "D", 4)

    costs = [route.cost for route in result]
    assert costs == sorted(costs)


def test_paths_never_repeat_a_vertex(network: Network):
    result = k_shortest_paths(network, "A", "D", 4)

    for route in result:
        assert len(route.path) == len(set(route.path))


def test_paths_are_not_duplicated(network: Network):
    result = k_shortest_paths(network, "A", "D", 4)

    paths_as_tuples = [tuple(route.path) for route in result]
    assert len(paths_as_tuples) == len(set(paths_as_tuples))


def test_k_larger_than_available_paths_returns_all_of_them_without_error(network: Network):
    result = k_shortest_paths(network, "A", "D", 10)

    assert len(result) == 4


def test_partitioned_network_returns_empty_list(network: Network):
    assert k_shortest_paths(network, "A", "isolated", 3) == []


def test_origin_equal_to_destination_returns_a_single_zero_cost_path(network: Network):
    result = k_shortest_paths(network, "A", "A", 5)

    assert result == [RouteResult(path=["A"], cost=0.0, found=True)]


@pytest.mark.parametrize(
    ("origin", "destination"),
    [("unknown", "A"), ("A", "unknown")],
)
def test_unknown_endpoint_raises_key_error(network: Network, origin: str, destination: str):
    with pytest.raises(KeyError):
        k_shortest_paths(network, origin, destination, 3)


@pytest.mark.parametrize("k", [0, -1])
def test_k_below_one_raises_value_error(network: Network, k: int):
    with pytest.raises(ValueError, match="k must be at least 1"):
        k_shortest_paths(network, "A", "D", k)


def test_search_does_not_change_network_state(network: Network):
    nodes_before = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_before = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )

    k_shortest_paths(network, "A", "D", 4)

    nodes_after = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_after = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )
    assert nodes_after == nodes_before
    assert edges_after == edges_before


def test_down_edge_removes_every_path_that_depends_on_it(network: Network):
    """Com B-D indisponivel, so sobram os 2 caminhos simples que nao o usam."""
    network.set_edge_down("B", "D")

    result = k_shortest_paths(network, "A", "D", 4)

    assert [route.path for route in result] == [
        ["A", "B", "C", "D"],
        ["A", "C", "D"],
    ]
    assert [route.cost for route in result] == [7.0, 9.0]
