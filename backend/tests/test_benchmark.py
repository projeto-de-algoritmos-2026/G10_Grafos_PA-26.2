"""Testes da inclusão da malha real no benchmark reproduzível."""

from scripts.benchmark import medir


def test_benchmark_real_mede_dataset_uma_vez_por_algoritmo():
    measurements = medir(
        topologias=("real",),
        tamanhos=(10, 50),
        grau_medio=4,
        amostras=3,
        repeticoes=1,
        seed=42,
    )

    assert len(measurements) == 2
    assert {measurement.algoritmo for measurement in measurements} == {
        "dijkstra",
        "bellman-ford",
    }
    assert all(measurement.topologia == "real" for measurement in measurements)
    assert all(measurement.tamanho == 100 for measurement in measurements)
    assert all(measurement.arestas == 180 for measurement in measurements)
    assert all(measurement.encontrada for measurement in measurements)
    assert measurements[0].custo == measurements[1].custo
