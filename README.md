# Projeto OWL — guia de utilização

Projeto académico de previsão de recorrência bioquímica do cancro da próstata e estudo de explicações por remoção de regiões de imagens histológicas.

## Estado atual

O fluxo atual permite verificar uma lâmina e a máscara de tecido, extrair recortes em lote e guardar as 768 características de cada recorte com o Phikon. O caso 0466 já foi processado com 1 000 recortes. Este guia cobre a preparação dos dados para o futuro modelo de sobrevivência.

## 1. Preparar o computador

Instalar Python (a versão usada neste projeto é 3.14.7) e VS Code.

## 2. Obter o código

No GitHub, abrir o repositório, selecionar **Code → Download ZIP**, extrair o ZIP e abrir a pasta no VS Code em **File → Open Folder**. Quem já utiliza Git pode clonar o repositório.

Abrir **Terminal → New Terminal**. Confirmar que o terminal está na pasta do projeto.

## 3. Criar o ambiente Python

No macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows, em PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, usar um terminal Command Prompt no VS Code e executar `.venv\Scripts\activate.bat`.

Deve aparecer `(.venv)` no início da linha. Sempre que abrir um novo terminal, volte a ativar o ambiente.

Instalar as dependências:

```bash
python -m pip install -r requirements.txt
```

No VS Code, abrir **Python: Select Interpreter** pela paleta de comandos e selecionar o Python de `.venv`.

## 4. Organizar os dados locais

Criar estas pastas na raiz do projeto:

| Pasta | Conteúdo |
|---|---|
| `imagens/` | Imagens originais `.tif`. |
| `mascaras/` | Máscaras correspondentes, com o sufixo `_tissue.tif`. |
| `dados/` | `training_labels.csv`. |
| `resultados/` | Ficheiros produzidos pelos scripts; a pasta é criada pelo código quando necessário. |


## 5. Configurar um caso novo

Em `config.py`, altera estas três linhas. O exemplo usa o caso 0596. Usa o identificador do teu caso sem `.tif` nem `_tissue`.

```python
NOME_CASO = "case_radboud_0596"
NOME_EXECUCAO = "piloto_v1_1000"
QUANTIDADE_RECORTES = 1000
```

Coloca `case_radboud_0596.tif` em `imagens/` e `case_radboud_0596_tissue.tif` em `mascaras/`. Usa a mesma revisão do Phikon e os parâmetros de preparação acordados pelo grupo.

## 6. Verificar a lâmina e a máscara

Executa na raiz do projeto, com o ambiente virtual ativo:

```bash
python verificar_imagem.py
python verificar_mascara.py
```

Os comandos mostram as dimensões de cada nível. Na imagem, confirma também os valores de MPP em X e Y. O script de extração precisa de ambos para calcular o tamanho do recorte na lâmina original.

Compara as duas listas e escolhe níveis reduzidos com **largura e altura exatamente iguais**. No caso 0466, o nível 3 da imagem e o nível 2 da máscara têm ambos 1408 × 1424 píxeis. Para cada caso novo, usa os níveis encontrados na respetiva listagem. Se não houver um par com dimensões iguais ou faltar um dos valores MPP, regista o caso para revisão.

Gera as prévias com os níveis escolhidos. Este comando usa os valores do **0466** como exemplo:

```bash
python gerar_previas.py --nivel-imagem 3 --nivel-mascara 2
python sobrepor_mascara.py
```

Abre `resultados/<caso>/previas/<caso>_sobreposicao.png`. Confirma que a região vermelha acompanha o tecido. Se estiver deslocada ou cobrir o fundo, revê a correspondência entre os ficheiros antes de extrair recortes. Os níveis escolhidos aqui servem para a visualização. A extração usa a máscara no nível 0 e calcula a escala a partir das dimensões originais.

## 7. Processar o caso

```bash
python extrair_lote.py
python phikon_lote.py
```

Executa o segundo comando após o primeiro terminar. O `execucao.json` é gerado automaticamente pelo Phikon em cada execução; não é preciso executar testes separados nem copiar um JSON de outro caso. Não alteres a configuração entre os dois comandos. Na primeira utilização, o Phikon descarrega os pesos para o computador. O processamento usa MPS quando disponível e CPU nos restantes casos.

Os ficheiros ficam em `resultados/<caso>/<execucao>/`.

