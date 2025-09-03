import logging
import os
import requests
from datetime import datetime, timedelta
from dateutil import parser
from twilio.rest import Client
from config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_NUMBER, TWILIO_MESSAGING_SERVICE_SID,
)

# --- Flag para ligar/desligar WhatsApp via .env (default: OFF) ---
try:
    from config import SEND_WHATSAPP  # caso você tenha colocado no config.py
except Exception:
    SEND_WHATSAPP = os.getenv("SEND_WHATSAPP", "false").lower() in ("1", "true", "yes", "on")

logging.basicConfig(level=logging.DEBUG)

# Mapa de WhatsApp dos vendedores
VENDEDORES_WHATSAPP = {
    "gabriel.previati@jflliving.com.br": "+5511937559739",
    "douglas.macedo@jflliving.com.br": "+5511993435161",
    # Desative o Rigol comentando a linha abaixo enquanto precisar:
    # "marcos.rigol@jflliving.com.br": "+5511910854440",
    "victor.adas@jflrealty.com.br": "+5511993969755",
}

# ---------- AUTH GRAPH ----------
def get_access_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

# ---------- DISPONIBILIDADE ----------
def buscar_disponibilidades(vendedores_emails):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        # força fuso do Outlook ao ler eventos
        'Prefer': 'outlook.timezone="E. South America Standard Time"',
    }

    # Janela do dia local em SP (aproximação usando UTC-3)
    agora = datetime.utcnow() - timedelta(hours=3)
    inicio = agora.replace(hour=8, minute=0, second=0, microsecond=0)
    fim = agora.replace(hour=18, minute=0, second=0, microsecond=0)

    disponibilidade = []

    for email in vendedores_emails:
        url = f"https://graph.microsoft.com/v1.0/users/{email}/calendarView"
        params = {
            "startDateTime": inicio.isoformat(),
            "endDateTime": fim.isoformat(),
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            res.raise_for_status()
            eventos = res.json().get("value", [])
            eventos_futuros = [e for e in eventos if parser.isoparse(e["start"]["dateTime"]) > agora]

            if not eventos_futuros:
                disponibilidade.append({"email": email, "disponivel": True, "proximo_horario": 0})
            else:
                primeiro_inicio = parser.isoparse(eventos_futuros[0]["start"]["dateTime"])
                delta_min = int((primeiro_inicio - agora).total_seconds() / 60)
                disponibilidade.append({
                    "email": email,
                    "disponivel": delta_min > 30,
                    "proximo_horario": delta_min,
                })

        except Exception as e:
            print(f"⚠️ Erro ao buscar agenda de {email}: {str(e)}")
            disponibilidade.append({"email": email, "disponivel": False, "proximo_horario": 9999})

    return disponibilidade

# ---------- CRIAR EVENTO ----------
def criar_evento_outlook(responsavel_email, cliente_email, cliente_nome, inicio_iso, fim_iso, local, descricao):
    access_token = get_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{responsavel_email}/calendar/events"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    body = {
        "subject": f"{cliente_nome} - Visita agendada em {local}",
        "body": {"contentType": "HTML", "content": descricao or "Visita agendada via Cal.com"},
        # Mantém consistência: passamos o ISO de entrada e o fuso do calendário explicitamente
        "start": {"dateTime": inicio_iso, "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": fim_iso, "timeZone": "America/Sao_Paulo"},
        "location": {"displayName": local},
        "attendees": [
            {"emailAddress": {"address": cliente_email, "name": cliente_nome}, "type": "required"}
        ],
    }

    try:
        res = requests.post(url, headers=headers, json=body)
        res.raise_for_status()
        print("📅 Evento criado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao criar evento: {str(e)}")

