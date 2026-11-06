from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from games.models import Action, Game, Hotspot, Item, PuzzleFlag, Room


class ActionModelTests(TestCase):
    def setUp(self):
        self.game = Game.objects.create(title='Island', is_published=True)
        self.other = Game.objects.create(title='Temple', is_published=True)
        self.room = Room.objects.create(game=self.game, name='Dock')
        self.spot = Hotspot.objects.create(
            room=self.room, label='Barrel', x=0, y=0, width=0.5, height=0.5,
        )
        self.item = Item.objects.create(game=self.game, name='Key')
        self.flag = PuzzleFlag.objects.create(game=self.game, key='door-open')
        other_room = Room.objects.create(game=self.other, name='Tomb')
        self.other_spot = Hotspot.objects.create(
            room=other_room, label='Statue', x=0, y=0, width=0.5, height=0.5,
        )
        self.other_item = Item.objects.create(game=self.other, name='Gem')
        self.other_flag = PuzzleFlag.objects.create(game=self.other, key='door-open')

    def test_action_rejects_cross_game_references_and_invalid_targets(self):
        for field, value in (
            ('target_hotspot', self.other_spot),
            ('target_item', self.other_item),
            ('input_item', self.other_item),
            ('required_item', self.other_item),
            ('grant_item', self.other_item),
            ('required_flag', self.other_flag),
            ('set_flag', self.other_flag),
        ):
            with self.subTest(field=field):
                action = Action(game=self.game, verb='use', target_hotspot=self.spot, text='Done')
                if field == 'target_item':
                    action.target_hotspot = None
                setattr(action, field, value)
                with self.assertRaises(ValidationError) as error:
                    action.full_clean()
                self.assertIn(field, error.exception.message_dict)

        for target in ({}, {'target_hotspot': self.spot, 'target_item': self.item}):
            with self.subTest(target=target):
                with self.assertRaises(ValidationError) as error:
                    Action(game=self.game, verb='look', text='Hello', **target).full_clean()
                self.assertIn('__all__', error.exception.message_dict)

    def test_verb_and_pick_up_requirements(self):
        for kwargs, field in (
            ({'verb': 'look', 'input_item': self.item}, 'input_item'),
            ({'verb': 'pick_up'}, 'grant_item'),
            ({'verb': 'pick_up', 'target_hotspot': None, 'target_item': self.item,
              'grant_item': self.item}, 'grant_item'),
        ):
            with self.subTest(kwargs=kwargs):
                action = Action(**{
                    'game': self.game, 'target_hotspot': self.spot, 'text': 'Done', **kwargs,
                })
                with self.assertRaises(ValidationError) as error:
                    action.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_flag_keys_are_unique_within_a_game_and_database_checks_target(self):
        with self.assertRaises(ValidationError):
            PuzzleFlag(game=self.game, key='door-open').full_clean()
        PuzzleFlag(game=self.other, key='another-flag').full_clean()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Action.objects.create(game=self.game, verb='look', text='Invalid')

    def test_published_actions_are_ordered_and_drafts_remain_private(self):
        Action.objects.create(game=self.other, verb='talk', target_hotspot=self.other_spot, text='Hidden')
        first = Action.objects.create(
            game=self.game, verb='use', target_hotspot=self.spot, input_item=self.item,
            required_item=self.item, required_flag=self.flag, required_flag_value=False,
            text='Unlocked', set_flag=self.flag, set_flag_value=True, order=4,
        )
        second = Action.objects.create(
            game=self.game, verb='pick_up', target_hotspot=self.spot,
            text='Found it', grant_item=self.item, order=4,
        )
        third = Action.objects.create(
            game=self.game, verb='look', target_item=self.item, text='A rusty key', order=1,
        )
        url = reverse('game-content', args=[self.game.pk])
        content = self.client.get(url).json()
        self.assertEqual(content['format_version'], 3)
        self.assertEqual(content['flags'], [{'key': 'door-open', 'initial': False}])
        self.assertEqual([rule['id'] for rule in content['actions']], [third.pk, first.pk, second.pk])
        self.assertEqual(content['actions'][0]['target'], {'kind': 'item', 'id': self.item.pk})
        self.assertEqual(content['actions'][1], {
            'id': first.pk, 'verb': 'use', 'target': {'kind': 'hotspot', 'id': self.spot.pk},
            'input_item_id': self.item.pk, 'required_item_id': self.item.pk,
            'required_flag': {'key': 'door-open', 'value': False},
            'text': 'Unlocked', 'grant_item_id': None,
            'set_flag': {'key': 'door-open', 'value': True}, 'order': 4,
        })
        self.assertEqual(content['actions'][2]['grant_item_id'], self.item.pk)
        self.assertNotIn('Hidden', str(content))
        self.game.is_published = False
        self.game.save(update_fields=['is_published'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_action_written_outside_editor_is_not_published(self):
        Action.objects.create(
            game=self.game, verb='look', target_item=self.other_item, text='Cross-game',
        )
        with self.assertRaises(ValidationError):
            self.client.get(reverse('game-content', args=[self.game.pk]))

    def test_deleting_game_cascades_through_actions_and_flags(self):
        Action.objects.create(
            game=self.game, verb='use', target_hotspot=self.spot, input_item=self.item,
            required_flag=self.flag, grant_item=self.item, set_flag=self.flag, text='Done',
        )
        self.game.delete()
        self.assertFalse(Action.objects.exists())
        self.assertFalse(PuzzleFlag.objects.filter(pk=self.flag.pk).exists())
        self.assertTrue(Game.objects.filter(pk=self.other.pk).exists())


class ActionEditorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username='editor', password='password', is_staff=True)
        self.regular = user_model.objects.create_user(username='viewer', password='password')
        self.game = Game.objects.create(title='Island')
        self.other = Game.objects.create(title='Temple')
        self.room = Room.objects.create(game=self.game, name='Dock')
        self.spot = Hotspot.objects.create(
            room=self.room, label='Barrel', x=0, y=0, width=0.5, height=0.5,
        )
        other_room = Room.objects.create(game=self.other, name='Tomb')
        self.other_spot = Hotspot.objects.create(
            room=other_room, label='Statue', x=0, y=0, width=0.5, height=0.5,
        )
        self.item = Item.objects.create(game=self.game, name='Key')
        self.other_item = Item.objects.create(game=self.other, name='Gem')
        self.flags_url = reverse('editor-flags', args=[self.game.pk])
        self.actions_url = reverse('editor-actions', args=[self.game.pk])

    def action_fields(self, **overrides):
        return {
            'verb': 'use', 'target_hotspot': self.spot.pk, 'target_item': '',
            'input_item': self.item.pk, 'required_item': '', 'required_flag': '',
            'text': 'Click!', 'grant_item': '', 'set_flag': '', 'order': 0,
            **overrides,
        }

    def test_game_scoped_forms_and_validation_errors(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.actions_url)
        self.assertContains(response, 'Barrel')
        self.assertNotContains(response, 'Statue')
        self.assertNotContains(response, 'Gem')
        for field, value in (
            ('target_hotspot', self.other_spot.pk),
            ('input_item', self.other_item.pk),
        ):
            with self.subTest(field=field):
                response = self.client.post(self.actions_url, self.action_fields(**{field: value}))
                self.assertContains(response, 'Select a valid choice')
                self.assertFalse(Action.objects.exists())
        response = self.client.post(self.actions_url, self.action_fields(target_item=self.item.pk))
        self.assertContains(response, 'Choose exactly one target')
        response = self.client.post(self.actions_url, self.action_fields(verb='pick_up', input_item=''))
        self.assertContains(response, 'Pick up requires')
        self.assertFalse(Action.objects.exists())

    def test_create_edit_delete_actions_and_flags_on_draft(self):
        self.client.force_login(self.staff)
        self.assertRedirects(
            self.client.post(self.flags_url, {'key': 'door-open', 'description': 'Entrance'}),
            self.flags_url,
        )
        flag = PuzzleFlag.objects.get(game=self.game)
        self.assertContains(
            self.client.post(self.flags_url, {'key': 'door-open', 'description': ''}),
            'already exists',
        )
        self.assertRedirects(
            self.client.post(self.actions_url, self.action_fields(
                required_flag=flag.pk, set_flag=flag.pk, set_flag_value='on',
            )),
            self.actions_url,
        )
        action = Action.objects.get(game=self.game)
        self.assertEqual(action.input_item, self.item)
        self.assertEqual(action.required_flag, flag)
        self.assertEqual(action.set_flag, flag)
        flag_edit = reverse('editor-flag-edit', args=[self.game.pk, flag.pk])
        self.assertRedirects(
            self.client.post(flag_edit, {'key': 'door-open', 'description': 'Opened entrance'}),
            self.flags_url,
        )
        flag.refresh_from_db()
        self.assertEqual(flag.description, 'Opened entrance')
        action_edit = reverse('editor-action-edit', args=[self.game.pk, action.pk])
        self.assertRedirects(
            self.client.post(action_edit, self.action_fields(
                text='A new response', order=3, required_flag=flag.pk, set_flag=flag.pk,
            )),
            self.actions_url,
        )
        action.refresh_from_db()
        self.assertEqual((action.text, action.order), ('A new response', 3))
        flag_delete = reverse('editor-flag-delete', args=[self.game.pk, flag.pk])
        self.assertRedirects(self.client.post(flag_delete), self.flags_url)
        self.assertTrue(PuzzleFlag.objects.filter(pk=flag.pk).exists())
        self.assertRedirects(
            self.client.post(reverse('editor-action-delete', args=[self.game.pk, action.pk])),
            self.actions_url,
        )
        self.assertRedirects(self.client.post(flag_delete), self.flags_url)
        self.assertFalse(PuzzleFlag.objects.filter(pk=flag.pk).exists())

    def test_staff_csrf_and_game_boundaries(self):
        action = Action.objects.create(
            game=self.other, verb='look', target_hotspot=self.other_spot, text='Other',
        )
        flag = PuzzleFlag.objects.create(game=self.other, key='secret')
        paths = [
            self.flags_url, self.actions_url,
            reverse('editor-flag-edit', args=[self.game.pk, flag.pk]),
            reverse('editor-flag-delete', args=[self.game.pk, flag.pk]),
            reverse('editor-action-edit', args=[self.game.pk, action.pk]),
            reverse('editor-action-delete', args=[self.game.pk, action.pk]),
        ]
        for user in (None, self.regular):
            if user:
                self.client.force_login(user)
            for path in paths:
                with self.subTest(user=user, path=path):
                    self.assertEqual(self.client.get(path).status_code, 302)
                    self.assertEqual(self.client.post(path).status_code, 302)
            self.client.logout()
        self.client.force_login(self.staff)
        for path in paths[2:]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 405 if path.endswith('/delete/') else 404)
                self.assertEqual(self.client.post(path).status_code, 404)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(self.actions_url, self.action_fields()).status_code, 403)
        self.assertEqual(csrf_client.post(self.flags_url, {'key': 'unsafe'}).status_code, 403)
        self.assertEqual(self.client.get(self.actions_url).status_code, 200)
        self.assertEqual(self.client.get(self.flags_url).status_code, 200)
