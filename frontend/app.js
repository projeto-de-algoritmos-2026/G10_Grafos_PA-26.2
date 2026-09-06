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
  routeRedundancy: document.querySelector("#route-redundancy"),
  criticalityDetails: document.querySelector("#criticality-details"),
  minCutDetails: document.querySelector("#min-cut-details"),
  originSelect: document.querySelector("#origin-select"),
  destinationSelect: document.querySelector("#destination-select"),
  algoDijkstra: document.querySelector("#algo-dijkstra"),
  algoBellmanFord: document.querySelector("#algo-bellman-ford"),
  algoAStar: document.querySelector("#algo-a-star"),
  minCutButton: document.querySelector("#min-cut-button"),
  resetButton: document.querySelector("#reset-button"),
  tracePlayButton: document.querySelector("#trace-play-button"),
  traceStepButton: document.querySelector("#trace-step-button"),
  traceSpeed: document.querySelector("#trace-speed"),
  traceStatus: document.querySelector("#trace-status"),
};

const ALGORITHM_LABELS = {
  dijkstra: "Dijkstra",
  bellman_ford: "Bellman-Ford",
  a_star: "A*",
};

const ROUTE_FLASH_COLOR = "#f2e6c2";
const ROUTE_FLASH_DURATION_MS = 500;
// Numero total de rotas pedidas ao endpoint de Yen: a melhor mais 3 de contingencia.
const ALTERNATE_ROUTES_K = 4;
const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const EMPTY_TILE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'/%3E";
const COLORS = {
  node: "#6fb98a",
  down: "#cf7a72",
  origin: "#8fd8a8",
  destination: "#d2b06a",
  sameEndpoint: "#7fb8c9",
  edge: "#3f7a5c",
  edgeDown: "#6b3b38",
  route: "#e0c07a",
  alternateRoute: "rgba(224, 192, 122, 0.4)",
  articulation: "#d2a24c",
  bridge: "#d2a24c",
  minCut: "#dc626c",
};

let mapInstance;
let tileLayer;
let cableLayer;
let articulationLayer;
let nodeLayer;
let resizeObserver;
let currentGraph;
let currentCriticidade = { articulacoes: [], pontes: [], componentes: 0 };
let flashedEdgeIds = new Set();
// Rotas 2..k devolvidas por /rotas (a melhor fica de fora, ja coberta por rota_atual).
let currentAlternateRoutes = [];
let currentRedundancyPercent = null;
let currentMinCut = null;
let currentMinCutEdgeIds = new Set();
let currentTrace = [];
let currentTraceIndex = 0;
let traceTimer;
let traceEvent;

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

function alternateRouteEdgeInfo(routes) {
  const info = new Map();

  routes.forEach((route, offset) => {
    const rank = offset + 2; // a melhor rota (rank 1) nao entra em `routes`.
    for (let index = 0; index < route.caminho.length - 1; index += 1) {
      const id = edgeKey(route.caminho[index], route.caminho[index + 1]);
      if (!info.has(id)) {
        info.set(id, { rank, custo: route.custo });
      }
    }
  });

  return info;
}

function articulationPointIds() {
  return new Set(currentCriticidade.articulacoes);
}

function bridgeEdgeIds() {
  return new Set(currentCriticidade.pontes.map((ponte) => edgeKey(ponte.origem, ponte.destino)));
}

function pointColorFor(node, route) {
  if (traceEvent?.tipo === "visita" && traceEvent.no === node.id) {
    return "#e0c07a";
  }
  const isOrigin = route?.origem === node.id;
  const isDestination = route?.destino === node.id;

  if (isOrigin && isDestination) {
    return COLORS.sameEndpoint;
  }
  if (isOrigin) {
    return COLORS.origin;
  }
  if (isDestination) {
    return COLORS.destination;
  }
  if (!node.ativo) {
    return COLORS.down;
  }
  return COLORS.node;
}

function toMapPoints(graph) {
  const articulationPoints = articulationPointIds();
  const regularRadius = Math.max(3, 5 * Math.sqrt(26 / graph.nos.length));

  return graph.nos.map((node) => {
    const route = graph.rota_atual;
    const isEndpoint = route?.origem === node.id || route?.destino === node.id;
    const isArticulation = articulationPoints.has(node.id);

    return {
      id: node.id,
      lat: node.lat,
      lng: node.lon,
      nome: node.nome,
      ativo: node.ativo,
      isArticulation,
      color: pointColorFor(node, route),
      radius: isEndpoint ? 7 : regularRadius,
    };
  });
}

