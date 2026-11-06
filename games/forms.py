from django import forms

from .models import Action, Character, DialogueLine, GameAsset, Hotspot, Item, PuzzleFlag, Room, RoomExit


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            else:
                css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = css_class


class AssetUploadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GameAsset
        fields = ('name', 'image')


class AssetNameForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GameAsset
        fields = ('name',)


class RoomForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Room
        fields = ('name', 'background', 'order')

    def __init__(self, *args, game, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.game = game
        self.fields['background'].queryset = game.assets.order_by('name', 'pk')


class HotspotForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Hotspot
        fields = ('label', 'description', 'x', 'y', 'width', 'height', 'order')

    def __init__(self, *args, room, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.room = room


class RoomExitForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RoomExit
        fields = ('label', 'target_room', 'x', 'y', 'width', 'height', 'order')

    def __init__(self, *args, room, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.room = room
        self.fields['target_room'].queryset = room.game.rooms.order_by('name', 'pk')


class GameImageFormMixin(BootstrapFormMixin):
    def __init__(self, *args, game, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.game = game
        self.fields[self.image_field].queryset = game.assets.order_by('name', 'pk')


class CharacterForm(GameImageFormMixin, forms.ModelForm):
    image_field = 'portrait'

    class Meta:
        model = Character
        fields = ('name', 'portrait')


class ItemForm(GameImageFormMixin, forms.ModelForm):
    image_field = 'image'

    class Meta:
        model = Item
        fields = ('name', 'image')


class DialogueLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DialogueLine
        fields = ('speaker', 'text', 'order')

    def __init__(self, *args, room, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.room = room
        self.fields['speaker'].queryset = room.game.characters.order_by('name', 'pk')


class PuzzleFlagForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PuzzleFlag
        fields = ('key', 'description')

    def __init__(self, *args, game, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.game = game


class ActionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Action
        fields = (
            'verb', 'target_hotspot', 'target_item', 'input_item', 'required_item',
            'required_flag', 'required_flag_value', 'text', 'grant_item',
            'set_flag', 'set_flag_value', 'order',
        )

    def __init__(self, *args, game, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.game = game
        self.fields['target_hotspot'].queryset = Hotspot.objects.filter(
            room__game=game,
        ).select_related('room').order_by('room__name', 'label', 'pk')
        items = game.items.order_by('name', 'pk')
        for field in ('target_item', 'input_item', 'required_item', 'grant_item'):
            self.fields[field].queryset = items
        flags = game.flags.order_by('key', 'pk')
        for field in ('required_flag', 'set_flag'):
            self.fields[field].queryset = flags
