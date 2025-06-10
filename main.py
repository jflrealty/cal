from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Any, Dict
from distribution import distribuir_agendamento
from calendar_service import buscar_disponibilidades
from database import get_proximo_vendedor
from config import ADMIN_EMAIL

app = FastAPI()

class WebhookPayload(BaseModel):
    event: Optional[str]
    payload: Optional[Dict[str, Any]] = None

@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    dados = data.payload or data.dict()
    print("Agendamento recebido:", dados)

    vendedores = await get_proximo_vendedor()
    disponibilidade = await buscar_disponibilidades(vendedores)
    responsavel = distribuir_agendamento(dados, vendedores, disponibilidade)

    return {"assigned_to": responsavel or ADMIN_EMAIL}
