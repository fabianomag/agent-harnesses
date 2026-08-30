# Multi-Project Harness — guia operacional

Este é o contrato operacional completo e agent-agnostic do runtime instalado. Ele não exige uma Skill formal nem uma API específica de agente. Use um único executável público do Python 3.10+ e o entrypoint local ao target indicado abaixo.

- Entrypoint: `scripts/cross_project.py`
- Package: `cross-project` v`0.2.2`

## Memória operacional

A coordination root mantém o manifest canônico entre projetos e projeções concisas; cada projeto independente preserva sua memória local detalhada.

- Estado canônico: `harness.config.json`
- Projeções legíveis: `AGENTS.md`, `FRONTS.md`, `NEXT.md`

## Readiness de instalação

- A coordination root e as raízes independentes dos projetos existentes estão explícitas.
- Os projetos têm boundaries conhecidos e uma necessidade real de handoffs ou structural sync entre raízes.
- O usuário pode fornecer o papel e a próxima ação de cada projeto selecionado sem descoberta de repositórios nem estado inventado.

## Readiness significa

O manifest de coordenação contém ao menos um registro explícito de projeto existente, cada projeção gerenciada corresponde a ele e hq-sync informa estado consistente.

## Antes de um write

Inspecione em modo read-only, informe o comando pretendido, os inputs, os paths e os efeitos e então obtenha confirmação explícita. Nunca infira, reorganize nem resuma dados do projeto para uma mutação. Mantenha placeholders até o usuário fornecer os valores correspondentes.

## Inventário de comandos

| Comando | Categoria | Finalidade | Inputs | Efeitos |
| --- | --- | --- | --- | --- |
| `bom-dia` | `read` | Abrir o estado de coordenação entre projetos ou o ponto de retomada de um projeto nomeado. | `<coordination-root>`, `<front-id?>` | Lê o estado delimitado de coordenação e informa a próxima ação atual sem writes. |
| `hq-init` | `write` | Fazer preview ou registrar um projeto independente existente sob uma raiz explícita de coordenação. | `<coordination-root>`, `<master-name>`, `<front-id>`, `<front-name>`, `<project-path>`, `<role>`, `<next-action>`, `--dry-run&#124;apply` | Cria ou atualiza somente o manifest canônico de coordenação e suas projeções na raiz; não assume ownership dos detalhes locais do projeto. |
| `hq-sync` | `read` | Validar o manifest canônico e todas as projeções gerenciadas de coordenação. | `<coordination-root>` | Informa consistência e issues sem repair. |
| `digere` | `read` | Classificar uma entrada explícita como local ao projeto, transversal à coordenação ou ephemeral. | `<coordination-root>`, `<front-id>`, `<local&#124;coordination&#124;ephemeral>` | Retorna o roteamento de ownership e não escreve; não sintetiza um digest. |
| `registra` | `write` | Persistir um checkpoint mínimo e confirmado de coordenação para um projeto registrado. | `<coordination-root>`, `<front-id>`, `<state>`, `<next-action>`, `<blocker?>` | Atualiza somente o estado explícito de coordenação e mantém a reflexão inicial pendente quando aplicável. |
| `encerra` | `write` | Persistir uma reflexão explícita completa ou um handoff posterior entre projetos. | `<coordination-root>`, `<front-id>`, `<role>`, `<state>`, `<next-action>`, `<summary>`, `<reflect-when>`, `<blocker?>` | Encerra o bloco de coordenação, remove a reflexão pendente e registra o contrato confirmado de retomada. |

## Exemplos com placeholders

### `bom-dia`

```text
<python> -B scripts/cross_project.py bom-dia --root "<coordination-root>" --front "<front-id>"
```

### `hq-init`

```text
<python> -B scripts/cross_project.py hq-init --root "<coordination-root>" --master-name "<master-name>" --front "<front-id>" --name "<front-name>" --path "<project-path>" --role "<role>" --next "<next-action>" --dry-run
```

### `hq-sync`

```text
<python> -B scripts/cross_project.py hq-sync --root "<coordination-root>"
```

### `digere`

```text
<python> -B scripts/cross_project.py digere --root "<coordination-root>" --front "<front-id>" --scope "<local|coordination|ephemeral>"
```

### `registra`

```text
<python> -B scripts/cross_project.py registra --root "<coordination-root>" --front "<front-id>" --state "<state>" --next "<next-action>" --blocker "<blocker>"
```

### `encerra`

```text
<python> -B scripts/cross_project.py encerra --root "<coordination-root>" --front "<front-id>" --role "<role>" --state "<state>" --next "<next-action>" --summary "<summary>" --reflect-when "<reflect-when>" --blocker "<blocker>"
```

## Workflows

### Primeiro uso

Abrir em modo read-only, fazer preview e registrar um projeto existente e confirmado e então exigir sincronização estrutural limpa.

`bom-dia` → `hq-init` → `hq-sync`

### Uso diário

Abrir um projeto nomeado, rotear a entrada explícita e salvar somente o delta mínimo e confirmado de coordenação.

`bom-dia` → `digere` → `registra` → `hq-sync`

### Closeout e retomada

Encerrar com uma reflexão completa e reabrir o mesmo projeto nomeado a partir da próxima ação registrada.

`encerra` → `hq-sync` → `bom-dia`

### Verify ou recovery

Usar hq-sync como diagnóstico read-only; em caso de inconsistência, parar para recovery manual explícito porque este harness não possui comando de repair.

`hq-sync`

## Receipt de instalação, rollback, update e uninstall

- Receipt: path relativo ao target `.agent-harnesses/runtime/cross-project/0.2.2/.agent-harness-receipt.json`.
- A partir de um bundle `0.2.2` com checksum verificado, antecipe a remoção do package com `<python> -B installer.py uninstall cross-project --target "<target>" --dry-run --json`; após a revisão, aplique-a com `<python> -B installer.py uninstall cross-project --target "<target>" --apply --json`.
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
