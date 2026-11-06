const assert = require('node:assert/strict');
const test = require('node:test');
const { start } = require('./player_harness');

test('player renders the first room and follows accessible exit buttons', async () => {
  const content = {
    format_version: 3,
    flags: [], actions: [], items: [],
    rooms: [
      {
        id: 2, name: 'Dock', background_url: '/games/1/assets/7/',
        hotspots: [],
        exits: [{ label: 'Door', target_room_id: 3, x: 0.6, y: 0.2, width: 0.2, height: 0.3 }],
      },
      { id: 3, name: 'Inn', background_url: '/games/1/assets/8/', hotspots: [], exits: [] },
    ],
  };
  const { scene, status, title, position, calls } = await start(content);
  assert.equal(calls[0].url, '/games/1/content/');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(title.textContent, 'Dock');
  assert.equal(scene.children[0].src, '/games/1/assets/7/');
  assert.equal(scene.children[1].className, 'player-marker');
  assert.equal(scene.children[1]['aria-hidden'], 'true');
  assert.equal(position.textContent, 'Player position: 50% across, 80% down.');
  assert.equal(scene.children[2].style.left, '60%');
  assert.equal(scene.children[2].style.width, '20%');
  assert.equal(scene.children[2]['aria-label'], 'Door: go to Inn');
  const oldImage = scene.children[0];
  scene.children[2].listeners.click();
  assert.equal(title.textContent, 'Inn');
  assert.equal(scene.children[0].src, '/games/1/assets/8/');
  assert.equal(scene.children.length, 2);
  assert.equal(scene.focused, true);
  assert.equal(position.textContent, 'Player position: 50% across, 80% down.');
  oldImage.listeners.error();
  assert.equal(status.textContent, '');
  scene.children[0].listeners.error();
  assert.equal(status.textContent, 'Could not load the room background.');
});

test('pointer movement uses scene coordinates and stays inside the scene', async () => {
  const { scene, status, position } = await start({
    format_version: 3,
    flags: [], actions: [], items: [],
    rooms: [{ id: 1, name: 'Dock', background_url: '/image/', exits: [
      { label: 'Door', target_room_id: 1, x: 0.6, y: 0.2, width: 0.2, height: 0.3 },
    ], hotspots: [] }],
  });
  const image = scene.children[0];
  const marker = scene.children[1];
  scene.listeners.click({ target: image, clientX: 60, clientY: 45 });
  assert.equal(marker.style.left, 'clamp(12px, 25%, calc(100% - 12px))');
  assert.equal(marker.style.top, 'clamp(12px, 25%, calc(100% - 12px))');
  scene.listeners.click({ target: scene, clientX: 500, clientY: -10 });
  assert.equal(position.textContent, 'Player position: 100% across, 0% down.');
  assert.equal(marker.style.left, 'clamp(12px, 100%, calc(100% - 12px))');
  assert.equal(marker.style.top, 'clamp(12px, 0%, calc(100% - 12px))');
  scene.listeners.click({ target: scene.children[2], clientX: 100, clientY: 100 });
  assert.equal(position.textContent, 'Player position: 100% across, 0% down.');

  image.complete = false;
  scene.listeners.click({ target: image, clientX: 100, clientY: 100 });
  assert.equal(status.textContent, 'Wait for the room background to load before moving.');
  assert.equal(position.textContent, 'Player position: 100% across, 0% down.');
});

test('arrow keys move in bounded steps only while the scene has focus', async () => {
  const { scene, status, position } = await start({
    format_version: 3,
    flags: [], actions: [], items: [],
    rooms: [{ id: 1, name: 'Dock', background_url: '/image/', hotspots: [], exits: [] }],
  });
  const marker = scene.children[1];
  let prevented = false;
  function press(key, target = scene) {
    scene.listeners.keydown({
      key, target, preventDefault: () => { prevented = true; },
    });
  }
  press('ArrowRight');
  assert.equal(marker.style.left, 'clamp(12px, 55%, calc(100% - 12px))');
  assert.equal(position.textContent, 'Player position: 55% across, 80% down.');
  assert.equal(prevented, true);
  prevented = false;
  press('ArrowLeft', scene.children[0]);
  assert.equal(position.textContent, 'Player position: 55% across, 80% down.');
  assert.equal(prevented, false);
  for (let index = 0; index < 30; index++) press('ArrowDown');
  assert.equal(position.textContent, 'Player position: 55% across, 100% down.');
  for (let index = 0; index < 30; index++) press('ArrowLeft');
  assert.equal(position.textContent, 'Player position: 0% across, 100% down.');
  scene.children[0].complete = false;
  press('ArrowRight');
  assert.equal(status.textContent, 'Wait for the room background to load before moving.');
  assert.equal(position.textContent, 'Player position: 0% across, 100% down.');
});

