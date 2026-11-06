from django.urls import path

from . import editor_views


urlpatterns = [
    path('', editor_views.game_list, name='editor-games'),
    path('games/<int:game_id>/readiness/', editor_views.game_readiness, name='editor-readiness'),
    path('games/<int:game_id>/preview/', editor_views.game_preview, name='editor-game-preview'),
    path('games/<int:game_id>/rooms/', editor_views.room_list, name='editor-rooms'),
    path('games/<int:game_id>/rooms/<int:room_id>/', editor_views.room_editor, name='editor-room'),
    path('games/<int:game_id>/rooms/<int:room_id>/hotspots/add/', editor_views.hotspot_create, name='editor-hotspot-create'),
    path('games/<int:game_id>/rooms/<int:room_id>/hotspots/<int:spot_id>/', editor_views.hotspot_edit, name='editor-hotspot-edit'),
    path('games/<int:game_id>/rooms/<int:room_id>/hotspots/<int:spot_id>/delete/', editor_views.hotspot_delete, name='editor-hotspot-delete'),
    path('games/<int:game_id>/rooms/<int:room_id>/exits/add/', editor_views.exit_create, name='editor-exit-create'),
    path('games/<int:game_id>/rooms/<int:room_id>/exits/<int:exit_id>/', editor_views.exit_edit, name='editor-exit-edit'),
    path('games/<int:game_id>/rooms/<int:room_id>/exits/<int:exit_id>/delete/', editor_views.exit_delete, name='editor-exit-delete'),
    path('games/<int:game_id>/rooms/<int:room_id>/dialogue/preview/', editor_views.dialogue_preview, name='editor-dialogue-preview'),
    path('games/<int:game_id>/rooms/<int:room_id>/dialogue/add/', editor_views.dialogue_create, name='editor-dialogue-create'),
    path('games/<int:game_id>/rooms/<int:room_id>/dialogue/<int:line_id>/', editor_views.dialogue_edit, name='editor-dialogue-edit'),
    path('games/<int:game_id>/rooms/<int:room_id>/dialogue/<int:line_id>/delete/', editor_views.dialogue_delete, name='editor-dialogue-delete'),
    path('games/<int:game_id>/rooms/<int:room_id>/dialogue/<int:line_id>/<str:direction>/', editor_views.dialogue_move, name='editor-dialogue-move'),
    path('games/<int:game_id>/characters/', editor_views.character_list, name='editor-characters'),
    path('games/<int:game_id>/characters/<int:character_id>/', editor_views.character_edit, name='editor-character-edit'),
    path('games/<int:game_id>/items/', editor_views.item_list, name='editor-items'),
    path('games/<int:game_id>/items/<int:item_id>/', editor_views.item_edit, name='editor-item-edit'),
    path('games/<int:game_id>/flags/', editor_views.flag_list, name='editor-flags'),
    path('games/<int:game_id>/flags/<int:flag_id>/', editor_views.flag_edit, name='editor-flag-edit'),
    path('games/<int:game_id>/flags/<int:flag_id>/delete/', editor_views.flag_delete, name='editor-flag-delete'),
    path('games/<int:game_id>/actions/', editor_views.action_list, name='editor-actions'),
    path('games/<int:game_id>/actions/<int:action_id>/', editor_views.action_edit, name='editor-action-edit'),
    path('games/<int:game_id>/actions/<int:action_id>/delete/', editor_views.action_delete, name='editor-action-delete'),
    path('games/<int:game_id>/assets/', editor_views.asset_list, name='editor-assets'),
    path('games/<int:game_id>/assets/<int:asset_id>/edit/', editor_views.asset_edit, name='editor-asset-edit'),
    path('games/<int:game_id>/assets/<int:asset_id>/delete/', editor_views.asset_delete, name='editor-asset-delete'),
    path('games/<int:game_id>/assets/<int:asset_id>/image/', editor_views.asset_preview, name='editor-asset-preview'),
]
