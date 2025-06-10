from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI()

class WebhookPayload(BaseModel):
    event: Optional[str]
    payload: Optional[Dict[str, Any]]

@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    print("🔔 Payload recebido:")
    print(data)

    return {"status": "recebido com sucesso"}