test('entering a different room resets movement and does not retain stale image errors', async () => {
  const { scene, status, position } = await start({
    format_version: 3,
    flags: [], actions: [], items: [],
    rooms: [
      {
        id: 1, name: 'Dock', background_url: '/dock/', exits: [
          { label: 'Door', target_room_id: 2, x: 0.1, y: 0.1, width: 0.2, height: 0.2 },
        ], hotspots: [],
      },
      { id: 2, name: 'Inn', background_url: '/inn/', hotspots: [], exits: [] },
    ],
  });
  const oldImage = scene.children[0];
  scene.listeners.click({ target: oldImage, clientX: 200, clientY: 100 });
  assert.equal(position.textContent, 'Player position: 95% across, 80% down.');
  scene.children[2].listeners.click();
  assert.equal(position.textContent, 'Player position: 50% across, 80% down.');
  oldImage.listeners.error();
  assert.equal(status.textContent, '');
});

test('hotspots use the selected verb and display only matching authored text', async () => {
  const spot = { id: 8, label: 'Barrel', x: 0.1, y: 0.2, width: 0.3, height: 0.4 };
  const { scene, verb, response, position } = await start({
    format_version: 3,
    flags: [{ key: 'opened', initial: false }], items: [],
    actions: [
      { id: 4, order: 4, verb: 'look', target: { kind: 'hotspot', id: 8 },
        input_item_id: null, required_item_id: null, required_flag: null, text: 'Late look',
        grant_item_id: null, set_flag: null },
      { id: 2, order: 1, verb: 'look', target: { kind: 'hotspot', id: 8 },
        input_item_id: null, required_item_id: null, required_flag: { key: 'opened', value: false },
        text: '<img src=x onerror=alert(1)>', grant_item_id: null, set_flag: null },
      { id: 3, order: 1, verb: 'look', target: { kind: 'hotspot', id: 8 },
        input_item_id: null, required_item_id: null, required_flag: null, text: 'Tie breaker',
        grant_item_id: null, set_flag: null },
      { id: 5, order: 0, verb: 'use', target: { kind: 'hotspot', id: 8 },
        input_item_id: null, required_item_id: null, required_flag: null, text: 'It moves',
        grant_item_id: null, set_flag: null },
    ],
    rooms: [{ id: 1, name: 'Dock', background_url: '/image/', hotspots: [spot], exits: [] }],
  });
  const hotspot = scene.children[2];
  assert.equal(hotspot.className, 'room-hotspot');
  assert.equal(hotspot.style.left, '10%');
  assert.equal(hotspot['aria-label'], 'Look: Barrel');
  hotspot.listeners.click();
  assert.equal(response.textContent, '<img src=x onerror=alert(1)>');
  assert.equal(response.hidden, false);
  scene.listeners.click({ target: hotspot, clientX: 60, clientY: 50 });
  assert.equal(position.textContent, 'Player position: 50% across, 80% down.');

  verb.value = 'use';
  verb.listeners.change();
  assert.equal(hotspot['aria-label'], 'Use: Barrel');
  assert.equal(response.hidden, true);
  hotspot.listeners.click();
  assert.equal(response.textContent, 'It moves');
  verb.value = 'talk';
  verb.listeners.change();
  hotspot.listeners.click();
  assert.equal(response.hidden, true);
  assert.equal(response.textContent, '');
});

