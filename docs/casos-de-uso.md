# Casos de uso

Exemplos de pedidos e de como a equipe responde. Os nomes de projetos são fictícios.

## 1. Criar um app do zero (web + mobile)

> `/masterdev` → **1. Construir** → "Quero um app para clínicas pequenas: pacientes agendam pelo celular e a recepção gerencia a agenda no computador."

- **Descoberta:** o `product-manager` define MVP (agendar, remarcar, lembrete) e o que fica fora (pagamento). O `ux-ui-designer` desenha a jornada e as telas com todos os estados. O `data-engineer` mapeia entidades, eventos de analytics e dados pessoais.
- **Arquitetura:** o `software-architect` propõe monólito modular + app Expo e registra os ADRs; o `database-engineer` modela o esquema; o `security-engineer` faz a modelagem de ameaças e o plano LGPD.
- **Construção em paralelo:** frontend, mobile e backend em arquivos separados, cada um esperando o contrato de que depende; `devops-sre-engineer` monta CI e preview.
- **Qualidade e revisão:** testes, Web Vitals, varredura de segurança, duas revisões independentes; achados corrigidos.
- **Entrega:** README, como rodar, decisões, validações reais e pendências.

É exatamente a missão da demonstração do painel (tecla **D**).

## 2. Adicionar uma funcionalidade a um produto existente

> `/masterdev` → **2. Evoluir** → "Adicionar exportação de relatórios em CSV no painel administrativo."

O coordenador lê a estrutura e as convenções, o arquiteto encontra onde a mudança mora e o que ela atinge, o backend cria o endpoint (com paginação e autorização), o frontend o botão e os estados, o QA os testes e os revisores conferem.

## 3. Revisar um pull request

> `/masterdev` → **3. Revisar** → "Revise o PR da nova tela de login."

Os dois revisores rodam em paralelo; o `security-engineer` entra por ser autenticação. Achados aparecem no painel com severidade, arquivo:linha e status. O código não é alterado sem pedido explícito.

## 4. Investigar um bug

> `/masterdev` → **4. Depurar** → "No Android, a lista de pedidos fica vazia depois de voltar do segundo plano."

O coordenador pede os passos e o ambiente, o `mobile-engineer` reproduz, encontra a causa raiz (ex.: estado perdido no ciclo de vida), o `qa-test-engineer` cria o teste de regressão, os revisores conferem a correção.

## 5. Recurso de IA dentro do produto

> "Quero que o suporte sugira respostas automáticas usando o histórico de tickets."

O `data-scientist` define métrica de sucesso, linha de base, conjunto de avaliação e riscos (injeção de prompt, dados pessoais); o `software-architect` e o `backend-engineer` integram; o `security-engineer` revisa o tratamento dos dados.

## 6. Entender a estrutura de dados de um sistema

> "Explique como os dados fluem neste app e o que é dado pessoal."

O `data-engineer` produz o dicionário de dados, a linhagem e a classificação de sensibilidade; o `database-engineer` aponta índices e riscos de consulta.

## 7. Acompanhar no telão do time

Abra o painel, tecle **F** (modo TV) e **N** (avisos). Bloqueios, gates reprovados e achados graves aparecem na faixa "Precisa de atenção" e como aviso do navegador.
