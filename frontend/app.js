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
const GLOBE_BACKGROUND_COLOR = "#080b09";
const GLOBE_ATMOSPHERE_COLOR = "#6fb98a";
// Os cabos sao submarinos: um arco baixo acompanha a curvatura do globo em vez
// de disparar para fora dele, o que deixava as ligacoes longas soltas no espaco.
const ARC_ALTITUDE_AUTO_SCALE = 0.12;
const COUNTRIES_GEOJSON_URL =
  "https://unpkg.com/globe.gl@2.27.1/example/datasets/ne_110m_admin_0_countries.geojson";
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
  landFill: "rgba(111, 185, 138, 0.09)",
  landStroke: "rgba(125, 175, 145, 0.42)",
};

let globeInstance;
let resizeObserver;
let currentGraph;
let currentCriticidade = { articulacoes: [], pontes: [], componentes: 0 };
let countryFeatures = [];
let flashedEdgeIds = new Set();
// Rotas 2..k devolvidas por /rotas (a melhor fica de fora, ja coberta por rota_atual).
let currentAlternateRoutes = [];
let currentRedundancyPercent = null;
let currentMinCut = null;
let currentMinCutEdgeIds = new Set();

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

function buildGridTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#0b120e";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "rgba(125, 175, 145, 0.16)";
  ctx.lineWidth = 1;
  const step = 32;
  for (let x = 0; x <= canvas.width; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y <= canvas.height; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(125, 175, 145, 0.34)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, canvas.height / 2);
  ctx.lineTo(canvas.width, canvas.height / 2);
  ctx.stroke();

  return canvas.toDataURL("image/png");
}

async function fetchCountries() {
  // Os contornos sao apenas referencia visual: se a CDN falhar, o globo
  // continua funcional sem eles em vez de derrubar a visualizacao inteira.
  try {
    const response = await fetch(COUNTRIES_GEOJSON_URL);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const geojson = await response.json();
    return geojson.features ?? [];
  } catch (error) {
    console.warn("Contornos dos continentes indisponíveis:", error);
    return [];
  }
}

function toGlobePoints(graph) {
  const articulationPoints = articulationPointIds();
  // Reduz pontos comuns conforme a malha cresce; extremos continuam grandes.
  const regularRadius = Math.max(0.18, 0.35 * Math.sqrt(26 / graph.nos.length));

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
      radius: isEndpoint ? 0.55 : regularRadius,
    };
  });
}

function toGlobeRings(points) {
  return points
    .filter((point) => point.isArticulation && point.ativo)
    .map((point) => ({ lat: point.lat, lng: point.lng }));
}

function toGlobeArcs(graph) {
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

      // Tracos curtos: um padrao longo deixaria so dois segmentos por arco, que
      // a distancia parecem riscos soltos em vez de um cabo pontilhado.
      let dashLength = 1;
      let dashGap = 0;
      let dashAnimateTime = 0;
      if (isMinCut) {
        dashLength = 1;
        dashGap = 0;
      } else if (belongsToRoute || isFlashed) {
        dashLength = 0.3;
        dashGap = 0.12;
        dashAnimateTime = 1600;
      } else if (!edge.ativo) {
        dashLength = 0.06;
        dashGap = 0.05;
      } else if (isBridge) {
        dashLength = 0.05;
        dashGap = 0.035;
      }

      return {
        id,
        startLat: origin.lat,
        startLng: origin.lon,
        endLat: destination.lat,
        endLng: destination.lon,
        cabo: edge.cabo,
        peso: edge.peso,
        ativo: edge.ativo,
        isBridge,
        isMinCut,
        alternateRank: alternate?.rank,
        alternateCusto: alternate?.custo,
        color,
        // Rota alternativa fica visivelmente mais fina e apagada, atras da rota otima.
        stroke: isMinCut
          ? 0.7
          : belongsToRoute || isFlashed
            ? 0.55
            : alternate
              ? 0.16
              : isBridge
                ? 0.38
                : 0.25 * densityScale,
        dashLength,
        dashGap,
        dashAnimateTime,
      };
    })
    .filter(Boolean);
}

function pointLabel(point) {
  return `${point.nome}<br>${point.lat.toFixed(2)}°, ${point.lng.toFixed(2)}°<br>${
    point.ativo ? "Ativo" : "Derrubado"
  }${point.isArticulation ? "<br>Ponto de articulação" : ""}`;
}

