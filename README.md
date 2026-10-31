# Galileo IA 2.0 — Prototipo educativo con voz

Tutor de Física para Bachillerato, inicialmente especializado en MRU. Responde con analogías adaptadas a los intereses del estudiante y promueve la comprensión paso a paso.

## Instalación local

Requisitos: Python 3.10+, Ollama instalado y suficiente memoria para ejecutar un modelo local.

```bash
ollama pull llama3.2:3b
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Abre http://127.0.0.1:8000 desde el equipo que ejecuta el servidor.

## Voz

La lectura de respuestas usa `speechSynthesis` y el micrófono usa `SpeechRecognition` o `webkitSpeechRecognition`. **No todos los navegadores y dispositivos admiten reconocimiento de voz.** La calidad, disponibilidad, voces y posible procesamiento remoto dependen del navegador. El micrófono en una web desplegada requiere HTTPS y permiso del usuario. No es una conversación de audio continua: el estudiante pulsa «Hablar» para cada turno. La síntesis de voz se puede detener.

## Arquitectura

- `frontend/`: interfaz adaptable para móvil y ordenador, texto y voz opcional.
- `backend/main.py`: API FastAPI que se comunica con Ollama.
- `backend/pedagogy.py`: instrucciones pedagógicas y socioemocionales.
- `tests/`: verificaciones de integridad básicas.

## Limitaciones importantes

- **No se ha validado todavía en iPhone ni desplegado en internet.**
- Ollama debe estar funcionando para que el modelo responda.
- La conversación se conserva solo en la memoria de la pestaña, no en una base de datos.
- No incluye animación labial, reconocimiento de voz universal ni conversación ininterrumpida.
- El modelo puede equivocarse en cálculos; antes de uso escolar real se debe agregar un verificador determinista y evaluación docente.
- No usar con estudiantes reales sin revisar privacidad, consentimiento, seguridad, límites de uso y política institucional.
- El código no contiene claves ni datos de alumnos. No expongas Ollama directamente a internet.

## Próximas fases

1. Pruebas pedagógicas y científicas supervisadas.
2. Voz robusta compatible con Safari iOS y otros navegadores mediante un servicio adecuado.
3. Motor de ejercicios y verificación matemática determinista.
4. Accesibilidad DUA, simulaciones y panel docente.
5. Despliegue seguro y conexión con el sitio web del proyecto.

## ElevenLabs (voz opcional)

La versión 2.1 incorpora un endpoint de voz en el servidor (`POST /api/voice`). El navegador solicita el audio al servidor; **la clave API nunca se entrega al navegador**. Si ElevenLabs no está configurado o falla, la interfaz intenta utilizar la voz integrada del navegador.

Configura en el entorno privado del servidor (NO en GitHub):

```bash
export ELEVENLABS_API_KEY='tu-clave-nueva-y-privada'
export ELEVENLABS_VOICE_ID='identificador-de-la-voz-elegida'
# Opcional:
export ELEVENLABS_MODEL_ID='eleven_multilingual_v2'
```

En Windows PowerShell, utiliza `$env:ELEVENLABS_API_KEY="..."` y equivalentes. El servicio de ElevenLabs consume créditos por generación de audio. La voz sigue siendo por turnos y requiere permiso de reproducción de audio en el navegador. Para producción: agregar autenticación, límites por usuario, controles de gasto, registro seguro y protección frente a abuso. No reutilices claves expuestas en conversaciones.
