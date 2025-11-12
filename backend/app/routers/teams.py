from fastapi import APIRouter
from app.supabase_client import supabase

router = APIRouter()

@router.post("/teams/")
def create_team(team: dict):
    result = supabase.table("Teams").insert(team).execute()
    return result.data

@router.get("/teams/")
def get_teams():
    result = supabase.table("Teams").select("*").execute()
    return result.data

@router.get("/teams/{team_id}")
def get_team(team_id: str):
    result = supabase.table("Teams").select("*").eq("id", team_id).single().execute()
    return result.data

@router.put("/teams/{team_id}")
def update_team(team_id: str, team: dict):
    result = supabase.table("Teams").update(team).eq("id", team_id).execute()
    return result.data

@router.delete("/teams/{team_id}")
def delete_team(team_id: str):
    result = supabase.table("Teams").delete().eq("id", team_id).execute()
    return {"deleted": result.data}
