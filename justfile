set shell := ["bash", "-cu"]

dev:
    uv run uvicorn backend.main:app --reload

test:
    uv run pytest

lint:
    uv run ruff check .

fmt:
    uv run ruff format .

check:
    just fmt
    just lint
    just test

validar:
    uv run python scripts/validar_rede.py

bench:
    uv run python scripts/benchmark.py