test('rule matching requires exact target and input plus every inventory and flag condition', async () => {
  const { rules } = await start({
    format_version: 3, flags: [], actions: [], items: [],
    rooms: [{ id: 1, name: 'Dock', background_url: '/image/', hotspots: [], exits: [] }],
  });
  const make = (id, overrides = {}) => ({
    id, order: 1, verb: 'use', target: { kind: 'hotspot', id: 8 },
    input_item_id: null, required_item_id: null, required_flag: null, text: `Rule ${id}`,
    ...overrides,
  });
  const selection = { verb: 'use', targetKind: 'hotspot', targetId: 8, inputItemId: null };
  const state = { inventory: new Set(), flags: new Map([['door-open', false]]) };
  const ruleset = [
    make(7, { order: 5 }),
    make(4, { order: 0, target: { kind: 'item', id: 8 } }),
    make(5, { order: 0, input_item_id: 11 }),
    make(6, { order: 0, required_item_id: 11 }),
    make(2, { required_flag: { key: 'door-open', value: true } }),
    make(3, { required_flag: { key: 'door-open', value: false } }),
    make(1, { required_flag: { key: 'door-open', value: false } }),
  ];
  assert.equal(rules.firstMatchingAction(ruleset, selection, state).id, 1);
  state.flags.set('door-open', true);
  assert.equal(rules.firstMatchingAction(ruleset, selection, state).id, 2);
  assert.equal(rules.firstMatchingAction([ruleset[1]], selection, state), null);
  assert.equal(rules.firstMatchingAction([ruleset[2]], selection, state), null);
  assert.equal(rules.firstMatchingAction([ruleset[3]], selection, state), null);
  assert.equal(rules.firstMatchingAction([make(9, { target: { kind: 'hotspot', id: 9 } })],
    selection, state), null);
  assert.equal(rules.firstMatchingAction([ruleset[2]], { ...selection, inputItemId: 11 },
    state), null);
  state.inventory.add(11);
  assert.equal(rules.firstMatchingAction([ruleset[2]], { ...selection, inputItemId: 11 },
    state).id, 5);
  assert.equal(rules.firstMatchingAction([ruleset[3]], selection, state).id, 6);
  const itemSelection = { ...selection, targetKind: 'item', targetId: 8 };
  assert.equal(rules.firstMatchingAction([ruleset[1]], itemSelection, state), null);
  state.inventory.add(8);
  assert.equal(rules.firstMatchingAction([ruleset[1]], itemSelection, state).id, 4);
});

test('room transitions clear stale hotspot responses', async () => {
  const { scene, response, verb } = await start({
    format_version: 3, flags: [], items: [],
    actions: [{
      id: 1, order: 0, verb: 'look', target: { kind: 'hotspot', id: 8 },
      input_item_id: null, required_item_id: null, required_flag: null, text: 'A wooden barrel.',
      grant_item_id: null, set_flag: null,
    }],
    rooms: [
      {
        id: 1, name: 'Dock', background_url: '/dock/',
        hotspots: [{ id: 8, label: 'Barrel', x: 0, y: 0, width: 0.3, height: 0.3 }],
        exits: [{ label: 'Door', target_room_id: 2, x: 0.5, y: 0, width: 0.3, height: 0.3 }],
      },
      { id: 2, name: 'Inn', background_url: '/inn/', hotspots: [], exits: [] },
    ],
  });
  scene.children[2].listeners.click();
  assert.equal(response.textContent, 'A wooden barrel.');
  scene.children[3].listeners.click();
  assert.equal(response.hidden, true);
  assert.equal(response.textContent, '');
  verb.value = 'talk';
  verb.listeners.change();
  assert.equal(scene.querySelectorAll('.room-hotspot').length, 0);
});

