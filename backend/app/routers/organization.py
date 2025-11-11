from fastapi import APIRouter
from app.supabase_client import supabase

router = APIRouter()

@router.post("/organizations/")
def create_organization(org: dict):
    result = supabase.table("Organization").insert(org).execute()
    return result.data

@router.get("/organizations/")
def get_organizations():
    result = supabase.table("Organization").select("*").execute()
    return result.data

@router.get("/organizations/{org_id}")
def get_organization(org_id: str):
    result = supabase.table("Organization").select("*").eq("id", org_id).single().execute()
    return result.data

@router.put("/organizations/{org_id}")
def update_organization(org_id: str, org: dict):
    result = supabase.table("Organization").update(org).eq("id", org_id).execute()
    return result.data

@router.delete("/organizations/{org_id}")
def delete_organization(org_id: str):
    result = supabase.table("Organization").delete().eq("id", org_id).execute()
    return {"deleted": result.data}
