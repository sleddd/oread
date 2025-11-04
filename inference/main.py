"""
Minimal Python Inference Microservice
Handles only LLM and Emotion model inference
Self-contained with no backend dependencies
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool

# Import our self-contained config
from config import config

# Import standalone LLM processor (refactored modular version)
from processors.llm_processor import LLMProcessor

# Import emotion detector
from processors.emotion import EmotionDetector

# Import MCP client for web search
from web_search.client import initialize_mcp, shutdown_mcp, get_mcp_client

# Import vector memory service
from memory.memory_service import MemoryService

# Validate configuration
if not config.validate():
    print("FATAL: Environment configuration validation failed. Exiting.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global processors (singleton)
llm_processor: Optional[LLMProcessor] = None
emotion_detector: Optional[EmotionDetector] = None
memory_service: Optional[MemoryService] = None

# Cancellation tracking (request_id -> cancelled flag)
cancelled_requests: set = set()

# ----------------------------------------------------------------------
## Lifespan Context Manager (Startup & Shutdown)
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events."""
    global llm_processor, emotion_detector, memory_service

    # ** STARTUP LOGIC **
    logger.info("=" * 60)
    logger.info("Starting Inference Service")
    config.print_config()

    # 1. Initialize Vector Memory Service
    try:
        logger.info("Initializing Vector Memory Service...")
        memory_service = MemoryService(persist_directory=config.memory_persist_dir)
        await memory_service.initialize()
        logger.info("✅ Vector Memory Service initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Vector Memory Service: {str(e)}", exc_info=True)
        logger.warning("Continuing without vector memory - semantic recall will be disabled")
        memory_service = None

    # 2. Initialize LLM Processor
    try:
        logger.info("Initializing LLM Processor...")
        llm_path = Path(config.llm_model_path)

        if not llm_path.exists():
            logger.error("LLM model file not found")
            logger.error("Please download a GGUF model and update LLM_MODEL_PATH in .env")
            llm_processor = None
        else:
            llm_processor = LLMProcessor(
                model_path=config.llm_model_path,
                n_ctx=config.llm_n_ctx,
                n_threads=config.llm_n_threads,
                n_gpu_layers=config.llm_n_gpu_layers,
                n_batch=config.llm_n_batch,  # Pass batch size from config
                memory_service=memory_service  # Pass vector memory to LLM
            )

            # Initialize - this is an async method that loads the model
            await llm_processor.initialize()
            logger.info("✅ LLM Processor initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM Processor: {str(e)}", exc_info=True)
        llm_processor = None

    # 2. Initialize Emotion Detector
    try:
        logger.info("Initializing Emotion Detector...")
        emotion_path = Path(config.emotion_model_path)

        if not emotion_path.exists():
            logger.warning("Emotion model directory not found")
            logger.warning("Will attempt to download model from HuggingFace (requires internet)")

        emotion_detector = EmotionDetector(model_path=config.emotion_model_path)

        # Initialize - check if it's async or sync
        if hasattr(emotion_detector, 'initialize'):
            # EmotionDetector.initialize might be async too
            init_method = emotion_detector.initialize
            if hasattr(init_method, '__call__'):
                # Try calling it - if it's a coroutine, await it
                result = emotion_detector.initialize()
                if hasattr(result, '__await__'):
                    await result
        logger.info("✅ Emotion Detector initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Emotion Detector: {e.__class__.__name__}: {str(e)}", exc_info=True)
        emotion_detector = None

    # 3. Initialize MCP Client (for web search only - memory is handled by ChromaDB above)
    try:
        logger.info("Initializing MCP Client (Brave Search)...")
        await initialize_mcp()
        mcp_client = get_mcp_client()
        if mcp_client and mcp_client.initialized:
            logger.info("✅ MCP Search Client initialized successfully")
        else:
            logger.warning("⚠️ MCP Search Client initialized but not fully connected")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MCP Search Client: {e}")
        logger.info("Continuing without MCP (web search disabled, vector memory still active)")

    logger.info("=" * 60)

    yield

    # ** SHUTDOWN LOGIC **
    logger.info("Shutting down Inference Service")

    # Shutdown emotion detector
    try:
        if emotion_detector and hasattr(emotion_detector, 'cleanup'):
            emotion_detector.cleanup()
            logger.info("✅ Emotion detector cleanup complete")
    except Exception as e:
        logger.error(f"Error cleaning up emotion detector: {e}")

    # Shutdown MCP search connection
    try:
        await shutdown_mcp()
        logger.info("✅ MCP Search Client shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down MCP search: {e}")

    # Shutdown vector memory service
    try:
        if memory_service and hasattr(memory_service, 'cleanup'):
            memory_service.cleanup()
            logger.info("✅ Memory service cleanup complete")
    except Exception as e:
        logger.error(f"Error cleaning up memory service: {e}")

