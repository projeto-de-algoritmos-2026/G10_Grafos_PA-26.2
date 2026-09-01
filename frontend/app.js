const elements = {
  status: document.querySelector("#api-status"),
  error: document.querySelector("#api-error"),
  network: document.querySelector("#network"),
  nodeCount: document.querySelector("#node-count"),
  edgeCount: document.querySelector("#edge-count"),
  libraryStatus: document.querySelector("#library-status"),
  routeDescription: document.querySelector("#route-description"),
  routeDetails: document.querySelector("#route-details"),
};

const PROJECTION_SCALE = 6;
const COLORS = {
  node: "#49bfa1",
  nodeBorder: "#b5f4e3",
  down: "#d65f67",
  downBorder: "#ffb5ba",
  origin: "#42df88",
  originBorder: "#d0ffe3",
  destination: "#f4bd5f",
  destinationBorder: "#ffedbd",
  sameEndpoint: "#b993ff",
  edge: "#52736d",
  edgeDown: "#b2525a",
  route: "#ffd166",
};

let visualization;
let resizeObserver;

function edgeKey(first, second) {
  return [first, second].sort().join("::");
}

function currentRouteEdges(route) {
  const edges = new Set();

  if (!route?.encontrada) {
    return edges;
  }

  for (let index = 0; index < route.caminho.length - 1; index += 1) {
    edges.add(edgeKey(route.caminho[index], route.caminho[index + 1]));
  }

  return edges;
}

function projectCoordinates(node) {
  return {
    x: node.lon * PROJECTION_SCALE,
    y: -node.lat * PROJECTION_SCALE,
  };
}

function nodeColors(node, route) {
  const isOrigin = route?.origem === node.id;
  const isDestination = route?.destino === node.id;

  if (isOrigin && isDestination) {
    return { background: COLORS.sameEndpoint, border: "#eadcff" };
  }
  if (isOrigin) {
    return { background: COLORS.origin, border: COLORS.originBorder };
  }
  if (isDestination) {
    return { background: COLORS.destination, border: COLORS.destinationBorder };
  }
  if (!node.ativo) {
    return { background: COLORS.down, border: COLORS.downBorder };
  }
  return { background: COLORS.node, border: COLORS.nodeBorder };
}

function toVisNodes(graph) {
  return graph.nos.map((node) => {
    const position = projectCoordinates(node);
    const color = nodeColors(node, graph.rota_atual);
    const isEndpoint =
      graph.rota_atual?.origem === node.id || graph.rota_atual?.destino === node.id;

    return {
      id: node.id,
      label: node.nome.split(",")[0],
      title: `${node.nome}<br>${node.lat.toFixed(2)}°, ${node.lon.toFixed(2)}°<br>${
        node.ativo ? "Ativo" : "Derrubado"
      }`,
      ...position,
      fixed: { x: true, y: true },
      size: isEndpoint ? 18 : 13,
      borderWidth: isEndpoint ? 4 : 2,
      color: {
        ...color,
        highlight: color,
        hover: color,
      },
    };
  });
}

function toVisEdges(graph) {
  const routeEdges = currentRouteEdges(graph.rota_atual);

  return graph.arestas.map((edge) => {
    const id = edgeKey(edge.origem, edge.destino);
    const belongsToRoute = routeEdges.has(id);
    const color = belongsToRoute
      ? COLORS.route
      : edge.ativo
        ? COLORS.edge
        : COLORS.edgeDown;

    return {
      id,
      from: edge.origem,
      to: edge.destino,
      title: `${edge.cabo}<br>${Math.round(edge.peso).toLocaleString("pt-BR")} km<br>${
        edge.ativo ? "Ativa" : "Derrubada"
      }`,
      width: belongsToRoute ? 5 : edge.ativo ? 1.5 : 2,
      color: { color, highlight: color, hover: color, opacity: edge.ativo ? 1 : 0.75 },
      dashes: !edge.ativo,
      smooth: false,
      chosen: false,
    };
  });
}

