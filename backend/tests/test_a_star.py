import math

import pytest

from backend.algorithms import RouteResult, a_star, dijkstra
from backend.dataset import WEIGHT_TOLERANCE_KM, haversine_km
from backend.graph import Network
from backend.state import load_network


def test_finds_the_shortest_path_and_cost(network: Network):
    result = a_star(network, "A", "D")

    assert result == RouteResult(path=["A", "B", "D"], cost=3.0, found=True)


def test_finds_path_in_reverse_on_undirected_network(network: Network):
    result = a_star(network, "D", "A")

    assert result == RouteResult(path=["D", "B", "A"], cost=3.0, found=True)


def test_origin_equal_to_destination_has_zero_cost(network: Network):
    assert a_star(network, "A", "A") == RouteResult(path=["A"], cost=0.0, found=True)


def test_isolated_destination_returns_not_found(network: Network):
    result = a_star(network, "A", "isolated")

    assert result.path == []
    assert math.isinf(result.cost)
    assert not result.found


def test_down_edge_can_partition_the_network():
    graph = Network()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_edge("A", "B", 1)
    graph.set_edge_down("A", "B")

    assert a_star(graph, "A", "B") == RouteResult(path=[], cost=math.inf, found=False)


def test_down_node_forces_route_through_second_best_path(network: Network):
    network.set_node_down("B")

    result = a_star(network, "A", "D")

    assert result == RouteResult(path=["A", "C", "D"], cost=9.0, found=True)


def test_down_edge_forces_route_through_second_best_path(network: Network):
    network.set_edge_down("B", "D")

    result = a_star(network, "A", "D")

    assert result == RouteResult(path=["A", "B", "C", "D"], cost=7.0, found=True)


@pytest.mark.parametrize("down_node", ["A", "D"])
def test_down_endpoint_returns_not_found(network: Network, down_node: str):
    network.set_node_down(down_node)

    assert a_star(network, "A", "D") == RouteResult(path=[], cost=math.inf, found=False)


@pytest.mark.parametrize(
    ("origin", "destination"),
    [("unknown", "A"), ("A", "unknown")],
)
def test_unknown_endpoint_raises_key_error(network: Network, origin: str, destination: str):
    with pytest.raises(KeyError):
        a_star(network, origin, destination)


def test_rejects_active_negative_edge():
    graph = Network()
    for node_id in ("A", "B", "C"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "C", -2)

    with pytest.raises(ValueError, match="negative"):
        a_star(graph, "A", "C")


def test_search_does_not_change_network_state(network: Network):
    nodes_before = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_before = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )

    a_star(network, "A", "D")

    nodes_after = tuple((node, network.is_node_up(node)) for node in network.node_ids())
    edges_after = tuple(
        (origin, edge.destination, edge.weight, edge.is_up) for origin, edge in network.edges()
    )
    assert nodes_after == nodes_before
    assert edges_after == edges_before


# --- Malha real: a heuristica so e informativa (e so precisa ser admissivel de
# verdade) quando os nos tem coordenadas geograficas reais, entao os criterios
# de aceite da issue #30 sao verificados sobre o dataset mundial carregado.


@pytest.fixture(scope="module")
def real_network() -> Network:
    return load_network()


def test_equivalente_a_dijkstra_em_todos_os_pares_da_malha_real(real_network: Network):
    """Para todo par (origem, destino) da malha real, A* e Dijkstra concordam no custo."""
    node_ids = real_network.node_ids()
    for origin in node_ids:
        for destination in node_ids:
            if origin == destination:
                continue
            dijkstra_result = dijkstra(real_network, origin, destination)
            a_star_result = a_star(real_network, origin, destination)

            assert a_star_result.found == dijkstra_result.found
            assert a_star_result.cost == pytest.approx(dijkstra_result.cost)


def test_heuristica_e_admissivel_para_todo_no_da_malha_real(real_network: Network):
    """h(n) = haversine(n, destino) nunca supera o custo real de n ate o destino.

    O dataset arredonda cada peso para o km mais proximo da distancia geodesica
    real (``WEIGHT_TOLERANCE_KM`` de tolerancia), entao a heuristica -- calculada
    sem arredondar -- pode superar em ate essa margem o custo de um trecho de um
    unico salto cujo peso caiu abaixo da distancia real por arredondamento.
    """
    node_ids = real_network.node_ids()
    for destination in node_ids:
        goal = real_network.get_node(destination)
        for origin in node_ids:
            if origin == destination:
                continue
            heuristic = haversine_km(*_lat_lon(real_network, origin), goal.lat, goal.lon)
            actual_cost = dijkstra(real_network, origin, destination).cost

            assert heuristic <= actual_cost + WEIGHT_TOLERANCE_KM


def _lat_lon(network: Network, node_id: str) -> tuple[float, float]:
    node = network.get_node(node_id)
    return node.lat, node.lon


@pytest.mark.parametrize(
    ("origin", "destination"),
    [
        ("virginia-beach", "sines"),
        ("los-angeles", "carcavelos"),
        ("virginia-beach", "bilbao"),
    ],
)
def test_a_star_expande_menos_nos_que_dijkstra_em_pares_transatlanticos(
    real_network: Network, origin: str, destination: str
):
    dijkstra_result = dijkstra(real_network, origin, destination)
    a_star_result = a_star(real_network, origin, destination)

    assert a_star_result.cost == pytest.approx(dijkstra_result.cost)
    assert a_star_result.nodes_expanded < dijkstra_result.nodes_expanded
