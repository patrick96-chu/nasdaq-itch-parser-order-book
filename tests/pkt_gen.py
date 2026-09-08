import string, random

# various generators for generating pkts (byte arrays) at MoldUDP64 layer

def gen_random_stock_locate():
    return int.from_bytes(random.randbytes(2), "big")

def gen_random_stock_symbol():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def order_id_generator():
    used_ids = set()
    while True:
        candidate = random.randint(0, (1 << 64) - 1)
        if candidate not in used_ids:
            used_ids.add(candidate)
            yield candidate

def gen_random_price():
    return random.randint(0, 4_000_0000) * 50

def gen_random_shares():
    return random.randint(0, (1 << 32) - 1)

def gen_header(session_id: str, seq_number: int, msg_count: int):
    return (bytes(session_id, encoding="utf-8") +
            int.to_bytes(seq_number, 8, "big") +
            int.to_bytes(msg_count, 2, "big"))

def gen_book_test_init_pkt(session_id: str, stock_symbol: str, stock_locate: int):
    return (gen_header(session_id, 1, 4)
           + gen_event_msg("O")
           + gen_event_msg("S")
           + gen_directory_msg(stock_locate, stock_symbol)
           + gen_trade_action_msg(stock_locate, stock_symbol, "T"))

# ITCH msg generators
def gen_event_msg(event_code: str):
    return (int.to_bytes(12, 2, "big")
            + b'S'
            + b'\00' * 10
            + bytes(event_code, encoding="utf-8")
    )

def gen_directory_msg(stock_locate: int, stock_symbol: str):
    return (int.to_bytes(39, 2, "big")
            + b'R'
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + bytes(stock_symbol, encoding="utf-8")
            + b'\00' * 20
    )

def gen_trade_action_msg(stock_locate: int, stock_symbol: str, trade_action: str):
    return (int.to_bytes(25, 2, "big")
            + b'H'
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + bytes(stock_symbol, encoding="utf-8")
            + bytes(trade_action, encoding="utf-8")
            + b'\00' * 5
    )

def gen_op_halt_msg(stock_locate: int, stock_symbol: str, market_code: str, action: str):
    return (int.to_bytes(21, 2, "big")
            + b'h'
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + bytes(stock_symbol, encoding="utf-8")
            + bytes(market_code, encoding="utf-8")
            + bytes(action, encoding="utf-8")
    )

def gen_add_msg(stock_locate: int, order_id: int, buy_sell: str, shares: int, price: int, mpid: bool=False):
    return (int.to_bytes(40 if mpid else 36, 2, "big")
            + (b'F' if mpid else b'A')
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + int.to_bytes(order_id, 8, "big")
            + bytes(buy_sell, encoding="utf-8")
            + int.to_bytes(shares, 4, "big")
            + b'\00' * 8
            + int.to_bytes(price, 4, "big")
            + b'\00' * (4 if mpid else 0)
    )

def gen_execute_msg(stock_locate: int, order_id: int, shares: int, at_price: bool=False):
    return (int.to_bytes(36 if at_price else 31, 2, "big")
            + (b'C' if at_price else b'E')
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + int.to_bytes(order_id, 8, "big")
            + int.to_bytes(shares, 4, "big")
            + b'\00' * 8
            + b'\00' * (5 if at_price else 0)
    )

def gen_cancel_msg(stock_locate: int, order_id: int, shares: int):
    return (int.to_bytes(23, 2, "big")
            + b'X'
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + int.to_bytes(order_id, 8, "big")
            + int.to_bytes(shares, 4, "big")
    )

def gen_delete_msg(stock_locate: int, order_id: int):
    return (int.to_bytes(19, 2, "big")
            + b'D'
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + int.to_bytes(order_id, 8, "big")
    )

def gen_replace_msg(stock_locate: int, order_id_del: int, order_id_add: int, shares: int, price: int):
    return (int.to_bytes(35, 2, "big")
            + b'U'
            + int.to_bytes(stock_locate, 2, "big")
            + b'\00' * 8
            + int.to_bytes(order_id_del, 8, "big")
            + int.to_bytes(order_id_add, 8, "big")
            + int.to_bytes(shares, 4, "big")
            + int.to_bytes(price, 4, "big")
    )

# TODO: random ignore msg generator?
def gen_ignore_msg():
    return (
        int.to_bytes(35, 2, "big")
        + b'J'
        + int.to_bytes(0xAA, 1, "big") * 34
    )

def gen_wrong_msg():
    return (
        int.to_bytes(35, 2, "big")
        + b'z'
        + int.to_bytes(0xAA, 1, "big") * 34
    )
