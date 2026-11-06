from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from games.models import Game, GameAsset, Room


class GameAssetTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings_override = override_settings(MEDIA_ROOT=media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def test_uploaded_image_is_only_served_for_its_published_game(self):
        game = Game.objects.create(title='Island')
        other = Game.objects.create(title='Other', is_published=True)
        image_bytes = BytesIO()
        Image.new('RGB', (1, 1), 'red').save(image_bytes, format='PNG')
        asset = GameAsset.objects.create(
            game=game,
            name='Dock image',
            image=SimpleUploadedFile('dock.png', image_bytes.getvalue(), content_type='image/png'),
        )
        room = Room.objects.create(game=game, name='Dock', background=asset)
        url = reverse('game-asset', args=[game.pk, asset.pk])
        content_url = reverse('game-content', args=[game.pk])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse('game-asset', args=[other.pk, asset.pk])).status_code, 404)
        game.is_published = True
        game.save(update_fields=['is_published'])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(b''.join(response.streaming_content), image_bytes.getvalue())
        self.assertEqual(
            self.client.get(content_url).json()['rooms'][0]['background_url'], url,
        )
        self.assertEqual(room.background_id, asset.pk)

        game.is_published = False
        game.save(update_fields=['is_published'])
        self.assertEqual(self.client.get(url).status_code, 404)
