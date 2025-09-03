from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import psycopg2
from datetime import datetime
import pytz

from calendar_service import (
    buscar_disponibilidades,
    criar_evento_outlook,
    enviar_email_notificacao,
    # enviar_whatsapp_notificacao,  # 🔕 WhatsApp desativado
    notificar_victor,               # (no calendar_service o Whats do Victor também está comentado)
)

from database import get_proximo_vendedor
from config import ADMIN_EMAIL
from ploomes_service import atualizar_owner_deal

app = FastAPI()

def converter_utc_para_sao_paulo(iso_string: str) -> str:
    """Converte string ISO UTC (ex: '2025-06-30T13:00:00Z') para 'dd/mm/YYYY HH:MM' em America/Sao_Paulo."""
    sp = pytz.timezone("America/Sao_Paulo")
    # aceita 'Z' ou offset explícito
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
    password="FgHGiyBQqSyFpjIcSRzDaArevEZTlWXE"
)
cursor = conn.cursor()

def obter_ou_vincular_vendedor(email_cliente, candidatos_disponiveis):
    # Verifica se já existe vínculo
    cursor.execute(
        "SELECT email_vendedor FROM clientes_atendidos WHERE email_cliente = %s",
        (email_cliente,)
    )
    resultado = cursor.fetchone()

    if resultado:
        vendedor_email = resultado[0]
        print(f"🔁 Cliente já vinculado: {email_cliente} → {vendedor_email}")
        return vendedor_email

    # Se não há vínculo ainda, escolhe o primeiro disponível (já ordenado pela sua lógica)
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
    # 🟥 CANCELAMENTO
    # ========================
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
            # 🔕 WhatsApp de cancelamento DESATIVADO
            print(f"ℹ️ Cancelamento recebido. WhatsApp desativado. Cliente={cliente_email} Vendedor={vendedor} Local={local} Início={inicio} CanceladoPor={cancelador}")
        else:
            print(f"ℹ️ Cancelamento de cliente sem vendedor associado: {cliente_email}")

        return {"status": "cancelamento tratado"}

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
        inicio = dados.get("startTime", "sem_data")  # UTC ISO (ex.: 2025-06-30T13:00:00Z)
        fim = dados.get("endTime", "sem_fim")        # UTC ISO
        local = dados.get("location", "Local não informado")
        descricao = dados.get("description", "")
        print(f"📅 Cliente: {cliente_email}, Horário (UTC): {inicio}")

        # ✅ Converte para exibição (e-mail/Whats) em America/Sao_Paulo
        inicio_formatado = converter_utc_para_sao_paulo(inicio)
        fim_formatado = converter_utc_para_sao_paulo(fim)

    except Exception as e:
        print("⚠️ Erro ao acessar dados do payload:", str(e))
        cliente_email = "sem_email"
        cliente_nome = ""
        inicio = "sem_data"
        fim = "sem_fim"
        local = "Erro ao ler local"
        descricao = ""
        inicio_formatado = inicio
        fim_formatado = fim

    try:
        # 1) Consulta candidatos e disponibilidade (para escolher novo vínculo quando necessário)
        vendedores = get_proximo_vendedor()
        disponibilidade = buscar_disponibilidades(vendedores)
        print("📊 Disponibilidade consultada no Outlook:")
        for d in disponibilidade:
            print(f"→ {d}")

        # 2) Recupera vendedor já vinculado ou cria novo vínculo
        responsavel = obter_ou_vincular_vendedor(cliente_email, disponibilidade)

        if responsavel:
            # 3) Cria o evento no calendário do vendedor (usa UTC bruto + timeZone correto)
            criar_evento_outlook(
                responsavel_email=responsavel,
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                inicio_iso=inicio,   # UTC
                fim_iso=fim,         # UTC
                local=local,
                descricao=descricao
            )

            # 4) E-mail para o vendedor responsável (horário formatado em São Paulo)
            telefone = dados.get("responses", {}).get("telefone", {}).get("value", "")
            enviar_email_notificacao(
                responsavel_email=responsavel,
                cliente_nome=cliente_nome,
                cliente_email=cliente_email,
                telefone=telefone,
                inicio_iso=inicio_formatado,  # exibido em PT-BR
                fim_iso=fim_formatado,        # exibido em PT-BR
                local=local,
                descricao=descricao
            )

            # 🔕 5) WhatsApp do vendedor DESATIVADO
            # if telefone:
            #     enviar_whatsapp_notificacao(
            #         responsavel_email=responsavel,
            #         cliente_nome=cliente_nome,
            #         telefone=telefone,
            #         inicio_iso=inicio_formatado,
            #         local=local
            #     )

            # 6) Notifica o Victor (no calendar_service o Whats está desativado, e-mail segue ativo)
            notificar_victor(
                cliente_nome=cliente_nome,
                cliente_email=cliente_email,
                telefone=telefone,
                inicio_iso=inicio_formatado,
                fim_iso=fim_formatado,
                local=local,
                descricao=descricao,
                vendedor_email=responsavel
            )

            # 7) Atualiza negócio no Ploomes (não depende de Whats nem do telefone)
            await atualizar_owner_deal(
                cliente_email=cliente_email,
                cliente_nome=cliente_nome,
                vendedor_email=responsavel
            )

    except Exception as e:
        print("💥 Erro na lógica de distribuição:", str(e))
        responsavel = None

    return {"assigned_to": responsavel or ADMIN_EMAIL}
