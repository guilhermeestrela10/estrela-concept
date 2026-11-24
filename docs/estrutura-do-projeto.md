# Estrutura do projeto

Este guia mostra onde encontrar o código da Estrela Concept. O repositório separa a aplicação, as páginas, os arquivos visuais, os testes e as configurações dos serviços.

```text
.
├── app/                       Código Python da aplicação
│   ├── server.py               Rotas HTTP e coordenação dos serviços
│   ├── store.py                Dados, autenticação e pedidos
│   ├── rag.py                  Busca semântica e respostas do assistente
│   ├── mongodb_analytics.py    Métricas agregadas de visualização
│   └── catalog.py              Produtos de exemplo para testes
├── templates/                 Páginas HTML servidas pelo site
├── static/
│   ├── css/                    Folhas de estilo
│   ├── images/                 Logos, ícones e imagens da loja
│   └── js/                     Scripts do catálogo, painel e assistente
├── tests/
│   └── fixtures/               Arquivos auxiliares de teste
├── supabase/
│   ├── functions/              Operações protegidas do banco
│   ├── migrations/             Alterações incrementais do banco
│   └── schema.sql              Esquema de referência completo
├── .github/workflows/          Verificações e automações do repositório
├── docs/                       Documentação complementar
├── server.py                   Ponto de entrada mantido para o Render
├── render.yaml                 Configuração de publicação
├── requirements.txt            Dependências Python
└── README.md                   Visão geral, configuração e conclusão do projeto
```

## Onde fazer cada alteração

- **Página, textos e estrutura visual:** altere o HTML correspondente em `templates/`.
- **Aparência e comportamento no navegador:** altere `static/css/styles.css` ou o JavaScript correspondente em `static/js/`.
- **Rotas HTTP, login, pedidos e notificações:** procure a lógica em `app/server.py`.
- **Persistência, validação e regras de pedidos:** procure `app/store.py` e a operação correspondente na Edge Function.
- **Busca do assistente:** use `app/rag.py`; alterações de estrutura do banco também precisam de uma migração em `supabase/migrations/`.
- **Métricas do MongoDB:** use `app/mongodb_analytics.py`.
- **Banco Supabase:** confira primeiro a migração relevante; `supabase/schema.sql` é uma referência completa, não um script para executar às cegas sobre a base publicada.
- **Testes:** mantenha os testes em `tests/` e os recursos auxiliares em `tests/fixtures/`.
- **Publicação ou automações:** revise `render.yaml` e os arquivos em `.github/workflows/`.

## Execução e verificação

Execute localmente a partir da raiz com `python server.py`. O ponto de entrada encaminha a inicialização para `app/server.py`, mantendo compatibilidade com o Render.

Antes de publicar alterações, confira o estado do Git, execute as verificações automatizadas existentes com `python -m unittest discover -s tests -v` e verifique no painel do Render se o deploy corresponde ao commit mais recente da `main`. Não coloque senhas, chaves, tokens, URIs de banco nem arquivos `.env` no repositório.
