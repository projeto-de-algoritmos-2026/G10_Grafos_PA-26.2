"""Estrutura de dados da malha de rede do simulador."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(slots=True)
class Edge:
    """Entrada de uma aresta na lista de adjacencia."""

    destination: str
    weight: float
    cable: str = "synthetic"
    source_ids: tuple[str, ...] = ()
    is_up: bool = True


@dataclass(slots=True)
class Node:
    """No da malha com os metadados necessarios para a visualizacao."""

    id: str
    name: str
    lat: float
    lon: float
    is_up: bool = True


class Network:
    """Grafo ponderado, nao dirigido, que representa a malha de rede.

    Cada cabo bidirecional e armazenado como duas entradas espelhadas na lista
    de adjacencia. Nos e arestas indisponiveis permanecem na estrutura e sao
    marcados apenas por flags, permitindo que sejam restaurados posteriormente.

    Rotas assimetricas podem ser consideradas como extensao futura; o dominio
    atual modela somente cabos bidirecionais.
    """

    def __init__(self) -> None:
        self._adjacency: dict[str, list[Edge]] = {}
        self._nodes: dict[str, Node] = {}

    def add_node(
        self,
        node_id: str,
        *,
        name: str | None = None,
        lat: float = 0.0,
        lon: float = 0.0,
    ) -> None:
        """Adiciona um no ativo; adicionar novamente o mesmo no nao tem efeito."""
        self._validate_node_id(node_id)
        if node_id not in self._adjacency:
            self._adjacency[node_id] = []
            self._nodes[node_id] = Node(node_id, name or node_id, float(lat), float(lon))

    def add_edge(
        self,
        origin: str,
        destination: str,
        weight: float,
        *,
        cable: str = "synthetic",
        source_ids: tuple[str, ...] = (),
    ) -> None:
        """Adiciona um cabo bidirecional entre dois nos existentes."""
        self._require_node(origin)
        self._require_node(destination)
        if origin == destination:
            raise ValueError("Self-loops are not supported")
        if isinstance(weight, bool) or not isinstance(weight, Real) or not isfinite(weight):
            raise ValueError("Edge weight must be a finite number")
        if self._find_edge(origin, destination) is not None:
            raise ValueError(f"Edge already exists: {origin!r} - {destination!r}")

        numeric_weight = float(weight)
        self._adjacency[origin].append(Edge(destination, numeric_weight, cable, source_ids))
        self._adjacency[destination].append(Edge(origin, numeric_weight, cable, source_ids))

    def set_node_down(self, node_id: str) -> None:
        """Marca um no como indisponivel sem remove-lo da estrutura."""
        self._require_node(node_id)
        self._nodes[node_id].is_up = False

    def set_node_up(self, node_id: str) -> None:
        """Marca um no como disponivel sem alterar o estado de suas arestas."""
        self._require_node(node_id)
        self._nodes[node_id].is_up = True

    def set_edge_down(self, origin: str, destination: str) -> None:
        """Marca as duas entradas de um cabo como indisponiveis."""
        self._set_edge_status(origin, destination, is_up=False)

    def set_edge_up(self, origin: str, destination: str) -> None:
        """Marca as duas entradas de um cabo como disponiveis."""
        self._set_edge_status(origin, destination, is_up=True)

    def neighbors(self, node_id: str) -> list[Edge]:
        """Retorna copias das conexoes disponiveis de um no disponivel."""
        self._require_node(node_id)
        if not self._nodes[node_id].is_up:
            return []
        return [
            Edge(edge.destination, edge.weight, edge.cable, edge.source_ids, edge.is_up)
            for edge in self._adjacency[node_id]
            if edge.is_up and self._nodes[edge.destination].is_up
        ]

    def is_node_up(self, node_id: str) -> bool:
        """Informa se um no existe e esta disponivel."""
        self._require_node(node_id)
        return self._nodes[node_id].is_up

    def is_edge_up(self, origin: str, destination: str) -> bool:
        """Informa o estado do cabo, independentemente do estado dos seus nos."""
        forward, reverse = self._require_edge_pair(origin, destination)
        return forward.is_up and reverse.is_up

    def node_ids(self) -> tuple[str, ...]:
        """Retorna os identificadores dos nos na ordem de insercao."""
        return tuple(self._adjacency)

    def nodes(self) -> tuple[Node, ...]:
        """Retorna copias dos nos na ordem de insercao."""
        return tuple(
            Node(node.id, node.name, node.lat, node.lon, node.is_up)
            for node in self._nodes.values()
        )

    def get_node(self, node_id: str) -> Node:
        """Retorna uma copia de um no existente."""
        self._require_node(node_id)
        node = self._nodes[node_id]
        return Node(node.id, node.name, node.lat, node.lon, node.is_up)

    def edges(self) -> tuple[tuple[str, Edge], ...]:
        """Retorna cada cabo uma unica vez, incluindo os indisponiveis."""
        result: list[tuple[str, Edge]] = []
        visited: set[frozenset[str]] = set()
        for origin, adjacent_edges in self._adjacency.items():
            for edge in adjacent_edges:
                key = frozenset((origin, edge.destination))
                if key not in visited:
                    visited.add(key)
                    result.append(
                        (
                            origin,
                            Edge(
                                edge.destination,
                                edge.weight,
                                edge.cable,
                                edge.source_ids,
                                edge.is_up,
                            ),
                        )
                    )
        return tuple(result)

    def _set_edge_status(self, origin: str, destination: str, *, is_up: bool) -> None:
        forward, reverse = self._require_edge_pair(origin, destination)
        forward.is_up = is_up
        reverse.is_up = is_up

    def _require_edge_pair(self, origin: str, destination: str) -> tuple[Edge, Edge]:
        self._require_node(origin)
        self._require_node(destination)
        forward = self._find_edge(origin, destination)
        reverse = self._find_edge(destination, origin)
        if forward is None or reverse is None:
            raise KeyError(f"Edge does not exist: {origin!r} - {destination!r}")
        return forward, reverse

    def _find_edge(self, origin: str, destination: str) -> Edge | None:
        return next(
            (edge for edge in self._adjacency[origin] if edge.destination == destination),
            None,
        )

    def _require_node(self, node_id: str) -> None:
        if node_id not in self._adjacency:
            raise KeyError(f"Node does not exist: {node_id!r}")

    @staticmethod
    def _validate_node_id(node_id: str) -> None:
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("Node id must be a non-empty string")
