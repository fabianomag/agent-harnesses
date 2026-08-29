#!/usr/bin/env python3
"""Dependency-free, target-local installer for Agent Harnesses."""

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath


PRODUCT = json.loads(r'''{
  "compatibility": {
    "primary": {
      "agent": "Codex",
      "description": {
        "en": "Primary guided-install and operator experience; release acceptance requires the complete copied-prompt flow.",
        "ptBr": "Experiência principal de instalação guiada e operação; a aceitação da release exige o fluxo completo a partir do prompt copiado."
      },
      "level": "primary"
    },
    "smoke": {
      "agent": "Claude Code Desktop",
      "description": {
        "en": "Agent-agnostic compatibility target; release acceptance requires a copied-prompt smoke flow without a formal Skill dependency. This bounded smoke does not claim complete agent equivalence.",
        "ptBr": "Alvo de compatibilidade agent-agnostic; a aceitação da release exige um smoke flow a partir do prompt copiado, sem depender de uma Skill formal. Esse smoke limitado não afirma equivalência completa entre agentes."
      },
      "level": "smoke"
    }
  },
  "executionModeInstruction": {
    "en": "If the current mode cannot execute, request a switch to an execution-capable mode only after presenting the plan and receiving confirmation.",
    "ptBr": "Se o modo atual não puder executar, peça a mudança para um modo capaz de executar somente depois de apresentar o plano e receber a confirmação."
  },
  "packages": [
    {
      "aliases": [
        "project",
        "single-project",
        "project-harness"
      ],
      "asset": "project-harness-0.2.1.zip",
      "complexity": {
        "en": "Low",
        "level": "low",
        "ptBr": "Baixa"
      },
      "content": {
        "en": {
          "bestFor": "One explicit project that needs checkpoints, closeout, and reliable resumption.",
          "notFor": "Coordination across workspace children or independent project roots.",
          "scenario": "I need one project to remember context between work sessions.",
          "summary": "A small project-local lifecycle for durable context and the next action.",
          "whatItChanges": "Creates a bounded project state directory and managed context blocks inside the selected project."
        },
        "ptBr": {
          "bestFor": "Um projeto explícito que precisa de checkpoints, closeout e retomada confiável.",
          "notFor": "Coordenação entre projetos filhos de um workspace ou raízes de projetos independentes.",
          "scenario": "Preciso que um único projeto preserve contexto entre sessões de trabalho.",
          "summary": "Um fluxo local ao projeto para preservar contexto e a próxima ação.",
          "whatItChanges": "Cria um diretório próprio de estado e blocos controlados de contexto dentro do projeto selecionado."
        }
      },
      "displayName": "Project Harness",
      "id": "project-harness",
      "operator": {
        "entrypoint": "project_harness.py",
        "installationReadiness": {
          "en": [
            "The explicit target is the root of one real project.",
            "That project's write boundary is understood and does not include sibling projects.",
            "The requested scope is project-local operational memory, not coordination across multiple projects."
          ],
          "ptBr": [
            "O target explícito é a raiz de um único projeto real.",
            "O write boundary desse projeto está compreendido e não inclui projetos irmãos.",
            "O escopo solicitado é memória operacional local ao projeto, não coordenação entre vários projetos."
          ]
        },
        "memory": {
          "canonical": [
            ".project-harness/state.json"
          ],
          "description": {
            "en": "Operational memory remains inside the selected project: one canonical state document plus deterministic Markdown projections.",
            "ptBr": "A memória operacional permanece dentro do projeto selecionado: um documento de estado canônico e projeções Markdown determinísticas."
          },
          "projections": [
            "docs/decisions.md",
            "docs/next-actions.md",
            "docs/session-log.md"
          ]
        },
        "operations": [
          {
            "command": "init",
            "effects": {
              "en": "Dry-run writes nothing; apply creates or reconciles only the declared project-local managed paths.",
              "ptBr": "O dry-run não escreve; o apply cria ou reconcilia apenas os paths gerenciados declarados e locais ao projeto."
            },
            "example": "<python> -B project_harness.py init --root \"<project-root>\" --dry-run",
            "inputs": [
              "<project-root>",
              "--dry-run|apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Preview or initialize the bounded project state and managed context projections.",
              "ptBr": "Fazer preview ou inicializar o estado delimitado do projeto e as projeções gerenciadas de contexto."
            }
          },
          {
            "command": "verify",
            "effects": {
              "en": "Reads the bounded project state and reports drift without repair.",
              "ptBr": "Lê o estado delimitado do projeto e informa drift sem fazer repair."
            },
            "example": "<python> -B project_harness.py verify --root \"<project-root>\" --json",
            "inputs": [
              "<project-root>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Check canonical state, ownership markers, and every managed projection.",
              "ptBr": "Verificar o estado canônico, os markers de ownership e cada projeção gerenciada."
            }
          },
          {
            "command": "status",
            "effects": {
              "en": "Reads canonical state without changing project files.",
              "ptBr": "Lê o estado canônico sem alterar arquivos do projeto."
            },
            "example": "<python> -B project_harness.py status --root \"<project-root>\" --json",
            "inputs": [
              "<project-root>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Show the current durable state and next action.",
              "ptBr": "Mostrar o estado durável atual e a próxima ação."
            }
          },
          {
            "command": "open",
            "effects": {
              "en": "Returns the resumption context and next step without writing.",
              "ptBr": "Retorna o contexto de retomada e a próxima ação sem writes."
            },
            "example": "<python> -B project_harness.py open --root \"<project-root>\" --json",
            "inputs": [
              "<project-root>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Open one work block from durable project context.",
              "ptBr": "Abrir um bloco de trabalho a partir do contexto durável do projeto."
            }
          },
          {
            "command": "digest",
            "effects": {
              "en": "Returns deterministic recorded context and does not synthesize or persist new content.",
              "ptBr": "Retorna contexto registrado de forma determinística e não sintetiza nem persiste conteúdo novo."
            },
            "example": "<python> -B project_harness.py digest --root \"<project-root>\" --json",
            "inputs": [
              "<project-root>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Collate the bounded durable records for review.",
              "ptBr": "Reunir os registros duráveis delimitados para revisão."
            }
          },
          {
            "command": "checkpoint",
            "effects": {
              "en": "Appends confirmed content to canonical state and refreshes its managed projections.",
              "ptBr": "Acrescenta conteúdo confirmado ao estado canônico e atualiza suas projeções gerenciadas."
            },
            "example": "<python> -B project_harness.py checkpoint --root \"<project-root>\" --session \"<session-id>\" --summary \"<summary>\" --decision \"<decision>\" --task \"<task>\" --next-step \"<next-step>\" --json",
            "inputs": [
              "<project-root>",
              "<session-id>",
              "<summary>",
              "<decision>",
              "<task>",
              "<next-step>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Persist an explicit intermediate work record and one next step.",
              "ptBr": "Persistir um registro intermediário explícito do trabalho e uma próxima ação."
            }
          },
          {
            "command": "close",
            "effects": {
              "en": "Persists the confirmed closeout and next step in canonical state and projections.",
              "ptBr": "Persiste o closeout confirmado e a próxima ação no estado canônico e nas projeções."
            },
            "example": "<python> -B project_harness.py close --root \"<project-root>\" --session \"<session-id>\" --summary \"<summary>\" --decision \"<decision>\" --task \"<task>\" --next-step \"<next-step>\" --json",
            "inputs": [
              "<project-root>",
              "<session-id>",
              "<summary>",
              "<decision>",
              "<task>",
              "<next-step>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Close the current work block with an explicit durable resumption point.",
              "ptBr": "Encerrar o bloco de trabalho atual com um ponto de retomada durável e explícito."
            }
          }
        ],
        "readiness": {
          "en": "The exact runtime inventory is installed, project state is initialized, managed projections verify, and the project can be opened from its persisted next step.",
          "ptBr": "O inventário exato do runtime está instalado, o estado do projeto foi inicializado, as projeções gerenciadas passam em verify e o projeto pode ser aberto a partir da próxima ação persistida."
        },
        "workflows": {
          "closeResume": {
            "purpose": {
              "en": "Close with an explicit next step and later reopen from that persisted point.",
              "ptBr": "Fazer closeout com uma próxima ação explícita e depois retomar a partir desse ponto persistido."
            },
            "steps": [
              "close",
              "open"
            ]
          },
          "daily": {
            "purpose": {
              "en": "Open durable context, review it, and save only a confirmed checkpoint when needed.",
              "ptBr": "Abrir o contexto durável, revisá-lo e salvar somente um checkpoint confirmado quando necessário."
            },
            "steps": [
              "open",
              "digest",
              "checkpoint"
            ]
          },
          "firstUse": {
            "purpose": {
              "en": "Preview initialization, apply it after confirmation, verify, and open the first work block.",
              "ptBr": "Fazer preview da inicialização, aplicar após confirmação, executar verify e abrir o primeiro bloco de trabalho."
            },
            "steps": [
              "init",
              "verify",
              "open"
            ]
          },
          "verifyRecover": {
            "purpose": {
              "en": "Verify first; when canonical state is valid but projections drift, preview and rerun init before verifying again.",
              "ptBr": "Executar verify primeiro; quando o estado canônico estiver válido mas as projeções tiverem drift, fazer preview e repetir init antes de verificar novamente."
            },
            "steps": [
              "verify",
              "init",
              "verify"
            ]
          }
        }
      },
      "strengths": {
        "en": [
          "Checkpoints",
          "Close and resume",
          "Fast setup"
        ],
        "ptBr": [
          "Checkpoints",
          "Closeout e retomada",
          "Configuração rápida"
        ]
      }
    },
    {
      "aliases": [
        "workspace",
        "workspace-harness",
        "workspace-coordination"
      ],
      "asset": "workspace-coordination-0.2.1.zip",
      "complexity": {
        "en": "Medium",
        "level": "medium",
        "ptBr": "Média"
      },
      "content": {
        "en": {
          "bestFor": "Contained child projects that share one workspace boundary and a small shared index.",
          "notFor": "Independent repositories or a single project with no child coordination.",
          "scenario": "I have autonomous child folders inside one containing workspace.",
          "summary": "A coordinator index that preserves child-local ownership.",
          "whatItChanges": "Creates a workspace control directory and child-local coordination records."
        },
        "ptBr": {
          "bestFor": "Projetos filhos no mesmo workspace que precisam de um pequeno índice compartilhado.",
          "notFor": "Repositórios independentes ou um único projeto sem coordenação de projetos filhos.",
          "scenario": "Tenho projetos filhos autônomos dentro de um único workspace.",
          "summary": "Um índice de coordenação que preserva a responsabilidade de cada projeto filho.",
          "whatItChanges": "Cria um diretório de controle do workspace e registros de coordenação próprios de cada projeto filho."
        }
      },
      "displayName": "Workspace Harness",
      "id": "workspace-coordination",
      "operator": {
        "entrypoint": "workspace_coordination.py",
        "installationReadiness": {
          "en": [
            "The explicit target is the container workspace, not one of its child projects.",
            "The existing contained child projects to register are already known.",
            "Each selected child has an explicit local owner file and its detailed state will remain locally owned."
          ],
          "ptBr": [
            "O target explícito é o workspace contêiner, não um de seus projetos filhos.",
            "Os projetos filhos existentes e contidos que serão registrados já são conhecidos.",
            "Cada projeto filho selecionado tem um owner file local explícito e seu estado detalhado continuará sob ownership local."
          ]
        },
        "memory": {
          "canonical": [
            ".workspace-coordination/workspace.json",
            "<child-path>/.workspace-coordination/local-state.json"
          ],
          "description": {
            "en": "The workspace index and shared deltas remain at the coordinator root; detailed continuity remains in each explicitly registered child.",
            "ptBr": "O índice do workspace e os deltas compartilhados permanecem na raiz coordenadora; a continuidade detalhada permanece em cada projeto filho registrado explicitamente."
          },
          "projections": [
            ".workspace-coordination/INDEX.md",
            ".workspace-coordination/BOUNDARIES.md",
            ".workspace-coordination/SHARED_DELTAS.md"
          ]
        },
        "operations": [
          {
            "command": "init",
            "effects": {
              "en": "Dry-run writes nothing; apply creates only the coordinator's canonical and generated files.",
              "ptBr": "O dry-run não escreve; o apply cria somente os arquivos canônicos e gerados do coordenador."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" init --dry-run",
            "inputs": [
              "<coordinator-root>",
              "--dry-run|--apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Preview or initialize the workspace coordinator boundary.",
              "ptBr": "Fazer preview ou inicializar o limite do coordenador do workspace."
            }
          },
          {
            "command": "add",
            "effects": {
              "en": "Updates only the coordinator index and the selected child's local coordination record.",
              "ptBr": "Atualiza somente o índice do coordenador e o registro local de coordenação do projeto filho selecionado."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" add --id \"<child-id>\" --path \"<child-path>\" --owner \"<owner-file>\" --dry-run",
            "inputs": [
              "<coordinator-root>",
              "<child-id>",
              "<child-path>",
              "<owner-file>",
              "--dry-run|--apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Register one existing contained child with its explicit owner file.",
              "ptBr": "Registrar um projeto filho contido e existente com seu owner file explícito."
            }
          },
          {
            "command": "remove",
            "effects": {
              "en": "Removes only coordinator-owned registration state and preserves the child.",
              "ptBr": "Remove somente o estado de registro pertencente ao coordenador e preserva o projeto filho."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" remove --id \"<child-id>\" --dry-run",
            "inputs": [
              "<coordinator-root>",
              "<child-id>",
              "--dry-run|--apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Remove one child registration without deleting or editing the child project.",
              "ptBr": "Remover um registro de projeto filho sem excluir nem editar o projeto filho."
            }
          },
          {
            "command": "open",
            "effects": {
              "en": "Reads coordinator and selected child records without writing.",
              "ptBr": "Lê registros do coordenador e do projeto filho selecionado sem writes."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" --json open --child \"<child-id>\"",
            "inputs": [
              "<coordinator-root>",
              "<child-id?>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Open the coordinator or one registered child's bounded resumption context.",
              "ptBr": "Abrir o contexto delimitado de retomada do coordenador ou de um projeto filho registrado."
            }
          },
          {
            "command": "digest",
            "effects": {
              "en": "Returns explicit child-local context without discovering or copying other project data.",
              "ptBr": "Retorna o contexto local explícito do projeto filho sem descobrir nem copiar outros dados de projeto."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" --json digest --child \"<child-id>\"",
            "inputs": [
              "<coordinator-root>",
              "<child-id>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Read the bounded owner and continuity context for one child.",
              "ptBr": "Ler o contexto delimitado de ownership e continuidade de um projeto filho."
            }
          },
          {
            "command": "record",
            "effects": {
              "en": "Writes the confirmed record only to the selected child's harness-owned local state.",
              "ptBr": "Escreve o registro confirmado somente no estado local pertencente ao harness do projeto filho selecionado."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" record --child \"<child-id>\" --key \"<record-key>\" --kind update --summary \"<summary>\" --next \"<next-action>\" --dry-run",
            "inputs": [
              "<coordinator-root>",
              "<child-id>",
              "<record-key>",
              "<record-kind>",
              "<summary>",
              "<next-action>",
              "--dry-run|--apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Append one explicit child-local continuity record.",
              "ptBr": "Acrescentar um registro explícito de continuidade local do projeto filho."
            }
          },
          {
            "command": "reflect",
            "effects": {
              "en": "Adds one bounded shared delta without absorbing the child's detailed state.",
              "ptBr": "Adiciona um delta compartilhado delimitado sem absorver o estado detalhado do projeto filho."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" reflect --child \"<child-id>\" --key \"<reflection-key>\" --summary \"<summary>\" --dry-run",
            "inputs": [
              "<coordinator-root>",
              "<child-id>",
              "<reflection-key>",
              "<summary>",
              "--dry-run|--apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Reflect one confirmed concise shared delta into the coordinator.",
              "ptBr": "Refletir um delta compartilhado, conciso e confirmado no coordenador."
            }
          },
          {
            "command": "verify",
            "effects": {
              "en": "Reports structural issues without repair.",
              "ptBr": "Informa issues estruturais sem repair."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" --json verify",
            "inputs": [
              "<coordinator-root>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Validate coordinator state, registrations, child ownership, and generated views.",
              "ptBr": "Validar o estado do coordenador, os registros, o ownership dos projetos filhos e as views geradas."
            }
          },
          {
            "command": "recover",
            "effects": {
              "en": "Repairs derivable coordinator-managed state and never reconstructs missing child-owned facts.",
              "ptBr": "Faz repair do estado derivável e gerenciado pelo coordenador sem reconstruir fatos ausentes pertencentes aos projetos filhos."
            },
            "example": "<python> -B workspace_coordination.py --root \"<coordinator-root>\" recover --dry-run",
            "inputs": [
              "<coordinator-root>",
              "--dry-run|--apply"
            ],
            "kind": "repair",
            "purpose": {
              "en": "Preview or regenerate only recoverable managed workspace state.",
              "ptBr": "Fazer preview ou regenerar somente o estado gerenciado recuperável do workspace."
            }
          }
        ],
        "readiness": {
          "en": "The coordinator is initialized, every registered child and owner path is explicit and valid, and canonical plus generated workspace state verifies cleanly.",
          "ptBr": "O coordenador está inicializado, todos os projetos filhos e owner paths registrados são explícitos e válidos e o estado canônico e gerado do workspace passa em verify sem issues."
        },
        "workflows": {
          "closeResume": {
            "purpose": {
              "en": "Record an explicit close record with a next action, then reopen that child from local state.",
              "ptBr": "Registrar um closeout explícito com próxima ação e depois reabrir o projeto filho a partir do estado local."
            },
            "steps": [
              "record",
              "open"
            ]
          },
          "daily": {
            "purpose": {
              "en": "Open one child, digest only its bounded context, record local continuity, and reflect only a confirmed shared delta.",
              "ptBr": "Abrir um projeto filho, digerir somente seu contexto delimitado, registrar a continuidade local e refletir apenas um delta compartilhado confirmado."
            },
            "steps": [
              "open",
              "digest",
              "record",
              "reflect"
            ]
          },
          "firstUse": {
            "purpose": {
              "en": "Preview and initialize the coordinator, register one confirmed existing child, verify, and open it.",
              "ptBr": "Fazer preview e inicializar o coordenador, registrar um projeto filho existente e confirmado, executar verify e abri-lo."
            },
            "steps": [
              "init",
              "add",
              "verify",
              "open"
            ]
          },
          "verifyRecover": {
            "purpose": {
              "en": "Verify first; preview recover only for derivable managed drift, apply after confirmation, and verify again.",
              "ptBr": "Executar verify primeiro; fazer preview de recover somente para drift gerenciado e derivável, aplicar após confirmação e executar verify novamente."
            },
            "steps": [
              "verify",
              "recover",
              "verify"
            ]
          }
        }
      },
      "strengths": {
        "en": [
          "Child index",
          "Ownership boundaries",
          "Shared workspace view"
        ],
        "ptBr": [
          "Índice dos projetos filhos",
          "Limites de responsabilidade",
          "Visão compartilhada do workspace"
        ]
      }
    },
    {
      "aliases": [
        "multi-project",
        "cross-project",
        "cross"
      ],
      "asset": "cross-project-0.2.1.zip",
      "complexity": {
        "en": "Medium",
        "level": "medium",
        "ptBr": "Média"
      },
      "content": {
        "en": {
          "bestFor": "Existing independent project roots that need explicit handoffs and transversal coordination.",
          "notFor": "A contained child index or a new strict registry with journaled recovery.",
          "scenario": "I need handoffs and shared state across existing independent projects.",
          "summary": "A canonical cross-project manifest with bounded reflection and structural sync.",
          "whatItChanges": "Creates a canonical coordination manifest and managed root projections without taking ownership of project-local details."
        },
        "ptBr": {
          "bestFor": "Projetos independentes com raízes próprias que precisam de handoffs explícitos e coordenação transversal.",
          "notFor": "Um índice de projetos filhos contidos ou um cadastro central novo e estrito com recuperação por histórico transacional.",
          "scenario": "Preciso de handoffs e estado compartilhado entre projetos independentes que já existem.",
          "summary": "Um manifest canônico entre projetos, com sínteses controladas e sincronização estrutural.",
          "whatItChanges": "Cria um manifest canônico de coordenação e sínteses controladas na raiz, sem assumir a responsabilidade pelos detalhes locais de cada projeto."
        }
      },
      "displayName": "Multi-Project Harness",
      "id": "cross-project",
      "operator": {
        "entrypoint": "scripts/cross_project.py",
        "installationReadiness": {
          "en": [
            "The coordination root and the independent existing project roots are explicit.",
            "The projects have known boundaries and a real need for handoffs or structural sync across roots.",
            "The user can supply each selected project's role and next action without repository discovery or invented state."
          ],
          "ptBr": [
            "A coordination root e as raízes independentes dos projetos existentes estão explícitas.",
            "Os projetos têm boundaries conhecidos e uma necessidade real de handoffs ou structural sync entre raízes.",
            "O usuário pode fornecer o papel e a próxima ação de cada projeto selecionado sem descoberta de repositórios nem estado inventado."
          ]
        },
        "memory": {
          "canonical": [
            "harness.config.json"
          ],
          "description": {
            "en": "The coordination root owns the canonical cross-project manifest and concise projections; each independent project keeps its detailed local memory.",
            "ptBr": "A coordination root mantém o manifest canônico entre projetos e projeções concisas; cada projeto independente preserva sua memória local detalhada."
          },
          "projections": [
            "AGENTS.md",
            "FRONTS.md",
            "NEXT.md"
          ]
        },
        "operations": [
          {
            "command": "bom-dia",
            "effects": {
              "en": "Reads bounded coordination state and reports the current next action without writing.",
              "ptBr": "Lê o estado delimitado de coordenação e informa a próxima ação atual sem writes."
            },
            "example": "<python> -B scripts/cross_project.py bom-dia --root \"<coordination-root>\" --front \"<front-id>\"",
            "inputs": [
              "<coordination-root>",
              "<front-id?>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Open the cross-project coordination state or one named project's resumption point.",
              "ptBr": "Abrir o estado de coordenação entre projetos ou o ponto de retomada de um projeto nomeado."
            }
          },
          {
            "command": "hq-init",
            "effects": {
              "en": "Creates or updates only the canonical coordination manifest and its root projections; it does not take ownership of project-local details.",
              "ptBr": "Cria ou atualiza somente o manifest canônico de coordenação e suas projeções na raiz; não assume ownership dos detalhes locais do projeto."
            },
            "example": "<python> -B scripts/cross_project.py hq-init --root \"<coordination-root>\" --master-name \"<master-name>\" --front \"<front-id>\" --name \"<front-name>\" --path \"<project-path>\" --role \"<role>\" --next \"<next-action>\" --dry-run",
            "inputs": [
              "<coordination-root>",
              "<master-name>",
              "<front-id>",
              "<front-name>",
              "<project-path>",
              "<role>",
              "<next-action>",
              "--dry-run|apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Preview or register one existing independent project under an explicit coordination root.",
              "ptBr": "Fazer preview ou registrar um projeto independente existente sob uma raiz explícita de coordenação."
            }
          },
          {
            "command": "hq-sync",
            "effects": {
              "en": "Reports consistency and issues without repair.",
              "ptBr": "Informa consistência e issues sem repair."
            },
            "example": "<python> -B scripts/cross_project.py hq-sync --root \"<coordination-root>\"",
            "inputs": [
              "<coordination-root>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Validate the canonical manifest and all managed coordination projections.",
              "ptBr": "Validar o manifest canônico e todas as projeções gerenciadas de coordenação."
            }
          },
          {
            "command": "digere",
            "effects": {
              "en": "Returns ownership routing and writes nothing; it does not synthesize a digest.",
              "ptBr": "Retorna o roteamento de ownership e não escreve; não sintetiza um digest."
            },
            "example": "<python> -B scripts/cross_project.py digere --root \"<coordination-root>\" --front \"<front-id>\" --scope \"<local|coordination|ephemeral>\"",
            "inputs": [
              "<coordination-root>",
              "<front-id>",
              "<local|coordination|ephemeral>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Classify one explicit input as project-local, coordination-wide, or ephemeral.",
              "ptBr": "Classificar uma entrada explícita como local ao projeto, transversal à coordenação ou ephemeral."
            }
          },
          {
            "command": "registra",
            "effects": {
              "en": "Updates only explicit coordination state and leaves the initial reflection pending when applicable.",
              "ptBr": "Atualiza somente o estado explícito de coordenação e mantém a reflexão inicial pendente quando aplicável."
            },
            "example": "<python> -B scripts/cross_project.py registra --root \"<coordination-root>\" --front \"<front-id>\" --state \"<state>\" --next \"<next-action>\" --blocker \"<blocker>\"",
            "inputs": [
              "<coordination-root>",
              "<front-id>",
              "<state>",
              "<next-action>",
              "<blocker?>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Persist one minimal confirmed coordination checkpoint for a registered project.",
              "ptBr": "Persistir um checkpoint mínimo e confirmado de coordenação para um projeto registrado."
            }
          },
          {
            "command": "encerra",
            "effects": {
              "en": "Closes the coordination block, clears the pending reflection, and records the confirmed resumption contract.",
              "ptBr": "Encerra o bloco de coordenação, remove a reflexão pendente e registra o contrato confirmado de retomada."
            },
            "example": "<python> -B scripts/cross_project.py encerra --root \"<coordination-root>\" --front \"<front-id>\" --role \"<role>\" --state \"<state>\" --next \"<next-action>\" --summary \"<summary>\" --reflect-when \"<reflect-when>\" --blocker \"<blocker>\"",
            "inputs": [
              "<coordination-root>",
              "<front-id>",
              "<role>",
              "<state>",
              "<next-action>",
              "<summary>",
              "<reflect-when>",
              "<blocker?>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Persist a complete explicit reflection or later cross-project handoff.",
              "ptBr": "Persistir uma reflexão explícita completa ou um handoff posterior entre projetos."
            }
          }
        ],
        "readiness": {
          "en": "The coordination manifest has at least one explicit existing project registration, every managed projection matches it, and hq-sync reports consistent state.",
          "ptBr": "O manifest de coordenação contém ao menos um registro explícito de projeto existente, cada projeção gerenciada corresponde a ele e hq-sync informa estado consistente."
        },
        "workflows": {
          "closeResume": {
            "purpose": {
              "en": "Close with a complete reflection and reopen the same named project from its recorded next action.",
              "ptBr": "Encerrar com uma reflexão completa e reabrir o mesmo projeto nomeado a partir da próxima ação registrada."
            },
            "steps": [
              "encerra",
              "hq-sync",
              "bom-dia"
            ]
          },
          "daily": {
            "purpose": {
              "en": "Open one named project, route explicit input, and save only the minimal confirmed coordination delta.",
              "ptBr": "Abrir um projeto nomeado, rotear a entrada explícita e salvar somente o delta mínimo e confirmado de coordenação."
            },
            "steps": [
              "bom-dia",
              "digere",
              "registra",
              "hq-sync"
            ]
          },
          "firstUse": {
            "purpose": {
              "en": "Open read-only, preview and register one confirmed existing project, then require clean structural sync.",
              "ptBr": "Abrir em modo read-only, fazer preview e registrar um projeto existente e confirmado e então exigir sincronização estrutural limpa."
            },
            "steps": [
              "bom-dia",
              "hq-init",
              "hq-sync"
            ]
          },
          "verifyRecover": {
            "purpose": {
              "en": "Use hq-sync as read-only diagnosis; on inconsistency, stop for explicit manual recovery because this harness has no repair command.",
              "ptBr": "Usar hq-sync como diagnóstico read-only; em caso de inconsistência, parar para recovery manual explícito porque este harness não possui comando de repair."
            },
            "steps": [
              "hq-sync"
            ]
          }
        }
      },
      "strengths": {
        "en": [
          "Independent projects",
          "Handoffs",
          "Structural sync"
        ],
        "ptBr": [
          "Projetos independentes",
          "Handoffs",
          "Sincronização estrutural"
        ]
      }
    },
    {
      "aliases": [
        "control-plane",
        "control-plane-harness",
        "orchestration"
      ],
      "asset": "orchestration-0.2.1.zip",
      "complexity": {
        "en": "High",
        "level": "high",
        "ptBr": "Alta"
      },
      "content": {
        "en": {
          "bestFor": "A new control plane whose registry and lifecycle mutations justify transactions and recovery.",
          "notFor": "Adopting an existing project layout, dispatching agents, or executing project work.",
          "scenario": "I am creating a new structure that needs a strict registry, transactions, and recovery.",
          "summary": "A transactional local control plane for a deliberate new Master structure.",
          "whatItChanges": "Creates a strict Master registry and managed front structure through validated transactional mutations. It does not call models or dispatch agents."
        },
        "ptBr": {
          "bestFor": "Um control plane novo em que o cadastro central e as mudanças de ciclo de vida justificam transações e recuperação.",
          "notFor": "Adotar uma estrutura de projetos existente, acionar coding agents ou executar o trabalho dos projetos.",
          "scenario": "Estou criando uma estrutura de coordenação nova que precisa de cadastro central estrito, transações e recuperação.",
          "summary": "Um control plane transacional para uma estrutura central criada de forma deliberada.",
          "whatItChanges": "Cria um cadastro central estrito e frentes gerenciadas por mudanças transacionais validadas. Não chama modelos nem aciona coding agents."
        }
      },
      "displayName": "Control Plane Harness",
      "id": "orchestration",
      "operator": {
        "entrypoint": "hq.py",
        "installationReadiness": {
          "en": [
            "The explicit target is a deliberate new Master or control-plane root, not an existing coordination structure to adopt.",
            "The initial fronts, their intended relative paths, and their boundaries are already known.",
            "The work genuinely requires a transactional registry, validated mutations, rollback, and recovery rather than only project handoffs."
          ],
          "ptBr": [
            "O target explícito é uma nova raiz Master ou de control plane deliberada, não uma estrutura de coordenação existente a ser adotada.",
            "As frentes iniciais, seus paths relativos pretendidos e seus boundaries já são conhecidos.",
            "O trabalho realmente exige registry transacional, validated mutations, rollback e recovery, e não apenas handoffs entre projetos."
          ]
        },
        "memory": {
          "canonical": [
            ".orchestration/manifest.json"
          ],
          "description": {
            "en": "The new control-plane root owns a transactional registry and lifecycle projections; registered fronts retain their bounded records below their confirmed paths.",
            "ptBr": "A nova raiz do control plane mantém um registry transacional e projeções do ciclo de vida; as frentes registradas preservam seus registros delimitados nos paths confirmados."
          },
          "projections": [
            "FRONTS.md",
            "NEXT.md",
            "<front-path>/REFLECTIONS.md",
            "<front-path>/RECORDS.md",
            "<front-path>/SESSIONS.md"
          ]
        },
        "operations": [
          {
            "command": "bom-dia",
            "effects": {
              "en": "Reads registry, sync, and recovery state without writing.",
              "ptBr": "Lê o registry e os estados de sync e recovery sem writes."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json bom-dia \"<front-selector>\"",
            "inputs": [
              "<workspace>",
              "<front-selector?>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Open the control plane or one selected front and determine the safe next operation.",
              "ptBr": "Abrir o control plane ou uma frente selecionada e determinar a próxima operação segura."
            }
          },
          {
            "command": "foco",
            "effects": {
              "en": "Updates the active-front selection in the strict registry and deterministic views.",
              "ptBr": "Atualiza a seleção da frente ativa no registry estrito e nas views determinísticas."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json foco \"<front-selector>\"",
            "inputs": [
              "<workspace>",
              "<front-selector>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Transactionally select one explicit registered front.",
              "ptBr": "Selecionar transacionalmente uma frente registrada e explícita."
            }
          },
          {
            "command": "init",
            "effects": {
              "en": "Dry-run writes nothing; apply creates the strict registry and declared Master/front lifecycle files through a journaled transaction.",
              "ptBr": "O dry-run não escreve; o apply cria o registry estrito e os arquivos declarados de ciclo de vida do Master e da frente por uma transação com journal."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json init --id \"<front-id>\" --name \"<front-name>\" --path \"<front-path>\" --alias \"<alias>\" --dry-run",
            "inputs": [
              "<workspace>",
              "<front-id>",
              "<front-name>",
              "<front-path>",
              "<alias?>",
              "--dry-run|--apply"
            ],
            "kind": "write",
            "purpose": {
              "en": "Preview or transactionally initialize the control plane and register one new front.",
              "ptBr": "Fazer preview ou inicializar transacionalmente o control plane e registrar uma nova frente."
            }
          },
          {
            "command": "hq-sync",
            "effects": {
              "en": "Reports clean state or bounded issues without repair.",
              "ptBr": "Informa estado limpo ou issues delimitadas sem repair."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json hq-sync",
            "inputs": [
              "<workspace>"
            ],
            "kind": "read",
            "purpose": {
              "en": "Strictly validate registry, front boundaries, generated files, locks, and recovery state.",
              "ptBr": "Validar estritamente o registry, os limites das frentes, os arquivos gerados, locks e o estado de recovery."
            }
          },
          {
            "command": "digere",
            "effects": {
              "en": "Transactionally records only the supplied reflection and moves the front to digested state.",
              "ptBr": "Registra transacionalmente somente a reflexão fornecida e move a frente para o estado digested."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json digere --front \"<front-selector>\" --summary \"<summary>\" --pending \"<pending-action>\"",
            "inputs": [
              "<workspace>",
              "<front-selector?>",
              "<summary>",
              "<pending-action>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Persist one explicit reflection and pending action for a selected front.",
              "ptBr": "Persistir uma reflexão explícita e uma ação pendente para a frente selecionada."
            }
          },
          {
            "command": "registra",
            "effects": {
              "en": "Transactionally records the current digest and moves the selected front to recorded state.",
              "ptBr": "Registra transacionalmente o digest atual e move a frente selecionada para o estado recorded."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json registra --front \"<front-selector>\" --note \"<note>\"",
            "inputs": [
              "<workspace>",
              "<front-selector?>",
              "<note?>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Promote the current explicit digest to a durable record.",
              "ptBr": "Promover o digest explícito atual para um registro durável."
            }
          },
          {
            "command": "encerra",
            "effects": {
              "en": "Transactionally persists closeout and the next resumption point, then moves the front to closed state.",
              "ptBr": "Persiste transacionalmente o closeout e o próximo ponto de retomada e move a frente para o estado closed."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json encerra --front \"<front-selector>\" --summary \"<summary>\" --next \"<next-action>\"",
            "inputs": [
              "<workspace>",
              "<front-selector?>",
              "<summary>",
              "<next-action>"
            ],
            "kind": "write",
            "purpose": {
              "en": "Close a recorded work block with an explicit summary and next action.",
              "ptBr": "Encerrar um bloco de trabalho registrado com summary e próxima ação explícitos."
            }
          },
          {
            "command": "repair-panel",
            "effects": {
              "en": "Repairs only the generated panel after every registry and boundary check passes; it never repoints or merges fronts.",
              "ptBr": "Faz repair somente do painel gerado depois que todas as verificações de registry e limites passam; nunca redireciona nem mescla frentes."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json repair-panel --dry-run",
            "inputs": [
              "<workspace>",
              "--dry-run|--apply"
            ],
            "kind": "repair",
            "purpose": {
              "en": "Preview or repair only a derivable generated pending-panel mismatch.",
              "ptBr": "Fazer preview ou repair somente de uma divergência derivável no painel gerado de pendências."
            }
          },
          {
            "command": "recover",
            "effects": {
              "en": "Rolls back a recognized pre-commit transaction or completes verified cleanup after a durable commit; unknown bytes stop recovery.",
              "ptBr": "Executa rollback de uma transação pre-commit reconhecida ou conclui cleanup verificado após commit durável; bytes desconhecidos interrompem recovery."
            },
            "example": "<python> -B hq.py --root \"<workspace>\" --json recover --dry-run",
            "inputs": [
              "<workspace>",
              "--dry-run|--apply",
              "--break-stale-lock?"
            ],
            "kind": "repair",
            "purpose": {
              "en": "Inspect or apply verified recovery for a durable transaction journal.",
              "ptBr": "Inspecionar ou aplicar recovery verificado para um journal durável de transação."
            }
          }
        ],
        "readiness": {
          "en": "A new control plane has at least one explicit registered front, the registry and generated lifecycle files are coherent, no recovery is pending, and hq-sync reports clean state.",
          "ptBr": "Um control plane novo contém ao menos uma frente registrada explicitamente, o registry e os arquivos gerados de ciclo de vida estão coerentes, não há recovery pendente e hq-sync informa estado limpo."
        },
        "workflows": {
          "closeResume": {
            "purpose": {
              "en": "Close a recorded block and reopen from its durable next action.",
              "ptBr": "Fazer closeout de um bloco registrado e retomar a partir da próxima ação durável."
            },
            "steps": [
              "encerra",
              "bom-dia"
            ]
          },
          "daily": {
            "purpose": {
              "en": "Open, require clean sync, select the intended front, persist only an explicit digest, and promote it deliberately.",
              "ptBr": "Abrir, exigir sync limpo, selecionar a frente pretendida, persistir somente um digest explícito e promovê-lo deliberadamente."
            },
            "steps": [
              "bom-dia",
              "hq-sync",
              "foco",
              "digere",
              "registra"
            ]
          },
          "firstUse": {
            "purpose": {
              "en": "Open read-only, preview one confirmed registration, apply it, require clean sync, and select the registered front.",
              "ptBr": "Abrir em modo read-only, fazer preview de um registro confirmado, aplicar, exigir sync limpo e selecionar a frente registrada."
            },
            "steps": [
              "bom-dia",
              "init",
              "hq-sync",
              "foco"
            ]
          },
          "verifyRecover": {
            "purpose": {
              "en": "Use hq-sync for diagnosis, inspect recovery before apply when a journal exists, use panel repair only for its narrow derivable case, and require clean sync afterward.",
              "ptBr": "Usar hq-sync para diagnóstico, inspecionar recovery antes do apply quando houver journal, usar repair do painel somente no caso derivável e delimitado e exigir sync limpo ao final."
            },
            "steps": [
              "hq-sync",
              "recover",
              "repair-panel",
              "hq-sync"
            ]
          }
        }
      },
      "strengths": {
        "en": [
          "Strict registry",
          "Transactions",
          "Recovery"
        ],
        "ptBr": [
          "Cadastro central com validação estrita",
          "Transações",
          "Recuperação"
        ]
      }
    }
  ],
  "promptInstructions": {
    "en": "Use the agent's native Plan mode and structured questions when available; otherwise present the same plan and questions conversationally. Work in two explicit stages: plan first, then execute only after confirmation. Before any write, including a download or temporary extraction, inspect only the explicit target and available public tooling read-only. Present four separate checklists: (1) fit and target, (2) safety and write plan, (3) initialization and readiness, and (4) tutorial and handoff. State the selected harness, target, one user- or system-available Python 3.10+ executable as `<python>` (for example `python3`, `python`, or `py -3`), expected writes, required initialization inputs, verification, rollback, and tutorial steps; ask the user to confirm that plan. Never use a private Codex runtime. Do not organize, rename, summarize, migrate, or infer the user's project data. Ask for any missing value instead of inventing it. After confirmation, download the ZIP and its adjacent `.sha256` sidecar into an isolated temporary directory, verify the checksum before extraction or execution, and extract it. From the extracted bundle root run:\n`<python> -B installer.py doctor <selector> --target \"<target>\" --json`\nIf doctor or any pre-apply readiness check fails, stop with zero target writes, clean only isolated temporary files, and recommend a better fit when applicable; never silently substitute another harness. Then run:\n`<python> -B installer.py install <selector> --target \"<target>\" --dry-run --json`\nReview the result against the confirmed plan and ask again if the write set or assumptions materially changed. Otherwise run:\n`<python> -B installer.py install <selector> --target \"<target>\" --apply --json`\nFollow `package/README.md` to initialize the target, previewing every runtime mutation and using only confirmed user values. If any step fails after the first apply or final readiness is false, stop normal execution and follow the exact package's documented rollback or recovery procedure, preview it before apply, preserve unrelated files, verify restoration toward the exact pre-install state, and report any unavoidable residual change instead of claiming success. Then run from the bundle root:\n`<python> -B installer.py verify <selector> --target \"<target>\" --json`\nReport installation success only when this final result contains `ready=true`. After readiness, read the installed runtime's `operations.json` and `OPERATOR_GUIDE.md`, then give the user a concise tutorial in the conversation covering every command, the first-use, daily, close-and-resume, and verify-or-recover workflows, safe examples with confirmed values or placeholders, and update/uninstall guidance. Do not create tutorial files. Clean temporary files and report the receipt, readiness evidence, rollback status, and runtime location. Offer support through LinkedIn at https://www.linkedin.com/in/fabianomag/ or email at fm@fabianomag.com. Do not edit unrelated documentation, `PATH`, or `.gitignore`, and do not install a global Skill.",
    "ptBr": "\n\nUse o Plan mode nativo e structured questions do agente quando disponíveis; caso contrário, apresente o mesmo plano e as mesmas perguntas na conversa. Trabalhe em duas etapas explícitas: primeiro o plano e depois a execução somente após confirmação. Antes de qualquer escrita, inclusive download ou extração temporária, inspecione apenas o diretório-alvo explícito e o ferramental público disponível em modo read-only. Apresente quatro checklists separados: (1) fit e target, (2) segurança e plano de writes, (3) inicialização e readiness e (4) tutorial e handoff. Informe o harness selecionado, o target, um único executável do Python 3.10+ disponível para o usuário ou para o sistema como `<python>` (por exemplo, `python3`, `python` ou `py -3`), as escritas previstas, os dados necessários para inicialização, a verificação, o rollback e o tutorial; peça ao usuário que confirme esse plano. Nunca use um runtime privado do Codex. Não organize, renomeie, resuma, migre nem infira dados do projeto do usuário. Pergunte por qualquer valor ausente em vez de inventá-lo. Após a confirmação, baixe o ZIP e o arquivo `.sha256` correspondente em um diretório temporário isolado, valide a soma SHA-256 antes de extrair ou executar qualquer arquivo e extraia o pacote. Na raiz do pacote extraído, execute:\n`<python> -B installer.py doctor <selector> --target \"<target>\" --json`\nSe doctor ou qualquer verificação de readiness anterior ao apply falhar, pare com zero writes no target, limpe somente os arquivos temporários isolados e recomende a opção mais adequada quando aplicável; nunca substitua silenciosamente por outro harness. Depois execute:\n`<python> -B installer.py install <selector> --target \"<target>\" --dry-run --json`\nCompare o resultado com o plano confirmado e pergunte novamente se o conjunto de writes ou as premissas mudaram de forma relevante. Caso contrário, execute:\n`<python> -B installer.py install <selector> --target \"<target>\" --apply --json`\nSiga `package/README.pt-BR.md` para inicializar o target, sempre antecipando cada mutação do runtime e usando somente valores confirmados pelo usuário. Se qualquer etapa falhar depois do primeiro apply ou a readiness final for falsa, interrompa a execução normal e siga o procedimento documentado de rollback ou recovery do package exato, faça preview antes do apply, preserve arquivos não relacionados, verifique a restauração em direção ao estado exato anterior à instalação e informe qualquer mudança residual inevitável em vez de declarar sucesso. Na raiz do pacote, execute:\n`<python> -B installer.py verify <selector> --target \"<target>\" --json`\nSó declare sucesso quando o resultado final contiver `ready=true`. Após readiness, leia `operations.json` e `OPERATOR_GUIDE.pt-BR.md` no runtime instalado e apresente ao usuário, na conversa, um tutorial conciso que cubra cada comando, os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery, exemplos seguros com valores confirmados ou placeholders e orientações de update/uninstall. Não crie arquivos de tutorial. Limpe os arquivos temporários e informe receipt, evidência de readiness, estado do rollback e localização do runtime. Ofereça suporte pelo LinkedIn em https://www.linkedin.com/in/fabianomag/ ou pelo email fm@fabianomag.com. Não edite documentação não relacionada, `PATH` ou `.gitignore` e não instale uma Skill global."
  },
  "ptBrEnglishTerms": [
    "harness",
    "coding agent",
    "workspace",
    "prompt",
    "Skill",
    "CLI",
    "dry-run",
    "apply",
    "rollback",
    "runtime",
    "manifest",
    "checkpoint",
    "closeout",
    "single writer",
    "control plane",
    "guardrails",
    "release",
    "commit",
    "handoff"
  ],
  "release": {
    "minimumPython": "3.10",
    "repository": "https://github.com/fabianomag/agent-harnesses",
    "site": {
      "en": "https://fabianomag.com/projects/agent-harnesses",
      "ptBr": "https://fabianomag.com/pt-br/projetos/agent-harnesses"
    },
    "tag": "v0.2.1",
    "version": "0.2.1"
  },
  "schemaVersion": 2,
  "support": {
    "email": "fm@fabianomag.com",
    "linkedin": "https://www.linkedin.com/in/fabianomag/"
  },
  "tutorial": {
    "constraints": {
      "en": "Deliver the tutorial in the user's language and in the conversation without creating project documentation. Use only values explicitly supplied by the user; otherwise retain placeholders. Do not install or instruct the installation of any global agent adapter.",
      "ptBr": "Entregue o tutorial no idioma do usuário e na conversa sem criar documentação no projeto. Use somente valores fornecidos explicitamente pelo usuário; caso contrário, mantenha placeholders. Não instale nem oriente a instalação de qualquer adapter global de agente."
    },
    "delivery": "conversation",
    "mustCover": {
      "en": [
        "The mental model: what the installed harness remembers and what remains outside its boundary.",
        "The exact target-local locations of canonical operational memory and readable projections.",
        "Every installed command, its read, write, or repair kind, and when to use it.",
        "The first-use, daily, close-and-resume, and verify-or-recover workflows.",
        "A first safe example that uses only confirmed user values and retains placeholders for anything unknown.",
        "How to close, resume, verify, and recover without inventing state.",
        "The installation receipt, how to preview mutations, and how to roll back, update, or uninstall."
      ],
      "ptBr": [
        "O modelo mental: o que o harness instalado preserva e o que permanece fora do seu limite.",
        "As localizações exatas e locais ao target da memória operacional canônica e das projeções legíveis.",
        "Cada comando instalado, sua categoria read, write ou repair e quando usá-lo.",
        "Os workflows de primeiro uso, uso diário, closeout e retomada e verificação ou recovery.",
        "Um primeiro exemplo seguro que use somente valores confirmados pelo usuário e preserve placeholders para tudo que for desconhecido.",
        "Como encerrar, retomar, verificar e executar recovery sem inventar estado.",
        "O receipt de instalação, como prever mutações e como executar rollback, update ou uninstall."
      ]
    },
    "packageLifecycle": {
      "en": [
        "Receipt: target-relative `.agent-harnesses/runtime/<id>/<version>/.agent-harness-receipt.json`.",
        "From a checksum-verified `<version>` bundle, preview package removal with `<python> -B installer.py uninstall <id> --target \"<target>\" --dry-run --json`; after review, apply it with `<python> -B installer.py uninstall <id> --target \"<target>\" --apply --json`.",
        "Uninstall removes only the receipt-owned runtime and installer-managed onboarding block. It never removes initialized operational state.",
        "If a step fails after package apply, first run this package's verify-or-recover workflow. If the target still is not ready, preview and then apply uninstall to roll back the package. Preserve and report any residual initialized state; never delete it automatically.",
        "To update, download the new version's ZIP and matching checksum sidecar, verify the checksum, read its migration notes, then run the new bundle's doctor, install --dry-run, and install --apply. Do not edit a versioned runtime in place; keep the old version until the new one reaches ready=true."
      ],
      "ptBr": [
        "Receipt: path relativo ao target `.agent-harnesses/runtime/<id>/<version>/.agent-harness-receipt.json`.",
        "A partir de um bundle `<version>` com checksum verificado, antecipe a remoção do package com `<python> -B installer.py uninstall <id> --target \"<target>\" --dry-run --json`; após a revisão, aplique-a com `<python> -B installer.py uninstall <id> --target \"<target>\" --apply --json`.",
        "Uninstall remove somente o runtime pertencente ao receipt e o bloco de onboarding gerenciado pelo installer. Ele nunca remove o estado operacional inicializado.",
        "Se uma etapa falhar após o apply do package, primeiro execute o workflow de verify ou recovery deste package. Se o target ainda não estiver ready, antecipe e depois aplique o uninstall para executar rollback do package. Preserve e informe qualquer estado inicializado residual; nunca o apague automaticamente.",
        "Para update, baixe o ZIP e o checksum sidecar correspondentes à nova versão, verifique o checksum, leia as migration notes e então execute doctor, install --dry-run e install --apply com o novo bundle. Não edite um runtime versionado in-place; mantenha a versão anterior até a nova chegar a ready=true."
      ]
    },
    "requiredAfterReady": true,
    "sources": {
      "operations": "operations.json",
      "operatorGuide": {
        "en": "OPERATOR_GUIDE.md",
        "ptBr": "OPERATOR_GUIDE.pt-BR.md"
      }
    }
  }
}''')
VERSION = PRODUCT["release"]["version"]
MARKERS = {
    "project-harness": Path(".project-harness/state.json"),
    "workspace-coordination": Path(".workspace-coordination/workspace.json"),
    "cross-project": Path("harness.config.json"),
    "orchestration": Path(".orchestration/manifest.json"),
}
RUNTIME_RELATIVE = Path(".agent-harnesses/runtime")
RECEIPT_NAME = ".agent-harness-receipt.json"
AGENTS_RELATIVE = Path("AGENTS.md")
ONBOARDING_MARKER_TOKEN = b"<!-- agent-harnesses:onboarding:"
ONBOARDING_MARKER = re.compile(
    rb"<!-- agent-harnesses:onboarding:"
    rb"([a-z][a-z0-9]*(?:-[a-z0-9]+)*):(start|end) -->"
)
ONBOARDING_PACKAGE_FILES = (
    "operations.json",
    "OPERATOR_GUIDE.md",
    "OPERATOR_GUIDE.pt-BR.md",
)
ONBOARDING_SEPARATOR = b"\n\n"
ONBOARDING_LOCK_NAME = ".onboarding.lock"
ONBOARDING_LOCK_ATTEMPTS = 500
MANAGED_PATH_SHAPES = {
    "project-harness": {
        ".project-harness": "directory",
        "docs": "directory",
        "generated": "directory",
        "plans": "directory",
        "references": "directory",
        "AGENTS.md": "file",
        "ARCHITECTURE.md": "file",
        "docs/project-context.md": "file",
        "docs/decisions.md": "file",
        "docs/next-actions.md": "file",
        "docs/session-log.md": "file",
    },
    "workspace-coordination": {
        ".workspace-coordination": "directory",
        "WORKSPACE_COORDINATION.md": "file",
    },
    "cross-project": {
        "harness.config.json": "file",
        "AGENTS.md": "file",
        "FRONTS.md": "file",
        "NEXT.md": "file",
    },
    "orchestration": {
        ".orchestration": "directory",
        "fronts": "directory",
        "AGENTS.md": "file",
        "ARCHITECTURE.md": "file",
        "FRONTS.md": "file",
        "NEXT.md": "file",
    },
}


