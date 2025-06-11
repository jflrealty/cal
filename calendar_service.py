import requests
from datetime import datetime, timedelta
from dateutil import parser
from config import (
    CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_MESSAGING_SERVICE_SID, TWILIO_WHATSAPP_NUMBER
)

print("🔎 Debug variáveis TWILIO:")
print("→ SID:", TWILIO_ACCOUNT_SID)
print("→ TOKEN:", TWILIO_AUTH_TOKEN)
print("→ FROM:", TWILIO_WHATSAPP_NUMBER)
print("→ MSG SID:", TWILIO_MESSAGING_SERVICE_SID)

from twilio.rest import Client

# Mapeia o e-mail do vendedor para número de WhatsApp
VENDEDORES_WHATSAPP = {
    "gabriel.previati@jflliving.com.br": "+5511937559739",
    "douglas.macedo@jflliving.com.br": "+5511993435161",
    "marcos.rigol@jflliving.com.br": "+5511910854440",
    "victor.adas@jflrealty.com.br": "+5511993969755"
}


def get_access_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        'client_id': CLIENT_ID,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()['access_token']


def buscar_disponibilidades(vendedores_emails):
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Prefer': 'outlook.timezone="E. South America Standard Time"'
    }

    agora = datetime.utcnow() - timedelta(hours=3)
    inicio = agora.replace(hour=8, minute=0, second=0, microsecond=0)
    fim = agora.replace(hour=18, minute=0, second=0, microsecond=0)

    disponibilidade = []

    for email in vendedores_emails:
        url = f"https://graph.microsoft.com/v1.0/users/{email}/calendarView"
        params = {
            "startDateTime": inicio.isoformat(),
            "endDateTime": fim.isoformat()
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            res.raise_for_status()
            eventos = res.json().get("value", [])

            eventos_futuros = [
                e for e in eventos if parser.isoparse(e["start"]["dateTime"]) > agora
            ]

            if not eventos_futuros:
                disponibilidade.append({
                    "email": email,
                    "disponivel": True,
                    "proximo_horario": 0
                })
            else:
                primeiro_inicio = parser.isoparse(eventos_futuros[0]["start"]["dateTime"])
                delta_min = int((primeiro_inicio - agora).total_seconds() / 60)

                disponibilidade.append({
                    "email": email,
                    "disponivel": delta_min > 30,
                    "proximo_horario": delta_min
                })

        except Exception as e:
            print(f"⚠️ Erro ao buscar agenda de {email}: {str(e)}")
            disponibilidade.append({
                "email": email,
                "disponivel": False,
                "proximo_horario": 9999
            })

    return disponibilidade


def criar_evento_outlook(responsavel_email, cliente_email, cliente_nome, inicio_iso, fim_iso, local, descricao):
    access_token = get_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{responsavel_email}/calendar/events"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    body = {
        "subject": f"Visita agendada - {local}",
        "body": {
            "contentType": "HTML",
            "content": descricao or "Visita agendada via Cal.com"
        },
        "start": {
            "dateTime": inicio_iso,
            "timeZone": "America/Sao_Paulo"
        },
        "end": {
            "dateTime": fim_iso,
            "timeZone": "America/Sao_Paulo"
        },
        "location": {
            "displayName": local
        },
        "attendees": [
            {
                "emailAddress": {
                    "address": cliente_email,
                    "name": cliente_nome
                },
                "type": "required"
            }
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=body)
        res.raise_for_status()
        print("📅 Evento criado com sucesso no calendário do responsável.")
    except Exception as e:
        print(f"❌ Erro ao criar evento no Outlook: {str(e)}")


def enviar_email_notificacao(responsavel_email, cliente_nome, cliente_email, telefone, inicio_iso, fim_iso, local, descricao):
    access_token = get_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{responsavel_email}/sendMail"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

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
            "body": {
                "contentType": "HTML",
                "content": corpo_email
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": responsavel_email
                    }
                }
            ]
        }
    }

    try:
        res = requests.post(url, headers=headers, json=email_data)
        res.raise_for_status()
        print("📧 Notificação por e-mail enviada com sucesso.")
    except Exception as e:
        print("⚠️ Falha ao enviar notificação por e-mail:", str(e))


def enviar_whatsapp_notificacao(responsavel_email, cliente_nome, telefone, inicio_iso, local):
    try:
        numero_destino = VENDEDORES_WHATSAPP.get(responsavel_email)
        if not numero_destino:
            print(f"📵 WhatsApp não cadastrado para {responsavel_email}")
            return

        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_MESSAGING_SERVICE_SID]):
            print("❗ Credenciais Twilio incompletas. Verifique seu .env ou config.py")
            return

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        mensagem = f"""
📢 *Novo Agendamento!*

👤 Cliente: *{cliente_nome}*
📞 Telefone: *{telefone}*
📍 Local: *{local}*
🗓 Horário: *{inicio_iso}*

✅ Este agendamento foi confirmado via Cal.com
        """.strip()

        message = client.messages.create(
            body=mensagem,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=numero_destino
        )

        print("✅ WhatsApp enviado com sucesso:", message.sid)

    except Exception as e:
        print("💥 Erro ao enviar mensagem via WhatsApp:", str(e))
