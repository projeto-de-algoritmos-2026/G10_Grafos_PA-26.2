const elements = {
  status: document.querySelector("#api-status"),
  error: document.querySelector("#api-error"),
  network: document.querySelector("#network"),
  nodeCount: document.querySelector("#node-count"),
  edgeCount: document.querySelector("#edge-count"),
  libraryStatus: document.querySelector("#library-status"),
};

function showGraphSummary(graph) {
  elements.nodeCount.textContent = graph.nos.length;
  elements.edgeCount.textContent = graph.arestas.length;
  elements.libraryStatus.textContent = window.vis?.Network ? "vis-network pronta" : "Indisponível";
  elements.status.textContent = "API conectada";
  elements.status.className = "status status-success";
  elements.network.setAttribute("aria-busy", "false");
  elements.network.innerHTML = `
    <div class="network-placeholder network-placeholder-success">
      <p>Topologia carregada. A visualização do grafo será adicionada na próxima etapa.</p>
    </div>
  `;
}

function showConnectionError(error) {
  console.error("Não foi possível carregar o grafo:", error);
  elements.status.textContent = "API indisponível";
  elements.status.className = "status status-error";
  elements.error.textContent =
    "Não foi possível carregar a topologia. Verifique se a API está em execução e tente novamente.";
  elements.error.hidden = false;
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
    showGraphSummary(graph);
  } catch (error) {
    showConnectionError(error);
  }
}

initialize();
