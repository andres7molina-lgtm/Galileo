const chat = document.querySelector('#chat');
const form = document.querySelector('#form');
const input = document.querySelector('#message');
const send = document.querySelector('#send');
const stopButton = document.querySelector('#stop');
const speak = document.querySelector('#speak');

const status = document.querySelector('#status');

const galileoHud = document.querySelector('#galileoHud');
const galileoOrb = document.querySelector('#galileoOrb');
const galileoState = document.querySelector('#galileoState');

const activityArea = document.querySelector('#activityArea');
const modeDescription = document.querySelector('#modeDescription');
const modeButtons = document.querySelectorAll('[data-mode]');

const history = [];

let currentMode = 'tutor';
let busy = false;
let recording = false;

let microphoneStream = null;
let audioContext = null;
let sourceNode = null;
let processorNode = null;
let silentGain = null;

let recordedBuffers = [];
let sampleRate = 44100;
let autoStopTimer = null;


/* =========================================
   ESTADOS VISUALES DE GALILEO
========================================= */

function setGalileoState(state, text) {

    galileoHud.classList.remove(
        'listening',
        'thinking',
        'speaking'
    );

    if (state !== 'idle') {
        galileoHud.classList.add(state);
    }

    galileoState.textContent = text;
}


/* =========================================
   CHAT
========================================= */

function bubble(text, who) {

    const element = document.createElement('div');

    element.className = 'bubble ' + who;
    element.textContent = text;

    chat.appendChild(element);

    chat.scrollTop = chat.scrollHeight;

    return element;
}


/* =========================================
   VOZ DE GALILEO
========================================= */

function stopVoice() {

    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }

    setGalileoState(
        'idle',
        'Toca GALILEO para hablar'
    );
}


function getSpanishVoice() {

    const voices =
        window.speechSynthesis.getVoices();

    const preferredLanguages = [
        'es-EC',
        'es-MX',
        'es-US',
        'es-419',
        'es-ES',
        'es'
    ];

    for (const language of preferredLanguages) {

        const voice = voices.find(
            item =>
                item.lang.toLowerCase() ===
                language.toLowerCase()
        );

        if (voice) {
            return voice;
        }
    }

    return voices.find(
        item =>
            item.lang
                .toLowerCase()
                .startsWith('es')
    ) || null;
}


