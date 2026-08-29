<!-- BEGIN GENERATED:PRODUCT -->
# Control Plane Harness

[English](README.md) · Versão `0.2.1`

**Melhor opção para:** Um control plane novo em que o cadastro central e as mudanças de ciclo de vida justificam transações e recuperação.

**Não serve para:** Adotar uma estrutura de projetos existente, acionar coding agents ou executar o trabalho dos projetos.

**O que muda:** Cria um cadastro central estrito e frentes gerenciadas por mudanças transacionais validadas. Não chama modelos nem aciona coding agents.

Pontos fortes: **Cadastro central com validação estrita · Transações · Recuperação**. Complexidade: alta.

**Readiness significa:** Um control plane novo contém ao menos uma frente registrada explicitamente, o registry e os arquivos gerados de ciclo de vida estão coerentes, não há recovery pendente e hq-sync informa estado limpo.

**Antes da instalação, confirme:**

- O target explícito é uma nova raiz Master ou de control plane deliberada, não uma estrutura de coordenação existente a ser adotada.
- As frentes iniciais, seus paths relativos pretendidos e seus boundaries já são conhecidos.
- O trabalho realmente exige registry transacional, validated mutations, rollback e recovery, e não apenas handoffs entre projetos.

## Instalação

Copie somente este prompt:

```text
Instale Control Plane Harness (`orchestration`) v0.2.1 a partir de https://github.com/fabianomag/agent-harnesses/releases/download/v0.2.1/orchestration-0.2.1.zip.

Antes de propor a execução, confirme cada fato de readiness do harness selecionado:
- O target explícito é uma nova raiz Master ou de control plane deliberada, não uma estrutura de coordenação existente a ser adotada.
- As frentes iniciais, seus paths relativos pretendidos e seus boundaries já são conhecidos.
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

O runtime instalado inclui `operations.json` e `OPERATOR_GUIDE.pt-BR.md`; após `ready=true`, o coding agent deve ler ambos e ensinar ao usuário, na conversa, o ciclo operacional completo.
<!-- END GENERATED:PRODUCT -->

`doctor` e `install --dry-run` param sem escrever quando o diretório-alvo parece
um Master existente ou contém projetos que o pacote não pode adotar com
segurança.

## Primeiro uso

Use uma nova raiz deliberada de control plane e somente valores confirmados das
frentes. Não adote uma estrutura existente nem crie frentes de exemplo. Use
como `<python>` o mesmo executável público do Python 3.10+ escolhido no prompt
de instalação. Use o runtime em
`<workspace>/.agent-harnesses/runtime/orchestration/0.2.1`:

```text
<python> -B hq.py --root "<workspace>" --json bom-dia
<python> -B hq.py --root "<workspace>" --json init --id "<id-da-frente>" --name "<nome-da-frente>" --path "<path-da-frente>" --dry-run
<python> -B hq.py --root "<workspace>" --json init --id "<id-da-frente>" --name "<nome-da-frente>" --path "<path-da-frente>" --apply
<python> -B hq.py --root "<workspace>" --json hq-sync
```

O state schema `1` permanece compatível. As mutações usam journal e recovery
explícito, mas o harness nunca executa os projetos cadastrados. A
[referência avançada](docs/REFERENCE.md) preserva os contratos de transações,
bloqueio, recuperação e evidência; o
[guia operacional](OPERATOR_GUIDE.pt-BR.md) ensina o ciclo completo. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.1/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.1/graphs/orchestration.graph.json).
Execute `<python> -B installer.py verify orchestration --target "<workspace>"
--json` na raiz do pacote ainda extraído; `installer.py` não é copiado para o
runtime.
