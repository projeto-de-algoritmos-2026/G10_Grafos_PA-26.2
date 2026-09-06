const elements = {
  status: document.querySelector("#api-status"),
  error: document.querySelector("#api-error"),
  actionError: document.querySelector("#action-error"),
  network: document.querySelector("#network"),
  nodeCount: document.querySelector("#node-count"),
  edgeCount: document.querySelector("#edge-count"),
  libraryStatus: document.querySelector("#library-status"),
  routeDescription: document.querySelector("#route-description"),
  routeDetails: document.querySelector("#route-details"),
  criticalityDetails: document.querySelector("#criticality-details"),
  originSelect: document.querySelector("#origin-select"),
  destinationSelect: document.querySelector("#destination-select"),
  algoDijkstra: document.querySelector("#algo-dijkstra"),
  algoBellmanFord: document.querySelector("#algo-bellman-ford"),
  resetButton: document.querySelector("#reset-button"),
};

const PROJECTION_SCALE = 6;
const ROUTE_FLASH_COLOR = "#fff3b0";
const ROUTE_FLASH_DURATION_MS = 500;
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
  articulation: "#ff8f3f",
  bridge: "#ff8f3f",
};
const BRIDGE_DASH_PATTERN = [2, 6];

let visualization;
let resizeObserver;
let nodesDataSet;
let edgesDataSet;
let currentGraph;
let currentCriticidade = { articulacoes: [], pontes: [], componentes: 0 };

const currentSelection = {
  origem: null,
  destino: null,
  algoritmo: "dijkstra",
};

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

function articulationPointIds() {
  return new Set(currentCriticidade.articulacoes);
}

function bridgeEdgeIds() {
  return new Set(currentCriticidade.pontes.map((ponte) => edgeKey(ponte.origem, ponte.destino)));
}

function toVisNodes(graph) {
  const articulationPoints = articulationPointIds();

  return graph.nos.map((node) => {
    const position = projectCoordinates(node);
    const color = nodeColors(node, graph.rota_atual);
    const isEndpoint =
      graph.rota_atual?.origem === node.id || graph.rota_atual?.destino === node.id;
    const isArticulation = articulationPoints.has(node.id);
    const border = isArticulation ? COLORS.articulation : color.border;

    return {
      id: node.id,
      label: node.nome.split(",")[0],
      title: `${node.nome}<br>${node.lat.toFixed(2)}°, ${node.lon.toFixed(2)}°<br>${
        node.ativo ? "Ativo" : "Derrubado"
      }${isArticulation ? "<br>Ponto de articulação" : ""}`,
      ...position,
      fixed: { x: true, y: true },
      size: isEndpoint ? 18 : 13,
      borderWidth: isArticulation ? 4 : isEndpoint ? 4 : 2,
      color: {
        background: color.background,
        border,
        highlight: { background: color.background, border },
        hover: { background: color.background, border },
      },
    };
  });
}

function toVisEdges(graph) {
  const routeEdges = currentRouteEdges(graph.rota_atual);
  const bridgeEdges = bridgeEdgeIds();

  return graph.arestas.map((edge) => {
    const id = edgeKey(edge.origem, edge.destino);
    const belongsToRoute = routeEdges.has(id);
    const isBridge = bridgeEdges.has(id);
    const color = belongsToRoute
      ? COLORS.route
      : isBridge
        ? COLORS.bridge
        : edge.ativo
          ? COLORS.edge
          : COLORS.edgeDown;

    return {
      id,
      from: edge.origem,
      to: edge.destino,
      title: `${edge.cabo}<br>${Math.round(edge.peso).toLocaleString("pt-BR")} km<br>${
        edge.ativo ? "Ativa" : "Derrubada"
      }${isBridge ? "<br>Ponte (ponto único de falha)" : ""}`,
      width: belongsToRoute ? 5 : isBridge ? 2.5 : edge.ativo ? 1.5 : 2,
      color: { color, highlight: color, hover: color, opacity: edge.ativo ? 1 : 0.75 },
      dashes: isBridge && !belongsToRoute ? BRIDGE_DASH_PATTERN : !edge.ativo,
      smooth: false,
      chosen: false,
    };
  });
}

