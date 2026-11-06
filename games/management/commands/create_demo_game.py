from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from games.demo import DEMO_TITLE, create_demo_adventure
from games.models import Game


class Command(BaseCommand):
    help = 'Create and publish an original two-room adventure for testing the browser player.'

    def handle(self, *args, **options):
        if Game.objects.filter(title=DEMO_TITLE).exists():
            raise CommandError(f'A game named "{DEMO_TITLE}" already exists.')
        try:
            game = create_demo_adventure()
        except ValidationError as error:
            raise CommandError('; '.join(error.messages)) from error
        self.stdout.write(self.style.SUCCESS(f'Demo game published: /games/{game.pk}/play/'))
