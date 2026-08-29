const $ = (s) => document.querySelector(s);
let tone = 'Warm', length = 'Balanced', mode = 'Write';
const prompt = $('#prompt');
const toast = (message) => { const el = $('#toast'); el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 2600); };

prompt.addEventListener('input', () => $('#charCount').textContent = `${prompt.value.length} / 1200`);
$('#tonePills').addEventListener('click', e => { if (!e.target.matches('.tone')) return; document.querySelectorAll('.tone').forEach(x => x.classList.remove('active')); e.target.classList.add('active'); tone = e.target.dataset.tone; });
$('#lengthPills').addEventListener('click', e => { if (!e.target.dataset.length) return; document.querySelectorAll('.length-pills button').forEach(x => x.classList.remove('active')); e.target.classList.add('active'); length = e.target.dataset.length; });
$('#modePills').addEventListener('click', e => {
  if (!e.target.matches('.mode')) return;
  document.querySelectorAll('.mode').forEach(x => x.classList.remove('active'));
  e.target.classList.add('active');
  mode = e.target.dataset.mode;
  if (mode === 'Refine') {
    prompt.placeholder = "Paste your existing draft here. Draftly will refine the grammar, polish the tone, and improve the style.";
    $('#promptHeading').textContent = "What would you like to refine?";
  } else {
    prompt.placeholder = "For example: Tell my professor I'll need two extra days to submit the assignment because I’ve been sick.";
    $('#promptHeading').textContent = "What would you like to say?";
  }
});

function localDraft(text, type, chosenTone) {
  if (mode === 'Refine') return text.trim();
  const greet = type === 'Email' ? 'Subject: A quick note\n\nHello,' : 'Hi,';
  const closing = type === 'Email' ? '\n\nThank you for your understanding.\n\nBest regards,' : '';
  return `${greet}\n\n${text.trim()}${closing}`;
}
function setServiceStatus(state, label) { const status = $('#connectionStatus'); status.classList.toggle('offline', state === 'offline'); status.classList.toggle('working', state === 'working'); status.lastChild.textContent = ` ${label}`; }
async function generate() {
  const text = prompt.value.trim(); if (!text) { prompt.focus(); toast('Start with a rough thought first'); return; }
  const button = $('#generateButton'); button.disabled = true; button.innerHTML = '<span class="sparkle">✦</span> Composing & reflecting…';
  const type = $('#messageType').value; let draft; let review;
  setServiceStatus('working', 'AI is composing');
  try {
    const response = await fetch('/api/draft', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:text, type, tone, length, mode}) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || body.message || 'The AI service could not create a draft.');
    draft = typeof body.draft === 'string' ? body.draft.trim() : '';
    review = body.review;
    if (!draft) throw new Error('The AI service returned an empty draft.');
    setServiceStatus('ready', 'AI service ready');
  } catch (error) { draft = localDraft(text, type, tone); setServiceStatus('offline', 'AI service unavailable'); toast(`${error.message} Showing a starter draft instead.`); }
  $('#draftContent').textContent = draft; $('#toneReview').textContent = review?.tone || `The ${tone.toLowerCase()} tone is consistent from opening to close.`; $('#clarity').textContent = review?.clarity || 'The main request is direct and easy to understand.'; $('#complete').textContent = review?.completeness || `Formatted appropriately as a ${type.toLowerCase()}.`; $('#output').classList.remove('hidden'); $('#output').scrollIntoView({behavior:'smooth', block:'start'});
  button.disabled = false; button.innerHTML = '<span class="sparkle">✦</span> Compose with Draftly <span class="arrow">→</span>';
}
$('#generateButton').onclick = generate;
$('#newDraft').onclick = () => { $('#output').classList.add('hidden'); prompt.focus(); window.scrollTo({top:0,behavior:'smooth'}); };
async function copyDraft(message) { try { await navigator.clipboard.writeText($('#draftContent').textContent); toast(message); } catch { toast('Could not copy automatically. Please select the draft and copy it.'); } }
$('#copyButton').onclick = () => copyDraft('Draft copied to clipboard');
$('#useButton').onclick = () => copyDraft('Draft copied — ready to send');
$('#reviseButton').onclick = () => { window.scrollTo({top:0,behavior:'smooth'}); document.querySelector('.tone-wrap').scrollIntoView({behavior:'smooth',block:'center'}); toast('Choose a new tone, then compose again'); };
