from fastapi import APIRouter
from app.supabase_client import supabase

router = APIRouter()

@router.post("/blogs/")
def create_blog(blog: dict):
    result = supabase.table("Blog").insert(blog).execute()
    return result.data

@router.get("/blogs/")
def get_blogs():
    result = supabase.table("Blog").select("*").execute()
    return result.data

@router.get("/blogs/{blog_id}")
def get_blog(blog_id: str):
    result = supabase.table("Blog").select("*").eq("id", blog_id).single().execute()
    return result.data

@router.put("/blogs/{blog_id}")
def update_blog(blog_id: str, blog: dict):
    result = supabase.table("Blog").update(blog).eq("id", blog_id).execute()
    return result.data

@router.delete("/blogs/{blog_id}")
def delete_blog(blog_id: str):
    result = supabase.table("Blog").delete().eq("id", blog_id).execute()
    return {"deleted": result.data}
