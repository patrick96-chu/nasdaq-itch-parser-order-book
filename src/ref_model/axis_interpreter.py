class AxisInterpreter:
    """
    Assembles complete MoldUDP64 packet from AXI Stream as bytes.
    """
    def __init__(self, callback):
        self.buffer = bytearray()
        self.callback = callback

    def process_bus_cycle(self, tdata: int, tlast: bool, tvalid: bool, tkeep: int, tready: bool):
        """
        Yields TopResults if packet was completed.
        """
        if not (tvalid and tready):
            return

        word_bytes = tdata.to_bytes(4, byteorder='little')
        for i in range(4):
            if (tkeep >> i) & 0x1:
                self.buffer.append(word_bytes[i])

        if tlast:
            completed_packet = bytes(self.buffer)
            self.buffer.clear()

            yield from self.callback(completed_packet)
