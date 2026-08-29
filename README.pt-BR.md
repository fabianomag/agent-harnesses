<!-- BEGIN GENERATED:PRODUCT -->
# Agent Harnesses

[English](README.md)

Quatro harnesses locais para quatro limites de coordenação diferentes. Escolha o menor limite que corresponda ao trabalho real; os pacotes são alternativas paralelas, não degraus de maturidade.

Guia interativo: https://fabianomag.com/pt-br/projetos/agent-harnesses

Requisitos: Python 3.10 ou mais recente, um diretório-alvo existente e explícito e um único arquivo da release `v0.2.0`. Os runtimes usam apenas a biblioteca padrão do Python. O instalador não altera `PATH`, não edita `.gitignore` e não instala uma Skill global.

## O que você precisa coordenar?

| Harness | Escolha quando | Não serve para | Pontos fortes | Complexidade |
| --- | --- | --- | --- | --- |
| [Project Harness](packages/project-harness/README.pt-BR.md) (`project-harness`) | Preciso que um único projeto preserve contexto entre sessões de trabalho. | Coordenação entre projetos filhos de um workspace ou raízes de projetos independentes. | Checkpoints · Closeout e retomada · Configuração rápida | Baixa |
| [Workspace Harness](packages/workspace-coordination/README.pt-BR.md) (`workspace-coordination`) | Tenho projetos filhos autônomos dentro de um único workspace. | Repositórios independentes ou um único projeto sem coordenação de projetos filhos. | Índice dos projetos filhos · Limites de responsabilidade · Visão compartilhada do workspace | Média |
| [Multi-Project Harness](packages/cross-project/README.pt-BR.md) (`cross-project`) | Preciso de handoffs e estado compartilhado entre projetos independentes que já existem. | Um índice de projetos filhos contidos ou um cadastro central novo e estrito com recuperação por histórico transacional. | Projetos independentes · Handoffs · Sincronização estrutural | Média |
| [Control Plane Harness](packages/orchestration/README.pt-BR.md) (`orchestration`) | Estou criando uma estrutura de coordenação nova que precisa de cadastro central estrito, transações e recuperação. | Adotar uma estrutura de projetos existente, acionar coding agents ou executar o trabalho dos projetos. | Cadastro central com validação estrita · Transações · Recuperação | Alta |

Control Plane Harness é um control plane local. Ele não chama modelos, não aciona coding agents e não executa projetos. Por segurança, também se recusa a adotar automaticamente uma estrutura de coordenação existente cuja responsabilidade seja ambígua.

## Copie um único prompt de instalação

Cada bloco abaixo contém somente um harness, uma versão e um ZIP. Copie apenas o bloco escolhido.

### Project Harness

```text
Instale Project Harness (`project-harness`) v0.2.0 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/project-harness-0.2.0.zip.

1. Antes de qualquer escrita, confirme o diretório-alvo explícito e escolha um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`); reutilize somente esse executável e nunca use um runtime privado do Codex.
2. Baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado e valide a soma SHA-256 antes de extrair ou executar qualquer arquivo.
3. Extraia o pacote e, na raiz do pacote extraído, execute:
`<python> -B installer.py doctor project-harness --target "<target>" --json`
4. Em caso de incompatibilidade, pare sem escrever nada e apenas recomende a melhor opção; nunca substitua silenciosamente por outro harness.
5. Execute:
`<python> -B installer.py install project-harness --target "<target>" --dry-run --json`
`<python> -B installer.py install project-harness --target "<target>" --apply --json`
6. Siga `package/README.md` dentro do pacote extraído (ou `package/README.pt-BR.md` em português) para inicializar o diretório-alvo e, na raiz do pacote, execute:
`<python> -B installer.py verify project-harness --target "<target>" --json`
Só reporte sucesso quando esse resultado final contiver `ready=true`.
7. Limpe os arquivos temporários e informe o recibo da instalação e as instruções de `uninstall`/rollback. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.
```

### Workspace Harness

```text
Instale Workspace Harness (`workspace-coordination`) v0.2.0 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/workspace-coordination-0.2.0.zip.

1. Antes de qualquer escrita, confirme o diretório-alvo explícito e escolha um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`); reutilize somente esse executável e nunca use um runtime privado do Codex.
2. Baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado e valide a soma SHA-256 antes de extrair ou executar qualquer arquivo.
3. Extraia o pacote e, na raiz do pacote extraído, execute:
`<python> -B installer.py doctor workspace-coordination --target "<target>" --json`
4. Em caso de incompatibilidade, pare sem escrever nada e apenas recomende a melhor opção; nunca substitua silenciosamente por outro harness.
5. Execute:
`<python> -B installer.py install workspace-coordination --target "<target>" --dry-run --json`
`<python> -B installer.py install workspace-coordination --target "<target>" --apply --json`
6. Siga `package/README.md` dentro do pacote extraído (ou `package/README.pt-BR.md` em português) para inicializar o diretório-alvo e, na raiz do pacote, execute:
`<python> -B installer.py verify workspace-coordination --target "<target>" --json`
Só reporte sucesso quando esse resultado final contiver `ready=true`.
7. Limpe os arquivos temporários e informe o recibo da instalação e as instruções de `uninstall`/rollback. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.
```

