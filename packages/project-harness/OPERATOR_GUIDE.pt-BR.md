# Project Harness — guia operacional

Este é o contrato operacional completo e agent-agnostic do runtime instalado. Ele não exige uma Skill formal nem uma API específica de agente. Use um único executável público do Python 3.10+ e o entrypoint local ao target indicado abaixo.

- Entrypoint: `project_harness.py`
- Package: `project-harness` v`0.2.2`

## Memória operacional

A memória operacional permanece dentro do projeto selecionado: um documento de estado canônico e projeções Markdown determinísticas.

- Estado canônico: `.project-harness/state.json`
- Projeções legíveis: `docs/decisions.md`, `docs/next-actions.md`, `docs/session-log.md`

## Readiness de instalação

- O target explícito é a raiz de um único projeto real.
- O write boundary desse projeto está compreendido e não inclui projetos irmãos.
- O escopo solicitado é memória operacional local ao projeto, não coordenação entre vários projetos.

## Readiness significa

O inventário exato do runtime está instalado, o estado do projeto foi inicializado, as projeções gerenciadas passam em verify e o projeto pode ser aberto a partir da próxima ação persistida.

## Antes de um write

Inspecione em modo read-only, informe o comando pretendido, os inputs, os paths e os efeitos e então obtenha confirmação explícita. Nunca infira, reorganize nem resuma dados do projeto para uma mutação. Mantenha placeholders até o usuário fornecer os valores correspondentes.

## Inventário de comandos

| Comando | Categoria | Finalidade | Inputs | Efeitos |
| --- | --- | --- | --- | --- |
| `init` | `write` | Fazer preview ou inicializar o estado delimitado do projeto e as projeções gerenciadas de contexto. | `<project-root>`, `--dry-run&#124;apply` | O dry-run não escreve; o apply cria ou reconcilia apenas os paths gerenciados declarados e locais ao projeto. |
| `verify` | `read` | Verificar o estado canônico, os markers de ownership e cada projeção gerenciada. | `<project-root>` | Lê o estado delimitado do projeto e informa drift sem fazer repair. |
| `status` | `read` | Mostrar o estado durável atual e a próxima ação. | `<project-root>` | Lê o estado canônico sem alterar arquivos do projeto. |
| `open` | `read` | Abrir um bloco de trabalho a partir do contexto durável do projeto. | `<project-root>` | Retorna o contexto de retomada e a próxima ação sem writes. |
| `digest` | `read` | Reunir os registros duráveis delimitados para revisão. | `<project-root>` | Retorna contexto registrado de forma determinística e não sintetiza nem persiste conteúdo novo. |
| `checkpoint` | `write` | Persistir um registro intermediário explícito do trabalho e uma próxima ação. | `<project-root>`, `<session-id>`, `<summary>`, `<decision>`, `<task>`, `<next-step>` | Acrescenta conteúdo confirmado ao estado canônico e atualiza suas projeções gerenciadas. |
| `close` | `write` | Encerrar o bloco de trabalho atual com um ponto de retomada durável e explícito. | `<project-root>`, `<session-id>`, `<summary>`, `<decision>`, `<task>`, `<next-step>` | Persiste o closeout confirmado e a próxima ação no estado canônico e nas projeções. |

## Exemplos com placeholders

### `init`

```text
<python> -B project_harness.py init --root "<project-root>" --dry-run
```

### `verify`

```text
<python> -B project_harness.py verify --root "<project-root>" --json
```

### `status`

```text
<python> -B project_harness.py status --root "<project-root>" --json
```

### `open`

```text
<python> -B project_harness.py open --root "<project-root>" --json
```

### `digest`

```text
<python> -B project_harness.py digest --root "<project-root>" --json
```

### `checkpoint`

```text
<python> -B project_harness.py checkpoint --root "<project-root>" --session "<session-id>" --summary "<summary>" --decision "<decision>" --task "<task>" --next-step "<next-step>" --json
```

### `close`

```text
<python> -B project_harness.py close --root "<project-root>" --session "<session-id>" --summary "<summary>" --decision "<decision>" --task "<task>" --next-step "<next-step>" --json
```

## Workflows

### Primeiro uso

Fazer preview da inicialização, aplicar após confirmação, executar verify e abrir o primeiro bloco de trabalho.

`init` → `verify` → `open`

### Uso diário

Abrir o contexto durável, revisá-lo e salvar somente um checkpoint confirmado quando necessário.

`open` → `digest` → `checkpoint`

### Closeout e retomada

Fazer closeout com uma próxima ação explícita e depois retomar a partir desse ponto persistido.

`close` → `open`

### Verify ou recovery

Executar verify primeiro; quando o estado canônico estiver válido mas as projeções tiverem drift, fazer preview e repetir init antes de verificar novamente.

`verify` → `init` → `verify`

## Receipt de instalação, rollback, update e uninstall

- Receipt: path relativo ao target `.agent-harnesses/runtime/project-harness/0.2.2/.agent-harness-receipt.json`.
- A partir de um bundle `0.2.2` com checksum verificado, antecipe a remoção do package com `<python> -B installer.py uninstall project-harness --target "<target>" --dry-run --json`; após a revisão, aplique-a com `<python> -B installer.py uninstall project-harness --target "<target>" --apply --json`.
- Uninstall remove somente o runtime pertencente ao receipt e o bloco de onboarding gerenciado pelo installer. Ele nunca remove o estado operacional inicializado.
- Se uma etapa falhar após o apply do package, primeiro execute o workflow de verify ou recovery deste package. Se o target ainda não estiver ready, antecipe e depois aplique o uninstall para executar rollback do package. Preserve e informe qualquer estado inicializado residual; nunca o apague automaticamente.
- Para update, baixe o ZIP e o checksum sidecar correspondentes à nova versão, verifique o checksum, leia as migration notes e então execute doctor, install --dry-run e install --apply com o novo bundle. Não edite um runtime versionado in-place; mantenha a versão anterior até a nova chegar a ready=true.

## Tutorial obrigatório após readiness

Depois que a verificação do instalador retornar `ready=true`, leia este guia e `operations.json` e ensine ao usuário, na conversa, o harness instalado. Não crie um arquivo de tutorial. Cubra:

- O modelo mental: o que o harness instalado preserva e o que permanece fora do seu limite.
- As localizações exatas e locais ao target da memória operacional canônica e das projeções legíveis.
- Cada comando instalado, sua categoria read, write ou repair e quando usá-lo.
- Os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery.
- Um primeiro exemplo seguro que use somente valores confirmados pelo usuário e preserve placeholders para tudo que for desconhecido.
- Como encerrar, retomar, verificar e executar recovery sem inventar estado.
- O receipt de instalação, como prever mutações e como executar rollback, update ou uninstall.

Entregue o tutorial no idioma do usuário e na conversa sem criar documentação no projeto. Use somente valores fornecidos explicitamente pelo usuário; caso contrário, mantenha placeholders. Não instale nem oriente a instalação de qualquer adapter global de agente.

## Suporte

- LinkedIn: https://www.linkedin.com/in/fabianomag/
- Email: fm@fabianomag.com
