import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from pedagogy import SYSTEM_PROMPT


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

ROOT = Path(__file__).resolve().parent


# =========================================================
# CEREBRO ONLINE: GOOGLE GEMINI
# =========================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


# =========================================================
# VOZ: ELEVENLABS
# =========================================================

ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID",
    "j9RedbMRSNQ74PyikQwD"
)

ELEVENLABS_MODEL_ID = os.getenv(
    "ELEVENLABS_MODEL_ID",
    "eleven_multilingual_v2"
)


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="Galileo IA",
    version="3.0.0"
)


# =========================================================
# MODELOS DE DATOS
# =========================================================

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


# =========================================================
# INTERFAZ WEB
# =========================================================

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


# =========================================================
# ESTADO DE GALILEO
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "brain_provider": "Google Gemini",
        "brain_model": GEMINI_MODEL,

        "gemini_configured": bool(
            os.getenv("GEMINI_API_KEY")
        ),

        "elevenlabs_configured": bool(
            os.getenv("ELEVENLABS_API_KEY")
        ),

        "voice_id": ELEVENLABS_VOICE_ID
    }


# =========================================================
# PREPARAR CONVERSACIÓN PARA GEMINI
# =========================================================

def build_gemini_contents(
    req: ChatRequest
):

    contents = []

    for turn in req.history[-10:]:

        if turn.role == "user":
            role = "user"

        elif turn.role == "assistant":
            role = "model"

        else:
            continue

        contents.append(
            {
                "role": role,
                "parts": [
                    {
                        "text": turn.content
                    }
                ]
            }
        )

    contents.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": req.message
                }
            ]
        }
    )

    return contents


# =========================================================
# CEREBRO DE GALILEO
# =========================================================

@app.post("/api/chat")
async def chat(
    req: ChatRequest
):

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:

        raise HTTPException(
            status_code=503,
            detail=(
                "La API de Gemini "
                "todavía no está configurada."
            )
        )


    payload = {

        "systemInstruction": {
            "parts": [
                {
                    "text": SYSTEM_PROMPT
                }
            ]
        },

        "contents":
            build_gemini_contents(req),

        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": 700
        }
    }


    try:

        async with httpx.AsyncClient(
            timeout=60
        ) as client:

            response = await client.post(
                GEMINI_API_URL,

                headers={
                    "x-goog-api-key":
                        api_key,

                    "Content-Type":
                        "application/json"
                },

                json=payload
            )


            response.raise_for_status()

            data = response.json()


            candidate = (
                data["candidates"][0]
                ["content"]
                ["parts"]
            )


            answer = "".join(
                part.get(
                    "text",
                    ""
                )
                for part in candidate
            ).strip()


            if not answer:

                raise ValueError(
                    "Gemini devolvió "
                    "una respuesta vacía"
                )


    except (
        httpx.HTTPError,
        KeyError,
        IndexError,
        ValueError
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo contactar "
                "con el cerebro online "
                "de Galileo."
            )
        ) from exc


    return {
        "answer": answer
    }


# =========================================================
# ESTADO DE LA VOZ
# =========================================================

@app.get("/api/voice/status")
def voice_status():

    return {

        "elevenlabs_available":
            bool(
                os.getenv(
                    "ELEVENLABS_API_KEY"
                )
            ),

        "voice_id":
            ELEVENLABS_VOICE_ID,

        "model_id":
            ELEVENLABS_MODEL_ID
    }


# =========================================================
# VOZ DE GALILEO CON ELEVENLABS
# =========================================================

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

                    "xi-api-key":
                        api_key,

                    "Content-Type":
                        "application/json",

                    "Accept":
                        "audio/mpeg"
                },

                json={

                    "text":
                        req.text,

                    "model_id":
                        ELEVENLABS_MODEL_ID,

                    "voice_settings": {

                        "stability":
                            0.55,

                        "similarity_boost":
                            0.75,

                        "style":
                            0.25,

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
            "Cache-Control":
                "no-store"
        }
    )
