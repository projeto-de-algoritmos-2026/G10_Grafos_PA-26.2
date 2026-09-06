"""Testes de integracao dos endpoints HTTP da simulacao."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.graph import Network
from backend.main import app
from backend.state import SessionStore, get_network, load_network


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
    [
        ("/app.js", "text/javascript"),
        ("/map-geometry.js", "text/javascript"),
        ("/style.css", "text/css"),
        ("/vendor/leaflet/leaflet.js", "text/javascript"),
        ("/vendor/leaflet/leaflet.css", "text/css"),
    ],
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


def test_criticidade_da_rede_sem_ponto_unico_de_falha(client: TestClient):
    """A rede de teste e formada por dois triangulos compartilhando o cabo B-C."""
    resposta = client.get("/analise/criticidade")

    assert resposta.status_code == 200
    assert resposta.json() == {"articulacoes": [], "pontes": [], "componentes": 2}


def test_criticidade_reflete_falhas_ativas(client: TestClient):
    """Derrubar B colapsa os dois triangulos em um caminho A-C-D: C fica critico."""
    client.post("/nos/B/derrubar")

    resposta = client.get("/analise/criticidade")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["articulacoes"] == ["C"]
    assert {(ponte["origem"], ponte["destino"]) for ponte in corpo["pontes"]} == {
        ("A", "C"),
        ("C", "D"),
    }
    assert corpo["componentes"] == 2


def test_cascata_devolve_ponto_inicial_e_um_por_remocao(client: TestClient):
    resposta = client.post(
        "/analise/cascata",
        json={"estrategia": "aleatoria", "passos": 3, "semente": 2026},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estrategia"] == "aleatoria"
    assert corpo["semente"] == 2026
    assert corpo["total_inicial"] == 5
    assert [ponto["passo"] for ponto in corpo["pontos"]] == [0, 1, 2, 3]
    assert corpo["pontos"][0]["no_removido"] is None
    assert {
        "nos_ativos",
        "fracao_removida",
        "maior_componente_fracao",
        "pares_alcancaveis_fracao",
        "custo_medio_rotas",
    } <= corpo["pontos"][0].keys()


def test_cascata_com_mesma_semente_repete_a_sequencia(client: TestClient):
    pedido = {"estrategia": "aleatoria", "passos": 5, "semente": 99}

    primeira = client.post("/analise/cascata", json=pedido).json()
    segunda = client.post("/analise/cascata", json=pedido).json()

    assert [ponto["no_removido"] for ponto in primeira["pontos"]] == [
        ponto["no_removido"] for ponto in segunda["pontos"]
    ]


def test_cascata_nao_altera_estado_global_da_api(client: TestClient):
    client.post("/nos/B/derrubar")
    client.post("/arestas/derrubar", json={"origem": "A", "destino": "C"})
    antes = client.get("/grafo").json()

    resposta = client.post(
        "/analise/cascata",
        json={"estrategia": "articulacao", "passos": 10, "semente": 42},
    )

    assert resposta.status_code == 200
    assert client.get("/grafo").json() == antes


@pytest.mark.parametrize(
    "pedido",
    [
        {"estrategia": "inexistente", "passos": 1},
        {"estrategia": "grau", "passos": -1},
        {"estrategia": "grau", "passos": 10_001},
    ],
)
def test_cascata_rejeita_parametros_invalidos(client: TestClient, pedido: dict[str, object]):
    assert client.post("/analise/cascata", json=pedido).status_code == 422


def test_corte_minimo_devolve_dois_cabos_para_dois_caminhos_disjuntos(
    client: TestClient,
):
    resposta = client.post("/analise/corte-minimo", json={"origem": "A", "destino": "D"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["capacidade"] == 2
    assert len(corpo["arestas"]) == 2


def test_corte_minimo_ja_desconectado_e_zero(client: TestClient):
    resposta = client.post("/analise/corte-minimo", json={"origem": "A", "destino": "isolated"})

    assert resposta.status_code == 200
    assert resposta.json() == {"capacidade": 0, "arestas": []}


def test_corte_minimo_rejeita_extremos_iguais(client: TestClient):
    resposta = client.post("/analise/corte-minimo", json={"origem": "A", "destino": "A"})

    assert resposta.status_code == 422


def test_derrubar_corte_devolvido_particiona_rede_ponta_a_ponta(client: TestClient):
    corte = client.post("/analise/corte-minimo", json={"origem": "A", "destino": "D"}).json()

    for aresta in corte["arestas"]:
        resposta = client.post("/arestas/derrubar", json=aresta)
        assert resposta.status_code == 200

    rota = client.post("/rota", json={"origem": "A", "destino": "D"})
    assert rota.status_code == 200
    assert rota.json()["encontrada"] is False


def test_corte_minimo_respeita_cabo_ja_fora_do_ar(client: TestClient):
    client.post("/arestas/derrubar", json={"origem": "A", "destino": "B"})

    resposta = client.post("/analise/corte-minimo", json={"origem": "A", "destino": "D"})

    assert resposta.status_code == 200
    assert resposta.json()["capacidade"] == 1


def test_corte_minimo_respeita_no_ja_fora_do_ar(client: TestClient):
    client.post("/nos/B/derrubar")

    resposta = client.post("/analise/corte-minimo", json={"origem": "A", "destino": "D"})

    assert resposta.status_code == 200
    assert resposta.json()["capacidade"] == 1


def test_grafo_publica_a_ultima_rota_calculada(client: TestClient):
    client.post("/rota", json={"origem": "A", "destino": "D", "algoritmo": "dijkstra"})

    rota_atual = client.get("/grafo").json()["rota_atual"]

    assert rota_atual["origem"] == "A"
    assert rota_atual["destino"] == "D"
    assert rota_atual["caminho"] == ["A", "B", "D"]
    assert rota_atual["custo"] == 3.0
    assert rota_atual["encontrada"] is True
    assert rota_atual["algoritmo"] == "dijkstra"
    assert rota_atual["nos_expandidos"] > 0
    assert rota_atual["arestas_relaxadas"] > 0


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


@pytest.mark.parametrize("algoritmo", ["dijkstra", "bellman_ford", "a_star"])
def test_rota_devolve_o_mesmo_caminho_minimo_nos_dois_algoritmos(
    client: TestClient, algoritmo: str
):
    response = client.post("/rota", json={"origem": "A", "destino": "D", "algoritmo": algoritmo})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["caminho"] == ["A", "B", "D"]
    assert corpo["custo"] == 3.0
    assert corpo["encontrada"] is True
    assert corpo["algoritmo"] == algoritmo
    assert corpo["nos_expandidos"] > 0
    assert corpo["arestas_relaxadas"] > 0


def test_rota_usa_dijkstra_por_padrao(client: TestClient):
    corpo = client.post("/rota", json={"origem": "A", "destino": "D"}).json()

    assert corpo["algoritmo"] == "dijkstra"


def test_rota_com_origem_igual_ao_destino_nao_e_erro(client: TestClient):
    response = client.post("/rota", json={"origem": "A", "destino": "A"})

    assert response.status_code == 200
    assert response.json()["caminho"] == ["A"]
    assert response.json()["custo"] == 0.0


def test_resetar_simulacao_devolve_grafo_integro_e_limpa_rota(client: TestClient):
    client.post("/rota", json={"origem": "A", "destino": "D"})
    client.post("/nos/B/derrubar")
    client.post("/arestas/derrubar", json={"origem": "A", "destino": "C"})

    response = client.post("/simulacao/resetar")

    assert response.status_code == 200
    corpo = response.json()
    assert all(no["ativo"] for no in corpo["nos"])
    assert all(aresta["ativo"] for aresta in corpo["arestas"])
    assert corpo["rota_atual"] is None


def test_aplicar_falhas_em_lote_e_atomo_em_identificador_invalido(client: TestClient):
    response = client.post(
        "/simulacao/falhas",
        json={"nos": ["B"], "arestas": [{"origem": "A", "destino": "nao-existe"}]},
    )

    assert response.status_code == 404
    assert all(no["ativo"] for no in client.get("/grafo").json()["nos"])


def test_rota_passos_devolve_traco_e_mesmo_resultado_da_rota(client: TestClient):
    response = client.post("/rota/passos", json={"origem": "A", "destino": "D"})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["rota"]["caminho"] == ["A", "B", "D"]
    assert corpo["passos"]
    assert corpo["passos"][-1]["tipo"] == "finaliza"


def test_clientes_tem_estado_de_falhas_isolado():
    """Uma falha e uma rota de um cliente nao afetam outro cliente."""
    app.state.network = load_network()
    app.state.sessions = SessionStore()
    cliente_a = TestClient(app)
    cliente_b = TestClient(app)
    try:
        cliente_a.get("/grafo")
        cliente_b.get("/grafo")

        resposta = cliente_a.post("/nos/virginia-beach/derrubar")

        assert resposta.status_code == 200
        grafo_a = cliente_a.get("/grafo").json()
        grafo_b = cliente_b.get("/grafo").json()
        assert next(no for no in grafo_a["nos"] if no["id"] == "virginia-beach")["ativo"] is False
        assert next(no for no in grafo_b["nos"] if no["id"] == "virginia-beach")["ativo"] is True

        cliente_a.post("/rota", json={"origem": "sines", "destino": "bilbao"})
        assert cliente_a.get("/grafo").json()["rota_atual"] is not None
        assert cliente_b.get("/grafo").json()["rota_atual"] is None
    finally:
        cliente_a.close()
        cliente_b.close()


def test_sessao_expirada_recomeca_com_malha_integra():
    """Uma sessao inativa e removida e o cookie antigo inicia uma sessao limpa."""
    app.state.network = load_network()
    app.state.sessions = SessionStore()
    with TestClient(app) as client:
        client.get("/grafo")
        client.post("/nos/virginia-beach/derrubar")
        app.state.sessions.ttl_seconds = 0

        grafo = client.get("/grafo").json()

        assert next(no for no in grafo["nos"] if no["id"] == "virginia-beach")["ativo"] is True
        assert grafo["rota_atual"] is None
        app.state.sessions.ttl_seconds = 30 * 60


def test_rota_inexistente_devolve_custo_nulo_e_nao_erro(client: TestClient):
    """Rede particionada e resultado valido do dominio, nao falha de requisicao.

    ``custo`` vira ``null`` porque o dominio usa ``math.inf``, que nao tem
    representacao em JSON.
    """
    response = client.post("/rota", json={"origem": "A", "destino": "isolated"})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["caminho"] == []
    assert corpo["custo"] is None
    assert corpo["encontrada"] is False
    assert corpo["algoritmo"] == "dijkstra"


def test_rota_com_no_inexistente_devolve_404(client: TestClient):
    response = client.post("/rota", json={"origem": "A", "destino": "Z"})

    assert response.status_code == 404
    assert "Z" in response.json()["detail"]


def test_rota_com_algoritmo_desconhecido_devolve_422(client: TestClient):
    response = client.post(
        "/rota", json={"origem": "A", "destino": "D", "algoritmo": "floyd_warshall"}
    )

    assert response.status_code == 422


def test_rotas_k_igual_a_um_repete_o_resultado_de_rota(client: TestClient):
    rota = client.post("/rota", json={"origem": "A", "destino": "D"}).json()

    rotas = client.post("/rotas", json={"origem": "A", "destino": "D", "k": 1}).json()

    assert rotas["rotas"] == [
        {
            "caminho": rota["caminho"],
            "custo": rota["custo"],
            "encontrada": rota["encontrada"],
            "algoritmo": "dijkstra",
            "nos_expandidos": rota["nos_expandidos"],
            "arestas_relaxadas": rota["arestas_relaxadas"],
        }
    ]


def test_rotas_devolve_lista_ordenada_por_custo_com_redundancia(client: TestClient):
    """A rede de teste tem exatamente 4 caminhos simples de A a D: 3, 7, 7 e 9."""
    response = client.post("/rotas", json={"origem": "A", "destino": "D", "k": 4})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["origem"] == "A"
    assert corpo["destino"] == "D"
    assert corpo["encontrada"] is True
    assert [rota["custo"] for rota in corpo["rotas"]] == [3.0, 7.0, 7.0, 9.0]
    assert [rota["caminho"] for rota in corpo["rotas"]] == [
        ["A", "B", "D"],
        ["A", "B", "C", "D"],
        ["A", "C", "B", "D"],
        ["A", "C", "D"],
    ]
    assert corpo["redundancia_percentual"] == pytest.approx((7.0 - 3.0) / 3.0 * 100)


def test_rotas_com_menos_caminhos_do_que_k_devolve_os_que_existem(client: TestClient):
    response = client.post("/rotas", json={"origem": "A", "destino": "D", "k": 10})

    assert response.status_code == 200
    assert len(response.json()["rotas"]) == 4


def test_rotas_rede_particionada_devolve_lista_vazia_com_200(client: TestClient):
    response = client.post("/rotas", json={"origem": "A", "destino": "isolated", "k": 3})

    assert response.status_code == 200
    assert response.json() == {
        "origem": "A",
        "destino": "isolated",
        "encontrada": False,
        "rotas": [],
        "redundancia_percentual": None,
    }


def test_rotas_com_uma_unica_rota_nao_calcula_redundancia(client: TestClient):
    response = client.post("/rotas", json={"origem": "A", "destino": "A", "k": 5})

    assert response.status_code == 200
    corpo = response.json()
    assert len(corpo["rotas"]) == 1
    assert corpo["redundancia_percentual"] is None


@pytest.mark.parametrize("k", [0, 11])
def test_rotas_com_k_fora_do_intervalo_devolve_422(client: TestClient, k: int):
    response = client.post("/rotas", json={"origem": "A", "destino": "D", "k": k})

    assert response.status_code == 422


def test_rotas_usa_k_igual_a_tres_por_padrao(client: TestClient):
    response = client.post("/rotas", json={"origem": "A", "destino": "D"})

    assert response.status_code == 200
    assert len(response.json()["rotas"]) == 3


def test_rotas_com_no_inexistente_devolve_404(client: TestClient):
    response = client.post("/rotas", json={"origem": "A", "destino": "Z"})

    assert response.status_code == 404
    assert "Z" in response.json()["detail"]


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
        "/analise/criticidade",
        "/analise/cascata",
        "/analise/corte-minimo",
        "/rota",
        "/rota/passos",
        "/rotas",
        "/simulacao/resetar",
        "/simulacao/falhas",
        "/nos/{no_id}/derrubar",
        "/nos/{no_id}/restaurar",
        "/arestas/derrubar",
        "/arestas/restaurar",
    }
    assert {
        "GrafoState",
        "RotaAtual",
        "RotaRequest",
        "RotaResult",
        "RotasRequest",
        "RotasResult",
        "ArestaRequest",
        "CriticidadeResult",
        "CascataRequest",
        "CascataPonto",
        "CascataResult",
        "CorteMinimoRequest",
        "CorteMinimoResult",
    } <= set(schema["components"]["schemas"])


def test_dataset_real_carrega_metadados_e_permite_rota_global():
    network = load_network()

    assert len(network.node_ids()) == 100
    assert len(network.edges()) == 180
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
    assert len(response.json()["nos"]) == 100
