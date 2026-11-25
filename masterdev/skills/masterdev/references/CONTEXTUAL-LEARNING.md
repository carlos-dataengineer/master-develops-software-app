# Contextual Learning Engine — especificação operacional

## Objetivo

O Contextual Learning Engine (CLE) permite que o MasterDevelops acumule conhecimento útil sobre a forma de trabalho do operador e sobre cada projeto, preservando-o entre sessões.

O CLE **não treina o modelo, não altera seus pesos e não cria uma inteligência independente**. É uma arquitetura de memória externa: o agente identifica conhecimento útil, grava resumos estruturados em uma base local e recupera somente memórias relevantes para uma nova tarefa. O modelo continua sendo o motor de raciocínio; o CLE fornece continuidade contextual.

A equipe não observa o terminal inteiro nem captura tudo automaticamente. O coordenador registra somente informações presentes nas tarefas atendidas e que respeitam as regras de memória.

## Escopos e isolamento

A base SQLite é criada por perfil local do sistema operacional:

| Sistema | Local padrão |
|---|---|
| Windows | %LOCALAPPDATA%\MasterDevelops\Memory\masterdev-memory.sqlite3 |
| macOS | ~/Library/Application Support/MasterDevelops/Memory/masterdev-memory.sqlite3 |
| Linux | $XDG_DATA_HOME/masterdev/memory/masterdev-memory.sqlite3; fallback ~/.local/share/masterdev/memory/masterdev-memory.sqlite3 |

A variável MASTERDEV_MEMORY_HOME permite escolher outro diretório. Não use diretório dentro do repositório, modelos ou criação. O script bloqueia por padrão um armazenamento dentro do projeto ativo.

- **Operador:** preferências estáveis e gerais, que podem ser úteis em diferentes projetos.
- **Projeto:** arquitetura, schemas, contratos, regras, decisões, soluções e padrões daquele projeto.

Claude Code e Codex sob o mesmo perfil local compartilham a base do operador. Contas diferentes e máquinas diferentes têm bases independentes. Projetos têm chaves próprias derivadas do caminho normalizado da raiz; mover uma pasta pode criar uma identidade nova. Não há sincronização entre máquinas.

## O que registrar

Tipos: preference, architecture, business_rule, pattern, solution, routine, decision e correction.

Registre resumos curtos e acionáveis, com contexto mínimo, evidência e limites de validade. Exemplos: uma preferência de linguagem explicitamente confirmada; uma convenção de pastas ou de testes confirmada; uma decisão de arquitetura aprovada; a causa raiz de um bug corrigido e coberto por teste.

Não registre grandes blocos de código, tabelas inteiras ou logs brutos.

## O que não registrar

É proibido armazenar senhas, tokens, chaves, certificados, connection strings, credenciais, dados pessoais, dados de clientes, registros de produção, logs integrais, dumps ou amostras sensíveis. O script bloqueia alguns formatos comuns de credenciais, mas não é um DLP completo. O coordenador deve sanitizar e revisar o resumo antes de persistir.

## Estados

- candidate: hipótese ou padrão inferido ainda não confirmado. Não aparece no recall normal.
- accepted: conhecimento confirmado e elegível para recuperação.
- rejected: conhecimento recusado; não utilizar.
- superseded: conhecimento substituído; não utilizar.

Use accepted somente para instruções explícitas, correções explícitas, decisões aprovadas ou resultados validados por evidência. Inferências ficam em candidate. Instruções atuais, código atual e contratos confirmados prevalecem sobre memórias antigas.

## Ciclo operacional

1. A skill pergunta o modo de trabalho.
2. Após a escolha, identifica a raiz do projeto e executa status.
3. Recupera memórias aceitas do operador e do projeto atual usando recall.
4. O coordenador fornece aos subagentes somente o conhecimento necessário; subagentes não acessam a base.
5. O projeto atual é inspecionado normalmente; memória nunca substitui validação.
6. Ao final, o coordenador registra fatos confirmados e deixa inferências como candidate.
7. Se o operador pedir para não aprender, não registre. Se pedir para esquecer, execute e confirme a exclusão.

## Comandos

Todos os comandos usam Python 3.10+ e somente a biblioteca padrão.

```bash
python "<skill-dir>/scripts/contextual_memory.py" status --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" recall --query "Delta MERGE incremental" --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" remember --scope operator --kind preference --title "Estilo SQL" --content "Preferência confirmada pelo operador." --status accepted --source user_explicit
python "<skill-dir>/scripts/contextual_memory.py" list --scope all --include-candidates --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" confirm <memory-id> --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" reject <memory-id> --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" forget <memory-id> --yes --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" forget-project --yes --project-root "<project-root>"
python "<skill-dir>/scripts/contextual_memory.py" export --output "<caminho-seguro>/memory-export.json"
```

O recall não inclui candidatos. Candidatos devem ser listados e confirmados pelo operador antes de influenciar a execução.

## Privacidade e limites

- SQLite não é criptografado automaticamente. Proteja o dispositivo, a conta e o diretório local.
- O SQLite pode criar arquivos WAL/SHM; trate a pasta inteira como privada.
- O módulo não implementa rede, telemetria, sincronização ou publicação automática. Verifique se diretórios personalizados não estão em pastas sincronizadas por nuvem.
- Trechos recuperados podem ser enviados ao provedor de IA como parte do prompt. Armazenamento local não significa inferência offline.
- A busca é lexical, não usa embeddings e não garante recuperação de todo conhecimento.
- A exportação contém conhecimento contextual e deve ser criada somente quando solicitada; mantenha o arquivo protegido.
