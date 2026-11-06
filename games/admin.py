from django.contrib import admin
from django import forms

from .models import Action, Character, DialogueLine, Game, GameAsset, Hotspot, Item, PuzzleFlag, Room, RoomExit
from .readiness import publication_issues


class GamePublicationForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_published') and not self.errors:
            issues = publication_issues(self.instance)
            for issue in issues:
                self.add_error('is_published', issue)
        return cleaned


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    form = GamePublicationForm
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title',)


@admin.register(GameAsset)
class GameAssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'order')
    list_filter = ('game',)


@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):
    list_display = ('label', 'room', 'order')


@admin.register(RoomExit)
class RoomExitAdmin(admin.ModelAdmin):
    list_display = ('label', 'room', 'target_room', 'order')


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)


@admin.register(DialogueLine)
class DialogueLineAdmin(admin.ModelAdmin):
    list_display = ('room', 'speaker', 'order')


@admin.register(PuzzleFlag)
class PuzzleFlagAdmin(admin.ModelAdmin):
    list_display = ('key', 'game')
    list_filter = ('game',)


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ('verb', 'game', 'target_hotspot', 'target_item', 'order')
    list_filter = ('game', 'verb')