# ---------- EMAIL VENDEDOR ----------
def enviar_email_notificacao(responsavel_email, cliente_nome, cliente_email, telefone, inicio_iso, fim_iso, local, descricao):
    access_token = get_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{responsavel_email}/sendMail"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    corpo_email = f"""
    <p>Olá, você tem um novo agendamento!</p>
    <ul>
      <li><strong>Cliente:</strong> {cliente_nome}</li>
      <li><strong>Email:</strong> {cliente_email}</li>
      <li><strong>Telefone:</strong> {telefone}</li>
      <li><strong>Data/Hora:</strong> {inicio_iso} até {fim_iso}</li>
      <li><strong>Local:</strong> {local}</li>
      <li><strong>Descrição:</strong> {descricao}</li>
    </ul>
    """

    email_data = {
        "message": {
            "subject": "Novo Agendamento Recebido",
            "body": {"contentType": "HTML", "content": corpo_email},
            "toRecipients": [{"emailAddress": {"address": responsavel_email}}],
        }
    }

    try:
        res = requests.post(url, headers=headers, json=email_data)
        res.raise_for_status()
        print("📧 Notificação por e-mail enviada com sucesso.")
    except Exception as e:
        print("⚠️ Falha ao enviar e-mail:", str(e))

# ---------- WHATSAPP VENDEDOR ----------
def enviar_whatsapp_notificacao(responsavel_email, cliente_nome, telefone, inicio_iso, local):
    if not SEND_WHATSAPP:
        print("🔕 WhatsApp desativado por configuração (SEND_WHATSAPP=false).")
        return

    try:
        numero_destino = VENDEDORES_WHATSAPP.get(responsavel_email)
        if not numero_destino:
            print(f"📵 WhatsApp não cadastrado para {responsavel_email}")
            return

        if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_MESSAGING_SERVICE_SID):
            print("❗ Variáveis TWILIO ausentes. Verifique .env / config.py.")
            return

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        mensagem = f"""
📢 *Novo Agendamento!*

👤 Cliente: *{cliente_nome}*
📞 Telefone: *{telefone}*
📍 Local: *{local}*
🗓 Horário: *{inicio_iso}*

✅ Agendamento confirmado via Cal.com
        """.strip()

        message = client.messages.create(
            body=mensagem,
            to=f"whatsapp:{numero_destino}",
            messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
        )
        print("✅ WhatsApp enviado com sucesso:", message.sid)

    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp para {responsavel_email}: {str(e)}")

# ---------- NOTIFICAR VICTOR ----------
def notificar_victor(cliente_nome, cliente_email, telefone, inicio_iso, fim_iso, local, descricao, vendedor_email):
    VICTOR_EMAIL = "victor.adas@jflrealty.com.br"
    numero_destino = VENDEDORES_WHATSAPP.get(VICTOR_EMAIL)

    try:
        # E-mail para o Victor (sempre ativo)
        access_token = get_access_token()
        url_email = f"https://graph.microsoft.com/v1.0/users/{VICTOR_EMAIL}/sendMail"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        corpo_email = f"""
        <p>🚨 <strong>Novo agendamento realizado</strong></p>
        <ul>
          <li><strong>Cliente:</strong> {cliente_nome}</li>
          <li><strong>Email:</strong> {cliente_email}</li>
          <li><strong>Telefone:</strong> {telefone}</li>
          <li><strong>Horário:</strong> {inicio_iso} até {fim_iso}</li>
          <li><strong>Local:</strong> {local}</li>
          <li><strong>Descrição:</strong> {descricao}</li>
          <li><strong>Vendedor direcionado:</strong> {vendedor_email}</li>
        </ul>
        """

        email_data = {
            "message": {
                "subject": "Alerta: Novo Agendamento Recebido",
                "body": {"contentType": "HTML", "content": corpo_email},
                "toRecipients": [{"emailAddress": {"address": VICTOR_EMAIL}}],
            }
        }

        res = requests.post(url_email, headers=headers, json=email_data)
        res.raise_for_status()
        print("📧 E-mail enviado ao Victor com sucesso.")

        # WhatsApp do Victor condicionado à flag
        if SEND_WHATSAPP:
            if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_MESSAGING_SERVICE_SID):
                print("❗ Variáveis TWILIO ausentes. WhatsApp do Victor pulado.")
                return

            if not numero_destino:
                print("❗ Número do Victor não encontrado em VENDEDORES_WHATSAPP.")
                return

            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            mensagem = f"""
🚨 *Novo Agendamento Realizado*

👤 *Cliente:* {cliente_nome}
📧 *Email:* {cliente_email}
📞 *Telefone:* {telefone}
📍 *Local:* {local}
🗓 *Horário:* {inicio_iso} até {fim_iso}
📋 *Descrição:* {descricao}
🧑‍💼 *Vendedor:* {vendedor_email}
            """.strip()

            client.messages.create(
                body=mensagem,
                to=f"whatsapp:{numero_destino}",
                messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
            )
            print("✅ WhatsApp enviado ao Victor com sucesso.")
        else:
            print("🔕 WhatsApp do Victor desativado por configuração.")

    except Exception as e:
        print("❌ Erro ao notificar Victor:", str(e))
