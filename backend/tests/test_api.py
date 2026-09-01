"""Testes de integracao dos endpoints HTTP da simulacao."""

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
    app.state.rota_atual = None
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.state.rota_atual = None


def test_status_ok(client: TestClient):
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_raiz_serve_a_interface_do_simulador(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Simulador de Colapso de Internet" in response.text
    assert 'id="api-error"' in response.text


@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/app.js", "text/javascript"), ("/style.css", "text/css")],
)
def test_frontend_serve_assets_estaticos(client: TestClient, path: str, content_type: str):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_grafo_publica_topologia_completa_e_ativa(client: TestClient):
    corpo = client.get("/grafo").json()

    assert [no["id"] for no in corpo["nos"]] == ["A", "B", "C", "D", "isolated"]
    assert all(no["ativo"] for no in corpo["nos"])
    assert all({"nome", "lat", "lon"} <= no.keys() for no in corpo["nos"])
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
    assert all({"cabo", "fontes"} <= aresta.keys() for aresta in corpo["arestas"])
    assert corpo["rota_atual"] is None


def test_grafo_publica_a_ultima_rota_calculada(client: TestClient):
    client.post("/rota", json={"origem": "A", "destino": "D", "algoritmo": "dijkstra"})

    rota_atual = client.get("/grafo").json()["rota_atual"]

    assert rota_atual == {
        "origem": "A",
        "destino": "D",
        "caminho": ["A", "B", "D"],
        "custo": 3.0,
        "encontrada": True,
        "algoritmo": "dijkstra",
    }


def test_grafo_preserva_extremos_quando_rota_nao_existe(client: TestClient):
    client.post("/rota", json={"origem": "A", "destino": "isolated"})

    rota_atual = client.get("/grafo").json()["rota_atual"]

    assert rota_atual["origem"] == "A"
    assert rota_atual["destino"] == "isolated"
    assert rota_atual["caminho"] == []
    assert rota_atual["encontrada"] is False


def test_mudanca_na_topologia_invalida_rota_atual(client: TestClient):
    client.post("/rota", json={"origem": "A", "destino": "D"})

    client.post("/nos/B/derrubar")

    assert client.get("/grafo").json()["rota_atual"] is None


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
    assert response.json() == {
        "id": "B",
        "nome": "B",
        "lat": 0.0,
        "lon": 0.0,
        "ativo": False,
    }

    grafo = client.get("/grafo").json()
    assert [no["ativo"] for no in grafo["nos"] if no["id"] == "B"] == [False]

    rota = client.post("/rota", json={"origem": "A", "destino": "D"}).json()
    assert rota["caminho"] == ["A", "C", "D"]
    assert rota["custo"] == 9.0


def test_restaurar_no_recupera_a_rota_original(client: TestClient):
    client.post("/nos/B/derrubar")

    response = client.post("/nos/B/restaurar")

    assert response.status_code == 200
    assert response.json() == {
        "id": "B",
        "nome": "B",
        "lat": 0.0,
        "lon": 0.0,
        "ativo": True,
    }
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
    assert response.json() == {
        "origem": "B",
        "destino": "D",
        "peso": 2.0,
        "cabo": "synthetic",
        "fontes": [],
        "ativo": False,
    }

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
    assert {"GrafoState", "RotaAtual", "RotaRequest", "RotaResult", "ArestaRequest"} <= set(
        schema["components"]["schemas"]
    )


def test_dataset_real_carrega_metadados_e_permite_rota_global():
    network = load_network()

    assert len(network.node_ids()) == 26
    assert len(network.edges()) == 30
    assert network.get_node("chiba").name.endswith("Japão")

    response = TestClient(app)
    app.dependency_overrides[get_network] = lambda: network
    try:
        rota = response.post("/rota", json={"origem": "praia-grande", "destino": "chiba"}).json()
    finally:
        app.dependency_overrides.clear()

    assert rota["encontrada"] is True
    assert rota["caminho"][0] == "praia-grande"
    assert rota["caminho"][-1] == "chiba"


def test_dataset_ausente_impede_inicializacao():
    with pytest.raises(RuntimeError, match="not found"):
        load_network(Path("caminho/inexistente/rede.json"))


def test_lifespan_carrega_dataset_antes_da_primeira_requisicao():
    with TestClient(app) as startup_client:
        response = startup_client.get("/grafo")

    assert response.status_code == 200
    assert len(response.json()["nos"]) == 26