class InstallerFailure(RuntimeError):
    def __init__(self, code, phase, message, remediation, ready=False):
        RuntimeError.__init__(self, message)
        self.result = {
            "code": code,
            "phase": phase,
            "message": message,
            "remediation": remediation,
            "ready": bool(ready),
        }


def _result(code, phase, message, remediation="", ready=False):
    return {
        "code": code,
        "phase": phase,
        "message": message,
        "remediation": remediation,
        "ready": bool(ready),
    }


def _onboarding_paths(package_id):
    base = (RUNTIME_RELATIVE / package_id / VERSION).as_posix()
    return {
        "operationsContract": "%s/operations.json" % base,
        "operatorGuides": {
            "en": "%s/OPERATOR_GUIDE.md" % base,
            "ptBr": "%s/OPERATOR_GUIDE.pt-BR.md" % base,
        },
    }


def _with_onboarding(result, package_id):
    enriched = dict(result)
    enriched.update(_onboarding_paths(package_id))
    return enriched


def _onboarding_markers(package_id):
    return (
        ("<!-- agent-harnesses:onboarding:%s:start -->" % package_id).encode("ascii"),
        ("<!-- agent-harnesses:onboarding:%s:end -->" % package_id).encode("ascii"),
    )


def _onboarding_block(package_id):
    begin, end = _onboarding_markers(package_id)
    paths = _onboarding_paths(package_id)
    return (
        begin
        + b"\n## Agent Harness operating contract\n\n"
        + b"Before operating this harness, read these target-relative files:\n\n"
        + ("- Operations contract: `%s`\n" % paths["operationsContract"]).encode("utf-8")
        + (
            "- Operator guide (English): `%s`\n"
            % paths["operatorGuides"]["en"]
        ).encode("utf-8")
        + (
            "- Guia do operador (PT-BR): `%s`\n\n"
            % paths["operatorGuides"]["ptBr"]
        ).encode("utf-8")
        + b"Use only the operations declared for this installed harness.\n"
        + end
        + b"\n"
    )


