# Benchmark: Dijkstra x Bellman-Ford

Comparação empírica de tempo de execução dos dois algoritmos de caminho mínimo do
simulador, sobre grafos sintéticos de tamanho crescente e sobre a malha mundial real.

Reproduzir:

```sh
uv run python scripts/benchmark.py
```

Saídas em `docs/benchmark/`: `benchmark.csv` (dados brutos, uma linha por execução),
`tempo_por_tamanho.png` (gráfico) e `metadata.json` (procedência da medição).

## Como foi medido

| | |
|---|---|
| Data | 2026-09-06 15:31 UTC |
| CPU | AMD64 Family 23 Model 24 Stepping 1, AuthenticAMD (8 núcleos) |
| SO / Python | Windows 11 / CPython 3.12.10 |
| Tamanhos (V) | 10, 50, 100, 500, 1000 |
| Amostras | 3 grafos distintos por tamanho × 3 repetições por grafo |
| Relógio | `time.perf_counter()` em volta da chamada do algoritmo |
| Semente | 42 (derivada por topologia/tamanho/amostra — cada grafo é reproduzível) |

As duas topologias sintéticas usam pesos uniformes em [1, 100]:

- **aleatória** — grafo esparso conexo com grau médio 4 (E ≈ 2V). É o formato que se
  parece com a malha do simulador: poucos cabos por nó e caminhos alternativos.
  A conexidade é garantida por construção (árvore geradora + arestas extras), senão
  boa parte das medições cairia em componente desconexa e mediria só a detecção de
  "sem rota".
- **caminho** — grafo em linha reta, com os nós inseridos na ordem inversa do
  caminho. Serve para expor o pior caso do Bellman-Ford (explicado abaixo).
- **real** — os 100 nós e 180 arestas de `backend/data/rede.json`, na consulta fixa
  Praia Grande → Chiba. É medida uma vez, com três repetições, pois não há sorteio de
  grafo nessa topologia.

Em todas as 31 combinações medidas os dois algoritmos devolveram exatamente o mesmo
custo de rota — a comparação é de desempenho entre implementações que concordam no
resultado, não entre respostas diferentes.

## Resultado

Tempo médio por execução (s):

### Topologia aleatória (E ≈ 2V)

| V | E | Dijkstra | Bellman-Ford | razão |
|---:|---:|---:|---:|---:|
| 10 | 20 | 0.000065 | 0.000064 | 1.0× |
| 50 | 100 | 0.000246 | 0.000328 | 1.3× |
| 100 | 200 | 0.000565 | 0.000709 | 1.3× |
| 500 | 1000 | 0.003492 | 0.005105 | 1.5× |
| 1000 | 2000 | 0.005174 | 0.010657 | 2.1× |

### Topologia caminho (E = V-1)

| V | E | Dijkstra | Bellman-Ford | razão |
|---:|---:|---:|---:|---:|
| 10 | 9 | 0.000040 | 0.000056 | 1.4× |
| 50 | 49 | 0.000188 | 0.000818 | 4.4× |
| 100 | 99 | 0.000367 | 0.003420 | 9.3× |
| 500 | 499 | 0.002093 | 0.084236 | 40.3× |
| 1000 | 999 | 0.004724 | 0.349873 | 74.1× |

### Topologia real

| V | E | consulta | Dijkstra | Bellman-Ford | razão |
|---:|---:|---|---:|---:|---:|
| 100 | 180 | Praia Grande → Chiba | 0.000548 | 0.000679 | 1.2× |

![Tempo de execução por tamanho do grafo](tempo_por_tamanho.png)

Expoente de crescimento, medido como inclinação da reta em escala log-log no trecho
V = 100 → 1000 (tempo ∝ V^expoente):

| topologia | Dijkstra | Bellman-Ford |
|---|---:|---:|
| aleatória | 0.96 | 1.18 |
| caminho | 1.11 | 2.01 |

## Empírico x teórico

O esperado para Dijkstra é O((V+E) log V); com E ∝ V isso dá V log V. O expoente
medido foi 1.11 no caminho. Na topologia aleatória ficou em 0.96: origem e destino
sorteados fazem a saída antecipada visitar apenas parte do grafo, e a faixa curta de
tamanhos e o ruído de uma máquina compartilhada tornam essa inclinação uma estimativa,
não uma prova da cota assintótica.

**Bellman-Ford só se aproxima do pior caso na topologia caminho.** O esperado é
O(V·E), que com E ∝ V dá O(V²), ou seja expoente 2. Medido: **2.01** no caminho. Na
topologia aleatória o expoente medido é **1.18**, longe de 2, e o algoritmo fica
próximo do Dijkstra nos tamanhos menores.

A divergência não é erro de medição, é consequência de uma otimização na nossa
implementação (`backend/algorithms/bellman_ford.py`): **o relaxamento para assim que
uma rodada não altera nenhum custo**, em vez de sempre executar as V-1 rodadas do
algoritmo de livro. O número de rodadas necessárias é o número de arestas do maior
caminho mínimo alcançável a partir da origem — ou seja, o diâmetro efetivo do grafo,
não V.

Isso explica os dois números:

- Em grafo aleatório esparso o diâmetro cresce como O(log V), não como V. O custo real
  vira O(E · log V) em vez de O(V · E), e o expoente cai de 2 para perto de 1 —
  compatível com o 1.18 medido.
- Na topologia caminho o diâmetro **é** V-1, e a ordem de inserção dos nós foi
  escolhida de propósito para ser adversa: o Bellman-Ford relaxa as arestas na ordem
  em que os nós foram inseridos, então cada rodada avança um único salto. Nesse
  cenário a saída antecipada não ajuda, as V-1 rodadas acontecem de fato, e o O(V·E)
  aparece inteiro — daí o expoente 2.01 e a razão de 74× contra o Dijkstra em V = 1000.

Ou seja: a cota O(V·E) do Bellman-Ford está correta como **pior caso**, mas é
pessimista para o caso médio de uma malha esparsa. A medição na topologia aleatória
sozinha daria a impressão errada de que os dois algoritmos são equivalentes; foi por
isso que a topologia caminho entrou no benchmark.

## O que isso significa para o simulador

Para a malha do projeto (100 nós, esparsa, pesos geodésicos sempre positivos), a
diferença de tempo entre os dois é irrelevante para a interação — ambos ficaram perto
de um milissegundo na consulta real medida.
A escolha entre eles no `POST /rota` é de demonstração didática, não de desempenho.
O Dijkstra continua sendo o padrão porque é o que degrada melhor se a malha crescer, e
o Bellman-Ford segue disponível por aceitar peso negativo, que o Dijkstra rejeita.

## Limitações

- Máquina única, sem isolamento de CPU: os números absolutos não são comparáveis com
  outro hardware. As taxas de crescimento (expoentes) são o resultado transferível.
- V = 1000 é o maior tamanho medido. A curva do Bellman-Ford na topologia caminho já
  chega a 0.35 s por execução ali; tamanhos maiores custariam minutos de benchmark sem
  mudar a conclusão.
- Ambos os algoritmos têm saída antecipada (o Dijkstra para ao remover o destino da
  fila), então os tempos medidos são de uma consulta origem→destino, não do cálculo da
  árvore de caminhos mínimos completa.
