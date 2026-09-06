# Dataset da rede mundial

O simulador usa uma malha mundial curada com **100 nós** e **180 arestas**. Os nós
representam landing points ou agregações metropolitanas próximas; as arestas
representam conectividade lógica por um sistema real de cabo submarino.

## Peso e coordenadas

- Coordenadas: WGS84, obtidas a partir do [GeoNames](https://www.geonames.org/),
  disponibilizado sob CC BY 4.0.
- Peso: distância geodésica Haversine entre as coordenadas exibidas, em quilômetros,
  arredondada ao inteiro mais próximo.
- O peso **não é** capacidade, comprimento físico do cabo nem latência medida.
- A linha desenhada é uma abstração e não reproduz o traçado no fundo do mar.

Essa escolha deixa o cálculo reproduzível sem sugerir uma precisão que as fontes
públicas não oferecem. A própria TeleGeography explica que as linhas de seu mapa são
estilizadas e não representam a geolocalização exata dos sistemas
([FAQ](https://www2.telegeography.com/submarine-cable-faqs-frequently-asked-questions)).

## Cobertura da topologia

| Região | Exemplos de pontos incluídos |
|---|---|
| América do Sul | Las Toninas, Punta del Este, Praia Grande, Fortaleza |
| América do Norte | Myrtle Beach, Virginia Beach, Bellport, Los Angeles, Milton |
| Europa | Bilbao, Bude, Portugal, Marseille, Barcelona, Gênova, Catânia, Irlanda, Islândia, Faroé |
| África Ocidental e Austral | Dakar, Abidjan, Accra, Lomé, Lagos, Libreville, Luanda, Swakopmund, Yzerfontein, Gqeberha |
| África Oriental e Índico | Maputo, Nacala, Mahajanga, Moroni, Carana, Dar es Salaam, Mombasa, Mogadíscio, Berbera, Djibouti |
| Oriente Médio e Sul da Ásia | Port Sudan, Suez, Jeddah, Omã, Golfo Pérsico, Karachi, Mumbai, Matara, Kuakata |
| Sudeste e Leste Asiático | Mianmar, Malásia, Singapura, Tailândia, Vietnã, Brunei, Filipinas, Hong Kong, Shantou, Chiba |
| Oceania e Pacífico | Austrália, Nova Zelândia, Papua-Nova Guiné, Salomão, Guam, Micronésia, Palau, Fiji, Samoa, Tonga, Cook, Niue, Taiti, Tokelau |
| Ártico | Nuuk, Qaqortoq, Maniitsoq, Sisimiut e Aasiaat, ligados a Canadá e Islândia |

A expansão preserva um grafo esparso, mas adiciona ciclos regionais e conexões entre
continentes. Isso cria gargalos geográficos reais sem transformar a visualização em
um grafo completo artificial.

## Sistemas e fontes

Cada entrada abaixo é uma página pública usada para conferir os landing points. Todas
foram consultadas em **6 de setembro de 2026**.

| Sistema | Fonte |
|---|---|
| Firmina | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/firmina) |
| Monet | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/monet) |
| EllaLink | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/ellalink) |
| BRUSA | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/brusa) |
| MAREA | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/marea) |
| Grace Hopper | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/grace-hopper) |
| 2Africa | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/2africa) |
| WACS | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/west-africa-cable-system-wacs) |
| Equiano | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/equiano) |
| EASSy | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/eastern-africa-submarine-system-eassy) |
| SeaMeWe-5 | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/seamewe-5) |
| India Asia Xpress | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/india-asia-xpress-iax) |
| Asia Direct Cable | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/asia-direct-cable-adc) |
| Asia-America Gateway | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/asia-america-gateway-aag-cable-system) |
| SEA-US | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/sea-us) |
| SJC2 | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/southeast-asia-japan-cable-2-sjc2) |
| INDIGO-West | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/indigo-west) |
| INDIGO-Central | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/indigo-central) |
| Coral Sea Cable System | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/coral-sea-cable-system-cs) |
| Hawaiki | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/hawaiki) |
| Manatua | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/manatua) |
| Tui-Samoa | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/tui-samoa) |
| Southern Cross NEXT | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/southern-cross-next) |
| JUPITER | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/jupiter) |
| Greenland Connect | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/greenland-connect) |
| Greenland Connect North | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/greenland-connect-north) |
| IRIS | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/iris) |
| AEC-1 | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/aec-1) |
| FARICE-1 | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/farice-1) |
| Europe India Gateway | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/europe-india-gateway-eig) |
| Africa Coast to Europe | [TeleGeography](https://www.submarinecablemap.com/submarine-cable/africa-coast-to-europe-ace) |

O JSON registra a fonte de cada aresta individualmente. Nenhum GeoJSON ou dataset
geocodificado bruto da TeleGeography foi copiado ou redistribuído.

## Agregações declaradas

Para evitar nós quase sobrepostos, alguns landing points próximos compartilham um nó
visual: Singapura (Tuas/Changi), Chiba (Chikura/Maruyama), Portugal (Sines/Sesimbra),
Marseille/Toulon, Suez/Zafarana, Jeddah/Yanbu, Bellport/Shirley e Irlanda oeste
(Galway/Killala). O nó Islândia agrega landing points do sul e leste do país. Uma
aresta afirma que os dois pontos são atendidos pelo sistema nomeado; não que sejam as
duas pontas de um único segmento físico sem ramificações.

## Validação e limites

O schema aceita de 15 a 2.000 nós como limite de sanidade. O carregamento continua
rejeitando:

- IDs ou arestas não direcionadas duplicadas;
- coordenadas fora dos limites WGS84;
- self-loops e referências a nós inexistentes;
- pesos não positivos ou incoerentes com Haversine em mais de 1 km;
- fontes desconhecidas;
- grafo desconexo.

Validação manual/CI:

```sh
uv run python scripts/validar_rede.py
```