test('pickup, inventory Use input, and puzzle flags work across rooms in one session', async () => {
  const action = (id, verb, targetId, text, overrides = {}) => ({
    id, order: id, verb, target: { kind: 'hotspot', id: targetId },
    input_item_id: null, required_item_id: null, required_flag: null,
    grant_item_id: null, set_flag: null, text, ...overrides,
  });
  const content = {
    format_version: 3,
    items: [{ id: 11, name: 'Key', image_url: '/games/1/assets/7/' }],
    flags: [{ key: 'door-open', initial: false }],
    actions: [
      action(1, 'pick_up', 1, 'You found a key.', { grant_item_id: 11 }),
      action(2, 'use', 2, 'The door needs a key.'),
      action(3, 'use', 2, 'The door opens.', {
        input_item_id: 11, required_item_id: 11,
        required_flag: { key: 'door-open', value: false },
        set_flag: { key: 'door-open', value: true },
      }),
      action(4, 'look', 2, 'Locked.', {
        required_flag: { key: 'door-open', value: false },
      }),
      action(5, 'look', 2, 'Unlocked.', {
        required_flag: { key: 'door-open', value: true },
      }),
      action(6, 'look', 11, 'An old key.', {
        target: { kind: 'item', id: 11 },
      }),
      action(7, 'talk', 2, 'A secret passage.', {
        required_item_id: 11, required_flag: { key: 'door-open', value: true },
      }),
    ],
    rooms: [
      {
        id: 1, name: 'Dock', background_url: '/dock/',
        hotspots: [
          { id: 1, label: 'Key', x: 0.1, y: 0.1, width: 0.2, height: 0.2 },
          { id: 2, label: 'Door', x: 0.4, y: 0.1, width: 0.2, height: 0.2 },
        ],
        exits: [{ label: 'To inn', target_room_id: 2, x: 0.7, y: 0.1, width: 0.2, height: 0.2 }],
      },
      {
        id: 2, name: 'Inn', background_url: '/inn/', hotspots: [],
        exits: [{ label: 'To dock', target_room_id: 1, x: 0.7, y: 0.1, width: 0.2, height: 0.2 }],
      },
    ],
  };
  const { scene, verb, input, inventory, inventoryEmpty, response } = await start(content);
  assert.equal(inventoryEmpty.hidden, false);
  assert.equal(input.disabled, true);
  verb.value = 'look';
  verb.listeners.change();
  scene.children[3].listeners.click();
  assert.equal(response.textContent, 'Locked.');

  verb.value = 'pick_up';
  verb.listeners.change();
  scene.children[2].listeners.click();
  assert.equal(response.textContent, 'You found a key.');
  assert.equal(inventory.children.length, 1);
  assert.equal(inventory.children[0].children[0].textContent, 'Key');
  assert.equal(inventory.children[0].children[0].children[0].src, '/games/1/assets/7/');
  assert.equal(inventoryEmpty.hidden, true);
  scene.children[2].listeners.click();
  assert.equal(inventory.children.length, 1);

  verb.value = 'look';
  verb.listeners.change();
  inventory.children[0].children[0].listeners.click();
  assert.equal(response.textContent, 'An old key.');
  verb.value = 'use';
  verb.listeners.change();
  assert.equal(input.disabled, false);
  scene.children[3].listeners.click();
  assert.equal(response.textContent, 'The door needs a key.');
  input.value = '11';
  input.listeners.change();
  scene.children[3].listeners.click();
  assert.equal(response.textContent, 'The door opens.');
  scene.children[3].listeners.click();
  assert.equal(response.hidden, true);
  verb.value = 'look';
  verb.listeners.change();
  scene.children[3].listeners.click();
  assert.equal(response.textContent, 'Unlocked.');
  verb.value = 'talk';
  verb.listeners.change();
  scene.children[3].listeners.click();
  assert.equal(response.textContent, 'A secret passage.');

  scene.children[4].listeners.click();
  assert.equal(inventory.children.length, 1);
  assert.equal(input.value, '11');
  scene.children[2].listeners.click();
  verb.value = 'look';
  verb.listeners.change();
  scene.children[3].listeners.click();
  assert.equal(response.textContent, 'Unlocked.');

  const fresh = await start(content);
  assert.equal(fresh.inventory.children.length, 0);
  fresh.verb.value = 'look';
  fresh.verb.listeners.change();
  fresh.scene.children[3].listeners.click();
  assert.equal(fresh.response.textContent, 'Locked.');
});

