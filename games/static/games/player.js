(() => {
  const player = document.getElementById('game-player');
  if (!player) return;

  const status = document.getElementById('player-status');
  const scene = document.getElementById('room-scene');
  const roomName = document.getElementById('room-name');
  const positionStatus = document.getElementById('player-position');
  const verbSelect = document.getElementById('verb-select');
  const actionResponse = document.getElementById('action-response');
  const inputSelect = document.getElementById('input-item-select');
  const inventoryList = document.getElementById('inventory-items');
  const inventoryEmpty = document.getElementById('inventory-empty');

  function regionStyle(element, region, kind = 'Room exit') {
    const { x, y, width, height } = region;
    if (![x, y, width, height].every(Number.isFinite) ||
        x < 0 || y < 0 || width <= 0 || height <= 0 ||
        x + width > 1 || y + height > 1) {
      throw new Error(`${kind} has invalid coordinates.`);
    }
    element.style.left = `${x * 100}%`;
    element.style.top = `${y * 100}%`;
    element.style.width = `${width * 100}%`;
    element.style.height = `${height * 100}%`;
  }

  async function load() {
    try {
      const response = await fetch(player.dataset.contentUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error('Could not load this adventure.');
      const content = await response.json();
      if (content.format_version !== 3 || !Array.isArray(content.rooms) ||
          !Array.isArray(content.actions) || !Array.isArray(content.flags) ||
          !Array.isArray(content.items)) {
        throw new Error('Unsupported adventure format.');
      }
      if (!globalThis.SmartScummRules) throw new Error('Adventure rules could not be loaded.');
      const rooms = new Map(content.rooms.map(room => [room.id, room]));
      const items = new Map(content.items.map(item => [item.id, item]));
      if (!rooms.size) throw new Error('This adventure has no rooms.');
      const state = {
        inventory: new Set(),
        flags: new Map(content.flags.map(flag => [flag.key, flag.initial])),
      };

      let inventoryButtons = [];
      function clearResponse() {
        actionResponse.textContent = '';
        actionResponse.hidden = true;
      }

      function updateLabels() {
        for (const button of scene.querySelectorAll('.room-hotspot')) {
          button.setAttribute('aria-label', `${verbSelect.selectedOptions[0].text}: ${button.textContent}`);
        }
        for (const [button, item] of inventoryButtons) {
          button.setAttribute('aria-label', `${verbSelect.selectedOptions[0].text}: ${item.name}`);
        }
      }

      function selectedInputId() {
        if (verbSelect.value !== 'use' || inputSelect.value === '') return null;
        const id = Number(inputSelect.value);
        if (!Number.isSafeInteger(id) || !state.inventory.has(id)) {
          throw new Error('Invalid inventory item selection.');
        }
        return id;
      }

      function interact(targetKind, targetId) {
        try {
          const action = globalThis.SmartScummRules.firstMatchingAction(
            content.actions,
            { verb: verbSelect.value, targetKind, targetId, inputItemId: selectedInputId() },
            state,
          );
          if (!action) {
            clearResponse();
            return;
          }
          const alreadyOwned = state.inventory.has(action.grant_item_id);
          globalThis.SmartScummRules.applyAction(action, state, items);
          if (action.grant_item_id !== null && !alreadyOwned) {
            renderInventory();
            if (targetKind === 'item') {
              inventoryButtons.find(([, item]) => item.id === targetId)?.[0].focus();
            }
          }
          actionResponse.textContent = action.text;
          actionResponse.hidden = false;
          status.textContent = '';
        } catch (error) {
          clearResponse();
          status.textContent = error.message;
        }
      }

      function renderInventory() {
        const selected = inputSelect.value;
        const entries = [];
        const options = [document.createElement('option')];
        options[0].value = '';
        options[0].textContent = 'No item';
        inventoryButtons = [];
        for (const item of content.items) {
          if (!state.inventory.has(item.id)) continue;
          const entry = document.createElement('li');
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn btn-outline-primary inventory-item';
          button.textContent = item.name;
          if (item.image_url) {
            const image = document.createElement('img');
            image.src = item.image_url;
            image.alt = '';
            button.prepend(image);
          }
          button.setAttribute('aria-label', `${verbSelect.selectedOptions[0].text}: ${item.name}`);
          button.addEventListener('click', () => interact('item', item.id));
          entry.append(button);
          entries.push(entry);
          inventoryButtons.push([button, item]);

          const option = document.createElement('option');
          option.value = String(item.id);
          option.textContent = item.name;
          options.push(option);
        }
        inventoryList.replaceChildren(...entries);
        inventoryEmpty.hidden = entries.length > 0;
        inputSelect.replaceChildren(...options);
        inputSelect.value = options.some(option => option.value === selected) ? selected : '';
        inputSelect.disabled = verbSelect.value !== 'use' || entries.length === 0;
      }

      verbSelect.addEventListener('change', () => {
        clearResponse();
        inputSelect.disabled = verbSelect.value !== 'use' || state.inventory.size === 0;
        updateLabels();
      });
      inputSelect.addEventListener('change', clearResponse);
      renderInventory();

      let currentImage = null;
      let marker = null;
      let position = { x: 0.5, y: 0.8 };
      const clamp = value => Math.max(0, Math.min(1, value));

      function moveTo(x, y) {
        position = {
          x: Number(clamp(x).toFixed(4)),
          y: Number(clamp(y).toFixed(4)),
        };
        marker.style.left = `clamp(12px, ${Number((position.x * 100).toFixed(2))}%, calc(100% - 12px))`;
        marker.style.top = `clamp(12px, ${Number((position.y * 100).toFixed(2))}%, calc(100% - 12px))`;
        positionStatus.textContent =
          `Player position: ${Math.round(position.x * 100)}% across, ${Math.round(position.y * 100)}% down.`;
      }

      scene.addEventListener('click', event => {
        if (!marker || (event.target !== currentImage && event.target !== scene)) return;
        const bounds = scene.getBoundingClientRect();
        if (!currentImage.complete || !currentImage.naturalWidth || !bounds.width || !bounds.height) {
          status.textContent = 'Wait for the room background to load before moving.';
          return;
        }
        moveTo((event.clientX - bounds.left) / bounds.width,
          (event.clientY - bounds.top) / bounds.height);
        status.textContent = '';
      });

      scene.addEventListener('keydown', event => {
        if (event.target !== scene || !marker) return;
        const step = {
          ArrowLeft: [-0.05, 0],
          ArrowRight: [0.05, 0],
          ArrowUp: [0, -0.05],
          ArrowDown: [0, 0.05],
        }[event.key];
        if (!step) return;
        event.preventDefault();
        if (!currentImage.complete || !currentImage.naturalWidth) {
          status.textContent = 'Wait for the room background to load before moving.';
          return;
        }
        moveTo(position.x + step[0], position.y + step[1]);
        status.textContent = '';
      });

      function showRoom(room) {
        if (!room?.background_url) throw new Error('This room has no background image.');
        if (!Array.isArray(room.hotspots) || !Array.isArray(room.exits)) {
          throw new Error('This room has invalid interactions.');
        }
        const image = document.createElement('img');
        image.src = room.background_url;
        image.alt = `Background of ${room.name}`;
        image.addEventListener('error', () => {
          if (scene.contains(image)) status.textContent = 'Could not load the room background.';
        });
        const roomMarker = document.createElement('span');
        roomMarker.className = 'player-marker';
        roomMarker.setAttribute('aria-hidden', 'true');
        const hotspots = [];
        for (const spot of room.hotspots) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'room-hotspot';
          button.textContent = spot.label;
          button.setAttribute('aria-label', `${verbSelect.selectedOptions[0].text}: ${spot.label}`);
          regionStyle(button, spot, 'Room hotspot');
          button.addEventListener('click', () => interact('hotspot', spot.id));
          hotspots.push(button);
        }
        const exits = [];
        for (const exit of room.exits) {
          const destination = rooms.get(exit.target_room_id);
          if (!destination) throw new Error('A room exit has no valid destination.');
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'room-exit';
          button.textContent = exit.label;
          button.setAttribute('aria-label', `${exit.label}: go to ${destination.name}`);
          regionStyle(button, exit);
          button.addEventListener('click', () => {
            try {
              showRoom(destination);
              scene.focus();
            } catch (error) {
              status.textContent = error.message;
            }
          });
          exits.push(button);
        }
        scene.replaceChildren(image, roomMarker, ...hotspots, ...exits);
        currentImage = image;
        marker = roomMarker;
        moveTo(0.5, 0.8);
        roomName.textContent = room.name;
        status.textContent = '';
        clearResponse();
      }

      showRoom(content.rooms[0]);
    } catch (error) {
      status.textContent = error.message;
    }
  }

  load();
})();
