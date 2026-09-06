"""Implementacao do algoritmo de Bellman-Ford."""

import math

from backend.algorithms.result import RouteResult, TraceEvent
from backend.graph import Network

type Arc = tuple[str, str, float]


class NegativeCycleError(ValueError):
    """Sinaliza um ciclo de custo negativo alcancavel a partir da origem."""


def bellman_ford(
    network: Network,
    origin: str,
    destination: str,
    *,
    trace: list[TraceEvent] | None = None,
    max_trace_events: int = 5000,
) -> RouteResult:
    """Calcula o caminho de menor custo relaxando todas as arestas a cada rodada.

    Um caminho minimo tem no maximo V-1 arestas, entao V-1 rodadas de relaxamento
    sobre as E arestas bastam para estabilizar os custos: O(V*E), mais lento que
    Dijkstra em troca de aceitar peso negativo. A rodada extra ao final detecta
    ciclo negativo -- se ainda houver aresta relaxavel, nao existe caminho minimo
    bem definido. Como a rede e nao dirigida, qualquer aresta negativa ativa e por
    si so um ciclo negativo (ida e volta pelo mesmo cabo).

    O relaxamento para assim que uma rodada nao altera nenhum custo; nesse caso a
    busca ja convergiu e nao ha ciclo negativo alcancavel.

    Ao contrario de Dijkstra/A*, Bellman-Ford nao seleciona um no de cada vez: a
    cada rodada ele reexamina toda aresta cuja origem tenha distancia finita, mesmo
    que ja estivesse estabilizada. ``nodes_expanded`` soma, rodada a rodada, quantos
    nos distintos tiveram suas arestas de saida reexaminadas -- por isso tende a ser
    bem maior que o de Dijkstra/A* no mesmo grafo, o que evidencia o custo de nao ter
    uma fila de prioridade guiando a busca. ``edges_relaxed`` conta cada tentativa de
    relaxamento (arestas com origem finita) somada sobre todas as rodadas.

    Raises:
        KeyError: se a origem ou o destino nao existir.
        NegativeCycleError: se houver ciclo negativo alcancavel pela origem.
    """
    if not network.is_node_up(origin) or not network.is_node_up(destination):
        return RouteResult.not_found()
    if origin == destination:
        return RouteResult(path=[origin], cost=0.0, found=True)

    arcs = _usable_arcs(network)
    distances = dict.fromkeys(network.node_ids(), math.inf)
    distances[origin] = 0.0
    predecessors: dict[str, str] = {}
    nodes_expanded = 0
    edges_relaxed = 0

    for round_number in range(1, len(distances)):
        changed, round_nodes, round_edges = _relax_all(
            arcs, distances, predecessors, trace, round_number, max_trace_events
        )
        nodes_expanded += round_nodes
        edges_relaxed += round_edges
        if not changed:
            _trace(trace, TraceEvent("finaliza", rodada=round_number), max_trace_events)
            break
    else:
        if _has_relaxable_arc(arcs, distances):
            raise NegativeCycleError(f"Negative cycle reachable from {origin!r}")

    if math.isinf(distances[destination]):
        return RouteResult.not_found(nodes_expanded=nodes_expanded, edges_relaxed=edges_relaxed)
    return RouteResult.from_predecessors(
        predecessors,
        origin,
        destination,
        distances[destination],
        nodes_expanded=nodes_expanded,
        edges_relaxed=edges_relaxed,
    )


def _usable_arcs(network: Network) -> tuple[Arc, ...]:
    """Lista os dois sentidos de cada cabo utilizavel.

    ``neighbors`` ja descarta no indisponivel e cabo fora do ar, garantindo o
    mesmo recorte da rede usado pelo Dijkstra.
    """
    return tuple(
        (node_id, edge.destination, edge.weight)
        for node_id in network.node_ids()
        for edge in network.neighbors(node_id)
    )


def _relax_all(
    arcs: tuple[Arc, ...],
    distances: dict[str, float],
    predecessors: dict[str, str],
    trace: list[TraceEvent] | None = None,
    round_number: int = 0,
    max_trace_events: int = 5000,
) -> tuple[bool, int, int]:
    """Executa uma rodada de relaxamento.

    Devolve se algum custo mudou, quantos nos distintos com distancia finita
    tiveram suas arestas examinadas e quantas tentativas de relaxamento houve.
    """
    changed = False
    touched_origins: set[str] = set()
    edges_relaxed = 0
    for origin, destination, weight in arcs:
        if math.isinf(distances[origin]):
            continue
        touched_origins.add(origin)
        edges_relaxed += 1
        new_cost = distances[origin] + weight
        event_type = "relaxa" if new_cost < distances[destination] else "descarta"
        _trace(
            trace,
            TraceEvent(
                event_type,
                origem=origin,
                destino=destination,
                custo=new_cost,
                rodada=round_number,
            ),
            max_trace_events,
        )
        if new_cost < distances[destination]:
            distances[destination] = new_cost
            predecessors[destination] = origin
            changed = True
    return changed, len(touched_origins), edges_relaxed


def _trace(trace: list[TraceEvent] | None, event: TraceEvent, limit: int) -> None:
    if trace is not None and len(trace) < limit:
        trace.append(event)


def _has_relaxable_arc(arcs: tuple[Arc, ...], distances: dict[str, float]) -> bool:
    return any(
        not math.isinf(distances[origin]) and distances[origin] + weight < distances[destination]
        for origin, destination, weight in arcs
    )
