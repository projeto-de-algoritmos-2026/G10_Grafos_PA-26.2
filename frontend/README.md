# Frontend

Interface do Simulador de Colapso de Internet, construída com HTML, CSS e
JavaScript puro e consumindo a API FastAPI do `backend/`.

## Decisões técnicas

### Visualização com Leaflet

Entre as duas alternativas avaliadas na issue do mapa, foi escolhida a primeira:
[`Leaflet`](https://leafletjs.com/) com uma camada de tiles do OpenStreetMap. Ela
oferece projeção Web Mercator, pan e zoom geográficos, além de posicionar os
`L.circleMarker` diretamente nas coordenadas WGS84. A reescrita da camada de desenho
foi preferida ao fundo estático do `vis-network` porque o zoom continua correto e
permite inspecionar regiões densas sem deslocar os nós de sua posição real.

A versão estável 1.9.4 está copiada em `frontend/vendor/leaflet/`, com sua licença.
Assim, apenas as imagens do mapa dependem de rede externa. Se elas não estiverem
disponíveis, o Leaflet, os nós, os cabos e todos os controles continuam funcionando
sobre uma grade neutra; a interface identifica esse estado como `modo sem tiles`.

### Arquivos estáticos pelo FastAPI

O próprio FastAPI serve o diretório `frontend/`. A interface e a API ficam na
mesma origem, então o JavaScript pode consultar `GET /grafo` com uma URL relativa
e o projeto precisa de apenas um processo local.

## Execução

Na raiz do repositório:

```sh
uv run uvicorn backend.main:app --reload
```

- Interface: <http://localhost:8000/>
- Documentação da API: <http://localhost:8000/docs>

Ao abrir a interface, o JSON retornado por `/grafo` é exibido no console do
navegador. A página também mostra o número de roteadores e conexões. Se a
requisição falhar, uma mensagem de erro é apresentada na própria interface.

## Visualização da topologia

Os nós usam latitude e longitude diretamente no mapa. Seus nomes aparecem no hover,
evitando 100 rótulos simultâneos; zoom e pan permitem inspecionar regiões densas. O
raio dos pontos comuns e a espessura dos cabos diminuem conforme o dataset cresce,
enquanto origem, destino, rotas e cortes mantêm destaque próprio.

Cada cabo é amostrado por interpolação esférica, formando uma aproximação de grande
círculo em vez de um segmento reto. Quando pontos consecutivos passam de +180° para
-180° (ou no sentido contrário), a polilinha é dividida nas duas bordas do mapa. Isso
faz conexões transpacíficas seguirem o caminho curto sem cruzar toda a tela.

As conexões mostram o nome do cabo, a distância e o estado em um tooltip. A
última rota calculada por `POST /rota` é retornada junto de `GET /grafo` e aparece
destacada assim que a página carrega.

## Interação em tempo real

Clicar em um nó ativo o derruba (`POST /nos/{id}/derrubar`); clicar de novo o
restaura (`POST /nos/{id}/restaurar`). A cada mudança, se já houver uma rota
selecionada, ela é recalculada automaticamente (`POST /rota`) e o novo caminho
é destacado no grafo, sem recarregar a página. Se a mudança isolar origem e
destino, a rede particionada aparece como mensagem de aviso no lugar do
caminho.
