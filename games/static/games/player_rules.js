(() => {
  function firstMatchingAction(actions, selection, state) {
    const { verb, targetKind, targetId, inputItemId } = selection;
    if (targetKind === 'item' && !state.inventory.has(targetId)) return null;
    if (inputItemId !== null && !state.inventory.has(inputItemId)) return null;

    return [...actions].sort((a, b) => a.order - b.order || a.id - b.id).find(action =>
      action.verb === verb &&
      action.target.kind === targetKind &&
      action.target.id === targetId &&
      action.input_item_id === inputItemId &&
      (action.required_item_id === null || state.inventory.has(action.required_item_id)) &&
      (action.required_flag === null ||
        state.flags.get(action.required_flag.key) === action.required_flag.value)
    ) || null;
  }

  function applyAction(action, state, items) {
    if (action.grant_item_id !== null && !items.has(action.grant_item_id)) {
      throw new Error('Action grants an unknown item.');
    }
    if (action.set_flag !== null &&
        (!state.flags.has(action.set_flag.key) || typeof action.set_flag.value !== 'boolean')) {
      throw new Error('Action sets an invalid puzzle flag.');
    }
    if (action.grant_item_id !== null) state.inventory.add(action.grant_item_id);
    if (action.set_flag !== null) state.flags.set(action.set_flag.key, action.set_flag.value);
  }

  globalThis.SmartScummRules = Object.freeze({ firstMatchingAction, applyAction });
})();
