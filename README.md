# Estrela Concept

Loja demonstrativa responsiva para a Estrela Concept, com catálogo, filtros, carrinho, registro simulado de pedidos e painel administrativo local. Os produtos iniciais são fictícios. O visual usa a referência enviada: rosa, branco, preto e a estrela da marca.

## Abrir no navegador

1. Instale Python 3.10 ou superior.
2. Na pasta do projeto, execute `python server.py`.
3. A loja abre em <http://127.0.0.1:8000>.
4. O painel abre em <http://127.0.0.1:8000/admin>.

Deixe o terminal com o servidor aberto enquanto usa as telas. Para encerrar, volte ao terminal e pressione `Ctrl+C`. O navegador precisa de internet para carregar as fotos de demonstração e fontes externas.

Na primeira visita ao painel, crie o acesso administrativo. O usuário vem preenchido como `login-admin`; informe e confirme uma senha com pelo menos 12 caracteres. A senha é guardada como hash no banco local, não como texto. As sessões expiram após 8 horas. Depois, use **Sair** para encerrar a sessão.

## O que dá para analisar

- **Loja:** busca, categorias, tamanho, faixa de preço, detalhes, variações e sacola.
- **Pedido:** nome e WhatsApp, conferência de estoque, registro local, número do pedido e link para negociar pagamento e entrega pelo WhatsApp. Nenhum pagamento é cobrado no site.
- **Painel:** resumo, pedidos e status, cadastro e edição de produtos, visibilidade, variações e estoque, criação de categorias.
- **Dados:** SQLite em `data/estrela.sqlite3`, criado automaticamente na primeira execução. Os produtos de exemplo são copiados do catálogo inicial apenas quando o banco é criado. Alterações posteriores ficam salvas no banco.
- **WhatsApp da marca:** +55 86 99926-9836.

Para abrir o banco em outra pasta, defina `ESTRELA_DB_PATH` antes de iniciar o servidor. Exemplo no PowerShell: `$env:ESTRELA_DB_PATH = "$PWD\data-teste\loja.sqlite3"; python server.py`.

## Testes

Na pasta do projeto, execute `python -m unittest discover -s tests -v`. Os testes cobrem checkout, cadastro, estoque, categorias, pedidos, cancelamento e resumo do painel.

Para testar dados antigos do carrinho, abra `http://127.0.0.1:8000/tests/seed_cart.html?case=malformed` ou `http://127.0.0.1:8000/tests/seed_cart.html?case=removed`.

## Estrutura

- `server.py`: servidor HTTP local e endpoints da loja e do painel.
- `store.py`: persistência SQLite, validação de catálogo, estoque e pedidos.
- `catalog.py`: dados fictícios que iniciam uma base vazia.
- `index.html`, `static/app.js`, `static/styles.css`: vitrine e carrinho.
- `admin.html`, `static/admin.js`: administração e dashboard.
- `tests/`: testes automáticos e fixture de carrinho.

## Limites antes de vender de verdade

Este projeto ainda é uma demonstração local. Não há conexão ativa com Supabase, implantação pública, domínio, HTTPS, backup automático, pagamento ou cálculo de frete. Pedidos, pagamento, entrega e dúvidas são encaminhados ao WhatsApp da loja. O servidor só escuta em `127.0.0.1` por padrão; qualquer hospedagem precisa de configuração própria e banco persistente. Antes de publicar, configure a conta do painel localmente. Se a criação inicial precisar ser feita remotamente, use `ESTRELA_ADMIN_SETUP_TOKEN` como segredo e remova-o depois de criar o usuário. Para hospedar o servidor, configure `HOST=0.0.0.0` e `PORT` conforme a plataforma. A autenticação deve ser reavaliada com HTTPS e armazenamento de sessões compartilhado antes de permitir acesso público.

Troque produtos, fotos, estoque e conteúdo pelos dados aprovados pela loja. Preencha os dados legais e operacionais: identificação do fornecedor, endereço e contato, política de privacidade, regras de entrega e informações de troca/devolução. As regras devem refletir a operação real e ser revisadas com orientação adequada; o texto do site não substitui revisão jurídica.