def _is_link_like(path):
    try:
        metadata = path.lstat()
    except OSError as error:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "downloaded",
            "Path metadata cannot be read safely.",
            "Choose one existing real directory with no linked components.",
        ) from error
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and attributes & reparse)


def _lexists(path):
    return os.path.lexists(os.fspath(path))


def _onboarding_failure(code, phase, message, remediation):
    raise InstallerFailure(code, phase, message, remediation)


def _inspect_onboarding(target, package_id, phase="downloaded", required=False):
    path = target / AGENTS_RELATIVE
    if not _lexists(path):
        if required:
            _onboarding_failure(
                "E_CHECKSUM_MISMATCH",
                phase,
                "The target-local onboarding block is missing.",
                "Restore the exact managed AGENTS.md block before retrying.",
            )
        return {
            "path": path,
            "exists": False,
            "data": None,
            "mode": 0o644,
            "packageId": None,
            "start": None,
            "end": None,
            "exclusive": False,
        }
    if _is_link_like(path) or not path.is_file():
        _onboarding_failure(
            "E_INITIALIZATION_CONFLICT",
            phase,
            "AGENTS.md is not a real regular file.",
            "Resolve the AGENTS.md collision without following or overwriting it.",
        )
    try:
        data = path.read_bytes()
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as error:
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            phase,
            "AGENTS.md cannot be read safely.",
            "Keep it unchanged and resolve its permissions before retrying.",
        ) from error
    matches = list(ONBOARDING_MARKER.finditer(data))
    reserved_count = data.count(ONBOARDING_MARKER_TOKEN)
    if reserved_count == 0:
        if required:
            _onboarding_failure(
                "E_CHECKSUM_MISMATCH",
                phase,
                "The target-local onboarding block is missing.",
                "Restore the exact managed AGENTS.md block before retrying.",
            )
        return {
            "path": path,
            "exists": True,
            "data": data,
            "mode": mode,
            "packageId": None,
            "start": None,
            "end": None,
            "exclusive": False,
        }
    if reserved_count != len(matches) or len(matches) != 2:
        _onboarding_failure(
            "E_INITIALIZATION_CONFLICT",
            phase,
            "The target-local onboarding markers are malformed or duplicated.",
            "Keep AGENTS.md unchanged and restore exactly one valid managed marker pair.",
        )
    first_id = matches[0].group(1).decode("ascii")
    second_id = matches[1].group(1).decode("ascii")
    first_kind = matches[0].group(2)
    second_kind = matches[1].group(2)
    if first_id != second_id or first_kind != b"start" or second_kind != b"end":
        _onboarding_failure(
            "E_INITIALIZATION_CONFLICT",
            phase,
            "The target-local onboarding markers are malformed or out of order.",
            "Keep AGENTS.md unchanged and restore exactly one ordered marker pair.",
        )
    if first_id != package_id:
        _onboarding_failure(
            "E_HARNESS_MISMATCH",
            phase,
            "AGENTS.md contains onboarding for a different harness.",
            "Keep the target unchanged and use %s." % _recommend(first_id)
            if first_id in {item["id"] for item in PRODUCT["packages"]}
            else "Remove the unknown managed block only after resolving its ownership.",
        )
    expected = _onboarding_block(package_id)
    start = matches[0].start()
    end = start + len(expected)
    if data[start:end] != expected or matches[1].end() != end - 1:
        _onboarding_failure(
            "E_CHECKSUM_MISMATCH",
            phase,
            "The target-local onboarding block differs from its exact contract.",
            "Restore the generated block without changing surrounding AGENTS.md bytes.",
        )
    return {
        "path": path,
        "exists": True,
        "data": data,
        "mode": mode,
        "packageId": package_id,
        "start": start,
        "end": end,
        "exclusive": data == expected,
    }


