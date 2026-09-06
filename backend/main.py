"""Aplicacao FastAPI que expoe a simulacao de colapso da malha de rede."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.algorithms import (
    TraceEvent,
    a_star,
    bellman_ford,
    dijkstra,
    find_critical_points,
    k_shortest_paths,
    minimum_edge_cut,
)
from backend.graph import Network
from backend.resilience import simulate_cascade
from backend.schemas import (
    AlgoritmoNome,
    ArestaRequest,
    ArestaState,
    CascataRequest,
    CascataResult,
    CorteMinimoRequest,
    CorteMinimoResult,
    CriticidadeResult,
    FalhasRequest,
    GrafoState,
    NoState,
    PonteState,
    RotaAtual,
    RotaPassosResult,
    RotaRequest,
    RotaResult,
    RotasRequest,
    RotasResult,
    StatusResponse,
)
from backend.simulation import (
    RoutingAlgorithm,
    derrubar_aresta,
    derrubar_no,
    recalcular_rota,
    restaurar_aresta,
    restaurar_no,
)
from backend.state import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    get_network,
    get_route,
    network_lifespan,
    set_route,
)

# O contrato HTTP usa `bellman_ford` (identificador valido em qualquer
# linguagem cliente) e o dominio usa `bellman-ford`; o mapa isola a traducao.
_ALGORITMOS: dict[AlgoritmoNome, RoutingAlgorithm] = {
    "dijkstra": "dijkstra",
    "bellman_ford": "bellman-ford",
    "a_star": "a-star",
}
_ALGORITMOS_COM_TRACE = {
    "dijkstra": dijkstra,
    "bellman_ford": bellman_ford,
    "a_star": a_star,
}

app = FastAPI(
    title="Simulador de Colapso de Internet",
    description="API de topologia, roteamento dinamico e injecao de falhas na malha.",
    version="0.1.0",
    lifespan=network_lifespan,
)


@app.middleware("http")
async def persist_session(request: Request, call_next):
    response = await call_next(request)
    network = getattr(request.state, "session_network", None)
    session_id = getattr(request.state, "session_id", None)
    if network is not None and session_id is not None:
        request.app.state.sessions.save(session_id, network)
        if getattr(request.state, "new_session", False):
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=SESSION_TTL_SECONDS,
                httponly=True,
                samesite="lax",
            )
    return response


# Em desenvolvimento o front-end e servido de uma porta arbitraria de localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

NetworkDep = Annotated[Network, Depends(get_network)]
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@contextmanager
def _traduz_erros() -> Iterator[None]:
    """Converte os erros de dominio em respostas HTTP.

    ``Network`` sinaliza no/cabo inexistente com ``KeyError``; os algoritmos
    sinalizam peso negativo e ciclo negativo com ``ValueError``.
    """
    try:
        yield
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error.args[0])) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/status")
def status() -> StatusResponse:
    return StatusResponse(status="ok")


@app.get("/grafo")
def obter_grafo(request: Request, network: NetworkDep) -> GrafoState:
    """Retorna a topologia completa com o estado corrente de nos e cabos."""
    return _grafo_state(request, network)


def _grafo_state(request: Request, network: Network) -> GrafoState:
    return GrafoState(
        nos=[_no_state(node.id, network) for node in network.nodes()],
        arestas=[
            ArestaState(
                origem=origem,
                destino=edge.destination,
                peso=edge.weight,
                cabo=edge.cable,
                fontes=list(edge.source_ids),
                ativo=edge.is_up,
            )
            for origem, edge in network.edges()
        ],
        rota_atual=get_route(request),
    )


@app.get("/analise/criticidade")
def obter_criticidade(network: NetworkDep) -> CriticidadeResult:
    """Identifica pontos de articulacao e pontes na rede disponivel no momento."""
    resultado = find_critical_points(network)
    return CriticidadeResult(
        articulacoes=list(resultado.articulation_points),
        pontes=[
            PonteState(origem=origem, destino=destino) for origem, destino in resultado.bridges
        ],
        componentes=resultado.components,
    )


@app.post("/analise/cascata")
def analisar_cascata(pedido: CascataRequest, network: NetworkDep) -> CascataResult:
    """Mede a degradacao progressiva sem alterar a rede compartilhada pela API."""
    with _traduz_erros():
        result = simulate_cascade(
            network,
            strategy=pedido.estrategia,
            steps=pedido.passos,
            seed=pedido.semente,
        )
    return CascataResult.from_domain(result)


@app.post("/analise/corte-minimo")
def calcular_corte_minimo(pedido: CorteMinimoRequest, network: NetworkDep) -> CorteMinimoResult:
    """Calcula quantos cabos ativos separam dois roteadores pelo teorema de Menger."""
    with _traduz_erros():
        resultado = minimum_edge_cut(network, pedido.origem, pedido.destino)
    return CorteMinimoResult(
        capacidade=resultado.capacity,
        arestas=[
            ArestaRequest(origem=origem, destino=destino) for origem, destino in resultado.edges
        ],
    )


@app.post("/rota")
def calcular_rota(pedido: RotaRequest, request: Request, network: NetworkDep) -> RotaResult:
    """Calcula a melhor rota atual entre dois roteadores.

    Rede particionada nao e erro: devolve 200 com ``encontrada=False``, que e o
    caso interessante da simulacao. Origem igual ao destino tambem e valido e
    devolve custo zero.
    """
    with _traduz_erros():
        resultado = recalcular_rota(
            network, pedido.origem, pedido.destino, _ALGORITMOS[pedido.algoritmo]
        )
    resposta = RotaResult.from_domain(resultado, pedido.algoritmo)
    set_route(
        request,
        RotaAtual(
            origem=pedido.origem,
            destino=pedido.destino,
            **resposta.model_dump(),
        ),
    )
    return resposta


@app.post("/rota/passos", response_model=RotaPassosResult)
def calcular_rota_passos(pedido: RotaRequest, request: Request, network: NetworkDep):
    """Calcula uma rota e devolve o traco limitado da execucao do algoritmo."""
    limit = 5000
    trace: list[TraceEvent] = []
    with _traduz_erros():
        calculator = _ALGORITMOS_COM_TRACE[pedido.algoritmo]
        resultado = calculator(
            network,
            pedido.origem,
            pedido.destino,
            trace=trace,
            max_trace_events=limit,
        )
    trace.append(TraceEvent("finaliza"))
    resposta = RotaResult.from_domain(resultado, pedido.algoritmo)
    set_route(
        request,
        RotaAtual(origem=pedido.origem, destino=pedido.destino, **resposta.model_dump()),
    )
    return RotaPassosResult(
        rota=resposta,
        passos=[asdict(event) for event in trace[:limit]],
        truncado=len(trace) > limit,
        limite=limit,
    )


@app.post("/rotas")
def calcular_rotas(pedido: RotasRequest, network: NetworkDep) -> RotasResult:
    """Calcula ate k rotas alternativas simples, ordenadas por custo (algoritmo de Yen).

    A diferenca percentual entre a 2a melhor rota e a melhor mede a
    redundancia do par. Rede particionada nao e erro: devolve 200 com lista
    vazia e ``encontrada=False``, como em ``/rota``.
    """
    with _traduz_erros():
        resultados = k_shortest_paths(network, pedido.origem, pedido.destino, pedido.k)
    return RotasResult.from_domain(pedido.origem, pedido.destino, resultados)


@app.post("/nos/{no_id}/derrubar")
def derrubar_no_endpoint(no_id: str, request: Request, network: NetworkDep) -> NoState:
    """Tira um roteador do ar sem remove-lo da topologia."""
    with _traduz_erros():
        derrubar_no(network, no_id)
    _invalidar_rota(request)
    return _no_state(no_id, network)


@app.post("/nos/{no_id}/restaurar")
def restaurar_no_endpoint(no_id: str, request: Request, network: NetworkDep) -> NoState:
    """Devolve um roteador ao ar, sem alterar o estado dos cabos."""
    with _traduz_erros():
        restaurar_no(network, no_id)
    _invalidar_rota(request)
    return _no_state(no_id, network)


@app.post("/arestas/derrubar")
def derrubar_aresta_endpoint(
    cabo: ArestaRequest, request: Request, network: NetworkDep
) -> ArestaState:
    """Tira um cabo bidirecional do ar."""
    with _traduz_erros():
        derrubar_aresta(network, cabo.origem, cabo.destino)
        estado = _aresta_state(network, cabo.origem, cabo.destino)
    _invalidar_rota(request)
    return estado


@app.post("/arestas/restaurar")
def restaurar_aresta_endpoint(
    cabo: ArestaRequest, request: Request, network: NetworkDep
) -> ArestaState:
    """Devolve um cabo bidirecional ao ar."""
    with _traduz_erros():
        restaurar_aresta(network, cabo.origem, cabo.destino)
        estado = _aresta_state(network, cabo.origem, cabo.destino)
    _invalidar_rota(request)
    return estado


@app.post("/simulacao/resetar", response_model=GrafoState)
def resetar_simulacao(request: Request, network: NetworkDep) -> GrafoState:
    """Restaura todos os elementos e limpa a rota corrente atomicamente."""
    for node in network.nodes():
        if not node.is_up:
            restaurar_no(network, node.id)
    for origin, edge in network.edges():
        if not edge.is_up:
            restaurar_aresta(network, origin, edge.destination)
    set_route(request, None)
    return _grafo_state(request, network)


@app.post("/simulacao/falhas", response_model=GrafoState)
def aplicar_falhas(pedido: FalhasRequest, request: Request, network: NetworkDep) -> GrafoState:
    """Aplica um lote de falhas somente depois de validar todos os identificadores."""
    with _traduz_erros():
        for node_id in pedido.nos:
            network.get_node(node_id)
        for edge in pedido.arestas:
            network.is_edge_up(edge.origem, edge.destino)
        for node_id in pedido.nos:
            derrubar_no(network, node_id)
        for edge in pedido.arestas:
            derrubar_aresta(network, edge.origem, edge.destino)
    _invalidar_rota(request)
    return _grafo_state(request, network)


def _invalidar_rota(request: Request) -> None:
    """Remove o destaque quando uma mudanca torna a rota armazenada obsoleta."""
    set_route(request, None)


def _aresta_state(network: Network, origem: str, destino: str) -> ArestaState:
    """Recupera os dados de um cabo ja validado pela operacao anterior."""
    for node_id, edge in network.edges():
        if {node_id, edge.destination} == {origem, destino}:
            return ArestaState(
                origem=origem,
                destino=destino,
                peso=edge.weight,
                cabo=edge.cable,
                fontes=list(edge.source_ids),
                ativo=edge.is_up,
            )
    raise KeyError(f"Edge does not exist: {origem!r} - {destino!r}")


def _no_state(node_id: str, network: Network) -> NoState:
    node = network.get_node(node_id)
    return NoState(
        id=node.id,
        nome=node.name,
        lat=node.lat,
        lon=node.lon,
        ativo=node.is_up,
    )


# O mount fica depois das rotas da API para que a raiz do front-end nao as intercepte.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
