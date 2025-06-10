# Simula uma fila de round-robin entre vendedores
fila = [
    "joao@jflrealty.com.br",
    "maria@jflrealty.com.br",
    "pedro@jflrealty.com.br"
]

# Index atual da fila (rotaciona a cada chamada)
index_atual = 0

async def get_proximo_vendedor():
    global index_atual
    vendedor = fila[index_atual]
    index_atual = (index_atual + 1) % len(fila)
    return [vendedor]
