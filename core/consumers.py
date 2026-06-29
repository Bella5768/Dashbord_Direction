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
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        for g in getattr(self, 'project_groups', []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def notif_new(self, event):
        await self.send(text_data=json.dumps({'msg_type': 'notif', **event['data']}))

    async def project_update(self, event):
        await self.send(text_data=json.dumps({'msg_type': 'proj', **event['data']}))

    @database_sync_to_async
    def _project_ids(self, user):
        from .models import ProjectMember, Project
        if user.is_staff:
            return list(Project.objects.values_list('id', flat=True))
        ids = set(
            ProjectMember.objects.filter(
                employee__user_profile__user=user
            ).values_list('project_id', flat=True)
        )
        ids.update(
            Project.objects.filter(
                manager_employee__user_profile__user=user
            ).values_list('id', flat=True)
        )
        return list(ids)


class ProjectConsumer(AsyncWebsocketConsumer):
    """Conservé pour les admins/non-membres sur la page détail projet."""
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.group_name = f'project_{self.project_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def project_update(self, event):
        await self.send(text_data=json.dumps(event['data']))
