"""Compara nos expandidos por Dijkstra x A* sobre a malha mundial real.

Mede, para todo par ordenado (origem, destino) dos 26 nos do dataset real
(``backend/data/rede.json``), quantos nos cada algoritmo expandiu ate encontrar
o caminho minimo, e confirma que os dois concordam no custo. Salva os dados
brutos em ``docs/benchmark/nos_expandidos.csv`` e imprime um resumo em Markdown
para colar no relatorio.

Uso:
    uv run python scripts/comparar_dijkstra_a_star.py
"""

import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.algorithms import a_star, dijkstra  # noqa: E402
from backend.state import load_network  # noqa: E402

SAIDA = Path(__file__).resolve().parents[1] / "docs" / "benchmark" / "nos_expandidos.csv"

# Pares com landing points em continentes opostos do Atlantico, citados no
# criterio de aceite da issue #30.
PARES_TRANSATLANTICOS = (
    ("virginia-beach", "sines"),
    ("los-angeles", "carcavelos"),
    ("virginia-beach", "bilbao"),
)


def main() -> None:
    network = load_network()
    node_ids = network.node_ids()

    linhas = []
    for origin in node_ids:
        for destination in node_ids:
            if origin == destination:
                continue
            dijkstra_result = dijkstra(network, origin, destination)
            a_star_result = a_star(network, origin, destination)
            assert a_star_result.cost == dijkstra_result.cost, (
                f"Custos divergentes em {origin}->{destination}: "
                f"dijkstra={dijkstra_result.cost} a_star={a_star_result.cost}"
            )
            linhas.append(
                {
                    "origem": origin,
                    "destino": destination,
                    "nos_expandidos_dijkstra": dijkstra_result.nodes_expanded,
                    "nos_expandidos_a_star": a_star_result.nodes_expanded,
                }
            )

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(linhas)

    media_dijkstra = statistics.mean(linha["nos_expandidos_dijkstra"] for linha in linhas)
    media_a_star = statistics.mean(linha["nos_expandidos_a_star"] for linha in linhas)
    reducao_pct = (media_dijkstra - media_a_star) / media_dijkstra * 100

    print(f"Pares avaliados: {len(linhas)} (todos os {len(node_ids)} nos, ordenados)")
    print(f"Media de nos expandidos - Dijkstra: {media_dijkstra:.2f}")
    print(f"Media de nos expandidos - A*:       {media_a_star:.2f}")
    print(f"Reducao media de A* sobre Dijkstra:  {reducao_pct:.1f}%")
    print(f"CSV salvo em {SAIDA.relative_to(Path.cwd())}")
    print()
    print("| Origem | Destino | Nós expandidos (Dijkstra) | Nós expandidos (A*) |")
    print("|---|---|---:|---:|")
    for origin, destination in PARES_TRANSATLANTICOS:
        dijkstra_result = dijkstra(network, origin, destination)
        a_star_result = a_star(network, origin, destination)
        print(
            f"| {origin} | {destination} | {dijkstra_result.nodes_expanded} "
            f"| {a_star_result.nodes_expanded} |"
        )


if __name__ == "__main__":
    main()
