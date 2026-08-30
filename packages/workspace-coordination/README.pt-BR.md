<!-- BEGIN GENERATED:PRODUCT -->
# Workspace Harness

[English](README.md) · Versão `0.2.3`

**Melhor opção para:** Projetos filhos no mesmo workspace que precisam de um pequeno índice compartilhado.

**Não serve para:** Repositórios independentes ou um único projeto sem coordenação de projetos filhos.

**O que muda:** Cria um diretório de controle do workspace e registros de coordenação próprios de cada projeto filho.

Pontos fortes: **Índice dos projetos filhos · Limites de responsabilidade · Visão compartilhada do workspace**. Complexidade: média.

**Readiness significa:** O coordenador está inicializado com pelo menos um projeto filho registrado; cada path de projeto filho e owner path relativo à raiz desse projeto filho é explícito e válido; e o estado canônico e gerado do workspace passa em verify sem issues.

**Antes da instalação, confirme:**

- O target explícito é o workspace contêiner, não um de seus projetos filhos.
- Os projetos filhos existentes e contidos que serão registrados já são conhecidos.
- Cada projeto filho selecionado tem um owner file local explícito, identificado por um path relativo à raiz desse projeto filho, e seu estado detalhado continuará sob ownership local.

## Instalação

Copie somente este prompt:

```text
Instale Workspace Harness (`workspace-coordination`) v0.2.3 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.3/workspace-coordination-0.2.3.zip.

Antes de propor a execução, confirme cada fato de readiness do harness selecionado:
- O target explícito é o workspace contêiner, não um de seus projetos filhos.
- Os projetos filhos existentes e contidos que serão registrados já são conhecidos.
- Cada projeto filho selecionado tem um owner file local explícito, identificado por um path relativo à raiz desse projeto filho, e seu estado detalhado continuará sob ownership local.
Se algum fato for desconhecido ou falso, pare antes de downloads ou writes no target, explique o que precisa ser organizado primeiro e ofereça os contatos de suporte abaixo.

Se o modo atual não puder executar, peça a mudança para um modo capaz de executar somente depois de apresentar o plano e receber a confirmação.

Use o Plan mode nativo e structured questions do agente quando disponíveis; caso contrário, apresente o mesmo plano e as mesmas perguntas na conversa. Trabalhe em duas etapas explícitas: primeiro o plano e depois a execução somente após confirmação. Antes de qualquer escrita, inclusive download ou extração temporária, inspecione apenas o diretório-alvo explícito e o ferramental público disponível em modo read-only. Apresente quatro checklists separados: (1) fit e target, (2) segurança e plano de writes, (3) inicialização e readiness e (4) tutorial e handoff. Informe o harness selecionado, o target, um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`), as escritas previstas, os dados necessários para inicialização, a verificação, o rollback e o tutorial; peça ao usuário que confirme esse plano. Nunca use um runtime privado do Codex. Não organize, renomeie, resuma, migre nem infira dados do projeto do usuário. Pergunte por qualquer valor ausente em vez de inventá-lo. Após a confirmação, baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado, valide a soma SHA-256 antes de extrair ou executar qualquer arquivo e extraia o pacote. Na raiz do pacote extraído, execute:
`<python> -B installer.py doctor workspace-coordination --target "<target>" --json`
Se doctor ou qualquer verificação de readiness anterior ao apply falhar, pare com zero writes no target, limpe somente os arquivos temporários isolados e recomende a opção mais adequada quando aplicável; nunca substitua silenciosamente por outro harness. Depois execute:
`<python> -B installer.py install workspace-coordination --target "<target>" --dry-run --json`
Compare o resultado com o plano confirmado e pergunte novamente se o conjunto de writes ou as premissas mudaram de forma relevante. Caso contrário, execute:
`<python> -B installer.py install workspace-coordination --target "<target>" --apply --json`
Siga `package/README.pt-BR.md` para inicializar o target, sempre antecipando cada mutação do runtime e usando somente valores confirmados pelo usuário. Se qualquer etapa falhar depois do primeiro apply ou a readiness final for falsa, interrompa a execução normal e siga o procedimento documentado de rollback ou recovery do package exato, faça preview antes do apply, preserve arquivos não relacionados, verifique a restauração em direção ao estado exato anterior à instalação e informe qualquer mudança residual inevitável em vez de declarar sucesso. Na raiz do pacote, execute:
`<python> -B installer.py verify workspace-coordination --target "<target>" --json`
Só declare sucesso quando o resultado final contiver `ready=true`. Após readiness, leia `operations.json` e `OPERATOR_GUIDE.pt-BR.md` no runtime instalado e apresente ao usuário, na conversa, um tutorial conciso que cubra cada comando, os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery, exemplos seguros com valores confirmados ou placeholders e orientações de update/uninstall. Não crie arquivos de tutorial. Limpe os arquivos temporários e informe receipt, evidência de readiness, estado do rollback e localização do runtime. Ofereça suporte pelo LinkedIn em https://www.linkedin.com/in/fabianomag/ ou pelo email fm@fabianomag.com. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.

Entregue o tutorial no idioma do usuário e na conversa sem criar documentação no projeto. Use somente valores fornecidos explicitamente pelo usuário; caso contrário, mantenha placeholders. Não instale nem oriente a instalação de qualquer adapter global de agente.
```

O runtime instalado inclui `operations.json` e `OPERATOR_GUIDE.pt-BR.md`; após `ready=true`, o coding agent deve ler ambos e ensinar ao usuário, na conversa, o ciclo operacional completo.
<!-- END GENERATED:PRODUCT -->

## Primeiro uso

Use somente paths de projetos filhos e owner files já confirmados pelo usuário;
não crie um workspace de exemplo nem infira projetos filhos. Use como
`<python>` o mesmo executável público do Python 3.10+ escolhido no prompt de
instalação. `--path` é relativo à raiz coordenadora; `--owner` é relativo à
raiz do projeto filho selecionado. Use o runtime em
`<raiz-coordenadora>/.agent-harnesses/runtime/workspace-coordination/0.2.3`:

```text
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" init --dry-run
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" init --apply
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" add --id "<id-do-projeto-filho>" --path "<path-do-projeto-filho>" --owner "<owner-file-relativo-ao-projeto-filho>" --dry-run
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" add --id "<id-do-projeto-filho>" --path "<path-do-projeto-filho>" --owner "<owner-file-relativo-ao-projeto-filho>" --apply
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" verify
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" open --child "<id-do-projeto-filho>"
```

O coordenador não descobre projetos filhos nem executa o trabalho deles. A
versão `0.2.3` exige um único writer de mutações (`single writer`) por raiz
coordenadora; serialize os writers. O state schema permanece `1`. O
[guia operacional](OPERATOR_GUIDE.pt-BR.md) ensina o ciclo completo; a
[referência avançada](docs/REFERENCE.md) preserva os contratos de single
writer, recuperação e evidência. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.3/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.3/graphs/workspace-coordination.graph.json).
Execute `<python> -B installer.py verify workspace-coordination --target
"<raiz-coordenadora>" --json` na raiz do pacote ainda extraído;
`installer.py` não é copiado para o runtime.
