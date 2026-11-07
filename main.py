
import base64
import json
import os

from pathlib import Path
from typing import Literal

import httpx

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)

from fastapi.responses import FileResponse

from pydantic import BaseModel, Field

from pedagogy import SYSTEM_PROMPT


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

ROOT = Path(__file__).resolve().parent


# =========================================================
# GEMINI
# =========================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite",
)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


# =========================================================
# APLICACIÓN
# =========================================================

app = FastAPI(
    title="Galileo IA",
    version="4.0.0",
)


# =========================================================
# MODELOS DE DATOS
# =========================================================

class Turn(BaseModel):

    role: str

    content: str = Field(
        min_length=1,
        max_length=2000,
    )


class ChatRequest(BaseModel):

    message: str = Field(
        min_length=1,
        max_length=2000,
    )

    history: list[Turn] = Field(
        default_factory=list,
        max_length=12,
    )


class ActivityRequest(BaseModel):

    mode: Literal[
        "quiz",
        "simulation",
        "game",
        "animation",
    ]

    topic: str = Field(
        default="MRU",
        max_length=100,
    )

    history: list[Turn] = Field(
        default_factory=list,
        max_length=10,
    )


# =========================================================
# ARCHIVOS WEB
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
        media_type="application/javascript",
    )


@app.get("/style.css")
def css():

    return FileResponse(
        ROOT / "style.css",
        media_type="text/css",
    )


# =========================================================
# ESTADO DE GALILEO
# =========================================================

@app.get("/health")
def health():

    return {

        "status": "ok",

        "version": "4.0.0",

        "brain_provider":
            "Google Gemini",

        "brain_model":
            GEMINI_MODEL,

        "gemini_configured":
            bool(
                os.getenv(
                    "GEMINI_API_KEY"
                )
            ),

        "speech_input":
            "Gemini audio",

        "speech_output":
            "voz del dispositivo",

        "learning_modes": [
            "tutor",
            "quiz",
            "simulation",
            "game",
            "animation",
        ],
    }


# =========================================================
# UTILIDADES GEMINI
# =========================================================

def get_api_key() -> str:

    key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not key:

        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini todavía "
                "no está configurado."
            ),
        )

    return key


def extract_text(
    data: dict,
) -> str:

    try:

        parts = (
            data["candidates"][0]
            ["content"]["parts"]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ) as exc:

        raise ValueError(
            "Gemini no devolvió contenido."
        ) from exc


    text = "".join(

        part.get(
            "text",
            ""
        )

        for part in parts

        if isinstance(
            part,
            dict
        )

        and not part.get(
            "thought",
            False
        )

    ).strip()


    if not text:

        text = "".join(

            part.get(
                "text",
                ""
            )

            for part in parts

            if isinstance(
                part,
                dict
            )

        ).strip()


    if not text:

        raise ValueError(
            "Gemini devolvió texto vacío."
        )


    return text


async def call_gemini(
    payload: dict,
    timeout: int = 60,
) -> dict:

    try:

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.post(

                GEMINI_API_URL,

                headers={

                    "x-goog-api-key":
                        get_api_key(),

                    "Content-Type":
                        "application/json",
                },

                json=payload,
            )


            response.raise_for_status()

            return response.json()


    except httpx.HTTPStatusError as exc:

        detail = (
            "Gemini rechazó la solicitud."
        )

        try:

            error_data = (
                exc.response.json()
            )

            google_error = (
                error_data
                .get(
                    "error",
                    {}
                )
                .get(
                    "message"
                )
            )

            if google_error:

                detail = (
                    google_error
                )

        except Exception:

            pass


        raise HTTPException(
            status_code=503,
            detail=detail,
        ) from exc


    except httpx.HTTPError as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo conectar "
                "con Gemini."
            ),
        ) from exc


# =========================================================
# CONVERSACIÓN SOCRÁTICA
# =========================================================

def build_chat_contents(
    req: ChatRequest,
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
                        "text":
                            turn.content
                    }
                ],
            }
        )


    contents.append(
        {

            "role": "user",

            "parts": [
                {
                    "text":
                        req.message
                }
            ],
        }
    )


    return contents


