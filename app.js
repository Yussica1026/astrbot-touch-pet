const $ = (selector) => document.querySelector(selector);
const pet = $('#pet');
const petStage = $('#petStage');
const speech = $('#speech');
const speechText = $('#speechText');
const settingsDialog = $('#settingsDialog');
const COOLDOWN_FALLBACK = 30;
const config = window.PET_CONFIG || {};
const storagePrefix = config.storagePrefix || 'touchPet';
const tokenKey = `${storagePrefix}PairToken`;
const cooldownKey = `${storagePrefix}CooldownUntil`;
const positionKey = `${storagePrefix}Position`;

document.title = config.name || 'AstrBot Touch Pet';
pet.src = config.image || './assets/pet-placeholder.svg';
pet.alt = config.alt || '可触摸的桌宠';
petStage.setAttribute('aria-label', pet.alt);
speechText.textContent = config.initialMessage || '碰一碰我吧。';
$('#pairingTitle').textContent = config.pairingTitle || '桌宠配对';

let pairToken = localStorage.getItem(tokenKey) || '';
let cooldownUntil = Number(localStorage.getItem(cooldownKey) || 0);
let petPosition = { x: 0, y: 0 };
try {
  const savedPosition = JSON.parse(localStorage.getItem(positionKey) || '{}');
  if (Number.isFinite(savedPosition.x) && Number.isFinite(savedPosition.y)) petPosition = savedPosition;
} catch (_) {
  localStorage.removeItem(positionKey);
}
let pointer = null;
let lastTapAt = 0;
let singleTapTimer = null;
let cooldownTimer = null;

function applyPetPosition() {
  petStage.style.setProperty('--pet-x', `${petPosition.x}px`);
  petStage.style.setProperty('--pet-y', `${petPosition.y}px`);
}

function clampPetPosition(x, y) {
  const rect = pet.getBoundingClientRect();
  const baseLeft = rect.left - petPosition.x;
  const baseTop = rect.top - petPosition.y;
  const margin = 8;
  return {
    x: Math.min(window.innerWidth - margin - baseLeft - rect.width, Math.max(margin - baseLeft, x)),
    y: Math.min(window.innerHeight - margin - baseTop - rect.height, Math.max(margin - baseTop, y))
  };
}

function savePetPosition() {
  localStorage.setItem(positionKey, JSON.stringify(petPosition));
}

applyPetPosition();
requestAnimationFrame(() => {
  petPosition = clampPetPosition(petPosition.x, petPosition.y);
  applyPetPosition();
});

function showSpeech(text, duration = 2600) {
  speechText.textContent = text;
  speech.classList.remove('hidden');
  clearTimeout(showSpeech.timer);
  showSpeech.timer = setTimeout(() => speech.classList.add('hidden'), duration);
}

function setPetState(state) {
  pet.className = `pet pixel-pet ${state}`;
  petStage.classList.toggle('talking', state === 'talking');
}

function makeRequestId() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function startCooldown(seconds) {
  cooldownUntil = Date.now() + seconds * 1000;
  localStorage.setItem(cooldownKey, String(cooldownUntil));
  updateCooldown();
  clearInterval(cooldownTimer);
  cooldownTimer = setInterval(updateCooldown, 250);
}

function updateCooldown() {
  const remainingMs = cooldownUntil - Date.now();
  const box = $('#cooldown');
  if (remainingMs <= 0) {
    box.hidden = true;
    $('#gestureHint').hidden = false;
    clearInterval(cooldownTimer);
    localStorage.removeItem(cooldownKey);
    return;
  }
  const total = COOLDOWN_FALLBACK * 1000;
  box.hidden = false;
  $('#gestureHint').hidden = true;
  $('#cooldownText').textContent = `${Math.ceil(remainingMs / 1000)} 秒后可以再碰我`;
  $('#cooldownBar').style.transform = `scaleX(${Math.max(0, remainingMs / total)})`;
}

