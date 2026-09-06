"""Testes da comparacao instrumentada dos algoritmos."""

from itertools import permutations

import pytest

from backend.comparison import compare_routes
from backend.graph import Network
from backend.state import load_network


def test_comparacao_devolve_algoritmos_em_ordem_e_metricas(network: Network):
    comparison = compare_routes(network, "A", "D")

    assert comparison.consistent is True
    assert [result.algorithm for result in comparison.results] == [
        "dijkstra",
        "bellman_ford",
        "a_star",
    ]
    assert {result.route.cost for result in comparison.results} == {3.0}
    assert all(result.route.nodes_expanded > 0 for result in comparison.results)
    assert all(result.route.edges_relaxed > 0 for result in comparison.results)
    assert all(result.elapsed_ms >= 0 for result in comparison.results)


def test_tempo_envolve_isoladamente_cada_algoritmo(network: Network, monkeypatch):
    readings = iter((1.0, 1.002, 2.0, 2.005, 3.0, 3.011))
    monkeypatch.setattr("backend.comparison.time.perf_counter", lambda: next(readings))

    comparison = compare_routes(network, "A", "D")

    assert [result.elapsed_ms for result in comparison.results] == pytest.approx([2, 5, 11])


def test_bellman_ford_relaxa_mais_arestas_que_dijkstra(network: Network):
    comparison = compare_routes(network, "A", "D")
    by_algorithm = {result.algorithm: result.route for result in comparison.results}

    assert by_algorithm["bellman_ford"].edges_relaxed > by_algorithm["dijkstra"].edges_relaxed


def test_rede_particionada_produz_concordancia_sem_rota(network: Network):
    comparison = compare_routes(network, "A", "isolated")

    assert comparison.consistent is True
    assert all(result.route.found is False for result in comparison.results)
    assert all(result.route.path == [] for result in comparison.results)


@pytest.mark.exhaustive
def test_todos_os_pares_da_malha_real_tem_o_mesmo_custo():
    """Cobre os 9.900 pares ordenados exigidos pela issue #37."""
    network = load_network()

    for origin, destination in permutations(network.node_ids(), 2):
        comparison = compare_routes(network, origin, destination)
        assert comparison.consistent, f"divergencia em {origin} -> {destination}"
