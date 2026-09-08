from src.ref_model.top import Top
from src.utils.rst_init import *
from src.utils.axis_driver import ref_axis_send_packet
from src.ref_model.structs import *

from tests.assertions import *
from tests.pkt_gen import *

# ==========================================
# AXIS + MOLDUDP64 LAYER TESTING
# ==========================================
# Use full process_pkt pipeline since error should be forwarded up

def test_early_tlast_header():
    print()
    SESSION_ID = "TEST_TLAST"

    INCOMPLETE_PKTS = [
        bytes("TEST_", encoding="utf-8"), # truncated in session ID
        bytes(SESSION_ID, encoding="utf-8"), # truncated after session ID
        bytes(SESSION_ID, encoding="utf-8") + int.to_bytes(0, 3, "big"), # truncated in sequence number
        bytes(SESSION_ID, encoding="utf-8") + int.to_bytes(1, 8, "big"), # truncated after sequence number
        bytes(SESSION_ID, encoding="utf-8") + int.to_bytes(1, 8, "big") + int.to_bytes(0, 1, "big"), # truncated in msg count
    ]

    for pkt in INCOMPLETE_PKTS:
        ref = ref_rst(False) # dont care about ideal and init params
        assert_error_msg(ref_axis_send_packet(ref, pkt), "Packet too short.")

        # also testing tvalid dropping
        ref = ref_rst(False)
        assert_error_msg(ref_axis_send_packet(ref, pkt, 0.5), "Packet too short.")

def test_session_id_mismatch():
    print()
    pkt_1 = gen_header("TEST_SID_1", 1, 0)
    pkt_2 = gen_header("TEST_SID_2", 1, 0)

    ref = ref_rst(False)
    assert_empty_result(ref_axis_send_packet(ref, pkt_1))
    assert_error_msg(ref_axis_send_packet(ref, pkt_2), "Session ID mismatch.")

    # testing other end of string
    pkt_1 = gen_header("TEST_SID_1", 1, 0)
    pkt_2 = gen_header("tEST_SID_1", 1, 0)

    ref = ref_rst(False)
    assert_empty_result(ref_axis_send_packet(ref, pkt_1))
    assert_error_msg(ref_axis_send_packet(ref, pkt_2), "Session ID mismatch.")

def test_seq_num_mismatch():
    print()
    # need this as first msg + initialize to pass ctrl error
    msg_hours_begin = gen_event_msg('O')
    # msg that should pass ITCH parser as msg_type = IGNORE
    ignore_msg = gen_ignore_msg()

    pkt_0_0 = gen_header("TEST_SEQ_0", 0, 0)
    pkt_1_0 = gen_header("TEST_SEQ_0", 1, 0)
    pkt_1_1 = gen_header("TEST_SEQ_0", 1, 1) + msg_hours_begin
    pkt_2_0 = gen_header("TEST_SEQ_0", 2, 0)
    pkt_2_3 = gen_header("TEST_SEQ_0", 2, 3) + ignore_msg + ignore_msg + ignore_msg
    pkt_5_0 = gen_header("TEST_SEQ_0", 5, 0)

    ref = ref_rst(False)
    assert_error_msg(ref_axis_send_packet(ref, pkt_0_0), "Seq number mismatch.")

    ref = ref_rst_init("B", "DONTCARE", 0, False)
    assert_empty_result(ref_axis_send_packet(ref, pkt_1_0))
    assert_empty_result(ref_axis_send_packet(ref, pkt_1_0))
    assert_empty_result(ref_axis_send_packet(ref, pkt_1_0))
    assert_no_error(ref_axis_send_packet(ref, pkt_1_1))
    assert_empty_result(ref_axis_send_packet(ref, pkt_2_0))
    assert_error_msg(ref_axis_send_packet(ref, pkt_5_0), "Seq number mismatch.")

    ref = ref_rst_init("B", "DONTCARE", 0, False)
    assert_no_error(ref_axis_send_packet(ref, pkt_1_1))
    assert_no_error(ref_axis_send_packet(ref, pkt_2_3))
    assert_empty_result(ref_axis_send_packet(ref, pkt_5_0))

