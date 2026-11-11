# Projeto OWL — guia da equipa

Este projeto extrai 1 000 recortes de tecido por lâmina e gera características Phikon de dimensão `(1000, 768)`, coordenadas e um registo JSON. Ainda não treina um modelo de sobrevivência.

## 1. Preparar o computador

Instala Git, Python e VS Code com a extensão Python. O ambiente validado é macOS Apple Silicon com Python 3.14.7. Windows e Linux têm instruções abaixo, mas a execução completa nesses sistemas ainda não foi validada. O processamento usa MPS no Mac compatível e CPU nos restantes computadores; não é necessário configurar CUDA.

Abre um terminal e confirma `git --version`. No Mac/Linux confirma `python3 --version`; no Windows, `py --version`. Usa Python 3.14 para reproduzir o ambiente. Reserva espaço para a imagem original, máscara, ambiente Python, pesos do modelo e recortes; verifica o tamanho dos downloads antes de começar.

## 2. Clonar o repositório

Usa clonagem, não Download ZIP, para receber atualizações e partilhar alterações:

```bash
git clone https://github.com/jhenifferg/projeto-owl.git
cd projeto-owl
```

Abre esta pasta no VS Code. Todos os comandos seguintes são executados na raiz, onde está `config.py`. 

Antes do primeiro commit, configura a tua identidade com `git config user.name "O teu nome"` e `git config user.email "O teu email associado ao GitHub"` dentro desta pasta.

