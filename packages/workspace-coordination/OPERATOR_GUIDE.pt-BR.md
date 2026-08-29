# Workspace Harness — guia operacional

Este é o contrato operacional completo e agent-agnostic do runtime instalado. Ele não exige uma Skill formal nem uma API específica de agente. Use um único executável público do Python 3.10+ e o entrypoint local ao target indicado abaixo.

- Entrypoint: `workspace_coordination.py`
- Package: `workspace-coordination` v`0.2.1`

## Memória operacional

O índice do workspace e os deltas compartilhados permanecem na raiz coordenadora; a continuidade detalhada permanece em cada projeto filho registrado explicitamente.

- Estado canônico: `.workspace-coordination/workspace.json`, `<child-path>/.workspace-coordination/local-state.json`
- Projeções legíveis: `.workspace-coordination/INDEX.md`, `.workspace-coordination/BOUNDARIES.md`, `.workspace-coordination/SHARED_DELTAS.md`

## Readiness de instalação

- O target explícito é o workspace contêiner, não um de seus projetos filhos.
- Os projetos filhos existentes e contidos que serão registrados já são conhecidos.
- Cada projeto filho selecionado tem um owner file local explícito e seu estado detalhado continuará sob ownership local.

## Readiness significa

O coordenador está inicializado, todos os projetos filhos e owner paths registrados são explícitos e válidos e o estado canônico e gerado do workspace passa em verify sem issues.

## Antes de um write

Inspecione em modo read-only, informe o comando pretendido, os inputs, os paths e os efeitos e então obtenha confirmação explícita. Nunca infira, reorganize nem resuma dados do projeto para uma mutação. Mantenha placeholders até o usuário fornecer os valores correspondentes.

## Inventário de comandos

| Comando | Categoria | Finalidade | Inputs | Efeitos |
| --- | --- | --- | --- | --- |
| `init` | `write` | Fazer preview ou inicializar o limite do coordenador do workspace. | `<coordinator-root>`, `--dry-run&#124;--apply` | O dry-run não escreve; o apply cria somente os arquivos canônicos e gerados do coordenador. |
| `add` | `write` | Registrar um projeto filho contido e existente com seu owner file explícito. | `<coordinator-root>`, `<child-id>`, `<child-path>`, `<owner-file>`, `--dry-run&#124;--apply` | Atualiza somente o índice do coordenador e o registro local de coordenação do projeto filho selecionado. |
| `remove` | `write` | Remover um registro de projeto filho sem excluir nem editar o projeto filho. | `<coordinator-root>`, `<child-id>`, `--dry-run&#124;--apply` | Remove somente o estado de registro pertencente ao coordenador e preserva o projeto filho. |
| `open` | `read` | Abrir o contexto delimitado de retomada do coordenador ou de um projeto filho registrado. | `<coordinator-root>`, `<child-id?>` | Lê registros do coordenador e do projeto filho selecionado sem writes. |
| `digest` | `read` | Ler o contexto delimitado de ownership e continuidade de um projeto filho. | `<coordinator-root>`, `<child-id>` | Retorna o contexto local explícito do projeto filho sem descobrir nem copiar outros dados de projeto. |
| `record` | `write` | Acrescentar um registro explícito de continuidade local do projeto filho. | `<coordinator-root>`, `<child-id>`, `<record-key>`, `<record-kind>`, `<summary>`, `<next-action>`, `--dry-run&#124;--apply` | Escreve o registro confirmado somente no estado local pertencente ao harness do projeto filho selecionado. |
| `reflect` | `write` | Refletir um delta compartilhado, conciso e confirmado no coordenador. | `<coordinator-root>`, `<child-id>`, `<reflection-key>`, `<summary>`, `--dry-run&#124;--apply` | Adiciona um delta compartilhado delimitado sem absorver o estado detalhado do projeto filho. |
| `verify` | `read` | Validar o estado do coordenador, os registros, o ownership dos projetos filhos e as views geradas. | `<coordinator-root>` | Informa issues estruturais sem repair. |
| `recover` | `repair` | Fazer preview ou regenerar somente o estado gerenciado recuperável do workspace. | `<coordinator-root>`, `--dry-run&#124;--apply` | Faz repair do estado derivável e gerenciado pelo coordenador sem reconstruir fatos ausentes pertencentes aos projetos filhos. |

## Exemplos com placeholders

### `init`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" init --dry-run
```

### `add`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" add --id "<child-id>" --path "<child-path>" --owner "<owner-file>" --dry-run
```

### `remove`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" remove --id "<child-id>" --dry-run
```

### `open`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" --json open --child "<child-id>"
```

### `digest`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" --json digest --child "<child-id>"
```

### `record`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" record --child "<child-id>" --key "<record-key>" --kind update --summary "<summary>" --next "<next-action>" --dry-run
```

### `reflect`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" reflect --child "<child-id>" --key "<reflection-key>" --summary "<summary>" --dry-run
```

### `verify`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" --json verify
```

### `recover`

```text
<python> -B workspace_coordination.py --root "<coordinator-root>" recover --dry-run
```

## Workflows

### Primeiro uso

Fazer preview e inicializar o coordenador, registrar um projeto filho existente e confirmado, executar verify e abri-lo.

`init` → `add` → `verify` → `open`

### Uso diário

Abrir um projeto filho, digerir somente seu contexto delimitado, registrar a continuidade local e refletir apenas um delta compartilhado confirmado.

`open` → `digest` → `record` → `reflect`

### Closeout e retomada

Registrar um closeout explícito com próxima ação e depois reabrir o projeto filho a partir do estado local.

`record` → `open`

### Verify ou recovery

Executar verify primeiro; fazer preview de recover somente para drift gerenciado e derivável, aplicar após confirmação e executar verify novamente.

`verify` → `recover` → `verify`

## Receipt de instalação, rollback, update e uninstall

- Receipt: path relativo ao target `.agent-harnesses/runtime/workspace-coordination/0.2.1/.agent-harness-receipt.json`.
- A partir de um bundle `0.2.1` com checksum verificado, antecipe a remoção do package com `<python> -B installer.py uninstall workspace-coordination --target "<target>" --dry-run --json`; após a revisão, aplique-a com `<python> -B installer.py uninstall workspace-coordination --target "<target>" --apply --json`.
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