function say(text) {

    if (!speak.checked) {

        setGalileoState(
            'idle',
            'Toca GALILEO para hablar'
        );

        return;
    }

    if (!('speechSynthesis' in window)) {

        status.textContent =
            'Este dispositivo no tiene voz disponible.';

        return;
    }

    stopVoice();

    const utterance =
        new SpeechSynthesisUtterance(
            text.replace(/[*#_`]/g, '')
        );

    const voice =
        getSpanishVoice();

    if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
    } else {
        utterance.lang = 'es-EC';
    }

    utterance.rate = 0.94;
    utterance.pitch = 1;

    utterance.onstart = () => {

        setGalileoState(
            'speaking',
            'Galileo está hablando'
        );

        status.textContent =
            'Galileo está hablando.';
    };

    utterance.onend = () => {

        setGalileoState(
            'idle',
            'Toca GALILEO para hablar'
        );

        status.textContent =
            'Puedes seguir preguntando.';
    };

    utterance.onerror = () => {

        setGalileoState(
            'idle',
            'Respuesta disponible en pantalla'
        );
    };

    window.speechSynthesis.speak(
        utterance
    );
}


/* =========================================
   CONVERSACIÓN CON GEMINI
========================================= */

async function ask(message) {

    if (
        busy ||
        !message.trim()
    ) {
        return;
    }

    busy = true;
    send.disabled = true;
    input.value = '';

    bubble(
        message,
        'student'
    );

    const reply =
        bubble(
            'Galileo está pensando…',
            'bot'
        );

    setGalileoState(
        'thinking',
        'Galileo está pensando…'
    );

    status.textContent =
        'Preparando una explicación...';

    try {

        const response =
            await fetch(
                '/api/chat',
                {
                    method: 'POST',

                    headers: {
                        'Content-Type':
                            'application/json'
                    },

                    body:
                        JSON.stringify({
                            message: message,
                            history:
                                history.slice(-10)
                        })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                'No se pudo conectar con Galileo.'
            );
        }

        reply.textContent =
            data.answer;

        history.push(
            {
                role: 'user',
                content: message
            },
            {
                role: 'assistant',
                content: data.answer
            }
        );

        say(
            data.answer
        );

    } catch (error) {

        reply.textContent =
            'No pude responder ahora. '
            + 'Inténtalo nuevamente.';

        status.textContent =
            error.message;

        setGalileoState(
            'idle',
            'Toca GALILEO para intentarlo otra vez'
        );

    } finally {

        busy = false;
        send.disabled = false;
    }
}


/* =========================================
   MICRÓFONO
========================================= */

async function startRecording() {

    if (busy) {
        return;
    }

    if (
        !navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia
    ) {

        status.textContent =
            'Este navegador no permite usar el micrófono.';

        return;
    }

    try {

        stopVoice();

        microphoneStream =
            await navigator
                .mediaDevices
                .getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        channelCount: 1
                    }
                });

        audioContext =
            new (
                window.AudioContext ||
                window.webkitAudioContext
            )();

        await audioContext.resume();

        sampleRate =
            audioContext.sampleRate;

        sourceNode =
            audioContext
                .createMediaStreamSource(
                    microphoneStream
                );

        processorNode =
            audioContext
                .createScriptProcessor(
                    4096,
                    1,
                    1
                );

        silentGain =
            audioContext
                .createGain();

        silentGain.gain.value = 0;

        recordedBuffers = [];
        recording = true;

        processorNode.onaudioprocess =
            event => {

                if (!recording) {
                    return;
                }

                const channel =
                    event.inputBuffer
                        .getChannelData(0);

                recordedBuffers.push(
                    new Float32Array(
                        channel
                    )
                );
            };

        sourceNode.connect(
            processorNode
        );

        processorNode.connect(
            silentGain
        );

        silentGain.connect(
            audioContext.destination
        );

        setGalileoState(
            'listening',
            'Te estoy escuchando…'
        );

        status.textContent =
            'Habla ahora. '
            + 'Toca GALILEO otra vez para terminar.';

        autoStopTimer =
            setTimeout(
                () => {

                    if (recording) {
                        stopRecording();
                    }

                },
                20000
            );

    } catch (error) {

        setGalileoState(
            'idle',
            'Toca GALILEO para hablar'
        );

        status.textContent =
            'Debes permitir el acceso al micrófono.';
    }
}


async function stopRecording() {

    if (!recording) {
        return;
    }

    recording = false;

    clearTimeout(
        autoStopTimer
    );

    setGalileoState(
        'thinking',
        'Entendiendo tu voz…'
    );

    status.textContent =
        'Procesando lo que dijiste...';

    processorNode.onaudioprocess = null;

    processorNode.disconnect();
    sourceNode.disconnect();
    silentGain.disconnect();

    microphoneStream
        .getTracks()
        .forEach(
            track => track.stop()
        );

    const wavBlob =
        createWavBlob(
            recordedBuffers,
            sampleRate
        );

    await audioContext.close();

    await sendAudio(
        wavBlob
    );
}


/* =========================================
   CREAR WAV 16 kHz
========================================= */

function mergeBuffers(buffers) {

    let length = 0;

    buffers.forEach(
        buffer => {
            length += buffer.length;
        }
    );

    const result =
        new Float32Array(
            length
        );

    let offset = 0;

    buffers.forEach(
        buffer => {

            result.set(
                buffer,
                offset
            );

            offset +=
                buffer.length;
        }
    );

    return result;
}


