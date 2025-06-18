import requests
import asyncio
from urllib.parse import quote
from config import PLOOMES_API_KEY

# Atualiza apenas o OwnerId do negócio (deal) baseado no e-mail do cliente e do vendedor
async def atualizar_owner_deal(cliente_email: str, cliente_nome: str, vendedor_email: str, telefone: str = ""):
    headers = {
        "User-Key": PLOOMES_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # 1. Buscar ID do vendedor no Ploomes
        filtro_usuario = quote(f"Email eq '{vendedor_email}'")
        url_usuario = f"https://api2.ploomes.com/Users?$filter={filtro_usuario}"
        res_user = requests.get(url_usuario, headers=headers)
        print(f"🔍 GET /Users = {res_user.status_code}")
        print(res_user.text)

        if res_user.status_code != 200:
            print(f"❌ Erro ao buscar usuário: {res_user.status_code} {res_user.text}")
            return

        user_data = res_user.json().get("value", [])
        if not user_data:
            print("⚠️ Vendedor não encontrado no Ploomes.")
            return

        vendedor_id = user_data[0]["Id"]
        print(f"✅ Vendedor encontrado: ID = {vendedor_id}")

        # 2. Buscar ID do cliente
        filtro_cliente = quote(f"Email eq '{cliente_email}'")
        url_cliente = f"https://api2.ploomes.com/Contacts?$filter={filtro_cliente}"
        res_cliente = requests.get(url_cliente, headers=headers)
        print(f"🔍 GET /Contacts = {res_cliente.status_code}")
        print(res_cliente.text)

        if res_cliente.status_code != 200:
            print(f"❌ Erro ao buscar contato: {res_cliente.status_code} {res_cliente.text}")
            return

        cliente_data = res_cliente.json().get("value", [])
        if not cliente_data:
            print("⚠️ Contato não encontrado no Ploomes.")
            return

        cliente_id = cliente_data[0]["Id"]

        # 3. Buscar negócio em aberto do cliente
        url_deal = f"https://api2.ploomes.com/Deals?$filter=ContactId eq {cliente_id} and IsWon eq false and IsLost eq false&$orderby=CreateDate desc"
        res_deal = requests.get(url_deal, headers=headers)
        print(f"🔍 GET /Deals = {res_deal.status_code}")
        print(res_deal.text)

        if res_deal.status_code != 200:
            print(f"❌ Erro ao buscar negócio: {res_deal.status_code} {res_deal.text}")
            return

        deals = res_deal.json().get("value", [])
        if not deals:
            print("⚠️ Nenhum negócio aberto encontrado para esse cliente.")
            return

        deal_id = deals[0]["Id"]

        # 4. Atualizar OwnerId do negócio
        payload = {"OwnerId": vendedor_id}
        res_update = requests.patch(
            f"https://api2.ploomes.com/Deals({deal_id})",
            headers=headers,
            json=payload
        )
        print(f"✏️ PATCH /Deals({deal_id}) = {res_update.status_code}")
        print(res_update.text)

    except Exception as e:
        print(f"❗Erro inesperado: {e}")
