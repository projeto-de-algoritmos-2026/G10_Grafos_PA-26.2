# Frontend

Interface do Simulador de Colapso de Internet, construída com HTML, CSS e
JavaScript puro e consumindo a API FastAPI do `backend/`.

## Decisões técnicas

### Visualização com Globe.gl

Foi escolhida a biblioteca [`Globe.gl`](https://globe.gl/) para posicionar a malha
pelas coordenadas WGS84 em um globo 3D e oferecer eventos de clique e seleção sem um
pipeline de build.

A versão `2.27.1` é carregada por CDN, sem npm ou bundler, mantendo a configuração
compatível com o escopo acadêmico do projeto.

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

Os nós usam latitude e longitude diretamente no globo. Seus nomes aparecem sob
ponteiro, evitando 100 rótulos simultâneos; o zoom e a rotação permitem inspecionar
regiões densas. O raio dos pontos comuns e a espessura dos cabos diminuem conforme o
dataset cresce, enquanto origem, destino, rotas e cortes mantêm destaque próprio.

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
