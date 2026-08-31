"""Contrato e validacao do dataset geografico da malha mundial."""

from __future__ import annotations

from datetime import date
from math import asin, cos, isclose, radians, sin, sqrt
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

EARTH_RADIUS_KM = 6371.0088
MIN_NODES = 15
MAX_NODES = 30
WEIGHT_TOLERANCE_KM = 1.0


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetSource(_StrictModel):
    """Referencia auditavel usada na construcao do dataset."""

    nome: str = Field(min_length=1)
    url: HttpUrl
    uso: str = Field(min_length=1)
    licenca: str | None = None


class DatasetMetadata(_StrictModel):
    """Decisoes de modelagem e procedencia do arquivo."""

    versao: Literal[1]
    escopo: Literal["malha_mundial"]
    unidade_peso: Literal["km"]
    sistema_coordenadas: Literal["WGS84"]
    metodologia_peso: str = Field(min_length=1)
    semantica_aresta: str = Field(min_length=1)
    consultado_em: date
    fontes: dict[str, DatasetSource] = Field(min_length=1)


class DatasetNode(_StrictModel):
    """Cidade, landing point ou agregacao metropolitana exibida no mapa."""

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    nome: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class DatasetEdge(_StrictModel):
    """Conectividade logica por um sistema real de cabo."""

    origem: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    destino: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    peso: float = Field(gt=0, allow_inf_nan=False)
    cabo: str = Field(min_length=1)
    fontes: list[str] = Field(min_length=1)


class NetworkDataset(_StrictModel):
    """Dataset completo, validado antes de chegar ao dominio."""

    metadata: DatasetMetadata
    nos: list[DatasetNode] = Field(min_length=MIN_NODES, max_length=MAX_NODES)
    arestas: list[DatasetEdge] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_topology(self) -> Self:
        nodes_by_id = {node.id: node for node in self.nos}
        if len(nodes_by_id) != len(self.nos):
            raise ValueError("Node ids must be unique")

        seen_edges: set[frozenset[str]] = set()
        adjacency = {node_id: set() for node_id in nodes_by_id}

        for edge in self.arestas:
            if edge.origem == edge.destino:
                raise ValueError(f"Self-loop is not supported: {edge.origem!r}")
            if edge.origem not in nodes_by_id or edge.destino not in nodes_by_id:
                raise ValueError(
                    f"Edge references unknown node: {edge.origem!r} - {edge.destino!r}"
                )

            key = frozenset((edge.origem, edge.destino))
            if key in seen_edges:
                raise ValueError(f"Duplicate undirected edge: {edge.origem!r} - {edge.destino!r}")
            seen_edges.add(key)

            missing_sources = set(edge.fontes) - self.metadata.fontes.keys()
            if missing_sources:
                names = ", ".join(sorted(missing_sources))
                raise ValueError(f"Edge references unknown sources: {names}")

            origin = nodes_by_id[edge.origem]
            destination = nodes_by_id[edge.destino]
            expected_weight = round(
                haversine_km(origin.lat, origin.lon, destination.lat, destination.lon)
            )
            if not isclose(edge.peso, expected_weight, abs_tol=WEIGHT_TOLERANCE_KM):
                raise ValueError(
                    f"Invalid weight for {edge.origem!r} - {edge.destino!r}: "
                    f"expected about {expected_weight} km, got {edge.peso}"
                )

            adjacency[edge.origem].add(edge.destino)
            adjacency[edge.destino].add(edge.origem)

        visited: set[str] = set()
        pending = [self.nos[0].id]
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            pending.extend(adjacency[node_id] - visited)

        if visited != nodes_by_id.keys():
            disconnected = ", ".join(sorted(nodes_by_id.keys() - visited))
            raise ValueError(
                f"Network dataset must be connected; unreachable nodes: {disconnected}"
            )
        return self


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distancia geodesica aproximada entre coordenadas WGS84."""
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, (lat1, lon1, lat2, lon2))
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    value = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(value))
