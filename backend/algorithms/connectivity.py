"""Identificacao de pontos de articulacao e pontes na malha de rede."""

from dataclasses import dataclass

from backend.graph import Network


@dataclass(frozen=True, slots=True)
class CriticalityResult:
    """Pontos unicos de falha da rede disponivel no momento da analise."""

    articulation_points: list[str]
    bridges: list[tuple[str, str]]
    components: int


def find_critical_points(network: Network) -> CriticalityResult:
    """Encontra pontos de articulacao e pontes na rede ativa (algoritmo de Tarjan).

    Uma unica DFS numera cada no na ordem de descoberta (``disc``) e mantem, para
    cada no, o menor ``disc`` alcancavel a partir de sua subarvore usando no
    maximo uma aresta de retorno (``low``). Intuitivamente, ``low[v] < disc[u]``
    significa que a subarvore de ``v`` tem um "atalho" para um ancestral de
    ``u``, logo remover ``u`` nao desconecta ``v`` do resto da rede.

    A partir dessa unica passagem:
    - a aresta de arvore ``(u, v)`` e uma **ponte** se ``low[v] > disc[u]``: a
      subarvore de ``v`` nao alcanca ``u`` nem seus ancestrais por outro caminho;
    - ``u`` e um **ponto de articulacao** se ele for a raiz da DFS com dois ou
      mais filhos na arvore, ou se nao for raiz e existir um filho ``v`` com
      ``low[v] >= disc[u]`` (a subarvore de ``v`` nao alcanca acima de ``u``).

    A analise considera apenas nos e arestas ativos (``is_up``), pois
    ``Network.neighbors`` ja filtra o recorte disponivel da malha; uma rede
    particionada e percorrida por componente, sem exigir tratamento especial.

    Complexidade O(V + E): cada no ativo e visitado uma vez e cada aresta ativa
    e examinada uma unica vez a partir de cada extremidade.
    """
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    articulation_points: set[str] = set()
    bridges: list[tuple[str, str]] = []
    components = 0
    counter = 0

    def dfs(node: str, parent: str | None) -> None:
        nonlocal counter
        disc[node] = low[node] = counter
        counter += 1
        children = 0

        for edge in network.neighbors(node):
            neighbor = edge.destination
            if neighbor == parent:
                continue
            if neighbor not in disc:
                children += 1
                dfs(neighbor, node)
                low[node] = min(low[node], low[neighbor])
                if low[neighbor] > disc[node]:
                    bridges.append((node, neighbor))
                if parent is not None and low[neighbor] >= disc[node]:
                    articulation_points.add(node)
            else:
                low[node] = min(low[node], disc[neighbor])

        if parent is None and children > 1:
            articulation_points.add(node)

    for node_id in network.node_ids():
        if network.is_node_up(node_id) and node_id not in disc:
            components += 1
            dfs(node_id, None)

    return CriticalityResult(
        articulation_points=sorted(articulation_points),
        bridges=sorted(tuple(sorted(bridge)) for bridge in bridges),
        components=components,
    )
