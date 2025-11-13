from fastapi import FastAPI
from app.routers import teams, organization, blog, contact

app = FastAPI()

app.include_router(teams.router)
app.include_router(organization.router)
app.include_router(blog.router)
app.include_router(contact.router)
