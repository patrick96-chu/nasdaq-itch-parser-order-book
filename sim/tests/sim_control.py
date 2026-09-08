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
from tests.pkt_gen import *
from sim.utils.monitors import *
from sim.utils.wrap_tests import extend_test

log = logging.getLogger("testbench")
log.setLevel("INFO")
logging.getLogger("monitor.error").setLevel("WARNING")
logging.getLogger("monitor.output").setLevel("WARNING")
logging.getLogger("driver").setLevel("WARNING")

# dut = control_interface (moldudp64 parser -> itch parser -> control)

class ControlMonitor(OutputMonitor):
    """
    Only monitors data outputs.
    For each message, collect complete output and construct corresponding python dataclass.
    Compare against expected list.
    """

    def __init__(self, dut, error_event: Event):
        # need interface's output since interface pulses output valid
        super().__init__(dut, error_event)

    def _process_cycle(self):
        if self.module.output_v_o.value == 1:
            self._log.info("Received control output.")

            stock_active = self.module.stock_active_o.value == 1
            stock_locate_v = self.module.stock_locate_v_o.value == 1
            stock_locate = int(self.module.stock_locate_o.value) if stock_locate_v else None
            result = ControlResult(stock_active=stock_active, stock_locate=stock_locate)

            try:
                if result != self.expected_outputs.get_nowait():
                    self._log.warning("Received control output does not match expected output.")
                    self._fail_event.set()
            except Empty:
                self._log.warning("Did not expect valid control output.")
                self._fail_event.set()

