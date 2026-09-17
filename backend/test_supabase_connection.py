from app.services.supabase_service import get_supabase_client


client = get_supabase_client()

response = (
    client
    .table("policies")
    .select("*")
    .limit(1)
    .execute()
)

print(response.data)