## 3. Instalar as dependências

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
```

Se a ativação for bloqueada, abre Command Prompt e usa `.venv\Scripts\activate.bat`, sem alterar políticas de segurança.

Com o ambiente ativo, em qualquer sistema:

```bash
python -m pip install -r requirements.txt
python -m pip check
python -c "import openslide, torch, transformers, numpy; print('Dependências disponíveis')"
```

O `requirements.txt` inclui a biblioteca nativa `openslide-bin`. S

## 4. Obter os dados do teu caso

Descarrega apenas a lâmina atribuída, a máscara correspondente e os rótulos necessários; não é preciso descarregar o conjunto completo.

Cria estas pastas na raiz e coloca os ficheiros nos caminhos indicados (0466 é um exemplo; usa o teu identificador):

```text
imagens/case_radboud_0466.tif
mascaras/case_radboud_0466_tissue.tif
dados/training_labels.csv
```

As imagens, máscaras e rótulos não são distribuídos com o código. Os rótulos serão necessários para a análise de sobrevivência, mas não para extrair características.

## 5. Configurar o teu caso sem alterar a configuração da equipa

Cria `config_local.json` na raiz com:

```json
{
  "caso": "case_radboud_0466",
  "execucao": "piloto_v1_1000"
}
```

Substitui o caso pelo que combinaste com o grupo. Este ficheiro é ignorado pelo Git, para não provocar conflitos entre colegas. `config.py` mantém os parâmetros comuns: 1 000 recortes, 224 px, 0,5 µm/px, mínimo de 80% de tecido, semente 42 e revisão fixa do Phikon. Não alteres esses parâmetros individualmente. Não alteres a configuração entre a extração e o Phikon.

## 6. Conferir a imagem e a máscara

```bash
python verificar_imagem.py
python verificar_mascara.py
```

Confirma que ambos os ficheiros abrem e que a imagem tem MPP em X e Y. Escolhe níveis reduzidos com largura e altura exatamente iguais. Para 0466, imagem nível 3 e máscara nível 2 têm 1408 × 1424 px:

```bash
python gerar_previas.py --nivel-imagem 3 --nivel-mascara 2
python sobrepor_mascara.py
```

Para outro caso, substitui os níveis pelos valores encontrados. Abre `resultados/<caso>/previas/<caso>_sobreposicao.png` e verifica que a camada vermelha acompanha o tecido. Se não houver níveis iguais, faltar MPP ou a máscara estiver deslocada, interrompe e pede revisão ao grupo.

## 7. Executar o piloto

Executa cada comando apenas depois de o anterior terminar sem erro:

```bash
python extrair_lote.py
python phikon_lote.py
python verificar_lote.py
python visualizar_amostragem.py
```

A pasta `resultados/<caso>/<execucao>/` contém os recortes PNG, `coordenadas.csv`, `preparacao.json`, `caracteristicas.npz` e `execucao.json`. O JSON final é gerado automaticamente na mesma execução. O registo da preparação impede que sejam atribuídos aos recortes parâmetros diferentes dos usados na extração.

O verificador confirma contagem, formato `(1000, 768)`, valores finitos, ordem dos nomes e coordenadas, caso e revisão do modelo. Uma verificação automática não substitui a inspeção visual da máscara.

O mapa fica em `visualizacoes/<caso>/<execucao>/distribuicao_recortes.png`. Esta pasta permite reunir os mapas de todos os casos no GitHub, sem colocar as imagens no README.

Se a pasta do lote já existir, o código protege os resultados. Se só falta o NPZ e a preparação terminou, retoma em `phikon_lote.py`. Se a extração foi interrompida ou pretendes repetir o lote, escolhe outro nome em `config_local.json`, por exemplo `piloto_v1_1000_v2`. Não copies JSONs entre execuções.

## 8. Publicar os resultados no GitHub

Em qualquer sistema, incluindo PowerShell:

```bash
python preparar_partilha.py
```

O comando valida o lote e copia apenas `caracteristicas.npz`, `coordenadas.csv` e `execucao.json` para `resultados_piloto/<caso>/<execucao>/`. Cópias existentes idênticas são aceites; ficheiros diferentes nunca são substituídos. Esta preparação é local e não faz uploads.

Os resultados podem ser publicados no repositório público do grupo, conforme confirmado pela equipa. A pasta `resultados_piloto/` não é ignorada pelo Git; não é necessária uma pasta privada. Para fazer push, usa a tua conta GitHub com o convite de colaboradora aceite.

Depois da preparação, executa os comandos abaixo. O exemplo usa o caso 0466: **substitui `case_radboud_0466`, `piloto_v1_1000` e a mensagem do commit pelo teu caso e execução em todos os caminhos**. Os comandos funcionam em Bash e PowerShell.

```bash
git add -- resultados_piloto/case_radboud_0466/piloto_v1_1000/caracteristicas.npz resultados_piloto/case_radboud_0466/piloto_v1_1000/coordenadas.csv resultados_piloto/case_radboud_0466/piloto_v1_1000/execucao.json
git diff --cached --name-status
git commit --only -m "Adicionar lote OWL 0466" -- resultados_piloto/case_radboud_0466/piloto_v1_1000/caracteristicas.npz resultados_piloto/case_radboud_0466/piloto_v1_1000/coordenadas.csv resultados_piloto/case_radboud_0466/piloto_v1_1000/execucao.json
git pull --rebase
git push
```

Se houver alterações locais pendentes, trata-as antes do pull. Se houver conflito, não uses force push: pede ajuda ao grupo. O `config_local.json` não entra no Git. Atualiza `Registo_piloto_OWL.md` e faz um commit separado desse registo. Para publicar o mapa, adiciona explicitamente o PNG em `visualizacoes/<caso>/<execucao>/` e faz um commit separado. Depois executa `git pull --rebase` e `git push` para enviar também esse commit.

## 9. Receber trabalho das colegas

Com as alterações locais guardadas em commits e sem conflitos:

```bash
git pull --ff-only
```

Um lote publicado aparece em `resultados_piloto/`. Para validar um lote recebido, sem precisar das lâminas nem de executar Phikon:

```bash
python verificar_lote.py --pasta resultados_piloto/case_radboud_0466/piloto_v1_1000
```

Se a pasta não aparecer, confirma que a colega fez push e partilhou o nome do caso. Se `git pull --ff-only` falhar por divergência, pede ajuda para integrar os commits.

## Organização

- Raiz: código, configuração comum, dependências e instruções.
- `config_local.json`: seleção pessoal do caso, ignorada pelo Git.
- `imagens/`, `mascaras/`, `dados/`, `resultados/`: dados e processamento locais, ignorados pelo Git.
- `resultados_piloto/`: três ficheiros por lote preparado para partilha.
- `visualizacoes/`: mapas separados por caso e execução.

## Erros frequentes

| Erro | Como resolver |
|---|---|
| `FileNotFoundError` | Confere os nomes da lâmina e máscara, a configuração local e a ordem dos comandos. |
| `ModuleNotFoundError` | Ativa `.venv` e instala as dependências nesse ambiente. |
| Pasta já existe | Retoma apenas a etapa em falta ou usa um nome novo de execução. |
| Configuração difere da preparação | Restaura os parâmetros usados ou cria outra execução. |
| Poucos candidatos | Regista o caso para revisão; não reduzas o mínimo de tecido sem acordo do grupo. |
| `not a git repository` | Usa a pasta criada por `git clone`, não um ZIP. |
| Push sem permissão | Confirma o convite de colaboradora e a conta autenticada. |
| Máscara parece preta | Os valores podem ser 0 e 1; inspeciona a sobreposição colorida. |
