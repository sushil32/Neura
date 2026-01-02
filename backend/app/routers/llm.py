"""LLM router for AI chat and completions."""
from typing import AsyncGenerator, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.deps import get_current_active_user

router = APIRouter()
logger = structlog.get_logger()


class ChatMessage(BaseModel):
    """Chat message."""
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Chat completion request."""
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=1024, ge=1, le=4096)
    stream: bool = False


class ChatResponse(BaseModel):
    """Chat completion response."""
    id: str
    model: str
    message: ChatMessage
    usage: dict


class CompletionRequest(BaseModel):
    """Text completion request."""
    prompt: str = Field(..., min_length=1, max_length=4096)
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=1024, ge=1, le=4096)


class CompletionResponse(BaseModel):
    """Text completion response."""
    id: str
    model: str
    text: str
    usage: dict


class ScriptGenerateRequest(BaseModel):
    """Script generation request."""
    topic: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="explainer", pattern="^(explainer|training|marketing|presentation)$")
    duration: int = Field(default=60, ge=15, le=600)  # seconds
    tone: str = Field(default="professional", pattern="^(professional|casual|friendly|formal)$")
    additional_instructions: Optional[str] = None


class ScriptGenerateResponse(BaseModel):
    """Script generation response."""
    script: str
    estimated_duration: int
    word_count: int


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a chat message and get a response."""
    from services.llm.provider import get_llm_provider
    
    try:
        provider = get_llm_provider()
        
        # Convert messages to provider format
        messages = [{"role": m.role, "content": m.content} for m in data.messages]
        
        # Get response
        response = await provider.chat(
            messages=messages,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
        
        return ChatResponse(
            id=response.get("id", "chat-" + str(user.id)[:8]),
            model=response.get("model", "unknown"),
            message=ChatMessage(
                role="assistant",
                content=response.get("content", ""),
            ),
            usage=response.get("usage", {}),
        )
        
    except Exception as e:
        logger.error("Chat error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get LLM response",
        )


@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest,
    user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """Stream chat response."""
    from services.llm.provider import get_llm_provider
    
    async def generate() -> AsyncGenerator[str, None]:
        try:
            provider = get_llm_provider()
            messages = [{"role": m.role, "content": m.content} for m in data.messages]
            
            async for chunk in provider.chat_stream(
                messages=messages,
                temperature=data.temperature,
                max_tokens=data.max_tokens,
            ):
                yield f"data: {chunk}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error("Stream error", error=str(e))
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/complete", response_model=CompletionResponse)
async def complete(
    data: CompletionRequest,
    user: User = Depends(get_current_active_user),
) -> CompletionResponse:
    """Get text completion."""
    from services.llm.provider import get_llm_provider
    
    try:
        provider = get_llm_provider()
        
        response = await provider.complete(
            prompt=data.prompt,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
        
        return CompletionResponse(
            id=response.get("id", "cmpl-" + str(user.id)[:8]),
            model=response.get("model", "unknown"),
            text=response.get("text", ""),
            usage=response.get("usage", {}),
        )
        
    except Exception as e:
        logger.error("Completion error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get completion",
        )


@router.post("/script/generate", response_model=ScriptGenerateResponse)
async def generate_script(
    data: ScriptGenerateRequest,
    user: User = Depends(get_current_active_user),
) -> ScriptGenerateResponse:
    """Generate a video script using AI."""
    from services.llm.provider import get_llm_provider
    
    # Build prompt for script generation
    system_prompt = f"""You are a professional video script writer. Generate a {data.type} video script.

Guidelines:
- Target duration: {data.duration} seconds (approximately {data.duration * 2} words)
- Tone: {data.tone}
- Write in a conversational style suitable for an AI avatar presenter
- Include natural pauses indicated by [PAUSE]
- Do not include stage directions or visual cues
- Focus on clear, engaging content"""

    if data.additional_instructions:
        system_prompt += f"\n\nAdditional instructions: {data.additional_instructions}"
    
    try:
        provider = get_llm_provider()
        
        response = await provider.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate a script about: {data.topic}"},
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        
        script = response.get("content", "")
        word_count = len(script.split())
        estimated_duration = word_count // 2  # ~120 words per minute
        
        return ScriptGenerateResponse(
            script=script,
            estimated_duration=estimated_duration,
            word_count=word_count,
        )
        
    except Exception as e:
        logger.error("Script generation error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate script",
        )

