"""Benchmark empirico de Dijkstra x Bellman-Ford em grafos sinteticos.

Gera grafos de tamanho crescente, mede o tempo real de cada algoritmo sobre
exatamente os mesmos grafos e salva os dados brutos (CSV), o grafico e os
metadados de execucao em ``docs/benchmark/``.

Uso:
    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --tamanhos 10 50 100 --repeticoes 5
"""

import argparse
import csv
import json
import os
import platform
import random
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# Executado como script solto (`python scripts/benchmark.py`), o sys.path comeca em
# scripts/ e o pacote backend nao seria encontrado.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.algorithms import RouteResult, bellman_ford, dijkstra  # noqa: E402
from backend.graph import Network  # noqa: E402

SAIDA_PADRAO = Path(__file__).resolve().parents[1] / "docs" / "benchmark"
TAMANHOS_PADRAO = (10, 50, 100, 500, 1000)
PESO_MINIMO, PESO_MAXIMO = 1.0, 100.0

type Algoritmo = Callable[[Network, str, str], RouteResult]

ALGORITMOS: dict[str, Algoritmo] = {"dijkstra": dijkstra, "bellman-ford": bellman_ford}


@dataclass(frozen=True, slots=True)
class Medicao:
    """Uma execucao cronometrada de um algoritmo sobre um grafo."""

    topologia: str
    tamanho: int
    arestas: int
    algoritmo: str
    amostra: int
    repeticao: int
    tempo_s: float
    custo: float
    encontrada: bool


def gerar_aleatorio(
    tamanho: int, grau_medio: float, rng: random.Random
) -> tuple[Network, str, str]:
    """Grafo esparso aleatorio e conexo, com origem e destino sorteados.

    A conexidade e garantida por construcao: primeiro uma arvore geradora ligando
    cada no novo a um no ja presente, depois arestas extras ate atingir o grau
    medio pedido. Sem isso boa parte das medicoes cairia em componente
    desconexa e mediria apenas a deteccao de "sem rota", nao a busca.
    """
    network = Network()
    ids = [f"n{indice}" for indice in range(tamanho)]
    for node_id in ids:
        network.add_node(node_id)

    for indice in range(1, tamanho):
        network.add_edge(ids[indice], ids[rng.randrange(indice)], _peso(rng))

    extras = max(0, round(tamanho * grau_medio / 2) - (tamanho - 1))
    tentativas = 0
    adicionadas = 0
    # O sorteio pode repetir um par ja ligado; o limite evita laco infinito
    # quando o grau pedido se aproxima do grafo completo.
    while adicionadas < extras and tentativas < extras * 20:
        tentativas += 1
        origem, destino = rng.sample(ids, 2)
        try:
            network.add_edge(origem, destino, _peso(rng))
        except ValueError:
            continue
        adicionadas += 1

    origem, destino = rng.sample(ids, 2) if tamanho > 1 else (ids[0], ids[0])
    return network, origem, destino


def gerar_caminho(tamanho: int, _grau_medio: float, rng: random.Random) -> tuple[Network, str, str]:
    """Grafo em linha reta -- o pior caso do Bellman-Ford.

    Os nos sao inseridos na ordem inversa do caminho de proposito: o Bellman-Ford
    relaxa as arestas na ordem de insercao, entao cada rodada avanca um unico
    salto e o algoritmo so converge apos V-1 rodadas. E o unico cenario aqui em
    que o custo teorico O(V*E) aparece inteiro; no grafo aleatorio a saida
    antecipada por convergencia esconde esse termo.
    """
    network = Network()
    ids = [f"n{indice}" for indice in range(tamanho)]
    for node_id in reversed(ids):
        network.add_node(node_id)
    for indice in range(tamanho - 1):
        network.add_edge(ids[indice], ids[indice + 1], _peso(rng))
    return network, ids[0], ids[-1]


TOPOLOGIAS: dict[str, Callable[[int, float, random.Random], tuple[Network, str, str]]] = {
    "aleatoria": gerar_aleatorio,
    "caminho": gerar_caminho,
}


def _peso(rng: random.Random) -> float:
    return rng.uniform(PESO_MINIMO, PESO_MAXIMO)


