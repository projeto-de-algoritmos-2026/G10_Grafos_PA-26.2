"""Valida o dataset mundial e imprime um resumo util para CI e revisao manual."""

import sys
from argparse import ArgumentParser
from pathlib import Path

# Executado como script solto, o sys.path comeca em scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.state import DATA_FILE, load_dataset  # noqa: E402


def main() -> int:
    parser = ArgumentParser(description="Valida backend/data/rede.json")
    parser.add_argument("arquivo", nargs="?", type=Path, default=DATA_FILE)
    args = parser.parse_args()

    try:
        dataset = load_dataset(args.arquivo)
    except RuntimeError as error:
        print(f"Dataset inválido: {error}")
        return 1

    cable_count = len({edge.cabo for edge in dataset.arestas})
    print("Dataset válido")
    print(f"{len(dataset.nos)} nós")
    print(f"{len(dataset.arestas)} arestas")
    print("Grafo conexo")
    print(f"Peso: distância geodésica em {dataset.metadata.unidade_peso}")
    print(f"{cable_count} sistemas de cabos")
    print("Todas as arestas possuem fonte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
