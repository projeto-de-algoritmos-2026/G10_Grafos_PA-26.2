import pytest

from backend.algorithms import minimum_edge_cut
from backend.graph import Network


def _network(nodes: tuple[str, ...], edges: tuple[tuple[str, str], ...]) -> Network:
    graph = Network()
    for node in nodes:
        graph.add_node(node)
    for origin, destination in edges:
        # Pesos propositalmente variados: distancia nao pode virar capacidade.
        graph.add_edge(origin, destination, 100 + len(graph.edges()))
    return graph


def test_simple_path_has_cut_one():
    graph = _network(("s", "a", "t"), (("s", "a"), ("a", "t")))

    result = minimum_edge_cut(graph, "s", "t")

    assert result.capacity == 1
    assert len(result.edges) == 1


def test_two_edge_disjoint_paths_have_cut_two():
    graph = _network(
        ("s", "a", "b", "t"),
        (("s", "a"), ("a", "t"), ("s", "b"), ("b", "t")),
    )

    result = minimum_edge_cut(graph, "s", "t")

    assert result.capacity == 2
    assert {frozenset(edge) for edge in result.edges} == {
        frozenset(("s", "a")),
        frozenset(("s", "b")),
    }


def test_disconnected_vertices_have_empty_cut():
    graph = _network(("s", "a", "t"), (("s", "a"),))

    result = minimum_edge_cut(graph, "s", "t")

    assert result.capacity == 0
    assert result.edges == []


def test_equal_endpoints_are_rejected():
    graph = _network(("s",), ())

    with pytest.raises(ValueError, match="different"):
        minimum_edge_cut(graph, "s", "s")


def test_down_nodes_and_edges_are_excluded():
    graph = _network(
        ("s", "a", "b", "t"),
        (("s", "a"), ("a", "t"), ("s", "b"), ("b", "t")),
    )
    graph.set_edge_down("a", "t")

    assert minimum_edge_cut(graph, "s", "t").capacity == 1

    graph.set_node_down("b")

    assert minimum_edge_cut(graph, "s", "t").capacity == 0
    assert minimum_edge_cut(graph, "s", "t").edges == []
