import cocotb
from cocotb.triggers import Event
from cocotb.handle import LogicArrayObject
from pathlib import Path
import sys
import logging
from queue import Empty

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.rst_init import *
from src.utils.axis_driver import *
from src.ref_model.structs import *
from src.ref_model.l3_order_table import L3Memory
from tests.pkt_gen import *
from sim.utils.monitors import *
from sim.utils.wrap_tests import extend_test

log = logging.getLogger("testbench")
log.setLevel("INFO")
logging.getLogger("monitor.error").setLevel("WARNING")
logging.getLogger("monitor.output").setLevel("WARNING")
logging.getLogger("driver").setLevel("WARNING")

# dut = itch_parser_interface (moldudp64 parser -> itch parser)

@dataclass
class DecCtrl:
    valid: int
    msg_type: int
    stock_locate: int
    event_code: int
    stock_symbol: int
    trade_action: int
    market: int
    is_halt: int

@dataclass
class DecBook:
    valid: int
    msg_type: int
    has_rep: int
    order_id: int
    is_buy: int
    shares: int
    price: int

class ITCHParserMonitor(OutputMonitor):

    def __init__(self, dut, error_event: Event):
        super().__init__(dut.itch_parser, error_event)

        self.oid_hash_v_q = None
        self.oid_hash_q = None
        self.stock_locate_q = None

    def _process_cycle(self):
        dec_ctrl_o_unpack = self._unpack_ctrl(self.module.dec_ctrl_o)
        dec_book_o_unpack = self._unpack_book(self.module.dec_book_o)

        if dec_ctrl_o_unpack.valid == 1:
            self._log.info("Received dec_ctrl.")
            result = self._decode_ctrl(dec_ctrl_o_unpack)

            try:
                if result != self.expected_outputs.get_nowait():
                    self._log.warning("Received dec_ctrl does not match expected output.")
                    self._fail_event.set()
            except Empty:
                self._log.warning("Did not expect valid dec_ctrl output.")
                self._fail_event.set()

        if dec_book_o_unpack.valid == 1:
            self._log.info("Received dec_book.")
            result = self._decode_book(dec_book_o_unpack)

            try:
                if result != self.expected_outputs.get_nowait():
                    self._log.warning("Received dec_book does not match expected output.")
                    self._fail_event.set()
            except Empty:
                self._log.warning("Did not expect valid dec_book output.")
                self._fail_event.set()

        # ensure oid_hash_q2 matches dec_book_o
        self.oid_hash_q = int(self.module.oid_hash_o.value)
        self.oid_hash_q2 = self.oid_hash_q

    def _unpack_ctrl(self, dec_ctrl_h: LogicArrayObject):
        self._log.debug(f"len(dec_ctrl_h) = {len(dec_ctrl_h.value)}")
        self._log.debug(f"dec_ctrl_h = {hex(dec_ctrl_h.value)}")
        return DecCtrl(
            int(dec_ctrl_h.value[90]),
            int(dec_ctrl_h.value[89:88]),
            int(dec_ctrl_h.value[87:72]),
            int(dec_ctrl_h.value[71:69]),
            int(dec_ctrl_h.value[68:5]),
            int(dec_ctrl_h.value[4:3]),
            int(dec_ctrl_h.value[2:1]),
            int(dec_ctrl_h.value[0]),
        )

    def _unpack_book(self, dec_book_h: LogicArrayObject):
        self._log.debug(f"len(dec_book_h) = {len(dec_book_h.value)}")
        self._log.debug(f"dec_book_h = {hex(dec_book_h.value)}")
        return DecBook(
            int(dec_book_h.value[132]),
            int(dec_book_h.value[131:130]),
            int(dec_book_h.value[129]),
            int(dec_book_h.value[128:65]),
            int(dec_book_h.value[64]),
            int(dec_book_h.value[63:32]),
            int(dec_book_h.value[31:0]),
        )

    def _decode_ctrl(self, dec_ctrl_s: DecCtrl):
        stock_locate = dec_ctrl_s.stock_locate
        stock_symbol = dec_ctrl_s.stock_symbol.to_bytes(8, "big").decode()
        match dec_ctrl_s.msg_type:
            case 0:
                event_code = None
                match dec_ctrl_s.event_code:
                    case 0:
                        event_code = SystemEventCode.MSG_BEGIN
                    case 1:
                        event_code = SystemEventCode.SYS_BEGIN
                    case 2:
                        event_code = SystemEventCode.MKT_BEGIN
                    case 3:
                        event_code = SystemEventCode.MKT_END
                    case 4:
                        event_code = SystemEventCode.SYS_END
                    case 5:
                        event_code = SystemEventCode.MSG_END
                    case _:
                        self._log.warning("ITCH monitor received invalid event code.")
                        self._fail_event.set()
                        # raise AssertionError("ITCH monitor received invalid event code.")

                return SystemEventMsg(stock_locate, event_code)
            case 1:
                return DirectoryMsg(stock_locate, stock_symbol)
            case 2:
                trade_action = None
                match dec_ctrl_s.trade_action:
                    case 0:
                        trade_action = TradeActionCode.HALT
                    case 1:
                        trade_action = TradeActionCode.PAUSE
                    case 2:
                        trade_action = TradeActionCode.QUOTE
                    case 3:
                        trade_action = TradeActionCode.TRADE
                    case _:
                        self._log.warning("ITCH monitor received invalid trade action.")
                        self._fail_event.set()
                        # raise AssertionError("ITCH monitor received invalid trade action.")
                return TradeActionMsg(stock_locate, stock_symbol, trade_action)
            case 3:
                market_code = None
                match dec_ctrl_s.market:
                    case 0:
                        market_code = "Q"
                    case 1:
                        market_code = "B"
                    case 2:
                        market_code = "X"
                    case _:
                        self._log.warning("ITCH monitor received invalid market code.")
                        self._fail_event.set()
                        # raise AssertionError("ITCH monitor received invalid market code.")
                return OpHaltMsg(stock_locate, stock_symbol, market_code, dec_ctrl_s.is_halt == 1)
            case _:
                self._log.warning("ITCH monitor received invalid msg_type for dec_ctrl.")
                self._fail_event.set()
                # raise AssertionError("ITCH monitor received invalid msg_type for dec_ctrl.")

    def _decode_book(self, dec_book_h: DecBook):
        oid_hash = self.oid_hash_q2
        stock_locate = self.stock_locate
        order_id = dec_book_h.order_id
        is_buy   = dec_book_h.is_buy
        shares   = dec_book_h.shares
        price    = dec_book_h.price

        if L3Memory.oid_hash(order_id) != oid_hash:
            self._log.warning("Order ID hash mismatch.")
            self._fail_event.set()

        match dec_book_h.msg_type:
            case 0:
                return AddOrderMsg(stock_locate, order_id, is_buy == 1, shares, price)
            case 1:
                return ReplaceOrderMsg(stock_locate, order_id, shares, price)
            case 2:
                return ReduceOrderMsg(stock_locate, order_id, shares)
            case 3:
                return DeleteOrderMsg(stock_locate, order_id)
            case _:
                self._log.warning("ITCH monitor received invalid msg_type for dec_book.")
                self._fail_event.set()

