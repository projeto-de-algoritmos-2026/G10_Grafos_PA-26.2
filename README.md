# G10_Grafos_PA-26.2

Simulador de Colapso de Internet (Roteamento Dinâmico). Modela uma malha de rede como grafo ponderado e recalcula a rota de menor custo (Dijkstra / Bellman-Ford) quando um nó ou link "cai", em tempo real.

## Estrutura

- `backend/`: API (FastAPI), estrutura de grafo e algoritmos de caminho mínimo, próprios (sem `networkx`)
- `backend/tests/`: testes (`pytest`)
- `frontend/`: interface web (HTML/CSS/JS) que consome a API
- `docs/`: relatório final e benchmarks

## Setup

Requer [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
```

## Rodando o backend

```sh
uv run uvicorn backend.main:app --reload
```

`GET http://localhost:8000/status` deve responder `{"status": "ok"}`.

## Testes e lint

```sh
uv run pytest
uv run ruff check .
uv run ruff format .
```
