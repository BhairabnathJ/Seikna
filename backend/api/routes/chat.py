"""
Chatbot API routes.
"""
from fastapi import APIRouter, HTTPException
from api.models.requests import ChatRequest
from api.models.responses import ChatResponse, Citation

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Domain-limited chatbot endpoint.
    For MVP, returns a simple response (full RAG implementation in Phase 4).
    """
    # TODO: Implement full RAG chatbot in Phase 4
    # For MVP, return a placeholder response
    
    return ChatResponse(
        response="The chatbot feature is coming in Phase 4. For now, please review the course content above.",
        citations=[],
        confidence="low",
    )

