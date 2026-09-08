from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ref_model.top import Top
from src.ref_model.l3_order_table import L3Memory
from src.utils.rst_init import *
from src.ref_model.structs import *
from src.ref_model.params import config

from tests.assertions import *
from tests.pkt_gen import *

def test_add_msg_no_errors():
    """
    Tests BBO insertion and result calculation logic.
    """
    print()

    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    ref = Top.get_test_process_book_msg(False, stock_locate, 10000)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 1000, 10500)
    exp = BookResult(bid_entry=BBOEntry(1000, 10500), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, False, 1000, 10700)
    exp = BookResult(bid_entry=BBOEntry(1000, 10500), off_entry=BBOEntry(1000, 10700), spread=200)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 1000, 10500)
    exp = BookResult(bid_entry=BBOEntry(2000, 10500), off_entry=BBOEntry(1000, 10700), spread=200)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 500, 10550)
    exp = BookResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 500, 10450)
    exp = BookResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 400, 10400)
    exp = BookResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 600, 10350)
    exp = BookResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 500, 10300)
    exp = BookResult(bid_entry=BBOEntry(500, 10550), off_entry=BBOEntry(1000, 10700), spread=150)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, True, 200, 10600)
    exp = BookResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(1000, 10700), spread=100)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, False, 500, 10750)
    exp = BookResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(1000, 10700), spread=100)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, False, 500, 10650)
    exp = BookResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(500, 10650), spread=50)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    oid = next(oid_gen)
    msg = AddOrderMsg(stock_locate, oid, False, 1000, 10650)
    exp = BookResult(bid_entry=BBOEntry(200, 10600), off_entry=BBOEntry(1500, 10650), spread=50)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.assert_consistent_book_state()