def _safe_existing_directory(value):
    if not value or not str(value).strip():
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "downloaded",
            "The target must be explicit.",
            "Pass --target with one existing project or workspace directory.",
        )
    requested = Path(value)
    lexical = requested if requested.is_absolute() else Path.cwd() / requested
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current = current / part
        if _lexists(current) and _is_link_like(current):
            raise InstallerFailure(
                "E_TARGET_AMBIGUOUS",
                "downloaded",
                "The target contains a linked path component.",
                "Choose one existing real directory with no symlinks or reparse points.",
            )
    try:
        target = lexical.resolve(strict=True)
    except OSError as error:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "downloaded",
            "The target does not resolve to an existing directory.",
            "Create or select the exact project or workspace directory first.",
        ) from error
    if not target.is_dir() or _is_link_like(target):
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "downloaded",
            "The target is not a real directory.",
            "Choose one existing real project or workspace directory.",
        )
    forbidden = {Path(target.anchor), Path.home().resolve()}
    if target in forbidden or target.name.casefold() == ".git" or ".git" in target.parts:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "downloaded",
            "The selected target is too broad or is Git metadata.",
            "Choose the exact project or workspace root, never a home, filesystem, or .git directory.",
        )
    return target


def _package_for_selector(selector):
    normalized = selector.strip().lower()
    for package in PRODUCT["packages"]:
        if normalized in package["aliases"]:
            return package
    raise InstallerFailure(
        "E_HARNESS_MISMATCH",
        "downloaded",
        "The selector does not identify one public harness.",
        "Use project-harness, workspace-coordination, cross-project, or orchestration.",
    )


