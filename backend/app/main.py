import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import lifespan manager and API router from their new locations
from app.db.lifespan import lifespan
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)

# Create FastAPI app instance using the lifespan manager
app = FastAPI(
    title="Sionna RT Simulation API",
    description="API for running Sionna RT simulations and managing devices.",
    version="0.1.0",
    lifespan=lifespan # Use the imported lifespan context manager
)

# --- CORS Middleware ---
# Adjust origins as needed for your frontend setup
origins = [
    "http://localhost",
    "http://localhost:5173", # Default Vite dev port
    # Add any other origins if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Or ["*"] for development testing
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)
logger.info("CORS middleware added.")

# --- Include API Routers ---
# Include the router for API version 1
app.include_router(api_router, prefix="/api/v1") # Add a /api/v1 prefix
logger.info("Included API router v1 at /api/v1.")

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """Provides a basic welcome message."""
    logger.info("--- Root endpoint '/' requested ---")
    return {"message": "Welcome to the Sionna RT Simulation API"}


# --- Uvicorn Entry Point (for direct run, if needed) ---
# Note: Running directly might skip lifespan events unless using uvicorn programmatically
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server directly (use 'docker-compose up' for full setup)...")
    # This won't properly run the lifespan events like DB init unless configured differently.
    # Recommended to run via Docker Compose or `uvicorn app.main:app --reload` from the backend directory.
    uvicorn.run(app, host="0.0.0.0", port=8000)

logger.info("FastAPI application setup complete. Ready for Uvicorn via external command.")