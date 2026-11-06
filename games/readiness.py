from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from .models import IMAGE_CONTENT_TYPES


def publication_issues(game):
    issues = []
    if not game.pk:
        return ['Add at least one room before publishing.']

    def check_model(instance, label):
        try:
            instance.full_clean()
        except ValidationError as error:
            for message in error.messages:
                issues.append(f'{label}: {message}')

    rooms = list(game.rooms.select_related('background'))
    if not rooms:
        issues.append('Add at least one room before publishing.')
    room_ids = {room.pk for room in rooms}
    for room in rooms:
        label = f'Room "{room.name}" (#{room.pk})'
        if not room.background_id:
            issues.append(f'{label} needs a background image.')
        check_model(room, label)
        for spot in room.hotspots.all():
            check_model(spot, f'Hotspot "{spot.label}" (#{spot.pk})')
        for exit in room.exits.all():
            exit_label = f'Exit "{exit.label}" (#{exit.pk}) in {label}'
            if not exit.target_room_id or exit.target_room_id not in room_ids:
                issues.append(f'{exit_label} needs a destination in this game.')
            else:
                check_model(exit, exit_label)
        for line in room.dialogue.all():
            check_model(line, f'Dialogue line #{line.pk} in {label}')

    for character in game.characters.all():
        check_model(character, f'Character "{character.name}" (#{character.pk})')
    for item in game.items.all():
        check_model(item, f'Item "{item.name}" (#{item.pk})')
    for flag in game.flags.all():
        check_model(flag, f'Flag "{flag.key}" (#{flag.pk})')
    for action in game.actions.all():
        check_model(action, f'Action #{action.pk}')

    for asset in game.assets.all():
        label = f'Image "{asset.name}" (#{asset.pk})'
        check_model(asset, label)
        suffix = Path(asset.image.name).suffix.lower()
        if suffix not in IMAGE_CONTENT_TYPES:
            issues.append(f'{label} has an unsupported image extension.')
            continue
        try:
            with asset.image.open('rb') as image_file:
                with Image.open(image_file) as image:
                    actual_type = Image.MIME.get(image.format)
                    image.verify()
        except (OSError, UnidentifiedImageError, ValueError):
            issues.append(f'{label} is missing or is not a readable image.')
            continue
        if actual_type != IMAGE_CONTENT_TYPES[suffix]:
            issues.append(f'{label} image format does not match its extension.')

    return issues