test('effects reject invalid references without partially changing play state', async () => {
  const { rules } = await start({
    format_version: 3, items: [], flags: [], actions: [],
    rooms: [{ id: 1, name: 'Dock', background_url: '/image/', hotspots: [], exits: [] }],
  });
  const state = { inventory: new Set(), flags: new Map([['door-open', false]]) };
  const items = new Map([[11, { id: 11 }]]);
  assert.throws(() => rules.applyAction(
    { grant_item_id: 11, set_flag: { key: 'unknown', value: true } }, state, items,
  ), /invalid puzzle flag/);
  assert.equal(state.inventory.size, 0);
  assert.equal(state.flags.get('door-open'), false);
  assert.throws(() => rules.applyAction(
    { grant_item_id: 99, set_flag: { key: 'door-open', value: true } }, state, items,
  ), /unknown item/);
  assert.equal(state.flags.get('door-open'), false);
  rules.applyAction({ grant_item_id: 11, set_flag: { key: 'door-open', value: true } }, state, items);
  rules.applyAction({ grant_item_id: 11, set_flag: { key: 'door-open', value: false } }, state, items);
  assert.equal(state.inventory.size, 1);
  assert.equal(state.flags.get('door-open'), false);
});

test('invalid authored effects and inventory selections surface errors in the player', async () => {
  const { scene, status, response, verb, input, inventory } = await start({
    format_version: 3, items: [], flags: [], actions: [{
      id: 1, order: 0, verb: 'pick_up', target: { kind: 'hotspot', id: 1 },
      input_item_id: null, required_item_id: null, required_flag: null,
      grant_item_id: 99, set_flag: null, text: 'Broken reward',
    }],
    rooms: [{
      id: 1, name: 'Dock', background_url: '/dock/',
      hotspots: [{ id: 1, label: 'Barrel', x: 0.1, y: 0.1, width: 0.2, height: 0.2 }],
      exits: [],
    }],
  });
  verb.value = 'pick_up';
  verb.listeners.change();
  scene.children[2].listeners.click();
  assert.equal(status.textContent, 'Action grants an unknown item.');
  assert.equal(response.hidden, true);
  assert.equal(inventory.children.length, 0);

  verb.value = 'use';
  verb.listeners.change();
  input.value = 'not-an-item';
  scene.children[2].listeners.click();
  assert.equal(status.textContent, 'Invalid inventory item selection.');
});

test('player reports missing or unsupported content instead of rendering it', async () => {
  for (const [content, ok, message] of [
    [{ format_version: 2, rooms: [] }, true, 'Unsupported adventure format.'],
    [{ format_version: 3, rooms: [] }, true, 'Unsupported adventure format.'],
    [{ format_version: 3, flags: [], actions: [], items: [], rooms: [] },
      true, 'This adventure has no rooms.'],
    [{ format_version: 3, flags: [], actions: [], items: [],
      rooms: [{ id: 1, name: 'Dock', hotspots: [], exits: [] }] },
      true, 'This room has no background image.'],
    [{ format_version: 3, rooms: [] }, false, 'Could not load this adventure.'],
  ]) {
    const { scene, status } = await start(content, ok);
    assert.equal(status.textContent, message);
    assert.equal(scene.children.length, 0);
  }
});

test('player rejects broken exits and invalid coordinates', async () => {
  for (const exit of [
    { label: 'Lost', target_room_id: 99, x: 0, y: 0, width: 0.2, height: 0.2 },
    { label: 'Outside', target_room_id: 1, x: 0.9, y: 0, width: 0.2, height: 0.2 },
  ]) {
    const { scene, status } = await start({
      format_version: 3,
      flags: [], actions: [], items: [],
      rooms: [{ id: 1, name: 'Dock', background_url: '/image/', hotspots: [], exits: [exit] }],
    });

    assert.equal(status.textContent, exit.label === 'Lost' ?
      'A room exit has no valid destination.' : 'Room exit has invalid coordinates.');
    assert.equal(scene.children.length, 0);
  }
});

test('player rejects invalid hotspot regions', async () => {
  const { scene, status } = await start({
    format_version: 3, flags: [], actions: [], items: [],
    rooms: [{
      id: 1, name: 'Dock', background_url: '/image/', exits: [],
      hotspots: [{ id: 1, label: 'Outside', x: 0.9, y: 0, width: 0.2, height: 0.2 }],
    }],
  });
  assert.equal(status.textContent, 'Room hotspot has invalid coordinates.');
  assert.equal(scene.children.length, 0);
});
