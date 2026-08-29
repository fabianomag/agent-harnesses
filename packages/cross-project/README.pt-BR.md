<!-- BEGIN GENERATED:PRODUCT -->
# Multi-Project Harness

[English](README.md) · Versão `0.2.0`

**Melhor opção para:** Projetos independentes com raízes próprias que precisam de handoffs explícitos e coordenação transversal.

**Não serve para:** Um índice de projetos filhos contidos ou um cadastro central novo e estrito com recuperação por histórico transacional.

**O que muda:** Cria um manifest canônico de coordenação e sínteses controladas na raiz, sem assumir a responsabilidade pelos detalhes locais de cada projeto.

Pontos fortes: **Projetos independentes · Handoffs · Sincronização estrutural**. Complexidade: média.

## Instalação

Copie somente este prompt:

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
<!-- END GENERATED:PRODUCT -->

## Primeiro uso

Crie o caminho do projeto independente antes do cadastro. Use como `<python>` o
mesmo executável público do Python 3.10+ escolhido no prompt de instalação. No
diretório do runtime em
`<raiz-coordenadora>/.agent-harnesses/runtime/cross-project/0.2.0`:

```text
<python> -B scripts/cross_project.py bom-dia --root "<raiz-coordenadora>"
<python> -B scripts/cross_project.py hq-init --root "<raiz-coordenadora>" --dry-run --front alpha --name "Alpha" --path projetos/alpha --role "Produz um componente limitado" --next "Validar a primeira etapa"
<python> -B scripts/cross_project.py hq-init --root "<raiz-coordenadora>" --front alpha --name "Alpha" --path projetos/alpha --role "Produz um componente limitado" --next "Validar a primeira etapa"
<python> -B scripts/cross_project.py hq-sync --root "<raiz-coordenadora>"
```

Continue com `digere`, `registra` e `encerra`. A
[referência avançada](docs/REFERENCE.md) preserva os contratos de bloqueio,
rollback, recuperação e evidência. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/cross-project.graph.json).
Execute `<python> -B installer.py verify cross-project --target
"<raiz-coordenadora>" --json` na raiz do pacote ainda extraído; `installer.py`
não é copiado para o runtime.
