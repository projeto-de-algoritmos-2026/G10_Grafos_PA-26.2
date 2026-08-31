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

`GET http://localhost:8000/status` deve responder `{"status": "ok"}` e `http://localhost:8000/docs` abre o Swagger com o contrato completo da API.

## Dataset mundial

A API carrega `backend/data/rede.json` durante a inicialização. A malha contém 26
landing points/áreas metropolitanas e 30 conexões associadas a sistemas reais de
cabos. O peso é a distância geodésica Haversine em quilômetros — não latência nem o
comprimento físico exato do cabo.

Fontes, metodologia e limitações: [`docs/rede-mundial.md`](docs/rede-mundial.md).

```sh
uv run python scripts/validar_rede.py
```

## Benchmark

Compara o tempo de execução dos dois algoritmos em grafos sintéticos e regenera CSV, gráfico e metadados em `docs/benchmark/`:

```sh
uv run python scripts/benchmark.py
```

Análise dos resultados: [`docs/benchmark/analise.md`](docs/benchmark/analise.md).

## Testes e lint

```sh
uv run pytest
uv run ruff check .
uv run ruff format .
```
