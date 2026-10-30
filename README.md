# Estrela Concept

Loja online da Estrela Concept, com catálogo, busca, filtros, sacola, registro de pedidos e painel administrativo. Pagamento, entrega, trocas, devoluções e dúvidas são combinados pelo WhatsApp **+55 86 99926-9836** com **Livya De Araújo Macedo Estrela**. Os cinco produtos atuais são exemplos editáveis.

## Executar localmente

1. Instale Python 3.10 ou superior.
2. Na pasta do projeto, execute `python server.py`.
3. Abra `http://127.0.0.1:8000` para a loja ou `http://127.0.0.1:8000/admin` para o painel.

O servidor precisa ficar aberto enquanto você usa o site. As imagens e fontes de demonstração precisam de internet.

## Dados e autenticação

- Produtos, categorias, estoque, pedidos, conta administrativa e sessões do painel ficam no Supabase do projeto `khxfjydzpltqgtuuagrm`.
- A conta administrativa usa Supabase Auth. O painel aceita o usuário `login-admin`; a senha não é salva neste repositório.
- O Auth usa um endereço técnico sem caixa postal para manter o login por usuário; antes de publicar, cadastrar um e-mail real para recuperação de acesso.
- Tokens de sessão são gerados aleatoriamente, enviados em cookie `HttpOnly` e salvos somente como hash na tabela privada pela RLS `admin_sessions`.
- A tabela `admin_accounts`, sessões, pedidos e chaves internas não concedem leitura ao `anon` nem a `authenticated`. A Edge Function usa a chave secreta apenas no servidor.
- Checkout, catálogo e administração passam pela Edge Function `estrela-api`; o RPC de checkout só pode ser chamado pela função com acesso de serviço.
- Neste computador, o token privado que autoriza o servidor está em `%LOCALAPPDATA%\Estrela Concept\edge_api.key`. Em outra hospedagem, configure-o como variável de ambiente `ESTRELA_EDGE_API_TOKEN`; nunca publique esse valor.
- Se o token não estiver configurado, as rotas de dados param com uma mensagem de erro; o servidor não grava pedidos ou produtos em um banco local por engano. A classe SQLite é usada apenas pelos testes.

## Fluxo do pedido

O site valida estoque e registra o pedido no Supabase. Depois, o cliente pode abrir o WhatsApp para combinar pagamento e entrega. Não há cobrança online. O contato também atende dúvidas sobre produtos, trocas e devoluções.

## Testes

Execute `python -m unittest discover -s tests -v` na pasta do projeto. Os testes usam SQLite temporário e cobrem pedidos, estoque, categorias e painel.

## Estrutura

- `server.py`: HTTP local, rotas da loja e sessão do painel.
- `store.py`: integração com Supabase e SQLite usado pelos testes locais.
- `catalog.py`: dados de exemplo para testes.
- `supabase/schema.sql`: esquema, RLS e permissões.
- `supabase/functions/estrela-api/`: API protegida para catálogo, pedidos e administração.
- `index.html`, `static/app.js`, `static/styles.css`: loja.
- `admin.html`, `static/admin.js`: painel.
- `tests/`: testes automáticos.

## Etapa final antes da publicação

Faltam cadastrar os produtos reais, contratar/configurar domínio e hospedagem, adicionar as informações e políticas definitivas, configurar backups na hospedagem e fazer testes de ponta a ponta no endereço final e em celulares reais.

**Lembrete solicitado:** quando esses itens estiverem concluídos, lembrar Livya de revisar segurança, backups, políticas e testes finais antes de divulgar a loja.
