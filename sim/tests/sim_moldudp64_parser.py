import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb.clock import Clock
from pathlib import Path
import sys
import logging

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.rst_init import *
from src.utils.axis_driver import *
from tests.assertions import *
from tests.pkt_gen import *
from sim.utils.monitors import ErrorMonitor
from sim.utils.wrap_tests import *

log = logging.getLogger("testbench")
log.setLevel("INFO")

# dut = moldudp64 parser module only

E = ErrorMonitor

@cocotb.test
@extend_test(None)
async def test_early_tlast_header(dut, error_monitor: E):
    SESSION_ID = "TEST_TLAST"
    header = gen_header(SESSION_ID, 1, 1)
    truncate_idxs = [5, 10, 13, 18, 19]

    for idx in truncate_idxs:
        pkt = header[0:idx]

        await dut_rst(dut)
        error_monitor.start()
        log.debug(f"Sending pkt truncated at index: {idx}.")
        await error_monitor.wait_for_expect_error(dut.moldudp64_parser.error_pkt_len, dut_send_pkt(dut, pkt))
        error_monitor.stop()
        log.debug(f"Passed idx {idx}.")

@cocotb.test
@extend_test(None)
async def test_session_id_mismatch(dut, error_monitor: E):
        pkt_1 = gen_header("TEST_SID_1", 1, 0)
        pkt_2 = gen_header("TEST_SID_2", 1, 0)

        await dut_rst(dut)
        error_monitor.start()
        log.debug("Sending pkt_1.")
        await dut_send_pkt(dut, pkt_1)
        log.debug("Sending pkt_2.")
        await error_monitor.wait_for_expect_error(dut.moldudp64_parser.error_session_id, dut_send_pkt(dut, pkt_2))

@cocotb.test
@extend_test(None)
async def test_seq_num_mismatch(dut, error_monitor: E):
    ignore_msg = gen_ignore_msg()
    pkt_0_0 = gen_header("TEST_SEQ_0", 0, 0)
    pkt_1_0 = gen_header("TEST_SEQ_0", 1, 0)
    pkt_1_1 = gen_header("TEST_SEQ_0", 1, 1) + ignore_msg
    pkt_2_0 = gen_header("TEST_SEQ_0", 2, 0)
    pkt_2_3 = gen_header("TEST_SEQ_0", 2, 3) + ignore_msg + ignore_msg + ignore_msg
    pkt_5_0 = gen_header("TEST_SEQ_0", 5, 0)

    await dut_rst(dut)
    error_monitor.start()
    log.debug("Sending pkt_0_0.")
    await error_monitor.wait_for_expect_error(dut.moldudp64_parser.error_seq, dut_send_pkt(dut, pkt_0_0))
    error_monitor.stop()
    log.debug("Passed: expect 1 received 0.")

    await dut_rst(dut)
    error_monitor.start()
    log.debug("Sending pkt_1_0.")
    await dut_send_pkt(dut, pkt_1_0)
    log.debug("Sending pkt_1_0.")
    await dut_send_pkt(dut, pkt_1_0)
    log.debug("Sending pkt_1_0.")
    await dut_send_pkt(dut, pkt_1_0)
    log.debug("Sending pkt_1_1.")
    await dut_send_pkt(dut, pkt_1_1)
    log.debug("Sending pkt_2_0.")
    await dut_send_pkt(dut, pkt_2_0)
    log.debug("Sending pkt_5_0.")
    await error_monitor.wait_for_expect_error(dut.moldudp64_parser.error_seq, dut_send_pkt(dut, pkt_5_0))
    error_monitor.stop()
    log.debug("Passed: expect 2 received 5.")

    await dut_rst(dut)
    error_monitor.start()
    log.debug("Sending pkt_1_1.")
    await dut_send_pkt(dut, pkt_1_1)
    log.debug("Sending pkt_2_3.")
    await dut_send_pkt(dut, pkt_2_3)
    log.debug("Sending pkt_5_0.")
    await dut_send_pkt(dut, pkt_5_0)
    await error_monitor.wait_no_error()
    log.debug("Passed: expect 5 received 5.")

@cocotb.test
@extend_test(None)
async def test_early_tlast_payload(dut, error_monitor: E):
    whole_pkt = gen_header("TEST_TLAST", 1, 1) + gen_ignore_msg()
    truncate_idxs = [20, 21, 22, 23, 24, 33]

    for idx in truncate_idxs:
        pkt = whole_pkt[0:idx]

        await dut_rst(dut)
        error_monitor.start()

        log.debug(f"Sending pkt truncated at index: {idx}.")
        await error_monitor.wait_for_expect_error(dut.moldudp64_parser.error_pkt_len, dut_send_pkt(dut, pkt))
        error_monitor.stop()
        log.debug(f"Passed idx {idx}.")

@cocotb.test
@extend_test(None)
async def test_extra_bytes(dut, error_monitor: E):
    pkt = gen_header("TEST_EXTRA", 1, 1) + gen_event_msg("O") + gen_event_msg("S")

    await dut_rst(dut)
    error_monitor.start()
    log.debug(f"Sending pkt.")
    await error_monitor.wait_for_expect_error(dut.moldudp64_parser.error_pkt_len, dut_send_pkt(dut, pkt))
