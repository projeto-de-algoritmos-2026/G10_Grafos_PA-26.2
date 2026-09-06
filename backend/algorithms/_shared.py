"""Validacoes reaproveitadas pelos algoritmos que exigem peso nao negativo."""

from backend.graph import Network


def require_non_negative_active_edges(network: Network, algorithm_name: str) -> None:
    """Levanta ValueError se uma aresta ativa entre dois nos ativos tiver peso negativo."""
    for origin, edge in network.edges():
        if (
            edge.is_up
            and network.is_node_up(origin)
            and network.is_node_up(edge.destination)
            and edge.weight < 0
        ):
            raise ValueError(f"{algorithm_name} does not support negative edge weights")
