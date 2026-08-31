# Dataset da rede mundial

O simulador usa uma malha mundial curada com **26 nós** e **30 arestas**. Os nós
representam landing points ou agregações metropolitanas de landing points próximos;
as arestas representam conectividade lógica por um sistema real de cabo em serviço.

## Peso e coordenadas

- Coordenadas: WGS84, obtidas a partir do [GeoNames](https://www.geonames.org/),
  disponibilizado sob CC BY 4.0.
- Peso: distância geodésica Haversine entre as coordenadas exibidas, em quilômetros,
  arredondada ao inteiro mais próximo.
- O peso **não é** o comprimento físico do cabo nem uma medição de latência.
- A linha desenhada entre os nós é uma abstração visual. Ela não reproduz o traçado
  no fundo do mar.

Essa escolha deixa o cálculo reproduzível sem sugerir uma precisão de latência ou de
rota física que as fontes públicas não oferecem. A própria TeleGeography explica que
as linhas do mapa público são estilizadas e não representam a geolocalização exata dos
sistemas ([FAQ](https://www2.telegeography.com/submarine-cable-faqs-frequently-asked-questions)).

## Topologia

| Região | Pontos selecionados |
|---|---|
| América do Sul | Las Toninas, Punta del Este, Praia Grande, Fortaleza |
| América do Norte | Myrtle Beach, Virginia Beach, Bellport/Nova York, Los Angeles |
| Europa | Bilbao, Bude, Sines, Carcavelos, Marseille |
| África e Oriente Médio | Accra, Lagos, Yzerfontein, Maputo, Mombasa, Djibouti, Jeddah |
| Ásia e Oceania | Mumbai, Singapura, Perth, Sydney, Auckland, Chiba |

A seleção mantém o grafo esparso, mas inclui ciclos nos eixos Atlântico, Europa–Ásia
e Pacífico. Assim, uma falha isolada normalmente força um desvio, enquanto uma
combinação deliberada de falhas pode particionar a rede.

## Sistemas e fontes

| Sistema | Fonte dos landing points |
|---|---|
| Firmina | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/firmina) |
| Monet | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/monet) |
| EllaLink | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/ellalink) |
| BRUSA | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/brusa) |
| MAREA | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/marea) |
| Grace Hopper | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/grace-hopper) |
| 2Africa | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/2africa) |
| India Asia Xpress | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/india-asia-xpress-iax) |
| INDIGO-West | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/indigo-west) |
| INDIGO-Central | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/indigo-central) |
| Southern Cross NEXT | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/southern-cross-next) |
| JUPITER | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/jupiter) |
| SJC2 | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/southeast-asia-japan-cable-2-sjc2) |
| Europe India Gateway | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/europe-india-gateway-eig) |
| Africa Coast to Europe | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/africa-coast-to-europe-ace) |

As fontes foram consultadas em 30 de agosto de 2026. O JSON registra a fonte de cada
aresta individualmente. Nenhum GeoJSON ou dataset geocodificado da TeleGeography foi
copiado ou redistribuído.

## Validação e limitações

O carregamento rejeita:

- quantidade fora de 15–30 nós;
- IDs ou arestas duplicadas;
- coordenadas fora dos limites WGS84;
- self-loops e referências a nós inexistentes;
- pesos não positivos ou incoerentes com Haversine;
- fontes desconhecidas;
- grafo desconexo.

Validação manual/CI:

```sh
uv run python scripts/validar_rede.py
```

Landing stations próximas foram agregadas em alguns nós metropolitanos, como
Singapura (Tuas/Changi) e Chiba (Chikura/Maruyama). Uma aresta informa que os dois
pontos são atendidos pelo sistema nomeado; ela não afirma que sejam as duas pontas de
um único segmento físico sem ramificações.