def _marker_ids(target):
    observed = []
    for package_id, relative in MARKERS.items():
        current = target
        parent_missing = False
        for part in relative.parts[:-1]:
            current = current / part
            if not _lexists(current):
                parent_missing = True
                break
            if _is_link_like(current) or not current.is_dir():
                raise InstallerFailure(
                    "E_INITIALIZATION_CONFLICT",
                    "downloaded",
                    "An existing harness marker boundary is not a real directory.",
                    "Resolve the marker collision without following or overwriting it.",
                )
        if parent_missing:
            continue
        marker = target / relative
        if not _lexists(marker):
            continue
        if _is_link_like(marker) or not marker.is_file():
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "downloaded",
                "An existing harness marker is not a real file.",
                "Resolve the marker collision without following or overwriting it.",
            )
        observed.append(package_id)
    return observed


def _validate_managed_shapes(package, target):
    for relative_text, expected_kind in MANAGED_PATH_SHAPES[package["id"]].items():
        relative = Path(relative_text)
        current = target
        for index, part in enumerate(relative.parts):
            current = current / part
            if not _lexists(current):
                break
            if _is_link_like(current):
                raise InstallerFailure(
                    "E_INITIALIZATION_CONFLICT",
                    "downloaded",
                    "A path managed by the selected harness contains a link.",
                    "Resolve the collision without following or overwriting the linked path.",
                )
            final = index == len(relative.parts) - 1
            if not final and not current.is_dir():
                raise InstallerFailure(
                    "E_INITIALIZATION_CONFLICT",
                    "downloaded",
                    "A parent of a managed path is not a directory.",
                    "Resolve the conflicting path before installation.",
                )
            if final:
                matches = current.is_dir() if expected_kind == "directory" else current.is_file()
                if not matches:
                    raise InstallerFailure(
                        "E_INITIALIZATION_CONFLICT",
                        "downloaded",
                        "An existing managed path has an incompatible type.",
                        "Keep it unchanged and choose another target or resolve the collision explicitly.",
                    )