def medir(
    topologias: Sequence[str],
    tamanhos: Sequence[int],
    grau_medio: float,
    amostras: int,
    repeticoes: int,
    seed: int,
) -> list[Medicao]:
    """Cronometra os dois algoritmos sobre os mesmos grafos.

    Varios grafos por tamanho diluem o efeito da topologia sorteada; varias
    repeticoes por grafo diluem o ruido de agendamento do sistema operacional.
    """
    medicoes: list[Medicao] = []
    for topologia in topologias:
        gerar = TOPOLOGIAS[topologia]
        for tamanho in tamanhos:
            for amostra in range(amostras):
                # Semente derivada: cada grafo e reproduzivel de forma independente.
                rng = random.Random((seed, topologia, tamanho, amostra).__hash__())
                network, origem, destino = gerar(tamanho, grau_medio, rng)
                arestas = len(network.edges())
                for nome, algoritmo in ALGORITMOS.items():
                    for repeticao in range(repeticoes):
                        inicio = time.perf_counter()
                        resultado = algoritmo(network, origem, destino)
                        decorrido = time.perf_counter() - inicio
                        medicoes.append(
                            Medicao(
                                topologia=topologia,
                                tamanho=tamanho,
                                arestas=arestas,
                                algoritmo=nome,
                                amostra=amostra,
                                repeticao=repeticao,
                                tempo_s=decorrido,
                                custo=resultado.cost,
                                encontrada=resultado.found,
                            )
                        )
            print(f"  {topologia} V={tamanho}: ok", flush=True)
    return medicoes


def escrever_csv(medicoes: Sequence[Medicao], destino: Path) -> None:
    """Salva os dados brutos, sem agregacao, para permitir reanalise."""
    campos = list(asdict(medicoes[0]))
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(asdict(medicao) for medicao in medicoes)


