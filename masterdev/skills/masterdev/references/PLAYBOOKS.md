# Playbooks da equipe

Cada playbook lista as etapas na ordem. Registre no painel a etapa ao entrar nela (`team_board.py stage <etapa>`). Convoque só os especialistas que a tarefa pede; os nomes abaixo são sugestões, não obrigação.

## 1. Construir do zero

**Descoberta** (`product-manager`, `ux-ui-designer`, `data-engineer` quando houver dados relevantes)
1. Entenda o problema, o público, o resultado esperado e como será usado (web, iOS, Android, desktop, API).
2. Defina o MVP, o que fica fora e os critérios de aceite. Pergunte o que bloqueia: plataforma, autenticação, dados existentes, integrações, hospedagem preferida, orçamento, prazo, idioma, requisitos legais.
3. Recupere memórias do projeto/operador.

**Arquitetura** (`software-architect`, `ux-ui-designer`, `database-engineer`, `security-engineer`)
4. Escolha a stack mais simples e madura para as plataformas; registre em ADR.
5. Modele domínio e dados (entidades, estados, relacionamentos) e os contratos (API, eventos, erros).
6. Desenhe fluxos e telas com todos os estados e o design system mínimo.
7. Faça a modelagem de ameaças curta e o plano de dados pessoais.

**Plano**
8. Quebre em unidades pequenas e verificáveis, com donos e arquivos exclusivos. Registre as tarefas com dependências (`--after`).
9. Apresente ao operador um resumo enxuto (stack, telas, entidades, ordem) e siga quando não houver bloqueio.

**Construção** (`frontend-engineer`, `mobile-engineer`, `backend-engineer`, `database-engineer`, `data-engineer`, `data-scientist`, `devops-sre-engineer`)
10. Esqueleto que roda ponta a ponta primeiro (walking skeleton), depois as funcionalidades em ordem de valor.
11. Cada unidade termina com build e testes passando.
12. CI, variáveis de ambiente de exemplo (`.env.example` sem segredos), scripts de execução e seeds fictícios.

**Qualidade** (`qa-test-engineer`, `performance-engineer`, `security-engineer`)
13. Testes de unidade, integração e ponta a ponta dos fluxos críticos. Acessibilidade, desempenho básico e varredura de segurança/dependências. Registre cada gate.

**Revisão** (`code-correctness-reviewer`, `code-maintainability-reviewer`, em paralelo)
14. Revisões independentes sobre o código completo. Corrija os achados críticos e altos; registre os demais.

**Ataque e blindagem** (`offensive-security-tester`, depois `security-hardening-engineer`)
15. Com o alvo autorizado (local ou de testes), o ataque explora o software como um invasor e prova cada vulnerabilidade; a blindagem corrige na causa raiz, adiciona proteções e testes de regressão de segurança; o ataque faz o reteste. Veja "Ataque e blindagem" no `SKILL.md`.

**Entrega** (`technical-writer`)
16. README com instalação, execução, configuração e arquitetura; CHANGELOG. Rode o app e mostre a evidência. Resposta final obrigatória.

## 2. Evoluir um produto existente

1. **Descoberta:** leia README, estrutura, stack, convenções, testes e histórico recente. Entenda a funcionalidade pedida e os critérios de aceite.
2. **Arquitetura:** encontre onde a mudança deve morar e tudo que ela atinge (chamadores, contratos, migrations, testes, documentação, apps clientes). Se o novo requisito não cabe no desenho atual, redesenhe a parte afetada em vez de empilhar exceções. ADR quando a decisão for relevante.
3. **Plano:** remova primeiro o que ficou obsoleto; depois construa sobre a base mais simples. Divida em unidades verificáveis.
4. **Construção:** siga as convenções existentes; compatibilidade com dados e clientes já em uso; migrations reversíveis; feature flag só quando o lançamento exigir.
5. **Qualidade:** testes da funcionalidade nova e de regressão do que já existia.
6. **Revisão:** revisões independentes de corretude e manutenibilidade; segurança e performance conforme o risco.
7. **Ataque e blindagem:** ataque focado na superfície que a funcionalidade criou ou mudou, blindagem e reteste.
8. **Entrega:** documentação e changelog atualizados; resposta final.

## 3. Revisar

1. Defina o escopo: diff, pull request, módulo, app inteiro, arquitetura, segurança, acessibilidade ou performance.
2. Leia o contexto: objetivo da mudança, contratos, chamadores e consumidores fora do diff.
3. Rode as revisões independentes em paralelo (`code-correctness-reviewer`, `code-maintainability-reviewer`) e acione `security-engineer`, `performance-engineer`, `ux-ui-designer` (acessibilidade) ou `database-engineer` conforme o risco.
4. Rode o que for possível (build, testes, lint) para transformar suspeitas em evidência. Registre gates.
5. Consolide sem duplicatas. Cada achado: severidade, arquivo:linha, cenário concreto, impacto e correção sugerida. Registre no painel com `finding`.
6. Mostre primeiro o que é crítico/alto, depois o restante, o escopo verificado e o que não foi verificado.
7. Em revisões de segurança, ou quando o operador autorizar, o `offensive-security-tester` tenta explorar os achados para separar o que é explorável do que é teórico.
8. Não altere o código durante a revisão, salvo pedido explícito de correção.

## 4. Depurar

1. Peça o que falta: mensagem de erro/stack trace sanitizado, passos para reproduzir, esperado versus observado, ambiente (navegador, SO, versão do app, dispositivo), última mudança e frequência.
2. Reproduza a falha localmente ou com um teste antes de mudar código.
3. Encontre o primeiro ponto em que o estado diverge do esperado. Separe defeito de código, dados, configuração, dependência, ambiente, rede ou infraestrutura.
4. Verifique todos os chamadores e consumidores afetados.
5. Corrija a causa raiz com a menor mudança, no código compartilhado. Guards só quando o estado tratado é legítimo.
6. Escreva o teste de regressão que falhava antes e passa depois (`qa-test-engineer`).
7. Revisão independente da correção; relate evidência antes/depois.
8. Se o bug for de segurança (ou tocar autenticação, autorização, dados pessoais ou entradas externas), rode ataque, blindagem e reteste antes de entregar.

## Escolhendo especialistas por tipo de produto

| Produto | Núcleo sugerido |
|---|---|
| Site/app web (SPA, SSR, painel) | product-manager, ux-ui-designer, software-architect, frontend-engineer, backend-engineer, database-engineer, qa-test-engineer |
| App mobile | product-manager, ux-ui-designer, software-architect, mobile-engineer, backend-engineer, security-engineer, qa-test-engineer |
| API/serviço | software-architect, backend-engineer, database-engineer, security-engineer, qa-test-engineer, devops-sre-engineer |
| Produto com dados/analytics | data-engineer, data-scientist, database-engineer, backend-engineer |
| Recurso de IA/LLM | data-scientist, software-architect, backend-engineer, security-engineer |
| Ferramenta interna/CLI | software-architect, backend-engineer, qa-test-engineer, technical-writer |

Revisão independente (`code-correctness-reviewer` e `code-maintainability-reviewer`) entra em toda mudança de código que será entregue. Ataque e blindagem (`offensive-security-tester` e `security-hardening-engineer`) entram como fase final antes de toda entrega de software ou app.