async function sendSignal(gesture) {
  if (Date.now() < cooldownUntil) {
    showSpeech('再等我一下，信号还在路上。');
    return;
  }
  if (!pairToken) {
    showSpeech(config.pairPrompt || '先和桌宠配对一下吧。');
    settingsDialog.showModal();
    return;
  }

  setPetState('talking');
  showSpeech(config.sendingText || '正在发送触摸信号…', 8000);
  try {
    const response = await fetch('./api/touch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${pairToken}` },
      body: JSON.stringify({ gesture, request_id: makeRequestId() })
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      pairToken = '';
      localStorage.removeItem(tokenKey);
      throw new Error('配对令牌不正确，请重新设置');
    }
    if (response.status === 429) {
      startCooldown(Number(data.retry_after || COOLDOWN_FALLBACK));
      throw new Error('信号正在冷却，再等一下哦');
    }
    if (!response.ok || !data.ok) throw new Error(data.detail || '服务器没有确认送达');
    showSpeech(config.deliveredText || '触摸信号已送达', 4200);
    startCooldown(Number(data.cooldown_seconds || COOLDOWN_FALLBACK));
  } catch (error) {
    showSpeech(`${error.message || '信号没有送到'}，轻轻再试一次`, 4200);
  } finally {
    setTimeout(() => setPetState('idle'), 700);
  }
}

petStage.addEventListener('pointerdown', (event) => {
  if (event.pointerType === 'mouse' && event.button !== 0) return;
  petStage.setPointerCapture?.(event.pointerId);
  pointer = {
    id: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    originX: petPosition.x,
    originY: petPosition.y,
    start: Date.now(),
    dragging: false,
    longPressed: false
  };
  pointer.longTimer = setTimeout(() => {
    if (!pointer || pointer.dragging) return;
    pointer.longPressed = true;
    navigator.vibrate?.(25);
    sendSignal('long_press');
  }, 600);
});

petStage.addEventListener('pointermove', (event) => {
  if (!pointer || event.pointerId !== pointer.id) return;
  const dx = event.clientX - pointer.x;
  const dy = event.clientY - pointer.y;
  if (!pointer.dragging && Math.hypot(dx, dy) > 10) {
    pointer.dragging = true;
    clearTimeout(pointer.longTimer);
    petStage.classList.add('dragging');
  }
  if (pointer.dragging) {
    petPosition = clampPetPosition(pointer.originX + dx, pointer.originY + dy);
    applyPetPosition();
  }
});

function finishPointer(event) {
  if (!pointer || event.pointerId !== pointer.id) return;
  clearTimeout(pointer.longTimer);
  const result = { ...pointer };
  pointer = null;
  petStage.classList.remove('dragging');
  if (result.longPressed) return;
  if (result.dragging) {
    savePetPosition();
    setPetState('tapped');
    sendSignal('drag');
    return;
  }
  const now = Date.now();
  if (now - lastTapAt <= 280) {
    clearTimeout(singleTapTimer);
    lastTapAt = 0;
    setPetState('tapped');
    sendSignal('double_tap');
  } else {
    lastTapAt = now;
    singleTapTimer = setTimeout(() => {
      if (lastTapAt === now) {
        lastTapAt = 0;
        setPetState('tapped');
        sendSignal('tap');
      }
    }, 285);
  }
}

petStage.addEventListener('pointerup', finishPointer);
petStage.addEventListener('pointercancel', (event) => {
  if (pointer && event.pointerId === pointer.id) clearTimeout(pointer.longTimer);
  pointer = null;
  petStage.classList.remove('dragging');
  savePetPosition();
  setPetState('idle');
});
petStage.addEventListener('contextmenu', (event) => event.preventDefault());

$('#settingsButton').addEventListener('click', () => settingsDialog.showModal());
document.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => $('#' + button.dataset.close).close()));
$('#pairToken').value = pairToken;
$('#settingsForm').addEventListener('submit', (event) => {
  event.preventDefault();
  pairToken = $('#pairToken').value.trim();
  if (!pairToken) return;
  localStorage.setItem(tokenKey, pairToken);
  settingsDialog.close();
  showSpeech(config.pairedText || '配对成功，轻轻碰我吧。');
});

const tokenFromUrl = new URLSearchParams(location.search).get('token');
if (tokenFromUrl) {
  pairToken = tokenFromUrl;
  localStorage.setItem(tokenKey, pairToken);
  history.replaceState({}, '', location.pathname);
}

updateCooldown();
window.addEventListener('resize', () => {
  petPosition = clampPetPosition(petPosition.x, petPosition.y);
  applyPetPosition();
  savePetPosition();
});
if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js'));
}
