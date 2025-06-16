import requests
import asyncio
from urllib.parse import quote
from config import PLOOMES_API_KEY

# Atualiza o OwnerId de um negócio no Ploomes com base no email do cliente e do vendedor
async def atualizar_owner_deal(cliente_email: str, cliente_nome: str, vendedor_email: str):
    headers = {
        "User-Key": PLOOMES_API_KEY
    }

    try:
        # 1. Buscar ID do vendedor no Ploomes
        filtro_usuario = quote(f"Email eq '{vendedor_email}'")  # encoding necessário
        url_usuario = f"https://api.ploomes.com/Users?$filter={filtro_usuario}"

        res_user = requests.get(url_usuario, headers=headers)
        print(f"🔍 GET /Users → {res_user.status_code}")
        print(res_user.text)

        if res_user.status_code != 200:
            print(f"❌ Erro ao buscar usuário: {res_user.status_code} {res_user.text}")
            return

        user_data = res_user.json().get("value", [])
        if not user_data:
            print(f"❌ Vendedor {vendedor_email} não encontrado no Ploomes.")
            return

        owner_id = user_data[0]["Id"]
        print(f"🔁 ID do vendedor {vendedor_email}: {owner_id}")

        # 2. Aguardar criação do negócio pelo Cal.com
        await asyncio.sleep(5)

        # 3. Buscar negócio na etapa 'Visita' com email do cliente
        filtro_deal = quote(f"Stage/Name eq 'Visita' and Contact/Email eq '{cliente_email}'")
        url_deals = f"https://api.ploomes.com/Deals?$filter={filtro_deal}&$orderby=Id desc"

        res_deals = requests.get(url_deals, headers=headers)
        print(f"🔍 GET /Deals → {res_deals.status_code}")
        print(res_deals.text)

        if res_deals.status_code != 200:
            print(f"❌ Erro ao buscar negócio: {res_deals.status_code} {res_deals.text}")
            return

        deals = res_deals.json().get("value", [])
        if not deals:
            print(f"❌ Nenhum negócio encontrado para {cliente_email} na etapa Visita.")
            return

        deal_id = deals[0]["Id"]
        print(f"📎 Negócio localizado: ID {deal_id} → atualizando OwnerId...")

        # 4. Atualizar o dono (owner) do negócio
        patch = requests.patch(
            f"https://api.ploomes.com/Deals({deal_id})",
            headers=headers,
            json={"OwnerId": owner_id}
        )

        if patch.status_code == 200:
            print(f"✅ Negócio {deal_id} atribuído a {vendedor_email}.")
        else:
            print(f"⚠️ Falha ao atualizar negócio {deal_id}: {patch.status_code} {patch.text}")

    except Exception as e:
        print(f"💥 Erro na integração com o Ploomes: {str(e)}")
