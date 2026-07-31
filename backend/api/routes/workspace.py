from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token
# Wait, orkestra_plans is created by orkestra.workspace.postgres, which uses its own Base.
# Since we need to query it from the control plane API, we can either use raw SQL 
# or import the PlanModel from orkestra.workspace.postgres.
from orkestra.workspace.postgres import PlanModel

router = APIRouter()

@router.get("/{session_id}/plan")
async def get_active_plan(
    session_id: str,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch the currently ACTIVE plan for a given session.
    """
    try:
        stmt = select(PlanModel).where(
            PlanModel.session_id == session_id
        ).order_by(PlanModel.id.desc())
        
        result = await db.execute(stmt)
        model = result.scalars().first()
        
        if not model:
            return {"plan": None}
            
        return {"plan": model.plan_data}
    except Exception as e:
        # Table might not exist yet if the agent hasn't been initialized
        return {"plan": None}
