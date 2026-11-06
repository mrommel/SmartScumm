from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Max
from django.db.models.deletion import RestrictedError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    ActionForm, AssetNameForm, AssetUploadForm, CharacterForm, DialogueLineForm,
    HotspotForm, ItemForm, PuzzleFlagForm, RoomExitForm, RoomForm,
)
from .models import Action, Character, DialogueLine, Game, GameAsset, Hotspot, Item, PuzzleFlag, Room, RoomExit
from .readiness import publication_issues
from .views import image_response, serialize_game


@staff_member_required
@require_GET
def game_list(request):
    return render(request, 'games/editor_games.html', {
        'games': Game.objects.order_by('title', 'pk'),
    })


@staff_member_required
@require_GET
@never_cache
def game_readiness(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'games/editor_readiness.html', {
        'game': game, 'issues': publication_issues(game),
    })


@staff_member_required
@require_GET
@never_cache
def game_preview(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    issues = publication_issues(game)
    if issues:
        return JsonResponse({'issues': issues}, status=409)
    return JsonResponse(serialize_game(game, asset_route='editor-asset-preview'))


@staff_member_required
@require_http_methods(['GET', 'POST'])
def room_list(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    form = RoomForm(request.POST if request.method == 'POST' else None, game=game, prefix='room-new')
    if request.method == 'POST' and form.is_valid():
        room = form.save()
        messages.success(request, 'Room created.')
        return redirect('editor-room', game_id=game_id, room_id=room.pk)
    return render(request, 'games/editor_rooms.html', {
        'game': game, 'rooms': game.rooms.select_related('background'), 'form': form,
    })


def get_room(game_id, room_id):
    return get_object_or_404(Room.objects.select_related('game', 'background'), pk=room_id, game_id=game_id)


def room_page(
    request, room, room_form=None, hotspot_form=None, exit_form=None, hotspot_edit=None,
    exit_edit=None, dialogue_form=None, dialogue_edit_form=None,
):
    last_order = room.dialogue.aggregate(Max('order'))['order__max']
    next_order = 0 if last_order is None else last_order + 1
    return render(request, 'games/editor_room.html', {
        'room': room,
        'room_form': room_form or RoomForm(game=room.game, instance=room, prefix='room'),
        'hotspot_form': hotspot_form or HotspotForm(room=room, prefix='hotspot-new'),
        'exit_form': exit_form or RoomExitForm(room=room, prefix='exit-new'),
        'dialogue_form': dialogue_form or DialogueLineForm(
            room=room, instance=DialogueLine(room=room, order=next_order), prefix='dialogue-new',
        ),
        'hotspots': [
            {
                'spot': spot,
                'form': hotspot_edit[1] if hotspot_edit and hotspot_edit[0] == spot.pk else
                HotspotForm(room=room, instance=spot, prefix=f'hotspot-{spot.pk}'),
            }
            for spot in room.hotspots.all()
        ],
        'exits': [
            {
                'exit': exit,
                'form': exit_edit[1] if exit_edit and exit_edit[0] == exit.pk else
                RoomExitForm(room=room, instance=exit, prefix=f'exit-{exit.pk}'),
            }
            for exit in room.exits.select_related('target_room')
        ],
        'dialogue': [
            {
                'line': line,
                'form': dialogue_edit_form[1] if dialogue_edit_form and dialogue_edit_form[0] == line.pk else
                DialogueLineForm(room=room, instance=line, prefix=f'dialogue-{line.pk}'),
            }
            for line in room.dialogue.select_related('speaker')
        ],
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def room_editor(request, game_id, room_id):
    room = get_room(game_id, room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, game=room.game, instance=room, prefix='room')
        if form.is_valid():
            form.save()
            messages.success(request, 'Room saved.')
            return redirect('editor-room', game_id=game_id, room_id=room_id)
        return room_page(request, room, room_form=form)
    return room_page(request, room)


@staff_member_required
@require_POST
def hotspot_create(request, game_id, room_id):
    room = get_room(game_id, room_id)
    form = HotspotForm(request.POST, room=room, prefix='hotspot-new')
    if form.is_valid():
        form.save()
        messages.success(request, 'Hotspot created.')
        return redirect('editor-room', game_id=game_id, room_id=room_id)
    return room_page(request, room, hotspot_form=form)


@staff_member_required
@require_POST
def hotspot_edit(request, game_id, room_id, spot_id):
    room = get_room(game_id, room_id)
    spot = get_object_or_404(Hotspot, pk=spot_id, room=room)
    form = HotspotForm(request.POST, room=room, instance=spot, prefix=f'hotspot-{spot_id}')
    if form.is_valid():
        form.save()
        messages.success(request, 'Hotspot saved.')
        return redirect('editor-room', game_id=game_id, room_id=room_id)
    return room_page(request, room, hotspot_edit=(spot_id, form))


@staff_member_required
@require_POST
def hotspot_delete(request, game_id, room_id, spot_id):
    room = get_room(game_id, room_id)
    get_object_or_404(Hotspot, pk=spot_id, room=room).delete()
    messages.success(request, 'Hotspot deleted.')
    return redirect('editor-room', game_id=game_id, room_id=room_id)


@staff_member_required
@require_POST
def exit_create(request, game_id, room_id):
    room = get_room(game_id, room_id)
    form = RoomExitForm(request.POST, room=room, prefix='exit-new')
    if form.is_valid():
        form.save()
        messages.success(request, 'Exit created.')
        return redirect('editor-room', game_id=game_id, room_id=room_id)
    return room_page(request, room, exit_form=form)


@staff_member_required
@require_POST
def exit_edit(request, game_id, room_id, exit_id):
    room = get_room(game_id, room_id)
    exit = get_object_or_404(RoomExit, pk=exit_id, room=room)
    form = RoomExitForm(request.POST, room=room, instance=exit, prefix=f'exit-{exit_id}')
    if form.is_valid():
        form.save()
        messages.success(request, 'Exit saved.')
        return redirect('editor-room', game_id=game_id, room_id=room_id)
    return room_page(request, room, exit_edit=(exit_id, form))


@staff_member_required
@require_POST
def exit_delete(request, game_id, room_id, exit_id):
    room = get_room(game_id, room_id)
    get_object_or_404(RoomExit, pk=exit_id, room=room).delete()
    messages.success(request, 'Exit deleted.')
    return redirect('editor-room', game_id=game_id, room_id=room_id)


@staff_member_required
@require_POST
def dialogue_create(request, game_id, room_id):
    room = get_room(game_id, room_id)
    form = DialogueLineForm(request.POST, room=room, prefix='dialogue-new')
    if form.is_valid():
        form.save()
        messages.success(request, 'Dialogue line created.')
        return redirect('editor-room', game_id=game_id, room_id=room_id)
    return room_page(request, room, dialogue_form=form)


@staff_member_required
@require_POST
def dialogue_edit(request, game_id, room_id, line_id):
    room = get_room(game_id, room_id)
    line = get_object_or_404(DialogueLine, pk=line_id, room=room)
    form = DialogueLineForm(request.POST, room=room, instance=line, prefix=f'dialogue-{line_id}')
    if form.is_valid():
        form.save()
        messages.success(request, 'Dialogue line saved.')
        return redirect('editor-room', game_id=game_id, room_id=room_id)
    return room_page(request, room, dialogue_edit_form=(line_id, form))


@staff_member_required
@require_POST
def dialogue_delete(request, game_id, room_id, line_id):
    room = get_room(game_id, room_id)
    get_object_or_404(DialogueLine, pk=line_id, room=room).delete()
    messages.success(request, 'Dialogue line deleted.')
    return redirect('editor-room', game_id=game_id, room_id=room_id)


@staff_member_required
@require_POST
@transaction.atomic
def dialogue_move(request, game_id, room_id, line_id, direction):
    if direction not in ('up', 'down'):
        raise Http404('Unknown direction.')
    room = get_room(game_id, room_id)
    lines = list(room.dialogue.select_for_update())
    index = next((index for index, line in enumerate(lines) if line.pk == line_id), None)
    if index is None:
        raise Http404('Dialogue line not found.')
    neighbor = index + (-1 if direction == 'up' else 1)
    if neighbor < 0 or neighbor >= len(lines):
        messages.info(request, 'Dialogue line is already at the end of the sequence.')
    else:
        lines[index], lines[neighbor] = lines[neighbor], lines[index]
        for position, line in enumerate(lines):
            line.order = position
        DialogueLine.objects.bulk_update(lines, ['order'])
        messages.success(request, 'Dialogue order updated.')
    return redirect('editor-room', game_id=game_id, room_id=room_id)


@staff_member_required
@require_GET
@never_cache
def dialogue_preview(request, game_id, room_id):
    room = get_room(game_id, room_id)
    return render(request, 'games/editor_dialogue_preview.html', {
        'room': room,
        'lines': room.dialogue.select_related('speaker'),
    })


def entity_list_page(request, game_id, form_class, relation, image_field, title, edit_route):
    game = get_object_or_404(Game, pk=game_id)
    form = form_class(request.POST if request.method == 'POST' else None, game=game)
    if request.method == 'POST' and form.is_valid():
        entity = form.save()
        messages.success(request, f'{entity._meta.verbose_name.capitalize()} created.')
        return redirect(request.path)
    entities = getattr(game, relation).select_related(image_field).order_by('name', 'pk')
    return render(request, 'games/editor_entities.html', {
        'game': game,
        'title': title,
        'label': form.instance._meta.verbose_name,
        'form': form,
        'entries': [{'entity': entity, 'asset': getattr(entity, image_field)} for entity in entities],
        'edit_route': edit_route,
    })


def entity_edit_page(request, game_id, entity_id, model, form_class, image_field, list_route):
    entity = get_object_or_404(model, pk=entity_id, game_id=game_id)
    form = form_class(request.POST if request.method == 'POST' else None, game=entity.game, instance=entity)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Changes saved.')
        return redirect(list_route, game_id=game_id)
    return render(request, 'games/editor_entity_edit.html', {
        'entity': entity,
        'form': form,
        'asset': getattr(entity, image_field),
        'list_route': list_route,
        'plural_title': entity._meta.verbose_name_plural,
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def character_list(request, game_id):
    return entity_list_page(
        request, game_id, CharacterForm, 'characters', 'portrait', 'Characters', 'editor-character-edit',
    )


@staff_member_required
@require_http_methods(['GET', 'POST'])
def character_edit(request, game_id, character_id):
    return entity_edit_page(
        request, game_id, character_id, Character, CharacterForm, 'portrait', 'editor-characters',
    )


@staff_member_required
@require_http_methods(['GET', 'POST'])
def item_list(request, game_id):
    return entity_list_page(
        request, game_id, ItemForm, 'items', 'image', 'Items', 'editor-item-edit',
    )


@staff_member_required
@require_http_methods(['GET', 'POST'])
def item_edit(request, game_id, item_id):
    return entity_edit_page(request, game_id, item_id, Item, ItemForm, 'image', 'editor-items')


@staff_member_required
@require_http_methods(['GET', 'POST'])
def flag_list(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    form = PuzzleFlagForm(request.POST if request.method == 'POST' else None, game=game)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Puzzle flag created.')
        return redirect('editor-flags', game_id=game_id)
    return render(request, 'games/editor_flags.html', {
        'game': game, 'form': form, 'flags': game.flags.all(),
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def flag_edit(request, game_id, flag_id):
    flag = get_object_or_404(PuzzleFlag, pk=flag_id, game_id=game_id)
    form = PuzzleFlagForm(request.POST if request.method == 'POST' else None, game=flag.game, instance=flag)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Puzzle flag saved.')
        return redirect('editor-flags', game_id=game_id)
    return render(request, 'games/editor_flag_edit.html', {'flag': flag, 'form': form})


@staff_member_required
@require_POST
def flag_delete(request, game_id, flag_id):
    flag = get_object_or_404(PuzzleFlag, pk=flag_id, game_id=game_id)
    try:
        flag.delete()
    except RestrictedError:
        messages.error(request, 'Remove this flag from actions before deleting it.')
    else:
        messages.success(request, 'Puzzle flag deleted.')
    return redirect('editor-flags', game_id=game_id)


@staff_member_required
@require_http_methods(['GET', 'POST'])
def action_list(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    form = ActionForm(request.POST if request.method == 'POST' else None, game=game)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Action created.')
        return redirect('editor-actions', game_id=game_id)
    return render(request, 'games/editor_actions.html', {
        'game': game, 'form': form,
        'actions': game.actions.select_related('target_hotspot__room', 'target_item', 'input_item'),
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def action_edit(request, game_id, action_id):
    action = get_object_or_404(Action, pk=action_id, game_id=game_id)
    form = ActionForm(request.POST if request.method == 'POST' else None, game=action.game, instance=action)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Action saved.')
        return redirect('editor-actions', game_id=game_id)
    return render(request, 'games/editor_action_edit.html', {'action': action, 'form': form})


@staff_member_required
@require_POST
def action_delete(request, game_id, action_id):
    get_object_or_404(Action, pk=action_id, game_id=game_id).delete()
    messages.success(request, 'Action deleted.')
    return redirect('editor-actions', game_id=game_id)


@staff_member_required
@require_http_methods(['GET', 'POST'])
def asset_list(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    form = AssetUploadForm(request.POST, request.FILES) if request.method == 'POST' else AssetUploadForm()
    if request.method == 'POST' and form.is_valid():
        asset = form.save(commit=False)
        asset.game = game
        asset.save()
        messages.success(request, 'Image uploaded.')
        return redirect('editor-assets', game_id=game.pk)
    return render(request, 'games/editor_assets.html', {
        'game': game,
        'assets': game.assets.prefetch_related(
            'background_rooms', 'portrait_characters', 'item_images',
        ).order_by('name', 'pk'),
        'form': form,
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def asset_edit(request, game_id, asset_id):
    asset = get_object_or_404(GameAsset, pk=asset_id, game_id=game_id)
    form = AssetNameForm(request.POST or None, instance=asset)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Image renamed.')
        return redirect('editor-assets', game_id=game_id)
    return render(request, 'games/editor_asset_edit.html', {'asset': asset, 'form': form})


@staff_member_required
@require_POST
def asset_delete(request, game_id, asset_id):
    asset = get_object_or_404(GameAsset, pk=asset_id, game_id=game_id)
    if (
        asset.background_rooms.exists()
        or asset.portrait_characters.exists()
        or asset.item_images.exists()
    ):
        messages.error(request, 'Remove this image from rooms, characters, and items before deleting it.')
        return redirect('editor-assets', game_id=game_id)

    try:
        asset.delete()
    except RestrictedError:
        messages.error(request, 'This image is in use and cannot be deleted.')
        return redirect('editor-assets', game_id=game_id)
    messages.success(request, 'Image deleted.')
    return redirect('editor-assets', game_id=game_id)


@staff_member_required
@require_GET
@never_cache
def asset_preview(request, game_id, asset_id):
    asset = get_object_or_404(GameAsset, pk=asset_id, game_id=game_id)
    return image_response(asset)