def _recommend(package_id):
    names = {item["id"]: item["displayName"] for item in PRODUCT["packages"]}
    return "%s (`%s`)" % (names[package_id], package_id)


def _doctor(package, target):
    marker_ids = _marker_ids(target)
    if len(marker_ids) > 1:
        raise InstallerFailure(
            "E_TARGET_AMBIGUOUS",
            "downloaded",
            "The target contains markers for more than one harness.",
            "Resolve the existing harness ownership before installing another runtime.",
        )
    if marker_ids and marker_ids[0] != package["id"]:
        observed = marker_ids[0]
        raise InstallerFailure(
            "E_HARNESS_MISMATCH",
            "downloaded",
            "The target is already initialized for a different harness.",
            "Keep the target unchanged and use %s." % _recommend(observed),
        )
    destination = _runtime_destination(target, package["id"])
    onboarding = _inspect_onboarding(
        target,
        package["id"],
        phase="installed" if _lexists(destination) else "downloaded",
    )
    _validate_managed_shapes(package, target)
    runtime_root = target / ".agent-harnesses"
    if _lexists(runtime_root) and (_is_link_like(runtime_root) or not runtime_root.is_dir()):
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "downloaded",
            "The target-local runtime boundary is not a real directory.",
            "Resolve the .agent-harnesses collision without overwriting it.",
        )
    if onboarding["packageId"] == package["id"] and not _lexists(destination):
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "downloaded",
            "AGENTS.md contains an unreceipted onboarding block.",
            "Keep it unchanged and resolve its ownership before installing this runtime.",
        )
    if _lexists(destination):
        receipt = _verify_runtime_files(destination, package["id"])
        _verify_onboarding(target, package["id"], receipt)
    if package["id"] == "orchestration" and not marker_ids:
        master_like = any(
            _lexists(target / name)
            for name in ("ARCHITECTURE.md", "NEXT.md", "FRONTS.md", "harness.config.json")
        )
        project_directories = [
            child
            for child in target.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
        if master_like or project_directories:
            raise InstallerFailure(
                "E_HARNESS_MISMATCH",
                "downloaded",
                "Control Plane Harness cannot safely adopt this existing project structure.",
                "Keep the target unchanged and evaluate %s for existing independent projects."
                % _recommend("cross-project"),
            )
    initialized = bool(marker_ids and marker_ids[0] == package["id"])
    message = "Preflight passed for the selected harness."
    if initialized:
        message = "Preflight passed; the target already has the selected harness marker."
    return _result("OK", "downloaded", message, ready=False)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(
    path,
    phase="downloaded",
    message="The package manifest is unreadable or invalid.",
    remediation="Discard the download and fetch the immutable release assets again.",
):
    def reject_duplicate(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate property")
            value[key] = item
        return value

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate)
    except (OSError, UnicodeError, ValueError) as error:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            phase,
            message,
            remediation,
        ) from error


def _inventory_failure(phase, message):
    remediation = "Discard the source and fetch it again."
    if phase == "installed":
        remediation = "Restore the exact receipt-owned runtime bytes before retrying."
    raise InstallerFailure("E_CHECKSUM_MISMATCH", phase, message, remediation)


def _portable_relative_path(value, phase):
    if not isinstance(value, str) or not value or chr(92) in value or "\x00" in value:
        _inventory_failure(phase, "The inventory contains an invalid portable path.")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or relative.as_posix() != value
        or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
    ):
        _inventory_failure(phase, "The inventory contains an unsafe or noncanonical path.")
    return relative


def _parse_inventory(inventory, phase):
    if not isinstance(inventory, list) or not inventory:
        _inventory_failure(phase, "The package inventory is missing or invalid.")
    expected = {}
    for entry in inventory:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            _inventory_failure(phase, "The package inventory entry shape is invalid.")
        relative = _portable_relative_path(entry["path"], phase)
        digest_value = entry["sha256"]
        if (
            not isinstance(digest_value, str)
            or len(digest_value) != 64
            or any(character not in "0123456789abcdef" for character in digest_value)
        ):
            _inventory_failure(phase, "The package inventory contains an invalid digest.")
        portable = relative.as_posix()
        if portable in expected:
            _inventory_failure(phase, "The package inventory contains a duplicate path.")
        expected[portable] = digest_value
    return expected


def _source_from_bundle(root, expected_id):
    manifest_path = root / "bundle-manifest.json"
    package_root = root / "package"
    if not manifest_path.is_file() or not package_root.is_dir():
        return None
    manifest = _load_json(manifest_path)
    package_identity = manifest.get("package") if isinstance(manifest, dict) else None
    if not isinstance(package_identity, dict) or package_identity.get("id") != expected_id or package_identity.get("version") != VERSION:
        raise InstallerFailure(
            "E_HARNESS_MISMATCH",
            "downloaded",
            "The extracted bundle does not match the selected harness.",
            "Discard it and download the exact selected asset.",
        )
    return package_root, manifest.get("files")


def _source_from_repository(root, expected_id):
    catalog_path = root / "catalog/harnesses.json"
    package_root = root / "packages" / expected_id
    if not catalog_path.is_file() or not package_root.is_dir():
        return None
    catalog = _load_json(catalog_path)
    for entry in catalog.get("packages", []):
        if entry.get("id") == expected_id and entry.get("version") == VERSION:
            return package_root, entry.get("files")
    raise InstallerFailure(
        "E_HARNESS_MISMATCH",
        "downloaded",
        "The source tree does not contain the selected v%s package." % VERSION,
        "Use the matching immutable release bundle.",
    )


def _validate_inventory(package_root, inventory):
    expected = _parse_inventory(inventory, "downloaded")
    missing_onboarding = sorted(set(ONBOARDING_PACKAGE_FILES) - set(expected))
    if missing_onboarding:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The package inventory is missing its operator onboarding contract.",
            "Discard the source and fetch the complete immutable release bundle.",
        )
    observed = {}
    for path in sorted(package_root.rglob("*")):
        if _is_link_like(path):
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The package contains a linked entry.", "Discard the source and fetch it again.")
        if path.is_file():
            observed[path.relative_to(package_root).as_posix()] = _sha256(path)
    if observed != expected:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The package bytes do not match the recorded inventory.",
            "Discard the source and fetch the immutable release assets again.",
        )
    return expected


def _safe_extract(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members:
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive is empty.", "Fetch the asset again.")
        for member in members:
            filename = member.orig_filename
            if member.filename != filename:
                raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive contains a nonportable entry.", "Discard the archive.")
            directory_suffix = filename.endswith("/")
            portable_name = filename[:-1] if directory_suffix else filename
            relative = _portable_relative_path(portable_name, "downloaded")
            mode = member.external_attr >> 16
            if member.is_dir() != directory_suffix or stat.S_ISLNK(mode):
                raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive contains an unsafe entry.", "Discard the archive.")
            candidate = destination.joinpath(*relative.parts).resolve()
            if destination.resolve() not in candidate.parents and candidate != destination.resolve():
                raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release archive escapes its extraction boundary.", "Discard the archive.")
        bundle.extractall(destination)


def _download_source(package, temporary):
    repository = PRODUCT["release"]["repository"]
    tag = PRODUCT["release"]["tag"]
    asset = package["asset"]
    url = "%s/releases/download/%s/%s" % (repository, tag, asset)
    archive = temporary / asset
    sidecar = temporary / (asset + ".sha256")
    try:
        urllib.request.urlretrieve(url, archive)
        urllib.request.urlretrieve(url + ".sha256", sidecar)
    except Exception as error:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The immutable release asset or checksum could not be downloaded.",
            "Check connectivity and the v%s release, then retry." % VERSION,
        ) from error
    try:
        fields = sidecar.read_text(encoding="ascii").strip().split()
    except (OSError, UnicodeError) as error:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The checksum sidecar is unreadable.", "Download both assets again.") from error
    if len(fields) != 2 or fields[1].lstrip("*") != asset or fields[0] != _sha256(archive):
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "downloaded",
            "The release archive checksum does not match its sidecar.",
            "Discard both files and do not extract or execute the archive.",
        )
    extracted = temporary / "extracted"
    extracted.mkdir()
    _safe_extract(archive, extracted)
    roots = [path.parent for path in extracted.rglob("bundle-manifest.json") if (path.parent / "package").is_dir()]
    if len(roots) != 1:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release bundle layout is invalid.", "Discard the archive and report the immutable asset.")
    source = _source_from_bundle(roots[0], package["id"])
    if source is None:
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "downloaded", "The release bundle is incomplete.", "Discard the archive and report the immutable asset.")
    return source


def _local_source(package_id):
    base = Path(__file__).resolve().parent
    for root in (base, base.parent):
        source = _source_from_bundle(root, package_id)
        if source is not None:
            return source
        source = _source_from_repository(root, package_id)
        if source is not None:
            return source
    return None


def _runtime_destination(target, package_id):
    return target / RUNTIME_RELATIVE / package_id / VERSION


def _onboarding_digest(package_id, agents_created, attachment_offset):
    block = _onboarding_block(package_id)
    if agents_created:
        return hashlib.sha256(block).hexdigest()
    anchored = (
        b"agent-harnesses:onboarding-attachment:v1\n"
        + str(attachment_offset).encode("ascii")
        + b"\n"
        + ONBOARDING_SEPARATOR
        + block
    )
    return hashlib.sha256(anchored).hexdigest()


def _onboarding_receipt(package_id, agents_created, attachment_offset):
    value = _onboarding_paths(package_id)
    value.update(
        {
            "agentsCreated": bool(agents_created),
            "blockSha256": _onboarding_digest(
                package_id,
                bool(agents_created),
                attachment_offset,
            ),
        }
    )
    return value


def _receipt(package_id, inventory, agents_created, attachment_offset):
    return {
        "schemaVersion": 2,
        "package": {"id": package_id, "version": VERSION},
        "files": [{"path": path, "sha256": inventory[path]} for path in sorted(inventory)],
        "onboarding": _onboarding_receipt(
            package_id,
            agents_created,
            attachment_offset,
        ),
    }