function downsample(
    buffer,
    inputRate,
    outputRate
) {

    if (
        inputRate === outputRate
    ) {
        return buffer;
    }

    const ratio =
        inputRate / outputRate;

    const newLength =
        Math.round(
            buffer.length / ratio
        );

    const result =
        new Float32Array(
            newLength
        );

    let resultOffset = 0;
    let bufferOffset = 0;

    while (
        resultOffset <
        result.length
    ) {

        const nextOffset =
            Math.round(
                (resultOffset + 1)
                * ratio
            );

        let total = 0;
        let count = 0;

        for (
            let i = bufferOffset;
            i < nextOffset
            && i < buffer.length;
            i++
        ) {

            total +=
                buffer[i];

            count++;
        }

        result[resultOffset] =
            count
                ? total / count
                : 0;

        resultOffset++;

        bufferOffset =
            nextOffset;
    }

    return result;
}


function createWavBlob(
    buffers,
    originalRate
) {

    const merged =
        mergeBuffers(
            buffers
        );

    const samples =
        downsample(
            merged,
            originalRate,
            16000
        );

    const arrayBuffer =
        new ArrayBuffer(
            44 +
            samples.length * 2
        );

    const view =
        new DataView(
            arrayBuffer
        );

    function writeString(
        offset,
        string
    ) {

        for (
            let i = 0;
            i < string.length;
            i++
        ) {

            view.setUint8(
                offset + i,
                string.charCodeAt(i)
            );
        }
    }

    writeString(
        0,
        'RIFF'
    );

    view.setUint32(
        4,
        36 + samples.length * 2,
        true
    );

    writeString(
        8,
        'WAVE'
    );

    writeString(
        12,
        'fmt '
    );

    view.setUint32(
        16,
        16,
        true
    );

    view.setUint16(
        20,
        1,
        true
    );

    view.setUint16(
        22,
        1,
        true
    );

    view.setUint32(
        24,
        16000,
        true
    );

    view.setUint32(
        28,
        32000,
        true
    );

    view.setUint16(
        32,
        2,
        true
    );

    view.setUint16(
        34,
        16,
        true
    );

    writeString(
        36,
        'data'
    );

    view.setUint32(
        40,
        samples.length * 2,
        true
    );

    let offset = 44;

    for (
        let i = 0;
        i < samples.length;
        i++
    ) {

        const sample =
            Math.max(
                -1,
                Math.min(
                    1,
                    samples[i]
                )
            );

        view.setInt16(
            offset,
            sample < 0
                ? sample * 0x8000
                : sample * 0x7FFF,
            true
        );

        offset += 2;
    }

    return new Blob(
        [view],
        {
            type: 'audio/wav'
        }
    );
}


/* =========================================
   TRANSCRIBIR CON GEMINI
========================================= */

async function sendAudio(blob) {

    const formData =
        new FormData();

    formData.append(
        'audio',
        blob,
        'pregunta.wav'
    );

    try {

        const response =
            await fetch(
                '/api/transcribe',
                {
                    method: 'POST',
                    body: formData
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.detail ||
                'No pude entender tu voz.'
            );
        }

        input.value =
            data.text;

        status.textContent =
            'Escuché: '
            + data.text;

        await ask(
            data.text
        );

    } catch (error) {

        status.textContent =
            error.message;

        setGalileoState(
            'idle',
            'Toca GALILEO para hablar'
        );
    }
}


/* =========================================
   MODOS DE APRENDIZAJE
========================================= */

const modeDescriptions = {

    tutor:
        'Galileo te guía mediante preguntas socráticas.',

    quiz:
        'Galileo genera un quiz adaptado a tu nivel.',

    simulation:
        'Experimenta cambiando velocidad, tiempo y posición.',

    game:
        'Aprende MRU mediante desafíos y misiones.',

    animation:
        'Observa el movimiento y las variables de forma visual.'
};


async function selectMode(
    mode,
    button
) {

    currentMode = mode;

    modeButtons.forEach(
        item =>
            item.classList.remove(
                'active'
            )
    );

    button.classList.add(
        'active'
    );

    modeDescription.textContent =
        modeDescriptions[mode];

    if (mode === 'tutor') {

        activityArea.hidden = true;

        return;
    }

    await generateActivity(
        mode
    );
}


