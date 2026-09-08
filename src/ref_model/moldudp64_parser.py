from src.ref_model.structs import MoldUDP64ParserResult

class MoldUDP64Parser:
    """
    Verifies MoldUDP64 protocol and outputs individual ITCH messages as byte arrays.
    """
    def __init__(self):
        self.seq_expected = 1
        self.session_id = None
        self.first_pkt_received = False

    def process_pkt(self, pkt: bytes):
        if len(pkt) < 20:
            # packet too short
            return MoldUDP64ParserResult.error(f"Packet too short. Received {len(pkt)} bytes.")

        # parse header
        session_id = pkt[0:10]
        seq_received = int.from_bytes(pkt[10:18], "big")
        msg_count = int.from_bytes(pkt[18:20], "big")

        if not self.first_pkt_received:
            self.session_id = session_id
            self.first_pkt_received = True

        if session_id != self.session_id:
            return MoldUDP64ParserResult.error("Session ID mismatch.")

        if seq_received != self.seq_expected:
            return MoldUDP64ParserResult.error(f"Seq number mismatch. Expected: {self.seq_expected}, received: {seq_received}.")
            # return MoldUDP64ParserResult(
            #     payload=None,
            #     seq_expected=self.seq_expected,
            #     seq_received=seq_received,
            #     seq_error=True,
            # )

        self.seq_expected += msg_count

        # parse payload
        itch_msgs = []
        idx = 20
        for _ in range(msg_count):
            if len(pkt) < idx + 2:
                return MoldUDP64ParserResult.error("Packet terminated in middle of payload.")

            msg_byte_len = int.from_bytes(pkt[idx:idx+2], "big")

            if len(pkt) < idx + 2 + msg_byte_len:
                return MoldUDP64ParserResult.error("Packet terminated in middle of payload.")

            itch_msgs.append(pkt[idx:idx+2+msg_byte_len])

            idx = idx+2+msg_byte_len

        if len(pkt) != idx:
            return MoldUDP64ParserResult.error("Packet has remaining bytes.")

        return MoldUDP64ParserResult(
            payload=itch_msgs,
            # seq_expected=seq_received, # seq_expected already updated to next, but received is correct
            # seq_received=seq_received,
            # seq_error=False,
        )