def _canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _verify_runtime_files(destination, package_id):
    if not destination.is_dir() or _is_link_like(destination):
        raise InstallerFailure("E_NOT_READY", "downloaded", "The selected runtime is not installed.", "Run install --dry-run and install --apply first.")
    receipt_path = destination / RECEIPT_NAME
    if not _lexists(receipt_path) or _is_link_like(receipt_path) or not receipt_path.is_file():
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installation receipt is missing or not a real file.", "Restore the exact receipt-owned runtime bytes before retrying.")
    receipt = _load_json(
        receipt_path,
        phase="installed",
        message="The installation receipt is unreadable or invalid.",
        remediation="Restore the exact receipt-owned runtime bytes before retrying.",
    )
    if (
        not isinstance(receipt, dict)
        or set(receipt) != {"schemaVersion", "package", "files", "onboarding"}
        or type(receipt.get("schemaVersion")) is not int
        or receipt.get("schemaVersion") != 2
        or not isinstance(receipt.get("package"), dict)
        or receipt["package"] != {"id": package_id, "version": VERSION}
        or not isinstance(receipt.get("onboarding"), dict)
    ):
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installation receipt is invalid.", "Do not overwrite it; use uninstall only after restoring receipt-owned bytes.")
    onboarding = receipt["onboarding"]
    expected_onboarding_paths = _onboarding_paths(package_id)
    if (
        set(onboarding)
        != {
            "agentsCreated",
            "blockSha256",
            "operationsContract",
            "operatorGuides",
        }
        or type(onboarding.get("agentsCreated")) is not bool
        or not isinstance(onboarding.get("blockSha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", onboarding["blockSha256"])
        or onboarding.get("operationsContract")
        != expected_onboarding_paths["operationsContract"]
        or onboarding.get("operatorGuides")
        != expected_onboarding_paths["operatorGuides"]
    ):
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installation receipt is invalid.", "Do not overwrite it; use uninstall only after restoring receipt-owned bytes.")
    expected = _parse_inventory(receipt["files"], "installed")
    if set(ONBOARDING_PACKAGE_FILES) - set(expected):
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "installed",
            "The installed runtime receipt omits its operator onboarding contract.",
            "Restore the exact receipt-owned runtime bytes before retrying.",
        )
    expected_directories = set()
    for relative_text in expected:
        parent = PurePosixPath(relative_text).parent
        while parent != PurePosixPath("."):
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    observed = {}
    for path in sorted(destination.rglob("*")):
        if _is_link_like(path):
            raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "The installed runtime contains a linked entry.", "Inspect it without following links.")
        relative_text = path.relative_to(destination).as_posix()
        if path.is_file() and path != receipt_path:
            observed[path.relative_to(destination).as_posix()] = _sha256(path)
        elif path.is_dir():
            if relative_text not in expected_directories:
                raise InstallerFailure(
                    "E_CHECKSUM_MISMATCH",
                    "installed",
                    "The installed runtime contains an unreceipted directory.",
                    "Do not uninstall or overwrite it; inspect the target-local runtime.",
                )
        elif path != receipt_path:
            raise InstallerFailure(
                "E_CHECKSUM_MISMATCH",
                "installed",
                "The installed runtime contains an unreceipted special entry.",
                "Do not uninstall or overwrite it; inspect the target-local runtime.",
            )
    if observed != expected or receipt_path.read_bytes() != _canonical_bytes(receipt):
        raise InstallerFailure("E_CHECKSUM_MISMATCH", "installed", "Installed runtime bytes differ from the receipt.", "Do not overwrite or uninstall changed bytes; inspect the target-local runtime.")
    return receipt


def _verify_onboarding(target, package_id, receipt):
    state = _inspect_onboarding(
        target,
        package_id,
        phase="installed",
        required=True,
    )
    agents_created = receipt["onboarding"]["agentsCreated"]
    attachment_start = state["start"]
    if not agents_created:
        separator_start = state["start"] - len(ONBOARDING_SEPARATOR)
        if (
            separator_start < 0
            or state["data"][separator_start : state["start"]]
            != ONBOARDING_SEPARATOR
        ):
            raise InstallerFailure(
                "E_CHECKSUM_MISMATCH",
                "installed",
                "The onboarding separator differs from its exact contract.",
                "Restore the generated separator and managed AGENTS.md block before retrying.",
            )
        attachment_start = separator_start
    expected_digest = _onboarding_digest(
        package_id,
        agents_created,
        attachment_start,
    )
    if receipt["onboarding"]["blockSha256"] != expected_digest:
        raise InstallerFailure(
            "E_CHECKSUM_MISMATCH",
            "installed",
            "The onboarding receipt does not match the managed block attachment.",
            "Restore the exact receipt-owned runtime and AGENTS.md attachment before retrying.",
        )
    return state


def _publish_no_replace(source, destination):
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        if function(os.fsencode(source), os.fsencode(destination), 0x00000004) != 0:
            number = ctypes.get_errno()
            if number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(number, os.strerror(number), os.fspath(destination))
            raise OSError(number or errno.EIO, os.strerror(number or errno.EIO))
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        function = getattr(libc, "renameat2", None)
        if function is None:
            raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "Atomic no-overwrite publication is unavailable.", "Use a supported macOS, Linux, or Windows runtime.")
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        if function(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
            number = ctypes.get_errno()
            if number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(number, os.strerror(number), os.fspath(destination))
            raise OSError(number or errno.EIO, os.strerror(number or errno.EIO))
        return
    if os.name == "nt":
        os.rename(source, destination)
        return
    raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "Atomic no-overwrite publication is unavailable.", "Use a supported macOS, Linux, or Windows runtime.")


def _fsync_directory(path):
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _acquire_onboarding_lock(target):
    boundary = target / RUNTIME_RELATIVE.parts[0]
    boundary_created = False
    try:
        boundary.mkdir()
        boundary_created = True
    except FileExistsError:
        if _is_link_like(boundary) or not boundary.is_dir():
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "downloaded",
                "The target-local runtime boundary is not a real directory.",
                "Resolve the .agent-harnesses collision without overwriting it.",
            )
    lock = boundary / ONBOARDING_LOCK_NAME
    for _attempt in range(ONBOARDING_LOCK_ATTEMPTS):
        try:
            lock.mkdir()
        except FileExistsError:
            try:
                metadata = lock.lstat()
            except FileNotFoundError:
                # The previous cooperative owner released the directory
                # between mkdir's EEXIST result and this inspection.
                continue
            except OSError as error:
                raise InstallerFailure(
                    "E_INITIALIZATION_CONFLICT",
                    "downloaded",
                    "The onboarding transaction lock cannot be inspected safely.",
                    "Keep it unchanged and resolve ownership before retrying.",
                ) from error
            attributes = getattr(metadata, "st_file_attributes", 0)
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            link_like = stat.S_ISLNK(metadata.st_mode) or bool(
                reparse and attributes & reparse
            )
            if link_like or not stat.S_ISDIR(metadata.st_mode):
                if boundary_created:
                    try:
                        boundary.rmdir()
                    except OSError:
                        pass
                raise InstallerFailure(
                    "E_INITIALIZATION_CONFLICT",
                    "downloaded",
                    "The onboarding transaction lock has an unsafe type.",
                    "Keep it unchanged and resolve ownership before retrying.",
                )
            time.sleep(0.01)
            continue
        return lock, boundary, boundary_created
    if boundary_created:
        try:
            boundary.rmdir()
        except OSError:
            pass
    raise InstallerFailure(
        "E_INITIALIZATION_CONFLICT",
        "downloaded",
        "Another onboarding transaction still owns this target.",
        "Wait for the active installer to finish; do not remove an unknown lock.",
    )


def _release_onboarding_lock(lock, boundary, boundary_created):
    try:
        if _lexists(lock) and not _is_link_like(lock) and lock.is_dir():
            lock.rmdir()
    finally:
        if boundary_created:
            try:
                boundary.rmdir()
            except OSError:
                pass


def _replace_agents_bytes(path, before, after, mode):
    if before is None:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        except FileExistsError as error:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "downloaded",
                "AGENTS.md changed during onboarding publication.",
                "Keep the concurrent change and retry after resolving ownership.",
            ) from error
        created_metadata = os.fstat(descriptor)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(after)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                current_metadata = path.lstat()
                if (
                    stat.S_ISREG(current_metadata.st_mode)
                    and current_metadata.st_dev == created_metadata.st_dev
                    and current_metadata.st_ino == created_metadata.st_ino
                ):
                    path.unlink()
            except OSError:
                pass
            raise
        _fsync_directory(path.parent)
        return
    if not _lexists(path) or _is_link_like(path) or not path.is_file():
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "downloaded",
            "AGENTS.md changed type during onboarding publication.",
            "Keep the concurrent change and retry after resolving ownership.",
        )
    try:
        current = path.read_bytes()
    except OSError as error:
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "downloaded",
            "AGENTS.md changed during onboarding publication.",
            "Keep it unchanged and retry after resolving ownership.",
        ) from error
    if current != before:
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "downloaded",
            "AGENTS.md changed during onboarding publication.",
            "Keep the concurrent change and retry after resolving ownership.",
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".agent-harnesses-agents-",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(after)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if _is_link_like(path) or not path.is_file() or path.read_bytes() != before:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "downloaded",
                "AGENTS.md changed during onboarding publication.",
                "Keep the concurrent change and retry after resolving ownership.",
            )
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _onboarding_plan(target, package_id):
    state = _inspect_onboarding(target, package_id)
    if state["packageId"] == package_id:
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "downloaded",
            "AGENTS.md contains an unreceipted onboarding block.",
            "Keep it unchanged and resolve its ownership before installing this runtime.",
        )
    before = state["data"] if state["exists"] else None
    attachment = _onboarding_block(package_id)
    if state["exists"]:
        attachment = ONBOARDING_SEPARATOR + attachment
    return {
        "path": state["path"],
        "before": before,
        "after": (before or b"") + attachment,
        "mode": state["mode"],
        "changed": True,
        "agentsCreated": not state["exists"],
        "attachmentStart": len(before or b""),
    }


def _restore_agents_plan(plan):
    if not plan["changed"]:
        return
    path = plan["path"]
    if plan["before"] is None:
        if not _lexists(path):
            return
        if _is_link_like(path) or not path.is_file() or path.read_bytes() != plan["after"]:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "downloaded",
                "AGENTS.md changed while the failed install was rolling back.",
                "Inspect the target without overwriting the concurrent change.",
            )
        path.unlink()
        _fsync_directory(path.parent)
        return
    _replace_agents_bytes(
        path,
        plan["after"],
        plan["before"],
        plan["mode"],
    )


def _copy_install(source_root, inventory, destination, package_id):
    expected = _validate_inventory(source_root, inventory)
    target = destination.parents[3]
    package = next(item for item in PRODUCT["packages"] if item["id"] == package_id)
    _doctor(package, target)
    if _lexists(destination):
        receipt = _verify_runtime_files(destination, package_id)
        _verify_onboarding(target, package_id, receipt)
        return "unchanged"
    lock, boundary, boundary_created = _acquire_onboarding_lock(target)
    runtime_root = destination.parents[2]
    created = []
    stage = runtime_root / (".install-%s-%s" % (package_id, uuid.uuid4().hex))
    stage_created = False
    onboarding_applied = False
    committed = False
    plan = None
    try:
        _doctor(package, target)
        if _lexists(destination):
            receipt = _verify_runtime_files(destination, package_id)
            _verify_onboarding(target, package_id, receipt)
            return "unchanged"
        plan = _onboarding_plan(target, package_id)
        current = destination.parent
        missing = []
        while not _lexists(current):
            missing.append(current)
            current = current.parent
        if _is_link_like(current) or not current.is_dir():
            raise InstallerFailure("E_INITIALIZATION_CONFLICT", "downloaded", "The runtime boundary contains an unsafe component.", "Resolve the collision without overwriting it.")
        for path in reversed(missing):
            try:
                path.mkdir()
            except FileExistsError:
                if _is_link_like(path) or not path.is_dir():
                    raise InstallerFailure(
                        "E_INITIALIZATION_CONFLICT",
                        "downloaded",
                        "A concurrent runtime parent has an unsafe type.",
                        "Keep it unchanged and retry only after resolving the collision.",
                    )
            else:
                created.append(path)
        stage.mkdir()
        stage_created = True
        for relative_text in sorted(expected):
            relative = Path(*PurePosixPath(relative_text).parts)
            file_target = stage / relative
            file_target.parent.mkdir(parents=True, exist_ok=True)
            with (source_root / relative).open("rb") as source, file_target.open("xb") as output:
                shutil.copyfileobj(source, output)
        (stage / RECEIPT_NAME).write_bytes(
            _canonical_bytes(
                _receipt(
                    package_id,
                    expected,
                    plan["agentsCreated"],
                    plan["attachmentStart"],
                )
            )
        )
        _verify_runtime_files(stage, package_id)
        if plan["changed"]:
            _replace_agents_bytes(
                plan["path"],
                plan["before"],
                plan["after"],
                plan["mode"],
            )
            onboarding_applied = True
        try:
            _publish_no_replace(stage, destination)
            committed = True
        except FileExistsError:
            receipt = _verify_runtime_files(destination, package_id)
            _verify_onboarding(target, package_id, receipt)
            shutil.rmtree(stage)
            committed = True
            return "unchanged"
    except BaseException:
        if onboarding_applied and not committed:
            _restore_agents_plan(plan)
        if stage_created and stage.exists() and not _is_link_like(stage):
            shutil.rmtree(stage, ignore_errors=True)
        for path in reversed(created):
            try:
                path.rmdir()
            except OSError:
                pass
        raise
    finally:
        _release_onboarding_lock(lock, boundary, boundary_created)
    return "installed"


