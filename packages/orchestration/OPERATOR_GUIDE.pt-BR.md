# Control Plane Harness — guia operacional

Este é o contrato operacional completo e agent-agnostic do runtime instalado. Ele não exige uma Skill formal nem uma API específica de agente. Use um único executável público do Python 3.10+ e o entrypoint local ao target indicado abaixo.

- Entrypoint: `hq.py`
- Package: `orchestration` v`0.2.1`

## Memória operacional

A nova raiz do control plane mantém um registry transacional e projeções do ciclo de vida; as frentes registradas preservam seus registros delimitados nos paths confirmados.

- Estado canônico: `.orchestration/manifest.json`
- Projeções legíveis: `FRONTS.md`, `NEXT.md`, `<front-path>/REFLECTIONS.md`, `<front-path>/RECORDS.md`, `<front-path>/SESSIONS.md`

## Readiness de instalação

- O target explícito é uma nova raiz Master ou de control plane deliberada, não uma estrutura de coordenação existente a ser adotada.
- As frentes iniciais, seus paths relativos pretendidos e seus boundaries já são conhecidos.
- O trabalho realmente exige registry transacional, validated mutations, rollback e recovery, e não apenas handoffs entre projetos.

## Readiness significa

Um control plane novo contém ao menos uma frente registrada explicitamente, o registry e os arquivos gerados de ciclo de vida estão coerentes, não há recovery pendente e hq-sync informa estado limpo.

## Antes de um write

Inspecione em modo read-only, informe o comando pretendido, os inputs, os paths e os efeitos e então obtenha confirmação explícita. Nunca infira, reorganize nem resuma dados do projeto para uma mutação. Mantenha placeholders até o usuário fornecer os valores correspondentes.

## Inventário de comandos

| Comando | Categoria | Finalidade | Inputs | Efeitos |
| --- | --- | --- | --- | --- |
| `bom-dia` | `read` | Abrir o control plane ou uma frente selecionada e determinar a próxima operação segura. | `<workspace>`, `<front-selector?>` | Lê o registry e os estados de sync e recovery sem writes. |
| `foco` | `write` | Selecionar transacionalmente uma frente registrada e explícita. | `<workspace>`, `<front-selector>` | Atualiza a seleção da frente ativa no registry estrito e nas views determinísticas. |
| `init` | `write` | Fazer preview ou inicializar transacionalmente o control plane e registrar uma nova frente. | `<workspace>`, `<front-id>`, `<front-name>`, `<front-path>`, `<alias?>`, `--dry-run&#124;--apply` | O dry-run não escreve; o apply cria o registry estrito e os arquivos declarados de ciclo de vida do Master e da frente por uma transação com journal. |
| `hq-sync` | `read` | Validar estritamente o registry, os limites das frentes, os arquivos gerados, locks e o estado de recovery. | `<workspace>` | Informa estado limpo ou issues delimitadas sem repair. |
| `digere` | `write` | Persistir uma reflexão explícita e uma ação pendente para a frente selecionada. | `<workspace>`, `<front-selector?>`, `<summary>`, `<pending-action>` | Registra transacionalmente somente a reflexão fornecida e move a frente para o estado digested. |
| `registra` | `write` | Promover o digest explícito atual para um registro durável. | `<workspace>`, `<front-selector?>`, `<note?>` | Registra transacionalmente o digest atual e move a frente selecionada para o estado recorded. |
| `encerra` | `write` | Encerrar um bloco de trabalho registrado com summary e próxima ação explícitos. | `<workspace>`, `<front-selector?>`, `<summary>`, `<next-action>` | Persiste transacionalmente o closeout e o próximo ponto de retomada e move a frente para o estado closed. |
| `repair-panel` | `repair` | Fazer preview ou repair somente de uma divergência derivável no painel gerado de pendências. | `<workspace>`, `--dry-run&#124;--apply` | Faz repair somente do painel gerado depois que todas as verificações de registry e limites passam; nunca redireciona nem mescla frentes. |
| `recover` | `repair` | Inspecionar ou aplicar recovery verificado para um journal durável de transação. | `<workspace>`, `--dry-run&#124;--apply`, `--break-stale-lock?` | Executa rollback de uma transação pre-commit reconhecida ou conclui cleanup verificado após commit durável; bytes desconhecidos interrompem recovery. |

## Exemplos com placeholders

### `bom-dia`

```text
<python> -B hq.py --root "<workspace>" --json bom-dia "<front-selector>"
```

### `foco`

```text
<python> -B hq.py --root "<workspace>" --json foco "<front-selector>"
```

### `init`

```text
<python> -B hq.py --root "<workspace>" --json init --id "<front-id>" --name "<front-name>" --path "<front-path>" --alias "<alias>" --dry-run
```

### `hq-sync`

```text
<python> -B hq.py --root "<workspace>" --json hq-sync
```

### `digere`

```text
<python> -B hq.py --root "<workspace>" --json digere --front "<front-selector>" --summary "<summary>" --pending "<pending-action>"
```

### `registra`

```text
<python> -B hq.py --root "<workspace>" --json registra --front "<front-selector>" --note "<note>"
```

### `encerra`

```text
<python> -B hq.py --root "<workspace>" --json encerra --front "<front-selector>" --summary "<summary>" --next "<next-action>"
```

### `repair-panel`

```text
<python> -B hq.py --root "<workspace>" --json repair-panel --dry-run
```

### `recover`

```text
<python> -B hq.py --root "<workspace>" --json recover --dry-run
```

## Workflows

### Primeiro uso

Abrir em modo read-only, fazer preview de um registro confirmado, aplicar, exigir sync limpo e selecionar a frente registrada.

`bom-dia` → `init` → `hq-sync` → `foco`

### Uso diário

Abrir, exigir sync limpo, selecionar a frente pretendida, persistir somente um digest explícito e promovê-lo deliberadamente.

`bom-dia` → `hq-sync` → `foco` → `digere` → `registra`

### Closeout e retomada

Fazer closeout de um bloco registrado e retomar a partir da próxima ação durável.

`encerra` → `bom-dia`

### Verify ou recovery

Usar hq-sync para diagnóstico, inspecionar recovery antes do apply quando houver journal, usar repair do painel somente no caso derivável e delimitado e exigir sync limpo ao final.

`hq-sync` → `recover` → `repair-panel` → `hq-sync`

## Receipt de instalação, rollback, update e uninstall

- Receipt: path relativo ao target `.agent-harnesses/runtime/orchestration/0.2.1/.agent-harness-receipt.json`.
- A partir de um bundle `0.2.1` com checksum verificado, antecipe a remoção do package com `<python> -B installer.py uninstall orchestration --target "<target>" --dry-run --json`; após a revisão, aplique-a com `<python> -B installer.py uninstall orchestration --target "<target>" --apply --json`.
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
