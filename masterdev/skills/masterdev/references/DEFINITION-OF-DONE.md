# Definição de pronto

Use como checklist antes da etapa de entrega. Marque só o que foi verificado de verdade; o que não se aplica, diga que não se aplica.

## Produto
- [ ] Os critérios de aceite combinados foram atendidos e demonstrados.
- [ ] O que ficou fora do escopo está escrito.

## Experiência e acessibilidade
- [ ] Cada tela trata carregando, vazio, erro, sem permissão e (quando aplicável) offline.
- [ ] Navegação por teclado, foco visível, rótulos acessíveis e contraste WCAG 2.2 AA.
- [ ] Layout funciona de 320px até telas largas; no mobile, áreas seguras e fonte dinâmica.

## Código
- [ ] Segue a stack, a estrutura e as convenções do projeto.
- [ ] Sem código morto, duplicado, comentado ou abstrações sem uso.
- [ ] Chamadores, contratos, migrations, testes e documentação afetados foram atualizados.

## Segurança e privacidade
- [ ] Entradas validadas nas bordas; autorização em cada operação.
- [ ] Nenhum segredo no código, no histórico, em logs ou no cliente. `.env.example` sem valores reais.
- [ ] Dependências novas justificadas e sem vulnerabilidades conhecidas.
- [ ] Dados pessoais minimizados, com retenção e exclusão pensadas (LGPD/GDPR).

## Dados
- [ ] Esquema e migrations reversíveis e seguros para dados existentes.
- [ ] Índices para os padrões de acesso reais; sem N+1 nas rotas críticas.
- [ ] Eventos de analytics documentados e com consentimento quando necessário.

## Verificação (registre cada item como gate no painel)
- [ ] Build passa.
- [ ] Lint e verificação de tipos passam.
- [ ] Testes de unidade e integração passam (com números).
- [ ] Fluxos críticos verificados ponta a ponta ou no app rodando.
- [ ] Desempenho básico medido quando a mudança afeta caminhos críticos.

## Revisão
- [ ] Revisão independente de corretude feita; achados críticos e altos corrigidos.
- [ ] Revisão de manutenibilidade feita.

## Ataque e blindagem
- [ ] Ataque controlado feito no alvo autorizado (local ou de testes), com prova de conceito de cada vulnerabilidade.
- [ ] Vulnerabilidades críticas e altas corrigidas na causa raiz, com teste de regressão de segurança.
- [ ] Reteste confirmou que as falhas corrigidas não são mais exploráveis (gate `pentest` aprovado).
- [ ] Riscos residuais aceitos explicitamente pelo operador e listados na resposta final.

## Entrega
- [ ] README/guia atualizado com como instalar, rodar e configurar.
- [ ] CHANGELOG atualizado quando houver versão.
- [ ] Resposta final com resultado, decisões, arquivos, validações reais, pendências e riscos.
