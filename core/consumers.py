import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        self.group_name = f'notif_user_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        # Subscribe to project groups so project updates reach all pages
        self.project_groups = []
        for pid in await self._project_ids(user):
            g = f'project_{pid}'
            await self.channel_layer.group_add(g, self.channel_name)
            self.project_groups.append(g)
        await self.channel_layer.group_add('calendar', self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.channel_layer.group_discard('calendar', self.channel_name)
        for g in getattr(self, 'project_groups', []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def notif_new(self, event):
        await self.send(text_data=json.dumps({'msg_type': 'notif', **event['data']}))

    async def project_update(self, event):
        await self.send(text_data=json.dumps({'msg_type': 'proj', **event['data']}))

    async def calendar_update(self, event):
        await self.send(text_data=json.dumps({'msg_type': 'calendar', **event['data']}))

    @database_sync_to_async
    def _project_ids(self, user):
        from .views import get_accessible_projects_qs
        return list(get_accessible_projects_qs(user).values_list('id', flat=True))
