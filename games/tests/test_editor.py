from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.deletion import RestrictedError
from django.contrib.staticfiles.finders import find
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from games.models import Character, Game, GameAsset, Item, Room


class AssetEditorTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings_override = override_settings(MEDIA_ROOT=media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username='editor', password='password', is_staff=True)
        self.regular_user = user_model.objects.create_user(username='viewer', password='password')
        self.game = Game.objects.create(title='Island')
        self.other = Game.objects.create(title='Temple')
        self.list_url = reverse('editor-assets', args=[self.game.pk])

    def image_upload(self, name='dock.png'):
        content = BytesIO()
        Image.new('RGB', (1, 1), 'red').save(content, format='PNG')
        return SimpleUploadedFile(name, content.getvalue(), content_type='image/png')

    def create_asset(self, name='Dock'):
        return GameAsset.objects.create(game=self.game, name=name, image=self.image_upload())

    def test_icon_is_used_by_editor_and_admin(self):
        self.assertIsNotNone(find('games/scummvm_icon.svg'))
        self.client.force_login(self.staff)
        for url in (reverse('editor-games'), reverse('admin:index')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'rel="icon" type="image/svg+xml"')
                self.assertContains(response, '/static/games/scummvm_icon.svg', count=2)

    def test_staff_can_choose_game_and_upload_preview_and_rename_draft_asset(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('editor-games'))
        self.assertContains(response, self.game.title)
        self.assertContains(response, self.other.title)

        response = self.client.post(
            self.list_url, {'name': 'Dock image', 'image': self.image_upload()},
        )
        self.assertRedirects(response, self.list_url)
        asset = GameAsset.objects.get()
        self.assertEqual(asset.game, self.game)
        self.assertIn(f'games/{self.game.pk}/', asset.image.name)
        self.assertContains(self.client.get(self.list_url), 'Dock image')

        preview = self.client.get(reverse('editor-asset-preview', args=[self.game.pk, asset.pk]))
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview['Content-Type'], 'image/png')
        self.assertIn('no-store', preview['Cache-Control'])
        self.assertTrue(b''.join(preview.streaming_content).startswith(b'\x89PNG'))
        self.assertEqual(
            self.client.get(reverse('game-asset', args=[self.game.pk, asset.pk])).status_code, 404,
        )

        edit_url = reverse('editor-asset-edit', args=[self.game.pk, asset.pk])
        self.assertContains(self.client.get(edit_url), 'Dock image')
        self.assertRedirects(self.client.post(edit_url, {'name': 'New name'}), self.list_url)
        asset.refresh_from_db()
        self.assertEqual(asset.name, 'New name')

    def test_invalid_upload_and_name_show_errors_without_saving(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.list_url,
            {'name': 'Not an image', 'image': SimpleUploadedFile('fake.png', b'not an image')},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'valid image')
        self.assertFalse(GameAsset.objects.exists())

        asset = self.create_asset()
        response = self.client.post(
            reverse('editor-asset-edit', args=[self.game.pk, asset.pk]), {'name': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'required')
        asset.refresh_from_db()
        self.assertEqual(asset.name, 'Dock')

    def test_delete_unreferenced_asset_removes_image_file(self):
        self.client.force_login(self.staff)
        asset = self.create_asset()
        storage, filename = asset.image.storage, asset.image.name
        url = reverse('editor-asset-delete', args=[self.game.pk, asset.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(url), self.list_url)
        self.assertFalse(GameAsset.objects.filter(pk=asset.pk).exists())
        self.assertFalse(storage.exists(filename))

    def test_deleting_game_cleans_up_its_files(self):
        asset = self.create_asset()
        storage, filename = asset.image.storage, asset.image.name
        Room.objects.create(game=self.game, name='Dock', background=asset)

        with self.captureOnCommitCallbacks(execute=True):
            self.game.delete()

        self.assertFalse(storage.exists(filename))

    def test_referenced_assets_cannot_be_deleted(self):
        self.client.force_login(self.staff)
        for model in ('room', 'character', 'item'):
            with self.subTest(model=model):
                asset = self.create_asset(name=model)
                if model == 'room':
                    reference = Room.objects.create(game=self.game, name='Dock', background=asset)
                elif model == 'character':
                    reference = Character.objects.create(game=self.game, name='Captain', portrait=asset)
                else:
                    reference = Item.objects.create(game=self.game, name='Key', image=asset)
                delete_url = reverse('editor-asset-delete', args=[self.game.pk, asset.pk])
                response = self.client.post(delete_url, follow=True)
                self.assertContains(response, 'Remove this image')
                self.assertTrue(GameAsset.objects.filter(pk=asset.pk).exists())
                with self.assertRaises(RestrictedError):
                    asset.delete()
                reference.delete()
                self.assertRedirects(self.client.post(delete_url), self.list_url)

    def test_editor_is_staff_only_and_assets_are_game_scoped(self):
        asset = self.create_asset()
        paths = (
            self.list_url,
            reverse('editor-asset-preview', args=[self.game.pk, asset.pk]),
            reverse('editor-asset-edit', args=[self.game.pk, asset.pk]),
            reverse('editor-asset-delete', args=[self.game.pk, asset.pk]),
        )
        for user in (None, self.regular_user):
            if user:
                self.client.force_login(user)
            for path in paths:
                with self.subTest(user=user, path=path):
                    response = self.client.post(path) if path.endswith('/delete/') else self.client.get(path)
                    self.assertEqual(response.status_code, 302)
            self.client.logout()

        self.client.force_login(self.staff)
        for name in ('editor-asset-preview', 'editor-asset-edit', 'editor-asset-delete'):
            with self.subTest(name=name):
                url = reverse(name, args=[self.other.pk, asset.pk])
                response = self.client.post(url) if name == 'editor-asset-delete' else self.client.get(url)
                self.assertEqual(response.status_code, 404)
        self.assertNotContains(self.client.get(reverse('editor-assets', args=[self.other.pk])), asset.name)

    def test_upload_and_delete_require_csrf(self):
        asset = self.create_asset()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)

        self.assertEqual(client.post(self.list_url, {'name': 'Other', 'image': self.image_upload()}).status_code, 403)
        self.assertEqual(
            client.post(reverse('editor-asset-delete', args=[self.game.pk, asset.pk])).status_code, 403,
        )
        self.assertTrue(GameAsset.objects.filter(pk=asset.pk).exists())
