from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Any, Dict
from distribution import distribuir_agendamento
from calendar_service import buscar_disponibilidades
from database import get_proximo_vendedor
from config import ADMIN_EMAIL

app = FastAPI()

# Modelo para entrada
class WebhookPayload(BaseModel):
    event: Optional[str]
    payload: Optional[Dict[str, Any]] = None

@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    # Tenta acessar o payload interno ou o corpo direto
    dados = data.payload or data.dict()
    
    # LOG para depuração
    print("🔔 Agendamento recebido:", dados)

    try:
        # Extração segura
        cliente_email = dados.get("attendee", {}).get("email", "sem_email")
        inicio = dados.get("startTime", "sem_data")
        print(f"📅 Cliente: {cliente_email}, Horário: {inicio}")
    except Exception as e:
        print("⚠️ Erro ao processar dados:", str(e))

    # Distribuição
    vendedores = await get_proximo_vendedor()
    disponibilidade = await buscar_disponibilidades(vendedores)
    responsavel = distribuir_agendamento(dados, vendedores, disponibilidade)

    return {"assigned_to": responsavel or ADMIN_EMAIL}