# ----------------------------------------------------------------------
## App Initialization & Schemas
# ----------------------------------------------------------------------
app = FastAPI(
    title="Inference Service",
    version="2.0.0",
    description="Self-contained ML inference microservice for LLM and Emotion detection",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LLMInferenceRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=50000)
    max_tokens: Optional[int] = Field(default=800, ge=1, le=4000)
    temperature: Optional[float] = Field(default=0.8, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=0.95, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=40, ge=1, le=100)
    repeat_penalty: Optional[float] = Field(default=1.1, ge=1.0, le=2.0)
    stop_sequences: Optional[List[str]] = Field(default=None)


class LLMInferenceResponse(BaseModel):
    text: str
    tokens_generated: int
    stopped_early: bool = False
    stop_reason: Optional[str] = None


class LLMContextInferenceRequest(BaseModel):
    """Request for context-aware LLM generation (uses Python's sophisticated prompt building)"""
    text: str = Field(..., min_length=1, max_length=5000)
    emotion_data: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    search_context: Optional[str] = None
    character_profile: Optional[Dict[str, Any]] = None
    max_tokens_override: Optional[int] = None
    temperature_override: Optional[float] = None
    request_id: Optional[str] = None  # For cancellation tracking
    enable_memory: Optional[bool] = False  # User preference for memory retrieval
    enable_web_search: Optional[bool] = False  # User preference for web search
    web_search_api_key: Optional[str] = None  # Brave Search API key from user settings

class EmotionInferenceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class EmotionScore(BaseModel):
    label: str
    score: float

class EmotionInferenceResponse(BaseModel):
    label: str
    score: float
    top_emotions: List[EmotionScore]
    intensity: Optional[str] = None
    category: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unavailable"]
    llm_loaded: bool
    emotion_loaded: bool
    service_info: Dict[str, Any]


# ----------------------------------------------------------------------
## Dependency Injection
# ----------------------------------------------------------------------
def get_llm_processor() -> LLMProcessor:
    """Get or ensure LLM processor is initialized"""
    if llm_processor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM processor is not initialized. Model file may be missing."
        )
    if hasattr(llm_processor, 'initialized') and not llm_processor.initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM processor initialization failed. Check server logs."
        )
    return llm_processor


def get_emotion_detector() -> EmotionDetector:
    """Get or ensure emotion detector is initialized"""
    if emotion_detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Emotion detector is not initialized. Check server logs."
        )
    if hasattr(emotion_detector, 'initialized') and not emotion_detector.initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Emotion detector initialization failed. Check server logs."
        )
    return emotion_detector


# ----------------------------------------------------------------------
## Routes
# ----------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    current_status: Literal["healthy", "degraded", "unavailable"] = "healthy"

    llm_ready = llm_processor is not None
    if hasattr(llm_processor, 'initialized'):
        llm_ready = llm_ready and llm_processor.initialized

    emotion_ready = emotion_detector is not None
    if hasattr(emotion_detector, 'initialized'):
        emotion_ready = emotion_ready and emotion_detector.initialized

    if not llm_ready and not emotion_ready:
        current_status = "unavailable"
    elif not llm_ready or not emotion_ready:
        current_status = "degraded"

    return HealthResponse(
        status=current_status,
        llm_loaded=llm_ready,
        emotion_loaded=emotion_ready,
        service_info={
            "version": "2.0.0",
            "host": config.host,
            "port": config.port,
            "gpu_layers": config.llm_n_gpu_layers,
        }
    )


