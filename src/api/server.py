# File: src/api/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import explorer_router, wallet_router

def create_app() -> FastAPI:
    app = FastAPI(title="bit2coin API")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(explorer_router)
    app.include_router(wallet_router)
    
    return app