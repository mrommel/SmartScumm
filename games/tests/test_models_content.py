from django.core.exceptions import ValidationError
from django.test import TestCase

from games.models import Character, DialogueLine, Game, GameAsset, Hotspot, Item, Room, RoomExit


class ContentModelTests(TestCase):
    def setUp(self):
        self.game = Game.objects.create(title='Island')
        self.other = Game.objects.create(title='Temple')
        self.room = Room.objects.create(game=self.game, name='Dock')
        self.other_room = Room.objects.create(game=self.other, name='Tomb')
        self.other_asset = GameAsset.objects.create(
            game=self.other, name='Background', image='games/2/background.png',
        )
        self.other_character = Character.objects.create(game=self.other, name='Explorer')

    def test_cross_game_references_are_rejected(self):
        invalid = [
            (Room(game=self.game, name='Wrong', background=self.other_asset), 'background'),
            (Character(game=self.game, name='Wrong', portrait=self.other_asset), 'portrait'),
            (Item(game=self.game, name='Wrong', image=self.other_asset), 'image'),
            (RoomExit(
                room=self.room, target_room=self.other_room, label='Wrong',
                x=0, y=0, width=0.5, height=0.5,
            ), 'target_room'),
            (DialogueLine(room=self.room, speaker=self.other_character, text='Wrong'), 'speaker'),
        ]
        for instance, field in invalid:
            with self.subTest(model=type(instance).__name__):
                with self.assertRaises(ValidationError) as error:
                    instance.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_regions_must_fit_inside_background(self):
        for width, x in [(0, 0), (0.5, 0.75)]:
            with self.subTest(width=width, x=x):
                hotspot = Hotspot(room=self.room, label='Wrong', x=x, y=0, width=width, height=0.5)
                with self.assertRaises(ValidationError) as error:
                    hotspot.full_clean()
                self.assertIn('width', error.exception.message_dict)

    def test_deleting_a_game_removes_its_content_without_affecting_others(self):
        RoomExit.objects.create(
            room=self.room, target_room=self.room, label='Loop',
            x=0, y=0, width=0.5, height=0.5,
        )
        self.game.delete()

        self.assertFalse(Room.objects.filter(pk=self.room.pk).exists())
        self.assertTrue(Room.objects.filter(pk=self.other_room.pk).exists())
