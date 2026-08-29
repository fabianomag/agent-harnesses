<!-- BEGIN GENERATED:PRODUCT -->
# Project Harness

[English](README.md) · Versão `0.2.0`

**Melhor opção para:** Um projeto explícito que precisa de checkpoints, closeout e retomada confiável.

**Não serve para:** Coordenação entre projetos filhos de um workspace ou raízes de projetos independentes.

**O que muda:** Cria um diretório próprio de estado e blocos controlados de contexto dentro do projeto selecionado.

Pontos fortes: **Checkpoints · Closeout e retomada · Configuração rápida**. Complexidade: baixa.

## Instalação

Copie somente este prompt:

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
<!-- END GENERATED:PRODUCT -->

## Primeiro uso

Use como `<python>` o mesmo executável público do Python 3.10+ escolhido no
prompt de instalação. No diretório do runtime instalado,
`<raiz-do-projeto>/.agent-harnesses/runtime/project-harness/0.2.0`:

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

O runtime `0.2.0` lê e verifica o estado `0.1.0` sem reescrever
`harnessVersion`; não há migração implícita. A
[referência avançada](docs/REFERENCE.md) preserva os contratos técnicos de
colisão, rollback, recuperação e evidência. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/project-harness.graph.json).