function arcLabel(arc) {
  const alternateInfo = arc.alternateRank
    ? `<br>Rota alternativa #${arc.alternateRank} · ${Math.round(arc.alternateCusto).toLocaleString(
        "pt-BR",
      )} km`
    : "";
  return `${arc.cabo}<br>${Math.round(arc.peso).toLocaleString("pt-BR")} km<br>${
    arc.ativo ? "Ativa" : "Derrubada"
  }${arc.isBridge ? "<br>Ponte (ponto único de falha)" : ""}${
    arc.isMinCut ? "<br>Parte do corte mínimo calculado" : ""
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

function averageCoordinates(nodes) {
  if (!nodes.length) {
    return { lat: 0, lng: 0 };
  }
  const total = nodes.reduce(
    (acc, node) => ({ lat: acc.lat + node.lat, lng: acc.lng + node.lon }),
    { lat: 0, lng: 0 },
  );
  return { lat: total.lat / nodes.length, lng: total.lng / nodes.length };
}

function resizeGlobe() {
  if (!globeInstance) {
    return;
  }
  globeInstance.width(elements.network.clientWidth);
  globeInstance.height(elements.network.clientHeight);
}

function buildGlobe(graph) {
  if (typeof window.Globe !== "function") {
    throw new Error("A biblioteca de visualização não pôde ser carregada.");
  }

  elements.network.innerHTML = "";

  globeInstance = window
    .Globe()(elements.network)
    .width(elements.network.clientWidth)
    .height(elements.network.clientHeight)
    .backgroundColor(GLOBE_BACKGROUND_COLOR)
    .globeImageUrl(buildGridTexture())
    .showAtmosphere(true)
    .atmosphereColor(GLOBE_ATMOSPHERE_COLOR)
    .atmosphereAltitude(0.14)
    .polygonsData(countryFeatures)
    .polygonCapColor(() => COLORS.landFill)
    .polygonSideColor(() => "rgba(0, 0, 0, 0)")
    .polygonStrokeColor(() => COLORS.landStroke)
    .polygonAltitude(0.006)
    .polygonLabel(() => "")
    .polygonsTransitionDuration(0)
    .pointsMerge(false)
    .pointAltitude(0.012)
    .pointRadius((point) => point.radius)
    .pointColor((point) => point.color)
    .pointLabel(pointLabel)
    .pointsTransitionDuration(200)
    .onPointClick((point) => toggleNode(point.id))
    .arcsTransitionDuration(0)
    .arcAltitudeAutoScale(ARC_ALTITUDE_AUTO_SCALE)
    .arcColor((arc) => arc.color)
    .arcStroke((arc) => arc.stroke)
    .arcDashLength((arc) => arc.dashLength)
    .arcDashGap((arc) => arc.dashGap)
    .arcDashAnimateTime((arc) => arc.dashAnimateTime)
    .arcLabel(arcLabel)
    .ringColor(() => (t) => `rgba(255, 153, 0, ${1 - t})`)
    .ringMaxRadius(3.4)
    .ringPropagationSpeed(2.2)
    .ringRepeatPeriod(1500);

  globeInstance.controls().autoRotate = true;
  globeInstance.controls().autoRotateSpeed = 0.35;
  globeInstance.controls().enableDamping = true;

  const { lat, lng } = averageCoordinates(graph.nos);
  globeInstance.pointOfView({ lat, lng, altitude: 1.85 }, 0);

  updateGlobe(graph);

  resizeObserver?.disconnect();
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(resizeGlobe);
    resizeObserver.observe(elements.network);
  }
}

function updateGlobe(graph) {
  const points = toGlobePoints(graph);
  globeInstance
    .pointsData(points)
    .arcsData(toGlobeArcs(graph))
    .ringsData(toGlobeRings(points));
}

function flashRouteEdges(edgeIds) {
  if (!edgeIds.length) {
    return;
  }
  flashedEdgeIds = new Set(edgeIds);
  updateGlobe(currentGraph);
  window.setTimeout(() => {
    flashedEdgeIds = new Set();
    updateGlobe(currentGraph);
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
  updateGlobe(currentGraph);
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
    updateGlobe(currentGraph);
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

  buildGlobe(graph);
  populateEndpointSelects(graph);
  setAlgorithm(currentSelection.algoritmo);
  updateMinCutButton();
  bindControls();
  renderRouteSummary(graph);
  renderCriticalitySummary();
  elements.nodeCount.textContent = graph.nos.length;
  elements.edgeCount.textContent = graph.arestas.length;
  elements.libraryStatus.textContent = "globe.gl ativo";
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
  globeInstance = undefined;
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
    const [graph, criticidade, countries] = await Promise.all([
      fetchGraph(),
      fetchCriticidade(),
      fetchCountries(),
    ]);
    console.info("Grafo recebido da API:", graph);
    currentCriticidade = criticidade;
    countryFeatures = countries;
    showGraph(graph);
  } catch (error) {
    showLoadError(error);
  }
}

initialize();
