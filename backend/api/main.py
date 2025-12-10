"""
FastAPI main application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import API_V1_PREFIX, CORS_ORIGINS
from core.config_validator import config_validator
from api.routes import courses, chat

app = FastAPI(
    title="Seikna API",
    description="Learning platform API",
    version="1.0.0",
)

@app.on_event("startup")
async def validate_configuration():
    """Validate configuration on application startup."""
    
    print("🔍 Validating configuration...")
    
    validation_result = config_validator.validate_all()
    
    # Print warnings
    for warning in validation_result["warnings"]:
        print(f"⚠️  WARNING: {warning}")
    
    # Print errors and fail if invalid
    if not validation_result["valid"]:
        print("\n❌ CONFIGURATION ERRORS DETECTED:\n")
        for error in validation_result["errors"]:
            print(f"   ❌ {error}")
        print("\n🛑 Application startup aborted due to configuration errors.\n")
        raise SystemExit(1)
    
    print("✅ Configuration validated successfully\n")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(courses.router, prefix=f"{API_V1_PREFIX}/courses", tags=["courses"])
app.include_router(chat.router, prefix=f"{API_V1_PREFIX}/chat", tags=["chat"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Seikna API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

