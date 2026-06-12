import json
from uuid import uuid4
from a2a.types import SendMessageRequest, MessageSendParams, Message, Role, Part, TextPart

message = Message(
    role=Role.user,
    parts=[Part(root=TextPart(text="my question"))],
    message_id=str(uuid4()),
)
request = SendMessageRequest(
    id=str(uuid4()),
    params=MessageSendParams(message=message),
)

print(request.model_dump_json(indent=2))
