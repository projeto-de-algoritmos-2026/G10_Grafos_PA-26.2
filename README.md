# Simulador de Colapso de Internet

Projeto da disciplina de Projeto de Algoritmos que representa uma malha mundial de
cabos como um grafo ponderado e recalcula a menor rota quando um nó ou uma conexão
fica indisponível. A aplicação permite comparar Dijkstra e Bellman-Ford e acompanhar
o resultado em uma interface web interativa.

![Interface com uma rota recalculada após a queda de um nó](docs/images/rota-recalculada.png)

## Funcionalidades

- visualização de 26 pontos de conexão e 30 ligações associadas a sistemas reais de
  cabos submarinos;
- cálculo de menor caminho com Dijkstra ou Bellman-Ford;
- queda e restauração de nós por clique;
- recálculo e destaque da rota sem recarregar a página;
- indicação de rede particionada quando não existe caminho disponível;
- API HTTP documentada automaticamente pelo FastAPI.

## Pré-requisitos

- [Git](https://git-scm.com/);
- Python 3.12 ou superior;
- [uv](https://docs.astral.sh/uv/getting-started/installation/);
- acesso à internet no navegador para carregar o `vis-network` 9.1.9 pela CDN.

Não é necessário instalar Node.js nem executar um servidor separado para o
front-end.

## Instalação do zero

```sh
git clone https://github.com/projeto-de-algoritmos-2026/G10_Grafos_PA-26.2.git
cd G10_Grafos_PA-26.2
uv sync
```

O `uv sync` cria o ambiente virtual e instala as dependências da aplicação e de
desenvolvimento conforme o `uv.lock`.

## Executando a demo

Na raiz do repositório, inicie o único processo necessário:

```sh
uv run uvicorn backend.main:app --reload
```

Abra <http://localhost:8000/> no navegador. Para testar o recálculo:

1. selecione uma origem e um destino;
2. escolha Dijkstra ou Bellman-Ford;
3. clique em um nó do grafo para derrubá-lo;
4. observe a nova rota ou o aviso de particionamento;
5. clique novamente no nó para restaurá-lo ou use **Resetar simulação**.

Verificações úteis:

- <http://localhost:8000/status> deve responder `{"status":"ok"}`;
- <http://localhost:8000/docs> abre o Swagger com o contrato da API.

O estado da simulação fica somente em memória. Reiniciar o processo restaura a rede.

## Estrutura do repositório

```text
backend/
├── algorithms/       # Dijkstra, Bellman-Ford e resultado compartilhado
├── data/rede.json    # topologia mundial usada pela aplicação
├── tests/            # testes unitários e de integração da API
├── graph.py          # grafo ponderado não dirigido
├── dataset.py        # esquema e validações do dataset
├── simulation.py     # falhas, restauração e seleção do algoritmo
├── state.py          # carga e estado em memória
└── main.py           # API FastAPI e entrega dos arquivos estáticos
frontend/             # interface em HTML, CSS e JavaScript
scripts/
├── validar_rede.py   # validação independente do dataset
└── benchmark.py      # benchmark reproduzível dos algoritmos
docs/
├── benchmark/        # CSV, gráfico, metadados e análise da issue #7
├── images/           # capturas reais da interface
├── rede-mundial.md   # fontes e metodologia do dataset da issue #8
└── relatorio.md      # relatório final
```

## Testes e qualidade

Execute, a partir da raiz:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Para conferir separadamente a integridade da topologia:

```sh
uv run python scripts/validar_rede.py
```

## Benchmark

O benchmark compara os algoritmos sobre grafos sintéticos aleatórios e em caminho,
usando os mesmos grafos em cada comparação:

```sh
uv run python scripts/benchmark.py
```

O comando sobrescreve `docs/benchmark/benchmark.csv`,
`docs/benchmark/tempo_por_tamanho.png` e `docs/benchmark/metadata.json` com uma nova
execução. Os tempos variam conforme a máquina. A metodologia, os dados já medidos e a
interpretação estão em [docs/benchmark/analise.md](docs/benchmark/analise.md).

## Documentação

- [Relatório final](docs/relatorio.md)
- [Dataset da rede mundial](docs/rede-mundial.md)
- [Análise do benchmark](docs/benchmark/analise.md)

O relatório foi mantido em Markdown porque não há, no repositório, enunciado ou
cronograma que determine outro padrão. Se a disciplina exigir PDF ou formatação ABNT,
a versão de entrega deve ser gerada a partir desse conteúdo conforme a orientação do
professor.

## Autoria

- Gustavo Xavier Evangelista
- Lucas A. Zanetti

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
