const test = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");

const { greatCircleSegments, interpolateGreatCircle } = require("../map-geometry.js");

test("a grande circunferência sai e chega nas coordenadas informadas", () => {
  const points = interpolateGreatCircle(
    { lat: -23.96, lng: -46.33 },
    { lat: 38.72, lng: -9.13 },
  );

  assert.ok(Math.abs(points[0].lat - -23.96) < 1e-9);
  assert.ok(Math.abs(points[0].lng - -46.33) < 1e-9);
  assert.ok(Math.abs(points.at(-1).lat - 38.72) < 1e-9);
  assert.ok(Math.abs(points.at(-1).lng - -9.13) < 1e-9);
  assert.ok(points.some((point) => point.lat > 10));
});

test("Tóquio–Los Angeles é partido nas duas bordas do antimeridiano", () => {
  const segments = greatCircleSegments(
    { lat: 35.68, lng: 139.69 },
    { lat: 34.05, lng: -118.24 },
  );

  assert.equal(segments.length, 2);
  assert.equal(Math.abs(segments[0].at(-1).lng), 180);
  assert.equal(Math.abs(segments[1][0].lng), 180);
  for (const segment of segments) {
    for (let index = 1; index < segment.length; index += 1) {
      assert.ok(Math.abs(segment[index].lng - segment[index - 1].lng) <= 180);
    }
  }
});

test("um cabo atlântico permanece em um único arco", () => {
  const segments = greatCircleSegments(
    { lat: 36.85, lng: -76.29 },
    { lat: 43.26, lng: -2.93 },
  );

  assert.equal(segments.length, 1);
  assert.ok(segments[0].length > 2);
});

test("nenhum cabo do dataset salta de uma borda à outra dentro da mesma polilinha", () => {
  const dataset = JSON.parse(
    readFileSync(join(__dirname, "../../backend/data/rede.json"), "utf8"),
  );
  const nodes = new Map(dataset.nos.map((node) => [node.id, node]));
  let splitCables = 0;

  for (const edge of dataset.arestas) {
    const origin = nodes.get(edge.origem);
    const destination = nodes.get(edge.destino);
    const segments = greatCircleSegments(
      { lat: origin.lat, lng: origin.lon },
      { lat: destination.lat, lng: destination.lon },
    );
    if (segments.length > 1) splitCables += 1;

    for (const segment of segments) {
      for (let index = 1; index < segment.length; index += 1) {
        assert.ok(
          Math.abs(segment[index].lng - segment[index - 1].lng) <= 180,
          `${edge.origem}–${edge.destino} atravessou o mapa`,
        );
      }
    }
  }

  assert.ok(splitCables > 0, "o teste precisa exercitar ao menos um cabo transpacífico");
});
