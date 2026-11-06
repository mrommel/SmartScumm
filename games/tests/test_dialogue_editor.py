from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from games.models import Character, DialogueLine, Game, Room


class DialogueEditorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username='editor', password='password', is_staff=True)
        self.viewer = user_model.objects.create_user(username='viewer', password='password')
        self.game = Game.objects.create(title='Island')
        self.other_game = Game.objects.create(title='Temple')
        self.room = Room.objects.create(game=self.game, name='Dock')
        self.other_room = Room.objects.create(game=self.other_game, name='Tomb')
        self.speaker = Character.objects.create(game=self.game, name='Captain')
        self.other_speaker = Character.objects.create(game=self.other_game, name='Explorer')
        self.room_url = reverse('editor-room', args=[self.game.pk, self.room.pk])
        self.preview_url = reverse('editor-dialogue-preview', args=[self.game.pk, self.room.pk])
        self.client.force_login(self.staff)

    def test_staff_creates_and_edits_ordered_lines_with_optional_speaker(self):
        create_url = reverse('editor-dialogue-create', args=[self.game.pk, self.room.pk])
        self.assertContains(self.client.get(self.room_url), 'id="dialogue-new-form"')
        self.assertRedirects(self.client.post(create_url, {
            'dialogue-new-speaker': self.speaker.pk,
            'dialogue-new-text': 'Welcome aboard!',
            'dialogue-new-order': 0,
        }), self.room_url)
        first = DialogueLine.objects.get()
        self.assertEqual(first.room, self.room)
        self.assertEqual(first.speaker, self.speaker)
        self.assertContains(self.client.get(self.room_url), 'name="dialogue-new-order" value="1"')
        self.assertRedirects(self.client.post(create_url, {
            'dialogue-new-speaker': '',
            'dialogue-new-text': 'The tide is rising.',
            'dialogue-new-order': 1,
        }), self.room_url)
        self.assertEqual(DialogueLine.objects.filter(room=self.room).count(), 2)

        edit_url = reverse('editor-dialogue-edit', args=[self.game.pk, self.room.pk, first.pk])
        self.assertRedirects(self.client.post(edit_url, {
            f'dialogue-{first.pk}-speaker': '',
            f'dialogue-{first.pk}-text': 'Look out!',
            f'dialogue-{first.pk}-order': 3,
        }), self.room_url)
        first.refresh_from_db()
        self.assertEqual((first.speaker, first.text, first.order), (None, 'Look out!', 3))

    def test_speakers_are_scoped_to_the_rooms_game(self):
        create_url = reverse('editor-dialogue-create', args=[self.game.pk, self.room.pk])
        page = self.client.get(self.room_url)
        self.assertContains(page, self.speaker.name)
        self.assertNotContains(page, self.other_speaker.name)
        response = self.client.post(create_url, {
            'dialogue-new-speaker': self.other_speaker.pk,
            'dialogue-new-text': 'Wrong game',
            'dialogue-new-order': 0,
        })
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(DialogueLine.objects.exists())

        line = DialogueLine.objects.create(room=self.room, speaker=self.speaker, text='Original')
        edit_url = reverse('editor-dialogue-edit', args=[self.game.pk, self.room.pk, line.pk])
        response = self.client.post(edit_url, {
            f'dialogue-{line.pk}-speaker': self.other_speaker.pk,
            f'dialogue-{line.pk}-text': 'Wrong game',
            f'dialogue-{line.pk}-order': 0,
        })
        self.assertContains(response, 'Select a valid choice')
        line.refresh_from_db()
        self.assertEqual(line.text, 'Original')
        response = self.client.post(edit_url, {
            f'dialogue-{line.pk}-speaker': '',
            f'dialogue-{line.pk}-text': '',
            f'dialogue-{line.pk}-order': 0,
        })
        self.assertContains(response, 'required')

    def test_move_buttons_reorder_tied_lines_and_delete_is_post_only(self):
        first = DialogueLine.objects.create(room=self.room, text='First')
        second = DialogueLine.objects.create(room=self.room, text='Second')
        third = DialogueLine.objects.create(room=self.room, text='Third')
        up_url = reverse('editor-dialogue-move', args=[self.game.pk, self.room.pk, first.pk, 'up'])
        down_url = reverse('editor-dialogue-move', args=[self.game.pk, self.room.pk, first.pk, 'down'])
        self.assertEqual(self.client.get(down_url).status_code, 405)
        self.assertRedirects(self.client.post(up_url), self.room_url)
        self.assertRedirects(self.client.post(down_url), self.room_url)
        self.assertEqual(
            list(self.room.dialogue.values_list('text', 'order')),
            [('Second', 0), ('First', 1), ('Third', 2)],
        )
        self.assertEqual(
            [line.text for line in self.client.get(self.preview_url).context['lines']],
            ['Second', 'First', 'Third'],
        )
        delete_url = reverse('editor-dialogue-delete', args=[self.game.pk, self.room.pk, third.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        self.assertRedirects(self.client.post(delete_url), self.room_url)
        self.assertFalse(DialogueLine.objects.filter(pk=third.pk).exists())
        self.assertEqual(self.client.post(
            reverse('editor-dialogue-move', args=[self.game.pk, self.room.pk, first.pk, 'sideways']),
        ).status_code, 404)

    def test_preview_includes_drafts_in_order_without_leaking_other_games(self):
        DialogueLine.objects.create(room=self.room, speaker=self.speaker, text='Later', order=10)
        DialogueLine.objects.create(room=self.room, text='<script>Early</script>', order=1)
        DialogueLine.objects.create(room=self.other_room, text='Secret', order=0)

        self.assertEqual(self.client.get(reverse('game-content', args=[self.game.pk])).status_code, 404)
        preview = self.client.get(self.preview_url)
        self.assertEqual(preview.status_code, 200)
        self.assertIn('no-store', preview['Cache-Control'])
        self.assertContains(preview, 'Back to room editor')
        self.assertNotContains(preview, 'Secret')
        self.assertContains(preview, '&lt;script&gt;Early&lt;/script&gt;')
        self.assertLess(preview.content.index(b'Early'), preview.content.index(b'Later'))
        self.assertEqual(
            list(preview.context['lines'].values_list('text', flat=True)),
            ['<script>Early</script>', 'Later'],
        )

    def test_other_room_and_nonstaff_cannot_edit_or_preview_dialogue(self):
        line = DialogueLine.objects.create(room=self.room, text='Private draft')
        for route, args in (
            ('editor-dialogue-preview', [self.other_game.pk, self.room.pk]),
            ('editor-dialogue-edit', [self.other_game.pk, self.room.pk, line.pk]),
            ('editor-dialogue-delete', [self.other_game.pk, self.room.pk, line.pk]),
            ('editor-dialogue-move', [self.other_game.pk, self.room.pk, line.pk, 'up']),
            ('editor-dialogue-edit', [self.other_game.pk, self.other_room.pk, line.pk]),
        ):
            url = reverse(route, args=args)
            response = self.client.get(url) if route == 'editor-dialogue-preview' else self.client.post(url)
            self.assertEqual(response.status_code, 404)
        for user in (None, self.viewer):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.get(self.preview_url).status_code, 302)
            self.assertEqual(self.client.post(
                reverse('editor-dialogue-delete', args=[self.game.pk, self.room.pk, line.pk]),
            ).status_code, 302)
        self.assertTrue(DialogueLine.objects.filter(pk=line.pk).exists())

    def test_dialogue_changes_require_csrf(self):
        line = DialogueLine.objects.create(room=self.room, text='Original')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post(
            reverse('editor-dialogue-create', args=[self.game.pk, self.room.pk]),
            {'dialogue-new-text': 'Wrong', 'dialogue-new-order': 0},
        ).status_code, 403)
        self.assertEqual(client.post(
            reverse('editor-dialogue-move', args=[self.game.pk, self.room.pk, line.pk, 'down']),
        ).status_code, 403)
        self.assertEqual(DialogueLine.objects.count(), 1)
