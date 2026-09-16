from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict

class SupportState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    