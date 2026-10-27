"""FastAPI service so other systems can request an investigation."""
from fastapi import FastAPI, HTTPException

from graph import CaseReport, investigate

app = FastAPI(title="Fraud Investigation Agent")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/investigate/{account_id}", response_model=CaseReport)
def run(account_id: str) -> CaseReport:
    try:
        return investigate(account_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
