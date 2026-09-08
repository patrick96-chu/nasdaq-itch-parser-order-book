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
from src.ref_model.params import config
from src.ref_model.l3_order_table import L3Memory
from tests.pkt_gen import *
from sim.utils.monitors import *
from sim.utils.wrap_tests import extend_test
from src.utils.axis_driver import ref_axis_send_packet
from sim.data.stream_pkt import generate_moldudp_packets
from tests.assertions import *

log = logging.getLogger("testbench")
log.setLevel("INFO")
logging.getLogger("monitor.error").setLevel("WARNING")
logging.getLogger("monitor.output").setLevel("WARNING")
logging.getLogger("driver").setLevel("WARNING")

# dut = top (all modules)

@dataclass
class BBORes:
    bid_valid: int
    bid_price: int
    bid_shares: int
    off_valid: int
    off_price: int
    off_shares: int
    spread: int

class TopMonitor(OutputMonitor):
    """
    Only monitors data outputs.
    For each message, collect complete output and construct corresponding python dataclass.
    Compare against expected list.
    """

    def __init__(self, dut, error_event: Event):
        # using top output since it include stock_active logic
        super().__init__(dut, error_event)

    def _process_cycle(self):
        bbo_res = self._decode_bbo(self.module.bbo_res_o)
        bid_valid = bbo_res.bid_valid == 1
        off_valid = bbo_res.off_valid == 1
        if self.module.bbo_res_v_o.value == 1:
            self._log.info("Received output.")

            result = TopResult(
                bid_entry=(BBOEntry(bbo_res.bid_shares, bbo_res.bid_price) if bid_valid else None),
                off_entry=(BBOEntry(bbo_res.off_shares, bbo_res.off_price) if off_valid else None),
                spread=bbo_res.spread if bid_valid and off_valid else None,
                # spread=(bbo_res.off_price - bbo_res.bid_price if bid_valid and off_valid else None),
            )

            try:
                expect = self.expected_outputs.get_nowait()
                if result != expect:
                    self._log.warning("Received output does not match expected output.")
                    self._log.warning(f"Received: {result}")
                    self._log.warning(f"Expected: {expect}")
                    self._fail_event.set()
            except Empty:
                self._log.warning("Did not expect valid output.")
                self._fail_event.set()

    def _decode_bbo(self, bbo_res_h: LogicArrayObject):
        return BBORes(
            int(bbo_res_h.value[225]),
            int(bbo_res_h.value[224:193]),
            int(bbo_res_h.value[192:129]),
            int(bbo_res_h.value[128]),
            int(bbo_res_h.value[127:96]),
            int(bbo_res_h.value[95:32]),
            int(bbo_res_h.value[31:0]),
        )

