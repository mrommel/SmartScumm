(() => {
  const canvas = document.getElementById('room-canvas');
  if (!canvas) return;

  const image = canvas.querySelector('img');
  const pending = document.getElementById('pending-region');
  const status = document.getElementById('drawing-status');
  const target = document.getElementById('drawing-target');
  const keys = ['x', 'y', 'width', 'height'];
  const clamp = value => Math.max(0, Math.min(1, value));
  const units = value => Math.round(value * 10000);

  function fields(form) {
    return keys.map(key => form.elements[`${form.id.replace('-form', '')}-${key}`]);
  }

  function formValues(form) {
    const inputs = fields(form);
    if (inputs.some(input => input.value === '')) return null;
    const values = inputs.map(input => Number(input.value));
    if (!values.every(Number.isFinite)) return null;
    const [x, y, width, height] = values;
    if (x < 0 || y < 0 || width <= 0 || height <= 0 || x + width > 1 || y + height > 1) return null;
    return values;
  }

  function setFormValues(form, values) {
    fields(form).forEach((input, index) => {
      input.value = values[index].toFixed(4);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  function paint(element, values) {
    [element.style.left, element.style.top, element.style.width, element.style.height] =
      values.map(value => `${value * 100}%`);
  }

  let selected = null;
  function select(box) {
    if (selected) selected.classList.remove('selected');
    selected = box;
    box.classList.add('selected');
    pending.hidden = true;
  }

  function adjusted(values, dx, dy, mode) {
    let [x, y, width, height] = values.map(units);
    if (mode === 'move') {
      x = Math.max(0, Math.min(10000 - width, x + units(dx)));
      y = Math.max(0, Math.min(10000 - height, y + units(dy)));
    } else {
      width = Math.max(1, Math.min(10000 - x, width + units(dx)));
      height = Math.max(1, Math.min(10000 - y, height + units(dy)));
    }
    return [x, y, width, height].map(value => value / 10000);
  }

  for (const box of canvas.querySelectorAll('[data-region-form]')) {
    const form = document.getElementById(box.dataset.regionForm);
    const inputs = fields(form);
    const update = () => {
      const values = formValues(form);
      box.hidden = !values;
      if (values) paint(box, values);
    };
    inputs.forEach(input => input.addEventListener('input', update));
    box.addEventListener('keydown', event => {
      const delta = {
        ArrowLeft: [-0.01, 0],
        ArrowRight: [0.01, 0],
        ArrowUp: [0, -0.01],
        ArrowDown: [0, 0.01],
      }[event.key];
      if (delta) {
        event.preventDefault();
        const values = formValues(form);
        if (!values) {
          status.textContent = 'Enter valid coordinates in the form before moving this region.';
          return;
        }
        select(box);
        const mode = event.target.closest('.resize-handle') ? 'resize' : 'move';
        const next = adjusted(values, ...delta, mode);
        if (next.some((value, index) => value !== values[index])) {
          setFormValues(form, next);
          status.textContent = 'Region changed. Save its form below to keep the new coordinates.';
        } else {
          status.textContent = 'Region is already at the image boundary.';
        }
      } else if (event.target === box && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        select(box);
        status.textContent = 'Region selected. Drag to move it or use its resize handle. Save its form below.';
      }
    });
    box.querySelector('.resize-handle').addEventListener('click', () => select(box));
    update();
  }

  let drag = null;
  const position = event => {
    const bounds = image.getBoundingClientRect();
    return [
      clamp((event.clientX - bounds.left) / bounds.width),
      clamp((event.clientY - bounds.top) / bounds.height),
    ];
  };
  const rectangle = (a, b) => {
    const left = Math.round(Math.min(a[0], b[0]) * 10000) / 10000;
    const top = Math.round(Math.min(a[1], b[1]) * 10000) / 10000;
    const right = Math.round(Math.max(a[0], b[0]) * 10000) / 10000;
    const bottom = Math.round(Math.max(a[1], b[1]) * 10000) / 10000;
    return [left, top, right - left, bottom - top];
  };

  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0 || !image.complete || !image.naturalWidth) return;
    const box = event.target.closest('[data-region-form]');
    if (box) {
      select(box);
      const form = document.getElementById(box.dataset.regionForm);
      const values = formValues(form);
      if (!values) {
        status.textContent = 'Enter valid coordinates in the form before moving this region.';
        return;
      }
      drag = {
        mode: event.target.closest('.resize-handle') ? 'resize' : 'move',
        start: position(event), original: values, form, changed: false,
      };
    } else {
      drag = { mode: 'create', start: position(event) };
      pending.hidden = false;
      paint(pending, [drag.start[0], drag.start[1], 0, 0]);
    }
    canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  });

  function updateDrag(event) {
    if (!drag) return;
    const end = position(event);
    if (drag.mode === 'create') {
      paint(pending, rectangle(drag.start, end));
    } else {
      const dx = end[0] - drag.start[0];
      const dy = end[1] - drag.start[1];
      const values = dx === 0 && dy === 0
        ? drag.original
        : adjusted(drag.original, dx, dy, drag.mode);
      const current = formValues(drag.form);
      if (values.some((value, index) => value !== current[index])) {
        setFormValues(drag.form, values);
      }
      drag.changed = values.some((value, index) => value !== drag.original[index]);
    }
  }

  canvas.addEventListener('pointermove', updateDrag);
  canvas.addEventListener('pointerup', event => {
    if (!drag) return;
    updateDrag(event);
    if (drag.mode === 'create') {
      const values = rectangle(drag.start, position(event));
      if (values[2] <= 0 || values[3] <= 0) {
        pending.hidden = true;
        status.textContent = 'Draw a larger rectangle.';
      } else {
        const form = document.getElementById(target.value);
        setFormValues(form, values);
        paint(pending, values);
        status.textContent = `Region drawn. Complete and save the ${target.selectedOptions[0].text.toLowerCase()} form below.`;
      }
    } else if (drag.changed) {
      status.textContent = 'Region changed. Save its form below to keep the new coordinates.';
    } else {
      status.textContent = 'Region selected. Drag to move it or use its resize handle. Save its form below.';
    }
    drag = null;
  });
  canvas.addEventListener('pointercancel', () => {
    if (drag && drag.mode !== 'create' && drag.changed) {
      setFormValues(drag.form, drag.original);
    }
    if (drag && drag.mode === 'create') pending.hidden = true;
    drag = null;
  });
})();