E = ErrorMonitor
O = ITCHParserMonitor

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_invalid_msg_type(dut, error_monitor: E):
    await dut_rst(dut)
    error_monitor.start()

    pkt = gen_header("TEST_TYPE_", 1, 1) + gen_wrong_msg()
    log.debug("Sending invalid msg pkt.")
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_msg_type, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_system_event(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    pkt = gen_header("TEST_EVENT", 1, 6)
    exp = []
    for code in "OSQMEC":
        pkt += gen_event_msg(code)
        exp.append(SystemEventMsg(0, SystemEventCode(ord(code))))

    log.debug("Sending good pkt.")
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    output_monitor.stop()

    # incorrect length (mismatch caught by ITCH Parser)
    pkt = gen_header("TEST_EVENT", 7, 1)
    pkt += (int.to_bytes(13, 2, "big")
            + b'S'
            + b'\00' * 10
            + bytes("O", encoding="utf-8")
            + b'\00' * 1
    )
    log.debug("Sending incorrect len pkt.")
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_msg_len, dut_send_pkt(dut, pkt))
    error_monitor.stop()

    # unexpected event code
    await dut_rst(dut)
    error_monitor.start()
    log.debug("Sending invalid event code pkt.")
    pkt = gen_header("TEST_EVENT", 1, 1) + gen_event_msg("z")
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_event_code, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_directory(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    stock_symbol = gen_random_stock_symbol()
    pkt = gen_header("TEST_DRCTY", 1, 1) + gen_directory_msg(stock_locate, stock_symbol)
    exp = [DirectoryMsg(stock_locate, stock_symbol)]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_trade_action(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    stock_symbol = gen_random_stock_symbol()
    pkt = gen_header("TEST_ACTN_", 1, 4)
    exp = []
    for code in "HPQT":
        pkt += gen_trade_action_msg(stock_locate, stock_symbol, code)
        exp.append(TradeActionMsg(stock_locate, stock_symbol, TradeActionCode(ord(code))))

    log.debug("Sending good pkt.")
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

    log.debug("Sending invalid event code pkt.")
    pkt = gen_header("TEST_ACTN_", 5, 1) + gen_trade_action_msg(stock_locate, stock_symbol, 'z')
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_trade_action, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_op_halt(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    stock_symbol = gen_random_stock_symbol()

    pkt = gen_header("TEST_HALT_", 1, 6)
    exp = []
    for code in "QBX":
        pkt += gen_op_halt_msg(stock_locate, stock_symbol, code, "H")
        exp.append(OpHaltMsg(stock_locate, stock_symbol, code, True))
        pkt += gen_op_halt_msg(stock_locate, stock_symbol, code, "T")
        exp.append(OpHaltMsg(stock_locate, stock_symbol, code, False))

    log.debug("Sending good pkt.")
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    output_monitor.stop()

    log.debug("Sending invalid market code pkt.")
    pkt = gen_header("TEST_HALT_", 7, 1) + gen_op_halt_msg(stock_locate, stock_symbol, "z", "H")
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_market_code, dut_send_pkt(dut, pkt))
    error_monitor.stop()

    await dut_rst(dut)
    error_monitor.start()
    log.debug("Sending invalid halt code pkt.")
    pkt = gen_header("TEST_HALT_", 1, 1) + gen_op_halt_msg(stock_locate, stock_symbol, "Q", "z")
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_halt_code, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_add(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    output_monitor.stock_locate = stock_locate
    dut.stock_locate_v_i.value = 1
    dut.stock_locate_i.value = stock_locate

    oid_gen = order_id_generator()
    pkt = gen_header("TEST_ADD__", 1, 4)
    exp = []
    for code in "BS":
        oid = next(oid_gen)
        shares = gen_random_shares()
        price = gen_random_price()
        pkt += gen_add_msg(stock_locate, oid, code, shares, price, False)
        exp.append(AddOrderMsg(stock_locate, oid, code == "B", shares, price))

        oid = next(oid_gen)
        shares = gen_random_shares()
        price = gen_random_price()
        pkt += gen_add_msg(stock_locate, oid, code, shares, price, True)
        exp.append(AddOrderMsg(stock_locate, oid, code == "B", shares, price))

    log.debug("Sending good pkt.")
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    output_monitor.stop()

    log.debug("Sending invalid buy/sell code, no mpid pkt.")
    oid = next(oid_gen)
    shares = gen_random_shares()
    price = gen_random_price()
    pkt = gen_header("TEST_ADD__", 5, 1) + gen_add_msg(stock_locate, oid, "z", shares, price, False)
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_buy_sell, dut_send_pkt(dut, pkt))
    error_monitor.stop()

    log.debug("Sending invalid buy/sell code, mpid pkt.")
    await dut_rst(dut)
    error_monitor.start()
    oid = next(oid_gen)
    shares = gen_random_shares()
    price = gen_random_price()
    pkt = gen_header("TEST_ADD__", 1, 1) + gen_add_msg(stock_locate, oid, "z", shares, price, True)
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_buy_sell, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_reduce(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    output_monitor.stock_locate = stock_locate
    dut.stock_locate_v_i.value = 1
    dut.stock_locate_i.value = stock_locate

    oid_gen = order_id_generator()

    pkt = gen_header("TEST_REDCE", 1, 3)

    oid = next(oid_gen)
    shares = gen_random_shares()
    pkt += gen_execute_msg(stock_locate, oid, shares, False)
    exp = [ReduceOrderMsg(stock_locate, oid, shares)]

    oid = next(oid_gen)
    shares = gen_random_shares()
    pkt += gen_execute_msg(stock_locate, oid, shares, True)
    exp += [ReduceOrderMsg(stock_locate, oid, shares)]

    oid = next(oid_gen)
    shares = gen_random_shares()
    pkt += gen_cancel_msg(stock_locate, oid, shares)
    exp += [ReduceOrderMsg(stock_locate, oid, shares)]

    log.debug("Sending good pkt.")
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_delete(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    output_monitor.stock_locate = stock_locate
    dut.stock_locate_v_i.value = 1
    dut.stock_locate_i.value = stock_locate

    oid_gen = order_id_generator()

    pkt = gen_header("TEST_DELTE", 1, 1)
    oid = next(oid_gen)
    pkt += gen_delete_msg(stock_locate, oid)
    exp = [DeleteOrderMsg(stock_locate, oid)]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_replace(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    output_monitor.stock_locate = stock_locate
    dut.stock_locate_v_i.value = 1
    dut.stock_locate_i.value = stock_locate

    oid_gen = order_id_generator()
    pkt = gen_header("TEST_REPLC", 1, 1)

    oid_del = next(oid_gen)
    oid_add = next(oid_gen)
    shares = gen_random_shares()
    price = gen_random_price()
    pkt += gen_replace_msg(stock_locate, oid_del, oid_add, shares, price)
    exp = [DeleteOrderMsg(stock_locate, oid_del),
           ReplaceOrderMsg(stock_locate, oid_add, shares, price)]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_stock_locate(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    stock_locate = gen_random_stock_locate()
    other_locate = gen_random_stock_locate()
    output_monitor.stock_locate = stock_locate
    dut.stock_locate_v_i.value = 1
    dut.stock_locate_i.value = stock_locate

    oid_gen = order_id_generator()

    TEST_SIZE = 10
    pkt = gen_header("TEST_LOCAT", 1, TEST_SIZE)
    exp = []

    for _ in range(TEST_SIZE):
        which_locate = random.random() < 0.5
        oid = next(oid_gen)

        if which_locate:
            pkt += gen_delete_msg(stock_locate, oid)
            exp += [DeleteOrderMsg(stock_locate, oid)]
        else:
            pkt += gen_delete_msg(other_locate, oid)
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
