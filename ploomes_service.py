import requests
import time
from urllib.parse import quote
from config import PLOOMES_API_KEY

SESSION = requests.Session()
TIMEOUT = 15  # segundos
BASE = "https://api2.ploomes.com"

HEADERS = {
    "User-Key": PLOOMES_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def _get(url, **kwargs):
    return SESSION.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)

def _patch(url, json):
    return SESSION.patch(url, headers=HEADERS, timeout=TIMEOUT, json=json)

# Atualiza OwnerId do negócio recém-criado no Ploomes, dado cliente e vendedor
async def atualizar_owner_deal(cliente_email: str, cliente_nome: str, vendedor_email: str, telefone: str = ""):
    try:
        # 1) Buscar usuário (vendedor)
        q_user = quote(f"Email eq '{vendedor_email}'")
        r_user = _get(f"{BASE}/Users?$filter={q_user}")
        print(f"🔍 GET /Users => {r_user.status_code}")
        if r_user.status_code != 200:
            print(f"❌ Erro Users: {r_user.status_code} {r_user.text}")
            return
        users = r_user.json().get("value", [])
        if not users:
            print(f"⚠️ Vendedor não encontrado no Ploomes: {vendedor_email}")
            return
        owner_id = users[0]["Id"]
        print(f"✅ Vendedor {vendedor_email} → OwnerId {owner_id}")

        # 2) Buscar contatos por e-mail
        q_ct = quote(f"Email eq '{cliente_email}'")
        r_ct = _get(f"{BASE}/Contacts?$filter={q_ct}")
        print(f"🔍 GET /Contacts => {r_ct.status_code}")
        if r_ct.status_code != 200:
            print(f"❌ Erro Contacts: {r_ct.status_code} {r_ct.text}")
            return
        contatos = r_ct.json().get("value", [])
        if not contatos:
            print(f"⚠️ Contato não encontrado no Ploomes: {cliente_email}")
            return

        # 3) Para cada contato, tenta achar o deal mais recente sem OwnerId
        for contato in contatos:
            cid = contato["Id"]
            for tentativa in range(4):  # dá um tempo pro Cal.com criar o deal
                q_deal = quote(f"ContactId eq {cid} and OwnerId eq null")
                r_deals = _get(f"{BASE}/Deals?$filter={q_deal}&$orderby=CreateDate desc")
                print(f"🔎 Tentativa {tentativa+1} GET /Deals (ContactId={cid}) => {r_deals.status_code}")

                if r_deals.status_code != 200:
                    print(f"   ↳ Erro Deals: {r_deals.status_code} {r_deals.text}")
                    time.sleep(2)
                    continue

                deals = r_deals.json().get("value", [])
                if deals:
                    deal_id = deals[0]["Id"]
                    print(f"📎 Deal sem Owner encontrado: {deal_id}. Atualizando OwnerId...")

                    r_patch = _patch(f"{BASE}/Deals({deal_id})", json={"OwnerId": owner_id})
                    print(f"✏️ PATCH /Deals({deal_id}) => {r_patch.status_code}")
                    if r_patch.status_code not in (200, 204):
                        print(f"   ↳ Falha PATCH: {r_patch.status_code} {r_patch.text}")
                        return

                    # Checagem rápida
                    r_check = _get(f"{BASE}/Deals({deal_id})")
                    ok = r_check.status_code == 200 and r_check.json().get("OwnerId") == owner_id
                    print("✅ Atualizado com sucesso." if ok else "⚠️ PATCH pode não ter aplicado.")
                    return
                else:
                    print("⌛ Ainda não apareceu deal sem Owner para esse contato. Aguardando...")
                    time.sleep(2)

        print("ℹ️ Não há deal sem OwnerId para esse cliente neste momento.")

    except Exception as e:
        print(f"💥 Erro inesperado no Ploomes: {e}")
