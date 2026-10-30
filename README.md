# Estrela Concept

MVP local de uma loja de moda fitness, feito para aprender e evoluir aos poucos. A primeira versão oferece uma vitrine responsiva com dados fictícios, busca, filtros, detalhes de produto, variações de tamanho e cor, carrinho salvo no navegador e preparação de pedido com validação de preço e estoque no servidor. O pagamento e o frete são combinados fora do site, pelo WhatsApp.

## Como executar

1. Instale Python 3.10 ou superior.
2. Abra um terminal nesta pasta.
3. Execute `python server.py`.
4. Acesse `http://127.0.0.1:8000` no navegador.

O projeto usa apenas a biblioteca padrão do Python. O navegador precisa de acesso à internet para carregar as fotos de demonstração e as fontes externas.

## Verificações automatizadas

Para executar os testes do checkout, rode `python -m unittest discover -s tests -v` na pasta do projeto. Eles verificam o preço calculado pelo servidor, a rejeição de estoque excedido e a validação de quantidade.

Para testar estados antigos do carrinho no navegador, abra `http://127.0.0.1:8000/tests/seed_cart.html?case=malformed` (JSON corrompido) ou `http://127.0.0.1:8000/tests/seed_cart.html?case=removed` (produto removido). No segundo cenário, abra a sacola e remova o item indisponível.

## O que está incluído

- Página inicial com identidade visual baseada na logo compartilhada: rosa, preto, branco e símbolo de estrela.
- Catálogo fictício de leggings, tops, conjuntos, shorts e camisetas.
- Busca por nome e filtros por categoria, tamanho e faixa de preço.
- Detalhes do produto com combinações vendáveis de tamanho e cor.
- Carrinho com adicionar, remover e alterar quantidade. O navegador guarda o carrinho no `localStorage`.
- Checkout de demonstração: o servidor recalcula valores e confere o estoque antes de preparar a mensagem para WhatsApp.
- Layout adaptável para celular e computador.

## Dados de exemplo

Edite `catalog.py` para alterar produtos, preços, fotos, categorias, variações e estoque. Todas as imagens e quantidades atuais são exemplos e devem ser trocados pelos dados reais antes de publicar.

## Integração futura com Supabase

Esta primeira versão ainda não usa um projeto Supabase nem persiste pedidos. O catálogo fica em `catalog.py` e os pedidos são apenas preparados para conversa no WhatsApp. Para ligar o Supabase, será necessário criar ou escolher o projeto e configurar credenciais seguras; a chave `service_role` nunca deve ir para o navegador. A evolução natural é migrar categorias, produtos, imagens e variações para tabelas com RLS e armazenamento de imagens no Storage.

## Limites desta demonstração

- Não há pagamento real, cálculo de frete, criação persistente de pedidos ou área administrativa.
- O endpoint atual valida preços e estoque contra os dados estáticos do catálogo, mas não reserva estoque entre compras.
- Fotos carregadas de endereço externo podem mudar ou ficar indisponíveis.
- Para colocar no ar, é necessário configurar hospedagem, domínio, política de privacidade e revisar os dados comerciais.
