# Fila de round-robin entre vendedores
fila = [
    "gabriel.previati@jflliving.com.br",
    "douglas.macedo@jflliving.com.br",
    "marcos.rigol@jflliving.com.br",
]

_index_atual = 0

def get_proximo_vendedor():
    global _index_atual
    if not fila:
        return []
    vendedor = fila[_index_atual]
    _index_atual = (_index_atual + 1) % len(fila)
    # O main espera uma lista de emails
    return [vendedor]
