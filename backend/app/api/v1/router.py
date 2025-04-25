from fastapi import APIRouter
from app.api.v1.endpoints import sionna # Import the endpoint router

api_router = APIRouter()

# Include routers from endpoint modules
api_router.include_router(sionna.router, prefix="/sionna", tags=["Sionna Simulation"])
# Add other endpoint routers here later, e.g., for device CRUD
# api_router.include_router(devices.router, prefix="/devices", tags=["Devices"])