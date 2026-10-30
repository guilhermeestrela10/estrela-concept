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

## Conectar ao Supabase

O esquema do Supabase está em `supabase/schema.sql` e já foi aplicado ao projeto `khxfjydzpltqgtuuagrm` (URL `https://khxfjydzpltqgtuuagrm.supabase.co`). O banco começa com cinco categorias e produtos fictícios para teste.

Para ativar o banco na loja deste computador:

1. No painel Supabase do projeto, abra **Project Settings → API Keys → Secret keys** e crie/copiei uma chave `sb_secret_…`.
2. Na pasta do projeto, execute `python configure_supabase.py` e cole a chave no prompt oculto. Não envie essa chave no chat, não a coloque no HTML/JavaScript e não a publique.
3. Reinicie `python server.py`. No painel, confirme o rótulo **SUPABASE ONLINE**. Se aparecer **BANCO LOCAL**, a chave não foi carregada e os cadastros ainda ficam no SQLite.

A chave fica em `%LOCALAPPDATA%\Estrela Concept\supabase.secret`, fora da pasta publicada pelo servidor. O login administrativo continua no SQLite local (`data/estrela.sqlite3`). Para produção, configure `ESTRELA_SUPABASE_URL` e `ESTRELA_SUPABASE_SECRET_KEY` como variáveis secretas do ambiente da hospedagem e use autenticação/sessões apropriadas para múltiplas instâncias.

## O que dá para analisar

- **Loja:** busca, categorias, tamanho, faixa de preço, detalhes, variações e sacola.
- **Pedido:** nome e WhatsApp, conferência de estoque, número do pedido e link para negociar pagamento e entrega pelo WhatsApp. Nenhum pagamento é cobrado no site.
- **Painel:** resumo, pedidos e status, cadastro e edição de produtos, visibilidade, variações e estoque, criação de categorias.
- **Dados:** Supabase depois de configurar a chave; caso contrário, SQLite em `data/estrela.sqlite3`. O painel mostra qual banco está ativo. Os produtos de exemplo são editáveis.
- **WhatsApp da marca:** +55 86 99926-9836.

Para abrir o banco em outra pasta, defina `ESTRELA_DB_PATH` antes de iniciar o servidor. Exemplo no PowerShell: `$env:ESTRELA_DB_PATH = "$PWD\data-teste\loja.sqlite3"; python server.py`.

## Testes

Na pasta do projeto, execute `python -m unittest discover -s tests -v`. Os testes cobrem checkout, cadastro, estoque, categorias, pedidos, cancelamento e resumo do painel.

## Estrutura

- `server.py`: servidor HTTP local e endpoints da loja e do painel.
- `store.py`: persistência SQLite, validação de catálogo, estoque e pedidos.
- `catalog.py`: dados fictícios que iniciam uma base vazia.
- `index.html`, `static/app.js`, `static/styles.css`: vitrine e carrinho.
- `admin.html`, `static/admin.js`: administração e dashboard.
- `tests/`: testes automáticos e fixture de carrinho.

## Antes da publicação

O banco está preparado no Supabase, mas a loja só se conecta depois de instalar a chave secreta na máquina/ambiente que executa o servidor. O app segue local até ser publicado. Para colocar no ar ainda faltam escolher/configurar hospedagem e domínio, ativar HTTPS, backups, e revisar autenticação para hospedagem com múltiplas instâncias. Pagamento, frete e entrega são combinados pelo WhatsApp; nenhum pagamento é cobrado no site.

# Troque produtos, fotos, estoque e conteúdo pelos dados aprovados pela loja. Preencha os dados legais e operacionais: identificação do fornecedor, endereço e contato, política de privacidade, regras de entrega e informações de troca/devolução. As regras devem refletir a operação real e ser revisadas com orientação adequada; o texto do site não substitui revisão jurídica.

# estrela-concept

Sistema de gerenciamento de loja de roupas

> > > > > > > origin/main
