from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
from distribution import distribuir_agendamento
from calendar_service import buscar_disponibilidades
from database import get_proximo_vendedor
from config import ADMIN_EMAIL

app = FastAPI()

class WebhookPayload(BaseModel):
    event: Optional[str]
    payload: Optional[Dict[str, Any]]

@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    dados = data.payload or data.dict()
    print("🔔 Payload recebido:")
    print(dados)

    try:
        cliente_email = dados.get("attendee", {}).get("email", "sem_email")
        inicio = dados.get("startTime", "sem_data")
        print(f"📅 Cliente: {cliente_email}, Horário: {inicio}")
    except Exception as e:
        print("⚠️ Erro ao acessar dados do payload:", str(e))

    try:
        vendedores = get_proximo_vendedor()  # ✅ Agora está definido
        disponibilidade = buscar_disponibilidades(vendedores)
        responsavel = distribuir_agendamento(dados, vendedores, disponibilidade)
    except Exception as e:
        print("💥 Erro na lógica de distribuição:", str(e))
        responsavel = None

    return {"assigned_to": responsavel or ADMIN_EMAIL}
