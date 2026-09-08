import random
import logging
from cocotb.triggers import RisingEdge

from src.ref_model.top import Top

log = logging.getLogger("driver.axis")

def ref_axis_send_packet(ref: Top, byte_data: bytes, tvalid_drop_prob: float=0, seed=random.randint(0, 67)):
    """
    REFERENCE MODEL DRIVER:
    Pushes a single packet (byte array) across a 32-bit AXI-Stream interface.
    Drops tvalid with specified probability.
    Correct tlast. To test incorrect tlast, truncate byte_data input.
    Yields TopResults.
    """
    random.seed(seed)

    padding_len = (4 - (len(byte_data) % 4)) % 4
    padded_data = byte_data + b'\x00' * padding_len

    total_words = len(padded_data) // 4

    for word_idx in range(total_words):
        start_byte = word_idx * 4
        # Extract 4 bytes for the current 32-bit word
        chunk = padded_data[start_byte : start_byte + 4]

        # Pack bytes into a 32-bit integer
        word_value = int.from_bytes(chunk, byteorder="little")

        tkeep_value = 0xF
        if word_idx == total_words - 1 and padding_len > 0:
            # e.g., if padding_len is 1, only the first 3 bytes are valid -> tkeep = 0b0111 (7)
            valid_bytes = 4 - padding_len
            tkeep_value = (1 << valid_bytes) - 1

        # Drop tvalid at random
        while random.random() < tvalid_drop_prob:
            yield from ref.process_bus_cycle(0, False, False, tkeep_value)

        yield from ref.process_bus_cycle(word_value, (word_idx == total_words - 1), True, tkeep_value)

async def dut_send_pkt(dut, byte_data: bytes, tvalid_drop_prob: float=0.3, seed=random.randint(0, 67)):
    """
    DUT DRIVER:
    Pushes a single packet (byte array) across a 32-bit AXI-Stream interface.
    Drops tvalid with specified probability.
    Correct tlast. To test incorrect tlast, truncate byte_data input.

    Assumes DUT signals:
        - axis_tdata_i  [31:0]
        - axis_tvalid_i
        - axis_tkeep_i [3:0]
        - axis_tready_o
        - axis_tlast_i
    """
    try:
        random.seed(seed)

        await RisingEdge(dut.clk_i)

        padding_len = (4 - (len(byte_data) % 4)) % 4
        padded_data = byte_data + b'\x00' * padding_len

        total_words = len(padded_data) // 4

        for word_idx in range(total_words):
            start_byte = word_idx * 4
            # Extract 4 bytes for the current 32-bit word
            chunk = padded_data[start_byte : start_byte + 4]

            # Pack bytes into a 32-bit integer
            word_value = int.from_bytes(chunk, byteorder="big")

            # # Calculate tkeep for this word (which bytes are valid)
            # # If it's the last word and we added padding, tkeep masks out the padding bytes
            tkeep_value = 0xF
            if word_idx == total_words - 1 and padding_len > 0:
                # e.g., if padding_len is 1, only the first 3 bytes are valid -> tkeep = 0b1110 (stream left to right)
                # valid_bytes = 4 - padding_len
                tkeep_value ^= (1 << padding_len) - 1

            # Drop tvalid at random
            while random.random() < tvalid_drop_prob:
                dut.axis_tdata_i.value = 0xDEADBEEF
                dut.axis_tkeep_i.value = 0
                dut.axis_tvalid_i.value = 0
                dut.axis_tlast_i.value = 0
                await RisingEdge(dut.clk_i)

            # Drive the signals
            dut.axis_tdata_i.value = word_value
            dut.axis_tkeep_i.value = tkeep_value
            dut.axis_tvalid_i.value = 1
            dut.axis_tlast_i.value = 1 if (word_idx == total_words - 1) else 0

            # Wait for handshake (TVALID & TREADY)
            await RisingEdge(dut.clk_i)
            while not dut.axis_tready_o.value:
                await RisingEdge(dut.clk_i)

        log.info("End of packet reached")
        # Deassert valid and last after transmission completes
        # dut.axis_tdata_i.value = 0xDEADBEEF
        # dut.axis_tvalid_i.value = 0
        # dut.axis_tlast_i.value = 0
        # dut.axis_tkeep_i.value = 0
    finally:
        log.info("Terminating packet.")
        dut.axis_tdata_i.value = 0xDEADBEEF
        dut.axis_tvalid_i.value = 0
        dut.axis_tlast_i.value = 0
        dut.axis_tkeep_i.value = 0
