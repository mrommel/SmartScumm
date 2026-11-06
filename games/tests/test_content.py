from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from games.models import Character, DialogueLine, Game, Hotspot, Item, Room, RoomExit


class GameContentTests(TestCase):
    def test_drafts_are_not_available(self):
        game = Game.objects.create(title='Draft')

        self.assertEqual(self.client.get(reverse('game-content', args=[game.pk])).status_code, 404)

    def test_published_game_content_is_versioned_and_isolated(self):
        first = Game.objects.create(
            title='Island Mystery', description='A coastal adventure', is_published=True,
        )
        second = Game.objects.create(title='Lost Temple', is_published=True)

        response = self.client.get(reverse('game-content', args=[first.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.json(), {
            'format_version': 3,
            'game': {
                'id': first.pk,
                'title': 'Island Mystery',
                'description': 'A coastal adventure',
            },
            'rooms': [],
            'characters': [],
            'items': [],
            'flags': [],
            'actions': [],
        })
        self.assertNotIn(second.title, response.content.decode())

    def test_content_only_exposes_published_games(self):
        draft = Game.objects.create(title='Secret draft')
        published = Game.objects.create(title='Public', is_published=True)
        draft_url = reverse('game-content', args=[draft.pk])
        published_url = reverse('game-content', args=[published.pk])

        self.assertEqual(self.client.get(draft_url).status_code, 404)
        self.assertEqual(self.client.get(reverse('game-content', args=[published.pk + 100])).status_code, 404)
        self.assertEqual(self.client.post(published_url).status_code, 405)

        published.is_published = False
        published.save(update_fields=['is_published'])
        self.assertEqual(self.client.get(published_url).status_code, 404)

    def test_room_content_and_related_entities_are_ordered_and_game_scoped(self):
        game = Game.objects.create(title='Island', is_published=True)
        other = Game.objects.create(title='Hidden', is_published=True)
        first = Room.objects.create(game=game, name='Dock', order=1)
        second = Room.objects.create(game=game, name='Inn', order=2)
        Room.objects.create(game=other, name='Other game')
        Hotspot.objects.create(
            room=first, label='Barrel', description='A wooden barrel',
            x=0.1, y=0.2, width=0.3, height=0.4,
        )
        exit = RoomExit.objects.create(
            room=first, target_room=second, label='Door', x=0.7, y=0.2,
            width=0.2, height=0.5,
        )
        character = Character.objects.create(game=game, name='Captain')
        Item.objects.create(game=game, name='Key')
        DialogueLine.objects.create(room=first, speaker=character, text='Welcome aboard!')

        data = self.client.get(reverse('game-content', args=[game.pk])).json()

        self.assertEqual(data['format_version'], 3)
        self.assertEqual([room['name'] for room in data['rooms']], ['Dock', 'Inn'])
        self.assertEqual(data['rooms'][0], {
            'id': first.pk,
            'name': 'Dock',
            'background_url': None,
            'hotspots': [{
                'id': first.hotspots.get().pk, 'label': 'Barrel',
                'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4,
                'description': 'A wooden barrel',
            }],
            'exits': [{
                'id': exit.pk, 'label': 'Door', 'x': 0.7, 'y': 0.2,
                'width': 0.2, 'height': 0.5, 'target_room_id': second.pk,
            }],
            'dialogue': [{
                'id': first.dialogue.get().pk, 'speaker_id': character.pk,
                'text': 'Welcome aboard!',
            }],
        })
        self.assertEqual(data['characters'], [
            {'id': character.pk, 'name': 'Captain', 'portrait_url': None},
        ])
        self.assertEqual(data['items'][0]['name'], 'Key')
        self.assertNotIn('Other game', str(data))

    def test_invalid_cross_game_reference_is_not_serialized(self):
        game = Game.objects.create(title='Island', is_published=True)
        other = Game.objects.create(title='Temple')
        room = Room.objects.create(game=game, name='Dock')
        RoomExit.objects.create(
            room=room, target_room=Room.objects.create(game=other, name='Tomb'),
            label='Invalid exit', x=0, y=0, width=0.5, height=0.5,
        )

        with self.assertRaises(ValidationError):
            self.client.get(reverse('game-content', args=[game.pk]))
