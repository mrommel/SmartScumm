from django.urls import path

from . import views


urlpatterns = [
    path('<int:game_id>/play/', views.game_player, name='game-player'),
    path('<int:game_id>/content/', views.game_content, name='game-content'),
    path('<int:game_id>/assets/<int:asset_id>/', views.game_asset, name='game-asset'),
]
