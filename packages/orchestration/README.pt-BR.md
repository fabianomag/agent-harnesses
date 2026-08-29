<!-- BEGIN GENERATED:PRODUCT -->
# Control Plane Harness

[English](README.md) · Versão `0.2.0`

**Melhor opção para:** Um control plane novo em que o cadastro central e as mudanças de ciclo de vida justificam transações e recuperação.

**Não serve para:** Adotar uma estrutura de projetos existente, acionar coding agents ou executar o trabalho dos projetos.

**O que muda:** Cria um cadastro central estrito e frentes gerenciadas por mudanças transacionais validadas. Não chama modelos nem aciona coding agents.

Pontos fortes: **Cadastro central com validação estrita · Transações · Recuperação**. Complexidade: alta.

## Instalação

Copie somente este prompt:

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

`doctor` e `install --dry-run` param sem escrever quando o diretório-alvo parece
um Master existente ou contém projetos que o pacote não pode adotar com
segurança.

## Primeiro uso

Use um workspace novo e vazio. Use como `<python>` o mesmo executável público
do Python 3.10+ escolhido no prompt de instalação. Use o runtime em
`<workspace>/.agent-harnesses/runtime/orchestration/0.2.0`:

```text
<python> -B hq.py --root "<workspace>" --json bom-dia
<python> -B hq.py --root "<workspace>" --json init --id alpha --name "Alpha" --path fronts/alpha --dry-run
<python> -B hq.py --root "<workspace>" --json init --id alpha --name "Alpha" --path fronts/alpha --apply
<python> -B hq.py --root "<workspace>" --json hq-sync
```

O harness nunca executa os projetos cadastrados. A
[referência avançada](docs/REFERENCE.md) preserva os contratos de transações,
bloqueio, recuperação e evidência. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/orchestration.graph.json).
Execute `<python> -B installer.py verify orchestration --target "<workspace>"
--json` na raiz do pacote ainda extraído; `installer.py` não é copiado para o
runtime.
