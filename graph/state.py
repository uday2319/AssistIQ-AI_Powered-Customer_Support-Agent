from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict

class SupportState(TypedDict,total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    refund_info:dict
    human_approval:str
    refund_order_id: str