import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from pedagogy import SYSTEM_PROMPT


# Todos los archivos de Galileo están actualmente
# en la raíz del repositorio.
ROOT = Path(__file__).resolve().parent

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:3b"
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat"
)

# Voz seleccionada para Galileo en ElevenLabs
ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID",
    "j9RedbMRSNQ74PyikQwD"
)

ELEVENLABS_MODEL_ID = os.getenv(
    "ELEVENLABS_MODEL_ID",
    "eleven_multilingual_v2"
)


app = FastAPI(
    title="Galileo IA",
    version="2.1.1"
)


class Turn(BaseModel):
    role: str
    content: str = Field(
        min_length=1,
        max_length=2000
    )


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000
    )

    history: list[Turn] = Field(
        default_factory=list,
        max_length=12
    )


class SpeechRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=1500
    )


@app.get("/")
def index():
    return FileResponse(
        ROOT / "index.html"
    )


@app.get("/app.js")
def javascript():
    return FileResponse(
        ROOT / "app.js",
        media_type="application/javascript"
    )


@app.get("/style.css")
def css():
    return FileResponse(
        ROOT / "style.css",
        media_type="text/css"
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "brain_model": OLLAMA_MODEL,
        "elevenlabs_configured": bool(
            os.getenv("ELEVENLABS_API_KEY")
        ),
        "voice_id": ELEVENLABS_VOICE_ID
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):

    history = [
        turn.model_dump()
        for turn in req.history
        if turn.role in (
            "user",
            "assistant"
        )
    ][-10:]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        *history,
        {
            "role": "user",
            "content": req.message
        }
    ]

    try:
        async with httpx.AsyncClient(
            timeout=90
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.55
                    }
                }
            )

            response.raise_for_status()

            data = response.json()

            answer = (
                data["message"]["content"]
                .strip()
            )

            if not answer:
                raise ValueError(
                    "Respuesta vacía del modelo"
                )

    except (
        httpx.HTTPError,
        KeyError,
        ValueError
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo contactar "
                "con el cerebro de Galileo."
            )
        ) from exc

    return {
        "answer": answer
    }


@app.get("/api/voice/status")
def voice_status():

    return {
        "elevenlabs_available": bool(
            os.getenv(
                "ELEVENLABS_API_KEY"
            )
        ),
        "voice_id": ELEVENLABS_VOICE_ID,
        "model_id": ELEVENLABS_MODEL_ID
    }


@app.post("/api/voice")
async def voice(
    req: SpeechRequest
):

    api_key = os.getenv(
        "ELEVENLABS_API_KEY"
    )

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "La API de ElevenLabs "
                "todavía no está configurada."
            )
        )

    elevenlabs_url = (
        "https://api.elevenlabs.io/"
        "v1/text-to-speech/"
        f"{ELEVENLABS_VOICE_ID}"
    )

    try:
        async with httpx.AsyncClient(
            timeout=45
        ) as client:

            result = await client.post(
                elevenlabs_url,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type":
                        "application/json",
                    "Accept":
                        "audio/mpeg"
                },
                json={
                    "text": req.text,
                    "model_id":
                        ELEVENLABS_MODEL_ID,
                    "voice_settings": {
                        "stability": 0.55,
                        "similarity_boost":
                            0.75,
                        "style": 0.25,
                        "use_speaker_boost":
                            True
                    }
                }
            )

            result.raise_for_status()

            if not result.content:
                raise ValueError(
                    "ElevenLabs devolvió "
                    "un audio vacío"
                )

    except (
        httpx.HTTPError,
        ValueError
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo generar "
                "la voz de Galileo "
                "con ElevenLabs."
            )
        ) from exc

    return Response(
        content=result.content,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store"
        }
    )
