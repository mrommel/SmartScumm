from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Action, Game, GameAsset, IMAGE_CONTENT_TYPES


def same_game(game_id, reference_game_id):
    if game_id != reference_game_id:
        raise ValidationError('Game content contains a cross-game reference.')


def asset_url(asset, game_id, route_name='game-asset'):
    if asset is None:
        return None
    same_game(game_id, asset.game_id)
    return reverse(route_name, args=[game_id, asset.pk])


def region_data(region):
    return {
        'id': region.pk,
        'label': region.label,
        'x': region.x,
        'y': region.y,
        'width': region.width,
        'height': region.height,
    }


def action_data(action):
    action.clean()
    if action.verb not in Action.Verb.values:
        raise ValidationError('Game content contains an unsupported action verb.')
    return {
        'id': action.pk,
        'verb': action.verb,
        'target': {
            'kind': 'hotspot' if action.target_hotspot_id else 'item',
            'id': action.target_hotspot_id or action.target_item_id,
        },
        'input_item_id': action.input_item_id,
        'required_item_id': action.required_item_id,
        'required_flag': (
            {'key': action.required_flag.key, 'value': action.required_flag_value}
            if action.required_flag_id else None
        ),
        'text': action.text,
        'grant_item_id': action.grant_item_id,
        'set_flag': (
            {'key': action.set_flag.key, 'value': action.set_flag_value}
            if action.set_flag_id else None
        ),
        'order': action.order,
    }


def image_response(asset):
    content_type = IMAGE_CONTENT_TYPES.get(Path(asset.image.name).suffix.lower())
    if content_type is None:
        raise Http404('Unsupported image type.')
    return FileResponse(asset.image.open('rb'), content_type=content_type)


def serialize_game(game, asset_route='game-asset'):
    rooms = []
    for room in game.rooms.select_related('background').prefetch_related(
        'hotspots', 'exits__target_room', 'dialogue__speaker',
    ):
        exits = []
        for exit in room.exits.all():
            same_game(game.pk, exit.target_room.game_id)
            exits.append({**region_data(exit), 'target_room_id': exit.target_room_id})

        dialogue = []
        for line in room.dialogue.all():
            if line.speaker_id:
                same_game(game.pk, line.speaker.game_id)
            dialogue.append({
                'id': line.pk,
                'speaker_id': line.speaker_id,
                'text': line.text,
            })

        rooms.append({
            'id': room.pk,
            'name': room.name,
            'background_url': asset_url(room.background, game.pk, asset_route),
            'hotspots': [
                {**region_data(spot), 'description': spot.description}
                for spot in room.hotspots.all()
            ],
            'exits': exits,
            'dialogue': dialogue,
        })

    return {
        'format_version': 3,
        'game': {
            'id': game.pk,
            'title': game.title,
            'description': game.description,
        },
        'rooms': rooms,
        'characters': [
            {'id': character.pk, 'name': character.name,
             'portrait_url': asset_url(character.portrait, game.pk, asset_route)}
            for character in game.characters.select_related('portrait').order_by('pk')
        ],
        'items': [
            {'id': item.pk, 'name': item.name, 'image_url': asset_url(item.image, game.pk, asset_route)}
            for item in game.items.select_related('image').order_by('pk')
        ],
        'flags': [{'key': flag.key, 'initial': False} for flag in game.flags.all()],
        'actions': [
            action_data(action)
            for action in game.actions.select_related(
                'target_hotspot__room', 'target_item', 'input_item', 'required_item',
                'required_flag', 'grant_item', 'set_flag',
            )
        ],
    }


@require_GET
@never_cache
def game_content(request, game_id):
    game = get_object_or_404(Game, pk=game_id, is_published=True)
    return JsonResponse(serialize_game(game))


@require_GET
@never_cache
def game_player(request, game_id):
    game = get_object_or_404(Game, pk=game_id, is_published=True)
    return render(request, 'games/player.html', {
        'game': game,
        'content_url': reverse('game-content', args=[game.pk]),
    })


@require_GET
@never_cache
def game_asset(request, game_id, asset_id):
    asset = get_object_or_404(GameAsset, pk=asset_id, game_id=game_id, game__is_published=True)
    return image_response(asset)
