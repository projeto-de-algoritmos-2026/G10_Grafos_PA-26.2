"""Orquestracao de falhas e recalculo de rotas da simulacao."""

from collections.abc import Callable
from typing import Literal

from backend.algorithms import RouteResult, bellman_ford, dijkstra
from backend.graph import Network

type RoutingAlgorithm = Literal["dijkstra", "bellman-ford"]
type RouteCalculator = Callable[[Network, str, str], RouteResult]

_ALGORITHMS: dict[RoutingAlgorithm, RouteCalculator] = {
    "dijkstra": dijkstra,
    "bellman-ford": bellman_ford,
}


def derrubar_no(network: Network, node_id: str) -> None:
    """Marca um roteador como indisponivel, preservando sua topologia."""
    network.set_node_down(node_id)


def restaurar_no(network: Network, node_id: str) -> None:
    """Restaura um roteador sem alterar o estado independente de seus cabos."""
    network.set_node_up(node_id)


def derrubar_aresta(network: Network, origin: str, destination: str) -> None:
    """Marca um cabo bidirecional como indisponivel."""
    network.set_edge_down(origin, destination)


def restaurar_aresta(network: Network, origin: str, destination: str) -> None:
    """Restaura um cabo bidirecional entre dois roteadores."""
    network.set_edge_up(origin, destination)


def recalcular_rota(
    network: Network,
    origin: str,
    destination: str,
    algorithm: RoutingAlgorithm,
) -> RouteResult:
    """Calcula a melhor rota atual usando o algoritmo selecionado.

    Uma rede particionada e devolvida como resultado valido do dominio:
    ``RouteResult(found=False, path=[], cost=inf)``.

    Raises:
        ValueError: se o identificador do algoritmo nao for suportado.
    """
    try:
        calculator = _ALGORITHMS[algorithm]
    except KeyError:
        supported = ", ".join(_ALGORITHMS)
        raise ValueError(
            f"Unsupported routing algorithm: {algorithm!r}. Supported: {supported}"
        ) from None
    return calculator(network, origin, destination)
