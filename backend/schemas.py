"""Modelos Pydantic do contrato HTTP da API.

Os nomes de campo aqui sao a interface publica consumida pelo front-end via
schema do Swagger: mante-los estaveis evita retrabalho na interface. Por isso o
vocabulario e o mesmo das rotas (PT-BR), mesmo que a camada de dominio use
identificadores em ingles.
"""

from typing import Literal

from pydantic import BaseModel, Field

from backend.algorithms import RouteResult

type AlgoritmoNome = Literal["dijkstra", "bellman_ford"]


class NoState(BaseModel):
    """Estado publicado de um roteador da malha."""

    id: str
    nome: str
    lat: float
    lon: float
    ativo: bool = Field(description="False quando o no foi derrubado pela simulacao")


class ArestaState(BaseModel):
    """Estado publicado de um cabo bidirecional.

    Cada cabo aparece uma unica vez; ``origem`` e ``destino`` sao apenas a ordem
    de insercao, nao um sentido de trafego.
    """

    origem: str
    destino: str
    peso: float
    cabo: str
    fontes: list[str]
    ativo: bool = Field(description="False quando o cabo foi derrubado pela simulacao")


class GrafoState(BaseModel):
    """Topologia completa da malha com o estado corrente de nos e cabos."""

    nos: list[NoState]
    arestas: list[ArestaState]


class RotaRequest(BaseModel):
    """Pedido de calculo de rota entre dois roteadores."""

    origem: str
    destino: str
    algoritmo: AlgoritmoNome = "dijkstra"


class ArestaRequest(BaseModel):
    """Identificacao de um cabo pelos seus dois extremos, em qualquer ordem."""

    origem: str
    destino: str


class RotaResult(BaseModel):
    """Rota calculada pelo algoritmo escolhido.

    ``custo`` e ``None`` quando nao existe rota: o dominio usa ``math.inf``, que
    nao tem representacao valida em JSON.
    """

    caminho: list[str]
    custo: float | None
    encontrada: bool
    algoritmo: AlgoritmoNome

    @classmethod
    def from_domain(cls, resultado: RouteResult, algoritmo: AlgoritmoNome) -> "RotaResult":
        """Converte o resultado do dominio para o formato publicado."""
        return cls(
            caminho=resultado.path,
            custo=resultado.cost if resultado.found else None,
            encontrada=resultado.found,
            algoritmo=algoritmo,
        )


class StatusResponse(BaseModel):
    """Resposta do health-check."""

    status: Literal["ok"]
