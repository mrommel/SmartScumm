import json
import shutil
import subprocess
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from games.demo import DEMO_TITLE, create_demo_adventure
from games.models import Game
from games.readiness import publication_issues


class DemoAdventureTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        override = override_settings(MEDIA_ROOT=media.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_command_creates_a_ready_published_game_with_real_assets(self):
        output = StringIO()
        call_command('create_demo_game', stdout=output)
        game = Game.objects.get(title=DEMO_TITLE)
        self.assertIn(reverse('game-player', args=[game.pk]), output.getvalue())
        self.assertTrue(game.is_published)
        self.assertEqual(publication_issues(game), [])
        self.assertEqual(self.client.get(reverse('game-player', args=[game.pk])).status_code, 200)

        content = self.client.get(reverse('game-content', args=[game.pk])).json()
        self.assertEqual(content['format_version'], 3)
        self.assertEqual([room['name'] for room in content['rooms']], ['Harbor', 'Lighthouse'])
        self.assertEqual(len(content['rooms'][0]['exits']), 1)
        self.assertEqual(len(content['rooms'][1]['exits']), 1)
        self.assertEqual(content['flags'], [{'key': 'lantern-lit', 'initial': False}])
        self.assertEqual([item['name'] for item in content['items']], ['Brass key'])
        self.assertEqual(
            set(action['verb'] for action in content['actions']), {'look', 'pick_up', 'use', 'talk'},
        )
        self.assertTrue(any(action['set_flag'] == {'key': 'lantern-lit', 'value': True}
                            for action in content['actions']))
        for asset in game.assets.all():
            response = self.client.get(reverse('game-asset', args=[game.pk, asset.pk]))
            self.assertEqual(response.status_code, 200)
            image_bytes = b''.join(response.streaming_content)
            with Image.open(BytesIO(image_bytes)) as image:
                self.assertEqual(image.format, 'PNG')
                image.verify()

        other = Game.objects.create(title='Unrelated')
        self.assertEqual(self.client.get(reverse('game-content', args=[other.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse('game-asset', args=[other.pk, game.assets.first().pk])).status_code,
            404,
        )
        with self.assertRaisesMessage(CommandError, 'already exists'):
            call_command('create_demo_game', stdout=StringIO())
        self.assertEqual(Game.objects.filter(title=DEMO_TITLE).count(), 1)

    @skipUnless(shutil.which('node'), 'Node.js is required for browser interaction tests')
    def test_published_document_drives_a_complete_browser_puzzle(self):
        game = create_demo_adventure()
        content = self.client.get(reverse('game-content', args=[game.pk])).json()
        script = Path(settings.BASE_DIR) / 'games' / 'tests' / 'verify_demo_player.js'
        result = subprocess.run(
            ['node', str(script)], input=json.dumps(content), text=True,
            capture_output=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