def test_early_tlast_payload():
    print()

    INCOMPLETE_PKTS = [
        gen_header("TEST_TLAST", 1, 1), # truncated after header
        gen_header("TEST_TLAST", 1, 1) + int.to_bytes(0, 1, "big"), # truncated in msg_len
        gen_header("TEST_TLAST", 1, 1) + int.to_bytes(12, 2, "big"), # truncated after msg_len
        gen_header("TEST_TLAST", 1, 1) + int.to_bytes(12, 2, "big") + int.to_bytes(0, 4, "big"), # truncated in msg
    ]

    for pkt in INCOMPLETE_PKTS:
        ref = ref_rst(False)
        assert_error_msg(ref_axis_send_packet(ref, pkt), "Packet terminated in middle of payload.")

def test_extra_bytes():
    print()

    pkt = gen_header("TEST_EXTRA", 1, 1) + gen_event_msg("O") + gen_event_msg("S")

    ref = ref_rst_init("B", "DONTCARE", 0, False)
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Packet has remaining bytes.")


# ==========================================
# ITCH LAYER TESTING
# ==========================================
# To avoid failing downstream errors, get Top instance via get_test_parser method.
# This configures send_packet to yield ITCHParserResult

# Since it is repetitive to test mismatching byte lengths for each type of message,
# we only test it for one message and assume the logic works for all other messages.
# If we encounter this error while parsing real data, then we investigate it manually.

def test_invalid_msg_type():
    print()

    ref = Top.get_test_parser()
    pkt = gen_header("TEST_TYPE_", 1, 1)
    pkt += gen_wrong_msg()
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Unexpected msg_type field.")

def test_sys_event():
    print()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_EVENT", 1, 6)
    exp = []
    for code in "OSQMEC":
        pkt += gen_event_msg(code)
        exp.append(ITCHParserResult(parsed_msg=SystemEventMsg(0, SystemEventCode(ord(code)))))
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

    # incorrect length (mismatch caught by ITCH Parser)
    pkt = gen_header("TEST_EVENT", 7, 1)
    pkt += (int.to_bytes(13, 2, "big")
            + b'S'
            + b'\00' * 10
            + bytes("O", encoding="utf-8")
            + b'\00' * 1
    )
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Unexpected msg byte length.")

    # unexpected event code
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_EVENT", 1, 1) + gen_event_msg("z")
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Invalid event code.")

def test_directory_msg():
    print()

    stock_locate = gen_random_stock_locate()
    stock_symbol = gen_random_stock_symbol()

    # correct msg
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_DRCTY", 1, 1) + gen_directory_msg(stock_locate, stock_symbol)
    exp = [ITCHParserResult(parsed_msg=DirectoryMsg(stock_locate, stock_symbol))]
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

def test_trade_action():
    print()

    stock_locate = gen_random_stock_locate()
    stock_symbol = gen_random_stock_symbol()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_ACTN_", 1, 4)
    exp = []
    for code in "HPQT":
        pkt += gen_trade_action_msg(stock_locate, stock_symbol, code)
        exp.append(ITCHParserResult(parsed_msg=TradeActionMsg(stock_locate, stock_symbol, TradeActionCode(ord(code)))))
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

    # unexpected trading action code
    pkt = gen_header("TEST_ACTN_", 5, 1) + gen_trade_action_msg(stock_locate, stock_symbol, 'z')
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Invalid trading action.")