| Ficheiro | Conteúdo |
|---|---|
| `recorte_*.png` | Recortes preparados para o Phikon. |
| `coordenadas.csv` | Posição, escala e fração estimada de tecido de cada recorte. |
| `caracteristicas.npz` | Características, coordenadas e nomes dos recortes na mesma ordem. |
| `preparacao.json` | Parâmetros realmente usados na extração; permite verificar a configuração antes de executar o Phikon. |
| `execucao.json` | Caso, revisão do modelo, parâmetros e contagem de recortes processados. |

Para o piloto de 1 000 recortes, confirma no terminal ou no JSON que o formato é **(1000, 768)**. Para visualizar a distribuição dos recortes na lâmina, executa `python visualizar_amostragem.py` e abre `visualizacoes/<caso>/<execucao>/distribuicao_recortes.png`. Esta pasta reúne os mapas de todos os casos e pode ser incluída no GitHub.

Se a extração indicar que a pasta já existe, usa um novo `NOME_EXECUCAO` para repetir o processamento. Se já tiveres os recortes, o CSV e o `preparacao.json` e faltar o NPZ, podes executar diretamente `python phikon_lote.py` com a configuração desse lote.

Avisa o grupo de qual caso vais processar para evitar duplicações.

## 8. Como partilhar os resultados do piloto no GitHub

Os scripts escrevem em `resultados/<caso>/<execucao>/`. Para partilhar um lote verificado, copia apenas o NPZ, o CSV e o JSON para `resultados_piloto/<caso>/<execucao>/`. Usem o repositório privado do grupo se as condições do OWL permitirem versionar os resultados derivados.

Exemplo para a lâmina 0466, a partir da raiz do projeto:

```bash
caso=case_radboud_0466
execucao=piloto_v1_1000
origem="resultados/$caso/$execucao"
destino="resultados_piloto/$caso/$execucao"

mkdir -p "$destino"
cp -i "$origem/caracteristicas.npz" "$origem/coordenadas.csv" "$origem/execucao.json" "$destino/"
git add -- "$destino/caracteristicas.npz" "$destino/coordenadas.csv" "$destino/execucao.json"
git diff --cached --name-status
git commit --only -m "Adicionar lote OWL $caso" -- "$destino/caracteristicas.npz" "$destino/coordenadas.csv" "$destino/execucao.json"
git log --oneline origin/main..HEAD
git push
```

Confirma a lista de commits antes do push. As colegas recebem o lote com `git pull`. Atualiza o [registo do piloto](Registo_piloto_OWL.md) com o caminho do lote. Para a agregação, os ficheiros do piloto estão em `resultados_piloto/` e os rótulos continuam em `dados/training_labels.csv`.

Mantém `imagens/`, `mascaras/`, `dados/` e `resultados/` no `.gitignore`. Inclui no GitHub o código, a configuração, o README, o registo e os lotes selecionados em `resultados_piloto/`.

## 9. Erros frequentes

| Situação | O que verificar |
|---|---|
| `Unsupported or missing image file` | Caminho, download completo e nome exato; a máscara termina em `_tissue.tif`. |
| `ModuleNotFoundError` | Ambiente `.venv` ativo e dependências instaladas nesse ambiente. |
| `FileNotFoundError` | Pastas, nome do caso e ordem de execução dos scripts. |
| PNG da máscara parece preto | Os valores podem ser 0 e 1; verificar a sobreposição colorida. |
| Aviso de falta de `HF_TOKEN` | O teste público já funcionou sem token; esperar o download ou verificar limites se falhar. |
| Aviso de `use_fast` | No preparador, usar `backend="pil"` na versão já testada. |
| Pesos `pooler` inesperados | No teste atual, a camada é excluída intencionalmente com `add_pooling_layer=False`; o vetor vem do CLS token. |



## Organização do repositório

Os scripts do fluxo ficam na raiz. Os mapas de distribuição ficam em `visualizacoes/<caso>/<execucao>/`, separados dos resultados e disponíveis para versionamento no GitHub. As prévias ficam em `resultados/<caso>/previas/` e cada lote em `resultados/<caso>/<execucao>/`. Testes e resultados antigos ficam fora do projeto, num arquivo recuperável. A configuração inicial usa o caso 0466 e 1 000 recortes; para outro caso, altera os campos da secção 5. O mesmo nome de execução pode ser usado para pacientes diferentes.
