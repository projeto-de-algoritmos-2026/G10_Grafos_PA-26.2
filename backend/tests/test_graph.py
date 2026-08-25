import pytest

from backend.graph import Network


@pytest.fixture
def network() -> Network:
    graph = Network()
    for node_id in ("A", "B", "C"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 10)
    graph.add_edge("B", "C", 4.5)
    return graph


def test_add_node_is_idempotent_and_nodes_start_up():
    graph = Network()

    graph.add_node("A")
    graph.add_node("A")

    assert graph.node_ids() == ("A",)
    assert graph.is_node_up("A")


def test_add_edge_creates_weighted_bidirectional_connection(network: Network):
    edge_from_a = network.neighbors("A")[0]
    edge_from_b = next(edge for edge in network.neighbors("B") if edge.destination == "A")

    assert (edge_from_a.destination, edge_from_a.weight) == ("B", 10.0)
    assert (edge_from_b.destination, edge_from_b.weight) == ("A", 10.0)
    assert network.is_edge_up("A", "B")
    assert network.is_edge_up("B", "A")


def test_node_can_be_taken_down_and_restored_without_removal(network: Network):
    network.set_node_down("B")

    assert not network.is_node_up("B")
    assert network.neighbors("B") == []
    assert network.neighbors("A") == []
    assert network.node_ids() == ("A", "B", "C")

    network.set_node_up("B")

    assert network.is_node_up("B")
    assert [edge.destination for edge in network.neighbors("A")] == ["B"]


def test_edge_can_be_taken_down_and_restored_in_both_directions(network: Network):
    network.set_edge_down("A", "B")

    assert not network.is_edge_up("A", "B")
    assert not network.is_edge_up("B", "A")
    assert network.neighbors("A") == []
    assert [edge.destination for edge in network.neighbors("B")] == ["C"]
    assert len(network.edges()) == 2

    network.set_edge_up("B", "A")

    assert network.is_edge_up("A", "B")
    assert [edge.destination for edge in network.neighbors("A")] == ["B"]


def test_restoring_node_does_not_restore_an_edge_independently(network: Network):
    network.set_edge_down("A", "B")
    network.set_node_down("B")
    network.set_node_up("B")

    assert network.is_node_up("B")
    assert not network.is_edge_up("A", "B")
    assert network.neighbors("A") == []


def test_unknown_nodes_and_edges_raise_key_error(network: Network):
    with pytest.raises(KeyError):
        network.neighbors("unknown")
    with pytest.raises(KeyError):
        network.set_node_down("unknown")
    with pytest.raises(KeyError):
        network.set_edge_down("A", "C")


def test_add_edge_validates_endpoints_weight_and_duplicates(network: Network):
    with pytest.raises(KeyError):
        network.add_edge("A", "unknown", 1)
    with pytest.raises(ValueError):
        network.add_edge("A", "C", float("inf"))
    with pytest.raises(ValueError):
        network.add_edge("B", "A", 10)
    with pytest.raises(ValueError):
        network.add_edge("A", "A", 1)


def test_negative_weight_is_preserved_for_bellman_ford():
    graph = Network()
    graph.add_node("A")
    graph.add_node("B")

    graph.add_edge("A", "B", -2)

    assert graph.neighbors("A")[0].weight == -2.0


def test_reading_edges_does_not_expose_internal_state(network: Network):
    network.neighbors("A")[0].is_up = False
    network.edges()[0][1].is_up = False

    assert network.is_edge_up("A", "B")
    assert [edge.destination for edge in network.neighbors("A")] == ["B"]
