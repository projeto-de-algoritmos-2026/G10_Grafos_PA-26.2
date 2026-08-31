"""Testes do contrato, procedencia e conexidade da malha mundial."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.dataset import MAX_NODES, MIN_NODES, haversine_km
from backend.state import DATA_FILE, load_dataset, load_network


@pytest.fixture
def raw_dataset() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def write_dataset(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "rede.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_dataset_real_tem_tamanho_fontes_e_pesos_reproduziveis():
    dataset = load_dataset()
    nodes = {node.id: node for node in dataset.nos}

    assert MIN_NODES <= len(dataset.nos) <= MAX_NODES
    assert len(dataset.nos) == 26
    assert len(dataset.arestas) == 30
    assert dataset.metadata.unidade_peso == "km"

    for edge in dataset.arestas:
        origin = nodes[edge.origem]
        destination = nodes[edge.destino]
        expected = round(haversine_km(origin.lat, origin.lon, destination.lat, destination.lon))
        assert edge.peso == pytest.approx(expected, abs=1)
        assert set(edge.fontes) <= dataset.metadata.fontes.keys()


def test_dataset_real_e_conexo_por_busca_independente():
    network = load_network()
    visited: set[str] = set()
    pending = [network.node_ids()[0]]

    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        pending.extend(edge.destination for edge in network.neighbors(node_id))

    assert visited == set(network.node_ids())


def test_metadados_geograficos_e_de_cabo_chegam_ao_dominio():
    network = load_network()
    node = network.get_node("fortaleza")
    edge = next(
        edge
        for origin, edge in network.edges()
        if {origin, edge.destination} == {"fortaleza", "sines"}
    )

    assert node.name == "Fortaleza, Brasil"
    assert node.lat == pytest.approx(-3.7319)
    assert node.lon == pytest.approx(-38.5267)
    assert edge.cable == "EllaLink"
    assert edge.source_ids == ("ellalink",)


def test_json_malformado_e_rejeitado(tmp_path: Path):
    path = tmp_path / "rede.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Invalid JSON"):
        load_dataset(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["nos"].append(deepcopy(data["nos"][0])), "ids must be unique"),
        (
            lambda data: data["arestas"][0].update(destino="nao-existe"),
            "unknown node",
        ),
        (
            lambda data: data["arestas"].append(
                {
                    **deepcopy(data["arestas"][0]),
                    "origem": data["arestas"][0]["destino"],
                    "destino": data["arestas"][0]["origem"],
                }
            ),
            "Duplicate undirected edge",
        ),
        (
            lambda data: data["arestas"][0].update(destino=data["arestas"][0]["origem"]),
            "Self-loop",
        ),
        (
            lambda data: data["arestas"][0].update(fontes=["fonte-inexistente"]),
            "unknown sources",
        ),
        (lambda data: data["arestas"][0].update(peso=1), "Invalid weight"),
        (lambda data: data["nos"][0].update(lat=91), "less than or equal to 90"),
    ],
)
def test_invariantes_invalidas_sao_rejeitadas(
    tmp_path: Path,
    raw_dataset: dict,
    mutation,
    message: str,
):
    mutation(raw_dataset)

    with pytest.raises(RuntimeError, match=message):
        load_dataset(write_dataset(tmp_path, raw_dataset))


def test_grafo_desconexo_e_rejeitado(tmp_path: Path, raw_dataset: dict):
    raw_dataset["arestas"] = [
        edge
        for edge in raw_dataset["arestas"]
        if "las-toninas" not in {edge["origem"], edge["destino"]}
    ]

    with pytest.raises(RuntimeError, match="must be connected"):
        load_dataset(write_dataset(tmp_path, raw_dataset))


def test_quantidade_de_nos_fora_do_limite_e_rejeitada(tmp_path: Path, raw_dataset: dict):
    raw_dataset["nos"] = raw_dataset["nos"][: MIN_NODES - 1]

    with pytest.raises(RuntimeError, match="at least 15"):
        load_dataset(write_dataset(tmp_path, raw_dataset))
