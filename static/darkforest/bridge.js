/* Guild Master RPG — interfaz accesible para Dark Forest de Nick Haras (MIT).
   El motor y los combates siguen siendo los originales; se sustituyen los
   controles visuales azules por botones explicativos y se pausan las emboscadas
   hasta que el jugador decida comenzar. No escribe en SQLite. */
(() => {
  'use strict';
  const params = new URLSearchParams(window.location.search);
  let squad = [];
  try {
    const data = JSON.parse(params.get('squad') || '[]');
    if (Array.isArray(data)) squad = data.slice(0, 3);
  } catch (_) { /* Dejar los personajes originales si no hay parámetros. */ }
  squad = squad.filter(h => h && typeof h.nombre === 'string' && h.nombre.length <= 32);

  let begun = false;
  let resultSent = false;
  let wasBattle = false;
  let encounterPending = false;
  let authorizedCombat = false;
  let pendingFieldEnemy = null;
  let activeWorld = null;
  let lastCombatMessage = '';
  const patchedWorlds = new WeakSet();
  const watchedBattles = new WeakSet();
  let latestPhase = '';
  let lastUiSignature = '';
  const adjusted = new WeakSet();

  const tellParent = data => {
    if (window.parent !== window) {
      window.parent.postMessage(data, window.location.origin);
    }
  };
  const phase = value => {
    if (latestPhase !== value) {
      latestPhase = value;
      tellParent({type:'guild:darkforest:phase', phase:value});
    }
  };
  const active = (game, key) => {
    try { return !!game.scene.isActive(key); }
    catch (_) { return false; }
  };
  const sceneOf = (game, key) => {
    try { return game.scene.getScene(key); }
    catch (_) { return null; }
  };
  const notify = victory => {
    if (resultSent) return;
    resultSent = true;
    tellParent({type:'guild:darkforest:result', victory});
  };

  const panel = document.createElement('section');
  panel.id = 'guild-battle-panel';
  panel.setAttribute('aria-label', 'Controles de combate');
  panel.hidden = true;
  panel.innerHTML = '<div class="guild-battle-head"><span class="guild-battle-kicker">COMBATE POR TURNOS</span><strong id="guild-battle-prompt">Preparando combate…</strong></div><div class="guild-battle-content"><div class="guild-battle-squad"><div class="guild-battle-label">TU EQUIPO</div><div id="guild-battle-party"></div></div><div class="guild-battle-commands"><div class="guild-battle-label">¿QUÉ QUERÉS HACER?</div><div id="guild-battle-actions"></div></div><div class="guild-battle-enemies"><div class="guild-battle-label">ENEMIGOS</div><div id="guild-battle-targets"></div></div></div>';
  document.body.appendChild(panel);
  const prompt = panel.querySelector('#guild-battle-prompt');
  const partyList = panel.querySelector('#guild-battle-party');
  const actions = panel.querySelector('#guild-battle-actions');
  const targets = panel.querySelector('#guild-battle-targets');
  const combatMessage = document.createElement('div');
  combatMessage.id = 'guild-combat-message';
  combatMessage.setAttribute('aria-live', 'polite');
  panel.appendChild(combatMessage);

  // El videojuego original contiene zonas de peligro INVISIBLES.
  // Mostramos criaturas visibles y requerimos E o clic para iniciar cada pelea.
  const explorePrompt = document.createElement('div');
  explorePrompt.id = 'guild-explore-prompt';
  explorePrompt.hidden = true;
  explorePrompt.textContent = 'E · Enfrentar criatura';
  document.body.appendChild(explorePrompt);

  const fieldDialog = document.createElement('div');
  fieldDialog.id = 'guild-field-encounter';
  fieldDialog.hidden = true;
  fieldDialog.innerHTML = '<div class="guild-encounter-card"><span class="guild-battle-kicker">CRIATURA A LA VISTA</span><h2>¿Iniciar el combate?</h2><p>El enemigo está en tu camino. Podés enfrentarlo con tu cuadrilla o seguir explorando y buscar otra ruta.</p><div class="guild-field-buttons"><button type="button" id="guild-field-fight">Enfrentar</button><button type="button" id="guild-field-cancel">Seguir explorando</button></div></div>';
  document.body.appendChild(fieldDialog);

  const curtain = document.createElement('div');
  curtain.id = 'guild-encounter-curtain';
  curtain.hidden = true;
  curtain.innerHTML = '<div class="guild-encounter-card"><span class="guild-battle-kicker">¡EMBOSCADA!</span><h2>Un enemigo bloquea el camino</h2><p>El combate se juega por turnos. Primero elegís <b>Atacar</b>; después seleccionás a qué enemigo golpear. Los rivales responderán automáticamente.</p><button type="button" id="guild-encounter-start">Comenzar combate</button></div>';
  document.body.appendChild(curtain);
  curtain.querySelector('button').addEventListener('click', () => {
    const game = window.game;
    if (!game || !encounterPending) return;
    encounterPending = false;
    curtain.hidden = true;
    try { game.scene.resume('Battle'); } catch (_) { /* El motor decide el estado. */ }
    try { game.scene.resume('UIScene'); } catch (_) { /* Si todavía no se creó, arranca normalmente. */ }
    phase('battle');
  });

  // El marcador no sustituye al enemigo real del combate; señala la emboscada
  // que antes se activaba sin ninguna advertencia visual.
  function nearestEnemy(world) {
    if (!world?.player || !world.spawns?.getChildren) return null;
    let nearest = null;
    let distance = Infinity;
    for (const z of world.spawns.getChildren()) {
      if (!z || z.active === false) continue;
      const d = Math.hypot(world.player.x - z.x, world.player.y - z.y);
      if (d < distance && d < 85) { nearest = z; distance = d; }
    }
    return nearest;
  }

  function closeFieldDialog() {
    const world = pendingFieldEnemy?.world;
    pendingFieldEnemy = null;
    fieldDialog.hidden = true;
    if (world) {
      try { window.game.scene.resume('Game'); } catch (_) { /* Solo presentación. */ }
      try { world.player?.body?.setVelocity(0); } catch (_) { /* Solo presentación. */ }
    }
  }

  function showFieldDialog(world, zone) {
    if (pendingFieldEnemy || !world || !zone || zone.active === false || resultSent) return;
    if (Math.hypot(world.player.x - zone.x, world.player.y - zone.y) >= 85) return;
    pendingFieldEnemy = {world, zone};
    try { world.player.body.setVelocity(0); } catch (_) { /* Inmóvil durante la elección. */ }
    try { window.game.scene.pause('Game'); } catch (_) { /* Solo presentación. */ }
    fieldDialog.hidden = false;
    explorePrompt.hidden = true;
    phase('encounter');
  }

  fieldDialog.querySelector('#guild-field-cancel').addEventListener('click', () => {
    closeFieldDialog();
    phase('explore');
  });
  fieldDialog.querySelector('#guild-field-fight').addEventListener('click', () => {
    if (!pendingFieldEnemy) return;
    const {world, zone} = pendingFieldEnemy;
    pendingFieldEnemy = null;
    fieldDialog.hidden = true;
    explorePrompt.hidden = true;
    try { window.game.scene.resume('Game'); } catch (_) { /* El juego controlará el estado. */ }
    try { zone.__guildMarker?.destroy(); } catch (_) { /* Marcador auxiliar. */ }
    authorizedCombat = true;
    // Se llama al método ORIGINAL: continúa intacto el sistema de batallas.
    world.__guildOriginalMeetEnemy.call(world, world.player, zone);
    phase('battle');
  });

  // V3.3: el juego original vuelve a CREAR un texto Score con fondo negro
  // en GameScene.wake(), después de cada combate. No basta ocultarlo al inicio.
  // Guild Master ya muestra la información en su propia interfaz.
  function removeLegacyHud(world) {
    if (!world) return;
    if (world.scoreText) {
      try { world.scoreText.destroy?.(); } catch (_) { /* Ya retirado. */ }
      world.scoreText = null;
    }
    const children = world.children?.list;
    if (!Array.isArray(children)) return;
    for (const item of [...children]) {
      if (item?.type === 'Text' && /^(?:Score|Player)\s*:/i.test(item.text || '')) {
        try { item.destroy?.(); } catch (_) { /* Solo interfaz original. */ }
      }
    }
  }

  // V3.3: deshabilitar de verdad las zonas de colisión que el juego original
  // registra en su mundo Phaser. Los marcadores visuales no usan estas físicas.
  // Destruir el cuerpo impediría reusar la zona al combatir; basta desactivarlo.
  function disableAutomaticEncounters(world) {
    if (!world?.spawns?.getChildren) return;
    for (const zone of world.spawns.getChildren()) {
      if (zone?.body) zone.body.enable = false;
    }
    const colliders = world.physics?.world?.colliders?.getActive?.();
    if (Array.isArray(colliders)) {
      for (const collider of colliders) {
        const isEncounter =
          (collider?.object1 === world.player && collider?.object2 === world.spawns) ||
          (collider?.object2 === world.player && collider?.object1 === world.spawns);
        if (isEncounter) collider.active = false;
      }
    }
  }

  function adaptWorld(world) {
    if (!world || patchedWorlds.has(world)) return;
    patchedWorlds.add(world);
    const originalMeet = world.onMeetEnemy;
    const originalCreate = world.create;
    const originalWake = world.wake;
    world.__guildOriginalMeetEnemy = originalMeet;
    // El puntaje sigue en el modelo original; solo quitamos su HUD redundante.
    // La función se llama tanto al crear GameScene como al volver del combate.
    world.updateScore = function () {
      this.score = Number(this.sys?.game?.globals?.model?.score) || 0;
      removeLegacyHud(this);
    };
    if (typeof originalWake === 'function') {
      world.wake = function (...args) {
        const result = originalWake.apply(this, args);
        removeLegacyHud(this);
        disableAutomaticEncounters(this);
        return result;
      };
    }
    // El callback invisible ya NO puede iniciar una batalla automáticamente.
    // Se instala ANTES de que create() registre la colisión de Phaser.
    world.onMeetEnemy = function () {};
    world.create = function (...args) {
      const result = originalCreate.apply(this, args);
      activeWorld = this;
      removeLegacyHud(this);
      disableAutomaticEncounters(this);
      // Tiled trae la capa Grass marcada visible:false. Forzarla restaura
      // el suelo en las celdas donde Obstacles es transparente.
      if (this.children?.list) {
        for (const item of this.children.list) {
          if (item?.layer?.name === 'Grass') item.setVisible(true);
          if (item?.type === 'Text' && /^Player:/i.test(item.text || '')) item.setVisible(false);
        }
      }
      if (this.spawns?.getChildren) {
        const enemyTextures = ['and', 'mage1', 'gnu', 'mage2', 'mage3'];
        this.spawns.getChildren().forEach((zone, index) => {
          const name = enemyTextures[index % enemyTextures.length];
          if (!this.textures?.exists?.(name)) return;
          const marker = this.add.sprite(zone.x, zone.y, name, 0)
            .setDisplaySize(46, 54).setDepth(50);
          zone.__guildMarker = marker;
          this.tweens?.add?.({targets:marker, y:zone.y - 6,
            duration:800 + (index % 3) * 200, yoyo:true, repeat:-1});
          marker.setInteractive?.({useHandCursor:true});
          marker.on?.('pointerdown', () => showFieldDialog(this, zone));
        });
      }
      // E es voluntaria; caminar sobre el enemigo no inicia el combate.
      this.input?.keyboard?.on?.('keydown-E', event => {
        if (event?.repeat || !this.scene.isActive() || pendingFieldEnemy) return;
        const enemy = nearestEnemy(this);
        if (enemy) showFieldDialog(this, enemy);
      });
      return result;
    };
  }

  function hideOriginalBattleChrome(game) {
    const ui = sceneOf(game, 'UIScene');
    if (!ui) return;
    // El motor necesita los menús originales para su lógica; solo ocultamos
    // sus gráficos y textos. El panel HTML sigue enviando sus eventos.
    ui.graphics?.setAlpha?.(0);
    ui.menus?.setAlpha?.(0);
    ui.message?.setAlpha?.(0);
    const battle = sceneOf(game, 'Battle');
    if (battle?.back?.setTint) battle.back.setTint(0xb9d6b7);
    if (battle?.events && !watchedBattles.has(battle)) {
      watchedBattles.add(battle);
      battle.events.on('Message', msg => {
        lastCombatMessage = String(msg || '').slice(0, 135);
        combatMessage.textContent = lastCombatMessage;
      });
    }
  }

  function createButton(label, click, variant = '') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'guild-command ' + variant;
    button.textContent = label;
    button.addEventListener('click', click);
    return button;
  }

  function adjustParty(game) {
    if (!active(game, 'Battle')) return;
    const battle = sceneOf(game, 'Battle');
    if (!battle || !Array.isArray(battle.heroes)) return;
    battle.heroes.forEach((hero, i) => {
      if (!hero || adjusted.has(hero)) return;
      adjusted.add(hero);
      const member = squad[i];
      if (member) {
        hero.type = member.nombre;
        const level = Math.max(1, Math.min(20, Number(member.nivel) || 1));
        const attack = Math.max(0, Math.min(500, Number(member.ataque) || 0));
        const defense = Math.max(0, Math.min(500, Number(member.defensa) || 0));
        const classBonus = member.clase === 'mago' ? 5 : member.clase === 'arquero' ? 4 : 2;
        hero.damage = Math.round(hero.damage + level * 2 + attack / 7 + classBonus);
        hero.maxHp = Math.round(hero.maxHp + level * 3 + defense / 6 + (member.clase === 'guerrero' ? 12 : 0));
        hero.hp = hero.maxHp;
      } else {
        hero.type = `Ayudante ${i + 1} (temporal)`;
        hero.damage = 4;
        hero.maxHp = 35;
        hero.hp = 35;
      }
    });
    const ui = sceneOf(game, 'UIScene');
    if (ui?.heroesMenu?.menuItems) {
      ui.heroesMenu.menuItems.forEach((item, i) => {
        const name = battle.heroes[i]?.type;
        if (name && typeof item.setText === 'function') item.setText(name);
      });
    }
  }

  function renderBattle(game) {
    const battle = sceneOf(game, 'Battle');
    const ui = sceneOf(game, 'UIScene');
    if (!battle || !ui || !Array.isArray(battle.heroes) || !Array.isArray(battle.enemies)) return;
    const available = ui.currentMenu === ui.actionsMenu ? 'action' :
      ui.currentMenu === ui.enemiesMenu ? 'target' : 'wait';
    const current = battle.units?.[battle.index];
    const currentName = current?.type || 'Tu equipo';
    const signature = JSON.stringify({
      available, currentName, index:battle.index,
      heroes:battle.heroes.map(h => [h.type,h.hp,h.maxHp,h.living]),
      enemies:battle.enemies.map(e => [e.type,e.hp,e.maxHp,e.living])
    });
    if (signature === lastUiSignature) return;
    lastUiSignature = signature;
    partyList.replaceChildren();
    actions.replaceChildren();
    targets.replaceChildren();
    for (const hero of battle.heroes) {
      const line = document.createElement('div');
      line.className = 'guild-unit' + (hero.living ? '' : ' guild-unit-fallen');
      const name = document.createElement('span'); name.textContent = hero.type;
      const hp = document.createElement('small');
      hp.textContent = `${Math.max(0, Math.round(hero.hp))}/${Math.round(hero.maxHp)} PV`;
      line.append(name, hp); partyList.appendChild(line);
    }
    if (available === 'action') {
      prompt.textContent = `${currentName}: elegí una acción`;
      actions.appendChild(createButton('Atacar', () => {
        if (ui.currentMenu === ui.actionsMenu) ui.actionsMenu.confirm();
      }, 'guild-command-primary'));
      const hint = document.createElement('p');
      hint.className = 'guild-action-hint';
      hint.textContent = 'Después elegí un enemigo.';
      actions.appendChild(hint);
    } else if (available === 'target') {
      prompt.textContent = `${currentName}: elegí a quién atacar`;
      const hint = document.createElement('p');
      hint.className = 'guild-action-hint';
      hint.textContent = 'Hacé clic en un enemigo de la derecha.';
      actions.appendChild(hint);
    } else {
      prompt.textContent = 'Turno del enemigo. Esperá la próxima acción.';
      const hint = document.createElement('p');
      hint.className = 'guild-action-hint';
      hint.textContent = 'Los enemigos atacan solos; vos decidís los ataques del equipo.';
      actions.appendChild(hint);
    }
    battle.enemies.forEach((enemy, i) => {
      if (!enemy.living) return;
      const button = createButton(`${enemy.type} · ${Math.max(0, Math.round(enemy.hp))} PV`, () => {
        if (ui.currentMenu === ui.enemiesMenu && enemy.living) {
          ui.events.emit('Enemy', i);
        }
      }, 'guild-command-target');
      button.disabled = available !== 'target';
      targets.appendChild(button);
    });
  }

  function tick() {
    const game = window.game;
    if (!game || !game.scene || !game.globals) return;
    if (!begun && active(game, 'UserScene')) {
      adaptWorld(sceneOf(game, 'Game'));
      const first = squad[0]?.nombre || 'Gremio';
      game.globals.model.userName = first + (squad.length > 1 ? ` +${squad.length-1}` : '');
      game.globals.model.musicOn = false;
      game.globals.model.soundOn = false;
      game.scene.stop('UserScene');
      game.scene.start('Game');
      begun = true;
      phase('explore');
    }
    if (!begun || resultSent) return;
    if (active(game, 'Victory')) { notify(true); phase('victory'); return; }
    if (active(game, 'GameOver')) { notify(false); phase('defeat'); return; }

    const battleNow = active(game, 'Battle') || (() => {
      try { return !!game.scene.isPaused('Battle'); } catch (_) { return false; }
    })();
    if (battleNow && !wasBattle) {
      adjustParty(game);
      panel.hidden = true;
      lastUiSignature = '';
      combatMessage.textContent = '';
      if (authorizedCombat) {
        // La persona ya confirmó enfrentarse al enemigo visible en el mapa.
        authorizedCombat = false;
        encounterPending = false;
        curtain.hidden = true;
        phase('battle');
      } else {
        // Protección para batallas iniciadas por un evento imprevisto.
        encounterPending = true;
        try { game.scene.pause('Battle'); } catch (_) { /* El motor controla el estado. */ }
        try { if (active(game, 'UIScene')) game.scene.pause('UIScene'); } catch (_) { /* Opcional. */ }
        curtain.hidden = false;
        phase('encounter');
      }
    } else if (!battleNow && wasBattle) {
      curtain.hidden = true;
      encounterPending = false;
      panel.hidden = true;
      lastUiSignature = '';
      phase('explore');
    }
    wasBattle = battleNow;
    if (battleNow) {
      adjustParty(game);
      hideOriginalBattleChrome(game);
      explorePrompt.hidden = true;
      if (!encounterPending) {
        panel.hidden = false;
        renderBattle(game);
      }
    } else {
      panel.hidden = true;
      if (active(game, 'Game')) {
        // El callback del mundo puede reconfigurarse al regresar de un combate.
        // No se reactivan los cuerpos físicos ni el cartel negro original.
        disableAutomaticEncounters(activeWorld);
        removeLegacyHud(activeWorld);
        const enemy = pendingFieldEnemy ? null : nearestEnemy(activeWorld);
        explorePrompt.hidden = !enemy;
        phase('explore');
      } else {
        explorePrompt.hidden = true;
      }
    }
  }

  const timer = window.setInterval(tick, 150);
  window.addEventListener('pagehide', () => window.clearInterval(timer), {once:true});
})();
