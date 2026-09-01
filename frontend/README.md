# Frontend

Interface do Simulador de Colapso de Internet, construída com HTML, CSS e
JavaScript puro e consumindo a API FastAPI do `backend/`.

## Decisões técnicas

### Visualização com vis-network

Foi escolhida a biblioteca [`vis-network`](https://visjs.github.io/vis-network/)
em vez de D3.js. Ela oferece layout físico de grafos pronto e uma API direta
para eventos de clique e seleção. Isso reduz a quantidade de código necessária
para renderizar a topologia e implementar as interações previstas nas issues
`#10` e `#11`.

A versão `9.1.9` é carregada por CDN, sem npm ou bundler, mantendo a configuração
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

Os nós são posicionados pelo `vis-network` com uma projeção equiretangular
simples: longitude no eixo horizontal e latitude invertida no eixo vertical. A
física da biblioteca fica desativada para preservar a posição geográfica.

As conexões mostram o nome do cabo, a distância e o estado em um tooltip. A
última rota calculada por `POST /rota` é retornada junto de `GET /grafo` e aparece
destacada depois que a página é recarregada.

As interações para derrubar e restaurar nós e cabos serão implementadas
separadamente na issue `#11`.
