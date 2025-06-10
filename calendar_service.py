import requests
from config import CLIENT_ID, CLIENT_SECRET, TENANT_ID
from datetime import datetime, timedelta
from dateutil import parser  # Novo: melhor suporte a ISO 8601

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

    # Corrigindo fuso horário: UTC → Brasília
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

            # Filtra eventos que ainda vão começar
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
