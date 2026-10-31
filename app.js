const chat=document.querySelector('#chat');
const form=document.querySelector('#form');
const input=document.querySelector('#message');
const send=document.querySelector('#send');
const mic=document.querySelector('#mic');
const status=document.querySelector('#status');
const speak=document.querySelector('#speak');
const history=[];
let busy=false;
function bubble(text,who){const el=document.createElement('div');el.className='bubble '+who;el.textContent=text;chat.appendChild(el);chat.scrollTop=chat.scrollHeight;return el;}
let activeAudio=null;
let audioUrl=null;
function stopVoice(){
  if(activeAudio){activeAudio.pause();activeAudio=null;}
  if(audioUrl){URL.revokeObjectURL(audioUrl);audioUrl=null;}
  if('speechSynthesis' in window)window.speechSynthesis.cancel();
}
function browserVoice(text){
  if(!('speechSynthesis' in window))return;
  const utterance=new SpeechSynthesisUtterance(text.replace(/[*#_`]/g,''));
  utterance.lang='es-ES';utterance.rate=.94;window.speechSynthesis.speak(utterance);
}
async function say(text){
  if(!speak.checked)return;
  stopVoice();
  try{
    const r=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text.slice(0,1500)})});
    if(!r.ok)throw new Error('ElevenLabs no disponible');
    const blob=await r.blob();
    audioUrl=URL.createObjectURL(blob);
    activeAudio=new Audio(audioUrl);
    activeAudio.onended=()=>{if(audioUrl){URL.revokeObjectURL(audioUrl);audioUrl=null;}activeAudio=null;};
    await activeAudio.play();
    status.textContent='Galileo está hablando.';
  }catch(error){
    stopVoice();
    browserVoice(text);
    status.textContent='Usando voz del navegador (ElevenLabs no disponible).';
  }
}
async function ask(message){if(busy||!message.trim())return;busy=true;send.disabled=true;input.value='';bubble(message,'student');const reply=bubble('Galileo está pensando…','bot');status.textContent='Preparando una explicación...';try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,history:history.slice(-10)})});if(!response.ok)throw new Error('Servicio no disponible');const data=await response.json();reply.textContent=data.answer;history.push({role:'user',content:message},{role:'assistant',content:data.answer});say(data.answer);status.textContent='Puedes seguir preguntando.';}catch(error){reply.textContent='Ahora no puedo conectar con mi cerebro. Comprueba que el servidor y Ollama estén encendidos.';status.textContent='Sin conexión al modelo.';}finally{busy=false;send.disabled=false;input.focus();}}
form.addEventListener('submit',e=>{e.preventDefault();ask(input.value.trim());});
document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>ask(button.dataset.example)));
document.querySelector('#stop').addEventListener('click',()=>{stopVoice();status.textContent='Voz detenida.';});
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SpeechRecognition){const recognition=new SpeechRecognition();recognition.lang='es-ES';recognition.interimResults=false;recognition.maxAlternatives=1;recognition.onstart=()=>{status.textContent='Escuchando...';mic.disabled=true;};recognition.onend=()=>{mic.disabled=false;};recognition.onerror=event=>{status.textContent='No se pudo reconocer la voz: '+event.error;};recognition.onresult=event=>{const text=event.results[0][0].transcript;input.value=text;status.textContent='Escuché: '+text;ask(text);};mic.addEventListener('click',()=>{try{recognition.start();}catch(e){status.textContent='No se pudo iniciar el micrófono.';}});}else{mic.disabled=true;status.textContent='Este navegador no ofrece reconocimiento de voz compatible. Puedes escribir tus preguntas.';}
