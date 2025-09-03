def distribuir_agendamento(agendamento, vendedores, disponibilidade):
    # 1) Alguém com slot < 30 min?
    for v in disponibilidade:
        if v["proximo_horario"] <= 30:
            return v["email"]

    # 2) Todos indisponíveis → manda pro Victor
    if not any(v["disponivel"] for v in disponibilidade):
        return "victor.adas@jflrealty.com.br"

    # 3) Round-robin filtrando quem está disponível
    for v in disponibilidade:
        if v["disponivel"]:
            return v["email"]

    return None
