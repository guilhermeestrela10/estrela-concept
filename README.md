<<<<<<< HEAD

# Estrela Concept

Loja responsiva da Estrela Concept com catálogo, filtros, sacola, registro de pedidos e painel administrativo. O pagamento, a entrega e as dúvidas são combinados pelo WhatsApp **+55 86 99926-9836**. Os produtos atuais são exemplos para teste.

## Abrir no navegador

1. Instale Python 3.10 ou superior.
2. Na pasta do projeto, execute `python server.py`.
3. A loja abre em <http://127.0.0.1:8000>.
4. O painel abre em <http://127.0.0.1:8000/admin>.

Deixe o terminal com o servidor aberto enquanto usa as telas. Para encerrar, volte ao terminal e pressione `Ctrl+C`. O navegador precisa de internet para carregar as fotos de demonstração e fontes externas.

Na primeira visita ao painel, crie o acesso administrativo. O usuário vem preenchido como `login-admin`; informe e confirme uma senha com pelo menos 12 caracteres. A senha é guardada como hash no banco local, não como texto. As sessões expiram após 8 horas. Depois, use **Sair** para encerrar a sessão.

## Supabase

O banco está configurado no projeto `khxfjydzpltqgtuuagrm` (`https://khxfjydzpltqgtuuagrm.supabase.co`) com catálogo, estoque, pedidos, RLS e checkout transacional. A função `estrela-api` usa a chave secreta fornecida pelo ambiente Supabase e valida chamadas do servidor. A chave secreta não é colocada no navegador nem precisa ser digitada.

O servidor local usa um token aleatório privado em `%LOCALAPPDATA%\Estrela Concept\edge_api.key`; o Supabase guarda somente seu hash. No painel, **SUPABASE ONLINE** confirma a conexão. O login do painel continua usando hash local em `data/estrela.sqlite3`. Para mover o app para outra hospedagem, será preciso copiar o token privado de forma segura, configurar o banco local de autenticação (ou substituí-lo por Supabase Auth) e revisar sessões para múltiplas instâncias.

## O que dá para analisar

- **Loja:** busca, categorias, tamanho, faixa de preço, detalhes, variações e sacola.
- **Pedido:** nome e WhatsApp, conferência de estoque, número do pedido e link para negociar pagamento e entrega pelo WhatsApp. Nenhum pagamento é cobrado no site.
- **Painel:** resumo, pedidos e status, cadastro e edição de produtos, visibilidade, variações e estoque, criação de categorias.
- **Dados:** produtos, categorias, estoque e pedidos ficam no Supabase; o hash do login administrativo fica no SQLite local. O painel mostra qual banco está ativo. Os produtos de exemplo são editáveis.
- **WhatsApp da marca:** +55 86 99926-9836.

Para abrir o banco em outra pasta, defina `ESTRELA_DB_PATH` antes de iniciar o servidor. Exemplo no PowerShell: `$env:ESTRELA_DB_PATH = "$PWD\data-teste\loja.sqlite3"; python server.py`.

## Testes

Na pasta do projeto, execute `python -m unittest discover -s tests -v`. Os testes cobrem checkout, cadastro, estoque, categorias, pedidos, cancelamento e resumo do painel.

## Estrutura

- `server.py`: servidor HTTP local e endpoints da loja e do painel.
- `store.py`: persistência SQLite, validação de catálogo, estoque e pedidos.
- `catalog.py`: dados fictícios que iniciam uma base vazia.
- `supabase/schema.sql`, `supabase/functions/estrela-api/`: esquema e API segura da loja no Supabase.
- `index.html`, `static/app.js`, `static/styles.css`: vitrine e carrinho.
- `admin.html`, `static/admin.js`: administração e dashboard.
- `tests/`: testes automáticos e fixture de carrinho.

## Antes da publicação

O app está conectado ao Supabase nesta máquina, mas a URL atual é um túnel temporário de demonstração e depende deste computador ligado. Para publicação permanente ainda faltam hospedagem, domínio, backups e migrar a autenticação do painel para uma solução hospedada. Pagamento, frete e entrega são combinados pelo WhatsApp; nenhum pagamento é cobrado no site.

# Troque produtos, fotos, estoque e conteúdo pelos dados aprovados pela loja. Preencha os dados legais e operacionais: identificação do fornecedor, endereço e contato, política de privacidade, regras de entrega e informações de troca/devolução. As regras devem refletir a operação real e ser revisadas com orientação adequada; o texto do site não substitui revisão jurídica.

# estrela-concept

Sistema de gerenciamento de loja de roupas

> > > > > > > origin/main
