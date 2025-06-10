from fastapi import FastAPI, Request
from distribution import distribuir_agendamento
from calendar_service import buscar_disponibilidades
from database import get_proximo_vendedor
from config import ADMIN_EMAIL

app = FastAPI()

@app.post("/webhook")
async def receber_agendamento(request: Request):
    body = await request.json()
    print("Novo agendamento:", body)

    # TODO: validar assinatura com segredo
    vendedores = await get_proximo_vendedor()
    disponibilidade = await buscar_disponibilidades(vendedores)

    responsavel = distribuir_agendamento(body, vendedores, disponibilidade)
    return {"assigned_to": responsavel or ADMIN_EMAIL}
