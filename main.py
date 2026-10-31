import os
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .pedagogy import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434/api/chat')
app = FastAPI(title='Galileo IA 2.0')

class Turn(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=2000)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=12)

@app.get('/')
def index():
    return FileResponse(ROOT / 'frontend/index.html')

@app.get('/app.js')
def js():
    return FileResponse(ROOT / 'frontend/app.js', media_type='application/javascript')

@app.get('/style.css')
def css():
    return FileResponse(ROOT / 'frontend/style.css', media_type='text/css')

@app.get('/health')
def health():
    return {'status': 'ok', 'model': MODEL}

@app.post('/api/chat')
async def chat(req: ChatRequest):
    # Never accept a client-provided system prompt or arbitrary roles.
    history = [t.model_dump() for t in req.history if t.role in ('user', 'assistant')][-10:]
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}, *history, {'role': 'user', 'content': req.message}]
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(URL, json={'model': MODEL, 'messages': messages, 'stream': False, 'options': {'temperature': 0.55}})
            response.raise_for_status()
            answer = response.json()['message']['content'].strip()
            if not answer:
                raise ValueError('Empty model response')
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(503, 'No se pudo contactar con el modelo. Comprueba Ollama y el modelo instalado.') from exc
    return {'answer': answer}

class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)

@app.get('/api/voice/status')
def voice_status():
    return {'elevenlabs_available': bool(os.getenv('ELEVENLABS_API_KEY') and os.getenv('ELEVENLABS_VOICE_ID'))}

@app.post('/api/voice')
async def voice(req: SpeechRequest):
    from fastapi.responses import Response
    key = os.getenv('ELEVENLABS_API_KEY')
    voice_id = os.getenv('ELEVENLABS_VOICE_ID')
    if not key or not voice_id:
        raise HTTPException(503, 'La voz de ElevenLabs no está configurada.')
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            result = await client.post(
                f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
                headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'},
                json={'text': req.text, 'model_id': os.getenv('ELEVENLABS_MODEL_ID', 'eleven_multilingual_v2')},
            )
            result.raise_for_status()
            if not result.content:
                raise ValueError('Empty audio')
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, 'No se pudo generar audio con ElevenLabs.') from exc
    return Response(content=result.content, media_type='audio/mpeg', headers={'Cache-Control': 'no-store'})
