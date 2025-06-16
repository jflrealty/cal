import requests
import asyncio
from config import PLOOMES_API_KEY

# Atualiza o OwnerId de um Negócio no Ploomes, com base no e-mail do cliente e do vendedor
async def atualizar_owner_deal(cliente_email: str, cliente_nome: str, vendedor_email: str):
    headers = {
        "User-Key": PLOOMES_API_KEY
    }

    try:
        # 1. Buscar ID do vendedor no Ploomes
        res_user = requests.get(
            f"https://api.ploomes.com/Users?$filter=Email eq '{vendedor_email}'",
            headers=headers
        )
        user_data = res_user.json().get("value", [])

        if not user_data:
            print(f"❌ Vendedor {vendedor_email} não encontrado no Ploomes.")
            return

        owner_id = user_data[0]["Id"]
        print(f"🔁 ID do vendedor {vendedor_email}: {owner_id}")

        # 2. Aguarda o Cal.com criar o negócio no Ploomes
        await asyncio.sleep(5)

        # 3. Busca o negócio recente da etapa 'Visita'
        res_deals = requests.get(
            f"https://api.ploomes.com/Deals?$filter=Stage/Name eq 'Visita' and Contact/Email eq '{cliente_email}'&$orderby=Id desc",
            headers=headers
        )
        deals = res_deals.json().get("value", [])

        if not deals:
            print(f"❌ Nenhum negócio encontrado para {cliente_email} na etapa Visita.")
            return

        deal_id = deals[0]["Id"]
        print(f"📎 Negócio localizado: ID {deal_id} → atualizando OwnerId...")

        # 4. Atualiza com o OwnerId correto
        patch = requests.patch(
            f"https://api.ploomes.com/Deals({deal_id})",
            headers=headers,
            json={"OwnerId": owner_id}
        )

        if patch.status_code == 200:
            print(f"✅ Negócio {deal_id} atribuído a {vendedor_email} no Ploomes.")
        else:
            print(f"⚠️ Falha ao atualizar negócio {deal_id}: {patch.status_code} {patch.text}")

    except Exception as e:
        print("💥 Erro na integração com o Ploomes:", str(e))
