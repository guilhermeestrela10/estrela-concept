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
  delete from public.rag_knowledge_chunks where id is not null;
  insert into public.rag_knowledge_chunks (id, source, content, embedding, updated_at)
  select gen_random_uuid()::text, item->>'source', item->>'content', (item->>'embedding')::extensions.vector, now()
  from jsonb_array_elements(p_chunks) as item;
  get diagnostics inserted_count = row_count;
  return inserted_count;
end;
$$;

revoke all on function public.replace_rag_chunks(jsonb) from public, anon, authenticated;
grant execute on function public.replace_rag_chunks(jsonb) to service_role;
