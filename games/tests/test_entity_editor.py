from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from games.models import Character, Game, GameAsset, Item


class EntityEditorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username='editor', password='password', is_staff=True)
        self.viewer = user_model.objects.create_user(username='viewer', password='password')
        self.game = Game.objects.create(title='Island', is_published=True)
        self.other_game = Game.objects.create(title='Temple')
        self.asset = GameAsset.objects.create(
            game=self.game, name='Portrait', image='games/1/portrait.png',
        )
        self.other_asset = GameAsset.objects.create(
            game=self.other_game, name='Secret image', image='games/2/secret.png',
        )
        self.client.force_login(self.staff)

    def test_staff_creates_and_edits_character_with_game_image(self):
        list_url = reverse('editor-characters', args=[self.game.pk])
        response = self.client.get(list_url)
        self.assertContains(response, reverse('editor-rooms', args=[self.game.pk]))
        self.assertContains(response, reverse('editor-assets', args=[self.game.pk]))
        self.assertContains(response, 'Portrait')
        self.assertNotContains(response, 'Secret image')
        self.assertContains(self.client.get(reverse('editor-games')), list_url)

        self.assertRedirects(
            self.client.post(list_url, {'name': 'Captain', 'portrait': self.asset.pk}), list_url,
        )
        character = Character.objects.get()
        self.assertEqual(character.game, self.game)
        self.assertEqual(character.portrait, self.asset)
        response = self.client.get(list_url)
        self.assertContains(response, reverse('editor-asset-preview', args=[self.game.pk, self.asset.pk]))
        self.assertContains(response, reverse('editor-asset-edit', args=[self.game.pk, self.asset.pk]))
        self.assertContains(response, reverse('editor-character-edit', args=[self.game.pk, character.pk]))

        edit_url = reverse('editor-character-edit', args=[self.game.pk, character.pk])
        self.assertContains(self.client.get(edit_url), 'Back to characters')
        self.assertRedirects(self.client.post(edit_url, {'name': 'Navigator', 'portrait': ''}), list_url)
        character.refresh_from_db()
        self.assertEqual(character.name, 'Navigator')
        self.assertIsNone(character.portrait)
        self.assertEqual(
            self.client.get(reverse('game-content', args=[self.game.pk])).json()['characters'],
            [{'id': character.pk, 'name': 'Navigator', 'portrait_url': None}],
        )

    def test_staff_creates_and_edits_item_with_game_image(self):
        list_url = reverse('editor-items', args=[self.game.pk])
        self.assertRedirects(
            self.client.post(list_url, {'name': 'Key', 'image': self.asset.pk}), list_url,
        )
        item = Item.objects.get()
        self.assertEqual(item.game, self.game)
        self.assertEqual(item.image, self.asset)
        edit_url = reverse('editor-item-edit', args=[self.game.pk, item.pk])
        self.assertContains(self.client.get(edit_url), 'Back to items')
        self.assertRedirects(self.client.post(edit_url, {'name': 'Old Key', 'image': self.asset.pk}), list_url)
        item.refresh_from_db()
        self.assertEqual(item.name, 'Old Key')
        self.assertEqual(
            self.client.get(reverse('game-content', args=[self.game.pk])).json()['items'],
            [{'id': item.pk, 'name': 'Old Key',
              'image_url': reverse('game-asset', args=[self.game.pk, self.asset.pk])}],
        )

    def test_invalid_images_and_names_are_rejected_on_create_and_edit(self):
        for list_route, edit_route, model, image_field in (
            ('editor-characters', 'editor-character-edit', Character, 'portrait'),
            ('editor-items', 'editor-item-edit', Item, 'image'),
        ):
            with self.subTest(model=model.__name__):
                list_url = reverse(list_route, args=[self.game.pk])
                response = self.client.post(list_url, {'name': 'Wrong', image_field: self.other_asset.pk})
                self.assertContains(response, 'Select a valid choice')
                self.assertFalse(model.objects.filter(name='Wrong').exists())
                entity = model.objects.create(game=self.game, name='Original')
                edit_url = reverse(edit_route, args=[self.game.pk, entity.pk])
                response = self.client.post(edit_url, {'name': 'Wrong', image_field: self.other_asset.pk})
                self.assertContains(response, 'Select a valid choice')
                entity.refresh_from_db()
                self.assertEqual(entity.name, 'Original')
                self.assertIsNone(getattr(entity, image_field))
                response = self.client.post(edit_url, {'name': '', image_field: ''})
                self.assertContains(response, 'required')

    def test_other_games_and_nonstaff_cannot_access_entity_pages(self):
        character = Character.objects.create(game=self.game, name='Captain')
        item = Item.objects.create(game=self.game, name='Key')
        for list_route, edit_route, entity in (
            ('editor-characters', 'editor-character-edit', character),
            ('editor-items', 'editor-item-edit', item),
        ):
            with self.subTest(route=list_route):
                list_url = reverse(list_route, args=[self.game.pk])
                edit_url = reverse(edit_route, args=[self.game.pk, entity.pk])
                self.assertEqual(
                    self.client.get(reverse(edit_route, args=[self.other_game.pk, entity.pk])).status_code,
                    404,
                )
                self.assertEqual(
                    self.client.post(reverse(edit_route, args=[self.other_game.pk, entity.pk])).status_code,
                    404,
                )
                self.assertNotContains(
                    self.client.get(reverse(list_route, args=[self.other_game.pk])), entity.name,
                )
                for user in (None, self.viewer):
                    self.client.logout()
                    if user:
                        self.client.force_login(user)
                    for url in (list_url, edit_url):
                        self.assertEqual(self.client.get(url).status_code, 302)
                        self.assertEqual(self.client.post(url, {'name': 'Wrong'}).status_code, 302)
                self.client.force_login(self.staff)
        self.assertEqual(Character.objects.get(pk=character.pk).name, 'Captain')
        self.assertEqual(Item.objects.get(pk=item.pk).name, 'Key')

    def test_create_and_edit_require_csrf(self):
        item = Item.objects.create(game=self.game, name='Key')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(
            client.post(reverse('editor-characters', args=[self.game.pk]), {'name': 'Wrong'}).status_code,
            403,
        )
        self.assertEqual(
            client.post(reverse('editor-item-edit', args=[self.game.pk, item.pk]), {'name': 'Wrong'}).status_code,
            403,
        )
        self.assertFalse(Character.objects.exists())
        item.refresh_from_db()
        self.assertEqual(item.name, 'Key')