@app.post("/api/chat")
async def chat(
    req: ChatRequest,
):

    payload = {

        "systemInstruction": {

            "parts": [
                {
                    "text":
                        SYSTEM_PROMPT
                }
            ],
        },

        "contents":
            build_chat_contents(
                req
            ),

        "generationConfig": {

            "temperature":
                0.65,

            "maxOutputTokens":
                700,
        },
    }


    data = await call_gemini(
        payload
    )


    try:

        answer = extract_text(
            data
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


    return {
        "answer": answer
    }


# =========================================================
# VOZ -> TEXTO CON GEMINI
# =========================================================

@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
):

    audio_bytes = await audio.read()


    if not audio_bytes:

        raise HTTPException(
            status_code=400,
            detail=(
                "El audio está vacío."
            ),
        )


    if len(audio_bytes) > (
        15 * 1024 * 1024
    ):

        raise HTTPException(
            status_code=413,
            detail=(
                "El audio es demasiado grande."
            ),
        )


    mime_type = (
        audio.content_type
        or "audio/wav"
    )


    if not mime_type.startswith(
        "audio/"
    ):

        mime_type = (
            "audio/wav"
        )


    encoded_audio = (
        base64
        .b64encode(
            audio_bytes
        )
        .decode(
            "ascii"
        )
    )


    payload = {

        "contents": [

            {

                "role": "user",

                "parts": [

                    {

                        "text": (
                            "Transcribe literalmente "
                            "este audio en español. "
                            "Devuelve únicamente "
                            "las palabras que escuches. "
                            "No respondas la pregunta. "
                            "No agregues explicaciones. "
                            "No uses comillas. "
                            "Si no hay voz inteligible, "
                            "devuelve exactamente "
                            "NO_ENTENDIDO."
                        )
                    },

                    {

                        "inlineData": {

                            "mimeType":
                                mime_type,

                            "data":
                                encoded_audio,
                        }
                    },
                ],
            }
        ],

        "generationConfig": {

            "temperature":
                0,

            "maxOutputTokens":
                300,
        },
    }


    data = await call_gemini(
        payload,
        timeout=60,
    )


    try:

        text = extract_text(
            data
        ).strip()

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=(
                "No pude entender tu voz."
            ),
        ) from exc


    if (
        not text

        or text
        .upper()
        .strip()
        == "NO_ENTENDIDO"
    ):

        raise HTTPException(
            status_code=422,
            detail=(
                "No pude entenderte. "
                "Habla un poco más cerca "
                "del micrófono."
            ),
        )


    return {
        "text": text
    }


# =========================================================
# HISTORIAL PARA PERSONALIZACIÓN
# =========================================================

def history_summary(
    history: list[Turn],
) -> str:

    if not history:

        return (
            "No existe conversación "
            "previa con el estudiante."
        )


    lines = []


    for turn in history[-8:]:

        if turn.role == "user":

            speaker = (
                "Estudiante"
            )

        else:

            speaker = (
                "Galileo"
            )


        content = (
            turn.content[:500]
        )


        lines.append(
            f"{speaker}: "
            f"{content}"
        )


    return "\n".join(
        lines
    )


# =========================================================
# ESQUEMA QUIZ
# =========================================================

QUIZ_SCHEMA = {

    "type": "object",

    "properties": {

        "type": {

            "type": "string",

            "enum": [
                "quiz"
            ],
        },

        "title": {
            "type": "string",
        },

        "question": {
            "type": "string",
        },

        "options": {

            "type": "array",

            "items": {
                "type": "string",
            },

            "minItems": 4,
            "maxItems": 4,
        },

        "correct_index": {

            "type": "integer",

            "minimum": 0,
            "maximum": 3,
        },

        "explanation": {
            "type": "string",
        },

        "hint": {
            "type": "string",
        },
    },

    "required": [

        "type",
        "title",
        "question",
        "options",
        "correct_index",
        "explanation",
        "hint",
    ],
}


# =========================================================
# ESQUEMA SIMULADOR
# =========================================================

SIMULATION_SCHEMA = {

    "type": "object",

    "properties": {

        "type": {

            "type": "string",

            "enum": [
                "simulation"
            ],
        },

        "title": {
            "type": "string",
        },

        "description": {
            "type": "string",
        },

        "emoji": {
            "type": "string",
        },

        "x0": {
            "type": "number",
        },

        "velocity": {
            "type": "number",
        },

        "duration": {
            "type": "number",
        },

        "unit": {
            "type": "string",
        },
    },

    "required": [

        "type",
        "title",
        "description",
        "emoji",
        "x0",
        "velocity",
        "duration",
        "unit",
    ],
}


# =========================================================
# ESQUEMA JUEGO
# =========================================================

GAME_SCHEMA = {

    "type": "object",

    "properties": {

        "type": {

            "type": "string",

            "enum": [
                "game"
            ],
        },

        "title": {
            "type": "string",
        },

        "story": {
            "type": "string",
        },

        "question": {
            "type": "string",
        },

        "answer": {
            "type": "number",
        },

        "tolerance": {
            "type": "number",
        },

        "hint": {
            "type": "string",
        },

        "emoji": {
            "type": "string",
        },
    },

    "required": [

        "type",
        "title",
        "story",
        "question",
        "answer",
        "tolerance",
        "hint",
        "emoji",
    ],
}


# =========================================================
# ESQUEMA ANIMACIÓN
# =========================================================

