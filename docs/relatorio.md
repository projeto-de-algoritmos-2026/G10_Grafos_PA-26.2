# Relatório final — Simulador de Colapso de Internet

**Disciplina:** Projeto de Algoritmos  
**Tema:** Grafos e caminhos mínimos  
**Autores:** Gustavo Xavier Evangelista e Lucas A. Zanetti  
**Repositório:** [G10_Grafos_PA-26.2](https://github.com/projeto-de-algoritmos-2026/G10_Grafos_PA-26.2)

> **Nota de formato:** não foi encontrado no repositório um enunciado ou cronograma
> que exija PDF ou normas ABNT. Por isso, este relatório foi produzido em Markdown.
> Caso exista uma orientação externa da disciplina, o conteúdo deve ser convertido e
> ajustado antes da entrega.

## Resumo

O projeto implementa um simulador visual de falhas em uma rede mundial. Pontos de
conexão são modelados como vértices, cabos como arestas e a distância geodésica entre
os pontos como peso. O usuário escolhe origem, destino e algoritmo de menor caminho;
quando um nó cai, a topologia disponível muda e a rota é calculada novamente. Foram
implementados Dijkstra, Bellman-Ford e A* sem bibliotecas de algoritmos de grafos. Os
testes empíricos mostram o comportamento quase linear-logarítmico de Dijkstra nos
grafos esparsos avaliados, o pior caso quadrático de Bellman-Ford em uma topologia em
caminho, e a redução real de nós explorados que a heurística geodésica de A* traz sobre
Dijkstra na malha mundial.

## 1. Contexto e objetivo

A infraestrutura da Internet possui redundância: quando um equipamento ou enlace
fica indisponível, o tráfego pode usar outro caminho. O simulador apresenta essa ideia
em uma escala didática. Seu objetivo não é reproduzir protocolos como BGP ou medir a
Internet real, mas permitir a observação direta de três conceitos:

1. uma rede pode ser representada como grafo ponderado;
2. a melhor rota depende do estado atual de seus vértices e arestas;
3. algoritmos corretos para o mesmo problema podem ter custos computacionais
   diferentes.

A aplicação reúne uma API FastAPI, implementações próprias dos algoritmos e uma
interface web. O estado é mantido em memória durante a execução.

## 2. Modelagem como grafo

Seja o grafo `G = (V, E)`, em que `V` é o conjunto de pontos da rede e `E` é o
conjunto de conexões. Cada aresta possui peso numérico. Na topologia mundial do
projeto, esse peso é a distância Haversine arredondada, em quilômetros.

### 2.1 Grafo não dirigido

O domínio atual considera que cada cabo pode ser percorrido nos dois sentidos com o
mesmo custo. Por isso, o grafo é **não dirigido**. A estrutura usa lista de adjacência
e armazena cada cabo em duas entradas espelhadas: `u → v` e `v → u`. As operações de
queda e restauração atualizam as duas entradas juntas.

Essa decisão simplifica a demonstração, mas não representa assimetrias de capacidade,
latência ou política de roteamento. Um grafo dirigido é mantido como possível extensão.

### 2.2 Nó indisponível em vez de remoção física

Nós e arestas têm uma flag `is_up`. Derrubar um nó altera essa flag, mas preserva o
vértice e suas conexões na estrutura. Ao consultar os vizinhos, a implementação omite
arestas desligadas e destinos indisponíveis. Essa escolha tem duas consequências
importantes:

- restaurar um nó não exige reconstruir seus metadados e conexões;
- a interface consegue continuar desenhando a topologia completa e diferenciar os
  elementos ativos dos derrubados.

A remoção física tornaria a restauração mais complexa e perderia parte do histórico
visual da simulação. O mesmo princípio é aplicado aos cabos.

### 2.3 Estado e recálculo

Uma instância do grafo é carregada quando a API inicia. As operações de falha mudam
essa instância e invalidam a rota armazenada. Se origem e destino estiverem
selecionados, o front-end solicita imediatamente um novo cálculo. Não encontrar um
caminho é um resultado válido (`encontrada = false`), e não um erro HTTP.

## 3. Dataset

A malha contém **100 nós e 180 arestas**. Os nós representam landing points ou
agregações metropolitanas de pontos próximos. As arestas indicam conectividade lógica
associada a sistemas reais de cabos em serviço.

As coordenadas WGS84 foram obtidas no GeoNames. Os sistemas e seus landing points
foram consultados no mapa público da TeleGeography, com a ampliação conferida em 6 de
setembro de 2026. A malha cobre também África Oriental, Sudeste Asiático, Oceania e o
corredor ártico da Groenlândia. Cada aresta de `backend/data/rede.json` mantém a
referência de sua fonte.

O peso é calculado pela fórmula de Haversine entre as coordenadas exibidas. Portanto,
ele não deve ser interpretado como latência, capacidade ou comprimento físico exato
do cabo. O arco de grande círculo aproximado mostrado pela interface também não
corresponde ao traçado no fundo do mar. A metodologia completa e todas as fontes estão em
[rede-mundial.md](rede-mundial.md).

O carregamento rejeita IDs e arestas duplicadas, coordenadas inválidas, self-loops,
referências inexistentes, pesos não positivos ou incoerentes, fontes desconhecidas e
uma topologia desconexa. A validação pode ser repetida com:

```sh
uv run python scripts/validar_rede.py
```

## 4. Algoritmos de menor caminho

### 4.1 Dijkstra

Dijkstra mantém a menor distância conhecida da origem até cada vértice e uma fila de
prioridade. A cada passo, remove da fila o vértice de menor custo acumulado e relaxa
suas arestas: se passar pelo vértice atual melhora o custo de um vizinho, a distância
e o predecessor são atualizados. Quando o destino é removido da fila, a busca termina
e o caminho é reconstruído pelos predecessores.

A implementação usa `heapq` e lista de adjacência. Sua complexidade de tempo é
`O((V + E) log V)` e o espaço auxiliar é `O(V)`, além do armazenamento `O(V + E)` do
grafo. Dijkstra exige pesos não negativos; a implementação rejeita uma aresta negativa
ativa.

### 4.2 Bellman-Ford

Bellman-Ford relaxa todas as arestas repetidamente. Um caminho mínimo simples possui
no máximo `V - 1` arestas, portanto esse número de rodadas é suficiente. Uma rodada
adicional detecta ciclo negativo alcançável: se ainda for possível reduzir um custo,
não existe menor caminho bem definido.

Como o grafo é não dirigido, uma única aresta negativa utilizável já forma um ciclo
negativo de ida e volta. Essa capacidade do algoritmo permanece didática; o dataset
real usa somente pesos positivos.

O pior caso de tempo é `O(VE)` e o espaço auxiliar é `O(V + E)` na implementação,
que materializa os dois arcos de cada cabo antes do relaxamento. Há saída antecipada
quando uma rodada inteira não muda nenhum custo, o que melhora muitos casos práticos
sem alterar a cota de pior caso.

### 4.3 A*

A* é uma variante de Dijkstra guiada por uma heurística `h(n)`: em vez de priorizar
pela fila só pelo custo acumulado `g(n)`, prioriza por `f(n) = g(n) + h(n)`, uma
estimativa do custo restante até o destino. O dataset guarda latitude e longitude de
cada nó e o peso de cada aresta é exatamente a distância Haversine entre seus
extremos (`backend/dataset.py`, `NetworkDataset.validate_topology`); isso dá de graça
uma heurística `h(n) = haversine(n, destino)` **admissível e consistente**: pela
desigualdade triangular na esfera, nenhum caminho de `n` até o destino custa menos que
a distância geodésica direta. Heurística admissível e consistente garante que A* nunca
reabre um nó já processado e sempre devolve o mesmo caminho ótimo de Dijkstra — a
implementação (`backend/algorithms/a_star.py`) reaproveita exatamente a mesma estrutura
de fila e o mesmo critério de descarte de entrada obsoleta do Dijkstra do projeto,
trocando apenas a prioridade.

A heurística só é válida enquanto o peso da aresta representar quilômetros: se uma
métrica futura (latência, capacidade) substituir a distância, `h` deixa de ser cota
inferior garantida e A* precisaria de sua própria heurística admissível para essa
métrica, ou usar Dijkstra/Bellman-Ford.

Complexidade de pior caso igual à de Dijkstra, `O((V + E) log V)`, pois a heurística
não muda a estrutura da busca — só a ordem de exploração. Na prática, guiar a busca
para o destino faz A* expandir menos nós, medido na seção 6.3.

### 4.4 Comparação teórica

| Algoritmo | Tempo | Espaço auxiliar nesta implementação | Peso negativo |
|---|---:|---:|---|
| Dijkstra com heap | `O((V + E) log V)` | `O(V)` | não |
| Bellman-Ford | `O(VE)` no pior caso | `O(V + E)` | sim, com detecção de ciclo negativo |
| A* com heurística Haversine | `O((V + E) log V)` | `O(V)` | não |

Para uma malha esparsa, em que `E` cresce proporcionalmente a `V`, Dijkstra e A* tendem
a `O(V log V)`, enquanto o pior caso de Bellman-Ford tende a `O(V²)`.

## 5. Arquitetura da solução

O back-end separa a estrutura do grafo (`backend/graph.py`), os algoritmos
(`backend/algorithms/`), as operações de simulação (`backend/simulation.py`) e a API
(`backend/main.py`). A API expõe a topologia, o cálculo de rota e a queda/restauração
de nós e cabos. O FastAPI também serve o front-end estático, portanto a demonstração
precisa de um único processo.

O front-end usa HTML, CSS e JavaScript sem framework. Foi escolhida a alternativa
**Leaflet + camada de tiles** discutida na issue do mapa. Em comparação com manter o
`vis-network` sobre um contorno estático, essa opção exigiu reescrever marcadores e
arestas, mas entrega pan e zoom em uma projeção geográfica real. Os nós são
`L.circleMarker` nas coordenadas WGS84 e seus rótulos aparecem somente no hover, o que
preserva a leitura com 100 pontos.

Os cabos são polilinhas amostradas por interpolação esférica, aproximando o arco de
grande círculo. A geometria detecta saltos de longitude maiores que 180° e divide a
linha exatamente nas bordas +180° e -180°; assim, uma ligação Tóquio–Los Angeles usa o
caminho curto pelo Pacífico, sem atravessar o mapa inteiro. A versão 1.9.4 do Leaflet
fica no próprio repositório. Somente os tiles do OpenStreetMap são externos: quando
falham, o mapa-base dá lugar a uma grade neutra, mas nós, cabos, zoom, cliques e
destaques continuam funcionando.

Pontos e cabos comuns ficam menores conforme a densidade cresce, enquanto extremos e
rotas selecionadas continuam destacados. Toda alteração relevante busca novamente o
estado do grafo e solicita o recálculo.

## 6. Avaliação empírica

### 6.1 Método

O benchmark foi executado em 6 de setembro de 2026, às 15:31 UTC, em um processador
AMD64 de 8 núcleos, Windows 11 e CPython 3.12.10. Foram avaliados
grafos com 10, 50, 100, 500 e 1.000 vértices, usando três grafos por tamanho e três
repetições por grafo. O relógio `time.perf_counter()` envolveu somente a chamada do
algoritmo.

Foram usadas duas topologias sintéticas com pesos uniformes entre 1 e 100:

- **aleatória:** grafo esparso conexo, com `E ≈ 2V`;
- **caminho:** `E = V - 1`, com ordem de inserção adversa ao Bellman-Ford para expor
  seu pior caso.
- **real:** os 100 nós e 180 arestas do dataset, na consulta Praia Grande → Chiba.

Nas 31 combinações de topologia, tamanho e amostra, os dois algoritmos retornaram o
mesmo custo. Os dados brutos estão em [benchmark/benchmark.csv](benchmark/benchmark.csv),
e os metadados em [benchmark/metadata.json](benchmark/metadata.json).

### 6.2 Resultados medidos

Tempo médio por execução, em segundos:

| Topologia | V | E | Dijkstra | Bellman-Ford | Razão BF/Dijkstra |
|---|---:|---:|---:|---:|---:|
| aleatória | 10 | 20 | 0,000065 | 0,000064 | 1,0× |
| aleatória | 50 | 100 | 0,000246 | 0,000328 | 1,3× |
| aleatória | 100 | 200 | 0,000565 | 0,000709 | 1,3× |
| aleatória | 500 | 1.000 | 0,003492 | 0,005105 | 1,5× |
| aleatória | 1.000 | 2.000 | 0,005174 | 0,010657 | 2,1× |
| caminho | 10 | 9 | 0,000040 | 0,000056 | 1,4× |
| caminho | 50 | 49 | 0,000188 | 0,000818 | 4,4× |
| caminho | 100 | 99 | 0,000367 | 0,003420 | 9,3× |
| caminho | 500 | 499 | 0,002093 | 0,084236 | 40,3× |
| caminho | 1.000 | 999 | 0,004724 | 0,349873 | 74,1× |
| real | 100 | 180 | 0,000548 | 0,000679 | 1,2× |

![Tempo de execução por tamanho do grafo](benchmark/tempo_por_tamanho.png)

No intervalo entre 100 e 1.000 vértices, a inclinação log-log medida foi 0,96 e 1,11
para Dijkstra nas topologias aleatória e caminho. Para Bellman-Ford, foi 1,18 e 2,01,
respectivamente. A saída antecipada e o par sorteado tornam a inclinação aleatória
mais ruidosa; o caminho adverso expõe o crescimento quadrático esperado.

O resultado de Dijkstra é compatível com `V log V` nos grafos esparsos. Bellman-Ford
se aproxima de `V²` no caminho adverso, como prevê o pior caso. No grafo aleatório,
a saída antecipada encerra o algoritmo após a convergência, escondendo grande parte
do fator `V`; por isso o crescimento medido foi muito menor que o pior caso.

Os tempos absolutos pertencem à máquina registrada e não devem ser generalizados.
A conclusão relevante é a forma de crescimento. A análise detalhada está em
[benchmark/analise.md](benchmark/analise.md).

### 6.3 Dijkstra x A*: nós expandidos na malha real

Reproduzir:

```sh
uv run python scripts/comparar_dijkstra_a_star.py
```

Diferente do benchmark de tempo (seção 6.1), esta medição roda sobre a malha mundial
real (`backend/data/rede.json`, 100 nós, 180 cabos) em vez de grafos sintéticos: é nela
que a heurística Haversine é informativa, porque os nós têm coordenadas geográficas de
verdade. O script calcula Dijkstra e A* para os 9.900 pares ordenados (origem, destino)
dos 100 nós, confirma que os dois concordam em custo em todos eles e conta quantos nós
cada um expandiu. Dados brutos em
[benchmark/nos_expandidos.csv](benchmark/nos_expandidos.csv).

| | |
|---|---|
| Pares avaliados | 9.900 (todos os nós, ordenados) |
| Custo divergente entre os algoritmos | 0 de 9.900 |
| Média de nós expandidos — Dijkstra | 51,00 |
| Média de nós expandidos — A* | 27,34 |
| Redução média de A* sobre Dijkstra | 46,4% |

Nos pares transatlânticos citados como critério de aceite da issue #30 — que cruzam o
Atlântico entre landing points nos Estados Unidos e na Península Ibérica — a redução é
maior que a média geral, porque a heurística geodésica descarta cedo os desvios pela
África e pela Ásia que Dijkstra ainda testa por terem custo acumulado competitivo:

| Origem | Destino | Nós expandidos (Dijkstra) | Nós expandidos (A*) |
|---|---|---:|---:|
| virginia-beach | sines | 7 | 4 |
| los-angeles | carcavelos | 69 | 25 |
| virginia-beach | bilbao | 3 | 2 |

Em nenhum dos 9.900 pares A* expandiu mais nós que Dijkstra; a diferença tende a zero
quando origem e destino já estão poucos saltos um do outro (ex.: `virginia-beach` →
`bilbao` é um cabo praticamente direto), e cresce nos pares mais distantes, onde
Dijkstra desperdiça mais exploração em direções erradas antes de convergir.

### 6.4 Resiliência a falhas em cascata

A malha real também foi submetida a 100 remoções progressivas usando três estratégias:
aleatória com semente 42, maior grau e pontos de articulação. Cada execução operou
sobre uma cópia, sem modificar o estado da API. A maior componente foi normalizada
pelos 100 nós iniciais e os pares alcançáveis pelos 4.950 pares iniciais.

Os ataques dirigidos reduziram a conectividade para menos de 50% dos pares após três
remoções por articulação (3% dos nós) e cinco por grau (5%). A sequência aleatória
medida cruzou o mesmo limiar após 18 remoções. Depois de duas remoções, grau e
articulação preservavam 52,7% e 50,1% dos pares; a sequência aleatória ainda
preservava 96,0%.

![Falhas aleatórias e ataques dirigidos](benchmark/cascata/curva_resiliencia.png)

Os valores vêm da execução de 6 de setembro de 2026, às 15:32 UTC, em Windows 11,
CPython 3.12.10 e processador AMD64 de 8 núcleos. Dados brutos, hash do dataset,
parâmetros e interpretação completa estão em
[benchmark/cascata/analise.md](benchmark/cascata/analise.md). Uma única semente não
prova estatisticamente uma propriedade de redes livres de escala; ela demonstra, na
topologia do projeto, o mecanismo de fragilidade a ataques dirigidos.

## 7. Resultados da interface

A captura abaixo foi produzida em 6 de setembro de 2026 com a aplicação local em
execução. O cenário selecionou Dijkstra, origem **Praia Grande / Santos** e destino
**Sines / Sesimbra**. A API retornou custo de **7.959 km**, em dois saltos; a rota
ótima aparece em amarelo sobre o Atlântico, enquanto os caminhos alternativos ficam
mais finos. Os pontos aparecem sobre continentes reconhecíveis e os cabos do Pacífico
são interrompidos nas bordas do mapa, demonstrando o tratamento do antimeridiano.

![Mapa mundial com a rota entre Praia Grande e Sines](images/mapa-rota.png)

O mesmo mapa preserva os estados de nó ativo, derrubado, origem, destino, pontos de
articulação, pontes, corte mínimo e rota. Clicar em um marcador continua alternando a
disponibilidade e provocando o recálculo sem recarregar a página.

## 8. Limitações e decisões em aberto

- **Grafo não dirigido:** não representa rotas assimétricas, políticas de trânsito ou
  custos diferentes conforme o sentido. Migrar para um grafo dirigido continua em
  aberto.
- **Peso aproximado:** distância Haversine não é latência nem comprimento real do
  cabo. Não há dados de capacidade, congestionamento ou disponibilidade histórica.
- **Topologia curada:** os 100 nós são uma amostra didática; pontos metropolitanos
  próximos foram agregados e as linhas não reproduzem a geometria submarina.
- **Simulação em memória:** não há persistência, usuários isolados nem controle de
  concorrência. Todos os clientes conectados ao mesmo processo compartilham o estado.
- **Escopo de falhas na interface:** nós podem ser alternados por clique; operações de
  cabo existem na API, mas não há um controle visual equivalente na versão atual.
- **Mapa-base externo:** os tiles cartográficos vêm do OpenStreetMap e exigem acesso à
  internet. O Leaflet está versionado localmente e a aplicação degrada para um fundo
  neutro sem perder topologia ou interação.
- **Algoritmos didáticos:** a aplicação calcula menor caminho centralmente e não
  implementa protocolos distribuídos da Internet, como OSPF ou BGP.
- **Benchmark limitado:** houve uma única máquina, sem isolamento dedicado de CPU, e
  tamanhos até 1.000 vértices. As medições avaliam consultas origem–destino com saídas
  antecipadas, não árvores completas de caminhos mínimos.

## 9. Conclusão

O projeto demonstra que a separação entre topologia e disponibilidade torna simples
simular falhas reversíveis. Dijkstra é a escolha padrão adequada ao dataset, cujos
pesos são positivos, e apresenta melhor crescimento. Bellman-Ford oferece o contraste
didático: produz os mesmos custos na malha válida, aceita pesos negativos e evidencia
um pior caso muito mais caro quando a topologia força `V - 1` rodadas.

A captura confirma que a topologia está ancorada em um mapa reconhecível, com arcos
geodésicos e tratamento do antimeridiano. Uma falha preserva o nó para visualização,
altera o conjunto de caminhos utilizáveis e provoca um recálculo visível da rota. O
dataset, os testes e os artefatos do benchmark permitem reproduzir tanto a
demonstração quanto a análise apresentada.

## Referências do projeto

- [Documentação e fontes do dataset](rede-mundial.md)
- [Metodologia e análise completa do benchmark](benchmark/analise.md)
- [Dados brutos do benchmark](benchmark/benchmark.csv)
- [Análise e dados da simulação em cascata](benchmark/cascata/analise.md)
- [README com instalação e execução](../README.md)