### Multi-Project Harness

```text
Instale Multi-Project Harness (`cross-project`) v0.2.0 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/cross-project-0.2.0.zip.

1. Antes de qualquer escrita, confirme o diretório-alvo explícito e escolha um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`); reutilize somente esse executável e nunca use um runtime privado do Codex.
2. Baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado e valide a soma SHA-256 antes de extrair ou executar qualquer arquivo.
3. Extraia o pacote e, na raiz do pacote extraído, execute:
`<python> -B installer.py doctor cross-project --target "<target>" --json`
4. Em caso de incompatibilidade, pare sem escrever nada e apenas recomende a melhor opção; nunca substitua silenciosamente por outro harness.
5. Execute:
`<python> -B installer.py install cross-project --target "<target>" --dry-run --json`
`<python> -B installer.py install cross-project --target "<target>" --apply --json`
6. Siga `package/README.md` dentro do pacote extraído (ou `package/README.pt-BR.md` em português) para inicializar o diretório-alvo e, na raiz do pacote, execute:
`<python> -B installer.py verify cross-project --target "<target>" --json`
Só reporte sucesso quando esse resultado final contiver `ready=true`.
7. Limpe os arquivos temporários e informe o recibo da instalação e as instruções de `uninstall`/rollback. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.
```

### Control Plane Harness

```text
Instale Control Plane Harness (`orchestration`) v0.2.0 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.0/orchestration-0.2.0.zip.

1. Antes de qualquer escrita, confirme o diretório-alvo explícito e escolha um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`); reutilize somente esse executável e nunca use um runtime privado do Codex.
2. Baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado e valide a soma SHA-256 antes de extrair ou executar qualquer arquivo.
3. Extraia o pacote e, na raiz do pacote extraído, execute:
`<python> -B installer.py doctor orchestration --target "<target>" --json`
4. Em caso de incompatibilidade, pare sem escrever nada e apenas recomende a melhor opção; nunca substitua silenciosamente por outro harness.
5. Execute:
`<python> -B installer.py install orchestration --target "<target>" --dry-run --json`
`<python> -B installer.py install orchestration --target "<target>" --apply --json`
6. Siga `package/README.md` dentro do pacote extraído (ou `package/README.pt-BR.md` em português) para inicializar o diretório-alvo e, na raiz do pacote, execute:
`<python> -B installer.py verify orchestration --target "<target>" --json`
Só reporte sucesso quando esse resultado final contiver `ready=true`.
7. Limpe os arquivos temporários e informe o recibo da instalação e as instruções de `uninstall`/rollback. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.
```
<!-- END GENERATED:PRODUCT -->

## Instalação manual

Baixe um ZIP e o arquivo `<arquivo>.sha256` correspondente. Valide essa soma
individual antes de extrair. Não existe um arquivo `SHA256SUMS` coletivo.

Depois da extração, execute na raiz do pacote. Mantenha essa raiz disponível
até o `verify` final; `installer.py` não é copiado para o runtime. Escolha um
único executável do Python 3.10+ disponível para o usuário ou para o sistema como
`<python>` (por exemplo, `python3`, `python` ou `py -3`) e reutilize-o em todos os
comandos:

```text
<python> -B installer.py doctor <seletor> --target "<diretório-alvo>" --json
<python> -B installer.py install <seletor> --target "<diretório-alvo>" --dry-run --json
<python> -B installer.py install <seletor> --target "<diretório-alvo>" --apply --json
```

Siga `package/README.md` no pacote extraído (ou
`package/README.pt-BR.md` em português) e finalize na raiz do pacote ainda
extraído:

```text
<python> -B installer.py verify <seletor> --target "<diretório-alvo>" --json
```

O estado é explícito: `downloaded → installed → initialized → verified →
ready`. Instalar os arquivos do pacote não significa sucesso operacional;
somente `"ready": true` confirma que o diretório-alvo inicializado está pronto.

O runtime selecionado fica em
`<diretório-alvo>/.agent-harnesses/runtime/<id>/0.2.0`.

Para remover somente os arquivos inalterados registrados no recibo do runtime,
sem apagar o estado inicializado do projeto ou workspace:

```text
<python> -B installer.py uninstall <seletor> --target "<diretório-alvo>" --dry-run --json
<python> -B installer.py uninstall <seletor> --target "<diretório-alvo>" --apply --json
```

## Evidência técnica e detalhes avançados

As cinco dimensões técnicas (`Context`, `Skill`, `Harness`, `Loop` e
`Guardrails`) registram evidência; não são selos de comparação nem uma
classificação dos pacotes.
Os detalhes, diagramas e contratos de segurança ficam no
[catálogo técnico](catalog/harnesses.json) e na
[referência avançada](docs/REFERENCE.md).

A release `v0.2.0` contém quatro ZIPs determinísticos, cada um com somente um
pacote, além de um arquivo de soma por artefato, o instalador independente, o
manifest da release, o registro fixado do site e o histórico de mudanças. As
versões `0.1.x` permanecem imutáveis e estão marcadas como substituídas.

Copyright Fabiano Magalhães. [Licença MIT](LICENSE).