function toMapCables(graph) {
  const nodesById = new Map(graph.nos.map((node) => [node.id, node]));
  const routeEdges = currentRouteEdges(graph.rota_atual);
  const bridgeEdges = bridgeEdgeIds();
  const alternateEdges = alternateRouteEdgeInfo(currentAlternateRoutes);
  const densityScale = Math.max(0.55, Math.sqrt(30 / graph.arestas.length));

  return graph.arestas
    .map((edge) => {
      const origin = nodesById.get(edge.origem);
      const destination = nodesById.get(edge.destino);
      if (!origin || !destination) {
        return null;
      }

      const id = edgeKey(edge.origem, edge.destino);
      const belongsToRoute = routeEdges.has(id);
      const isBridge = bridgeEdges.has(id);
      const isFlashed = flashedEdgeIds.has(id);
      const isMinCut = currentMinCutEdgeIds.has(id);
      const isTraceEdge =
        traceEvent &&
        traceEvent.tipo === "relaxa" &&
        edgeKey(traceEvent.origem, traceEvent.destino) === id;
      const alternate = belongsToRoute ? undefined : alternateEdges.get(id);

      let color = edge.ativo ? COLORS.edge : COLORS.edgeDown;
      if (isBridge) {
        color = COLORS.bridge;
      }
      if (alternate) {
        color = COLORS.alternateRoute;
      }
      if (belongsToRoute) {
        color = COLORS.route;
      }
      if (isFlashed) {
        color = ROUTE_FLASH_COLOR;
      }
      if (isMinCut) {
        color = COLORS.minCut;
      }
      if (isTraceEdge) {
        color = "#e0c07a";
      }

      const dashArray = !edge.ativo ? "4 6" : isBridge ? "2 5" : null;
      const priority = isMinCut
        ? 5
        : isFlashed
          ? 4
          : belongsToRoute
            ? 3
            : alternate
              ? 2
              : isBridge
                ? 1
                : 0;

      return {
        id,
        cabo: edge.cabo,
        peso: edge.peso,
        ativo: edge.ativo,
        isBridge,
        isMinCut,
        alternateRank: alternate?.rank,
        alternateCusto: alternate?.custo,
        color,
        segments: window.MapGeometry.greatCircleSegments(
          { lat: origin.lat, lng: origin.lon },
          { lat: destination.lat, lng: destination.lon },
        ),
        weight: isMinCut
          ? 5
          : belongsToRoute || isFlashed
            ? 4
            : alternate
              ? 1
              : isBridge
                ? 2.5
                : Math.max(1, 1.6 * densityScale),
        opacity: alternate ? 0.45 : edge.ativo ? 0.82 : 0.62,
        dashArray,
        priority,
      };
    })
    .filter(Boolean);
}

function pointLabel(point) {
  return `${point.nome}<br>${point.lat.toFixed(2)}°, ${point.lng.toFixed(2)}°<br>${
    point.ativo ? "Ativo" : "Derrubado"
  }${point.isArticulation ? "<br>Ponto de articulação" : ""}`;
}

function cableLabel(cable) {
  const alternateInfo = cable.alternateRank
    ? `<br>Rota alternativa #${cable.alternateRank} · ${Math.round(cable.alternateCusto).toLocaleString(
        "pt-BR",
      )} km`
    : "";
  return `${cable.cabo}<br>${Math.round(cable.peso).toLocaleString("pt-BR")} km<br>${
    cable.ativo ? "Ativa" : "Derrubada"
  }${cable.isBridge ? "<br>Ponte (ponto único de falha)" : ""}${
    cable.isMinCut ? "<br>Parte do corte mínimo calculado" : ""
  }${alternateInfo}`;
}

