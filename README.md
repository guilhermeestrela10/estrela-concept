# Estrela Concept

**Seu estilo, seu brilho.** A Estrela Concept é uma loja virtual de moda fitness. O site apresenta produtos, permite montar uma sacola e registra pedidos para a equipe continuar o atendimento pelo WhatsApp.

> **Demonstração:** os produtos e estoques atuais são exemplos. O site está publicado, mas ainda não está pronto para receber vendas reais.

## Acessos

- **Loja:** [estrela-concept.onrender.com](https://estrela-concept.onrender.com/)
- **Painel administrativo:** [abrir o painel](https://estrela-concept.onrender.com/admin)
- **Código no GitHub:** [guilhermeestrela10/estrela-concept](https://github.com/guilhermeestrela10/estrela-concept)

O painel não tem link na loja pública. Para acessá-lo, abra diretamente o endereço `/admin`; a página exige login.

## O que o site faz

### Para quem visita a loja

- Pesquisa produtos e filtra por categoria, tamanho e preço.
- Consulta fotos, descrição, tamanhos, cores e disponibilidade.
- Adiciona itens à sacola e informa nome e WhatsApp para enviar um pedido.
- O site confere o estoque e registra o pedido no banco de dados.
- O cliente pode abrir o WhatsApp para combinar pagamento, frete, entrega, trocas, devoluções ou tirar dúvidas.

O site **não cobra pagamentos** e não calcula frete. Essas combinações são feitas diretamente com a loja pelo WhatsApp **+55 86 99926-9836**.

### Para a administração

- Consulta pedidos e acompanha seus status.
- Cadastra e edita produtos, categorias, preços e estoque.
- Adiciona até 10 fotos por produto. As imagens podem vir de endereços HTTPS ou do dispositivo, em JPEG, PNG ou WebP, com até 4 MB por arquivo.
- Controla se cada produto aparece na loja.
- Usa o link **Esqueci minha senha** para receber um link de recuperação no e-mail cadastrado no Supabase.

## Situação atual

O projeto está publicado para demonstração no Render e usa o Supabase para os dados, as imagens e a autenticação. Na revisão de **3 de novembro de 2026**, o banco tinha sete produtos de exemplo, cinco visíveis. Essa quantidade pode mudar quando o catálogo for editado.

O plano gratuito do Render pode suspender o serviço depois de um período sem visitas; a primeira abertura após a pausa pode demorar. O site não depende de este computador ficar ligado. O projeto Supabase também está no plano gratuito e pode pausar projetos sem atividade prolongada.

## Como os dados são protegidos

- O navegador conversa com o servidor Python. A chave de serviço do Supabase fica na Edge Function e não é usada no navegador.
- O servidor chama a função estrela-api com um token privado. O banco armazena o hash desse token.
- As tabelas têm RLS habilitado, e o acesso de escrita passa pelas rotas protegidas do servidor.
- A sacola fica no navegador; pedidos, produtos, estoque e dados administrativos ficam no Supabase.
- O painel usa sessão protegida por cookie, com validade de até oito horas. Trocar a senha pela recuperação encerra as sessões administrativas existentes.
- O upload de imagens exige acesso administrativo e valida o tipo e o conteúdo do arquivo.

**Limite conhecido:** a proteção do Supabase contra senhas vazadas está desativada no plano atual. A proprietária decidiu manter as credenciais administrativas atuais durante a demonstração. Reavalie essas decisões antes da abertura ao público.

## Tecnologias

- **Loja e painel:** HTML, CSS e JavaScript, sem framework.
- **Servidor:** Python 3.10 ou superior e biblioteca padrão do Python.
- **Banco, login e arquivos:** Supabase Database, Supabase Auth e Supabase Storage.
- **Hospedagem da demonstração:** Render.
- **Testes:** unittest, com SQLite temporário para simular o armazenamento local.

Não há dependências Python externas para instalar.

## Executar no computador

### 1. Preparar o token privado

O servidor local precisa de ESTRELA_EDGE_API_TOKEN para acessar a Edge Function. No computador usado para a demonstração, o token pode ser lido de:

    %LOCALAPPDATA%\Estrela Concept\edge_api.key

Se ainda não tiver esse arquivo, configure a variável de ambiente no PowerShell. Use o valor do token guardado em local seguro; não o coloque no código, no README, em capturas de tela ou no GitHub.

    $env:ESTRELA_EDGE_API_TOKEN = "SEU_TOKEN_PRIVADO"

### 2. Iniciar o servidor

Abra o PowerShell na pasta do projeto e execute:

    python server.py

Abra estes endereços no navegador:

- Loja: <http://127.0.0.1:8000>
- Painel: <http://127.0.0.1:8000/admin>
- Estado da conexão: <http://127.0.0.1:8000/api/status>

Para encerrar, volte ao terminal e pressione Ctrl+C. O servidor usa 127.0.0.1:8000 por padrão; HOST e PORT podem ser definidos por variáveis de ambiente.

O servidor local conectado ao Supabase não troca automaticamente para SQLite se a conexão falhar: as rotas de dados retornam erro para evitar gravar dados no lugar errado. SQLite é usado nos testes.

## Recuperação da senha do painel

O painel solicita a recuperação pelo nome de usuário e não informa se um usuário existe. O link é enviado pelo Supabase Auth ao e-mail cadastrado. A nova senha precisa ter pelo menos 12 caracteres; depois de alterá-la, entre novamente no painel.

Para que o link de recuperação abra corretamente, nas configurações **Authentication → URL Configuration** do Supabase, inclua este endereço na lista de redirecionamentos permitidos:

    https://estrela-concept.onrender.com/admin

Quando um domínio próprio for configurado, atualize também o destino usado pela função e a lista permitida no Supabase. A recuperação por e-mail não foi testada de ponta a ponta, pois isso enviaria uma mensagem real.

## Banco de dados e imagens

O arquivo supabase/schema.sql documenta as tabelas, validações, permissões e funções usadas pelo projeto. A aplicação publicada usa o projeto Supabase já conectado; não é necessário executar esse arquivo novamente para testar o site.

O catálogo de demonstração fica no Supabase. As imagens enviadas pelo painel são salvas no bucket product-images; a vitrine lê as imagens desse bucket. O arquivo catalog.py fornece produtos de exemplo para o armazenamento SQLite usado nos testes.

## Hospedagem e atualizações

O serviço do Render está ligado ao repositório do GitHub e à branch main. As mudanças são versionadas e enviadas ao GitHub. O Render está configurado para publicar automaticamente; se uma alteração enviada não iniciar um deploy, acesse o serviço no Render e use **Manual Deploy** para publicar o último commit.

O arquivo render.yaml descreve o serviço, o comando de inicialização e a variável secreta ESTRELA_EDGE_API_TOKEN. O token deve ser configurado nas variáveis privadas do Render e nunca incluído neste repositório.

## Testes

Na pasta do projeto, execute:

    python -m unittest discover -s tests -v

Os testes cobrem cadastro e sessão do painel, recuperação de senha no servidor, validação de pedidos e estoque, imagens e ciclo de pedidos no armazenamento SQLite temporário. Eles não enviam e-mails nem substituem a conferência do fluxo real no Supabase.

## Arquivos principais

| Arquivo | Para que serve |
| --- | --- |
| index.html | Página da loja |
| admin.html | Tela do painel administrativo |
| server.py | Servidor web e rotas da aplicação |
| store.py | Acesso ao Supabase e armazenamento SQLite dos testes |
| catalog.py | Produtos de exemplo para os testes locais |
| static/app.js | Catálogo, sacola e envio de pedidos |
| static/admin.js | Login, cadastro e gerenciamento no painel |
| static/styles.css | Estilos responsivos da loja e do painel |
| supabase/schema.sql | Estrutura e regras do banco |
| supabase/functions/estrela-api/ | Função de API protegida do Supabase |
| tests/ | Testes automatizados |

## O que falta antes de abrir ao público

Estas etapas foram deixadas para o final, conforme combinado:

1. **Cadastrar o catálogo real:** fotos, descrições, preços, tamanhos, cores e estoque conferidos.
2. **Escolher domínio e hospedagem:** registrar um domínio próprio e escolher um plano que mantenha o site disponível sem a pausa do plano gratuito.
3. **Definir e publicar as informações da loja:** dados de identificação e políticas definitivas de privacidade, entrega, troca e devolução.
4. **Definir backups:** no plano gratuito do Supabase, não há backups automáticos disponíveis para download. Escolha uma rotina de exportação segura ou um plano que ofereça o tipo de backup necessário. Consulte a [documentação de backups do Supabase](https://supabase.com/docs/guides/platform/backups).
5. **Revisar o domínio final:** liberar o endereço de recuperação no Supabase e testar login, recuperação, cadastro e edição de produtos, estoque, pedidos e WhatsApp em celular e computador.
6. **Revisão de segurança e publicação:** conferir credenciais, chaves, permissões, backups e conteúdo antes de divulgar a loja.

**Lembrete solicitado:** quando essas etapas estiverem concluídas, fazer a revisão final de segurança, backups, políticas e funcionamento antes de abrir ao público.
