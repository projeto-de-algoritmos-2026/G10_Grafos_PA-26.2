"""Aplicacao FastAPI que expoe a simulacao de colapso da malha de rede."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.graph import Network
from backend.schemas import (
    AlgoritmoNome,
    ArestaRequest,
    ArestaState,
    GrafoState,
    NoState,
    RotaRequest,
    RotaResult,
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
from backend.state import get_network, network_lifespan

# O contrato HTTP usa `bellman_ford` (identificador valido em qualquer
# linguagem cliente) e o dominio usa `bellman-ford`; o mapa isola a traducao.
_ALGORITMOS: dict[AlgoritmoNome, RoutingAlgorithm] = {
    "dijkstra": "dijkstra",
    "bellman_ford": "bellman-ford",
}

app = FastAPI(
    title="Simulador de Colapso de Internet",
    description="API de topologia, roteamento dinamico e injecao de falhas na malha.",
    version="0.1.0",
    lifespan=network_lifespan,
)

# Em desenvolvimento o front-end e servido de uma porta arbitraria de localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

NetworkDep = Annotated[Network, Depends(get_network)]


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
def obter_grafo(network: NetworkDep) -> GrafoState:
    """Retorna a topologia completa com o estado corrente de nos e cabos."""
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
    )


@app.post("/rota")
def calcular_rota(pedido: RotaRequest, network: NetworkDep) -> RotaResult:
    """Calcula a melhor rota atual entre dois roteadores.

    Rede particionada nao e erro: devolve 200 com ``encontrada=False``, que e o
    caso interessante da simulacao. Origem igual ao destino tambem e valido e
    devolve custo zero.
    """
    with _traduz_erros():
        resultado = recalcular_rota(
            network, pedido.origem, pedido.destino, _ALGORITMOS[pedido.algoritmo]
        )
    return RotaResult.from_domain(resultado, pedido.algoritmo)


@app.post("/nos/{no_id}/derrubar")
def derrubar_no_endpoint(no_id: str, network: NetworkDep) -> NoState:
    """Tira um roteador do ar sem remove-lo da topologia."""
    with _traduz_erros():
        derrubar_no(network, no_id)
    return _no_state(no_id, network)


@app.post("/nos/{no_id}/restaurar")
def restaurar_no_endpoint(no_id: str, network: NetworkDep) -> NoState:
    """Devolve um roteador ao ar, sem alterar o estado dos cabos."""
    with _traduz_erros():
        restaurar_no(network, no_id)
    return _no_state(no_id, network)


@app.post("/arestas/derrubar")
def derrubar_aresta_endpoint(cabo: ArestaRequest, network: NetworkDep) -> ArestaState:
    """Tira um cabo bidirecional do ar."""
    with _traduz_erros():
        derrubar_aresta(network, cabo.origem, cabo.destino)
        estado = _aresta_state(network, cabo.origem, cabo.destino)
    return estado


@app.post("/arestas/restaurar")
def restaurar_aresta_endpoint(cabo: ArestaRequest, network: NetworkDep) -> ArestaState:
    """Devolve um cabo bidirecional ao ar."""
    with _traduz_erros():
        restaurar_aresta(network, cabo.origem, cabo.destino)
        estado = _aresta_state(network, cabo.origem, cabo.destino)
    return estado


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
