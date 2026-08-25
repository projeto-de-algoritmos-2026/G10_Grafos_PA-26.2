from fastapi import FastAPI

app = FastAPI(title="Simulador de Colapso de Internet")


@app.get("/status")
def status() -> dict[str, str]:
    return {"status": "ok"}
