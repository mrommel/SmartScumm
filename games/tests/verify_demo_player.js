const assert = require('node:assert/strict');
const fs = require('node:fs');
const { start } = require('./player_harness');

function control(scene, className, label) {
  const found = scene.children.find(child =>
    child.className === className && child.textContent === label,
  );
  assert.ok(found, `Missing ${className}: ${label}`);
  return found;
}

async function verify() {
  const content = JSON.parse(fs.readFileSync(0, 'utf8'));
  const { scene, title, verb, input, inventory, response, position, status } = await start(content);
  assert.equal(title.textContent, 'Harbor');
  assert.equal(status.textContent, '');
  assert.equal(scene.children[0].src, content.rooms[0].background_url);

  scene.listeners.click({ target: scene.children[0], clientX: 60, clientY: 45 });
  assert.equal(position.textContent, 'Player position: 25% across, 25% down.');
  scene.focus();
  let prevented = false;
  scene.listeners.keydown({
    target: scene, key: 'ArrowRight', preventDefault: () => { prevented = true; },
  });
  assert.equal(prevented, true);
  assert.equal(position.textContent, 'Player position: 30% across, 25% down.');

  control(scene, 'room-hotspot', 'Crate').listeners.click();
  assert.equal(response.textContent, 'A weathered crate with a loose lid.');
  assert.equal(control(scene, 'room-exit', 'To the lighthouse')['aria-label'],
    'To the lighthouse: go to Lighthouse');
  control(scene, 'room-exit', 'To the lighthouse').listeners.click();
  assert.equal(title.textContent, 'Lighthouse');
  assert.equal(control(scene, 'room-hotspot', 'Lantern')['aria-label'], 'Look: Lantern');
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern is dark.');
  verb.value = 'use';
  verb.listeners.change();
  assert.equal(input.disabled, true);
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern housing has a keyhole.');
  control(scene, 'room-exit', 'To the harbor').listeners.click();
  verb.value = 'pick_up';
  verb.listeners.change();
  control(scene, 'room-hotspot', 'Crate').listeners.click();
  assert.equal(response.textContent, 'You found a brass key.');
  assert.equal(inventory.children.length, 1);
  assert.equal(inventory.children[0].children[0].textContent, 'Brass key');
  assert.equal(inventory.children[0].children[0]['aria-label'], 'Pick up: Brass key');
  assert.equal(inventory.children[0].children[0].children[0].src, content.items[0].image_url);
  control(scene, 'room-hotspot', 'Crate').listeners.click();
  assert.equal(inventory.children.length, 1);

  control(scene, 'room-exit', 'To the lighthouse').listeners.click();
  assert.equal(title.textContent, 'Lighthouse');
  assert.equal(position.textContent, 'Player position: 50% across, 80% down.');
  assert.equal(scene.focused, true);
  verb.value = 'look';
  verb.listeners.change();
  assert.equal(control(scene, 'room-hotspot', 'Lantern')['aria-label'], 'Look: Lantern');
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern is dark.');
  verb.value = 'talk';
  verb.listeners.change();
  control(scene, 'room-hotspot', 'Signal horn').listeners.click();
  assert.equal(response.textContent, 'No ship can see your signal yet.');

  verb.value = 'use';
  verb.listeners.change();
  assert.equal(input.disabled, false);
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern housing has a keyhole.');
  input.value = String(content.items[0].id);
  input.listeners.change();
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The key turns. The lantern shines!');
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern is already lit.');
  verb.value = 'look';
  verb.listeners.change();
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern lights the harbor.');
  control(inventory.children[0], 'btn btn-outline-primary inventory-item', 'Brass key')
    .listeners.click();
  assert.equal(response.textContent, 'A small key with a lighthouse crest.');
  verb.value = 'talk';
  verb.listeners.change();
  control(scene, 'room-hotspot', 'Signal horn').listeners.click();
  assert.equal(response.textContent, 'A ship answers the signal!');

  control(scene, 'room-exit', 'To the harbor').listeners.click();
  assert.equal(inventory.children.length, 1);
  control(scene, 'room-exit', 'To the lighthouse').listeners.click();
  verb.value = 'look';
  verb.listeners.change();
  control(scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(response.textContent, 'The lantern lights the harbor.');

  const fresh = await start(content);
  assert.equal(fresh.inventory.children.length, 0);
  control(fresh.scene, 'room-exit', 'To the lighthouse').listeners.click();
  control(fresh.scene, 'room-hotspot', 'Lantern').listeners.click();
  assert.equal(fresh.response.textContent, 'The lantern is dark.');
  const unsupported = await start({ ...content, format_version: 99 });
  assert.equal(unsupported.status.textContent, 'Unsupported adventure format.');
}

verify().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
