from config import CLIENT_ID, CLIENT_SECRET, TENANT_ID
import requests

def buscar_disponibilidades(vendedores_emails):
    # Essa função simula a disponibilidade de cada vendedor
    # Idealmente, aqui você chamaria a Graph API para cada um
    return [
        {"email": email, "disponivel": True, "proximo_horario": 60}
        for email in vendedores_emails
    ]