function renderRouteSummary(graph) {
  const route = graph.rota_atual;
  elements.routeDetails.classList.remove("route-details-warning");

  if (!route) {
    elements.routeDescription.textContent = "Nenhuma rota selecionada.";
    elements.routeDetails.textContent = "Selecione origem e destino para calcular uma rota.";
    return;
  }

  const names = new Map(graph.nos.map((node) => [node.id, node.nome]));
  const origin = names.get(route.origem) ?? route.origem;
  const destination = names.get(route.destino) ?? route.destino;
  elements.routeDescription.textContent = `${origin} → ${destination}`;

  if (!route.encontrada) {
    elements.routeDetails.textContent = `Rede particionada: não há caminho disponível entre ${origin} e ${destination} no momento.`;
    elements.routeDetails.classList.add("route-details-warning");
    return;
  }

  const hops = Math.max(route.caminho.length - 1, 0);
  const algorithm = route.algoritmo === "bellman_ford" ? "Bellman-Ford" : "Dijkstra";
  const cost = Math.round(route.custo).toLocaleString("pt-BR");
  elements.routeDetails.textContent = `${algorithm} · ${cost} km · ${hops} ${
    hops === 1 ? "salto" : "saltos"
  }`;
}

function buildNetwork(graph) {
  if (!window.vis?.Network || !window.vis?.DataSet) {
    throw new Error("A biblioteca de visualização não pôde ser carregada.");
  }

  visualization?.destroy();
  resizeObserver?.disconnect();

  nodesDataSet = new window.vis.DataSet(toVisNodes(graph));
  edgesDataSet = new window.vis.DataSet(toVisEdges(graph));
  const data = { nodes: nodesDataSet, edges: edgesDataSet };
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
  visualization.on("click", handleNetworkClick);

  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => visualization?.fit({ animation: false }));
    resizeObserver.observe(elements.network);
  }
}

function updateNetwork(graph) {
  nodesDataSet.update(toVisNodes(graph));
  edgesDataSet.update(toVisEdges(graph));
}

function flashRouteEdges(edgeIds) {
  if (!edgeIds.length) {
    return;
  }
  edgesDataSet.update(
    edgeIds.map((id) => ({
      id,
      width: 6,
      color: { color: ROUTE_FLASH_COLOR, highlight: ROUTE_FLASH_COLOR, hover: ROUTE_FLASH_COLOR },
    })),
  );
  window.setTimeout(() => updateNetwork(currentGraph), ROUTE_FLASH_DURATION_MS);
}

async function handleNetworkClick(params) {
  if (!params.nodes.length) {
    return;
  }
  await toggleNode(params.nodes[0]);
}

async function toggleNode(nodeId) {
  const node = currentGraph.nos.find((candidate) => candidate.id === nodeId);
  if (!node) {
    return;
  }
  const action = node.ativo ? "derrubar" : "restaurar";

  try {
    clearActionError();
    const response = await fetch(`/nos/${encodeURIComponent(nodeId)}/${action}`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`A API respondeu com HTTP ${response.status}.`);
    }
    currentGraph = await fetchGraph();
    currentCriticidade = await fetchCriticidade();
    await recalculateAndRender();
  } catch (error) {
    showActionError(error);
  }
}

async function refreshRoute() {
  const previousRouteEdges = currentRouteEdges(currentGraph.rota_atual);

  if (!currentSelection.origem || !currentSelection.destino) {
    currentGraph.rota_atual = null;
    return previousRouteEdges;
  }

  const response = await fetch("/rota", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origem: currentSelection.origem,
      destino: currentSelection.destino,
      algoritmo: currentSelection.algoritmo,
    }),
  });
  if (!response.ok) {
    throw new Error(`A API respondeu com HTTP ${response.status}.`);
  }
  const rota = await response.json();
  currentGraph.rota_atual = {
    origem: currentSelection.origem,
    destino: currentSelection.destino,
    ...rota,
  };
  return previousRouteEdges;
}

async function recalculateAndRender() {
  const previousRouteEdges = await refreshRoute();
  updateNetwork(currentGraph);
  renderRouteSummary(currentGraph);
  renderCriticalitySummary();

  const newRouteEdges = [...currentRouteEdges(currentGraph.rota_atual)].filter(
    (edgeId) => !previousRouteEdges.has(edgeId),
  );
  flashRouteEdges(newRouteEdges);
}

