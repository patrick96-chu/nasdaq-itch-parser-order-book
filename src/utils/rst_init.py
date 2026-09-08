import logging
from cocotb.triggers import RisingEdge

from src.ref_model.top import Top

log = logging.getLogger("driver.rst_init")

async def dut_flush(dut, cycles=12):
    """
    Waits for some cycles
    """
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)

async def dut_rst_init(dut, market_code: str, stock_symbol: str, price_base: int):
    """
    Does global reset followed by initialization.
    """
    await dut_rst(dut)

    await RisingEdge(dut.clk_i)

    await dut_init(dut, market_code, stock_symbol, price_base)

    MAX_RESET_CYCLES = 5000
    reset_cycles = 0
    while dut.book_ready_o.value != 1:
        assert reset_cycles < MAX_RESET_CYCLES, "Timed out while waiting for book_ready_o."
        reset_cycles += 1
        await RisingEdge(dut.clk_i)

    log.debug("Initialized and ready.")

async def dut_rst(dut):
    """
    Pulses global reset pin.
    """
    await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 0
    await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)
    log.debug("Reset toggled.")

async def dut_init(dut, market_code: str, stock_symbol: str, price_base: int):
    """
    Initializes dut with given market, stock symbol, and price array base.
    """
    # pad with spaces
    symbol_bytes = stock_symbol.encode('ascii')[:8].rjust(8, b' ')

    match market_code:
        case "Q":
            market = 0
        case "B":
            market = 1
        case "X":
            market = 2
        case _:
            raise ValueError("Invalid market code.")

    log.debug(f"Initializing...Market: {market_code}, Symbol: {stock_symbol}, Price base: 0x{price_base:08X} ; ${price_base / 10000}")
    dut.init_v_i.value            = 1
    dut.init_market_i.value       = market
    dut.init_stock_symbol_i.value = int.from_bytes(symbol_bytes, byteorder='big')
    dut.init_price_base_i.value   = price_base

    await RisingEdge(dut.clk_i)

    log.debug("Parameters initialized.")
    dut.init_v_i.value            = 0
    dut.init_market_i.value       = 0
    dut.init_stock_symbol_i.value = int.from_bytes(b"DEADBEEF", byteorder="big")
    dut.init_price_base_i.value   = 0xBEEF

def ref_rst_init(market_code: str, stock_symbol: str, price_base: int, ideal=False):
    ref = ref_rst(ideal)
    ref_init(ref, market_code, stock_symbol, price_base)
    return ref

def ref_rst(ideal=False):
    """
    Resetting reference model equivalent to creating new instance.
    """
    return Top(ideal)

def ref_init(ref: Top, market_code: str, stock_symbol: str, price_base: int):
    """
    Initialize ref model, return true if errored due to previous initialization
    """
    return ref.init_params(market_code, stock_symbol, price_base)
