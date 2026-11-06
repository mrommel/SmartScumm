from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from games.models import Action, Character, DialogueLine, Game, GameAsset, Hotspot, Item, Room, RoomExit
from games.readiness import publication_issues


class PublicationReadinessTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings_override = override_settings(MEDIA_ROOT=media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(username='admin', password='password')
        self.staff = user_model.objects.create_user(username='editor', password='password', is_staff=True)
        self.viewer = user_model.objects.create_user(username='viewer', password='password')
        self.game = Game.objects.create(title='Island')
        self.other = Game.objects.create(title='Temple')
        self.admin_url = reverse('admin:games_game_change', args=[self.game.pk])
        self.readiness_url = reverse('editor-readiness', args=[self.game.pk])
        self.preview_url = reverse('editor-game-preview', args=[self.game.pk])

    def image(self, filename='dock.png', format='PNG'):
        data = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(data, format=format)
        return SimpleUploadedFile(filename, data.getvalue(), content_type='image/png')

    def room_with_image(self):
        asset = GameAsset.objects.create(game=self.game, name='Dock image', image=self.image())
        room = Room.objects.create(game=self.game, name='Dock', background=asset)
        return room, asset

    def admin_publish(self, published=True):
        self.client.force_login(self.admin)
        return self.client.post(self.admin_url, {
            'title': self.game.title, 'description': self.game.description,
            **({'is_published': 'on'} if published else {}),
            '_save': 'Save',
        })

    def test_missing_rooms_and_background_block_admin_publication(self):
        response = self.admin_publish()
        self.assertContains(response, 'Add at least one room')
        self.game.refresh_from_db()
        self.assertFalse(self.game.is_published)
        self.assertEqual(self.client.get(reverse('game-content', args=[self.game.pk])).status_code, 404)

        Room.objects.create(game=self.game, name='Dock')
        response = self.admin_publish()
        self.assertContains(response, 'needs a background image')
        self.game.refresh_from_db()
        self.assertFalse(self.game.is_published)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.readiness_url), 'needs a background image')
        self.assertEqual(self.client.get(self.preview_url).status_code, 409)

    def test_valid_game_can_publish_and_unpublish_through_admin(self):
        room, asset = self.room_with_image()
        response = self.admin_publish()
        self.assertEqual(response.status_code, 302)
        self.game.refresh_from_db()
        self.assertTrue(self.game.is_published)
        self.assertEqual(self.client.get(reverse('game-content', args=[self.game.pk])).status_code, 200)

        room.background = None
        room.save(update_fields=['background'])
        self.assertContains(self.admin_publish(), 'needs a background image')
        self.game.refresh_from_db()
        self.assertTrue(self.game.is_published)
        self.assertEqual(self.admin_publish(published=False).status_code, 302)
        self.game.refresh_from_db()
        self.assertFalse(self.game.is_published)
        self.assertTrue(asset.image.storage.exists(asset.image.name))

    def test_broken_exits_and_cross_game_references_are_reported(self):
        room, _ = self.room_with_image()
        other_room = Room.objects.create(game=self.other, name='Tomb')
        RoomExit.objects.create(
            room=room, target_room=other_room, label='Wrong exit',
            x=0, y=0, width=0.5, height=0.5,
        )
        other_character = Character.objects.create(game=self.other, name='Stranger')
        DialogueLine.objects.create(room=room, speaker=other_character, text='Wrong line')
        other_item = Item.objects.create(game=self.other, name='Gem')
        spot = Hotspot.objects.create(
            room=room, label='Barrel', x=0, y=0, width=0.5, height=0.5,
        )
        Action.objects.create(
            game=self.game, verb='use', target_hotspot=spot,
            grant_item=other_item, text='Wrong rule',
        )
        issues = publication_issues(self.game)
        self.assertTrue(any('Wrong exit' in issue and 'destination' in issue for issue in issues))
        self.assertTrue(any('Dialogue line' in issue and 'Speaker' in issue for issue in issues))
        self.assertTrue(any('Action' in issue and 'Reference' in issue for issue in issues))
        self.assertContains(self.admin_publish(), 'Wrong exit')
        self.game.refresh_from_db()
        self.assertFalse(self.game.is_published)

    def test_out_of_bounds_regions_are_reported(self):
        room, _ = self.room_with_image()
        Hotspot.objects.create(
            room=room, label='Outside', x=0.9, y=0, width=0.5, height=0.5,
        )
        self.assertTrue(any('Outside' in issue and 'fit inside' in issue
                            for issue in publication_issues(self.game)))
        self.assertContains(self.admin_publish(), 'Outside')

    def test_unsupported_missing_and_mislabeled_images_are_reported(self):
        _, asset = self.room_with_image()
        other = GameAsset.objects.create(game=self.game, name='Bad extension', image=self.image('wrong.bmp'))
        missing = GameAsset.objects.create(game=self.game, name='Missing', image='games/missing.png')
        mislabeled = GameAsset.objects.create(game=self.game, name='Mislabeled', image=self.image('wrong.jpg'))
        corrupt = GameAsset.objects.create(game=self.game, name='Corrupt', image=SimpleUploadedFile(
            'broken.png', b'not an image',
        ))
        issues = publication_issues(self.game)
        self.assertTrue(any('Bad extension' in issue and 'unsupported' in issue for issue in issues))
        self.assertTrue(any('Missing' in issue and 'missing' in issue for issue in issues))
        self.assertTrue(any('Mislabeled' in issue and 'does not match' in issue for issue in issues))
        self.assertTrue(any('Corrupt' in issue and 'not a readable image' in issue for issue in issues))
        for item in (other, missing, mislabeled, corrupt):
            item.delete()
        self.assertEqual(publication_issues(self.game), [])
        self.assertTrue(asset.image.storage.exists(asset.image.name))

    def test_staff_can_preview_draft_without_exposing_public_content_or_assets(self):
        room, asset = self.room_with_image()
        public_content = reverse('game-content', args=[self.game.pk])
        public_asset = reverse('game-asset', args=[self.game.pk, asset.pk])
        private_asset = reverse('editor-asset-preview', args=[self.game.pk, asset.pk])
        for user in (None, self.viewer):
            if user:
                self.client.force_login(user)
            for url in (self.readiness_url, self.preview_url, private_asset):
                with self.subTest(user=user, url=url):
                    self.assertEqual(self.client.get(url).status_code, 302)
            self.client.logout()

        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.readiness_url), 'No blocking issues found')
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.json()['rooms'][0]['background_url'], private_asset)
        self.assertEqual(response.json()['rooms'][0]['id'], room.pk)
        self.assertEqual(self.client.get(private_asset).status_code, 200)
        self.assertEqual(self.client.get(public_content).status_code, 404)
        self.assertEqual(self.client.get(public_asset).status_code, 404)
        self.assertEqual(self.client.post(self.preview_url).status_code, 405)
        self.assertEqual(
            self.client.get(reverse('editor-game-preview', args=[self.other.pk])).status_code, 409,
        )
