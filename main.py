from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import psycopg2
from datetime import datetime
from ploomes_service import atualizar_owner_deal

from calendar_service import (
    buscar_disponibilidades,
    criar_evento_outlook,
    enviar_email_notificacao,
    enviar_whatsapp_notificacao,
    notificar_victor,  # ✅
)

from distribution import distribuir_agendamento
from database import get_proximo_vendedor
from config import ADMIN_EMAIL

app = FastAPI()

class WebhookPayload(BaseModel):
    event: Optional[str] = Field(default=None)
    triggerEvent: Optional[str] = Field(default=None)
    payload: Optional[Dict[str, Any]]

# Conexão com o banco Railway
conn = psycopg2.connect(
    host="mainline.proxy.rlwy.net",
    port=15443,
    dbname="railway",
    user="postgres",
    password="FgHGiyBQqSyFpjIcSRzDaArevEZTlWXE"
)
cursor = conn.cursor()

def obter_ou_vincular_vendedor(email_cliente, candidatos_disponiveis):
    cursor.execute(
        "SELECT email_vendedor FROM clientes_atendidos WHERE email_cliente = %s",
        (email_cliente,)
    )
    resultado = cursor.fetchone()

    if resultado:
        vendedor_email = resultado[0]
        print(f"🔁 Cliente já vinculado: {email_cliente} → {vendedor_email}")
        return vendedor_email

    if not candidatos_disponiveis:
        raise Exception("Nenhum vendedor disponível.")

    vendedor_email = candidatos_disponiveis[0]["email"]
    print(f"🆕 Novo vínculo: {email_cliente} → {vendedor_email}")

    cursor.execute(
        "INSERT INTO clientes_atendidos (email_cliente, email_vendedor, data_agendamento) VALUES (%s, %s, %s)",
        (email_cliente, vendedor_email, datetime.now())
    )
    conn.commit()

    return vendedor_email

@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    dados = data.payload or {}

    # ========================
    # 🟥 TRATAMENTO: CANCELAMENTO
    # ========================
    # 👉 Verifica se é cancelamento
    if dados.get("status") == "CANCELLED":
        cancelador = dados.get("cancelledBy", "não informado")
        cliente = dados.get("attendees", [{}])[0]
        cliente_email = cliente.get("email", "sem_email")
        local = dados.get("location", "Local não informado")
        inicio = dados.get("startTime", "sem_data")

        # Busca vendedor previamente atribuído
        cursor.execute(
            "SELECT email_vendedor FROM clientes_atendidos WHERE email_cliente = %s",
            (cliente_email,)
        )
        result = cursor.fetchone()

        if result:
            vendedor = result[0]
            telefone = dados.get("responses", {}).get("telefone", {}).get("value", "")

            # WhatsApp só para o vendedor (NÃO notifica o Victor)
            if telefone and vendedor:
                try:
                    from twilio.rest import Client
                    from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_MESSAGING_SERVICE_SID

                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                    numero_destino = VENDEDORES_WHATSAPP.get(vendedor)

                    if numero_destino:
                        mensagem = f"""
📣 *Agendamento Cancelado*

👤 Cliente: *{cliente_email}*
📍 Local: *{local}*
🗓 Data/hora: *{inicio}*

❌ Cancelado por: {cancelador}
                        """.strip()

                        client.messages.create(
                            body=mensagem,
                            to=f"whatsapp:{numero_destino}",
                            messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID
                        )
                        print(f"📲 WhatsApp de cancelamento enviado para {vendedor} ({numero_destino})")
                    else:
                        print(f"❗ Vendedor {vendedor} não tem número cadastrado.")

                except Exception as e:
                    print("⚠️ Falha ao enviar WhatsApp de cancelamento:", str(e))
        else:
            print(f"ℹ️ Cancelamento de cliente sem vendedor associado: {cliente_email}")

        return {"status": "cancelamento tratado"}
   
    # ========================
    # 🟩 TRATAMENTO: NOVO AGENDAMENTO
    # ========================
    
    print("🔔 Payload recebido:")
    print(dados)

    if data.triggerEvent == "PING":
        print("📣 Webhook de teste recebido (PING). Ignorando processamento.")
        return {"status": "ping ok"}

    try:
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
        vendedores = get_proximo_vendedor()
        disponibilidade = buscar_disponibilidades(vendedores)
        print("📊 Disponibilidade consultada no Outlook:")
        for d in disponibilidade:
            print(f"→ {d}")

        responsavel = obter_ou_vincular_vendedor(cliente_email, disponibilidade)

        if responsavel:
            criar_evento_outlook(
                responsavel_email=responsavel,
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                inicio_iso=inicio,
                fim_iso=fim,
                local=local,
                descricao=descricao
            )

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

            if telefone:
                enviar_whatsapp_notificacao(
                    responsavel_email=responsavel,
                    cliente_nome=cliente_nome,
                    telefone=telefone,
                    inicio_iso=inicio,
                    local=local
                )

                # ✅ Notifica o Victor por e-mail e WhatsApp
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
