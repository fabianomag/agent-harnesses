<!-- BEGIN GENERATED:PRODUCT -->
# Project Harness

[English](README.md) · Versão `0.2.2`

**Melhor opção para:** Um projeto explícito que precisa de checkpoints, closeout e retomada confiável.

**Não serve para:** Coordenação entre projetos filhos de um workspace ou raízes de projetos independentes.

**O que muda:** Cria um diretório próprio de estado e blocos controlados de contexto dentro do projeto selecionado.

Pontos fortes: **Checkpoints · Closeout e retomada · Configuração rápida**. Complexidade: baixa.

**Readiness significa:** O inventário exato do runtime está instalado, o estado do projeto foi inicializado, as projeções gerenciadas passam em verify e o projeto pode ser aberto a partir da próxima ação persistida.

**Antes da instalação, confirme:**

- O target explícito é a raiz de um único projeto real.
- O write boundary desse projeto está compreendido e não inclui projetos irmãos.
- O escopo solicitado é memória operacional local ao projeto, não coordenação entre vários projetos.

## Instalação

Copie somente este prompt:

```text
Instale Project Harness (`project-harness`) v0.2.2 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.2/project-harness-0.2.2.zip.

Antes de propor a execução, confirme cada fato de readiness do harness selecionado:
- O target explícito é a raiz de um único projeto real.
- O write boundary desse projeto está compreendido e não inclui projetos irmãos.
- O escopo solicitado é memória operacional local ao projeto, não coordenação entre vários projetos.
Se algum fato for desconhecido ou falso, pare antes de downloads ou writes no target, explique o que precisa ser organizado primeiro e ofereça os contatos de suporte abaixo.

Se o modo atual não puder executar, peça a mudança para um modo capaz de executar somente depois de apresentar o plano e receber a confirmação.

Use o Plan mode nativo e structured questions do agente quando disponíveis; caso contrário, apresente o mesmo plano e as mesmas perguntas na conversa. Trabalhe em duas etapas explícitas: primeiro o plano e depois a execução somente após confirmação. Antes de qualquer escrita, inclusive download ou extração temporária, inspecione apenas o diretório-alvo explícito e o ferramental público disponível em modo read-only. Apresente quatro checklists separados: (1) fit e target, (2) segurança e plano de writes, (3) inicialização e readiness e (4) tutorial e handoff. Informe o harness selecionado, o target, um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`), as escritas previstas, os dados necessários para inicialização, a verificação, o rollback e o tutorial; peça ao usuário que confirme esse plano. Nunca use um runtime privado do Codex. Não organize, renomeie, resuma, migre nem infira dados do projeto do usuário. Pergunte por qualquer valor ausente em vez de inventá-lo. Após a confirmação, baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado, valide a soma SHA-256 antes de extrair ou executar qualquer arquivo e extraia o pacote. Na raiz do pacote extraído, execute:
`<python> -B installer.py doctor project-harness --target "<target>" --json`
Se doctor ou qualquer verificação de readiness anterior ao apply falhar, pare com zero writes no target, limpe somente os arquivos temporários isolados e recomende a opção mais adequada quando aplicável; nunca substitua silenciosamente por outro harness. Depois execute:
`<python> -B installer.py install project-harness --target "<target>" --dry-run --json`
Compare o resultado com o plano confirmado e pergunte novamente se o conjunto de writes ou as premissas mudaram de forma relevante. Caso contrário, execute:
`<python> -B installer.py install project-harness --target "<target>" --apply --json`
Siga `package/README.pt-BR.md` para inicializar o target, sempre antecipando cada mutação do runtime e usando somente valores confirmados pelo usuário. Se qualquer etapa falhar depois do primeiro apply ou a readiness final for falsa, interrompa a execução normal e siga o procedimento documentado de rollback ou recovery do package exato, faça preview antes do apply, preserve arquivos não relacionados, verifique a restauração em direção ao estado exato anterior à instalação e informe qualquer mudança residual inevitável em vez de declarar sucesso. Na raiz do pacote, execute:
`<python> -B installer.py verify project-harness --target "<target>" --json`
Só declare sucesso quando o resultado final contiver `ready=true`. Após readiness, leia `operations.json` e `OPERATOR_GUIDE.pt-BR.md` no runtime instalado e apresente ao usuário, na conversa, um tutorial conciso que cubra cada comando, os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery, exemplos seguros com valores confirmados ou placeholders e orientações de update/uninstall. Não crie arquivos de tutorial. Limpe os arquivos temporários e informe receipt, evidência de readiness, estado do rollback e localização do runtime. Ofereça suporte pelo LinkedIn em https://www.linkedin.com/in/fabianomag/ ou pelo email fm@fabianomag.com. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.

Entregue o tutorial no idioma do usuário e na conversa sem criar documentação no projeto. Use somente valores fornecidos explicitamente pelo usuário; caso contrário, mantenha placeholders. Não instale nem oriente a instalação de qualquer adapter global de agente.
```

O runtime instalado inclui `operations.json` e `OPERATOR_GUIDE.pt-BR.md`; após `ready=true`, o coding agent deve ler ambos e ensinar ao usuário, na conversa, o ciclo operacional completo.
<!-- END GENERATED:PRODUCT -->

## Primeiro uso

Use como `<python>` o mesmo executável público do Python 3.10+ escolhido no
prompt de instalação. No diretório do runtime instalado,
`<raiz-do-projeto>/.agent-harnesses/runtime/project-harness/0.2.2`:

```text
<python> -B project_harness.py init --root "<raiz-do-projeto>" --dry-run
<python> -B project_harness.py init --root "<raiz-do-projeto>"
<python> -B project_harness.py verify --root "<raiz-do-projeto>"
<python> -B project_harness.py open --root "<raiz-do-projeto>"
```

Use `checkpoint` durante o trabalho e `close` no encerramento. A instalação
guiada só termina quando `<python> -B installer.py verify project-harness
--target "<raiz-do-projeto>" --json` retornar `"ready": true`. Execute esse
`verify` na raiz do pacote ainda extraído; `installer.py` não é copiado para o
runtime.

Package version e state schema são independentes. O runtime `0.2.2` cria state
schema `1` e lê e verifica o estado `0.1.0` sem reescrever `harnessVersion`;
não há migração implícita. O harness é local ao projeto e não coordena roots
irmãs nem serviços externos. Ele preserva texto existente fora de seus blocos
gerenciados. Use o dry-run do runtime antes de qualquer repair; uninstall remove
somente bytes inalterados pertencentes ao receipt e preserva os arquivos de
estado inicializados. O
[guia operacional](OPERATOR_GUIDE.pt-BR.md) ensina o ciclo completo; a
[referência avançada](docs/REFERENCE.md) preserva os contratos técnicos de
colisão, rollback, recuperação e evidência. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.2/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.2/graphs/project-harness.graph.json).
