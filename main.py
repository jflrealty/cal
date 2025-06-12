from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from calendar_service import (
    buscar_disponibilidades,
    criar_evento_outlook,
    enviar_email_notificacao,
    enviar_whatsapp_notificacao,
)

from distribution import distribuir_agendamento
from database import get_proximo_vendedor
from config import ADMIN_EMAIL

app = FastAPI()

class WebhookPayload(BaseModel):
    event: Optional[str] = Field(default=None)
    triggerEvent: Optional[str] = Field(default=None)
    payload: Optional[Dict[str, Any]]

@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    dados = data.payload or {}

    print("🔔 Payload recebido:")
    print(dados)

    # Webhook de teste enviado pelo Cal.com
    if data.triggerEvent == "PING":
        print("📣 Webhook de teste recebido (PING). Ignorando processamento.")
        return {"status": "ping ok"}

    try:
        # Extrai dados principais do agendamento
        cliente = dados.get("attendees", [{}])[0]
        cliente_email = cliente.get("email", "sem_email")
        cliente_nome = cliente.get("name", "")
        inicio = dados.get("startTime", "sem_data")
        fim = dados.get("endTime", "sem_fim")
        local = dados.get("location", "Local não informado")
        descricao = dados.get("description", "")
        print(f"📅 Cliente: {cliente_email}, Horário: {inicio}")
    except Exception as e:
        print("⚠️ Erro ao acessar dados do payload:", str(e))
        cliente_email = "sem_email"
        cliente_nome = ""
        inicio = "sem_data"
        fim = "sem_fim"
        local = "Erro ao ler local"
        descricao = ""

    try:
        # Lógica de distribuição e consulta
        vendedores = get_proximo_vendedor()
        disponibilidade = buscar_disponibilidades(vendedores)
        print("📊 Disponibilidade consultada no Outlook:")
        for d in disponibilidade:
            print(f"→ {d}")

        responsavel = distribuir_agendamento(dados, vendedores, disponibilidade)

        if responsavel:
            # Criação do evento no Outlook
            criar_evento_outlook(
                responsavel_email=responsavel,
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                inicio_iso=inicio,
                fim_iso=fim,
                local=local,
                descricao=descricao
            )

            # Notificação por e-mail
            telefone = dados.get("responses", {}).get("telefone", {}).get("value", "")
            enviar_email_notificacao(
                responsavel_email=responsavel,
                cliente_nome=cliente_nome,
                cliente_email=cliente_email,
                telefone=telefone,
                inicio_iso=inicio,
                fim_iso=fim,
                local=local,
                descricao=descricao
            )

            # Notificação via WhatsApp (se telefone existir)
            if telefone:
                enviar_whatsapp_notificacao(
                    responsavel_email=responsavel,
                    cliente_nome=cliente_nome,
                    telefone=telefone,
                    inicio_iso=inicio,
                    local=local
                )
                    # Notificação para o Victor
    from calendar_service import notificar_victor

                notificar_victor(
                    cliente_nome=cliente_nome,
                    cliente_email=cliente_email,
                    telefone=telefone,
                    inicio_iso=inicio,
                    fim_iso=fim,
                    local=local,
                    descricao=descricao,
                    vendedor_email=responsavel
                )

    except Exception as e:
        print("💥 Erro na lógica de distribuição:", str(e))
        responsavel = None

    return {"assigned_to": responsavel or ADMIN_EMAIL}
