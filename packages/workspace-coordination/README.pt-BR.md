<!-- BEGIN GENERATED:PRODUCT -->
# Workspace Harness

[English](README.md) · Versão `0.2.0`

**Melhor opção para:** Projetos filhos no mesmo workspace que precisam de um pequeno índice compartilhado.

**Não serve para:** Repositórios independentes ou um único projeto sem coordenação de projetos filhos.

**O que muda:** Cria um diretório de controle do workspace e registros de coordenação próprios de cada projeto filho.

Pontos fortes: **Índice dos projetos filhos · Limites de responsabilidade · Visão compartilhada do workspace**. Complexidade: média.

## Instalação

Copie somente este prompt:

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
<!-- END GENERATED:PRODUCT -->

## Primeiro uso

Crie as pastas dos projetos filhos e um arquivo que declare o responsável em
cada uma. Use como `<python>` o mesmo executável público do Python 3.10+
escolhido no prompt de instalação. Use o runtime em
`<raiz-coordenadora>/.agent-harnesses/runtime/workspace-coordination/0.2.0`:

```text
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" init --dry-run
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" init --apply
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" add --id alpha --path projeto-alpha --owner AGENTS.md --dry-run
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" add --id alpha --path projeto-alpha --owner AGENTS.md --apply
<python> -B workspace_coordination.py --root "<raiz-coordenadora>" verify
```

O coordenador não descobre projetos filhos nem executa o trabalho deles. A
[referência avançada](docs/REFERENCE.md) preserva os contratos de single
writer, recuperação e evidência. Consulte também o
[catálogo imutável](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/catalog/harnesses.json)
e o [diagrama](https://github.com/fabianomag/agent-harnesses/blob/v0.2.0/graphs/workspace-coordination.graph.json).
Execute `<python> -B installer.py verify workspace-coordination --target
"<raiz-coordenadora>" --json` na raiz do pacote ainda extraído;
`installer.py` não é copiado para o runtime.