def test_reduce_delete_msg_no_errors_no_updt():
    """
    Tests BBO depletion and result logic, L3 lookup.
    Using sequential oid generation. Test oid hash logic with L3 error testing.
    Assume both bid/offer halves function equivalently (only difference is comparator).
    """
    print()

    stock_locate = gen_random_stock_locate()

    ref = Top.get_test_process_book_msg(False, stock_locate, 10000)

    ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 1000, 10500))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 2, True, 1000, 10600))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 3, True, 1000, 10700))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 4, True, 1000, 10800))

    msg = ReduceOrderMsg(stock_locate, 4, 500)
    exp = BookResult(bid_entry=BBOEntry(500, 10800), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = ReduceOrderMsg(stock_locate, 3, 500)
    exp = BookResult(bid_entry=BBOEntry(500, 10800), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = ReduceOrderMsg(stock_locate, 4, 500)
    exp = BookResult(bid_entry=BBOEntry(500, 10700), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.assert_consistent_book_state()

    msg = DeleteOrderMsg(stock_locate, 3)
    exp = BookResult(bid_entry=BBOEntry(1000, 10600), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = DeleteOrderMsg(stock_locate, 2)
    exp = BookResult(bid_entry=BBOEntry(1000, 10500), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = DeleteOrderMsg(stock_locate, 1)
    exp = BookResult(bid_entry=None, off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.assert_consistent_book_state()

def test_reduce_delete_no_errors():
    """
    Tests L2 functionality in addition to previous test.
    """
    print()

    stock_locate = gen_random_stock_locate()

    ref = Top.get_test_process_book_msg(False, stock_locate, 10000)

    ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 1000, 10500))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 2, True, 1000, 10600))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 3, True, 1000, 10700))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 4, True, 1000, 10800))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 5, True, 1000, 10900))

    msg = DeleteOrderMsg(stock_locate, 1)
    exp = BookResult(bid_entry=BBOEntry(1000, 10900), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    # no updt req here because no outside shares
    msg = DeleteOrderMsg(stock_locate, 5)
    exp = BookResult(bid_entry=BBOEntry(1000, 10800), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.test_process_book_msg(AddOrderMsg(stock_locate, 6, True, 1000, 10550))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 7, True, 1000, 10650))
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 8, True, 1000, 10750))
    # total aggregate orders: 1000 at each of 550, 600, 650, 700, 750, 800

    ref.assert_consistent_book_state()

    # should updt req here because 1000 outside shares in range
    msg = DeleteOrderMsg(stock_locate, 4)
    exp = BookResult(bid_entry=BBOEntry(1000, 10750), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.assert_consistent_book_state()

    msg = DeleteOrderMsg(stock_locate, 8)
    exp = BookResult(bid_entry=BBOEntry(1000, 10700), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = DeleteOrderMsg(stock_locate, 3)
    exp = BookResult(bid_entry=BBOEntry(1000, 10650), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = DeleteOrderMsg(stock_locate, 7)
    exp = BookResult(bid_entry=BBOEntry(1000, 10600), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = DeleteOrderMsg(stock_locate, 2)
    exp = BookResult(bid_entry=BBOEntry(1000, 10550), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = DeleteOrderMsg(stock_locate, 6)
    exp = BookResult(bid_entry=None, off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.assert_consistent_book_state()

def test_replace_no_errors():
    """
    Testing that only 1 Bookresult after both messages, correct replace order buy/sell side.
    """
    print()

    stock_locate = gen_random_stock_locate()

    ref = Top.get_test_process_book_msg(False, stock_locate, 10000)
    ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 1000, 10500))

    msg = [
        DeleteOrderMsg(stock_locate, 1),
        ReplaceOrderMsg(stock_locate, 2, 1000, 10600),
    ]
    exp = BookResult(bid_entry=BBOEntry(1000, 10600), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.test_process_book_msg(AddOrderMsg(stock_locate, 3, False, 1000, 10700))
    msg = [
        DeleteOrderMsg(stock_locate, 3),
        ReplaceOrderMsg(stock_locate, 4, 1000, 10800),
    ]
    exp = BookResult(bid_entry=BBOEntry(1000, 10600), off_entry=BBOEntry(1000, 10800), spread=200)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    msg = [
        DeleteOrderMsg(stock_locate, 2),
        ReplaceOrderMsg(stock_locate, 5, 1000, 10550),
    ]
    exp = BookResult(bid_entry=BBOEntry(1000, 10550), off_entry=BBOEntry(1000, 10800), spread=250)
    assert_matching_result(ref.test_process_book_msg(msg), exp)

    ref.assert_consistent_book_state()

def test_L3_errors():
    """
    L3 order ID missing / duplicates, negative shares
    """
    print()

    stock_locate = gen_random_stock_locate()

    # add duplicate
    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 200, 10500)))
    assert_error_msg(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 400, 10600)), "Attempted to add with existing order ID.")

    # replace duplicate
    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 200, 10500)))
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, 2, True, 200, 10500)))
    msg = [
        DeleteOrderMsg(stock_locate, 2),
        ReplaceOrderMsg(stock_locate, 1, 1000, 10500),
    ]
    assert_error_msg(ref.test_process_book_msg(msg), "Attempted to replace-add with existing order ID.")

    # reduce missing
    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_error_msg(ref.test_process_book_msg(ReduceOrderMsg(stock_locate, 1, 400)), "Attempted to reduce shares of missing order ID.")

    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 400, 10500)))
    assert_no_error(ref.test_process_book_msg(ReduceOrderMsg(stock_locate, 1, 400)))
    assert_error_msg(ref.test_process_book_msg(ReduceOrderMsg(stock_locate, 1, 400)), "Attempted to reduce shares of missing order ID.")

    # reduce more than original shares
    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 400, 10500)))
    assert_error_msg(ref.test_process_book_msg(ReduceOrderMsg(stock_locate, 1, 500)), "Unexpected negative shares after reducing.")

    # delete missing
    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_error_msg(ref.test_process_book_msg(DeleteOrderMsg(stock_locate, 1)), "Attempted to delete missing order ID.")

    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 400, 10500)))
    assert_no_error(ref.test_process_book_msg(DeleteOrderMsg(stock_locate, 1)))
    assert_error_msg(ref.test_process_book_msg(DeleteOrderMsg(stock_locate, 1)), "Attempted to delete missing order ID.")

