# Resiliência a falhas em cascata

Comparação empírica da conectividade da malha real sob falhas aleatórias e
ataques dirigidos. A execução é reproduzida com:

```sh
uv run python scripts/cascata.py
```

O comando gera neste diretório `cascata.csv` (pontos brutos),
`curva_resiliencia.png` (gráfico) e `metadata.json` (ambiente, parâmetros e hash
do dataset).

## Como foi medido

| | |
|---|---|
| Data | 2026-09-06 14:26:29 UTC |
| CPU | AMD64 Family 23 Model 24 Stepping 1, AuthenticAMD (8 núcleos) |
| SO / Python | Windows 11 / CPython 3.12.10 |
| Topologia | 26 nós e 30 arestas de `backend/data/rede.json` |
| Estratégias | aleatória, maior grau e ponto de articulação |
| Passos | 26 remoções por estratégia, além do ponto inicial |
| Semente | 42 |

Cada estratégia opera sobre uma cópia da mesma rede. A estratégia aleatória
embaralha os IDs ativos com uma instância local de `random.Random`; as estratégias
dirigidas recalculam a prioridade após cada remoção. `grau` escolhe o maior grau
ativo. `articulacao` escolhe primeiro entre os pontos de articulação atuais e usa
maior grau quando nenhum existe. Empates são resolvidos pelo ID.

As frações têm denominador fixo para não criarem uma recuperação artificial quando
restam poucos nós:

- maior componente: tamanho da maior componente / 26 nós iniciais;
- pares alcançáveis: pares conectados / 325 pares iniciais;
- custo médio: média dos menores custos somente entre pares que ainda possuem rota.

## Resultado medido

| Estratégia | 1ª remoção | Pares após 1 remoção | Passo abaixo de 50% dos pares | Fração removida no limiar |
|---|---|---:|---:|---:|
| aleatória | Mumbai | 57,2% | 4 | 15,4% |
| grau | Carcavelos | 92,3% | 2 | 7,7% |
| articulação | Mumbai | 57,2% | 2 | 7,7% |

Depois de duas remoções dirigidas, ambas as estratégias mantêm somente **24,9%**
dos pares originais alcançáveis e a maior componente possui **38,5%** dos nós
iniciais. Na sequência aleatória, esses valores após duas remoções ainda são 55,7%
e 73,1%, respectivamente.

![Curvas de resiliência da malha](curva_resiliencia.png)

O ataque por articulação começa por Mumbai, dividindo a rede já no primeiro passo.
O ataque por grau começa por Carcavelos: a malha continua conectada, mas o custo médio
das rotas sobe de 22.030,1 km para 24.892,7 km, sinal de que os caminhos sobreviventes
precisam contornar o hub removido. No segundo passo, a remoção de outro nó central
provoca a queda abrupta observada nas duas curvas dirigidas.

O custo médio não é monotônico e não deve ser lido isoladamente como melhora. Quando
a rede se fragmenta, pares distantes deixam de ter rota e saem da média; por isso o
custo pode cair justamente quando a disponibilidade piora. As curvas de componente
e pares alcançáveis fornecem o contexto necessário.

## Interpretação e limitações

Nesta topologia, a remoção dirigida cruza o limiar de 50% de pares alcançáveis com
metade das remoções exigidas pela sequência aleatória medida. Isso é compatível com a
fragilidade de malhas concentradas diante de ataques a hubs ou articulações.

O experimento usa uma rede pequena e curada e apenas uma semente aleatória. Além
disso, a semente 42 sorteou Mumbai primeiro, um nó estruturalmente importante, tornando
a falha aleatória inicial mais severa que um sorteio típico poderia ser. Portanto, a
execução demonstra o mecanismo com os dados do projeto, mas não constitui evidência
estatística de que a topologia seja uma rede livre de escala. Comparações probabilísticas
exigiriam várias sementes e intervalos de confiança.
