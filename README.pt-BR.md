<!-- BEGIN GENERATED:PRODUCT -->
# Agent Harnesses

[English](README.md)

Quatro harnesses locais para quatro limites de coordenação diferentes. Escolha o menor limite que corresponda ao trabalho real; os pacotes são alternativas paralelas, não degraus de maturidade.

Guia interativo: https://fabianomag.com/pt-br/projetos/agent-harnesses

Requisitos: Python 3.10 ou mais recente, um diretório-alvo existente e explícito e um único ZIP da release `v0.2.3` com seu checksum sidecar correspondente. Cada ZIP instala o runtime completo baseado apenas na biblioteca padrão do Python, o inventário de comandos e o guia operacional agent-agnostic de um harness. O instalador não altera `PATH`, não edita `.gitignore` e não exige uma Skill global.

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
Instale Project Harness (`project-harness`) v0.2.3 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.3/project-harness-0.2.3.zip.

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

### Workspace Harness

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

### Multi-Project Harness

```text
Instale Multi-Project Harness (`cross-project`) v0.2.3 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.3/cross-project-0.2.3.zip.

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

### Control Plane Harness

```text
Instale Control Plane Harness (`orchestration`) v0.2.3 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.3/orchestration-0.2.3.zip.

Antes de propor a execução, confirme cada fato de readiness do harness selecionado:
- O target explícito é uma nova raiz Master ou de control plane deliberada, não uma estrutura de coordenação existente a ser adotada.
- As frentes iniciais e seus paths relativos à raiz estão conhecidos, e o usuário consegue declarar o responsibility boundary semântico de cada frente. O harness não inferirá esse boundary.
- O trabalho realmente exige registry transacional, validated mutations, rollback e recovery, e não apenas handoffs entre projetos.
Se algum fato for desconhecido ou falso, pare antes de downloads ou writes no target, explique o que precisa ser organizado primeiro e ofereça os contatos de suporte abaixo.

Se o modo atual não puder executar, peça a mudança para um modo capaz de executar somente depois de apresentar o plano e receber a confirmação.

Use o Plan mode nativo e structured questions do agente quando disponíveis; caso contrário, apresente o mesmo plano e as mesmas perguntas na conversa. Trabalhe em duas etapas explícitas: primeiro o plano e depois a execução somente após confirmação. Antes de qualquer escrita, inclusive download ou extração temporária, inspecione apenas o diretório-alvo explícito e o ferramental público disponível em modo read-only. Apresente quatro checklists separados: (1) fit e target, (2) segurança e plano de writes, (3) inicialização e readiness e (4) tutorial e handoff. Informe o harness selecionado, o target, um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`), as escritas previstas, os dados necessários para inicialização, a verificação, o rollback e o tutorial; peça ao usuário que confirme esse plano. Nunca use um runtime privado do Codex. Não organize, renomeie, resuma, migre nem infira dados do projeto do usuário. Pergunte por qualquer valor ausente em vez de inventá-lo. Após a confirmação, baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado, valide a soma SHA-256 antes de extrair ou executar qualquer arquivo e extraia o pacote. Na raiz do pacote extraído, execute:
`<python> -B installer.py doctor orchestration --target "<target>" --json`
Se doctor ou qualquer verificação de readiness anterior ao apply falhar, pare com zero writes no target, limpe somente os arquivos temporários isolados e recomende a opção mais adequada quando aplicável; nunca substitua silenciosamente por outro harness. Depois execute:
`<python> -B installer.py install orchestration --target "<target>" --dry-run --json`
Compare o resultado com o plano confirmado e pergunte novamente se o conjunto de writes ou as premissas mudaram de forma relevante. Caso contrário, execute:
`<python> -B installer.py install orchestration --target "<target>" --apply --json`
Siga `package/README.pt-BR.md` para inicializar o target, sempre antecipando cada mutação do runtime e usando somente valores confirmados pelo usuário. Se qualquer etapa falhar depois do primeiro apply ou a readiness final for falsa, interrompa a execução normal e siga o procedimento documentado de rollback ou recovery do package exato, faça preview antes do apply, preserve arquivos não relacionados, verifique a restauração em direção ao estado exato anterior à instalação e informe qualquer mudança residual inevitável em vez de declarar sucesso. Na raiz do pacote, execute:
`<python> -B installer.py verify orchestration --target "<target>" --json`
Só declare sucesso quando o resultado final contiver `ready=true`. Após readiness, leia `operations.json` e `OPERATOR_GUIDE.pt-BR.md` no runtime instalado e apresente ao usuário, na conversa, um tutorial conciso que cubra cada comando, os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery, exemplos seguros com valores confirmados ou placeholders e orientações de update/uninstall. Não crie arquivos de tutorial. Limpe os arquivos temporários e informe receipt, evidência de readiness, estado do rollback e localização do runtime. Ofereça suporte pelo LinkedIn em https://www.linkedin.com/in/fabianomag/ ou pelo email fm@fabianomag.com. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global.

Entregue o tutorial no idioma do usuário e na conversa sem criar documentação no projeto. Use somente valores fornecidos explicitamente pelo usuário; caso contrário, mantenha placeholders. Não instale nem oriente a instalação de qualquer adapter global de agente.
```

## Compatibilidade com agentes

Codex é a experiência principal de instalação guiada. Claude Code Desktop é o alvo agent-agnostic de smoke; nenhum dos dois fluxos exige uma Skill global.

## Suporte

LinkedIn: https://www.linkedin.com/in/fabianomag/ · Email: fm@fabianomag.com
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
`tutorial delivered` é um resultado conversacional separado: após readiness, o
coding agent lê o contrato operacional instalado e ensina o usuário; o
instalador não finge medir se essa explicação aconteceu.

O runtime selecionado fica em
`<diretório-alvo>/.agent-harnesses/runtime/<id>/0.2.3`.

Para remover somente o bloco de onboarding gerenciado exato e os arquivos
inalterados registrados no receipt do runtime, sem apagar o estado inicializado
do projeto ou workspace:

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
Integrações nativas opcionais de plataformas ficam em
[`adapters/`](adapters/) e nunca fazem parte dos quatro ZIPs centrais nem da
instalação padrão.

A release `v0.2.3` contém quatro ZIPs determinísticos, cada um com somente um
pacote, além de um arquivo de soma por artefato, o instalador independente, o
manifest da release, o registro fixado do site e o histórico de mudanças. As
versões `0.1.x` e a release imutável `v0.2.0` permanecem disponíveis e estão
marcadas como substituídas.

Copyright Fabiano Magalhães. [Licença MIT](LICENSE).
