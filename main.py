from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import os
import psycopg2
from datetime import datetime
import pytz

from calendar_service import (
    buscar_disponibilidades,
    criar_evento_outlook,
    enviar_email_notificacao,
    # enviar_whatsapp_notificacao,  # deixamos importado/desligado no main
    notificar_victor,
)

from distribution import distribuir_agendamento
from database import get_proximo_vendedor
from config import ADMIN_EMAIL
from ploomes_service import atualizar_owner_deal  # integração Ploomes

# -----------------------------
# Flag global para WhatsApp
# -----------------------------
SEND_WHATSAPP = os.getenv("SEND_WHATSAPP", "false").lower() in ("1", "true", "yes", "on")

app = FastAPI()


def converter_utc_para_sao_paulo(iso_string: str) -> str:
    """
    Converte ISO (com 'Z' ou offset) para string no fuso America/Sao_Paulo.
    Retorna 'DD/MM/YYYY HH:MM'.
    """
    if not iso_string:
        return ""
    sp = pytz.timezone("America/Sao_Paulo")
    # Normaliza 'Z' para offset +00:00
    dt_utc = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    dt_sp = dt_utc.astimezone(sp)
    return dt_sp.strftime("%d/%m/%Y %H:%M")


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
    password="FgHGiyBQqSyFpjIcSRzDaArevEZTlWXE",
)
cursor = conn.cursor()


def obter_ou_vincular_vendedor(email_cliente: str, candidatos_disponiveis: List[Dict[str, Any]]) -> str:
    """
    Se já existe um vendedor para o cliente, reaproveita.
    Caso contrário, usa o primeiro elegível de 'candidatos_disponiveis'
    e grava em 'clientes_atendidos'.
    """
    cursor.execute(
        "SELECT email_vendedor FROM clientes_atendidos WHERE email_cliente = %s",
        (email_cliente,),
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
        (email_cliente, vendedor_email, datetime.now()),
    )
    conn.commit()

    return vendedor_email


@app.post("/webhook")
async def receber_agendamento(data: WebhookPayload):
    dados = data.payload or {}

    # ========================
    # 🟥 CANCELAMENTO
    # ========================
    if dados.get("status") == "CANCELLED":
        cancelador = dados.get("cancelledBy", "não informado")
        cliente = dados.get("attendees", [{}])[0]
        cliente_email = cliente.get("email", "sem_email")
        local = dados.get("location", "Local não informado")
        inicio_iso = dados.get("startTime", "")
        inicio_sp = converter_utc_para_sao_paulo(inicio_iso)

        # Busca vendedor previamente atribuído
        cursor.execute(
            "SELECT email_vendedor FROM clientes_atendidos WHERE email_cliente = %s",
            (cliente_email,),
        )
        result = cursor.fetchone()

        if result:
            vendedor = result[0]
            print(
                f"🛑 Cancelamento: cliente={cliente_email} vendedor={vendedor} local={local} inicio(SP)={inicio_sp} cancelado_por={cancelador}"
            )

            # 🔕 WhatsApp desativado globalmente via SEND_WHATSAPP; por ora, não enviamos nada.
            # Se quiser reativar só para cancelamento no futuro:
            # if SEND_WHATSAPP:
            #     ... chamar enviar_whatsapp_notificacao de cancelamento aqui ...
        else:
            print(f"ℹ️ Cancelamento de cliente sem vendedor associado: {cliente_email}")

        return {"status": "cancelamento_tratado"}

    # ========================
    # 🟩 NOVO AGENDAMENTO
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
        inicio_iso = dados.get("startTime", "")
        fim_iso = dados.get("endTime", "")
        local = dados.get("location", "Local não informado")
        descricao = dados.get("description", "")

        print(f"📅 Cliente: {cliente_email}, Horário (UTC): {inicio_iso}")

        # ✅ Conversão para horário de São Paulo (para mensagens/emails)
        inicio_sp = converter_utc_para_sao_paulo(inicio_iso)
        fim_sp = converter_utc_para_sao_paulo(fim_iso)

    except Exception as e:
        print("⚠️ Erro ao acessar dados do payload:", str(e))
        # fallback seguro
        cliente_email = "sem_email"
        cliente_nome = ""
        inicio_iso = ""
        fim_iso = ""
        inicio_sp = ""
        fim_sp = ""
        local = "Erro ao ler local"
        descricao = ""

    try:
        # pega a ordem de candidatos (round-robin já vem de get_proximo_vendedor, sua função)
        vendedores = get_proximo_vendedor()
        disponibilidade = buscar_disponibilidades(vendedores)

        print("📊 Disponibilidade consultada no Outlook:")
        for d in disponibilidade:
            print(f"→ {d}")

        responsavel = obter_ou_vincular_vendedor(cliente_email, disponibilidade)

        if responsavel:
            # Cria evento no calendário (com fuso explícito)
            criar_evento_outlook(
                responsavel_email=responsavel,
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                inicio_iso=inicio_iso,
                fim_iso=fim_iso,
                local=local,
                descricao=descricao,
            )

            # Notifica por e-mail o vendedor
            telefone = dados.get("responses", {}).get("telefone", {}).get("value", "")
            enviar_email_notificacao(
                responsavel_email=responsavel,
                cliente_nome=cliente_nome,
                cliente_email=cliente_email,
                telefone=telefone,
                inicio_iso=inicio_sp,  # já formatado para SP
                fim_iso=fim_sp,        # já formatado para SP
                local=local,
                descricao=descricao,
            )

            # 🔕 WhatsApp desligado globalmente
            # if telefone and SEND_WHATSAPP:
            #     enviar_whatsapp_notificacao(
            #         responsavel_email=responsavel,
            #         cliente_nome=cliente_nome,
            #         telefone=telefone,
            #         inicio_iso=inicio_sp,  # mostramos no fuso SP
            #         local=local,
            #     )

            # Notifica o Victor por e-mail (o WhatsApp dele também está governado por flag dentro de calendar_service)
            notificar_victor(
                cliente_nome=cliente_nome,
                cliente_email=cliente_email,
                telefone=telefone,
                inicio_iso=inicio_sp,
                fim_iso=fim_sp,
                local=local,
                descricao=descricao,
                vendedor_email=responsavel,
            )

            # Atualiza o negócio no Ploomes (atribui Owner pelo e-mail do vendedor)
            await atualizar_owner_deal(
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                vendedor_email=responsavel,
            )

    except Exception as e:
        print("💥 Erro na lógica de distribuição:", str(e))
        responsavel = None

    return {"assigned_to": responsavel or ADMIN_EMAIL}