def _runtime_command(package_id, destination, target):
    python = sys.executable
    if package_id == "project-harness":
        return [python, "-B", str(destination / "project_harness.py"), "verify", "--root", str(target)]
    if package_id == "workspace-coordination":
        return [python, "-B", str(destination / "workspace_coordination.py"), "--root", str(target), "verify"]
    if package_id == "cross-project":
        return [python, "-B", str(destination / "scripts/cross_project.py"), "hq-sync", "--root", str(target)]
    return [python, "-B", str(destination / "hq.py"), "--root", str(target), "--json", "hq-sync"]


def _verify_ready(package, target):
    destination = _runtime_destination(target, package["id"])
    receipt = _verify_runtime_files(destination, package["id"])
    _verify_onboarding(target, package["id"], receipt)
    marker_ids = _marker_ids(target)
    if not marker_ids:
        raise InstallerFailure(
            "E_NOT_READY",
            "installed",
            "The runtime is installed, but the target is uninitialized.",
            "Follow the selected package README initialization dry-run/apply steps, then run verify again.",
        )
    if marker_ids != [package["id"]]:
        raise InstallerFailure("E_HARNESS_MISMATCH", "initialized", "The target marker does not match the installed runtime.", "Keep the target unchanged and select its existing harness.")
    environment = os.environ.copy()
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    process = subprocess.run(_runtime_command(package["id"], destination, target), check=False, capture_output=True, env=environment)
    if process.returncode != 0:
        raise InstallerFailure(
            "E_NOT_READY",
            "initialized",
            "The target is initialized, but operational verification failed.",
            "Run the selected runtime verifier directly and resolve its bounded findings; do not claim installation success.",
        )
    return _result("OK", "ready", "The runtime is installed and the initialized target passed operational verification.", ready=True)


def _onboarding_removal_plan(target, package_id, receipt):
    state = _verify_onboarding(target, package_id, receipt)
    before = state["data"]
    start = state["start"]
    if not receipt["onboarding"]["agentsCreated"]:
        start -= len(ONBOARDING_SEPARATOR)
    after = before[:start] + before[state["end"] :]
    return {
        "path": state["path"],
        "before": before,
        "after": after,
        "mode": state["mode"],
        "delete": bool(receipt["onboarding"]["agentsCreated"] and state["exclusive"]),
    }


def _apply_onboarding_removal(plan):
    path = plan["path"]
    if plan["delete"]:
        if _is_link_like(path) or not path.is_file() or path.read_bytes() != plan["before"]:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "installed",
                "AGENTS.md changed during uninstall.",
                "Keep the concurrent change and retry after resolving ownership.",
            )
        path.unlink()
        _fsync_directory(path.parent)
        return
    _replace_agents_bytes(
        path,
        plan["before"],
        plan["after"],
        plan["mode"],
    )


def _restore_onboarding_removal(plan):
    path = plan["path"]
    if not _lexists(path):
        if not plan["delete"]:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "installed",
                "AGENTS.md disappeared while uninstall was rolling back.",
                "Inspect the target without overwriting concurrent changes.",
            )
        _replace_agents_bytes(
            path,
            None,
            plan["before"],
            plan["mode"],
        )
        return
    if _is_link_like(path) or not path.is_file():
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "installed",
            "AGENTS.md changed type while uninstall was rolling back.",
            "Inspect the target without overwriting concurrent changes.",
        )
    current = path.read_bytes()
    if current == plan["before"]:
        return
    if current != plan["after"]:
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "installed",
            "AGENTS.md changed while uninstall was rolling back.",
            "Inspect the target without overwriting concurrent changes.",
        )
    _replace_agents_bytes(
        path,
        plan["after"],
        plan["before"],
        plan["mode"],
    )


def _remove_owned_tree(root):
    if not _lexists(root):
        return
    if _is_link_like(root) or not root.is_dir():
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "installed",
            "An installer-owned cleanup path changed type.",
            "Keep it unchanged and inspect the target-local runtime boundary.",
        )
    entries = sorted(
        root.rglob("*"),
        key=lambda path: (len(path.relative_to(root).parts), path.as_posix()),
        reverse=True,
    )
    for path in entries:
        if not _lexists(path):
            continue
        if _is_link_like(path):
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "installed",
                "An installer-owned cleanup entry changed type.",
                "Keep it unchanged and inspect the target-local runtime boundary.",
            )
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            path.rmdir()
        elif stat.S_ISREG(metadata.st_mode):
            path.unlink()
        else:
            raise InstallerFailure(
                "E_INITIALIZATION_CONFLICT",
                "installed",
                "An installer-owned cleanup entry has an unsafe type.",
                "Keep it unchanged and inspect the target-local runtime boundary.",
            )
    root.rmdir()


def _copy_runtime_tree(source, destination, package_id):
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    _verify_runtime_files(destination, package_id)


def _restore_runtime_backup(backup, destination, package_id):
    if _lexists(destination):
        raise InstallerFailure(
            "E_INITIALIZATION_CONFLICT",
            "installed",
            "The runtime destination changed while uninstall was rolling back.",
            "Keep both paths unchanged and inspect ownership.",
        )
    stage = destination.parent / (".restore-%s-%s" % (VERSION, uuid.uuid4().hex))
    try:
        _copy_runtime_tree(backup, stage, package_id)
        _publish_no_replace(stage, destination)
    finally:
        if _lexists(stage):
            _remove_owned_tree(stage)


def _uninstall(package, target, apply):
    destination = _runtime_destination(target, package["id"])
    receipt = _verify_runtime_files(destination, package["id"])
    _verify_onboarding(target, package["id"], receipt)
    if not apply:
        return _result("OK", "installed", "Uninstall dry-run passed; only the exact onboarding block and receipt-owned unchanged runtime bytes would be removed.", ready=False)
    lock, boundary, boundary_created = _acquire_onboarding_lock(target)
    quarantine = destination.parent / (".remove-%s-%s" % (VERSION, uuid.uuid4().hex))
    backup_parent = None
    backup = None
    quarantined = False
    removal = None
    removal_applied = False
    try:
        receipt = _verify_runtime_files(destination, package["id"])
        removal = _onboarding_removal_plan(target, package["id"], receipt)
        backup_parent = Path(
            tempfile.mkdtemp(prefix="agent-harnesses-uninstall-rollback-")
        )
        backup = backup_parent / "runtime"
        _copy_runtime_tree(destination, backup, package["id"])
        _publish_no_replace(destination, quarantine)
        quarantined = True
        _apply_onboarding_removal(removal)
        removal_applied = True
        _remove_owned_tree(quarantine)
        quarantined = False
    except BaseException:
        if removal_applied and removal is not None:
            _restore_onboarding_removal(removal)
        if quarantined and not _lexists(destination) and backup is not None:
            _restore_runtime_backup(backup, destination, package["id"])
        if quarantined and _lexists(quarantine):
            _remove_owned_tree(quarantine)
            quarantined = False
        raise
    finally:
        try:
            if backup_parent is not None and _lexists(backup_parent):
                _remove_owned_tree(backup_parent)
        finally:
            _release_onboarding_lock(lock, boundary, boundary_created)
    for parent in (destination.parent, destination.parents[1], destination.parents[2]):
        try:
            parent.rmdir()
        except OSError:
            break
    return _result("OK", "downloaded", "The exact onboarding block and receipt-owned runtime were removed; initialized target files were left untouched.", ready=False)


def _parser():
    parser = argparse.ArgumentParser(description="Install one Agent Harness runtime into one explicit target.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "verify"):
        command = commands.add_parser(name)
        command.add_argument("selector")
        command.add_argument("--target", required=True)
        command.add_argument("--json", action="store_true")
    install = commands.add_parser("install")
    install.add_argument("selector")
    install.add_argument("--target", required=True)
    mode = install.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    install.add_argument("--json", action="store_true")
    uninstall = commands.add_parser("uninstall")
    uninstall.add_argument("selector")
    uninstall.add_argument("--target", required=True)
    mode = uninstall.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    uninstall.add_argument("--json", action="store_true")
    return parser


def _render(result, as_json):
    if as_json:
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    prefix = "READY" if result["ready"] else ("PASS" if result["code"] == "OK" else "STOP")
    text = "%s [%s] %s" % (prefix, result["code"], result["message"])
    if result["remediation"]:
        text += " " + result["remediation"]
    return text


def main(argv=None):
    arguments_list = list(sys.argv[1:] if argv is None else argv)
    wants_json = "--json" in arguments_list
    if sys.version_info < (3, 10):
        result = _result("E_PYTHON_UNSUPPORTED", "downloaded", "Python 3.10 or newer is required.", "Use a Python 3.10+ executable available to the user or system; do not use a private Codex runtime.")
        print(_render(result, wants_json))
        return 2
    arguments = _parser().parse_args(arguments_list)
    package = None
    try:
        package = _package_for_selector(arguments.selector)
        target = _safe_existing_directory(arguments.target)
        if arguments.command == "uninstall":
            result = _uninstall(package, target, arguments.apply)
        else:
            doctor = _doctor(package, target)
        if arguments.command == "doctor":
            result = doctor
        elif arguments.command == "verify":
            result = _verify_ready(package, target)
        elif arguments.command == "uninstall":
            pass
        elif not arguments.apply:
            destination = _runtime_destination(target, package["id"])
            source = _local_source(package["id"])
            if source is None:
                with tempfile.TemporaryDirectory(prefix="agent-harnesses-") as directory:
                    source = _download_source(package, Path(directory))
                    _validate_inventory(source[0], source[1])
            else:
                _validate_inventory(source[0], source[1])
            if _lexists(destination):
                receipt = _verify_runtime_files(destination, package["id"])
                _verify_onboarding(target, package["id"], receipt)
                message = "Install dry-run passed; source inventory, target-local onboarding, and the exact installed runtime are verified."
            else:
                message = "Install dry-run passed; source inventory is verified and the selected runtime plus target-local onboarding block can be installed without initializing the target."
            result = _result("OK", "downloaded", message, ready=False)
        else:
            source = _local_source(package["id"])
            if source is None:
                with tempfile.TemporaryDirectory(prefix="agent-harnesses-") as directory:
                    source = _download_source(package, Path(directory))
                    action = _copy_install(source[0], source[1], _runtime_destination(target, package["id"]), package["id"])
            else:
                action = _copy_install(source[0], source[1], _runtime_destination(target, package["id"]), package["id"])
            result = _result("OK", "installed", "The selected runtime is %s; the target still requires operational initialization and verify." % action, "Follow the selected package README. Do not report ready until verify returns ready=true.", ready=False)
    except InstallerFailure as error:
        result = error.result
    except (OSError, ValueError, zipfile.BadZipFile):
        result = _result("E_INITIALIZATION_CONFLICT", "downloaded", "The operation failed safely without overwriting target content.", "Inspect the target-local runtime boundary and retry from a clean immutable bundle.")
    if package is not None:
        result = _with_onboarding(result, package["id"])
    print(_render(result, arguments.json))
    return 0 if result["code"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