@app.post("/infer/llm", response_model=LLMInferenceResponse)
async def infer_llm(
    request: LLMInferenceRequest,
    llm: LLMProcessor = Depends(get_llm_processor)
):
    """
    Generate text using the LLM. Runs synchronously in a threadpool.
    """
    import time
    start_time = time.time()

    try:
        logger.info(f"LLM inference request: {len(request.prompt)} chars")

        # LLM generation is async
        response_text = await llm.generate_response(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repeat_penalty=request.repeat_penalty,
            stop_sequences=request.stop_sequences or []
        )

        if response_text is None or response_text.strip() == "":
            raise RuntimeError("LLM returned an empty or invalid response.")

        # Approximate token count (not exact tokenization)
        tokens_generated = len(response_text.split())

        elapsed = time.time() - start_time
        logger.info(f"✅ LLM inference completed in {elapsed:.2f}s ({tokens_generated} tokens)")

        if elapsed > 120:
            logger.warning(f"⚠️ Slow inference detected: {elapsed:.2f}s (approaching 180s timeout limit)")

        return LLMInferenceResponse(
            text=response_text,
            tokens_generated=tokens_generated,
            stopped_early=False,
            stop_reason=None
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"LLM inference error after {elapsed:.2f}s: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM inference failed: {e.__class__.__name__} - {str(e)}"
        )


@app.post("/infer/llm/context", response_model=LLMInferenceResponse)
async def infer_llm_with_context(
    request: LLMContextInferenceRequest,
    llm: LLMProcessor = Depends(get_llm_processor)
):
    """
    Generate text using context-aware LLM with sophisticated prompt building.
    This endpoint uses Python's prompt engineering (romantic instructions, actions, etc.)

    Uses FIFO (First In, First Out) processing - requests are handled sequentially.
    """
    import time
    start_time = time.time()

    try:
        logger.info(f"Context-aware LLM inference request: {len(request.text)} chars")

        # Check if request was already cancelled before starting
        if request.request_id and request.request_id in cancelled_requests:
            logger.info(f"🚫 Request was cancelled before inference started")
            cancelled_requests.discard(request.request_id)
            raise HTTPException(status_code=499, detail="Request cancelled by client")

        # Extract character name from request (support both camelCase and snake_case)
        character_name = None
        if request.character_profile and isinstance(request.character_profile, dict):
            character_name = (
                request.character_profile.get('character_name') or
                request.character_profile.get('characterName')
            )

        # Character loaded (logged at debug level without name)

        # Call LLM processor directly (FIFO - sequential processing)
        result = await llm.generate_with_context(
            text=request.text,
            emotion_data=request.emotion_data,
            conversation_history=request.conversation_history,
            search_context=request.search_context,
            character_profile=request.character_profile,
            max_tokens_override=request.max_tokens_override,
            temperature_override=request.temperature_override,
            character_name=character_name,  # Explicitly pass character name
            request_id=request.request_id,  # Pass for cancellation checking
            enable_memory=request.enable_memory,  # User preference for memory retrieval
            enable_web_search=request.enable_web_search,  # User preference for web search
            web_search_api_key=request.web_search_api_key  # Brave Search API key
        )

        if not result or not result.get("text"):
            raise RuntimeError("LLM returned an empty or invalid response.")

        elapsed = time.time() - start_time
        logger.info(f"✅ Context-aware LLM inference completed in {elapsed:.2f}s ({result.get('tokens_generated', 0)} tokens)")

        # Log warning if response is taking too long (approaching timeout)
        if elapsed > 120:
            logger.warning(f"⚠️ Slow inference detected: {elapsed:.2f}s (approaching 180s timeout limit)")

        return LLMInferenceResponse(
            text=result["text"],
            tokens_generated=result.get("tokens_generated", 0),
            stopped_early=False,
            stop_reason=None
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Context-aware LLM inference error after {elapsed:.2f}s: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Context-aware LLM inference failed: {e.__class__.__name__} - {str(e)}"
        )