function renderCriticalitySummary() {
  const routerCount = currentCriticidade.articulacoes.length;
  const cableCount = currentCriticidade.pontes.length;

  if (routerCount === 0 && cableCount === 0) {
    elements.criticalityDetails.textContent =
      "Nenhum ponto único de falha identificado na rede disponível.";
    return;
  }

  const routerLabel = routerCount === 1 ? "roteador" : "roteadores";
  const cableLabel = cableCount === 1 ? "cabo" : "cabos";
  const parts = [];
  if (routerCount > 0) {
    parts.push(`${routerCount} ${routerLabel}`);
  }
  if (cableCount > 0) {
    parts.push(`${cableCount} ${cableLabel}`);
  }
  const verb = routerCount + cableCount === 1 ? "é" : "são";
  elements.criticalityDetails.textContent = `${parts.join(" e ")} ${verb} ponto único de falha.`;
}

function populateEndpointSelects(graph) {
  const options = graph.nos
    .slice()
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"))
    .map((node) => `<option value="${node.id}">${node.nome}</option>`)
    .join("");

  elements.originSelect.innerHTML = `<option value="">Selecione…</option>${options}`;
  elements.destinationSelect.innerHTML = `<option value="">Selecione…</option>${options}`;
  elements.originSelect.value = currentSelection.origem ?? "";
  elements.destinationSelect.value = currentSelection.destino ?? "";
}

function setAlgorithm(algoritmo) {
  currentSelection.algoritmo = algoritmo;
  elements.algoDijkstra.setAttribute("aria-pressed", String(algoritmo === "dijkstra"));
  elements.algoBellmanFord.setAttribute("aria-pressed", String(algoritmo === "bellman_ford"));
}

async function resetSimulation() {
  try {
    clearActionError();
    const downNodes = currentGraph.nos.filter((node) => !node.ativo);
    const downEdges = currentGraph.arestas.filter((edge) => !edge.ativo);
    await Promise.all([
      ...downNodes.map((node) =>
        fetch(`/nos/${encodeURIComponent(node.id)}/restaurar`, { method: "POST" }),
      ),
      ...downEdges.map((edge) =>
        fetch("/arestas/restaurar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ origem: edge.origem, destino: edge.destino }),
        }),
      ),
    ]);
    currentGraph = await fetchGraph();
    currentCriticidade = await fetchCriticidade();
    await recalculateAndRender();
  } catch (error) {
    showActionError(error);
  }
}

function bindControls() {
  elements.originSelect.addEventListener("change", async (event) => {
    currentSelection.origem = event.target.value || null;
    try {
      clearActionError();
      await recalculateAndRender();
    } catch (error) {
      showActionError(error);
    }
  });

  elements.destinationSelect.addEventListener("change", async (event) => {
    currentSelection.destino = event.target.value || null;
    try {
      clearActionError();
      await recalculateAndRender();
    } catch (error) {
      showActionError(error);
    }
  });

  elements.algoDijkstra.addEventListener("click", async () => {
    setAlgorithm("dijkstra");
    try {
      clearActionError();
      await recalculateAndRender();
    } catch (error) {
      showActionError(error);
    }
  });

  elements.algoBellmanFord.addEventListener("click", async () => {
    setAlgorithm("bellman_ford");
    try {
      clearActionError();
      await recalculateAndRender();
    } catch (error) {
      showActionError(error);
    }
  });

  elements.resetButton.addEventListener("click", resetSimulation);
}

function clearActionError() {
  elements.actionError.hidden = true;
  elements.actionError.textContent = "";
}

function showActionError(error) {
  console.error("Falha ao aplicar mudança na simulação:", error);
  elements.actionError.textContent = `Não foi possível aplicar a mudança. ${error.message}`;
  elements.actionError.hidden = false;
}

function showGraph(graph) {
  currentGraph = graph;
  currentSelection.origem = graph.rota_atual?.origem ?? currentSelection.origem;
  currentSelection.destino = graph.rota_atual?.destino ?? currentSelection.destino;
  currentSelection.algoritmo = graph.rota_atual?.algoritmo ?? currentSelection.algoritmo;

  buildNetwork(graph);
  populateEndpointSelects(graph);
  setAlgorithm(currentSelection.algoritmo);
  bindControls();
  renderRouteSummary(graph);
  renderCriticalitySummary();
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

async function fetchCriticidade() {
  const response = await fetch("/analise/criticidade", {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`A API respondeu com HTTP ${response.status}.`);
  }

  return response.json();
}

async function initialize() {
  try {
    const graph = await fetchGraph();
    console.info("Grafo recebido da API:", graph);
    currentCriticidade = await fetchCriticidade();
    showGraph(graph);
  } catch (error) {
    showLoadError(error);
  }
}

initialize();