function renderRouteSummary(graph) {
  const route = graph.rota_atual;

  if (!route) {
    elements.routeDescription.textContent = "Nenhuma rota foi calculada ainda.";
    elements.routeDetails.innerHTML =
      'Use o endpoint <code>POST /rota</code> e recarregue esta página.';
    return;
  }

  const names = new Map(graph.nos.map((node) => [node.id, node.nome]));
  const origin = names.get(route.origem) ?? route.origem;
  const destination = names.get(route.destino) ?? route.destino;
  elements.routeDescription.textContent = `${origin} → ${destination}`;

  if (!route.encontrada) {
    elements.routeDetails.textContent = "Não existe caminho disponível entre esses pontos.";
    return;
  }

  const hops = Math.max(route.caminho.length - 1, 0);
  const algorithm = route.algoritmo === "bellman_ford" ? "Bellman-Ford" : "Dijkstra";
  const cost = Math.round(route.custo).toLocaleString("pt-BR");
  elements.routeDetails.textContent = `${algorithm} · ${cost} km · ${hops} ${
    hops === 1 ? "salto" : "saltos"
  }`;
}

function renderNetwork(graph) {
  if (!window.vis?.Network || !window.vis?.DataSet) {
    throw new Error("A biblioteca de visualização não pôde ser carregada.");
  }

  visualization?.destroy();
  resizeObserver?.disconnect();

  const data = {
    nodes: new window.vis.DataSet(toVisNodes(graph)),
    edges: new window.vis.DataSet(toVisEdges(graph)),
  };
  const options = {
    autoResize: true,
    physics: false,
    layout: { improvedLayout: false },
    nodes: {
      shape: "dot",
      font: { color: "#e8f5f1", size: 13, strokeWidth: 4, strokeColor: "#071412" },
    },
    edges: { font: { color: "#e8f5f1" } },
    interaction: {
      dragNodes: false,
      hover: true,
      keyboard: true,
      navigationButtons: true,
      tooltipDelay: 120,
    },
  };

  visualization = new window.vis.Network(elements.network, data, options);
  visualization.fit({ animation: false });

  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => visualization?.fit({ animation: false }));
    resizeObserver.observe(elements.network);
  }
}

function showGraph(graph) {
  renderNetwork(graph);
  renderRouteSummary(graph);
  elements.nodeCount.textContent = graph.nos.length;
  elements.edgeCount.textContent = graph.arestas.length;
  elements.libraryStatus.textContent = "vis-network ativa";
  elements.status.textContent = "API conectada";
  elements.status.className = "status status-success";
  elements.error.hidden = true;
  elements.network.setAttribute("aria-busy", "false");
}

function showLoadError(error) {
  console.error("Não foi possível renderizar o grafo:", error);
  elements.status.textContent = "Falha ao carregar";
  elements.status.className = "status status-error";
  elements.error.textContent = `Não foi possível carregar a topologia. ${error.message}`;
  elements.error.hidden = false;
  visualization?.destroy();
  resizeObserver?.disconnect();
  elements.network.setAttribute("aria-busy", "false");
  elements.network.innerHTML = `
    <div class="network-placeholder">
      <p>Os dados da rede não estão disponíveis no momento.</p>
    </div>
  `;
}

async function fetchGraph() {
  const response = await fetch("/grafo", { headers: { Accept: "application/json" } });

  if (!response.ok) {
    throw new Error(`A API respondeu com HTTP ${response.status}.`);
  }

  const graph = await response.json();

  if (!Array.isArray(graph.nos) || !Array.isArray(graph.arestas)) {
    throw new Error("A resposta da API não possui o formato esperado.");
  }

  return graph;
}

async function initialize() {
  try {
    const graph = await fetchGraph();
    console.info("Grafo recebido da API:", graph);
    showGraph(graph);
  } catch (error) {
    showLoadError(error);
  }
}

initialize();
