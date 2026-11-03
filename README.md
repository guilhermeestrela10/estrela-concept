# Estrela Concept

**Seu estilo, seu brilho.** Uma loja virtual de moda fitness com catálogo, sacola, pedidos pelo WhatsApp e painel administrativo. O projeto está em fase de demonstração: os cinco produtos cadastrados são exemplos e devem ser trocados pelos dados reais antes da abertura ao público.

<p align="center">
  <img src="static/brand-horizontal.png" alt="Estrela Concept" width="300">
</p>

## Sobre a loja

A Estrela Concept apresenta peças de moda fitness em uma experiência responsiva, pensada para celular e computador. O atendimento é feito pelo WhatsApp da loja: **+55 86 99926-9836**. Livya De Araújo Macedo Estrela combina com o cliente pagamento, frete, entrega, trocas, devoluções e dúvidas sobre os produtos.

## Demonstração

- **Loja:** [abrir Estrela Concept](https://laws-commissioner-hobbies-interested.trycloudflare.com)
- **Painel administrativo:** [abrir o painel](https://laws-commissioner-hobbies-interested.trycloudflare.com/admin)
- **Repositório:** [guilhermeestrela10/estrela-concept](https://github.com/guilhermeestrela10/estrela-concept)

Os endereços acima usam um túnel temporário de demonstração. Ele depende desta máquina, do servidor e da conexão com a internet; o link pode mudar ou ficar indisponível. Para uma loja pública permanente será necessário contratar e configurar hospedagem e domínio.

## Recursos

### Loja

- Busca e filtros por categoria, tamanho e faixa de preço.
- Página de detalhes com descrição, imagem e variações disponíveis.
- Sacola com seleção de tamanho/cor e quantidade.
- Validação de estoque e registro do pedido no Supabase.
- Atalho para continuar o atendimento do pedido pelo WhatsApp.
- Layout adaptável a telas pequenas, com navegação por teclado e suporte a preferência por movimento reduzido.

### Painel administrativo

- Login de administrador e sessão protegida.
- Resumo de pedidos, vendas, produtos e estoque baixo.
- Cadastro e edição de produtos, com imagens por URL HTTPS ou envio de JPEG, PNG e WebP (até 4 MB) ao Supabase Storage; inclui categorias, tamanhos, cores e estoque.
- Controle de visibilidade dos produtos e atualização do status dos pedidos.

### Identidade visual

A interface usa o logotipo e o símbolo aprovados da Estrela Concept, com rosa antigo, preto e branco. Os arquivos oficiais usados pelo site estão em `static/brand-horizontal.png` e `static/brand-mark.png`.

## Tecnologias e dados

- **Interface:** HTML, CSS e JavaScript sem framework.
- **Servidor web:** Python 3, usando a biblioteca padrão.
- **Banco e autenticação:** Supabase Database e Supabase Auth.
- **API de dados:** Edge Function `estrela-api`, que mantém a chave de serviço no ambiente Supabase.
- **Imagens:** bucket público `product-images` para leitura das fotos no catálogo; upload limitado a administradores e a JPEG/PNG/WebP de até 4 MB.
- **Testes automatizados:** `unittest` da biblioteca padrão do Python.

O Supabase conectado contém categorias, produtos, imagens, variações/estoque, pedidos, itens do pedido, conta administrativa e sessões. A autorização para chamar a API do projeto usa um token privado; o Supabase guarda somente seu hash. A chave de serviço não é usada no navegador nem deve ser adicionada ao repositório.

## Executar neste computador

### Requisitos

- Windows, macOS ou Linux.
- Python 3.10 ou superior.
- Acesso à internet para conectar ao Supabase e carregar fontes e imagens externas.
- Token privado da API do projeto configurado localmente. No computador usado para a demonstração, ele já é lido de `%LOCALAPPDATA%\Estrela Concept\edge_api.key`.

### Iniciar

No terminal, abra a pasta do projeto e execute:

```powershell
python server.py
```

Depois, acesse:

- Loja: <http://127.0.0.1:8000>
- Painel: <http://127.0.0.1:8000/admin>
- Verificação da conexão: <http://127.0.0.1:8000/api/status>

O endpoint de status deve indicar `supabase`. Para encerrar o servidor, pressione `Ctrl+C` no terminal. As configurações `HOST` e `PORT` podem ser substituídas por variáveis de ambiente. O padrão é `127.0.0.1:8000`.

### Token privado da API

O servidor precisa de `ESTRELA_EDGE_API_TOKEN` para se comunicar com a Edge Function. No computador de demonstração, o valor é lido do arquivo privado indicado acima. Também é possível fornecê-lo no ambiente antes de iniciar o servidor:

```powershell
$env:ESTRELA_EDGE_API_TOKEN = "COLOQUE_O_TOKEN_PRIVADO_LOCALMENTE"
python server.py
```

O texto acima é apenas um exemplo de configuração. Não coloque o token real neste README, no código, em capturas de tela ou em commits. Se o token não estiver configurado, as rotas de dados falham de forma segura em vez de gravarem pedidos em um banco local por engano.

## Primeiro acesso ao painel

Abra `/admin` e entre com a conta administrativa configurada para o projeto. A senha não fica armazenada neste repositório. Se o Supabase ainda não tiver uma conta administrativa, a configuração inicial só pode ser feita uma vez e exige uma solicitação local ou o token de configuração definido no servidor. Não tente recriar uma conta já configurada.

O endereço de recuperação está configurado, e a proprietária informa que a configuração de e-mail está concluída. O painel ainda não tem uma tela própria de redefinição de senha. As credenciais administrativas atuais foram mantidas conforme solicitado para esta demonstração. A proteção contra senhas vazadas permanece desativada porque a opção exige um plano superior do Supabase.

## Como funciona um pedido

1. O cliente escolhe as peças, tamanhos, cores e quantidades.
2. O site confere o estoque e registra o pedido no Supabase.
3. O cliente pode abrir o WhatsApp com o resumo para combinar pagamento e entrega.

O site não cobra pagamentos. O pedido registrado é uma solicitação para atendimento; pagamento, frete e entrega são combinados diretamente com a loja pelo WhatsApp.

## Testes

Na pasta do projeto, execute:

```powershell
python -m unittest discover -s tests -v
```

Os testes usam um banco SQLite temporário e cobrem pedidos, validação de estoque, categorias, autenticação do painel e regras de acesso. O SQLite é usado nos testes; a loja configurada usa o Supabase.

## Estrutura do projeto

```text
├── index.html                       # Vitrine da loja
├── admin.html                       # Painel administrativo
├── server.py                        # Servidor local e rotas HTTP
├── store.py                         # Integração Supabase e armazenamento de teste
├── catalog.py                       # Produtos fictícios para testes
├── static/
│   ├── app.js                        # Catálogo, sacola e pedido
│   ├── admin.js                      # Ações do painel
│   ├── styles.css                    # Layout e identidade visual
│   ├── brand-horizontal.png          # Logotipo oficial
│   └── brand-mark.png                # Símbolo e ícone da aba
├── supabase/
│   ├── schema.sql                    # Estrutura, RLS e permissões
│   └── functions/estrela-api/        # API protegida
└── tests/                            # Testes automatizados
```

## Situação e próximos passos

### Disponível para demonstração

- Loja, painel administrativo e fluxo de pedido integrados ao Supabase.
- Cinco produtos de demonstração editáveis pelo painel.
- Pagamento, entrega e atendimento direcionados ao WhatsApp.
- Identidade visual oficial aplicada na loja e no painel.

### Antes de abrir ao público

- Substituir os produtos de demonstração por produtos reais, com fotos, descrições, preços, tamanhos, cores e estoque conferidos.
- Contratar e configurar hospedagem permanente, domínio e HTTPS. O túnel atual é temporário e depende desta máquina ligada e conectada à internet.
- Revisar e publicar os dados de identificação da loja e as políticas definitivas de privacidade, entrega, troca e devolução.
- Configurar backups e revisar as proteções do banco no ambiente de produção; tabelas e sequências estão bloqueadas para `anon` e `authenticated`, com RLS ativo e acesso apenas pelo serviço.
- Testar cadastro e edição de produtos, estoque, pedido, login e WhatsApp no domínio final, em computadores e celulares reais.

**Observações de segurança:** a proteção contra senhas vazadas está desativada no plano atual. A proprietária optou por manter as credenciais administrativas e a chave de serviço atuais durante a demonstração. Reavaliar essas escolhas ao preparar o ambiente de produção. O endereço de recuperação está cadastrado, mas o painel não inclui um fluxo de redefinição de senha.

**Lembrete solicitado:** quando os itens acima estiverem concluídos, fazer a revisão final de segurança, backups, políticas e funcionamento antes de divulgar a loja.
