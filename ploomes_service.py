import requests
import asyncio
from urllib.parse import quote
from config import PLOOMES_API_KEY

# Atualiza ou cria lead no Ploomes com base no e-mail do cliente e do vendedor
async def atualizar_owner_deal(cliente_email: str, cliente_nome: str, vendedor_email: str, telefone: str = ""):
    headers = {
        "User-Key": PLOOMES_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # 1. Buscar ID do vendedor no Ploomes
        filtro_usuario = quote(f"Email eq '{vendedor_email}'")  # encoding necessário
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

        # 2. Buscar se o cliente já é um lead
        filtro_cliente = quote(f"Email eq '{cliente_email}'")
        url_cliente = f"https://api2.ploomes.com/Contacts?$filter={filtro_cliente}"

        res_cliente = requests.get(url_cliente, headers=headers)
        print(f"🔍 GET /Contacts = {res_cliente.status_code}")
        print(res_cliente.text)

        if res_cliente.status_code != 200:
            print(f"❌ Erro ao buscar contato: {res_cliente.status_code} {res_cliente.text}")
            return

        cliente_data = res_cliente.json().get("value", [])

        if cliente_data:
            # 3a. Atualizar OwnerId se já existir
            cliente_id = cliente_data[0]["Id"]
            print(f"✏️ Atualizando OwnerId do contato ID = {cliente_id}")
            res_update = requests.patch(
                f"https://api2.ploomes.com/Contacts({cliente_id})",
                headers=headers,
                json={"OwnerId": vendedor_id}
            )
            print(f"📌 PATCH /Contacts = {res_update.status_code}")
        else:
            # 3b. Criar novo lead
            print("➕ Criando novo lead...")
            payload = {
                "Name": cliente_nome,
                "Email": cliente_email,
                "Phones": [{"PhoneNumber": telefone}] if telefone else [],
                "OwnerId": vendedor_id
            }
            res_create = requests.post(
                "https://api2.ploomes.com/Contacts",
                headers=headers,
                json=payload
            )
            print(f"✅ POST /Contacts = {res_create.status_code}")
            print(res_create.text)

    except Exception as e:
        print(f"❗Erro inesperado: {e}")
