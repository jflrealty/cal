from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
from calendar_service import buscar_disponibilidades, criar_evento_outlook
from database import get_proximo_vendedor
from config import ADMIN_EMAIL
from datetime import datetime, timedelta

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
        cliente = dados.get("attendees", [{}])[0]
        cliente_email = cliente.get("email", "sem_email")
        cliente_nome = cliente.get("name", "Cliente")
        inicio = dados.get("startTime", "sem_data")
        print(f"📅 Cliente: {cliente_email}, Horário: {inicio}")
    except Exception as e:
        print("⚠️ Erro ao acessar dados do payload:", str(e))
        return {"assigned_to": ADMIN_EMAIL}

    try:
        vendedores = get_proximo_vendedor()
        disponibilidade = buscar_disponibilidades(vendedores)
        print("📊 Disponibilidade consultada no Outlook:")
        for d in disponibilidade:
            print(f"→ {d}")

        responsavel = vendedores[0] if disponibilidade[0]["disponivel"] else ADMIN_EMAIL

        if responsavel != ADMIN_EMAIL:
            # Cria evento no Outlook
            inicio_dt = datetime.fromisoformat(inicio)
            fim_dt = inicio_dt + timedelta(minutes=60)
            criar_evento_outlook(
                responsavel_email=responsavel,
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                inicio_iso=inicio_dt.isoformat(),
                fim_iso=fim_dt.isoformat(),
                local=dados.get("location", "JFL Empreendimento"),
                descricao=dados.get("description", "")
            )

    except Exception as e:
        print("💥 Erro na lógica de distribuição:", str(e))
        responsavel = ADMIN_EMAIL

    return {"assigned_to": responsavel}
