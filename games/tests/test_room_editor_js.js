const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

class Element {
  constructor() {
    this.listeners = {};
    this.style = {};
    this.hidden = false;
    this.classList = {
      add() {},
      remove() {},
    };
  }

  addEventListener(type, handler) {
    this.listeners[type] = handler;
  }

  dispatchEvent(event) {
    this.listeners[event.type]?.(event);
  }

  closest() {
    return null;
  }
}

function makeForm(prefix, coordinates) {
  const form = { id: `${prefix}-form`, elements: {} };
  ['x', 'y', 'width', 'height'].forEach((key, index) => {
    const input = new Element();
    input.value = coordinates[index] === null ? '' : String(coordinates[index]);
    form.elements[`${prefix}-${key}`] = input;
  });
  return form;
}

function coordinates(form) {
  return ['x', 'y', 'width', 'height'].map(key =>
    Number(form.elements[`${form.id.slice(0, -5)}-${key}`].value),
  );
}

test('drawing, moving, resizing, keyboard control, and cancellation respect image bounds', () => {
  const canvas = new Element();
  const image = {
    complete: true, naturalWidth: 100,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }),
  };
  const pending = new Element();
  pending.hidden = true;
  const status = new Element();
  const target = { value: 'hotspot-new-form', selectedOptions: [{ text: 'Hotspot' }] };
  const existing = makeForm('hotspot-1', [0.1, 0.2, 0.3, 0.4]);
  const newHotspot = makeForm('hotspot-new', [null, null, null, null]);
  const box = new Element();
  const handle = new Element();
  box.dataset = { regionForm: existing.id };
  box.querySelector = () => handle;
  box.closest = selector => selector === '[data-region-form]' ? box : null;
  handle.closest = selector => {
    if (selector === '[data-region-form]') return box;
    if (selector === '.resize-handle') return handle;
    return null;
  };
  canvas.querySelector = () => image;
  canvas.querySelectorAll = () => [box];
  canvas.setPointerCapture = () => {};
  const nodes = {
    'room-canvas': canvas,
    'pending-region': pending,
    'drawing-status': status,
    'drawing-target': target,
    [existing.id]: existing,
    [newHotspot.id]: newHotspot,
  };
  const source = fs.readFileSync(
    path.join(__dirname, '../static/games/editor_room.js'), 'utf8',
  );
  vm.runInNewContext(source, {
    document: { getElementById: id => nodes[id] },
    Event: class { constructor(type) { this.type = type; } },
  });

  function pointer(type, targetElement, x, y) {
    canvas.listeners[type]({
      button: 0, pointerId: 1, target: targetElement,
      clientX: x, clientY: y, preventDefault() {},
    });
  }

  pointer('pointerdown', canvas, 10, 20);
  pointer('pointermove', canvas, 40, 60);
  pointer('pointerup', canvas, 40, 60);
  assert.deepEqual(coordinates(newHotspot), [0.1, 0.2, 0.3, 0.4]);

  pointer('pointerdown', box, 20, 30);
  pointer('pointermove', box, 95, 95);
  pointer('pointerup', box, 95, 95);
  assert.deepEqual(coordinates(existing), [0.7, 0.6, 0.3, 0.4]);

  pointer('pointerdown', handle, 100, 100);
  pointer('pointermove', handle, 85, 90);
  pointer('pointerup', handle, 85, 90);
  assert.deepEqual(coordinates(existing), [0.7, 0.6, 0.15, 0.3]);

  box.listeners.keydown({
    key: 'ArrowLeft', target: box, preventDefault() {},
  });
  box.listeners.keydown({
    key: 'ArrowRight', target: handle, preventDefault() {},
  });
  assert.deepEqual(coordinates(existing), [0.69, 0.6, 0.16, 0.3]);

  pointer('pointerdown', handle, 85, 90);
  pointer('pointerup', handle, 200, 200);
  assert.deepEqual(coordinates(existing), [0.69, 0.6, 0.31, 0.4]);

  pointer('pointerdown', box, 70, 70);
  pointer('pointermove', box, 20, 20);
  canvas.listeners.pointercancel();
  assert.deepEqual(coordinates(existing), [0.69, 0.6, 0.31, 0.4]);

  const x = existing.elements['hotspot-1-x'];
  x.value = '0.5';
  x.dispatchEvent({ type: 'input' });
  assert.equal(box.style.left, '50%');
});
