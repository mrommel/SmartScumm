from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageDraw

from .models import Action, Game, GameAsset, Hotspot, Item, PuzzleFlag, Room, RoomExit
from .readiness import publication_issues


DEMO_TITLE = 'The Lighthouse Signal'


def background_image(scene):
    if scene not in ('harbor', 'tower'):
        raise ValueError(f'Unknown demo scene: {scene}')
    image = Image.new('RGB', (640, 360), '#79bdd4' if scene == 'harbor' else '#24354b')
    draw = ImageDraw.Draw(image)
    if scene == 'harbor':
        draw.rectangle((0, 265, 640, 360), fill='#40748b')
        draw.rectangle((60, 185, 190, 285), fill='#8c613f')
        draw.line((60, 185, 190, 285), fill='#422c24', width=5)
        draw.line((190, 185, 60, 285), fill='#422c24', width=5)
        draw.rectangle((505, 95, 555, 265), fill='#e8dfcb')
        draw.polygon(((495, 95), (565, 95), (530, 55)), fill='#673c34')
    else:
        draw.rectangle((0, 265, 640, 360), fill='#4a4b56')
        draw.rectangle((355, 65, 510, 235), fill='#ae9b72')
        draw.rectangle((380, 85, 490, 190), fill='#453c33')
        draw.ellipse((406, 100, 464, 158), fill='#daa951')
        draw.polygon(((155, 175), (235, 155), (275, 180), (185, 215)), fill='#a4adb3')
        draw.rectangle((185, 215, 205, 265), fill='#5c6872')
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def key_image():
    image = Image.new('RGB', (64, 64), '#e8dcb9')
    draw = ImageDraw.Draw(image)
    draw.ellipse((9, 18, 30, 39), outline='#74521e', width=5)
    draw.line((28, 29, 52, 29), fill='#74521e', width=6)
    draw.line((43, 29, 43, 39), fill='#74521e', width=5)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


@transaction.atomic
def create_demo_adventure():
    game = Game.objects.create(
        title=DEMO_TITLE,
        description='Find a key at the harbor and light the old lighthouse.',
    )
    harbor_asset = GameAsset.objects.create(
        game=game, name='Harbor backdrop',
        image=ContentFile(background_image('harbor'), name='harbor.png'),
    )
    tower_asset = GameAsset.objects.create(
        game=game, name='Lighthouse backdrop',
        image=ContentFile(background_image('tower'), name='tower.png'),
    )
    key_asset = GameAsset.objects.create(
        game=game, name='Brass key icon',
        image=ContentFile(key_image(), name='key.png'),
    )
    harbor = Room.objects.create(game=game, name='Harbor', background=harbor_asset, order=0)
    tower = Room.objects.create(game=game, name='Lighthouse', background=tower_asset, order=1)
    crate = Hotspot.objects.create(
        room=harbor, label='Crate', description='A weathered crate.',
        x=0.1, y=0.5, width=0.2, height=0.3,
    )
    lantern = Hotspot.objects.create(
        room=tower, label='Lantern', description='A lantern with a keyhole.',
        x=0.58, y=0.22, width=0.2, height=0.36,
    )
    horn = Hotspot.objects.create(
        room=tower, label='Signal horn', description='A horn pointed out to sea.',
        x=0.24, y=0.42, width=0.2, height=0.2,
    )
    RoomExit.objects.create(
        room=harbor, target_room=tower, label='To the lighthouse',
        x=0.8, y=0.3, width=0.18, height=0.55,
    )
    RoomExit.objects.create(
        room=tower, target_room=harbor, label='To the harbor',
        x=0.02, y=0.55, width=0.18, height=0.4,
    )
    key = Item.objects.create(game=game, name='Brass key', image=key_asset)
    lit = PuzzleFlag.objects.create(game=game, key='lantern-lit', description='The lantern is shining.')
    Action.objects.create(
        game=game, verb=Action.Verb.LOOK, target_hotspot=crate,
        text='A weathered crate with a loose lid.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.PICK_UP, target_hotspot=crate,
        text='You found a brass key.', grant_item=key,
    )
    Action.objects.create(
        game=game, verb=Action.Verb.LOOK, target_item=key,
        text='A small key with a lighthouse crest.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.LOOK, target_hotspot=lantern,
        required_flag=lit, required_flag_value=False, text='The lantern is dark.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.LOOK, target_hotspot=lantern,
        required_flag=lit, required_flag_value=True, text='The lantern lights the harbor.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.USE, target_hotspot=lantern,
        text='The lantern housing has a keyhole.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.USE, target_hotspot=lantern, input_item=key,
        required_item=key, required_flag=lit, required_flag_value=False,
        text='The key turns. The lantern shines!', set_flag=lit, set_flag_value=True,
    )
    Action.objects.create(
        game=game, verb=Action.Verb.USE, target_hotspot=lantern, input_item=key,
        required_flag=lit, required_flag_value=True, text='The lantern is already lit.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.TALK, target_hotspot=horn,
        required_flag=lit, required_flag_value=False, text='No ship can see your signal yet.',
    )
    Action.objects.create(
        game=game, verb=Action.Verb.TALK, target_hotspot=horn,
        required_flag=lit, required_flag_value=True, text='A ship answers the signal!',
    )

    issues = publication_issues(game)
    if issues:
        raise ValidationError(issues)
    game.is_published = True
    game.save(update_fields=['is_published'])
    return game
