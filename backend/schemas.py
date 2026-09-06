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


class RotasRequest(BaseModel):
    """Pedido das k melhores rotas alternativas entre dois roteadores."""

    origem: str
    destino: str
    k: int = Field(default=3, ge=1, le=10, description="Quantidade de rotas desejadas")


class RotasResult(BaseModel):
    """Rotas alternativas calculadas pelo algoritmo de Yen, da mais barata a mais cara.

    Reaproveita ``RotaResult`` por item da lista para que o front-end use a
    mesma renderizacao da rota principal nas alternativas.
    """

    origem: str
    destino: str
    encontrada: bool
    rotas: list[RotaResult]
    redundancia_percentual: float | None = Field(
        default=None,
        description=(
            "Diferenca percentual de custo entre a 2a melhor rota e a melhor: "
            "mede a redundancia do par. None quando ha menos de 2 rotas."
        ),
    )

    @classmethod
    def from_domain(cls, origem: str, destino: str, resultados: list[RouteResult]) -> "RotasResult":
        """Converte a lista ordenada de resultados do dominio para o formato publicado."""
        rotas = [RotaResult.from_domain(resultado, "dijkstra") for resultado in resultados]
        redundancia = None
        if len(resultados) >= 2 and resultados[0].cost > 0:
            redundancia = (resultados[1].cost - resultados[0].cost) / resultados[0].cost * 100
        return cls(
            origem=origem,
            destino=destino,
            encontrada=bool(resultados),
            rotas=rotas,
            redundancia_percentual=redundancia,
        )


class RotaAtual(RotaResult):
    """Ultima consulta de rota, incluindo os extremos mesmo sem caminho."""

    origem: str
    destino: str


class GrafoState(BaseModel):
    """Topologia completa e ultima rota calculada pela simulacao."""

    nos: list[NoState]
    arestas: list[ArestaState]
    rota_atual: RotaAtual | None = None


class StatusResponse(BaseModel):
    """Resposta do health-check."""

    status: Literal["ok"]


class PonteState(BaseModel):
    """Cabo cuja remocao aumenta o numero de componentes conexas da rede ativa."""

    origem: str
    destino: str


class CriticidadeResult(BaseModel):
    """Pontos unicos de falha da rede disponivel no momento da analise."""

    articulacoes: list[str]
    pontes: list[PonteState]
    componentes: int
