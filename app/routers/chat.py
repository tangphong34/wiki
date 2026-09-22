import json
import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database.models import Conversation, User
from app.database.session import get_db
from app.dependencies import (
    PHASE1_BYPASS_USER_ID,
    PHASE1_BYPASS_WORKSPACE_ID,
    get_current_user,
)
from app.services.dify_service import DifyServiceError, dify_service

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatMessageRequest(BaseModel):
    query: str = Field(min_length=1)
    conversation_id: Optional[str] = None
    workspace_id: Optional[str] = None
    inputs: dict[str, Any] = Field(default_factory=dict)


@router.post("/message")
async def chat_message(
    payload: ChatMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EventSourceResponse:
    # PHASE 1: Auth bypass — skip workspace membership check
    workspace_uuid = (
        uuid.UUID(payload.workspace_id) if payload.workspace_id else PHASE1_BYPASS_WORKSPACE_ID
    )
    # verify_workspace_access(db, user_id=current_user.id, workspace_id=workspace_uuid)

    dify_conversation_id = payload.conversation_id
    user_id = current_user.id or PHASE1_BYPASS_USER_ID

    async def event_generator():
        try:
            async for event in dify_service.stream_chat_message(
                query=payload.query,
                user=str(user_id),
                conversation_id=dify_conversation_id,
                inputs={
                    **payload.inputs,
                    "workspace_id": str(workspace_uuid),
                },
            ):
                event_name = event.get("event", "message")
                yield {
                    "event": event_name,
                    "data": json.dumps(event),
                }

                if event_name == "message_end":
                    metadata = event.get("metadata") or {}
                    citations = metadata.get("retriever_resources")
                    if citations:
                        logger.info(
                            "Chat citations user=%s conv=%s citations=%s",
                            user_id,
                            dify_conversation_id,
                            citations,
                        )

                    new_conversation_id = event.get("conversation_id")
                    if new_conversation_id and not dify_conversation_id:
                        conversation = Conversation(
                            dify_conversation_id=new_conversation_id,
                            user_id=user_id,
                            workspace_id=workspace_uuid,
                            title=payload.query[:120],
                        )
                        db.add(conversation)
                        db.commit()

        except DifyServiceError as exc:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(exc)}),
            }
        except Exception:
            logger.exception("Unexpected chat stream failure")
            yield {
                "event": "error",
                "data": json.dumps({"message": "Internal chat streaming error"}),
            }

    return EventSourceResponse(event_generator())
