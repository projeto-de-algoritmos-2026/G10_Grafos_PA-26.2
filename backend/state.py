"""Carga e ciclo de vida da malha de rede servida pela API."""

import json
from pathlib import Path
from typing import Any

from backend.graph import Network

DATA_FILE = Path(__file__).parent / "data" / "rede.json"


def load_network(data_file: Path = DATA_FILE) -> Network:
    """Carrega a malha do dataset da issue #8, com fallback para a rede minima.

    Enquanto ``backend/data/rede.json`` nao existir, a API sobe com uma malha
    reduzida embutida, o que mantem os endpoints (e o front-end) utilizaveis sem
    bloquear no dataset. Assim que o arquivo aparecer, ele passa a valer sem
    nenhuma outra mudanca de codigo.
    """
    if data_file.exists():
        return _network_from_json(json.loads(data_file.read_text(encoding="utf-8")))
    return _placeholder_network()


def _network_from_json(data: Any) -> Network:
    """Monta a ``Network`` a partir do JSON `{nos: [...], arestas: [...]}`.

    So os campos usados pelo grafo sao lidos; metadados de exibicao (`nome`,
    `lat`, `lon`) ficam a cargo da camada de visualizacao.
    """
    if not isinstance(data, dict):
        raise ValueError("Network dataset must be a JSON object")

    network = Network()
    for no in data.get("nos", ()):
        network.add_node(no["id"])
    for aresta in data.get("arestas", ()):
        network.add_edge(aresta["origem"], aresta["destino"], aresta["peso"])
    return network


def _placeholder_network() -> Network:
    """Malha minima de datacenters, com peso em latencia aproximada (ms).

    Placeholder ate o dataset real (issue #8): topologia pequena, conexa e com
    caminho alternativo entre os extremos, para que derrubar um no ou um cabo
    produza um recalculo visivel de rota.
    """
    network = Network()
    latencias = (
        ("brasilia", "sao-paulo", 15.0),
        ("sao-paulo", "miami", 110.0),
        ("sao-paulo", "lisboa", 180.0),
        ("miami", "lisboa", 90.0),
        ("lisboa", "frankfurt", 35.0),
        ("miami", "los-angeles", 70.0),
        ("los-angeles", "toquio", 105.0),
        ("frankfurt", "toquio", 230.0),
    )
    for origem, destino, _ in latencias:
        network.add_node(origem)
        network.add_node(destino)
    for origem, destino, peso in latencias:
        network.add_edge(origem, destino, peso)
    return network


_network: Network | None = None


def get_network() -> Network:
    """Dependencia do FastAPI: a instancia unica da malha viva do processo.

    A simulacao e stateful por natureza -- derrubar um no precisa valer para a
    proxima requisicao de rota -- entao o estado vive no processo da API. Nos
    testes a dependencia e sobrescrita para que cada caso parta de uma rede
    limpa.
    """
    global _network
    if _network is None:
        _network = load_network()
    return _network
