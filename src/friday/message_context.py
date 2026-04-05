import json

from pydantic import BaseModel


class MessageContext(BaseModel):
    channel: str
    session_key: str
    actor_key: str | None
    chat_id: str
    sender_id: str | None
    display_name: str | None
    message_text: str


def parse_message_context(
    *,
    channel: str,
    session_id: str,
    chat_id: str,
    raw_content: str,
) -> MessageContext:
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError:
        payload = {"message": raw_content}
    sender_id = payload.get("sender_id")
    actor_key = f"{channel}:{sender_id}" if sender_id else None
    return MessageContext(
        channel=channel,
        session_key=session_id,
        actor_key=actor_key,
        chat_id=chat_id,
        sender_id=sender_id,
        display_name=payload.get("full_name") or payload.get("username"),
        message_text=payload.get("message", ""),
    )
