from fastapi import APIRouter

from app.api.routes import auth, items, me, medicines, routine, scans, system

api = APIRouter(prefix="/api/v1")
api.include_router(system.router)
api.include_router(auth.router)
api.include_router(scans.router)
api.include_router(items.router)
api.include_router(medicines.router)
api.include_router(routine.router)
api.include_router(me.router)