def gerar_grafico(medicoes: Sequence[Medicao], destino: Path, metadados: dict[str, object]) -> None:
    """Plota tempo medio x tamanho do grafo, um painel por topologia.

    Escala log-log: a comparacao aqui e de taxa de crescimento, e nela uma
    curva polinomial vira reta com inclinacao igual ao expoente.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    topologias = sorted({medicao.topologia for medicao in medicoes})
    figura, eixos = plt.subplots(
        1, len(topologias), figsize=(6 * len(topologias), 4.5), squeeze=False
    )

    for eixo, topologia in zip(eixos[0], topologias, strict=True):
        for nome in ALGORITMOS:
            pontos = _agregar(medicoes, topologia, nome)
            tamanhos = sorted(pontos)
            medias = [pontos[tamanho][0] for tamanho in tamanhos]
            minimos = [pontos[tamanho][1] for tamanho in tamanhos]
            maximos = [pontos[tamanho][2] for tamanho in tamanhos]
            eixo.plot(tamanhos, medias, marker="o", label=nome)
            eixo.fill_between(tamanhos, minimos, maximos, alpha=0.2)
        eixo.set(
            xscale="log",
            yscale="log",
            xlabel="numero de nos (V)",
            ylabel="tempo de execucao (s)",
            title=f"topologia: {topologia}",
        )
        eixo.grid(True, which="both", linewidth=0.3)
        eixo.legend()

    figura.suptitle("Dijkstra x Bellman-Ford - tempo por tamanho do grafo")
    figura.text(
        0.5,
        0.005,
        f"{metadados['timestamp_utc']} | {metadados['cpu']} | Python {metadados['python']} | "
        f"media de {metadados['amostras']} grafos x {metadados['repeticoes']} repeticoes "
        f"(faixa = min-max)",
        ha="center",
        fontsize=7,
    )
    figura.tight_layout(rect=(0, 0.03, 1, 1))
    figura.savefig(destino, dpi=150)
    plt.close(figura)


def _agregar(
    medicoes: Sequence[Medicao], topologia: str, algoritmo: str
) -> dict[int, tuple[float, float, float]]:
    """Agrupa as medicoes em (media, minimo, maximo) por tamanho."""
    por_tamanho: dict[int, list[float]] = {}
    for medicao in medicoes:
        if medicao.topologia == topologia and medicao.algoritmo == algoritmo:
            por_tamanho.setdefault(medicao.tamanho, []).append(medicao.tempo_s)
    return {
        tamanho: (statistics.fmean(tempos), min(tempos), max(tempos))
        for tamanho, tempos in por_tamanho.items()
    }


def coletar_metadados(argumentos: argparse.Namespace) -> dict[str, object]:
    """Registra quando, onde e com quais parametros os numeros foram medidos.

    Sem isso o CSV e o grafico viram numero sem procedencia -- outra maquina
    produz outra escala absoluta, mesmo com a mesma taxa de crescimento.
    """
    return {
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cpu": _modelo_cpu(),
        "nucleos": os.cpu_count(),
        "so": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "topologias": argumentos.topologias,
        "tamanhos": argumentos.tamanhos,
        "grau_medio": argumentos.grau_medio,
        "amostras": argumentos.amostras,
        "repeticoes": argumentos.repeticoes,
        "seed": argumentos.seed,
    }


def _modelo_cpu() -> str:
    """Le o modelo do processador; ``platform.processor()`` costuma vir vazio no Linux."""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for linha in cpuinfo.read_text(encoding="utf-8").splitlines():
            if linha.startswith("model name"):
                return linha.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tamanhos", type=int, nargs="+", default=list(TAMANHOS_PADRAO))
    parser.add_argument(
        "--topologias",
        nargs="+",
        choices=sorted(TOPOLOGIAS),
        default=sorted(TOPOLOGIAS),
        help="aleatoria = malha esparsa conexa; caminho = pior caso do Bellman-Ford",
    )
    parser.add_argument(
        "--grau-medio",
        type=float,
        default=4.0,
        help="densidade da topologia aleatoria: E ~ V*grau/2 (padrao: 4.0)",
    )
    parser.add_argument("--amostras", type=int, default=3, help="grafos distintos por tamanho")
    parser.add_argument("--repeticoes", type=int, default=3, help="execucoes por grafo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    argumentos = _parse_args(argv)
    argumentos.saida.mkdir(parents=True, exist_ok=True)

    print("Medindo...", flush=True)
    medicoes = medir(
        argumentos.topologias,
        argumentos.tamanhos,
        argumentos.grau_medio,
        argumentos.amostras,
        argumentos.repeticoes,
        argumentos.seed,
    )
    metadados = coletar_metadados(argumentos)

    csv_destino = argumentos.saida / "benchmark.csv"
    grafico_destino = argumentos.saida / "tempo_por_tamanho.png"
    metadados_destino = argumentos.saida / "metadata.json"

    escrever_csv(medicoes, csv_destino)
    gerar_grafico(medicoes, grafico_destino, metadados)
    metadados_destino.write_text(json.dumps(metadados, indent=2) + "\n", encoding="utf-8")

    print(f"{len(medicoes)} medicoes -> {csv_destino}")
    print(f"grafico -> {grafico_destino}")
    print(f"metadados -> {metadados_destino}")
    _resumo(medicoes)


def _resumo(medicoes: Sequence[Medicao]) -> None:
    """Imprime a tabela que sustenta a nota de analise."""
    topologias = sorted({medicao.topologia for medicao in medicoes})
    for topologia in topologias:
        print(f"\n{topologia}:")
        print(f"{'V':>6} {'E':>6} {'dijkstra (s)':>14} {'bellman-ford (s)':>18} {'razao':>8}")
        arestas_por_tamanho = {
            medicao.tamanho: medicao.arestas
            for medicao in medicoes
            if medicao.topologia == topologia
        }
        dij = _agregar(medicoes, topologia, "dijkstra")
        bfd = _agregar(medicoes, topologia, "bellman-ford")
        for tamanho in sorted(dij):
            razao = bfd[tamanho][0] / dij[tamanho][0]
            print(
                f"{tamanho:>6} {arestas_por_tamanho[tamanho]:>6} "
                f"{dij[tamanho][0]:>14.6f} {bfd[tamanho][0]:>18.6f} {razao:>7.1f}x"
            )


if __name__ == "__main__":
    main()