function renderRouteSummary(graph) {
  const route = graph.rota_atual;
  elements.routeDetails.classList.remove("route-details-warning");
  elements.routeRedundancy.textContent = "";

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
  const algorithm = ALGORITHM_LABELS[route.algoritmo] ?? route.algoritmo;
  const cost = Math.round(route.custo).toLocaleString("pt-BR");
  elements.routeDetails.textContent = `${algorithm} · ${cost} km · ${hops} ${
    hops === 1 ? "salto" : "saltos"
  } · ${route.nos_expandidos} nós expandidos · ${
    route.arestas_relaxadas
  } arestas relaxadas`;
  elements.routeRedundancy.textContent = redundancyText();
}

function redundancyText() {
  if (currentRedundancyPercent === null) {
    return currentAlternateRoutes.length === 0
      ? "Sem rota de contingência: este par não tem caminho alternativo simples."
      : "";
  }
  const percent = currentRedundancyPercent.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  return `Redundância do par: a 2ª melhor rota (algoritmo de Yen) custa ${percent}% a mais que a ótima.`;
}

function resizeMap() {
  if (!mapInstance) {
    return;
  }
  mapInstance.invalidateSize({ animate: false });
}

function setTileStatus(available) {
  elements.network.classList.toggle("network-canvas-offline", !available);
  elements.libraryStatus.textContent = available
    ? "Leaflet · mapa carregado"
    : "Leaflet · modo sem tiles";
}

function buildMap(graph) {
  if (typeof window.L?.map !== "function" || !window.MapGeometry) {
    throw new Error("A biblioteca de visualização não pôde ser carregada.");
  }

  resizeObserver?.disconnect();
  mapInstance?.remove();
  elements.network.innerHTML = "";
  mapInstance = window.L.map(elements.network, {
    minZoom: 1,
    maxZoom: 10,
    maxBounds: [
      [-85, -180],
      [85, 180],
    ],
    maxBoundsViscosity: 1,
    preferCanvas: true,
    worldCopyJump: false,
  });

  window.L.control.scale({ imperial: false, position: "bottomleft" }).addTo(mapInstance);
  tileLayer = window.L.tileLayer(TILE_URL, {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    errorTileUrl: EMPTY_TILE,
    maxZoom: 10,
    noWrap: true,
  });
  let loadedTiles = 0;
  tileLayer.on("loading", () => {
    loadedTiles = 0;
  });
  elements.libraryStatus.textContent = "Leaflet · carregando mapa";
  tileLayer.on("tileload", (event) => {
    if (!event.tile.src.startsWith("data:")) {
      loadedTiles += 1;
    }
  });
  tileLayer.on("load", () => setTileStatus(loadedTiles > 0));
  tileLayer.on("tileerror", () => {
    setTileStatus(false);
  });
  tileLayer.addTo(mapInstance);

  cableLayer = window.L.layerGroup().addTo(mapInstance);
  articulationLayer = window.L.layerGroup().addTo(mapInstance);
  nodeLayer = window.L.layerGroup().addTo(mapInstance);

  const bounds = window.L.latLngBounds(graph.nos.map((node) => [node.lat, node.lon]));
  mapInstance.fitBounds(bounds, { animate: false, maxZoom: 3, padding: [24, 24] });
  updateMap(graph);

  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(resizeMap);
    resizeObserver.observe(elements.network);
  }
}

function updateMap(graph) {
  if (!mapInstance) {
    return;
  }

  cableLayer.clearLayers();
  articulationLayer.clearLayers();
  nodeLayer.clearLayers();

  toMapCables(graph)
    .sort((first, second) => first.priority - second.priority)
    .forEach((cable) => {
      cable.segments.forEach((segment) => {
        window.L.polyline(
          segment.map((point) => [point.lat, point.lng]),
          {
            color: cable.color,
            dashArray: cable.dashArray,
            interactive: true,
            opacity: cable.opacity,
            smoothFactor: 0.5,
            weight: cable.weight,
          },
        )
          .bindTooltip(cableLabel(cable), { className: "map-tooltip", sticky: true })
          .addTo(cableLayer);
      });
    });

  toMapPoints(graph).forEach((point) => {
    if (point.isArticulation && point.ativo) {
      window.L.circleMarker([point.lat, point.lng], {
        className: "articulation-ring",
        color: COLORS.articulation,
        fill: false,
        interactive: false,
        opacity: 0.9,
        radius: point.radius + 5,
        weight: 2,
      }).addTo(articulationLayer);
    }

    window.L.circleMarker([point.lat, point.lng], {
      bubblingMouseEvents: false,
      className: "network-node",
      color: point.isArticulation ? COLORS.articulation : "#dceae2",
      fillColor: point.color,
      fillOpacity: 1,
      radius: point.radius,
      weight: point.isArticulation ? 2.5 : 1.2,
    })
      .bindTooltip(pointLabel(point), {
        className: "map-tooltip",
        direction: "top",
        offset: [0, -5],
      })
      .on("click", () => toggleNode(point.id))
      .addTo(nodeLayer);
  });
}

