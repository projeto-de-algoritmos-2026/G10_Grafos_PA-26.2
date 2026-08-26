import pytest

from backend.graph import Network


@pytest.fixture
def network() -> Network:
    """Rede compartilhada pelos testes de caminho minimo.

    Dijkstra e Bellman-Ford precisam ser exercitados sobre exatamente o mesmo
    grafo para que os resultados possam ser comparados diretamente.
    """
    graph = Network()
    for node_id in ("A", "B", "C", "D", "isolated"):
        graph.add_node(node_id)
    graph.add_edge("A", "B", 1)
    graph.add_edge("B", "D", 2)
    graph.add_edge("A", "C", 4)
    graph.add_edge("B", "C", 1)
    graph.add_edge("C", "D", 5)
    return graph