E = ErrorMonitor
O = ControlMonitor

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_no_init_params(dut, error_monitor: E, output_monitor: O):
    await dut_rst(dut)
    error_monitor.start()

    pkt = gen_header("TEST_NINIT", 1, 1) + gen_event_msg("O")
    await error_monitor.wait_for_expect_error(dut.control.error_init, dut_send_pkt(dut, pkt))
    error_monitor.stop()

    # no_init causes error_stock_locate in itch_parser on book message.
    await dut_rst(dut)
    error_monitor.start()
    pkt = gen_header("TEST_NINIT", 1, 1) + gen_delete_msg(gen_random_stock_locate(), next(order_id_generator()))
    await error_monitor.wait_for_expect_error(dut.itch_parser.error_stock_locate, dut_send_pkt(dut, pkt))
    error_monitor.stop()

    await dut_rst(dut)
    error_monitor.start()
    output_monitor.start()

    # should not be any valid dec output, therefore no output nor error
    pkt = gen_header("TEST_NINIT", 1, 1) + gen_ignore_msg()
    await dut_send_pkt(dut, pkt)
    await error_monitor.wait_no_error()

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_no_msg_hours(dut, error_monitor: E, output_monitor: O):
    await dut_rst_init(dut, "B", "DONTCARE", 0)
    error_monitor.start()

    pkt = gen_header("TEST_NMSGH", 1, 1) + gen_event_msg("S")
    await error_monitor.wait_for_expect_error(dut.control.error_msg_hours, dut_send_pkt(dut, pkt))
    error_monitor.stop()

    # removing this because error_stock_locate in itch_parser happens first
    # await dut_rst_init(dut, "B", "DONTCARE", 0)
    # error_monitor.start()
    # pkt = gen_header("TEST_NMSGH", 1, 1) + gen_delete_msg(gen_random_stock_locate(), next(order_id_generator()))
    # await error_monitor.wait_for_expect_error(dut.control.error_msg_hours, dut_send_pkt(dut, pkt))
    # error_monitor.stop()

    await dut_rst_init(dut, "B", "DONTCARE", 0)
    error_monitor.start()
    output_monitor.start()

    pkt = gen_header("TEST_NMSGH", 1, 1) + gen_ignore_msg()
    await dut_send_pkt(dut, pkt)
    await error_monitor.wait_no_error()

    pkt = gen_header("TEST_NMSGH", 2, 2) + gen_event_msg("O") + gen_event_msg("C")
    exp = [ControlResult(stock_active=False, stock_locate=None)] * 2
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    await error_monitor.wait_no_error()

    output_monitor.stop()
    pkt = gen_header("TEST_NMSGH", 4, 1) + gen_event_msg("S")
    await error_monitor.wait_for_expect_error(dut.control.error_msg_hours, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_system_event(dut, error_monitor: E, output_monitor: O):
    stock_symbol = gen_random_stock_symbol()
    await dut_rst_init(dut, "B", stock_symbol, 0)
    error_monitor.start()
    output_monitor.start()

    pkt = (gen_header("TEST_SYS_E", 1, 8) +
           gen_event_msg("O") +
           gen_trade_action_msg(gen_random_stock_locate(), stock_symbol, "T") +
           gen_event_msg("S") +
           gen_event_msg("Q") +
           gen_event_msg("E") +
           gen_event_msg("S") +
           gen_event_msg("M") +
           gen_event_msg("C"))

    exp = [ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ]

    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_directory(dut, error_monitor: E, output_monitor: O):
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()
    other_symbol = gen_random_stock_symbol()
    other_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 0)
    error_monitor.start()
    output_monitor.start()

    pkt = (gen_header("TEST_DRCTY", 1, 4) +
           gen_event_msg("O") +
           gen_directory_msg(stock_locate, stock_symbol) +
           gen_directory_msg(stock_locate, stock_symbol) +
           gen_directory_msg(other_locate, other_symbol))

    exp = [ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=stock_locate),
           ControlResult(stock_active=False, stock_locate=stock_locate),
           ControlResult(stock_active=False, stock_locate=stock_locate),
           ]

    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    output_monitor.stop()

    pkt = gen_header("TEST_DRCTY", 5, 1) + gen_directory_msg(other_locate, stock_symbol)
    await error_monitor.wait_for_expect_error(dut.control.error_stock_locate, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_trade_action(dut, error_monitor: E, output_monitor: O):
    stock_symbol = gen_random_stock_symbol()
    other_symbol = gen_random_stock_symbol()

    await dut_rst_init(dut, "B", stock_symbol, 0)
    error_monitor.start()
    output_monitor.start()

    pkt = (gen_header("TEST_T_ACT", 1, 10) +
           gen_event_msg("O") +
           gen_event_msg("S") +
           gen_trade_action_msg(0, other_symbol, "T") +
           gen_trade_action_msg(0, stock_symbol, "T") +
           gen_trade_action_msg(0, stock_symbol, "Q") +
           gen_trade_action_msg(0, other_symbol, "H") +
           gen_trade_action_msg(0, stock_symbol, "H") +
           gen_trade_action_msg(0, stock_symbol, "Q") +
           gen_trade_action_msg(0, stock_symbol, "P") +
           gen_trade_action_msg(0, stock_symbol, "H"))

    exp = [ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ]

    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_op_halt(dut, error_monitor: E, output_monitor: O):
    stock_symbol = gen_random_stock_symbol()
    other_symbol = gen_random_stock_symbol()

    market_code = "B"
    other_code = "Q"

    await dut_rst_init(dut, market_code, stock_symbol, 0)
    error_monitor.start()
    output_monitor.start()

    pkt = (gen_header("TEST_OP_HT", 1, 8) +
           gen_event_msg("O") +
           gen_event_msg("S") +
           gen_trade_action_msg(0, stock_symbol, "T") +
           gen_op_halt_msg(0, other_symbol, market_code, "H") +
           gen_op_halt_msg(0, other_symbol, other_code,  "H") +
           gen_op_halt_msg(0, stock_symbol, other_code,  "H") +
           gen_op_halt_msg(0, stock_symbol, market_code, "H") +
           gen_op_halt_msg(0, stock_symbol, market_code, "T"))

    exp = [ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ControlResult(stock_active=False, stock_locate=None),
           ControlResult(stock_active=True, stock_locate=None),
           ]

    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
