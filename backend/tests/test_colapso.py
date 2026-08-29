import math

import pytest

from backend.algorithms import RouteResult
from backend.graph import Network
from backend.simulation import (
    derrubar_aresta,
    derrubar_no,
    recalcular_rota,
    restaurar_aresta,
    restaurar_no,
)


@pytest.fixture
def collapse_network() -> Network:
    network = Network()
    for node_id in ("A", "B", "C", "D"):
        network.add_node(node_id)
    network.add_edge("A", "B", 1)
    network.add_edge("B", "D", 1)
    network.add_edge("A", "C", 3)
    network.add_edge("C", "D", 3)
    return network


@pytest.mark.parametrize("algorithm", ["dijkstra", "bellman-ford"])
def test_node_failure_forces_route_through_available_detour(
    collapse_network: Network, algorithm: str
):
    derrubar_no(collapse_network, "B")

    result = recalcular_rota(collapse_network, "A", "D", algorithm)

    assert result == RouteResult(path=["A", "C", "D"], cost=6.0, found=True)


@pytest.mark.parametrize("algorithm", ["dijkstra", "bellman-ford"])
def test_multiple_simultaneous_failures_partition_network(
    collapse_network: Network, algorithm: str
):
    derrubar_no(collapse_network, "B")
    derrubar_no(collapse_network, "C")

    result = recalcular_rota(collapse_network, "A", "D", algorithm)

    assert result.path == []
    assert math.isinf(result.cost)
    assert not result.found


@pytest.mark.parametrize("algorithm", ["dijkstra", "bellman-ford"])
def test_restoring_node_recovers_original_best_route(collapse_network: Network, algorithm: str):
    derrubar_no(collapse_network, "B")
    recalcular_rota(collapse_network, "A", "D", algorithm)

    restaurar_no(collapse_network, "B")

    assert recalcular_rota(collapse_network, "A", "D", algorithm) == RouteResult(
        path=["A", "B", "D"], cost=2.0, found=True
    )


def test_edge_failure_and_restoration_do_not_change_node_status(collapse_network: Network):
    derrubar_aresta(collapse_network, "B", "D")

    assert recalcular_rota(collapse_network, "A", "D", "dijkstra") == RouteResult(
        path=["A", "C", "D"], cost=6.0, found=True
    )
    assert collapse_network.is_node_up("B")
    assert collapse_network.is_node_up("D")

    restaurar_aresta(collapse_network, "B", "D")

    assert recalcular_rota(collapse_network, "A", "D", "dijkstra").path == ["A", "B", "D"]


def test_recalculation_rejects_unknown_algorithm(collapse_network: Network):
    with pytest.raises(ValueError, match="Unsupported routing algorithm"):
        recalcular_rota(collapse_network, "A", "D", "floyd-warshall")


def test_failure_helpers_propagate_unknown_element_errors(collapse_network: Network):
    with pytest.raises(KeyError):
        derrubar_no(collapse_network, "unknown")
    with pytest.raises(KeyError):
        derrubar_aresta(collapse_network, "A", "D")
