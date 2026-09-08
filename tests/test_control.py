from src.ref_model.top import Top
from src.utils.rst_init import *
from src.ref_model.structs import *

from tests.assertions import *
from tests.pkt_gen import *

def test_no_init_params():
    print()

    ref = ref_rst()
    msg = SystemEventMsg(0, SystemEventCode.MSG_BEGIN)
    assert_error_msg(ref.test_process_ctrl_msg(msg), "Control module received msg while not initialized.")

def test_no_msg_hours():
    print()

    ref = ref_rst_init("B", "DONTCARE", 0)
    msg = SystemEventMsg(0, SystemEventCode.SYS_BEGIN)
    assert_error_msg(ref.test_process_ctrl_msg(msg), "Received msg while not msg_hours.")

    ref = ref_rst_init("B", "DONTCARE", 0)
    msg = ITCHMsg(ITCHMsgType.IGNORE, 0)
    assert_error_msg(ref.test_process_ctrl_msg(msg), "Received msg while not msg_hours.")

    ref = ref_rst_init("B", "DONTCARE", 0)
    msg = SystemEventMsg(0, SystemEventCode.MSG_BEGIN)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.MSG_END)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = ITCHMsg(ITCHMsgType.IGNORE, 0)
    assert_error_msg(ref.test_process_ctrl_msg(msg), "Received msg while not msg_hours.")

def test_system_event_msg():
    print()

    stock_symbol = gen_random_stock_symbol()

    ref = ref_rst_init("B", stock_symbol, 0)
    msg = SystemEventMsg(0, SystemEventCode.MSG_BEGIN)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(gen_random_stock_locate(), stock_symbol, TradeActionCode.TRADE)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.SYS_BEGIN)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.MKT_BEGIN)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.SYS_END)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.SYS_BEGIN)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.MKT_END)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = SystemEventMsg(0, SystemEventCode.MSG_END)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

def test_directory_msg():
    print()

    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    other_symbol = gen_random_stock_symbol()
    other_locate = gen_random_stock_locate()

    ref = ref_rst_init("B", stock_symbol, 0)
    ref.test_process_ctrl_msg(SystemEventMsg(0, SystemEventCode.MSG_BEGIN))

    msg = DirectoryMsg(stock_locate, stock_symbol)
    exp = ControlResult(stock_active=False, stock_locate=stock_locate)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    # same symbol and locate
    msg = DirectoryMsg(stock_locate, stock_symbol)
    exp = ControlResult(stock_active=False, stock_locate=stock_locate)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    # different symbol and locate
    msg = DirectoryMsg(other_locate, other_symbol)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    # same symbol different locate
    msg = DirectoryMsg(other_locate, stock_symbol)
    assert_error_msg(ref.test_process_ctrl_msg(msg), "Received mismatch stock locate")

def test_trade_action_msg():
    print()

    stock_symbol = gen_random_stock_symbol()
    other_symbol = gen_random_stock_symbol()

    ref = ref_rst_init("B", stock_symbol, 0)
    ref.test_process_ctrl_msg(SystemEventMsg(0, SystemEventCode.MSG_BEGIN))
    ref.test_process_ctrl_msg(SystemEventMsg(0, SystemEventCode.SYS_BEGIN))

    msg = TradeActionMsg(0, other_symbol, TradeActionCode.TRADE)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, stock_symbol, TradeActionCode.TRADE)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, stock_symbol, TradeActionCode.QUOTE)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, other_symbol, TradeActionCode.HALT)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, stock_symbol, TradeActionCode.HALT)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, stock_symbol, TradeActionCode.QUOTE)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, stock_symbol, TradeActionCode.PAUSE)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = TradeActionMsg(0, stock_symbol, TradeActionCode.HALT)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

def test_op_halt_msg():
    print()

    stock_symbol = gen_random_stock_symbol()
    other_symbol = gen_random_stock_symbol()

    market_code = "B"
    other_code = "Q"

    ref = ref_rst_init(market_code, stock_symbol, 0)
    ref.test_process_ctrl_msg(SystemEventMsg(0, SystemEventCode.MSG_BEGIN))
    ref.test_process_ctrl_msg(SystemEventMsg(0, SystemEventCode.SYS_BEGIN))
    ref.test_process_ctrl_msg(TradeActionMsg(0, stock_symbol, TradeActionCode.TRADE))

    msg = OpHaltMsg(0, other_symbol, market_code, True)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = OpHaltMsg(0, other_symbol, other_code, True)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = OpHaltMsg(0, stock_symbol, other_code, True)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = OpHaltMsg(0, stock_symbol, market_code, True)
    exp = ControlResult(stock_active=False, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)

    msg = OpHaltMsg(0, stock_symbol, market_code, False)
    exp = ControlResult(stock_active=True, stock_locate=None)
    assert_matching_result(ref.test_process_ctrl_msg(msg), exp)
