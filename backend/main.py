import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.logging import setup_structured_logging, get_logger
from backend.middleware.timing import TimingMiddleware

# Optional: Orkestra integration testing
# from orkestra.events.bus import EventBus
# from backend.telemetry.bridge import TelemetryBridge

from backend.api.routes import auth, users, tools, roles, llms, agents, mcps, guardrails, deployments, telemetry, workspace
from backend.api.routes.api_keys import router as api_keys_router
from backend.api.routes.hitl import router as hitl_router
from backend.api.core.database import AsyncSessionLocal, engine, Base
from backend.api.models.user import User
from backend.api.models.tool import Tool
from backend.api.models.role import Role
from backend.api.models.llm import LlmConfig
from backend.api.models.agent import AgentConfig
from backend.api.models.guardrail import GuardrailConfig
from backend.api.models.deployment import AgentDeployment
from backend.api.models.telemetry import AgentRun, RunEvent
from backend.api.core.security import get_password_hash
from backend.api.core.config import settings
from sqlalchemy.future import select

# 1. Initialize logging before anything else
setup_structured_logging()
logger = get_logger("api.main")

# 2. Create FastAPI app
app = FastAPI(
    title="Orkestra Control Plane API",
    description="Backend for monitoring and managing Orkestra Agents",
    version="1.0.0"
)

# 3. Middleware
app.add_middleware(TimingMiddleware)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Global State and Database Seeding
@app.on_event("startup")
async def startup_event():
    # Auto-create tables for local development
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Also ensure workspace tables exist for the control plane
        from orkestra.workspace.postgres import Base as WorkspaceBase
        await conn.run_sync(WorkspaceBase.metadata.create_all)
        
    # Seed default roles and admin
    async with AsyncSessionLocal() as db:
        from backend.api.core.iam import ROLE_PERMISSIONS
        for role_name, perms in ROLE_PERMISSIONS.items():
            result = await db.execute(select(Role).where(Role.name == role_name))
            existing_role = result.scalars().first()
            if not existing_role:
                db.add(Role(name=role_name, permissions=perms))
            elif existing_role.permissions != perms:
                existing_role.permissions = perms
        await db.commit()
        
        result = await db.execute(select(User).where(User.role == "ADMIN"))
        admin = result.scalars().first()
        if not admin:
            default_admin = User(
                email="admin@orkestra.local",
                hashed_password=get_password_hash("admin"),
                role="ADMIN",
                is_active=True
            )
            db.add(default_admin)
            await db.commit()
            logger.info("default_admin_seeded", email="admin@orkestra.local")
            
    logger.info("server_started", version=settings.VERSION)

# Mount Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(api_keys_router, prefix="/api/keys", tags=["API Keys"])
app.include_router(hitl_router, prefix="/api/hitl", tags=["HITL"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(roles.router, prefix="/api/roles", tags=["roles"])
app.include_router(llms.router, prefix="/api/llms", tags=["llms"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(mcps.router, prefix="/api/mcps", tags=["mcps"])
app.include_router(guardrails.router, prefix="/api/guardrails", tags=["guardrails"])
app.include_router(deployments.router, prefix="/api/deployments", tags=["deployments"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])

@app.get("/health")
async def health_check():
    """Simple health check endpoint that logs execution via middleware."""
    logger.info("health_check_hit", status="ok")
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    # Run server via: python -m backend.main
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
