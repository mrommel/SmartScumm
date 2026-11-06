# SmartScumm

SmartScumm is a Django project for creating multiple point-and-click adventures inspired by *The Secret of Monkey Island* and *Indiana Jones and the Fate of Atlantis*. The goal is to author games with rooms, characters, dialogue, inventory, and puzzles and play them through a SCUMM-style engine. This is an early scaffold, not yet a playable engine or a tool for running original SCUMM games; use original or properly licensed content.

## Current state

The `games` app stores separate adventures with rooms, uploaded images, hotspots, exits, characters, items, dialogue, puzzle flags, and declarative actions. Staff can manage these in a separate authoring editor and check publication readiness; publication is managed through Django's admin. Games are private by default. Published games have read-only JSON content and image endpoints and a browser player with room transitions, click-to-move, hotspot verbs, inventory, and puzzle flags. Save/load and dialogue progression are not implemented yet.

Install dependencies and run:

```sh
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `/admin/` to create a game and control publication. Staff can use `/editor/` to choose a game and:

1. **Manage images:** Upload, preview, rename, or delete PNG, JPEG, GIF, and WebP files. Images referenced by rooms, characters, or items cannot be deleted until their references are removed.
2. **Build rooms:** Create rooms, give each a background image, and set its order. On a room's page, select *Hotspot* or *Exit*, drag over empty space on the image to draw a rectangle, complete the corresponding form, and save it. Drag an existing region to move it or drag its bottom-right handle to resize it, then **save its form** to persist the change. Focus a region or its handle and use arrow keys to move or resize in 0.01 increments. Numerical coordinate inputs also work without JavaScript; all coordinates are validated to stay within the background. Exit destinations are limited to rooms in the same game.
3. **Create characters and items:** Open the game's *Characters* or *Items* page to add or edit names and optionally choose a portrait or item image from that game's asset library. Previews and links lead back to the selected image, and navigation leads back to rooms and images.
4. **Write room dialogue:** On the room page, add and edit ordered lines. The speaker selector contains only that game's characters; leave it empty for narration. Set the order number or use *Move up*/*Move down* (which renumbers the sequence), then use *Preview sequence* to read the current dialogue, even while the game is a draft. This is a linear preview, not branching dialogue or a playable conversation.
5. **Author interactions:** On *Flags*, create game-scoped puzzle flags (initially false). On *Actions*, choose a verb (*look*, *pick up*, *use*, or *talk*) and exactly one hotspot or item target. Optionally require an inventory item and/or flag value, write response text, and grant an item and/or set a flag. *Use* may also select an input inventory item. Pick up requires a hotspot target and a granted item. Edit or delete rules as needed; flags referenced by actions cannot be deleted until their references are removed. Rule order determines which matching rule wins; see the content contract below.
6. **Check and publish:** Open *Readiness* for a game to see blockers, then preview its version 3 content JSON with staff-only image URLs. Fix any issues and publish through the game's Django admin page. The admin form refuses publication if checks fail; unpublishing is always allowed.

A draft's images, dialogue, and content JSON can be previewed by staff in the editor, but public content and image endpoints remain closed until the game is published. Deleting an unreferenced asset or game also removes its files after the database transaction commits. The editor does not yet support non-rectangular regions, dialogue branches, or playing puzzle actions.

For a published game, visit `/games/<game_id>/play/` (or use *Open player* in the editor). The browser player loads the version 3 content document, displays the first ordered room and its background, and lets you follow labeled exits to other rooms. Click the background to move a visible marker toward that point, or focus the room and use arrow keys to move in 5% steps. Movement stays within the scene and resets to the lower center of each room (50% across, 80% down). Reduced-motion settings disable the marker's movement animation. Choose *Look*, *Pick up*, *Use*, or *Talk* and activate a labeled hotspot or an owned inventory item to see the first matching authored response. A matching rule can grant an item and set a puzzle flag. The inventory lists owned items (with thumbnails when available), and *Use with inventory item* selects an optional input for Use rules; leave it on *No item* for rules without an input. Granted items remain owned even if a rule is triggered again. Inventory and flag state survive room transitions but are **reset on page reload**: saving/loading is a later step. Hotspots, exits, and inventory buttons are keyboard-accessible; the page reports missing or unsupported content instead of silently showing an empty scene. Drafts return `404`.

### Try the vertical slice

Run `python manage.py create_demo_game` to explicitly create and **publish** an original two-room adventure with generated PNG artwork; the command prints its `/games/<id>/play/` URL. It does not modify existing games and refuses to create another game with the same demo title. At the Harbor, look at the Crate, pick up the Brass key, and take the exit to the Lighthouse. Look at the dark Lantern, choose *Use*, select the Brass key as the input item, and activate the Lantern. Look at it again or talk to the Signal horn to see flag-gated responses. The player also supports a keyboard-only route through the controls. This demo is public until you unpublish it through Django admin; do not run the command on a public server unless that is intended.

Images are stored under `media/`; back up that directory alongside the database. For production, provide persistent storage for `MEDIA_ROOT` and serve assets through the guarded endpoints rather than exposing `media/` as a public static directory. The editor uses Django's staff authentication and CSRF protection; it is not an anonymous authoring interface.

The editor uses a locally hosted [Bootstrap 5.3.8](https://getbootstrap.com/) stylesheet (MIT license; see `games/static/games/vendor/bootstrap-LICENSE`). No external CDN or Bootstrap JavaScript is required.

### Icon attribution

The editor and admin favicon/icon is the unmodified [ScummVM icon](https://commons.wikimedia.org/wiki/File:Scummvm_icon.svg) by Matan Bareket ("mataniko") for the ScummVM project, licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). It is used here with attribution; SmartScumm is not affiliated with or endorsed by ScummVM.

## Runtime boundary

SmartScumm will create **original adventures** with SCUMM-inspired point-and-click mechanics, not load or run original SCUMM game files. No SCUMM-compatible runtime or proprietary game assets are required. Game creators must supply content they have the rights to use.

Django is the authoring and publishing backend: each `Game` will own its content and assets. A browser-based player will fetch a game-specific content document, render scenes, and handle interactions locally. Server-side models and admin forms are authoring tools, not runtime APIs. This keeps the authoring model separate from the player and prevents content from one game being mixed with another.

### Content API (implemented)

`GET /games/<game_id>/content/` returns JSON for a published game without requiring a login. Unpublished and nonexistent games both return `404`; other HTTP methods are not supported. Newly created games are unpublished, and unpublishing a game immediately removes access through this endpoint. Responses are not cached so they do not continue to be served after unpublishing.

The current version 3 document follows this shape (example values shown):

```json
{
  "format_version": 3,
  "game": {
    "id": 1,
    "title": "Island Mystery",
    "description": "A coastal adventure"
  },
  "rooms": [
    {
      "id": 4,
      "name": "Dock",
      "background_url": "/games/1/assets/7/",
      "hotspots": [
        {
          "id": 8, "label": "Barrel", "description": "A wooden barrel",
          "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4
        }
      ],
      "exits": [
        {
          "id": 9, "label": "Door", "target_room_id": 5,
          "x": 0.7, "y": 0.2, "width": 0.2, "height": 0.5
        }
      ],
      "dialogue": [
        {"id": 10, "speaker_id": 3, "text": "Welcome aboard!"}
      ]
    }
  ],
  "characters": [
    {"id": 3, "name": "Captain", "portrait_url": null}
  ],
  "items": [
    {"id": 11, "name": "Key", "image_url": null}
  ],
  "flags": [
    {"key": "door-open", "initial": false}
  ],
  "actions": [
    {
      "id": 12, "verb": "use",
      "target": {"kind": "hotspot", "id": 8},
      "input_item_id": 11, "required_item_id": 11,
      "required_flag": {"key": "door-open", "value": false},
      "text": "The door opens.", "grant_item_id": null,
      "set_flag": {"key": "door-open", "value": true},
      "order": 0
    }
  ]
}
```

`format_version` is an integer for the **content document**, not a game revision or save version. Version 3 adds puzzle flags and actions to version 2's room and entity data; players should reject unsupported versions rather than guess at their meaning. `game.id` is the database ID from the URL; `title` and `description` are strings, with `description` possibly empty. Empty collections are arrays; optional image URLs, `speaker_id`, and optional action references are `null` when unset. IDs are stable database IDs; all referenced entities belong to the same game.

Rooms, hotspots, exits, and dialogue are ordered by their `order` field (then by ID for ties); characters and items are ordered by ID. Region coordinates `x`, `y`, `width`, and `height` are fractions of the background image, measured from its top-left, and must fit within `[0, 1]` with positive width and height. Coordinates and relationships are validated by the Django admin; cross-game references are also rejected by the content endpoint if data was written outside the admin. Room backgrounds may be `null` while authoring.

Flags are ordered by key (then ID) and all start `false`. Actions are ordered by `order` (then ID). The browser player should consider only the **first** action matching the selected verb, exact target kind/ID, and exact input item ID (`null` when no input was selected). A hotspot target is available only in the current room; an item target and any selected input item must already be in inventory. An optional `required_item_id` must be in inventory, and `required_flag` must equal its boolean `value`; both conditions apply when present. On a match, show `text`, add `grant_item_id` to inventory if present (without duplicating it), and set `set_flag.key` to its `value` if present. A missing match leaves state unchanged and displays no rule text. `pick_up` targets a hotspot and grants an item; other verbs can target either kind. Rules contain data only, not executable scripts. These are authoring/runtime semantics for the future player; this endpoint does **not** run the actions or persist play state.

`GET /games/<game_id>/assets/<asset_id>/` streams uploaded PNG, JPEG, GIF, or WebP images only if the asset belongs to that published game. Drafts, unknown IDs, and assets belonging to another game return `404`. The asset endpoint does not expose a directory listing; responses are not cached so unpublishing also stops new downloads. Both endpoints are read-only and currently public for published games.

### Publication readiness and private preview

The staff-only `/editor/games/<game_id>/readiness/` page checks for at least one room, missing room backgrounds, exits without a destination in the same game, invalid content (including cross-game references and region bounds), and image assets that are unsupported, unreadable, missing, or mislabeled. **All reported issues block publication through the Django admin form.** The same checks run before the staff-only `/editor/games/<game_id>/preview/` content JSON endpoint responds; when blockers remain it returns `409` with an `issues` array. The preview uses staff-only `/editor/.../image/` URLs instead of public image URLs and is not a playable preview. Neither staff endpoint is cached. Publishing validation runs when the admin form is saved; subsequent edits to an already published game should be checked on the readiness page before release (and the admin form will reject saving it while issues remain). Direct database writes bypass the admin publication gate.

### Planned extensions (not implemented)

- The authoring editor manages images, rooms, rectangular hotspots/exits, characters, items, ordered room dialogue, and declarative puzzle actions. It checks publication readiness and offers a private content preview; dialogue branches and a playable draft preview are still future work. The browser player renders rooms, matches actions, and applies authored item/flag effects.
- The browser keeps current-room, inventory, and flag state separately from the immutable content document. Dialogue progress, save/load, scripting rules, and their versioned save-data format are later steps. No author-supplied executable code is part of the content contract.
- New optional fields may be added within a content format version; incompatible changes require a new `format_version` and corresponding player support. Publishing, testing, and migration of authored content will be designed alongside the editor.

## Development plan

1. **Define the runtime boundary (done):** Build original adventures for a browser player, with Django serving per-game content and protected images. See [Runtime boundary](#runtime-boundary).
2. **Model game content (done):** Game-owned rooms, background images, hotspots/exits, characters, items, and dialogue have coordinates, ordering, and cross-game reference validation.
3. **Build the authoring workflow (done):** The staff-only editor covers all increments below and scopes every edit to its game.
4. **Implement a playable vertical slice (done):** The browser player renders rooms, supports click-to-move and keyboard movement, interprets authored verbs and conditions, and supports inventory pickup/use. Gameplay rules and state remain separate from presentation. See [Try the vertical slice](#try-the-vertical-slice).
5. **Add scripting and persistence:** Extend the existing declarative conditions, puzzle flags, and inventory with dialogue branches, save/load, and per-game play sessions; finalize a versioned save-data format for the browser player.
6. **Expand and harden:** Add audio, animations, accessibility, content previews, automated gameplay and model tests, and an export/publishing path. Validate with an original multi-room adventure before broadening the editor.

### Step 3: Authoring workflow increments

| Part | Status | Deliverable |
|---|---|---|
| 3a. Asset library | Done | Upload, preview, rename, and delete game-scoped images; block deletion while an image is in use. |
| 3b. Basic room layout | Done | Create rooms, select backgrounds, draw rectangular hotspots and exits, edit their fields, and choose same-game exit destinations. |
| 3c. Room layout refinements | Done | Select and reposition or resize existing regions on the image; keep numeric inputs usable without JavaScript and validate bounds. |
| 3d. Characters and items | Done | Create and edit game-scoped characters and items, assign their images from the game's asset library, and expose clear links back to rooms and images. |
| 3e. Dialogue | Done | Edit and reorder room dialogue with speaker selection limited to characters in the same game; preview the sequence before publishing. |
| 3f. Interactions and actions | Done | Author game-scoped hotspot/item rules with look, pick up, use, and talk verbs, inventory/flag conditions, text and item/flag effects; publish a versioned declarative format without executing author-supplied code. |
| 3g. Draft checks and publishing | Done | Report missing backgrounds, incomplete/cross-game exits, invalid content, and unsupported or missing images; provide a private draft content preview and block publication via Django admin when checks fail. |

### Step 4: Playable vertical slice increments

| Part | Status | Deliverable |
|---|---|---|
| 4a. Room viewer and transitions | Done | Public page for published games: fetch version 3 content, display the first ordered room and background, render accessible exit controls, and navigate to their destinations. Reject unsupported or broken content; keep drafts private. |
| 4b. Click-to-move | Done | Track a visible player marker, move it toward clicked positions or via arrow keys, constrain it within the scene, and reset it on room transitions. |
| 4c. Hotspots and verbs | Done | Show interactive hotspots, choose look/talk/use/pick-up verbs, and evaluate the first matching authored action with exact target/input matching and required conditions. Display response text without running author code. |
| 4d. Inventory and puzzle state | Done | Pick up and display items, select an inventory item as Use input, grant items and set flags per authored effects, and keep state local to the current play session. |
| 4e. End-to-end slice | Done | Provide a reproducible original two-room adventure with generated images and a key/flag puzzle; verify publication, actual content and image endpoints, browser-script interactions, errors, and keyboard/accessible controls. Saving and loading remain Step 5. |