def test_L3_memory():
    """
    Non-ideal memory testing.
    Full hash table line, lookup from CAM, full CAM error
    """
    print()

    stock_locate = gen_random_stock_locate()
    ref = Top.get_test_process_book_msg(False, stock_locate, 10000)

    # oid hash function is lower (config.L3_LOG_ADDR_SIZE) bits XOR next (config.L3_LOG_ADDR_SIZE) bits.
    # use L3Memory.oid_hash(oid) to assert hash conflict.
    shares_count = 0
    i = 1
    for _ in range(1 << config.L3_LOG_LINE_SIZE):
        oid = (i << config.L3_LOG_ADDR_SIZE) + 1
        assert L3Memory.oid_hash(oid) == 1, "Test case requires conflicting oid hash."
        assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, oid, True, 100, 10500)))
        shares_count += 100
        i += 1

    for _ in range(config.L3_CAM_SIZE):
        oid = (i << config.L3_LOG_ADDR_SIZE) + 1
        assert L3Memory.oid_hash(oid) == 1, "Test case requires conflicting oid hash."
        assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, oid, True, 100, 10500)))
        # test accessing orders in CAM
        shares_count += 50
        exp = BookResult(bid_entry=BBOEntry(shares_count, 10500), off_entry=None, spread=None)
        assert_matching_result(ref.test_process_book_msg(ReduceOrderMsg(stock_locate, oid, 50)), exp)
        i += 1

    # test adding / accessing other oid hash
    oid = (1 << config.L3_LOG_ADDR_SIZE) + 2
    assert L3Memory.oid_hash(oid) != 1, "Test case requires other oid hash."
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, oid, True, 100, 10500)))
    shares_count += 50
    exp = BookResult(bid_entry=BBOEntry(shares_count, 10500), off_entry=None, spread=None)
    assert_matching_result(ref.test_process_book_msg(ReduceOrderMsg(stock_locate, oid, 50)), exp)

    ref.assert_consistent_book_state()

    # overflow hash 0
    oid = (i << config.L3_LOG_ADDR_SIZE) + 1
    assert L3Memory.oid_hash(oid) == 1, "Test case requires conflicting oid hash."
    assert_error_msg(ref.test_process_book_msg(AddOrderMsg(stock_locate, oid, True, 100, 10500)), "L3 Hash Table out of memory slots")

def test_L2_errors():
    """
    Price not in tick
    """
    print()

    stock_locate = gen_random_stock_locate()
    ref = Top.get_test_process_book_msg(True, stock_locate, 10000)
    assert_error_msg(ref.test_process_book_msg(AddOrderMsg(stock_locate, 1, True, 100, 10625)), "Invalid price not on tick increment.")

def test_L2_memory():
    """
    Testing non-ideal memory
    Get updt for price out of range on both sides

    Note: outside shares in range calculation added to bbo, so bbo should throw the error.
    """
    print()

    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()
    price_base = 10000
    upper_price_bound = price_base + (config.L2_MEM_SIZE - 1) * 50 # inclusive

    ref = Top.get_test_process_book_msg(False, stock_locate, price_base)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), True, 400, 9900)))
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), True, 400, 10000)))
    # assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), True, 400, 10100)))
    # assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), True, 400, 10200)))
    oid_to_del = next(oid_gen)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, oid_to_del, True, 400, 10300)))
    assert_error_msg(ref.test_process_book_msg(DeleteOrderMsg(stock_locate, oid_to_del)), "No shares in range for updt.")

    ref = Top.get_test_process_book_msg(False, stock_locate, price_base)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), False, 400, upper_price_bound + 100)))
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), False, 400, upper_price_bound)))
    # assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), False, 400, upper_price_bound - 100)))
    # assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, next(oid_gen), False, 400, upper_price_bound - 200)))
    oid_to_del = next(oid_gen)
    assert_no_error(ref.test_process_book_msg(AddOrderMsg(stock_locate, oid_to_del, False, 400, upper_price_bound - 300)))
    assert_error_msg(ref.test_process_book_msg(DeleteOrderMsg(stock_locate, oid_to_del)), "No shares in range for updt.")





if __name__ == "__main__":
    test_L2_memory()
