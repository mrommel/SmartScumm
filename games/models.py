from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Game(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


def asset_path(instance, filename):
    return f'games/{instance.game_id}/{filename}'


IMAGE_CONTENT_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}


class GameAsset(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='assets')
    name = models.CharField(max_length=200)
    image = models.ImageField(
        upload_to=asset_path,
        validators=[FileExtensionValidator(allowed_extensions=[ext[1:] for ext in IMAGE_CONTENT_TYPES])],
    )

    def __str__(self):
        return self.name


@receiver(post_delete, sender=GameAsset)
def remove_deleted_asset_file(sender, instance, **kwargs):
    if instance.image:
        storage = instance.image.storage
        filename = instance.image.name
        transaction.on_commit(lambda: storage.delete(filename))


class Room(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=200)
    background = models.ForeignKey(
        GameAsset, on_delete=models.RESTRICT, null=True, blank=True, related_name='background_rooms',
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')

    def clean(self):
        if self.background_id and self.game_id and self.background.game_id != self.game_id:
            raise ValidationError({'background': 'Background must belong to this game.'})

    def __str__(self):
        return self.name


class Region(models.Model):
    label = models.CharField(max_length=200)
    x = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    y = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    width = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    height = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])

    class Meta:
        abstract = True

    def clean(self):
        errors = {}
        if self.x is not None and self.width is not None and (
            self.width <= 0 or self.x + self.width > 1
        ):
            errors['width'] = 'Region must have positive width and fit inside the background.'
        if self.y is not None and self.height is not None and (
            self.height <= 0 or self.y + self.height > 1
        ):
            errors['height'] = 'Region must have positive height and fit inside the background.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.label


class Hotspot(Region):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='hotspots')
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')


class RoomExit(Region):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='exits')
    target_room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='entrances')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')

    def clean(self):
        super().clean()
        if self.room_id and self.target_room_id and self.room.game_id != self.target_room.game_id:
            raise ValidationError({'target_room': 'Exit destination must belong to this game.'})


class Character(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='characters')
    name = models.CharField(max_length=200)
    portrait = models.ForeignKey(
        GameAsset, on_delete=models.RESTRICT, null=True, blank=True, related_name='portrait_characters',
    )

    def clean(self):
        if self.portrait_id and self.game_id and self.portrait.game_id != self.game_id:
            raise ValidationError({'portrait': 'Portrait must belong to this game.'})

    def __str__(self):
        return self.name


class Item(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    image = models.ForeignKey(
        GameAsset, on_delete=models.RESTRICT, null=True, blank=True, related_name='item_images',
    )

    def clean(self):
        if self.image_id and self.game_id and self.image.game_id != self.game_id:
            raise ValidationError({'image': 'Item image must belong to this game.'})

    def __str__(self):
        return self.name


class DialogueLine(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='dialogue')
    speaker = models.ForeignKey(
        Character, on_delete=models.SET_NULL, null=True, blank=True, related_name='lines',
    )
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')

    def clean(self):
        if self.room_id and self.speaker_id and self.room.game_id != self.speaker.game_id:
            raise ValidationError({'speaker': 'Speaker must belong to this game.'})

    def __str__(self):
        return self.text[:80]


class PuzzleFlag(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='flags')
    key = models.SlugField(max_length=64)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('game', 'key'), name='unique_flag_key_per_game'),
        ]
        ordering = ('key', 'pk')

    def __str__(self):
        return self.key

    def clean(self):
        if self.game_id and self.key and PuzzleFlag.objects.filter(
            game_id=self.game_id, key=self.key,
        ).exclude(pk=self.pk).exists():
            raise ValidationError({'key': 'A flag with this key already exists in this game.'})


class Action(models.Model):
    class Verb(models.TextChoices):
        LOOK = 'look', 'Look'
        PICK_UP = 'pick_up', 'Pick up'
        USE = 'use', 'Use'
        TALK = 'talk', 'Talk'

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='actions')
    verb = models.CharField(max_length=7, choices=Verb.choices)
    target_hotspot = models.ForeignKey(
        Hotspot, on_delete=models.CASCADE, null=True, blank=True, related_name='actions',
    )
    target_item = models.ForeignKey(
        Item, on_delete=models.CASCADE, null=True, blank=True, related_name='targeted_actions',
    )
    input_item = models.ForeignKey(
        Item, on_delete=models.RESTRICT, null=True, blank=True, related_name='input_actions',
    )
    required_item = models.ForeignKey(
        Item, on_delete=models.RESTRICT, null=True, blank=True, related_name='required_actions',
    )
    required_flag = models.ForeignKey(
        PuzzleFlag, on_delete=models.RESTRICT, null=True, blank=True, related_name='required_actions',
    )
    required_flag_value = models.BooleanField(default=True)
    text = models.TextField()
    grant_item = models.ForeignKey(
        Item, on_delete=models.RESTRICT, null=True, blank=True, related_name='granting_actions',
    )
    set_flag = models.ForeignKey(
        PuzzleFlag, on_delete=models.RESTRICT, null=True, blank=True, related_name='setting_actions',
    )
    set_flag_value = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(target_hotspot__isnull=False, target_item__isnull=True)
                    | models.Q(target_hotspot__isnull=True, target_item__isnull=False)
                ),
                name='action_exactly_one_target',
            ),
            models.CheckConstraint(
                condition=models.Q(input_item__isnull=True) | models.Q(verb='use'),
                name='action_input_only_for_use',
            ),
            models.CheckConstraint(
                condition=~models.Q(verb='pick_up') | models.Q(
                    target_hotspot__isnull=False, target_item__isnull=True,
                    grant_item__isnull=False,
                ),
                name='action_pick_up_grants_item',
            ),
        ]

    def clean(self):
        errors = {}
        if bool(self.target_hotspot_id) == bool(self.target_item_id):
            errors['__all__'] = 'Choose exactly one target: a hotspot or an item.'
        if self.input_item_id and self.verb != self.Verb.USE:
            errors['input_item'] = 'An input item can only be used with the Use verb.'
        if self.verb == self.Verb.PICK_UP and (
            not self.target_hotspot_id or not self.grant_item_id
        ):
            errors['grant_item'] = 'Pick up requires a hotspot target and an item to grant.'
        if self.game_id:
            references = {
                'target_hotspot': self.target_hotspot.room.game_id if self.target_hotspot_id else None,
                'target_item': self.target_item.game_id if self.target_item_id else None,
                'input_item': self.input_item.game_id if self.input_item_id else None,
                'required_item': self.required_item.game_id if self.required_item_id else None,
                'required_flag': self.required_flag.game_id if self.required_flag_id else None,
                'grant_item': self.grant_item.game_id if self.grant_item_id else None,
                'set_flag': self.set_flag.game_id if self.set_flag_id else None,
            }
            for field, referenced_game_id in references.items():
                if referenced_game_id is not None and referenced_game_id != self.game_id:
                    errors[field] = 'Reference must belong to this game.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        target = self.target_hotspot or self.target_item
        return f'{self.get_verb_display()} {target}' if target else self.get_verb_display()
