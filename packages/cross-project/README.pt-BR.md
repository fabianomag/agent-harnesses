<!-- BEGIN GENERATED:PRODUCT -->
# Multi-Project Harness

[English](README.md) · Versão `0.2.2`

**Melhor opção para:** Projetos independentes com raízes próprias que precisam de handoffs explícitos e coordenação transversal.

**Não serve para:** Um índice de projetos filhos contidos ou um cadastro central novo e estrito com recuperação por histórico transacional.

**O que muda:** Cria um manifest canônico de coordenação e sínteses controladas na raiz, sem assumir a responsabilidade pelos detalhes locais de cada projeto.

Pontos fortes: **Projetos independentes · Handoffs · Sincronização estrutural**. Complexidade: média.

**Readiness significa:** O manifest de coordenação contém ao menos um registro explícito de projeto existente, cada projeção gerenciada corresponde a ele e hq-sync informa estado consistente.

**Antes da instalação, confirme:**

- A coordination root e as raízes independentes dos projetos existentes estão explícitas.
- Os projetos têm boundaries conhecidos e uma necessidade real de handoffs ou structural sync entre raízes.
- O usuário pode fornecer o papel e a próxima ação de cada projeto selecionado sem descoberta de repositórios nem estado inventado.

## Instalação

Copie somente este prompt:

```text
Instale Multi-Project Harness (`cross-project`) v0.2.2 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.2/cross-project-0.2.2.zip.

Antes de propor a execução, confirme cada fato de readiness do harness selecionado:
- A coordination root e as raízes independentes dos projetos existentes estão explícitas.
- Os projetos têm boundaries conhecidos e uma necessidade real de handoffs ou structural sync entre raízes.
- O usuário pode fornecer o papel e a próxima ação de cada projeto selecionado sem descoberta de repositórios nem estado inventado.
Se algum fato for desconhecido ou falso, pare antes de downloads ou writes no target, explique o que precisa ser organizado primeiro e ofereça os contatos de suporte abaixo.

Se o modo atual não puder executar, peça a mudança para um modo capaz de executar somente depois de apresentar o plano e receber a confirmação.

Use o Plan mode nativo e structured questions do agente quando disponíveis; caso contrário, apresente o mesmo plano e as mesmas perguntas na conversa. Trabalhe em duas etapas explícitas: primeiro o plano e depois a execução somente após confirmação. Antes de qualquer escrita, inclusive download ou extração temporária, inspecione apenas o diretório-alvo explícito e o ferramental público disponível em modo read-only. Apresente quatro checklists separados: (1) fit e target, (2) segurança e plano de writes, (3) inicialização e readiness e (4) tutorial e handoff. Informe o harness selecionado, o target, um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`), as escritas previstas, os dados necessários para inicialização, a verificação, o rollback e o tutorial; peça ao usuário que confirme esse plano. Nunca use um runtime privado do Codex. Não organize, renomeie, resuma, migre nem infira dados do projeto do usuário. Pergunte por qualquer valor ausente em vez de inventá-lo. Após a confirmação, baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado, valide a soma SHA-256 antes de extrair ou executar qualquer arquivo e extraia o pacote. Na raiz do pacote extraído, execute:
`<python> -B installer.py doctor cross-project --target "<target>" --json`
Se doctor ou qualquer verificação de readiness anterior ao apply falhar, pare com zero writes no target, limpe somente os arquivos temporários isolados e recomende a opção mais adequada quando aplicável; nunca substitua silenciosamente por outro harness. Depois execute:
`<python> -B installer.py install cross-project --target "<target>" --dry-run --json`
Compare o resultado com o plano confirmado e pergunte novamente se o conjunto de writes ou as premissas mudaram de forma relevante. Caso contrário, execute:
`<python> -B installer.py install cross-project --target "<target>" --apply --json`
Siga `package/README.pt-BR.md` para inicializar o target, sempre antecipando cada mutação do runtime e usando somente valores confirmados pelo usuário. Se qualquer etapa falhar depois do primeiro apply ou a readiness final for falsa, interrompa a execução normal e siga o procedimento documentado de rollback ou recovery do package exato, faça preview antes do apply, preserve arquivos não relacionados, verifique a restauração em direção ao estado exato anterior à instalação e informe qualquer mudança residual inevitável em vez de declarar sucesso. Na raiz do pacote, execute:
`<python> -B installer.py verify cross-project --target "<target>" --json`
Só declare sucesso quando o resultado final contiver `ready=true`. Após readiness, leia `operations.json` e `OPERATOR_GUIDE.pt-BR.md` no runtime instalado e apresente ao usuário, na conversa, um tutorial conciso que cubra cada comando, os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery, exemplos seguros com valores confirmados ou placeholders e orientações de update/uninstall. Não crie arquivos de tutorial. Limpe os arquivos temporários e informe receipt, evidência de readiness, estado do rollback e localização do runtime. Ofereça suporte pelo LinkedIn em https://www.linkedin.com/in/fabianomag/ ou pelo email fm@fabianomag.com. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.

Entregue o tutorial no idioma do usuário e na conversa sem criar documentação no projeto. Use somente valores fornecidos explicitamente pelo usuário; caso contrário, mantenha placeholders. Não instale nem oriente a instalação de qualquer adapter global de agente.
```

O runtime instalado inclui `operations.json` e `OPERATOR_GUIDE.pt-BR.md`; após `ready=true`, o coding agent deve ler ambos e ensinar ao usuário, na conversa, o ciclo operacional completo.
<!-- END GENERATED:PRODUCT -->

## Primeiro uso

Use somente paths, papéis e próximas ações de projetos independentes já
confirmados pelo usuário; não crie projetos de exemplo nem descubra
repositórios. Use como `<python>` o mesmo executável público do Python 3.10+
escolhido no prompt de instalação. No diretório do runtime em
`<raiz-coordenadora>/.agent-harnesses/runtime/cross-project/0.2.2`:

```text
<python> -B scripts/cross_project.py bom-dia --root "<raiz-coordenadora>"
<python> -B scripts/cross_project.py hq-init --root "<raiz-coordenadora>" --dry-run --front "<id-da-frente>" --name "<nome-da-frente>" --path "<path-do-projeto>" --role "<papel-confirmado>" --next "<próxima-ação-confirmada>"
<python> -B scripts/cross_project.py hq-init --root "<raiz-coordenadora>" --front "<id-da-frente>" --name "<nome-da-frente>" --path "<path-do-projeto>" --role "<papel-confirmado>" --next "<próxima-ação-confirmada>"
<python> -B scripts/cross_project.py hq-sync --root "<raiz-coordenadora>"
```

Continue com `digere`, `registra` e `encerra`. O state schema `1` permanece
compatível. O rollback cobre falhas capturáveis entre processos cooperativos,
não power loss nem substituição adversarial da raiz. A
[referência avançada](docs/REFERENCE.md) preserva os contratos de bloqueio,
rollback, recuperação e evidência; o
[guia operacional](OPERATOR_GUIDE.pt-BR.md) ensina o ciclo completo. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.2/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.2/graphs/cross-project.graph.json).
Execute `<python> -B installer.py verify cross-project --target
"<raiz-coordenadora>" --json` na raiz do pacote ainda extraído; `installer.py`
não é copiado para o runtime.
