/* Guild Master RPG V3.2 — flexible display & SQLite result bridge.
   No modifies the data model or the Dark Forest original bundle. */
(() => {
  'use strict';
  const cfg = window.GUILD_DARK_FOREST;
  const frame = document.getElementById('dark-forest-frame');
  const container = document.getElementById('forest-window');
  const label = document.getElementById('forest-status');
  const launcher = document.getElementById('forest-launch');
  const launchButton = document.getElementById('forest-launch-button');
  const tip = document.getElementById('forest-tip');
  const fullButton = document.getElementById('forest-fullscreen');
  if (!cfg || !frame || !container || !label || !launcher || !launchButton) return;

  let submitting = false;
  let completed = false;
  let started = false;
  const message = (txt, className = '') => {
    label.textContent = txt;
    label.className = className;
  };

  // Scaling, including UPscaling, preserves 800×600 proportions and all controls.
  function resizeGame() {
    const full = document.fullscreenElement === container;
    const width = container.clientWidth || 800;
    const heightLimit = full ? (container.clientHeight || innerHeight) :
      Math.max(440, innerHeight - 120);
    const scale = Math.max(0.32, Math.min(width / 800, heightLimit / 600));
    frame.style.transform = `translate(-50%, -50%) scale(${scale})`;
    if (!full) container.style.height = `${Math.ceil(600 * scale)}px`;
  }
  resizeGame();
  if ('ResizeObserver' in window) new ResizeObserver(resizeGame).observe(container);
  window.addEventListener('resize', resizeGame);
  document.addEventListener('fullscreenchange', () => {
    if (document.fullscreenElement !== container) container.style.height = '';
    if (fullButton) fullButton.textContent = document.fullscreenElement === container ?
      'Salir de pantalla completa' : 'Pantalla completa';
    resizeGame();
    frame.focus();
  });
  fullButton?.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement === container) await document.exitFullscreen();
      else await container.requestFullscreen();
    } catch (_) { message('No se pudo activar la pantalla completa en este navegador.', 'error'); }
  });

  message('Lista para comenzar. Leé los controles y pulsá Entrar al bosque.');
  launchButton.addEventListener('click', () => {
    if (started) return;
    started = true;
    const src = new URL(cfg.game_url, window.location.href);
    src.searchParams.set('squad', JSON.stringify(cfg.squad));
    frame.src = src.toString();
    launcher.hidden = true;
    if (tip) tip.textContent = 'FLECHAS: caminar · E o clic en el enemigo cercano: enfrentarlo · COMBATE: Atacar y elegir objetivo.';
    message('Explorá con las flechas. Los enemigos son visibles; acercate y pulsá E para decidir si luchás.');
    frame.focus();
  });

  window.addEventListener('message', async event => {
    if (event.origin !== window.location.origin || event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || typeof data.type !== 'string') return;
    if (data.type === 'guild:darkforest:phase' && !submitting && !completed) {
      const phases = {
        explore: 'EXPLORACIÓN — Buscá criaturas visibles y pulsá E cerca de una para enfrentarte. También podés buscar la salida.',
        encounter: 'CRIATURA A LA VISTA — Elegí Enfrentar o Seguir explorando.',
        battle: 'COMBATE — Elegí Atacar y después el objetivo. Los enemigos responden en su turno.',
        victory: 'Salida alcanzada. Registrando victoria…',
        defeat: 'La cuadrilla cayó. Registrando derrota…'
      };
      if (Object.prototype.hasOwnProperty.call(phases, data.phase)) message(phases[data.phase]);
      return;
    }
    if (data.type !== 'guild:darkforest:result' || typeof data.victory !== 'boolean') return;
    if (completed || submitting) return;
    submitting = true;
    message(data.victory ? 'Salida alcanzada. Registrando victoria en SQLite…' :
      'La cuadrilla fue derrotada. Registrando el resultado…');
    try {
      const response = await fetch(cfg.api_url, {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json', 'X-CSRF-Token':cfg.csrf},
        body:JSON.stringify({victory:data.victory, token:cfg.run_token})
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      completed = true;
      message(payload.message, 'complete');
      window.setTimeout(() => window.location.assign(payload.redirect), 2000);
    } catch (err) {
      submitting = false;
      message('No se pudo registrar la misión: ' + String(err.message || err), 'error');
    }
  });
})();
