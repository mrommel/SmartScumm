from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from games.models import Game, GameAsset, Hotspot, Room, RoomExit


class RoomEditorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username='editor', password='password', is_staff=True)
        self.viewer = user_model.objects.create_user(username='viewer', password='password')
        self.game = Game.objects.create(title='Island', is_published=True)
        self.other_game = Game.objects.create(title='Temple')
        self.asset = GameAsset.objects.create(
            game=self.game, name='Dock image', image='games/1/dock.png',
        )
        self.other_asset = GameAsset.objects.create(
            game=self.other_game, name='Tomb image', image='games/2/tomb.png',
        )
        self.room = Room.objects.create(game=self.game, name='Dock', background=self.asset)
        self.destination = Room.objects.create(game=self.game, name='Inn')
        self.other_room = Room.objects.create(game=self.other_game, name='Tomb')
        self.room_url = reverse('editor-room', args=[self.game.pk, self.room.pk])
        self.client.force_login(self.staff)

    def test_staff_creates_room_and_edits_background(self):
        list_url = reverse('editor-rooms', args=[self.game.pk])
        self.assertContains(self.client.get(reverse('editor-games')), 'Rooms')
        self.assertContains(self.client.get(list_url), 'Dock')
        response = self.client.post(list_url, {
            'room-new-name': 'Ship', 'room-new-background': self.asset.pk, 'room-new-order': 3,
        })
        created = Room.objects.get(name='Ship')
        self.assertRedirects(response, reverse('editor-room', args=[self.game.pk, created.pk]))
        self.assertEqual(created.game, self.game)
        self.assertEqual(created.background, self.asset)

        response = self.client.post(self.room_url, {
            'room-name': 'Harbor', 'room-background': self.asset.pk, 'room-order': 1,
        })
        self.assertRedirects(response, self.room_url)
        self.room.refresh_from_db()
        self.assertEqual(self.room.name, 'Harbor')

    def test_cross_game_assets_cannot_be_assigned_to_rooms(self):
        response = self.client.post(self.room_url, {
            'room-name': 'Dock', 'room-background': self.other_asset.pk, 'room-order': 0,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.room.refresh_from_db()
        self.assertEqual(self.room.background, self.asset)
        response = self.client.post(reverse('editor-rooms', args=[self.game.pk]), {
            'room-new-name': 'Wrong', 'room-new-background': self.other_asset.pk, 'room-new-order': 0,
        })
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(Room.objects.filter(name='Wrong').exists())

    def test_visual_room_shows_preview_and_forms(self):
        response = self.client.get(self.room_url)
        self.assertContains(response, '/static/games/vendor/bootstrap-5.3.8.min.css')
        self.assertContains(response, '/static/games/editor.css')
        self.assertContains(response, 'class="card h-100"')
        self.assertContains(response, 'class="form-control"')
        self.assertContains(response, 'class="form-select"')
        self.assertContains(response, 'id="room-canvas"')
        self.assertContains(response, 'games/editor_room.js')
        self.assertContains(response, reverse('editor-asset-preview', args=[self.game.pk, self.asset.pk]))
        self.assertContains(response, 'id="hotspot-new-form"')
        self.assertContains(response, 'id="exit-new-form"')
        self.assertContains(response, 'id="id_hotspot-new-x"')

    def test_create_edit_and_delete_hotspot(self):
        create_url = reverse('editor-hotspot-create', args=[self.game.pk, self.room.pk])
        response = self.client.post(create_url, {
            'hotspot-new-label': 'Barrel', 'hotspot-new-description': 'Old barrel',
            'hotspot-new-x': 0.1, 'hotspot-new-y': 0.2,
            'hotspot-new-width': 0.3, 'hotspot-new-height': 0.4,
            'hotspot-new-order': 2,
        })
        self.assertRedirects(response, self.room_url)
        spot = Hotspot.objects.get()
        self.assertEqual(spot.room, self.room)
        self.assertEqual(spot.x, 0.1)
        page = self.client.get(self.room_url)
        self.assertContains(page, f'data-region-form="hotspot-{spot.pk}-form"')
        self.assertContains(page, f'aria-label="Move hotspot Barrel with arrow keys"')
        self.assertContains(page, f'aria-label="Resize hotspot Barrel with arrow keys"')
        edit_url = reverse('editor-hotspot-edit', args=[self.game.pk, self.room.pk, spot.pk])
        data = {
            f'hotspot-{spot.pk}-label': 'Chest', f'hotspot-{spot.pk}-description': 'Locked',
            f'hotspot-{spot.pk}-x': 0.6, f'hotspot-{spot.pk}-y': 0.2,
            f'hotspot-{spot.pk}-width': 0.3, f'hotspot-{spot.pk}-height': 0.4,
            f'hotspot-{spot.pk}-order': 1,
        }
        data[f'hotspot-{spot.pk}-width'] = 0.5
        self.assertContains(self.client.post(edit_url, data), 'fit inside')
        spot.refresh_from_db()
        self.assertEqual(spot.label, 'Barrel')
        data[f'hotspot-{spot.pk}-width'] = 0.3
        self.assertRedirects(self.client.post(edit_url, data), self.room_url)
        spot.refresh_from_db()
        self.assertEqual(spot.label, 'Chest')
        self.assertEqual(
            self.client.get(reverse('game-content', args=[self.game.pk])).json()['rooms'][0]['hotspots'][0]['label'],
            'Chest',
        )
        delete_url = reverse('editor-hotspot-delete', args=[self.game.pk, self.room.pk, spot.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        self.assertRedirects(self.client.post(delete_url), self.room_url)
        self.assertFalse(Hotspot.objects.exists())

    def test_exit_targets_only_rooms_of_same_game(self):
        create_url = reverse('editor-exit-create', args=[self.game.pk, self.room.pk])
        data = {
            'exit-new-label': 'Door', 'exit-new-target_room': self.other_room.pk,
            'exit-new-x': 0.6, 'exit-new-y': 0.2,
            'exit-new-width': 0.3, 'exit-new-height': 0.5, 'exit-new-order': 0,
        }
        self.assertContains(self.client.post(create_url, data), 'Select a valid choice')
        self.assertFalse(RoomExit.objects.exists())
        data['exit-new-target_room'] = self.destination.pk
        self.assertRedirects(self.client.post(create_url, data), self.room_url)
        exit = RoomExit.objects.get()
        self.assertEqual(exit.target_room, self.destination)
        page = self.client.get(self.room_url)
        self.assertContains(page, f'data-region-form="exit-{exit.pk}-form"')
        self.assertContains(page, 'aria-label="Resize exit Door with arrow keys"')

        edit_url = reverse('editor-exit-edit', args=[self.game.pk, self.room.pk, exit.pk])
        edit_data = {
            f'exit-{exit.pk}-label': 'Gate', f'exit-{exit.pk}-target_room': self.other_room.pk,
            f'exit-{exit.pk}-x': 0.6, f'exit-{exit.pk}-y': 0.2,
            f'exit-{exit.pk}-width': 0.3, f'exit-{exit.pk}-height': 0.5,
            f'exit-{exit.pk}-order': 0,
        }
        self.assertContains(self.client.post(edit_url, edit_data), 'Select a valid choice')
        exit.refresh_from_db()
        self.assertEqual(exit.target_room, self.destination)
        edit_data[f'exit-{exit.pk}-target_room'] = self.room.pk
        self.assertRedirects(self.client.post(edit_url, edit_data), self.room_url)
        exit.refresh_from_db()
        self.assertEqual(exit.target_room, self.room)
        self.assertRedirects(
            self.client.post(reverse('editor-exit-delete', args=[self.game.pk, self.room.pk, exit.pk])),
            self.room_url,
        )
        self.assertFalse(RoomExit.objects.exists())

    def test_staff_only_csrf_and_game_scope(self):
        create_url = reverse('editor-hotspot-create', args=[self.game.pk, self.room.pk])
        other_url = reverse('editor-room', args=[self.other_game.pk, self.room.pk])
        self.assertEqual(self.client.get(other_url).status_code, 404)
        self.assertEqual(
            self.client.post(reverse('editor-exit-create', args=[self.other_game.pk, self.room.pk])).status_code,
            404,
        )
        for user in (None, self.viewer):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in (self.room_url, reverse('editor-rooms', args=[self.game.pk])):
                self.assertEqual(self.client.get(url).status_code, 302)
            self.assertEqual(self.client.post(create_url).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post(create_url, {}).status_code, 403)
        self.assertFalse(Hotspot.objects.exists())
