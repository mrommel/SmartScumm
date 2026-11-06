from django.test import TestCase
from django.urls import reverse

from games.models import Game


class PlayerPageTests(TestCase):
    def test_only_published_games_have_a_player_page(self):
        draft = Game.objects.create(title='Secret')
        public = Game.objects.create(title='Island', is_published=True)
        url = reverse('game-player', args=[public.pk])
        self.assertEqual(self.client.get(reverse('game-player', args=[draft.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('game-player', args=[public.pk + 100])).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 405)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('game-content', args=[public.pk]))
        self.assertContains(response, '/static/games/player_rules.js')
        self.assertContains(response, '/static/games/player.js')
        self.assertContains(response, 'id="verb-select"')
        self.assertContains(response, 'id="action-response"')
        self.assertContains(response, 'id="inventory-items"')
        self.assertContains(response, 'id="input-item-select"')
        self.assertIn('no-store', response['Cache-Control'])

        public.is_published = False
        public.save(update_fields=['is_published'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_game_title_is_escaped_in_player_page(self):
        game = Game.objects.create(title='<script>alert(1)</script>', is_published=True)
        response = self.client.get(reverse('game-player', args=[game.pk]))
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
