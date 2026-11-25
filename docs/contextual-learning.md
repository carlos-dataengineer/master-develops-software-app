# Memória contextual

A equipe lembra, entre sessões, preferências confirmadas do operador e conhecimentos de cada projeto (convenções, decisões de arquitetura, causas raiz de bugs). É uma **memória externa local**, não treinamento do modelo.

| Pergunta | Resposta |
|---|---|
| Onde fica? | Windows `%LOCALAPPDATA%\MasterDevelops\Memory`, macOS `~/Library/Application Support/MasterDevelops/Memory`, Linux `~/.local/share/masterdev/memory`. Mude com `MASTERDEV_MEMORY_HOME`. |
| Vai para o repositório? | Não. O script recusa gravar dentro do projeto ativo. |
| Projetos se misturam? | Não. Cada projeto tem uma chave própria; o `recall` só traz memórias do projeto atual e do operador. |
| Quem grava? | Só o coordenador, com resumos curtos e sanitizados. Os agentes recebem apenas o que o coordenador passar. |
| Inferências viram regra? | Não. Ficam como `candidate` até você confirmar. |
| Guarda segredo? | Não deve. O script bloqueia formatos comuns de credencial, mas não é um DLP completo. |
| Como apagar? | `contextual_memory.py forget <id> --yes`, `forget-project --project-root <pasta> --yes` ou apagar a pasta. |

Comandos e regras completas: [`CONTEXTUAL-LEARNING.md`](../masterdev/skills/masterdev/references/CONTEXTUAL-LEARNING.md).
