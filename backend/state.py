"""Carga e ciclo de vida da malha de rede servida pela API."""

import json
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Request
from pydantic import ValidationError

from backend.dataset import NetworkDataset
from backend.graph import Network

DATA_FILE = Path(__file__).parent / "data" / "rede.json"
SESSION_COOKIE = "simulation_session"
SESSION_TTL_SECONDS = 30 * 60
MAX_SESSIONS = 100


@dataclass
class SimulationState:
    """Estado mutavel exclusivo de uma sessao de simulacao."""

    last_seen: float = field(default_factory=time.monotonic)
    down_nodes: set[str] = field(default_factory=set)
    down_edges: set[frozenset[str]] = field(default_factory=set)
    route: object | None = None


class SessionStore:
    """Armazena sessoes com expiracao e limite para evitar crescimento infinito."""

    def __init__(self, *, ttl_seconds: int = SESSION_TTL_SECONDS, max_sessions: int = MAX_SESSIONS):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, SimulationState] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str | None) -> tuple[str, SimulationState, bool]:
        now = time.monotonic()
        with self._lock:
            self._collect_expired(now)
            if session_id and session_id in self._sessions:
                state = self._sessions[session_id]
                state.last_seen = now
                return session_id, state, False
            new_id = secrets.token_urlsafe(32)
            state = SimulationState(last_seen=now)
            self._sessions[new_id] = state
            self._trim_oldest()
            return new_id, state, True

    def save(self, session_id: str, network: Network) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            state.last_seen = time.monotonic()
            state.down_nodes = {node.id for node in network.nodes() if not node.is_up}
            state.down_edges = {
                frozenset((origin, edge.destination))
                for origin, edge in network.edges()
                if not edge.is_up
            }

    def _collect_expired(self, now: float) -> None:
        expired = [
            session_id
            for session_id, state in self._sessions.items()
            if now - state.last_seen >= self.ttl_seconds
        ]
        for session_id in expired:
            del self._sessions[session_id]

    def _trim_oldest(self) -> None:
        while len(self._sessions) > self.max_sessions:
            oldest = min(self._sessions, key=lambda key: self._sessions[key].last_seen)
            del self._sessions[oldest]


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
    """Carrega a topologia imutavel e inicializa o armazenamento de sessoes."""
    app.state.network = load_network()
    app.state.sessions = SessionStore()
    yield


def get_network(request: Request) -> Network:
    """Retorna uma visao da topologia com as falhas da sessao corrente."""
    store: SessionStore = request.app.state.sessions
    session_id, state, is_new = store.get_or_create(request.cookies.get(SESSION_COOKIE))
    network = request.app.state.network.clone()
    for node_id in state.down_nodes:
        network.set_node_down(node_id)
    for edge in state.down_edges:
        origin, destination = tuple(edge)
        network.set_edge_down(origin, destination)
    request.state.session_id = session_id
    request.state.session = state
    request.state.session_network = network
    request.state.new_session = is_new
    return network


def get_route(request: Request) -> object | None:
    """Retorna a rota corrente da sessao, com fallback para testes legados."""
    state = getattr(request.state, "session", None)
    if state is not None:
        return state.route
    return getattr(request.app.state, "rota_atual", None)


def set_route(request: Request, route: object | None) -> None:
    """Atualiza a rota corrente da sessao."""
    state = getattr(request.state, "session", None)
    if state is not None:
        state.route = route
    else:
        request.app.state.rota_atual = route