async function generateActivity(
    mode
) {

    activityArea.hidden = false;

    activityArea.replaceChildren();

    const loading =
        document.createElement('p');

    loading.textContent =
        'Galileo está creando la actividad…';

    activityArea.appendChild(
        loading
    );

    setGalileoState(
        'thinking',
        'Creando actividad…'
    );

    try {

        const response =
            await fetch(
                '/api/activity',
                {
                    method: 'POST',

                    headers: {
                        'Content-Type':
                            'application/json'
                    },

                    body:
                        JSON.stringify({
                            mode: mode,
                            topic: 'MRU',
                            history:
                                history.slice(-8)
                        })
                }
            );

        const activity =
            await response.json();

        if (!response.ok) {

            throw new Error(
                activity.detail ||
                'No pude crear la actividad.'
            );
        }

        renderActivity(
            activity
        );

        setGalileoState(
            'idle',
            'Actividad lista'
        );

    } catch (error) {

        activityArea.replaceChildren();

        const errorText =
            document.createElement('p');

        errorText.textContent =
            error.message;

        activityArea.appendChild(
            errorText
        );

        setGalileoState(
            'idle',
            'Toca GALILEO para hablar'
        );
    }
}


/* =========================================
   RENDERIZAR ACTIVIDADES
========================================= */

function renderActivity(activity) {

    activityArea.replaceChildren();

    const title =
        document.createElement('h3');

    title.textContent =
        activity.title ||
        'Actividad Galileo';

    activityArea.appendChild(
        title
    );

    if (activity.type === 'quiz') {

        renderQuiz(activity);

    } else if (
        activity.type === 'simulation'
    ) {

        renderSimulation(activity);

    } else if (
        activity.type === 'game'
    ) {

        renderGame(activity);

    } else if (
        activity.type === 'animation'
    ) {

        renderAnimation(activity);

    } else {

        const text =
            document.createElement('p');

        text.textContent =
            activity.description ||
            'Actividad preparada.';

        activityArea.appendChild(
            text
        );
    }
}


/* =========================================
   QUIZ
========================================= */

function renderQuiz(activity) {

    const question =
        document.createElement('p');

    question.textContent =
        activity.question;

    question.style.fontWeight =
        '700';

    activityArea.appendChild(
        question
    );

    const feedback =
        document.createElement('p');

    activity.options.forEach(
        (option, index) => {

            const button =
                document.createElement(
                    'button'
                );

            button.textContent =
                option;

            button.style.margin =
                '5px';

            button.addEventListener(
                'click',
                () => {

                    if (
                        index ===
                        activity.correct_index
                    ) {

                        feedback.textContent =
                            '✅ Correcto. '
                            +
                            activity.explanation;

                    } else {

                        feedback.textContent =
                            '💡 Todavía no. '
                            +
                            (
                                activity.hint ||
                                'Piensa nuevamente en los datos.'
                            );
                    }
                }
            );

            activityArea.appendChild(
                button
            );
        }
    );

    activityArea.appendChild(
        feedback
    );
}


/* =========================================
   SIMULADOR
========================================= */

function renderSimulation(
    activity
) {

    const description =
        document.createElement('p');

    description.textContent =
        activity.description;

    activityArea.appendChild(
        description
    );

    const velocity =
        document.createElement('input');

    velocity.type =
        'range';

    velocity.min =
        '1';

    velocity.max =
        '30';

    velocity.value =
        activity.velocity || 5;

    const label =
        document.createElement('p');

    label.textContent =
        'Velocidad: '
        + velocity.value
        + ' m/s';

    velocity.addEventListener(
        'input',
        () => {

            label.textContent =
                'Velocidad: '
                + velocity.value
                + ' m/s';
        }
    );

    const track =
        document.createElement('div');

    track.style.position =
        'relative';

    track.style.height =
        '80px';

    track.style.margin =
        '18px 0';

    track.style.borderBottom =
        '3px solid #35d9ff';

    const object =
        document.createElement('div');

    object.textContent =
        activity.emoji ||
        '🚗';

    object.style.position =
        'absolute';

    object.style.left =
        '0';

    object.style.bottom =
        '5px';

    object.style.fontSize =
        '38px';

    track.appendChild(
        object
    );

    const play =
        document.createElement('button');

    play.textContent =
        '▶ Iniciar simulación';

    play.addEventListener(
        'click',
        () => {

            object.style.transition =
                'none';

            object.style.left =
                '0';

            requestAnimationFrame(
                () => {

                    requestAnimationFrame(
                        () => {

                            object.style.transition =
                                'left 4s linear';

                            object.style.left =
                                'calc(100% - 48px)';
                        }
                    );
                }
            );
        }
    );

    activityArea.append(
        label,
        velocity,
        track,
        play
    );
}


