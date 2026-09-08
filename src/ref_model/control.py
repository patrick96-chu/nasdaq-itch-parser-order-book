from src.ref_model.structs import *

class Control:
    """
    Keeps track of control-side states.
    Returns whether stock is active (open for quotation or trading).
    Returns not-None stock_locate on first directory message to initialize book.
    """
    def __init__(self):
        self.initialized = False
        self.market_code = None
        self.stock_symbol = None

        self.msg_hours = False
        self.sys_hours = False
        self.mkt_hours = False
        self.stock_halt = True
        self.market_halt = False

        self.stock_locate = None

    def init_params(self, market_code: str, stock_symbol: str):
        # if self.initialized:
        #     return ControlResult.error("Already initialized.")
        assert not self.initialized, "Control module already initialized."

        self.initialized = True
        self.market_code = market_code
        self.stock_symbol = stock_symbol

    def process_msg(self, msg: ITCHMsg):
        if not self.initialized:
            return ControlResult.error("Control module received msg while not initialized.")

        msg_expected = self.msg_hours
        stock_locate = None
        match msg.msg_type:
            case ITCHMsgType.EVENT:
                assert isinstance(msg, SystemEventMsg), f"Incorrect msg object type for {msg.msg_type}."

                match msg.event_code:
                    case SystemEventCode.MSG_BEGIN:
                        assert not self.msg_hours, "Incorrect msg_hours."
                        self.msg_hours = True
                        msg_expected = True
                    case SystemEventCode.SYS_BEGIN:
                        assert not self.sys_hours, "Incorrect sys_hours."
                        self.sys_hours = True
                    case SystemEventCode.MKT_BEGIN:
                        assert not self.mkt_hours, "Incorrect mkt_hours."
                        self.mkt_hours = True
                    case SystemEventCode.MKT_END:
                        assert self.mkt_hours, "Incorrect mkt_hours."
                        self.mkt_hours = False
                    case SystemEventCode.SYS_END:
                        assert self.sys_hours, "Incorrect sys_hours."
                        self.sys_hours = False
                    case SystemEventCode.MSG_END:
                        assert self.msg_hours, "Incorrect msg_hours."
                        self.msg_hours = False
                    case _:
                        assert False, "Unexpected event_code."

            case ITCHMsgType.DIRECTORY:
                assert isinstance(msg, DirectoryMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.stock_symbol == self.stock_symbol:
                    if self.stock_locate is not None and msg.stock_locate != self.stock_locate:
                        return ControlResult.error(f"Received mismatch stock locate {msg.stock_locate} in secondary directory message.")
                        # return ControlResult.error(f"Stock locate {self.stock_locate} already exists. Received directory msg: {msg.stock_locate}")

                    self.stock_locate = msg.stock_locate
                    stock_locate = self.stock_locate # output

            case ITCHMsgType.ACTION:
                assert isinstance(msg, TradeActionMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.stock_symbol == self.stock_symbol:
                    match msg.trade_action:
                        case TradeActionCode.HALT | TradeActionCode.PAUSE:
                            self.stock_halt = True
                        case TradeActionCode.QUOTE | TradeActionCode.TRADE:
                            self.stock_halt = False
                        case _:
                            assert False, "Unexpected trade_action."

            case ITCHMsgType.HALT:
                assert isinstance(msg, OpHaltMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.stock_symbol == self.stock_symbol and msg.market_code == self.market_code:
                    assert self.market_halt != msg.is_halt, "Incorrect is_halt."
                    self.market_halt = msg.is_halt

        if not msg_expected:
            return ControlResult.error("Received msg while not msg_hours.")

        stock_active = (self.msg_hours and
                        self.sys_hours and
                        not self.stock_halt and
                        not self.market_halt)

        return ControlResult(
            stock_active = stock_active,
            stock_locate = stock_locate,
        )
