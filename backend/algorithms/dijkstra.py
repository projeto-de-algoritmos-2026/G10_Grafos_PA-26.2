"""Implementacao do algoritmo de Dijkstra."""

import heapq
import math

from backend.algorithms._shared import require_non_negative_active_edges
from backend.algorithms.result import RouteResult, TraceEvent
from backend.graph import Network


def dijkstra(
    network: Network,
    origin: str,
    destination: str,
    *,
    trace: list[TraceEvent] | None = None,
    max_trace_events: int = 5000,
) -> RouteResult:
    """Calcula o caminho de menor custo entre dois nos disponiveis.

    A fila de prioridade de ``heapq`` permite selecionar o proximo no em tempo
    logaritmico, resultando em O((V + E) log V) com a lista de adjacencia da
    ``Network``. Uma busca linear pelo menor custo levaria a O(V²), menos
    adequada para as redes maiores usadas nos benchmarks do projeto.

    ``nodes_expanded`` conta os nos efetivamente processados (entradas obsoletas
    da fila sao ignoradas); ``edges_relaxed`` conta cada aresta examinada a
    partir de um no processado, tenha ela melhorado o custo ou nao.

    Raises:
        KeyError: se a origem ou o destino nao existir.
        ValueError: se uma aresta utilizavel tiver peso negativo.
    """
    origin_is_up = network.is_node_up(origin)
    destination_is_up = network.is_node_up(destination)

    if not origin_is_up or not destination_is_up:
        return RouteResult.not_found()
    if origin == destination:
        return RouteResult(path=[origin], cost=0.0, found=True)

    require_non_negative_active_edges(network, "Dijkstra")

    distances = dict.fromkeys(network.node_ids(), math.inf)
    distances[origin] = 0.0
    predecessors: dict[str, str] = {}
    queue: list[tuple[float, str]] = [(0.0, origin)]
    nodes_expanded = 0
    edges_relaxed = 0

    while queue:
        current_cost, current = heapq.heappop(queue)
        if current_cost > distances[current]:
            _trace(trace, TraceEvent("descarta", no=current, custo=current_cost), max_trace_events)
            continue
        _trace(trace, TraceEvent("visita", no=current, custo=current_cost), max_trace_events)
        nodes_expanded += 1
        if current == destination:
            return RouteResult.from_predecessors(
                predecessors,
                origin,
                destination,
                current_cost,
                nodes_expanded=nodes_expanded,
                edges_relaxed=edges_relaxed,
            )

        for edge in network.neighbors(current):
            edges_relaxed += 1
            new_cost = current_cost + edge.weight
            event_type = "relaxa" if new_cost < distances[edge.destination] else "descarta"
            _trace(
                trace,
                TraceEvent(
                    event_type,
                    origem=current,
                    destino=edge.destination,
                    custo=new_cost,
                ),
                max_trace_events,
            )
            if new_cost < distances[edge.destination]:
                distances[edge.destination] = new_cost
                predecessors[edge.destination] = current
                heapq.heappush(queue, (new_cost, edge.destination))

    return RouteResult.not_found(nodes_expanded=nodes_expanded, edges_relaxed=edges_relaxed)


def _trace(trace: list[TraceEvent] | None, event: TraceEvent, limit: int) -> None:
    if trace is not None and len(trace) < limit:
        trace.append(event)