ANIMATION_SCHEMA = {

    "type": "object",

    "properties": {

        "type": {

            "type": "string",

            "enum": [
                "animation"
            ],
        },

        "title": {
            "type": "string",
        },

        "description": {
            "type": "string",
        },

        "emoji": {
            "type": "string",
        },

        "x0": {
            "type": "number",
        },

        "velocity": {
            "type": "number",
        },

        "duration": {
            "type": "number",
        },
    },

    "required": [

        "type",
        "title",
        "description",
        "emoji",
        "x0",
        "velocity",
        "duration",
    ],
}


ACTIVITY_SCHEMAS = {

    "quiz":
        QUIZ_SCHEMA,

    "simulation":
        SIMULATION_SCHEMA,

    "game":
        GAME_SCHEMA,

    "animation":
        ANIMATION_SCHEMA,
}


# =========================================================
# INSTRUCCIONES PARA ACTIVIDADES
# =========================================================

def activity_instructions(
    mode: str,
) -> str:

    common = """
Crea una actividad educativa sobre Movimiento
Rectilíneo Uniforme para un estudiante de Bachillerato.

Debe ser científicamente correcta.

Utiliza unidades coherentes.

La actividad debe ayudar al estudiante a razonar,
no solamente memorizar una fórmula.

Adapta el contexto a los intereses detectados en
la conversación previa cuando sea posible.

No utilices siempre el mismo personaje.

Puedes utilizar:

deportes,
videojuegos,
animales,
vehículos,
trenes,
aviones,
viajes,
ciencia ficción,
superhéroes,
personajes imaginarios,
situaciones cotidianas,
o cualquier contexto apropiado.

No generes HTML.
No generes JavaScript.
No generes Markdown.
Devuelve solamente los datos solicitados.
"""


    if mode == "quiz":

        return common + """
Genera UNA pregunta de opción múltiple.

Debe tener exactamente cuatro opciones.

Solo una opción debe ser correcta.

Incluye una pista socrática que ayude sin revelar
la respuesta.

Incluye una explicación breve de la respuesta
correcta.

La pregunta puede ser conceptual o numérica.
"""


    if mode == "simulation":

        return common + """
Diseña una simulación sencilla de MRU.

El objeto debe moverse en línea recta.

La velocidad debe permanecer constante.

Usa una velocidad positiva entre 1 y 30 metros
por segundo.

La duración debe estar entre 3 y 20 segundos.

El emoji debe representar el objeto que se mueve.

La descripción debe explicar qué debería observar
el estudiante durante la simulación.
"""


    if mode == "game":

        return common + """
Crea una misión matemática basada en MRU.

Debe existir una respuesta numérica única.

El estudiante debe resolver el desafío utilizando
distancia, desplazamiento, velocidad, tiempo o
posición.

La historia debe ser breve y entretenida.

Incluye una pista que no revele directamente la
respuesta.

Usa tolerance igual a 0.1 normalmente.
"""


    if mode == "animation":

        return common + """
Diseña una pequeña animación educativa de MRU.

Debe existir un objeto desplazándose en línea recta.

La velocidad debe ser constante.

Utiliza una velocidad y duración sencillas.

La descripción debe explicar claramente qué
representa el movimiento y cómo se relaciona con
el MRU.
"""


    raise ValueError(
        "Modo de actividad inválido."
    )


# =========================================================
# GENERADOR DE ACTIVIDADES
# =========================================================

@app.post("/api/activity")
async def create_activity(
    req: ActivityRequest,
):

    try:

        schema = (
            ACTIVITY_SCHEMAS[
                req.mode
            ]
        )

    except KeyError as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                "Modo de actividad inválido."
            ),
        ) from exc


    prompt = f"""
{activity_instructions(req.mode)}

TEMA:
{req.topic}

CONVERSACIÓN RECIENTE:

{history_summary(req.history)}

MODO SOLICITADO:
{req.mode}

Genera una actividad nueva y diferente.
"""


    payload = {

        "systemInstruction": {

            "parts": [
                {
                    "text":
                        SYSTEM_PROMPT
                }
            ],
        },

        "contents": [

            {

                "role": "user",

                "parts": [
                    {
                        "text":
                            prompt
                    }
                ],
            }
        ],

        "generationConfig": {

            "temperature":
                0.8,

            "maxOutputTokens":
                1200,

            "responseMimeType":
                "application/json",

            "responseJsonSchema":
                schema,
        },
    }


    data = await call_gemini(
        payload,
        timeout=60,
    )


    try:

        raw = extract_text(
            data
        )


        activity = json.loads(
            raw
        )


    except (
        ValueError,
        json.JSONDecodeError,
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "Galileo no pudo construir "
                "la actividad."
            ),
        ) from exc


    if (
        activity.get("type")
        != req.mode
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "La actividad generada "
                "no coincide con el modo solicitado."
            ),
        )


    return activity
