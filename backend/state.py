"""Carga e ciclo de vida da malha de rede servida pela API."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from pydantic import ValidationError

from backend.dataset import NetworkDataset
from backend.graph import Network

DATA_FILE = Path(__file__).parent / "data" / "rede.json"


def load_dataset(data_file: Path = DATA_FILE) -> NetworkDataset:
    """Le e valida integralmente o dataset; erros impedem uma inicializacao parcial."""
    try:
        raw_data = json.loads(data_file.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"Network dataset not found: {data_file}") from error
    except json.JSONDecodeError as error:
        location = f"line {error.lineno}, column {error.colno}"
        raise RuntimeError(f"Invalid JSON in network dataset {data_file}: {location}") from error

    try:
        return NetworkDataset.model_validate(raw_data)
    except ValidationError as error:
        raise RuntimeError(f"Invalid network dataset {data_file}: {error}") from error


def load_network(data_file: Path = DATA_FILE) -> Network:
    """Converte o dataset validado para a estrutura usada pelos algoritmos."""
    dataset = load_dataset(data_file)
    network = Network()
    for node in dataset.nos:
        network.add_node(node.id, name=node.nome, lat=node.lat, lon=node.lon)
    for edge in dataset.arestas:
        network.add_edge(
            edge.origem,
            edge.destino,
            edge.peso,
            cable=edge.cabo,
            source_ids=tuple(edge.fontes),
        )
    return network


@asynccontextmanager
async def network_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Carrega uma unica rede stateful antes de a API aceitar requisicoes."""
    app.state.network = load_network()
    app.state.rota_atual = None
    yield


def get_network(request: Request) -> Network:
    """Dependencia FastAPI que recupera a rede carregada durante o startup."""
    return request.app.state.network
