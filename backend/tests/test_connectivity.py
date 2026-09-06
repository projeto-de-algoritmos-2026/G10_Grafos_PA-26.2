from backend.algorithms.connectivity import CriticalityResult, find_critical_points
from backend.graph import Network


def _linear_network(*node_ids: str) -> Network:
    graph = Network()
    for node_id in node_ids:
        graph.add_node(node_id)
    for origin, destination in zip(node_ids, node_ids[1:]):
        graph.add_edge(origin, destination, 1)
    return graph


def _cycle_network(*node_ids: str) -> Network:
    graph = _linear_network(*node_ids)
    graph.add_edge(node_ids[-1], node_ids[0], 1)
    return graph


def test_path_graph_has_every_internal_node_and_edge_critical():
    graph = _linear_network("A", "B", "C", "D")

    result = find_critical_points(graph)

    assert set(result.articulation_points) == {"B", "C"}
    assert {frozenset(bridge) for bridge in result.bridges} == {
        frozenset({"A", "B"}),
        frozenset({"B", "C"}),
        frozenset({"C", "D"}),
    }
    assert result.components == 1


def test_cycle_graph_has_no_articulation_points_or_bridges():
    graph = _cycle_network("A", "B", "C", "D")

    result = find_critical_points(graph)

    assert result.articulation_points == []
    assert result.bridges == []
    assert result.components == 1


def test_two_cycles_joined_by_a_bridge():
    graph = Network()
    for node_id in ("A", "B", "C", "D", "E", "F"):
        graph.add_node(node_id)
    # Ciclo 1: A-B-C-A
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "C", 1)
    graph.add_edge("C", "A", 1)
    # Ciclo 2: D-E-F-D
    graph.add_edge("D", "E", 1)
    graph.add_edge("E", "F", 1)
    graph.add_edge("F", "D", 1)
    # Ponte entre os dois ciclos
    graph.add_edge("C", "D", 1)

    result = find_critical_points(graph)

    assert set(result.articulation_points) == {"C", "D"}
    assert [frozenset(bridge) for bridge in result.bridges] == [frozenset({"C", "D"})]
    assert result.components == 1


def test_single_node_network_returns_empty_lists():
    graph = Network()
    graph.add_node("A")

    result = find_critical_points(graph)

    assert result == CriticalityResult(articulation_points=[], bridges=[], components=1)


def test_isolated_node_alongside_a_connected_component():
    graph = _cycle_network("A", "B", "C")
    graph.add_node("isolated")

    result = find_critical_points(graph)

    assert result.articulation_points == []
    assert result.bridges == []
    assert result.components == 2


def test_two_triangles_sharing_an_edge_has_no_single_point_of_failure():
    graph = Network()
    for node_id in ("A", "B", "C", "D"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "D", 2)
    graph.add_edge("A", "C", 4)
    graph.add_edge("B", "C", 1)
    graph.add_edge("C", "D", 5)

    result = find_critical_points(graph)

    assert result.articulation_points == []
    assert result.bridges == []
    assert result.components == 1


def test_partitioned_network_runs_analysis_per_component():
    graph = _linear_network("A", "B", "C")
    graph.set_edge_down("B", "C")

    result = find_critical_points(graph)

    # B tem grau 1 na rede ativa (o cabo para C esta caido): um no-folha nunca
    # e ponto de articulacao, mesmo que fosse antes de o cabo cair.
    assert result.articulation_points == []
    assert [frozenset(bridge) for bridge in result.bridges] == [frozenset({"A", "B"})]
    assert result.components == 2


def test_down_node_is_ignored_by_the_analysis():
    graph = _linear_network("A", "B", "C")

    graph.set_node_down("B")
    result = find_critical_points(graph)

    assert result.articulation_points == []
    assert result.bridges == []
    assert result.components == 2


def test_bringing_down_a_node_changes_the_articulation_set():
    graph = _cycle_network("A", "B", "C")
    graph.add_node("D")
    graph.add_edge("C", "D", 1)

    before = find_critical_points(graph)
    assert before.articulation_points == ["C"]

    graph.set_node_down("C")
    after = find_critical_points(graph)

    # Sem C, o triangulo A-B-C vira apenas o cabo A-B: uma unica aresta entre
    # dois nos e sempre uma ponte, mesmo tendo sido parte de um ciclo antes.
    assert after.articulation_points == []
    assert [frozenset(bridge) for bridge in after.bridges] == [frozenset({"A", "B"})]
    assert after.components == 2


def test_down_edge_is_excluded_from_the_analysis():
    graph = _linear_network("A", "B", "C")
    graph.add_edge("A", "C", 5)

    graph.set_edge_down("A", "C")
    result = find_critical_points(graph)

    assert set(result.articulation_points) == {"B"}
    assert {frozenset(bridge) for bridge in result.bridges} == {
        frozenset({"A", "B"}),
        frozenset({"B", "C"}),
    }