@app.post("/infer/emotion", response_model=EmotionInferenceResponse)
async def infer_emotion(
    request: EmotionInferenceRequest,
    detector: EmotionDetector = Depends(get_emotion_detector)
):
    """
    Detect emotion in text. Runs synchronously in a threadpool.
    """
    try:
        logger.info(f"Emotion inference request: {len(request.text)} chars")

        # Run the synchronous method in a threadpool
        result = await run_in_threadpool(detector.detect, request.text)

        return EmotionInferenceResponse(
            label=result.get("label"),
            score=result.get("score"),
            top_emotions=result.get("top_emotions", []),
            intensity=result.get("intensity"),
            category=result.get("category")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emotion inference error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emotion inference failed: {e.__class__.__name__} - {str(e)}"
        )


# ----------------------------------------------------------------------
## Request Cancellation Endpoint
# ----------------------------------------------------------------------
@app.post("/cancel")
async def cancel_request(request: Dict[str, Any]):
    """
    Cancel an in-flight inference request to free up LLM resources.

    Args:
        request: Dict with 'session_id' and 'request_id'

    Returns:
        Success status
    """
    global cancelled_requests

    session_id = request.get('session_id')
    request_id = request.get('request_id')

    if not request_id:
        raise HTTPException(status_code=400, detail="request_id is required")

    # Add to cancelled set
    cancelled_requests.add(request_id)
    logger.info(f"🚫 Request marked for cancellation")

    # Auto-cleanup after 60 seconds (request should be done by then)
    async def cleanup():
        await asyncio.sleep(60)
        cancelled_requests.discard(request_id)
        logger.debug(f"Cleaned up cancelled request")

    # Fire and forget cleanup
    asyncio.create_task(cleanup())

    return {
        "status": "cancelled",
        "request_id": request_id,
        "message": "Cancellation signal set - inference will abort at next check"
    }


# ----------------------------------------------------------------------
## MCP Integration Endpoints
# ----------------------------------------------------------------------
@app.post("/mcp/save_conversation")
async def save_conversation_to_memory(request: Dict[str, Any]):
    """
    Save conversation to persistent vector memory.
    Returns success even if memory is unavailable (graceful degradation).
    """
    try:
        # If memory service not initialized, log and return gracefully
        if not memory_service or not memory_service.initialized:
            logger.warning("Vector memory not initialized - conversation not saved to persistent storage")
            return {
                "status": "skipped",
                "message": "Memory not available - conversation saved to session only"
            }

        # Store user message (skip system messages)
        user_message = request.get("user_message", "")
        is_system_message = user_message.strip().startswith("[System:")

        user_msg_id = None
        if not is_system_message:
            user_msg_id = memory_service.store_message(
                message=user_message,
                character=request.get("character_name", "Unknown"),
                speaker="User",
                session_id=request.get("session_id", "unknown"),
                emotion=request.get("emotion")
            )
        else:
            logger.debug("Skipping system message from memory storage")

        # Store character response
        char_msg_id = memory_service.store_message(
            message=request.get("character_response", ""),
            character=request.get("character_name", "Unknown"),
            speaker=request.get("character_name", "Unknown"),
            session_id=request.get("session_id", "unknown")
        )

        if user_msg_id and char_msg_id:
            logger.debug(f"Saved conversation to vector memory: {user_msg_id}, {char_msg_id}")
            return {"status": "success", "message": "Conversation saved to vector memory"}
        else:
            logger.warning("Failed to save conversation to vector memory")
            return {
                "status": "skipped",
                "message": "Conversation saved to session only"
            }

    except Exception as e:
        logger.warning(f"Vector memory save error (non-fatal): {str(e)}")
        # Don't raise exception - gracefully degrade
        return {
            "status": "skipped",
            "message": "Conversation saved to session only"
        }


