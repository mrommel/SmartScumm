const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() {
    this.style = {};
    this.listeners = {};
    this.children = [];
    this.textContent = '';
  }

  addEventListener(type, handler) {
    this.listeners[type] = handler;
  }

  setAttribute(name, value) {
    this[name] = value;
  }

  replaceChildren(...children) {
    this.children = children;
  }

  append(...children) {
    this.children.push(...children);
  }

  prepend(...children) {
    this.children.unshift(...children);
  }

  contains(child) {
    return this.children.includes(child);
  }

  focus() {
    this.focused = true;
  }

  getBoundingClientRect() {
    return { left: 10, top: 20, width: 200, height: 100 };
  }

  querySelectorAll(selector) {
    return this.children.filter(child => selector === '.room-hotspot' && child.className === 'room-hotspot');
  }
}

async function start(content, ok = true) {
  const player = new Element();
  player.dataset = { contentUrl: '/games/1/content/' };
  const status = new Element();
  const scene = new Element();
  const title = new Element();
  const position = new Element();
  const response = new Element();
  response.hidden = true;
  const inventory = new Element();
  const inventoryEmpty = new Element();
  const input = new Element();
  input.value = '';
  input.disabled = true;
  const verb = new Element();
  const verbLabels = { look: 'Look', pick_up: 'Pick up', use: 'Use', talk: 'Talk' };
  verb.value = 'look';
  Object.defineProperty(verb, 'selectedOptions', {
    get: () => [{ text: verbLabels[verb.value] }],
  });
  const nodes = {
    'game-player': player,
    'player-status': status,
    'room-scene': scene,
    'room-name': title,
    'player-position': position,
    'verb-select': verb,
    'action-response': response,
    'inventory-items': inventory,
    'inventory-empty': inventoryEmpty,
    'input-item-select': input,
  };
  const calls = [];
  const source = fs.readFileSync(
    path.join(__dirname, '../static/games/player.js'), 'utf8',
  );
  const context = vm.createContext({
    document: {
      getElementById: id => nodes[id],
      createElement: tag => {
        const element = new Element();
        if (tag === 'img') {
          element.complete = true;
          element.naturalWidth = 200;
        }
        return element;
      },
    },
    fetch: async (url, options) => {
      calls.push({ url, options });
      return { ok, json: async () => content };
    },
  });
  const rulesSource = fs.readFileSync(
    path.join(__dirname, '../static/games/player_rules.js'), 'utf8',
  );
  vm.runInContext(rulesSource, context);
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return {
    scene, status, title, position, response, verb, input, inventory, inventoryEmpty,
    calls, rules: context.SmartScummRules,
  };
}

module.exports = { start };
