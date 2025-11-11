from fastapi import FastAPI
from app.routers import team, organization, blog

app = FastAPI()

app.include_router(team.router)
app.include_router(organization.router)
app.include_router(blog.router)
