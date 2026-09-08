from enum import Enum, auto
from dataclasses import dataclass, field

@dataclass
class ModuleResult:
    error_flag: bool = False
    error_code: str = ""

    prefix: str = field(default="", init=False)
    @classmethod
    def forward_error(cls, result):
        return cls.error(result.prefix + result.error_code)

# ==========================================
# MOLDUDP64 PARSER
# ==========================================
@dataclass(kw_only=True)
class MoldUDP64ParserResult(ModuleResult):
    payload: list[bytearray]
    # seq_expected: int
    # seq_received: int
    # seq_error: bool

    prefix: str = field(default="(NP) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            payload=None,
            # seq_expected=0,
            # seq_received=0,
            # seq_error=False,
        )

# ==========================================
# ITCH PARSER
# ==========================================
class ITCHMsgType(Enum):
    EVENT     = auto() # ord('S')
    DIRECTORY = auto() # ord('R')
    ACTION    = auto() # ord('H')
    HALT      = auto() # ord('h')
    ADD       = auto() # ord('A')
    # ADD_MPID  = auto() # ord('F')
    # EXECUTE   = auto() # ord('E')
    # EXECUTE_P = auto() # ord('C')
    # CANCEL    = auto() # ord('X')
    REDUCE    = auto()
    DELETE    = auto() # ord('D')
    REPLACE   = auto() # ord('U')
    IGNORE    = auto()

class SystemEventCode(Enum):
    MSG_BEGIN = ord('O')
    SYS_BEGIN = ord('S')
    MKT_BEGIN = ord('Q')
    MKT_END   = ord('M')
    SYS_END   = ord('E')
    MSG_END   = ord('C')

class TradeActionCode(Enum):
    HALT      = ord('H')
    PAUSE     = ord('P')
    QUOTE     = ord('Q')
    TRADE     = ord('T')

@dataclass
class ITCHMsg:
    msg_type: ITCHMsgType
    stock_locate: int
    # tracking_num: int
    # timestamp: int

    def is_ctrl_msg(self):
        return isinstance(self, (SystemEventMsg, DirectoryMsg, TradeActionMsg, OpHaltMsg))

    def is_book_msg(self):
        return isinstance(self, (AddOrderMsg, ReduceOrderMsg, DeleteOrderMsg, ReplaceOrderMsg))

@dataclass
class ITCHCtrlMsg(ITCHMsg):
    pass

@dataclass
class ITCHBookMsg(ITCHMsg):
    pass

@dataclass
class SystemEventMsg(ITCHCtrlMsg):
    event_code: SystemEventCode
    msg_type: ITCHMsgType = field(default=ITCHMsgType.EVENT, init=False)

@dataclass
class DirectoryMsg(ITCHCtrlMsg):
    stock_symbol: str
    msg_type: ITCHMsgType = field(default=ITCHMsgType.DIRECTORY, init=False)

@dataclass
class TradeActionMsg(ITCHCtrlMsg):
    stock_symbol: str
    trade_action: TradeActionCode
    msg_type: ITCHMsgType = field(default=ITCHMsgType.ACTION, init=False)

@dataclass
class OpHaltMsg(ITCHCtrlMsg):
    stock_symbol: str
    market_code: str
    is_halt: bool
    msg_type: ITCHMsgType = field(default=ITCHMsgType.HALT, init=False)

@dataclass
class AddOrderMsg(ITCHBookMsg):
    order_id: int
    is_buy: bool
    shares: int
    price: int
    msg_type: ITCHMsgType = field(default=ITCHMsgType.ADD, init=False)

@dataclass
class ReduceOrderMsg(ITCHBookMsg):
    order_id: int
    shares: int
    msg_type: ITCHMsgType = field(default=ITCHMsgType.REDUCE, init=False)

@dataclass
class DeleteOrderMsg(ITCHBookMsg):
    order_id: int
    msg_type: ITCHMsgType = field(default=ITCHMsgType.DELETE, init=False)

@dataclass
class ReplaceOrderMsg(ITCHBookMsg):
    order_id: int
    shares: int
    price: int
    msg_type: ITCHMsgType = field(default=ITCHMsgType.REPLACE, init=False)

@dataclass(kw_only=True)
class ITCHParserResult(ModuleResult):
    parsed_msg: ITCHMsg

    prefix: str = field(default="(IP) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            parsed_msg=None,
        )

# ==========================================
# CONTROL
# ==========================================

@dataclass(kw_only=True)
class ControlResult(ModuleResult):
    stock_active: bool
    stock_locate: int

    prefix: str = field(default="(CTRL) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            stock_active=False,
            stock_locate=0,
        )

# ==========================================
# Book
# ==========================================

@dataclass
class BBOEntry:
    shares: int
    price: int

@dataclass
class DownstreamOrderMsg:
    msg_type: ITCHMsgType # assert only the 4 order type messages
    is_buy: bool
    shares: int
    price: int

@dataclass(kw_only=True)
class BookResult(ModuleResult):
    bid_entry: BBOEntry
    off_entry: BBOEntry
    spread: int

    prefix: str = field(default="(BOOK) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            bid_entry=None,
            off_entry=None,
            spread=0,
        )


# ==========================================
# BBO
# ==========================================

@dataclass(kw_only=True)
class BBOHalfResult(ModuleResult):
    entry: BBOEntry
    updt_req: bool
    updt_req_mask_enc: int

    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            entry=None,
            updt_req=False,
            updt_req_mask_enc=0
        )

@dataclass(kw_only=True)
class BBOResult(ModuleResult):
    bid_entry: BBOEntry
    off_entry: BBOEntry
    spread: int

    updt_req: bool
    updt_req_is_buy: bool
    updt_req_mask_enc: int

    prefix: str = field(default="(BBO) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            bid_entry=None,
            off_entry=None,
            spread=0,
            updt_req=False,
            updt_req_is_buy=False,
            updt_req_mask_enc=0,
        )


# ==========================================
# L3
# ==========================================

@dataclass
class L3Entry:
    is_buy: bool
    shares: int
    price: int

@dataclass(kw_only=True)
class L3Result(ModuleResult):
    lookup_msg: DownstreamOrderMsg

    prefix: str = field(default="(L3) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            lookup_msg=None,
        )

# ==========================================
# L2
# ==========================================

@dataclass(kw_only=True)
class L2OrderResult(ModuleResult):

    prefix: str = field(default="(L2 MSG) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
        )

@dataclass(kw_only=True)
class L2UpdtReqResult(ModuleResult):
    entry: BBOEntry

    prefix: str = field(default="(L2 UPDT) ", init=False)
    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            entry=None,
        )

# ==========================================
# Top
# ==========================================

@dataclass(kw_only=True)
class TopResult(ModuleResult):
    bid_entry: BBOEntry
    off_entry: BBOEntry
    spread: int

    # seq_expected: int
    # seq_received: int
    # seq_error: bool

    @classmethod
    def error(cls, code):
        return cls(
            error_flag=True,
            error_code=code,
            bid_entry=None,
            off_entry=None,
            spread=0,
            # seq_expected=0,
            # seq_received=0,
            # seq_error=False,
        )