E = ErrorMonitor
O = TopMonitor

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_add_no_errors(dut, error_monitor: E, output_monitor: O):
    """Tests BBO insertion and result calculation logic."""
    SESSION_ID = "ADD_NERROR"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()
    output_monitor.start()

    # sim model should have bbo_res_v_o == 1 each time one ITCH message passes
    pkt = gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate)
    # exp = [
    #     TopResult(bid_entry=None, off_entry=None, spread=None),
    #     TopResult(bid_entry=None, off_entry=None, spread=None),
    #     TopResult(bid_entry=None, off_entry=None, spread=None),
    #     TopResult(bid_entry=None, off_entry=None, spread=None),
    # ]
    # await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    await dut_send_pkt(dut, pkt)

    pkt = (gen_header(SESSION_ID, 5, 12)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 1000, 10500)
           + gen_add_msg(stock_locate, next(oid_gen), "S", 1000, 10700)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 1000, 10500)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 500, 10550)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 500, 10450)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 400, 10400)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 600, 10350)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 500, 10300)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 200, 10600)
           + gen_add_msg(stock_locate, next(oid_gen), "S", 500, 10750)
           + gen_add_msg(stock_locate, next(oid_gen), "S", 500, 10650)
           + gen_add_msg(stock_locate, next(oid_gen), "S", 1000, 10650)
    )

    exp = [
        TopResult(bid_entry=BBOEntry(1000, 10500), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(1000, 10500), off_entry=BBOEntry(1000, 10700), spread=200),
        TopResult(bid_entry=BBOEntry(2000, 10500), off_entry=BBOEntry(1000, 10700), spread=200),
        TopResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150),
        TopResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150),
        TopResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150),
        TopResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150),
        TopResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150),
        TopResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(1000, 10700), spread=100),
        TopResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(1000, 10700), spread=100),
        TopResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(500, 10650), spread=50),
        TopResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(1500, 10650), spread=50),
    ]

    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_reduce_delete_no_errors_no_updt(dut, error_monitor: E, output_monitor: O):
    """
    Tests BBO depletion and result logic, L3 lookup.
    Assume both bid/offer halves function equivalently (only difference is comparator).
    """

    SESSION_ID = "RED_NERROR"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    await dut_flush(dut)
    output_monitor.start()

    pkt = (gen_header(SESSION_ID, 5, 2)
           + gen_add_msg(stock_locate, 1, "B", 1000, 10500)
           + gen_add_msg(stock_locate, 2, "B", 1000, 10600)
        #    + gen_add_msg(stock_locate, 3, "B", 1000, 10700)
        #    + gen_add_msg(stock_locate, 4, "B", 1000, 10800)
    )
    exp = [
        TopResult(bid_entry=BBOEntry(1000, 10500), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(1000, 10600), off_entry=None, spread=None),
        # TopResult(bid_entry=BBOEntry(1000, 10700), off_entry=None, spread=None),
        # TopResult(bid_entry=BBOEntry(1000, 10800), off_entry=None, spread=None),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

    pkt = (gen_header(SESSION_ID, 7, 4)
           + gen_execute_msg(stock_locate, 2, 500)
           + gen_cancel_msg(stock_locate, 1, 500)
           + gen_execute_msg(stock_locate, 2, 500)
           + gen_delete_msg(stock_locate, 1)
        #    + gen_delete_msg(stock_locate, 2)
        #    + gen_delete_msg(stock_locate, 1)
    )
    exp = [
        TopResult(bid_entry=BBOEntry(500, 10600), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(500, 10600), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(500, 10500), off_entry=None, spread=None),
        # TopResult(bid_entry=BBOEntry(1000, 10600), off_entry=None, spread=None),
        # TopResult(bid_entry=BBOEntry(1000, 10500), off_entry=None, spread=None),
        TopResult(bid_entry=None, off_entry=None, spread=None),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_reduce_delete_no_errors(dut, error_monitor: E, output_monitor: O):
    """Tests L2 functionality in addition to previous test."""

    SESSION_ID = "UPDT_N_ERR"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    await dut_flush(dut)
    output_monitor.start()

    pkt = (gen_header(SESSION_ID, 5, 3)
           + gen_add_msg(stock_locate, 1, "B", 500, 10500)
           + gen_add_msg(stock_locate, 2, "B", 600, 10600)
           + gen_add_msg(stock_locate, 3, "B", 700, 10700)
        #    + gen_add_msg(stock_locate, 4, "B", 1000, 10800)
        #    + gen_add_msg(stock_locate, 5, "B", 1000, 10900)
    )
    exp = [
        TopResult(bid_entry=BBOEntry(500, 10500), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(700, 10700), off_entry=None, spread=None),
        # TopResult(bid_entry=BBOEntry(1000, 10800), off_entry=None, spread=None),
        # TopResult(bid_entry=BBOEntry(1000, 10900), off_entry=None, spread=None),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

    pkt = (gen_header(SESSION_ID, 8, 2)
           + gen_delete_msg(stock_locate, 1)
           + gen_delete_msg(stock_locate, 3) # should not updt because no outside shares
    )
    exp = [
        TopResult(bid_entry=BBOEntry(700, 10700), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=None, spread=None),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

    pkt = (gen_header(SESSION_ID, 10, 5)
           + gen_add_msg(stock_locate, 4, "B", 550, 10550)
           + gen_add_msg(stock_locate, 5, "B", 650, 10650)
           + gen_add_msg(stock_locate, 6, "B", 500, 10500)
           + gen_add_msg(stock_locate, 7, "B", 700, 10700)
           + gen_add_msg(stock_locate, 8, "B", 750, 10750)
    )
    exp = [
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(650, 10650), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(650, 10650), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(700, 10700), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(750, 10750), off_entry=None, spread=None),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    # total aggregate orders: 1000 at each of 500, 550, 600, 650, 700, 750

    pkt = (gen_header(SESSION_ID, 15, 6)
           + gen_delete_msg(stock_locate, 8)
           + gen_delete_msg(stock_locate, 7)
           + gen_delete_msg(stock_locate, 5)
           + gen_delete_msg(stock_locate, 2)
           + gen_delete_msg(stock_locate, 4)
           + gen_delete_msg(stock_locate, 6)
    )
    exp = [
        TopResult(bid_entry=BBOEntry(700, 10700), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(650, 10650), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(550, 10550), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(500, 10500), off_entry=None, spread=None),
        TopResult(bid_entry=None, off_entry=None, spread=None),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_replace_no_errors(dut, error_monitor: E, output_monitor: O):
    """
    Testing that only 1 Bookresult after both messages, correct replace order buy/sell side.
    """
    SESSION_ID = "REPLC_NERR"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    await dut_flush(dut)
    output_monitor.start()

    pkt = (gen_header(SESSION_ID, 5, 5)
           + gen_add_msg(stock_locate, 1, "B", 500, 10500)
           + gen_replace_msg(stock_locate, 1, 2, 600, 10600)
           + gen_add_msg(stock_locate, 3, "S", 700, 10700)
           + gen_replace_msg(stock_locate, 3, 4, 800, 10800)
           + gen_replace_msg(stock_locate, 2, 5, 550, 10550)
    )
    exp = [
        TopResult(bid_entry=BBOEntry(500, 10500), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=None, spread=None),
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=BBOEntry(700, 10700), spread=100),
        TopResult(bid_entry=BBOEntry(600, 10600), off_entry=BBOEntry(800, 10800), spread=200),
        TopResult(bid_entry=BBOEntry(550, 10550), off_entry=BBOEntry(800, 10800), spread=250),
    ]
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_L3_errors(dut, error_monitor: E, output_monitor: O):
    """
    L3 order ID missing / duplicates, negative shares
    """
    SESSION_ID = "L3_ERR_IDS"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    # duplicate add IDs
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    oid = next(oid_gen)
    pkt = (gen_header(SESSION_ID, 5, 2)
           + gen_add_msg(stock_locate, oid, "B", 500, 10500)
           + gen_add_msg(stock_locate, oid, "B", 700, 10700)
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_add_id, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    # replace_add with duplicate ID
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    oid_1 = next(oid_gen)
    oid_2 = next(oid_gen)
    pkt = (gen_header(SESSION_ID, 5, 3)
           + gen_add_msg(stock_locate, oid_1, "B", 500, 10500)
           + gen_add_msg(stock_locate, oid_2, "B", 700, 10700)
           + gen_replace_msg(stock_locate, oid_2, oid_1, 800, 10800)
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_add_id, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    # missing reduce order IDs
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    pkt = (gen_header(SESSION_ID, 5, 1)
           + gen_cancel_msg(stock_locate, next(oid_gen), 200)
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_reduce_id, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    oid = next(oid_gen)
    pkt = (gen_header(SESSION_ID, 5, 3)
           + gen_add_msg(stock_locate, oid, "B", 500, 10500)
           + gen_delete_msg(stock_locate, oid)
           + gen_cancel_msg(stock_locate, oid, 500)
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_reduce_id, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    # reduce more than possible shares
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    # log.info("Sending reduce more than possible shares")
    oid = next(oid_gen)
    pkt = (gen_header(SESSION_ID, 5, 2)
           + gen_add_msg(stock_locate, oid, "B", 500, 10500)
           + gen_cancel_msg(stock_locate, oid, 800)
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_neg_shares, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    # delete missing
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)

    pkt = (gen_header(SESSION_ID, 5, 1)
           + gen_delete_msg(stock_locate, next(oid_gen))
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_reduce_id, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_L3_memory(dut, error_monitor: E, output_monitor: O):
    """
    Non-ideal memory testing.
    Full hash table line, lookup from CAM, full CAM error
    """

    SESSION_ID = "L3_MEMORYS"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    await dut_flush(dut)
    output_monitor.start()

    shares_count = 0
    i = 1

    # filling up RAM line
    pkt = gen_header(SESSION_ID, 5, (1 << config.L3_LOG_LINE_SIZE))
    exp = []
    for _ in range(1 << config.L3_LOG_LINE_SIZE):
        oid = (i << config.L3_LOG_ADDR_SIZE) + 1
        assert L3Memory.oid_hash(oid) == 1, "Test case requires conflicting oid hash."
        shares_count += 100
        pkt += gen_add_msg(stock_locate, oid, "B", 100, 10500)
        exp.append(TopResult(bid_entry=BBOEntry(shares_count, 10500), off_entry=None, spread=None))
        i += 1
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt, 0))

    # filling up CAM
    pkt = gen_header(SESSION_ID, 5 + (1 << config.L3_LOG_LINE_SIZE), 2 * config.L3_CAM_SIZE)
    exp = []
    for _ in range(config.L3_CAM_SIZE):
        oid = (i << config.L3_LOG_ADDR_SIZE) + 1
        assert L3Memory.oid_hash(oid) == 1, "Test case requires conflicting oid hash."
        pkt += gen_add_msg(stock_locate, oid, "B", 100, 10500)
        exp.append(TopResult(bid_entry=BBOEntry(shares_count + 100, 10500), off_entry=None, spread=None))

        # test accessing orders in CAM
        shares_count += 50
        pkt += gen_execute_msg(stock_locate, oid, 50)
        exp.append(TopResult(bid_entry=BBOEntry(shares_count, 10500), off_entry=None, spread=None))
        i += 1
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt, 0))

    # test adding / accessing other oid hash
    pkt = gen_header(SESSION_ID, 5 + (1 << config.L3_LOG_LINE_SIZE) + 2 * config.L3_CAM_SIZE, 2)
    exp = []
    oid = (1 << config.L3_LOG_ADDR_SIZE) + 2
    assert L3Memory.oid_hash(oid) != 1, "Test case requires other oid hash."
    pkt += gen_add_msg(stock_locate, oid, "B", 100, 10500)
    exp.append(TopResult(bid_entry=BBOEntry(shares_count + 100, 10500), off_entry=None, spread=None))

    shares_count += 50
    pkt += gen_execute_msg(stock_locate, oid, 50)
    exp.append(TopResult(bid_entry=BBOEntry(shares_count, 10500), off_entry=None, spread=None))
    await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt))
    output_monitor.stop()

    # overflow hash 1
    pkt = gen_header(SESSION_ID, 5 + (1 << config.L3_LOG_LINE_SIZE) + 2 * config.L3_CAM_SIZE + 2, 1)
    oid = (i << config.L3_LOG_ADDR_SIZE) + 1
    assert L3Memory.oid_hash(oid) == 1, "Test case requires conflicting oid hash."
    pkt += gen_add_msg(stock_locate, oid, "B", 100, 10500)
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.l3_cam_error, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_L2_errors(dut, error_monitor: E, output_monitor: O):
    """
    Price not in tick
    """
    SESSION_ID = "L2_ERRTICK"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()

    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)

    pkt = gen_header(SESSION_ID, 5, 1) + gen_add_msg(stock_locate, 1, "B", 100, 10625)
    await error_monitor.wait_for_expect_error(dut.book.l2_price_table.error_tick, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_L2_memory(dut, error_monitor: E, output_monitor: O):
    """
    Testing non-ideal memory
    Get updt for price out of range on both sides

    Note: outside shares in range calculation added to bbo, so bbo should throw the error.
    """
    SESSION_ID = "L2_MEMORYS"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()
    price_base = 10000
    price_max = price_base + (config.L2_MEM_SIZE - 1) * 50 # inclusive

    await dut_rst_init(dut, "B", stock_symbol, price_base)
    error_monitor.start()

    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)

    oid_to_del = next(oid_gen)
    pkt = (gen_header(SESSION_ID, 5, 4)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 400, 9900)
           + gen_add_msg(stock_locate, next(oid_gen), "B", 400, 10000)
           + gen_add_msg(stock_locate, oid_to_del, "B", 400, 10100)
           + gen_delete_msg(stock_locate, oid_to_del)
    )
    await error_monitor.wait_for_expect_error(dut.book.bbo.bid_half.error_updt, dut_send_pkt(dut, pkt))
    error_monitor.stop()
    await dut_rst_init(dut, "B", stock_symbol, price_base)
    error_monitor.start()

    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)
    log.info("Sending offer pkt.")
    oid_to_del = next(oid_gen)
    pkt = (gen_header(SESSION_ID, 5, 4)
           + gen_add_msg(stock_locate, next(oid_gen), "S", 400, price_max + 100)
           + gen_add_msg(stock_locate, next(oid_gen), "S", 400, price_max)
           + gen_add_msg(stock_locate, oid_to_del, "S", 400, price_max - 100)
           + gen_delete_msg(stock_locate, oid_to_del)
    )
    await error_monitor.wait_for_expect_error(dut.book.bbo.off_half.error_updt, dut_send_pkt(dut, pkt))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_memory_hazards(dut, error_monitor: E, output_monitor: O):
    """
    On no tvalid drop, replace message requires reading and writing from L3 memory at same time.
    Test bypass path in L3 hash table with same oid hash between old and new IDs.
    """
    SESSION_ID = "MEM_HAZARD"
    stock_symbol = gen_random_stock_symbol()
    stock_locate = gen_random_stock_locate()

    await dut_rst_init(dut, "B", stock_symbol, 10000)
    error_monitor.start()
    await dut_send_pkt(dut, gen_book_test_init_pkt(SESSION_ID, stock_symbol, stock_locate), tvalid_drop_prob=0)

    oid_1 = (1 << config.L2_LOG_MEM_SIZE) + 1
    oid_2 = (2 << config.L2_LOG_MEM_SIZE) + 1

    # if the bypass failed, we would expect the deleted shares to still be present in the L3 line.
    # test this by attempting to delete it again; correct behavior should be to throw a missing ID error.
    pkt = (gen_header(SESSION_ID, 5, 3)
           + gen_add_msg(stock_locate, oid_1, "B", 1000, 10700)
           + gen_replace_msg(stock_locate, oid_1, oid_2, 1200, 10800)
           + gen_delete_msg(stock_locate, oid_1)
    )
    await error_monitor.wait_for_expect_error(dut.book.l3_order_table.error_reduce_id, dut_send_pkt(dut, pkt, 0))

