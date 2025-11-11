from fastapi import FastAPI
from app.routers import teams, organization, blog

app = FastAPI()

app.include_router(teams.router)
app.include_router(organization.router)
app.include_router(blog.router)
