
from pydantic import BaseModel

class TradeRequest(BaseModel):
    symbol: str
    action: str 
    volume: float
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0

class PositionModifyRequest(BaseModel):
    ticket: int
    sl: float
    tp: float

class PositionCloseRequest(BaseModel):
    ticket: int