function flashRouteEdges(edgeIds) {
  if (!edgeIds.length) {
    return;
  }
  flashedEdgeIds = new Set(edgeIds);
  updateMap(currentGraph);
  window.setTimeout(() => {
    flashedEdgeIds = new Set();
    updateMap(currentGraph);
  }, ROUTE_FLASH_DURATION_MS);
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
    clearMinimumCut();
    currentGraph = await fetchGraph();
    currentCriticidade = await fetchCriticidade();
    await recalculateAndRender();
  } catch (error) {
    showActionError(error);
  }
}

async function fetchAlternateRoutes(origem, destino) {
  const response = await fetch("/rotas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origem, destino, k: ALTERNATE_ROUTES_K }),
  });
  if (!response.ok) {
    throw new Error(`A API respondeu com HTTP ${response.status}.`);
  }
  return response.json();
}

async function refreshRoute() {
  const previousRouteEdges = currentRouteEdges(currentGraph.rota_atual);

  if (!currentSelection.origem || !currentSelection.destino) {
    currentGraph.rota_atual = null;
    currentAlternateRoutes = [];
    currentRedundancyPercent = null;
    return previousRouteEdges;
  }

  const [rotaResponse, rotas] = await Promise.all([
    fetch("/rota", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origem: currentSelection.origem,
        destino: currentSelection.destino,
        algoritmo: currentSelection.algoritmo,
      }),
    }),
    fetchAlternateRoutes(currentSelection.origem, currentSelection.destino),
  ]);
  if (!rotaResponse.ok) {
    throw new Error(`A API respondeu com HTTP ${rotaResponse.status}.`);
  }
  const rota = await rotaResponse.json();
  currentGraph.rota_atual = {
    origem: currentSelection.origem,
    destino: currentSelection.destino,
    ...rota,
  };
  // A melhor rota (rank 1) ja e desenhada por rota_atual; so as demais entram como alternativas.
  currentAlternateRoutes = rotas.rotas.slice(1);
  currentRedundancyPercent = rotas.redundancia_percentual;
  return previousRouteEdges;
}

async function recalculateAndRender() {
  const previousRouteEdges = await refreshRoute();
  await loadTrace();
  updateMap(currentGraph);
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

function updateMinCutButton() {
  elements.minCutButton.disabled =
    !currentSelection.origem ||
    !currentSelection.destino ||
    currentSelection.origem === currentSelection.destino;
}

function clearMinimumCut() {
  currentMinCut = null;
  currentMinCutEdgeIds = new Set();
  elements.minCutDetails.textContent =
    "Selecione dois roteadores e calcule quantos cabos os separam.";
}

function renderMinimumCut() {
  if (!currentMinCut) {
    return;
  }
  const count = currentMinCut.capacidade;
  if (count === 0) {
    elements.minCutDetails.textContent =
      "0 cabos: os roteadores já estão desconectados na rede disponível.";
    return;
  }
  elements.minCutDetails.textContent = `${count} ${
    count === 1 ? "cabo precisa" : "cabos precisam"
  } cair para separar os roteadores selecionados.`;
}

async function calculateMinimumCut() {
  if (elements.minCutButton.disabled) {
    return;
  }
  try {
    clearActionError();
    const response = await fetch("/analise/corte-minimo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origem: currentSelection.origem,
        destino: currentSelection.destino,
      }),
    });
    if (!response.ok) {
      throw new Error(`A API respondeu com HTTP ${response.status}.`);
    }
    currentMinCut = await response.json();
    currentMinCutEdgeIds = new Set(
      currentMinCut.arestas.map((edge) => edgeKey(edge.origem, edge.destino)),
    );
    renderMinimumCut();
    updateMap(currentGraph);
  } catch (error) {
    showActionError(error);
  }
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
  elements.algoAStar.setAttribute("aria-pressed", String(algoritmo === "a_star"));
}

