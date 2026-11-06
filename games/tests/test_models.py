from django.contrib import admin
from django.test import TestCase

from games.models import Game


class GameTests(TestCase):
    def test_multiple_games_can_be_created(self):
        first = Game.objects.create(title='Island Mystery', description='A coastal adventure')
        second = Game.objects.create(title='Lost Temple')

        self.assertEqual(list(Game.objects.order_by('pk')), [first, second])
        self.assertEqual(str(first), 'Island Mystery')
        self.assertEqual(second.description, '')
        self.assertIsNotNone(first.created_at)

    def test_game_is_registered_in_admin(self):
        self.assertIn(Game, admin.site._registry)

    def test_games_are_unpublished_by_default(self):
        game = Game.objects.create(title='Draft')

        self.assertFalse(game.is_published)