@cocotb.test
@extend_test(output_monitor_class=O)
async def test_full_pipeline(dut, error_monitor: E, output_monitor: O):
    """
    Running rtl model against python reference model on real data.
    """
    log.setLevel("DEBUG")

    FAST = True
    INPUT_FILE = "/mnt/c/Users/patri/Documents/NASDAQ_ITCH_Parser/sim/data/20191230_BX_AMD_344" if FAST else "/mnt/c/Users/patri/Documents/NASDAQ_ITCH_Parser/sim/data/20191230.BX_ITCH_50"
    ITCH_MESSAGE_COUNT = 108965 if FAST else 29156747
    APPROX_PACKET_COUNT = ITCH_MESSAGE_COUNT / 10
    STOCK_SYMBOL = "AMD     "
    PRICE_BASE = 40_0000
    pkt_generator = generate_moldudp_packets(INPUT_FILE, b"20191230BX") #, seed=0

    # ref_ideal = ref_rst_init("B", STOCK_SYMBOL, 40_0000, True)
    ref_not_i = ref_rst_init("B", STOCK_SYMBOL, PRICE_BASE, False)

    await dut_rst_init(dut, "B", STOCK_SYMBOL, PRICE_BASE)
    error_monitor.start()
    output_monitor.start()

    # note: assume reference model output is correct by pytest testing
    progress = 1
    count = 0
    for pkt in pkt_generator:
        # log.debug(f"pkt: {pkt.hex()}")
        if count > APPROX_PACKET_COUNT / 100:
            log.info(f"Testing packets: {progress}% done.")
            # ref_ideal.book.bbo.print_bbo_state()
            progress += 1
            count = 0
        # res_ideal = ref_axis_send_packet(ref_ideal, pkt)
        res_not_i = list(ref_axis_send_packet(ref_not_i, pkt))
        # assert_no_error(res_ideal)
        assert_no_error(res_not_i)
        # exp = [res for res in res_not_i if (res.bid_entry is not None or res.off_entry is not None)]
        exp = res_not_i
        # log.debug("Expected outputs for this pkt:")
        # log.debug(exp)
        await output_monitor.wait_for_expected_outputs(exp, dut_send_pkt(dut, pkt, 0.1))
        # assert list(res_ideal) == list(res_not_i)
        # ref_ideal.assert_consistent_book_state()
        # ref_not_i.assert_consistent_book_state()
        count += 1