def test_op_halt():
    print()

    stock_locate = gen_random_stock_locate()
    stock_symbol = gen_random_stock_symbol()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_HALT_", 1, 6)
    exp = []
    for code in "QBX":
        pkt += gen_op_halt_msg(stock_locate, stock_symbol, code, "H")
        exp.append(ITCHParserResult(parsed_msg=OpHaltMsg(stock_locate, stock_symbol, code, True)))
        pkt += gen_op_halt_msg(stock_locate, stock_symbol, code, "T")
        exp.append(ITCHParserResult(parsed_msg=OpHaltMsg(stock_locate, stock_symbol, code, False)))
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

    # unexpected market code
    pkt = gen_header("TEST_HALT_", 7, 1) + gen_op_halt_msg(stock_locate, stock_symbol, "z", "H")
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Invalid market code.")

    # unexpected halt code
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_HALT_", 1, 1) + gen_op_halt_msg(stock_locate, stock_symbol, "Q", "z")
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Invalid op halt code.")

def test_add():
    print()

    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_ADD__", 1, 4)
    exp = []
    for code in "BS":
        oid = next(oid_gen)
        shares = gen_random_shares()
        price = gen_random_price()
        pkt += gen_add_msg(stock_locate, oid, code, shares, price, False)
        exp.append(ITCHParserResult(parsed_msg=AddOrderMsg(stock_locate, oid, code == "B", shares, price)))

        oid = next(oid_gen)
        shares = gen_random_shares()
        price = gen_random_price()
        pkt += gen_add_msg(stock_locate, oid, code, shares, price, True)
        exp.append(ITCHParserResult(parsed_msg=AddOrderMsg(stock_locate, oid, code == "B", shares, price)))
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

    # unexpected buy/sell code
    oid = next(oid_gen)
    shares = gen_random_shares()
    price = gen_random_price()
    pkt = gen_header("TEST_ADD__", 5, 1) + gen_add_msg(stock_locate, oid, "z", shares, price, False)
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Invalid buy/sell indicator.")

    ref = Top.get_test_parser()
    pkt = gen_header("TEST_ADD__", 1, 1) + gen_add_msg(stock_locate, oid, "z", shares, price, True)
    assert_error_msg(ref_axis_send_packet(ref, pkt), "Invalid buy/sell indicator.")

def test_reduce():
    print()

    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_REDCE", 1, 3)

    oid = next(oid_gen)
    shares = gen_random_shares()
    pkt += gen_execute_msg(stock_locate, oid, shares, False)
    exp = [ITCHParserResult(parsed_msg=ReduceOrderMsg(stock_locate, oid, shares))]

    oid = next(oid_gen)
    shares = gen_random_shares()
    pkt += gen_execute_msg(stock_locate, oid, shares, True)
    exp += [ITCHParserResult(parsed_msg=ReduceOrderMsg(stock_locate, oid, shares))]

    oid = next(oid_gen)
    shares = gen_random_shares()
    pkt += gen_cancel_msg(stock_locate, oid, shares)
    exp += [ITCHParserResult(parsed_msg=ReduceOrderMsg(stock_locate, oid, shares))]
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

def test_delete():
    print()

    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_DELTE", 1, 1)

    oid = next(oid_gen)
    pkt += gen_delete_msg(stock_locate, oid)
    exp = [ITCHParserResult(parsed_msg=DeleteOrderMsg(stock_locate, oid))]
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)

def test_replace():
    print()

    stock_locate = gen_random_stock_locate()
    oid_gen = order_id_generator()

    # correct msgs
    ref = Top.get_test_parser()
    pkt = gen_header("TEST_REPLC", 1, 1)

    oid_del = next(oid_gen)
    oid_add = next(oid_gen)
    shares = gen_random_shares()
    price = gen_random_price()
    pkt += gen_replace_msg(stock_locate, oid_del, oid_add, shares, price)
    exp = [ITCHParserResult(parsed_msg=DeleteOrderMsg(stock_locate, oid_del)),
           ITCHParserResult(parsed_msg=ReplaceOrderMsg(stock_locate, oid_add, shares, price))]
    assert_matching_result(ref_axis_send_packet(ref, pkt), exp)
