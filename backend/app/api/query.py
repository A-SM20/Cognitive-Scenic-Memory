"""
Chatbot & Cognitive Query API endpoints.

POST /api/query — Query the cognitive memory chatbot about objects,
relationships, and scene comparison changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.services.query_service import QueryService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])


class ChatQueryRequest(BaseModel):
    """Natural language question with optional explicit comparison targets."""
    query: str = Field(min_length=1, description="Natural language question")
    scene_id: Optional[str] = Field(default=None, description="Optional target scene ID")
    scene_before_id: Optional[str] = Field(default=None, description="Optional earlier scene ID for comparison")
    scene_after_id: Optional[str] = Field(default=None, description="Optional later scene ID for comparison")


class ChatQueryResponse(BaseModel):
    """Structured response from the Cognitive Chatbot."""
    query: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    context: Optional[dict] = None
    timestamp: datetime


@router.post(
    "",
    response_model=ChatQueryResponse,
    summary="Ask the cognitive scene memory chatbot",
)
async def ask_chatbot(
    request: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatQueryResponse:
    """
    Ask natural language questions regarding:
    - Object locations, statuses, and counts
    - Spatial relationships in the semantic scene graph
    - Environment changes when comparing two scenes
    """
    try:
        service = QueryService(db)
        result = await service.answer_query(
            query=request.query,
            scene_id=request.scene_id,
            scene_before_id=request.scene_before_id,
            scene_after_id=request.scene_after_id,
        )
        return ChatQueryResponse(**result)
    except Exception as e:
        logger.error("Chatbot query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")
