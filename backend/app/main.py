import asyncio
import json
import logging
import shutil
from pathlib import Path
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import ensure_directories, settings
from app.rag_engine import RagEngine

from app.schemas import (
    ChatRequest, ChatResponse,
    ConversationCreate, ConversationOut, MessageOut, SaveMessageRequest,
)
from app.vector_store import get_vector_store
from app.database import (
    init_db, create_conversation, get_conversations,
    get_conversation, update_conversation_title,
    delete_conversation, add_message, get_messages,
)
from app.auth import get_current_user, get_optional_user
from ingest import ingest_single_file

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI(title='Turkish Law RAG API', version='1.0.0')

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _sse_payload(payload: dict) -> str:
    return f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'


@app.on_event('startup')
async def on_startup() -> None:
    ensure_directories()
    await init_db()
    if not settings.ADMIN_API_KEY:
        logger.warning('ADMIN_API_KEY is missing from .env. Upload endpoints will be locked.')
    logger.info('Application startup complete')


try:
    rag_engine = RagEngine()
except Exception as exc:
    rag_engine = None
    logger.exception('RAG engine failed to initialize: %s', exc)


api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False)

def verify_admin_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail='Invalid or missing API Key.')
    return api_key


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


# ── Conversation CRUD ────────────────────────────────────────────────────────

@app.get('/conversations')
async def list_conversations(user: dict = Depends(get_current_user)) -> list[ConversationOut]:
    """List all conversations for the current user."""
    convs = await get_conversations(user['id'])
    return [ConversationOut(**c) for c in convs]


@app.post('/conversations')
async def create_new_conversation(
    body: ConversationCreate,
    user: dict = Depends(get_current_user),
) -> ConversationOut:
    """Create a new conversation."""
    conv = await create_conversation(user['id'], body.title)
    return ConversationOut(**conv)


@app.get('/conversations/{conversation_id}/messages')
async def list_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> list[MessageOut]:
    """Get all messages for a conversation."""
    conv = await get_conversation(conversation_id, user['id'])
    if not conv:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    msgs = await get_messages(conversation_id)
    return [MessageOut(**m) for m in msgs]


@app.post('/conversations/{conversation_id}/messages')
async def save_message(
    conversation_id: str,
    body: SaveMessageRequest,
    user: dict = Depends(get_current_user),
) -> MessageOut:
    """Save a message to a conversation."""
    conv = await get_conversation(conversation_id, user['id'])
    if not conv:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    msg = await add_message(conversation_id, body.role, body.content)
    return MessageOut(**msg)


@app.patch('/conversations/{conversation_id}')
async def rename_conversation(
    conversation_id: str,
    body: ConversationCreate,
    user: dict = Depends(get_current_user),
) -> dict:
    """Rename a conversation."""
    conv = await get_conversation(conversation_id, user['id'])
    if not conv:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    await update_conversation_title(conversation_id, body.title)
    return {'status': 'ok'}


@app.delete('/conversations/{conversation_id}')
async def remove_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Delete a conversation."""
    deleted = await delete_conversation(conversation_id, user['id'])
    if not deleted:
        raise HTTPException(status_code=404, detail='Conversation not found.')
    return {'status': 'deleted'}


# ── Admin Upload ─────────────────────────────────────────────────────────────

@app.post('/admin/upload')
async def admin_upload(
    file: UploadFile = File(...), 
    _: str = Depends(verify_admin_key)
) -> dict:
    if not file.filename or not file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail='Only JSON files are supported.')

    ensure_directories()
    
    save_path = Path(settings.DATA_DIR) / file.filename
    try:
        with open(save_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        logger.exception('Failed to save uploaded file')
        raise HTTPException(status_code=500, detail='Failed to save file on server.')

    try:
        vector_store = get_vector_store()
    except Exception as exc:
        logger.exception('Vector store load failed')
        raise HTTPException(status_code=500, detail='Failed to connect to vector database.')

    try:
        processed, added = ingest_single_file(vector_store, save_path)
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
    except Exception as exc:
        logger.exception('Ingestion failed for %s', file.filename)
        raise HTTPException(status_code=500, detail='File saved but ingestion failed.')

    return {
        'status': 'success',
        'message': f'File {file.filename} uploaded successfully.',
        'ingestion_stats': {
            'chunks_processed': processed,
            'chunks_added': added
        }
    }


# ── Chat Endpoint ────────────────────────────────────────────────────────────

@app.post('/chat')
async def chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    if rag_engine is None:
        raise HTTPException(status_code=500, detail='RAG engine is not initialized.')

    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail='Query cannot be empty.')

    messages, sources = rag_engine.prepare_messages(query)

    async def event_stream() -> AsyncGenerator[str, None]:
        answer_chunks: list[str] = []

        if messages is None:
            fallback = ChatResponse(answer=settings.NO_CONTEXT_MESSAGE, sources=[]).model_dump()
            yield _sse_payload({'type': 'token', 'token': settings.NO_CONTEXT_MESSAGE})
            yield _sse_payload({'type': 'final', 'data': fallback})
            yield _sse_payload({'type': 'done', 'ok': True})
            return

        try:
            async with asyncio.timeout(settings.CHAT_STREAM_TIMEOUT_SECONDS):
                async for token in rag_engine.stream_tokens(messages):
                    if await request.is_disconnected():
                        logger.info('Client disconnected during /chat stream.')
                        return
                    answer_chunks.append(token)
                    yield _sse_payload({'type': 'token', 'token': token})

            final_answer, final_sources = rag_engine.build_final_answer(''.join(answer_chunks), sources)
            final_payload = ChatResponse(answer=final_answer, sources=final_sources).model_dump()

            if await request.is_disconnected():
                logger.info('Client disconnected before final /chat payload.')
                return

            yield _sse_payload({'type': 'final', 'data': final_payload})
            yield _sse_payload({'type': 'done', 'ok': True})
        except TimeoutError:
            logger.warning('Chat stream timed out after %s seconds.', settings.CHAT_STREAM_TIMEOUT_SECONDS)
            partial_answer = ''.join(answer_chunks)
            if partial_answer.strip():
                final_answer, final_sources = rag_engine.build_final_answer(partial_answer, sources)
            else:
                final_answer, final_sources = settings.NO_CONTEXT_MESSAGE, []

            if await request.is_disconnected():
                return

            yield _sse_payload({'type': 'error', 'detail': 'Stream timeout'})
            yield _sse_payload(
                {'type': 'final', 'data': ChatResponse(answer=final_answer, sources=final_sources).model_dump()}
            )
            yield _sse_payload({'type': 'done', 'ok': False, 'reason': 'timeout'})
        except asyncio.CancelledError:
            logger.info('Chat stream cancelled.')
            return
        except Exception as exc:
            logger.exception('Chat endpoint stream error: %s', exc)
            partial_answer = ''.join(answer_chunks)
            if partial_answer.strip():
                final_answer, final_sources = rag_engine.build_final_answer(partial_answer, sources)
            else:
                final_answer, final_sources = settings.NO_CONTEXT_MESSAGE, []

            if await request.is_disconnected():
                return

            yield _sse_payload({'type': 'error', 'detail': 'Internal server error.'})
            yield _sse_payload(
                {'type': 'final', 'data': ChatResponse(answer=final_answer, sources=final_sources).model_dump()}
            )
            yield _sse_payload({'type': 'done', 'ok': False, 'reason': 'error'})

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )



@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
    logger.exception('Unhandled exception: %s', exc)
    return JSONResponse(status_code=500, content={'detail': 'Beklenmeyen bir hata olustu.'})
