"""Copiar apenas os três ficheiros validados, sem fazer upload."""
import hashlib
import shutil
from config import PASTA_PROJETO, NOME_CASO, NOME_EXECUCAO
from verificar_lote import verificar


def preparar():
    origem = PASTA_PROJETO / 'resultados' / NOME_CASO / NOME_EXECUCAO
    destino = PASTA_PROJETO / 'resultados_piloto' / NOME_CASO / NOME_EXECUCAO
    registo = verificar(origem)
    if registo['caso'] != NOME_CASO or registo['execucao'] != NOME_EXECUCAO:
        raise ValueError('O lote não corresponde ao caso e execução selecionados.')
    nomes = ('caracteristicas.npz', 'coordenadas.csv', 'execucao.json')
    def sha(p):
        return hashlib.sha256(p.read_bytes()).digest()
    for nome in nomes:
        if (destino / nome).exists() and sha(destino / nome) != sha(origem / nome):
            raise FileExistsError(f'Cópia diferente já existe: {destino / nome}')
    destino.mkdir(parents=True, exist_ok=True)
    for nome in nomes:
        if not (destino / nome).exists():
            shutil.copy2(origem / nome, destino / nome)
        if sha(destino / nome) != sha(origem / nome):
            raise RuntimeError(f'Falha na verificação da cópia: {nome}')
    print('Três ficheiros preparados em:', destino)
    print('Nenhum ficheiro foi enviado ao GitHub.')


if __name__ == '__main__':
    preparar()
