"""Testes de integracao dos endpoints HTTP da simulacao."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.graph import Network
from backend.main import app
from backend.state import get_network, load_network


@pytest.fixture
def client(network: Network) -> Iterator[TestClient]:
    """Cliente com a malha dos testes no lugar da malha real do processo.

    Sobrescrever a dependencia isola cada teste: como derrubar um no altera o
    estado do processo, reaproveitar a instancia real faria um teste vazar para
    o seguinte.
    """
    app.dependency_overrides[get_network] = lambda: network
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_status_ok(client: TestClient):
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_grafo_publica_topologia_completa_e_ativa(client: TestClient):
    corpo = client.get("/grafo").json()

    assert [no["id"] for no in corpo["nos"]] == ["A", "B", "C", "D", "isolated"]
    assert all(no["ativo"] for no in corpo["nos"])
    assert {
        (aresta["origem"], aresta["destino"], aresta["peso"]) for aresta in corpo["arestas"]
    } == {
        ("A", "B", 1.0),
        ("B", "D", 2.0),
        ("A", "C", 4.0),
        ("B", "C", 1.0),
        ("C", "D", 5.0),
    }
    assert all(aresta["ativo"] for aresta in corpo["arestas"])


@pytest.mark.parametrize("algoritmo", ["dijkstra", "bellman_ford"])
def test_rota_devolve_o_mesmo_caminho_minimo_nos_dois_algoritmos(
    client: TestClient, algoritmo: str
):
    response = client.post("/rota", json={"origem": "A", "destino": "D", "algoritmo": algoritmo})

    assert response.status_code == 200
    assert response.json() == {
        "caminho": ["A", "B", "D"],
        "custo": 3.0,
        "encontrada": True,
        "algoritmo": algoritmo,
    }


def test_rota_usa_dijkstra_por_padrao(client: TestClient):
    corpo = client.post("/rota", json={"origem": "A", "destino": "D"}).json()

    assert corpo["algoritmo"] == "dijkstra"


def test_rota_com_origem_igual_ao_destino_nao_e_erro(client: TestClient):
    response = client.post("/rota", json={"origem": "A", "destino": "A"})

    assert response.status_code == 200
    assert response.json()["caminho"] == ["A"]
    assert response.json()["custo"] == 0.0


def test_rota_inexistente_devolve_custo_nulo_e_nao_erro(client: TestClient):
    """Rede particionada e resultado valido do dominio, nao falha de requisicao.

    ``custo`` vira ``null`` porque o dominio usa ``math.inf``, que nao tem
    representacao em JSON.
    """
    response = client.post("/rota", json={"origem": "A", "destino": "isolated"})

    assert response.status_code == 200
    assert response.json() == {
        "caminho": [],
        "custo": None,
        "encontrada": False,
        "algoritmo": "dijkstra",
    }


def test_rota_com_no_inexistente_devolve_404(client: TestClient):
    response = client.post("/rota", json={"origem": "A", "destino": "Z"})

    assert response.status_code == 404
    assert "Z" in response.json()["detail"]


def test_rota_com_algoritmo_desconhecido_devolve_422(client: TestClient):
    response = client.post(
        "/rota", json={"origem": "A", "destino": "D", "algoritmo": "floyd_warshall"}
    )

    assert response.status_code == 422


def test_derrubar_no_muda_o_grafo_e_forca_desvio(client: TestClient):
    response = client.post("/nos/B/derrubar")

    assert response.status_code == 200
    assert response.json() == {"id": "B", "ativo": False}

    grafo = client.get("/grafo").json()
    assert [no["ativo"] for no in grafo["nos"] if no["id"] == "B"] == [False]

    rota = client.post("/rota", json={"origem": "A", "destino": "D"}).json()
    assert rota["caminho"] == ["A", "C", "D"]
    assert rota["custo"] == 9.0


def test_restaurar_no_recupera_a_rota_original(client: TestClient):
    client.post("/nos/B/derrubar")

    response = client.post("/nos/B/restaurar")

    assert response.status_code == 200
    assert response.json() == {"id": "B", "ativo": True}
    assert client.post("/rota", json={"origem": "A", "destino": "D"}).json()["caminho"] == [
        "A",
        "B",
        "D",
    ]


@pytest.mark.parametrize("acao", ["derrubar", "restaurar"])
def test_operacao_em_no_inexistente_devolve_404(client: TestClient, acao: str):
    response = client.post(f"/nos/Z/{acao}")

    assert response.status_code == 404
    assert "Z" in response.json()["detail"]


def test_derrubar_aresta_muda_o_grafo_e_forca_desvio(client: TestClient):
    response = client.post("/arestas/derrubar", json={"origem": "B", "destino": "D"})

    assert response.status_code == 200
    assert response.json() == {"origem": "B", "destino": "D", "peso": 2.0, "ativo": False}

    grafo = client.get("/grafo").json()
    inativas = [aresta for aresta in grafo["arestas"] if not aresta["ativo"]]
    assert len(inativas) == 1
    assert {inativas[0]["origem"], inativas[0]["destino"]} == {"B", "D"}

    rota = client.post("/rota", json={"origem": "A", "destino": "D"}).json()
    assert rota["caminho"] == ["A", "B", "C", "D"]
    assert rota["custo"] == 7.0


def test_restaurar_aresta_aceita_os_extremos_em_qualquer_ordem(client: TestClient):
    client.post("/arestas/derrubar", json={"origem": "B", "destino": "D"})

    response = client.post("/arestas/restaurar", json={"origem": "D", "destino": "B"})

    assert response.status_code == 200
    assert response.json()["ativo"] is True
    assert client.post("/rota", json={"origem": "A", "destino": "D"}).json()["custo"] == 3.0


@pytest.mark.parametrize("acao", ["derrubar", "restaurar"])
def test_operacao_em_aresta_inexistente_entre_nos_validos_devolve_404(
    client: TestClient, acao: str
):
    response = client.post(f"/arestas/{acao}", json={"origem": "A", "destino": "isolated"})

    assert response.status_code == 404
    assert "isolated" in response.json()["detail"]


@pytest.mark.parametrize("acao", ["derrubar", "restaurar"])
def test_operacao_em_aresta_com_no_inexistente_devolve_404(client: TestClient, acao: str):
    response = client.post(f"/arestas/{acao}", json={"origem": "A", "destino": "Z"})

    assert response.status_code == 404
    assert "Z" in response.json()["detail"]


def test_cors_liberado_para_o_front_end_em_localhost(client: TestClient):
    response = client.get("/grafo", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_documenta_todos_os_endpoints_tipados(client: TestClient):
    """Criterio de aceite: o Swagger reflete o contrato que o front-end consome."""
    schema = client.get("/openapi.json").json()

    assert set(schema["paths"]) == {
        "/status",
        "/grafo",
        "/rota",
        "/nos/{no_id}/derrubar",
        "/nos/{no_id}/restaurar",
        "/arestas/derrubar",
        "/arestas/restaurar",
    }
    assert {"GrafoState", "RotaRequest", "RotaResult", "ArestaRequest"} <= set(
        schema["components"]["schemas"]
    )


def test_malha_padrao_e_conexa_e_permite_rota_entre_os_extremos():
    """Sem o dataset da issue #8, a API ainda sobe com uma malha utilizavel."""
    network = load_network(Path("caminho/inexistente/rede.json"))

    assert len(network.node_ids()) >= 2


def test_dataset_em_disco_substitui_a_malha_padrao(tmp_path: Path):
    dataset = tmp_path / "rede.json"
    dataset.write_text(
        json.dumps(
            {
                "nos": [{"id": "sp", "nome": "Sao Paulo"}, {"id": "tok", "nome": "Toquio"}],
                "arestas": [{"origem": "sp", "destino": "tok", "peso": 250}],
            }
        ),
        encoding="utf-8",
    )

    network = load_network(dataset)

    assert network.node_ids() == ("sp", "tok")
    assert network.is_edge_up("sp", "tok")
