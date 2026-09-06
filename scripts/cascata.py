"""Gera curvas reproduziveis de resiliencia da malha real.

Executa as estrategias aleatoria, por grau e por articulacao sobre copias da
rede, salvando dados brutos, grafico e procedencia em um diretorio proprio.

Uso:
    uv run python scripts/cascata.py
    uv run python scripts/cascata.py --passos 15 --semente 42
"""

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.resilience import CascadeResult, CascadeStrategy, simulate_cascade  # noqa: E402
from backend.state import DATA_FILE, load_network  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "benchmark" / "cascata"
STRATEGIES: tuple[CascadeStrategy, ...] = ("aleatoria", "grau", "articulacao")

CSV_FIELDS = (
    "estrategia",
    "semente",
    "total_inicial",
    "passo",
    "no_removido",
    "nos_ativos",
    "fracao_removida",
    "maior_componente_fracao",
    "pares_alcancaveis_fracao",
    "custo_medio_rotas",
)


def run_analysis(
    strategies: Sequence[CascadeStrategy], steps: int | None, seed: int
) -> list[CascadeResult]:
    """Executa todas as estrategias pedidas sobre a topologia real."""
    network = load_network()
    requested_steps = len(network.node_ids()) if steps is None else steps
    return [
        simulate_cascade(network, strategy, requested_steps, seed)
        for strategy in strategies
    ]


def write_csv(results: Sequence[CascadeResult], destination: Path) -> None:
    """Grava um ponto da curva por linha para permitir reanalise."""
    with destination.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in results:
            for point in result.points:
                writer.writerow(
                    {
                        "estrategia": result.strategy,
                        "semente": result.seed,
                        "total_inicial": result.initial_nodes,
                        "passo": point.step,
                        "no_removido": point.removed_node or "",
                        "nos_ativos": point.active_nodes,
                        "fracao_removida": point.removed_fraction,
                        "maior_componente_fracao": point.largest_component_fraction,
                        "pares_alcancaveis_fracao": point.reachable_pairs_fraction,
                        "custo_medio_rotas": (
                            point.average_route_cost
                            if point.average_route_cost is not None
                            else ""
                        ),
                    }
                )


def plot_results(
    results: Sequence[CascadeResult], destination: Path, metadata: dict[str, object]
) -> None:
    """Plota as tres metricas, comparando todas as estrategias."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    metrics = (
        ("largest_component_fraction", "maior componente / nos iniciais", (0, 1.05)),
        ("reachable_pairs_fraction", "pares alcancaveis / pares iniciais", (0, 1.05)),
        ("average_route_cost", "custo medio das rotas (km)", None),
    )
    colors = {"aleatoria": "#4c78a8", "grau": "#e45756", "articulacao": "#72b7b2"}

    for axis, (attribute, label, limits) in zip(axes, metrics, strict=True):
        for result in results:
            x_values = [point.removed_fraction for point in result.points]
            y_values = [getattr(point, attribute) for point in result.points]
            axis.plot(
                x_values,
                y_values,
                marker="o",
                markersize=2.8,
                linewidth=1.5,
                label=result.strategy,
                color=colors[result.strategy],
            )
        axis.set(xlabel="fracao de nos removidos", ylabel=label, xlim=(0, 1))
        if limits is not None:
            axis.set_ylim(*limits)
        axis.grid(True, linewidth=0.35, alpha=0.6)
        axis.legend()

    figure.suptitle("Resiliencia da malha: falhas aleatorias x ataques dirigidos")
    figure.text(
        0.5,
        0.005,
        f"{metadata['timestamp_utc']} | {metadata['cpu']} | Python {metadata['python']} | "
        f"semente {metadata['semente']}",
        ha="center",
        fontsize=7,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(destination, dpi=150)
    plt.close(figure)


def collect_metadata(
    arguments: argparse.Namespace,
    results: Sequence[CascadeResult],
    elapsed_seconds: float,
) -> dict[str, object]:
    """Registra ambiente, parametros e identidade exata do dataset."""
    network = load_network()
    return {
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cpu": _cpu_model(),
        "nucleos": os.cpu_count(),
        "so": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "estrategias": [result.strategy for result in results],
        "passos_solicitados": arguments.passos,
        "passos_executados": max(len(result.points) - 1 for result in results),
        "semente": arguments.semente,
        "nos_iniciais": len(network.node_ids()),
        "arestas": len(network.edges()),
        "dataset": str(DATA_FILE.relative_to(Path(__file__).resolve().parents[1])),
        "dataset_sha256": hashlib.sha256(DATA_FILE.read_bytes()).hexdigest(),
        "tempo_execucao_s": elapsed_seconds,
        "normalizacao": {
            "maior_componente": "tamanho da maior componente / nos ativos no inicio",
            "pares_alcancaveis": "pares alcancaveis / pares entre nos ativos no inicio",
            "custo_medio": "media dos menores custos apenas entre pares alcancaveis",
        },
    }


def _cpu_model() -> str:
    """Obtem o modelo do processador em Linux, Windows ou macOS."""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--estrategias",
        nargs="+",
        choices=STRATEGIES,
        default=list(STRATEGIES),
    )
    parser.add_argument(
        "--passos",
        type=int,
        default=None,
        help="remocoes por estrategia; por padrao remove todos os nos ativos",
    )
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--saida", type=Path, default=OUTPUT_DIR)
    arguments = parser.parse_args(argv)
    if arguments.passos is not None and arguments.passos < 0:
        parser.error("--passos deve ser nao negativo")
    return arguments


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _parse_args(argv)
    arguments.saida.mkdir(parents=True, exist_ok=True)

    started_at = time.perf_counter()
    results = run_analysis(arguments.estrategias, arguments.passos, arguments.semente)
    elapsed_seconds = time.perf_counter() - started_at
    metadata = collect_metadata(arguments, results, elapsed_seconds)

    csv_path = arguments.saida / "cascata.csv"
    chart_path = arguments.saida / "curva_resiliencia.png"
    metadata_path = arguments.saida / "metadata.json"
    write_csv(results, csv_path)
    plot_results(results, chart_path, metadata)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"{sum(len(result.points) for result in results)} pontos -> {csv_path}")
    print(f"grafico -> {chart_path}")
    print(f"metadados -> {metadata_path}")
    for result in results:
        order = ", ".join(
            point.removed_node or "inicio" for point in result.points[:6]
        )
        print(f"{result.strategy}: {order} ...")


if __name__ == "__main__":
    main()
