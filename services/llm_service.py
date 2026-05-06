import httpx
import json
from groq import AsyncGroq
from loguru import logger
from config import settings
from typing import AsyncIterator, List, Dict, Optional

SYSTEM_PROMPT = """You are InsurBot, a concise insurance specialist AI for Sri Lanka. Answer insurance questions accurately and briefly. Cover: life/health/motor/property policies, IRCSL regulations, NCD, claims, major Sri Lankan insurers (Ceylinco Life, AIA, SLIC, Allianz, HNB Assurance). Keep answers under 200 words. Use bullet points for lists."""


class LLMService:
    def __init__(self):
        self.model = settings.groq_model
        self._client: Optional[AsyncGroq] = None

    def _get_client(self) -> AsyncGroq:
        if self._client is None:
            self._client = AsyncGroq(api_key=settings.groq_api_key)
        return self._client

    def _build_messages(
        self,
        user_message: str,
        context: str,
        history: List[Dict[str, str]],
    ) -> List[Dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context:
            messages.append({
                "role": "system",
                "content": f"Use this knowledge base context to answer:\n\n{context}"
            })

        for turn in history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_message})
        return messages

    async def generate_stream(
        self,
        user_message: str,
        context: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        messages = self._build_messages(user_message, context, history or [])

        stream = await client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            stream=True,
            max_tokens=512,
            temperature=0.7,
        )

        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    async def generate(
        self,
        user_message: str,
        context: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
    ) -> str:
        full = ""
        async for token in self.generate_stream(user_message, context, history, model):
            full += token
        return full.strip()

    async def is_available(self) -> bool:
        if not settings.groq_api_key or settings.groq_api_key == "your-groq-api-key-here":
            return False
        try:
            client = self._get_client()
            await client.models.list()
            return True
        except Exception:
            return False

    async def get_models(self) -> List[str]:
        try:
            client = self._get_client()
            resp = await client.models.list()
            return [m.id for m in resp.data]
        except Exception:
            return []


llm_service = LLMService()