/* =========================================
   JUEGO
========================================= */

function renderGame(activity) {

    const story =
        document.createElement('p');

    story.textContent =
        activity.story;

    const question =
        document.createElement('p');

    question.textContent =
        activity.question;

    question.style.fontWeight =
        '700';

    const answer =
        document.createElement('input');

    answer.type =
        'number';

    answer.placeholder =
        'Tu respuesta';

    answer.style.padding =
        '10px';

    const check =
        document.createElement('button');

    check.textContent =
        'Comprobar';

    const feedback =
        document.createElement('p');

    check.addEventListener(
        'click',
        () => {

            const student =
                Number(
                    answer.value
                );

            const expected =
                Number(
                    activity.answer
                );

            const tolerance =
                Number(
                    activity.tolerance ||
                    0.01
                );

            if (
                Math.abs(
                    student -
                    expected
                )
                <= tolerance
            ) {

                feedback.textContent =
                    '🏆 ¡Misión cumplida!';

            } else {

                feedback.textContent =
                    '💡 '
                    +
                    (
                        activity.hint ||
                        'Revisa la relación entre distancia, velocidad y tiempo.'
                    );
            }
        }
    );

    activityArea.append(
        story,
        question,
        answer,
        check,
        feedback
    );
}


/* =========================================
   ANIMACIÓN
========================================= */

function renderAnimation(
    activity
) {

    const explanation =
        document.createElement('p');

    explanation.textContent =
        activity.description;

    const track =
        document.createElement('div');

    track.style.position =
        'relative';

    track.style.height =
        '100px';

    track.style.margin =
        '20px 0';

    track.style.borderBottom =
        '3px solid #22cfff';

    const object =
        document.createElement('div');

    object.textContent =
        activity.emoji ||
        '🚆';

    object.style.position =
        'absolute';

    object.style.bottom =
        '5px';

    object.style.left =
        '0';

    object.style.fontSize =
        '42px';

    track.appendChild(
        object
    );

    const play =
        document.createElement(
            'button'
        );

    play.textContent =
        '🎬 Reproducir';

    play.addEventListener(
        'click',
        () => {

            object.style.transition =
                'none';

            object.style.left =
                '0';

            requestAnimationFrame(
                () => {

                    requestAnimationFrame(
                        () => {

                            object.style.transition =
                                'left 5s linear';

                            object.style.left =
                                'calc(100% - 52px)';
                        }
                    );
                }
            );
        }
    );

    activityArea.append(
        explanation,
        track,
        play
    );
}


/* =========================================
   EVENTOS
========================================= */

form.addEventListener(
    'submit',
    event => {

        event.preventDefault();

        ask(
            input.value.trim()
        );
    }
);


galileoOrb.addEventListener(
    'click',
    () => {

        if (recording) {

            stopRecording();

        } else {

            startRecording();
        }
    }
);


stopButton.addEventListener(
    'click',
    () => {

        stopVoice();

        status.textContent =
            'Voz detenida.';
    }
);


modeButtons.forEach(
    button => {

        button.addEventListener(
            'click',
            () => {

                selectMode(
                    button.dataset.mode,
                    button
                );
            }
        );
    }
);


if (
    'speechSynthesis'
    in window
) {

    window.speechSynthesis
        .getVoices();
}


setGalileoState(
    'idle',
    'Toca GALILEO para hablar'
);
