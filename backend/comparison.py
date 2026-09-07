"""Comparacao instrumentada dos algoritmos sobre o mesmo estado da rede."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from backend.algorithms import RouteResult, a_star, bellman_ford, dijkstra
from backend.graph import Network

type ComparisonAlgorithm = Literal["dijkstra", "bellman_ford", "a_star"]
type RouteCalculator = Callable[[Network, str, str], RouteResult]

_ALGORITHMS: tuple[tuple[ComparisonAlgorithm, RouteCalculator], ...] = (
    ("dijkstra", dijkstra),
    ("bellman_ford", bellman_ford),
    ("a_star", a_star),
)


@dataclass(frozen=True, slots=True)
class TimedRouteResult:
    """Resultado de um algoritmo e o tempo isolado de sua chamada."""

    algorithm: ComparisonAlgorithm
    route: RouteResult
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class RouteComparison:
    """Resultados dos tres algoritmos e sua concordancia observada."""

    results: tuple[TimedRouteResult, ...]
    consistent: bool


def compare_routes(network: Network, origin: str, destination: str) -> RouteComparison:
    """Executa todos os algoritmos sequencialmente sobre a mesma rede.

    ``perf_counter`` envolve somente a chamada do algoritmo. O valor e uma
    medicao unica para exploracao interativa, nao substitui o benchmark com
    repeticoes e ambiente registrado.
    """
    results: list[TimedRouteResult] = []
    for algorithm, calculator in _ALGORITHMS:
        started_at = time.perf_counter()
        route = calculator(network, origin, destination)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        results.append(TimedRouteResult(algorithm, route, elapsed_ms))

    return RouteComparison(tuple(results), _results_are_consistent(results))


def _results_are_consistent(results: list[TimedRouteResult]) -> bool:
    found_states = {result.route.found for result in results}
    if len(found_states) != 1:
        return False
    if not results[0].route.found:
        return True
    reference_cost = results[0].route.cost
    return all(
        math.isclose(result.route.cost, reference_cost, rel_tol=1e-12, abs_tol=1e-9)
        for result in results[1:]
    )
