def distribuir_agendamento(agendamento, vendedores, disponibilidade):
    # 1. Se alguém tem slot em < 30min
    for v in disponibilidade:
        if v["proximo_horario"] <= 30:
            return v["email"]

    # 2. Se todos indisponíveis
    if not any(v["disponivel"] for v in disponibilidade):
        return "victor@jflrealty.com.br"

    # 3. Round-robin (persistido em banco)
    for v in disponibilidade:
        if v["disponivel"]:
            return v["email"]

    return None