async function resetSimulation() {
  try {
    clearActionError();
    clearMinimumCut();
    const response = await fetch("/simulacao/resetar", { method: "POST" });
    if (!response.ok) throw new Error(`A API respondeu com HTTP ${response.status}.`);
    currentGraph = await response.json();
    currentCriticidade = await fetchCriticidade();
    await recalculateAndRender();
  } catch (error) {
    showActionError(error);
  }
}

async function loadTrace() {
  if (!currentSelection.origem || !currentSelection.destino) {
    currentTrace = [];
    currentTraceIndex = 0;
    traceEvent = null;
    elements.tracePlayButton.disabled = true;
    elements.traceStepButton.disabled = true;
    elements.traceStatus.textContent = "Calcule uma rota para carregar o traço.";
    return;
  }
  const response = await fetch("/rota/passos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentSelection),
  });
  if (!response.ok) throw new Error(`A API respondeu com HTTP ${response.status}.`);
  const payload = await response.json();
  currentTrace = payload.passos;
  currentTraceIndex = 0;
  traceEvent = null;
  elements.tracePlayButton.disabled = currentTrace.length === 0;
  elements.traceStepButton.disabled = currentTrace.length === 0;
  elements.traceStatus.textContent = `${currentTrace.length} passos carregados${payload.truncado ? " (limite atingido)" : ""}.`;
  updateMap(currentGraph);
}

function applyTraceStep() {
  if (currentTraceIndex >= currentTrace.length) {
    clearInterval(traceTimer);
    traceTimer = undefined;
    elements.tracePlayButton.textContent = "Reproduzir";
    return;
  }
  traceEvent = currentTrace[currentTraceIndex];
  currentTraceIndex += 1;
  elements.traceStatus.textContent = `Passo ${currentTraceIndex}/${currentTrace.length}: ${traceEvent.tipo}`;
  updateMap(currentGraph);
}

function toggleTracePlayback() {
  if (traceTimer) {
    clearInterval(traceTimer);
    traceTimer = undefined;
    elements.tracePlayButton.textContent = "Reproduzir";
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    while (currentTraceIndex < currentTrace.length) applyTraceStep();
    return;
  }
  elements.tracePlayButton.textContent = "Pausar";
  traceTimer = window.setInterval(applyTraceStep, Number(elements.traceSpeed.value));
}

function bindControls() {
  elements.originSelect.addEventListener("change", async (event) => {
    currentSelection.origem = event.target.value || null;
    clearMinimumCut();
    updateMinCutButton();
    try {
      clearActionError();
      await recalculateAndRender();
    } catch (error) {
      showActionError(error);
    }
  });

  elements.destinationSelect.addEventListener("change", async (event) => {
    currentSelection.destino = event.target.value || null;
    clearMinimumCut();
    updateMinCutButton();
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

  elements.algoAStar.addEventListener("click", async () => {
    setAlgorithm("a_star");
    try {
      clearActionError();
      await recalculateAndRender();
    } catch (error) {
      showActionError(error);
    }
  });

  elements.minCutButton.addEventListener("click", calculateMinimumCut);
  elements.resetButton.addEventListener("click", resetSimulation);
  elements.tracePlayButton.addEventListener("click", toggleTracePlayback);
  elements.traceStepButton.addEventListener("click", applyTraceStep);
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

  buildMap(graph);
  populateEndpointSelects(graph);
  setAlgorithm(currentSelection.algoritmo);
  updateMinCutButton();
  bindControls();
  renderRouteSummary(graph);
  renderCriticalitySummary();
  elements.nodeCount.textContent = graph.nos.length;
  elements.edgeCount.textContent = graph.arestas.length;
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
  resizeObserver?.disconnect();
  mapInstance?.remove();
  mapInstance = undefined;
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
    const [graph, criticidade] = await Promise.all([fetchGraph(), fetchCriticidade()]);
    console.info("Grafo recebido da API:", graph);
    currentCriticidade = criticidade;
    showGraph(graph);
  } catch (error) {
    showLoadError(error);
  }
}

initialize();
