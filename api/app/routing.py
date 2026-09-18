"""Route answer generation only to the pinned Kanana 3B service."""

import asyncio

from api.app.provider import ModelProvider
from api.app.service import ChatService


class RoutedChatService:
    def __init__(self, primary: ModelProvider):
        self.primary = primary

    async def respond(self, age, history):
        async with asyncio.timeout(self.primary.settings.primary_timeout_seconds):
            answer, action = await ChatService(self.primary).respond(age, history)
            return answer, action, "kanana"