@app.delete("/api/conversations/delete-all")
async def delete_all_conversations():
    """
    Delete all conversation history and memories from vector memory.
    This is a destructive operation and cannot be undone.
    """
    try:
        if not memory_service or not memory_service.initialized:
            logger.warning("Vector memory not initialized - nothing to delete")
            return {
                "status": "success",
                "message": "No conversations to delete",
                "deleted_count": 0
            }

        # Get stats before deletion
        stats = memory_service.get_stats()
        total_count = stats.get("total_messages", 0)

        # Delete all memories
        success = memory_service.delete_all()

        if success:
            logger.info(f"Deleted {total_count} messages from vector memory")
            return {
                "status": "success",
                "message": f"Successfully deleted all conversation history",
                "deleted_count": total_count
            }
        else:
            raise RuntimeError("Failed to delete memories")

    except Exception as e:
        logger.error(f"Error deleting conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversations: {str(e)}"
        )


@app.get("/api/conversations/history/{character_name}")
async def get_conversation_history(
    character_name: str,
    limit: int = 50,
    offset: int = 0
):
    """
    Retrieve conversation history for a specific character.
    Returns messages sorted by timestamp (most recent first).

    Args:
        character_name: Name of the character
        limit: Maximum number of messages to return (default: 50)
        offset: Pagination offset (default: 0)

    Returns:
        List of conversation messages with metadata
    """
    try:
        if not memory_service or not memory_service.initialized:
            logger.warning("Vector memory not initialized - no history available")
            return {
                "status": "success",
                "character": character_name,
                "messages": [],
                "total": 0
            }

        # Get messages from memory service
        messages = memory_service.get_messages(
            character=character_name,
            limit=limit,
            offset=offset
        )

        # Sort by timestamp (most recent first)
        sorted_messages = sorted(
            messages,
            key=lambda m: m.get('metadata', {}).get('timestamp', ''),
            reverse=True
        )

        # Format for frontend
        formatted_messages = []
        for msg in sorted_messages:
            metadata = msg.get('metadata', {})
            formatted_messages.append({
                "speaker": metadata.get('speaker', 'Unknown'),
                "text": msg.get('message', ''),
                "timestamp": metadata.get('timestamp', ''),
                "emotion": metadata.get('emotion'),
                "session_id": metadata.get('session_id')
            })

        logger.info(f"Retrieved {len(formatted_messages)} messages")
        return {
            "status": "success",
            "character": character_name,
            "messages": formatted_messages,
            "total": len(formatted_messages)
        }

    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversation history: {str(e)}"
        )


@app.delete("/api/conversations/delete-character/{character_name}")
async def delete_character_conversations(character_name: str):
    """
    Delete all conversation history for a specific character.
    This is a destructive operation and cannot be undone.
    """
    try:
        if not memory_service or not memory_service.initialized:
            logger.warning("Vector memory not initialized - nothing to delete")
            return {
                "status": "success",
                "message": "No conversations to delete",
                "deleted_count": 0,
                "character": character_name
            }

        # Get stats before deletion
        stats = memory_service.get_stats(character=character_name)
        count = stats.get("characters", {}).get(character_name, 0)

        # Delete character memories
        success = memory_service.delete_character_memories(character_name)

        if success:
            logger.info(f"Deleted {count} messages")
            return {
                "status": "success",
                "message": f"Successfully deleted conversation history for {character_name}",
                "deleted_count": count,
                "character": character_name
            }
        else:
            raise RuntimeError(f"Failed to delete memories for {character_name}")

    except Exception as e:
        logger.error(f"Error deleting character conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete character conversations: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {config.host}:{config.port}")

    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level=config.log_level
    )