create extension if not exists vector with schema extensions;

create table if not exists public.rag_knowledge_chunks (
  id text primary key,
  source text not null check (length(source) between 1 and 120),
  content text not null check (length(content) between 1 and 2000),
  embedding extensions.vector(768) not null,
  updated_at timestamptz not null default now()
);

create index if not exists rag_knowledge_chunks_embedding_idx
  on public.rag_knowledge_chunks using hnsw (embedding extensions.vector_cosine_ops);

alter table public.rag_knowledge_chunks enable row level security;
revoke all on table public.rag_knowledge_chunks from public, anon, authenticated;

create or replace function public.replace_rag_chunks(p_chunks jsonb)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  inserted_count integer;
begin
  if jsonb_typeof(p_chunks) <> 'array' or jsonb_array_length(p_chunks) < 1 or jsonb_array_length(p_chunks) > 500 then
    raise exception 'Invalid knowledge index size';
  end if;
  delete from public.rag_knowledge_chunks;
  insert into public.rag_knowledge_chunks (id, source, content, embedding, updated_at)
  select gen_random_uuid()::text, item->>'source', item->>'content', (item->>'embedding')::extensions.vector, now()
  from jsonb_array_elements(p_chunks) as item;
  get diagnostics inserted_count = row_count;
  return inserted_count;
end;
$$;

create or replace function public.search_rag_chunks(
  p_query_embedding extensions.vector(768),
  p_match_count integer default 5,
  p_min_similarity double precision default 0.48
)
returns table (source text, content text, similarity double precision)
language sql
security definer
set search_path = ''
as $$
  select chunks.source, chunks.content,
    (1 - (chunks.embedding OPERATOR(extensions.<=>) p_query_embedding))::double precision
  from public.rag_knowledge_chunks as chunks
  where p_match_count between 1 and 5
    and p_min_similarity between 0 and 1
    and 1 - (chunks.embedding OPERATOR(extensions.<=>) p_query_embedding) >= p_min_similarity
  order by chunks.embedding OPERATOR(extensions.<=>) p_query_embedding
  limit least(greatest(p_match_count, 1), 5)
$$;

revoke all on function public.replace_rag_chunks(jsonb) from public, anon, authenticated;
revoke all on function public.search_rag_chunks(extensions.vector, integer, double precision) from public, anon, authenticated;
grant execute on function public.replace_rag_chunks(jsonb) to service_role;
grant execute on function public.search_rag_chunks(extensions.vector, integer, double precision) to service_role;
