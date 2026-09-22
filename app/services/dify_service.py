import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DifyServiceError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DifyService:
    def __init__(self) -> None:
        self.base_url = str(settings.dify_api_base_url).rstrip("/")
        self.api_key = settings.dify_api_key
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_document_by_text(
        self,
        *,
        dataset_id: str,
        name: str,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "text": text,
            "indexing_technique": "high_quality",
            "process_rule": {
                "mode": "automatic",
            },
        }
        if metadata:
            payload["doc_metadata"] = metadata

        url = f"{self.base_url}/v1/datasets/{dataset_id}/document/create-by-text"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._headers, json=payload)

        if response.status_code >= 400:
            raise DifyServiceError(
                f"Dify ingestion failed: {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    async def stream_chat_message(
        self,
        *,
        query: str,
        user: str,
        conversation_id: Optional[str] = None,
        inputs: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream Dify chat events.
        Yields parsed JSON objects from SSE/chunked lines.
        """
        payload: dict[str, Any] = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "streaming",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        url = f"{self.base_url}/v1/chat-messages"

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                headers={
                    **self._headers,
                    "Accept": "text/event-stream",
                },
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise DifyServiceError(
                        f"Dify chat failed: {body.decode()}",
                        status_code=response.status_code,
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data:"):
                        data_str = line[len("data:") :].strip()
                    else:
                        data_str = line.strip()

                    if not data_str or data_str == "[DONE]":
                        continue

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("Non-JSON Dify stream chunk: %s", data_str)
                        continue

                    yield event

                    if event.get("event") in {"message_end", "error"}:
                        metadata = event.get("metadata") or {}
                        retriever_resources = metadata.get("retriever_resources")
                        if retriever_resources:
                            logger.info(
                                "Dify citations for conversation=%s: %s",
                                conversation_id,
                                retriever_resources,
                            )


dify_service = DifyService()
