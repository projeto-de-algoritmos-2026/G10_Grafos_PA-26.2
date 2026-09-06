"""Implementacao do algoritmo A* com heuristica geodesica (Haversine)."""

import heapq
import math

from backend.algorithms._shared import require_non_negative_active_edges
from backend.algorithms.result import RouteResult, TraceEvent
from backend.dataset import haversine_km
from backend.graph import Network


def a_star(
    network: Network,
    origin: str,
    destination: str,
    *,
    trace: list[TraceEvent] | None = None,
    max_trace_events: int = 5000,
) -> RouteResult:
    """Calcula o caminho de menor custo guiado pela distancia geodesica ate o destino.

    A heuristica ``h(n) = haversine(n, destino)`` e admissivel e consistente: o
    dataset garante que cada cabo pesa exatamente a distancia geodesica entre
    seus dois extremos (``NetworkDataset.validate_topology``), entao pela
    desigualdade triangular na esfera nenhum caminho de ``n`` ate o destino
    pode custar menos que ``h(n)``. Heuristica admissivel e consistente garante
    que A* nunca reabre um no ja processado e devolve o mesmo caminho otimo de
    Dijkstra -- a mesma estrutura de fila e o mesmo criterio de entrada obsoleta
    sao reaproveitados aqui, trocando apenas a prioridade de custo acumulado
    (``g``) por custo acumulado mais heuristica (``f = g + h``), o que faz A*
    tender a expandir menos nos ao priorizar quem esta geometricamente mais
    perto do destino.

    A heuristica so e valida com peso em quilometros: se o peso da aresta vier
    a representar outra metrica (latencia, capacidade etc.), ``h`` deixa de ser
    uma cota inferior garantida e A* poderia devolver caminho sub-otimo. Uma
    metrica alternativa futura precisa fornecer sua propria heuristica
    admissivel para essa metrica, ou cair para Dijkstra/Bellman-Ford.

    ``nodes_expanded`` e ``edges_relaxed`` seguem exatamente a mesma definicao
    usada por ``dijkstra`` para que a comparacao entre os dois seja direta.

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

    require_non_negative_active_edges(network, "A*")

    goal = network.get_node(destination)

    def heuristic(node_id: str) -> float:
        node = network.get_node(node_id)
        return haversine_km(node.lat, node.lon, goal.lat, goal.lon)

    g_score = dict.fromkeys(network.node_ids(), math.inf)
    g_score[origin] = 0.0
    f_score = dict.fromkeys(network.node_ids(), math.inf)
    f_score[origin] = heuristic(origin)
    predecessors: dict[str, str] = {}
    queue: list[tuple[float, str]] = [(f_score[origin], origin)]
    nodes_expanded = 0
    edges_relaxed = 0

    while queue:
        current_f, current = heapq.heappop(queue)
        if current_f > f_score[current]:
            if trace is not None and len(trace) < max_trace_events:
                trace.append(TraceEvent("descarta", no=current, custo=current_f))
            continue
        if trace is not None and len(trace) < max_trace_events:
            trace.append(TraceEvent("visita", no=current, custo=g_score[current]))
        nodes_expanded += 1
        if current == destination:
            return RouteResult.from_predecessors(
                predecessors,
                origin,
                destination,
                g_score[current],
                nodes_expanded=nodes_expanded,
                edges_relaxed=edges_relaxed,
            )

        for edge in network.neighbors(current):
            edges_relaxed += 1
            tentative_g = g_score[current] + edge.weight
            if trace is not None and len(trace) < max_trace_events:
                trace.append(
                    TraceEvent(
                        "relaxa" if tentative_g < g_score[edge.destination] else "descarta",
                        origem=current,
                        destino=edge.destination,
                        custo=tentative_g,
                    )
                )
            if tentative_g < g_score[edge.destination]:
                g_score[edge.destination] = tentative_g
                predecessors[edge.destination] = current
                new_f = tentative_g + heuristic(edge.destination)
                f_score[edge.destination] = new_f
                heapq.heappush(queue, (new_f, edge.destination))

    return RouteResult.not_found(nodes_expanded=nodes_expanded, edges_relaxed=edges_relaxed)
