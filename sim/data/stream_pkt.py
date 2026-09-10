import struct
import random

def stream_raw_itch(file_path):
    """Generator yielding individual raw ITCH message bytes."""
    print(f"Reading {file_path}...")
    with open(file_path, "rb") as f:
        while True:
            len_bytes = f.read(2)
            if not len_bytes or len(len_bytes) < 2:
                break
            msg_len = int.from_bytes(len_bytes, "big")

            msg = f.read(msg_len)
            if len(msg) < msg_len:
                break
            yield len_bytes + msg

def generate_moldudp_packets(itch_file_path, session_id, min_pkt_size=0, max_pkt_size=20, seed=random.randint(0, 67)):
    """
    Groups raw ITCH messages into MoldUDP64 packet bytearrays.
    """
    random.seed(seed)
    current_seq = 1
    itch_stream = stream_raw_itch(itch_file_path)

    while True:
        batch_size = random.randint(min_pkt_size, max_pkt_size)
        batch_messages = bytes()
        msg_count = 0

        try:
            for _ in range(batch_size):
                batch_messages += next(itch_stream)
                msg_count += 1
        except StopIteration:
            break # Reached end of raw ITCH file

        # Build MoldUDP64 header
        header = struct.pack(">10sQH", session_id, current_seq, msg_count)

        current_seq += msg_count
        yield header + batch_messages

    print(f"Generated pkts containing total {current_seq} ITCH messages.")

def filter_itch_file(input_filepath: str, output_filepath: str, target_locate: int):
    """
    Parses a NASDAQ ITCH binary file and writes out a new binary file containing
    only messages that match the target stock locate code.
    """
    filtered_count = 0
    total_count = 0

    with open(input_filepath, "rb") as infile, open(output_filepath, "wb") as outfile:
        while True:
            # Read the 2-byte length prefix
            length_bytes = infile.read(2)
            if not length_bytes or len(length_bytes) < 2:
                break  # End of file

            # Unpack message length (Big-endian unsigned short)
            msg_length = int.from_bytes(length_bytes, byteorder="big", signed=False)

            # Read the actual message payload
            message = infile.read(msg_length)
            if len(message) < msg_length:
                break  # Unexpected EOF

            total_count += 1

            # NASDAQ ITCH 5.0 layout:
            # message[0] = Message Type (1 byte)
            # message[1:3] = Stock Locate (2 bytes, big-endian)
            # Some system events or administrative messages might not have a stock locate.
            # We safely check if the message is long enough to contain a stock locate.
            if msg_length >= 3:
                stock_locate = int.from_bytes(message[1:3], byteorder="big", signed=False)

                if stock_locate == target_locate or stock_locate == 0:
                    outfile.write(length_bytes)
                    outfile.write(message)
                    filtered_count += 1
            else:
                # If it's a control/system message shorter than 3 bytes,
                # you can choose to drop it or keep it. Here we drop it if it lacks a locate.
                continue

    print(f"Processing complete. Kept {filtered_count:,} out of {total_count:,} messages.")

if __name__ == "__main__":
    # test how many packets there are
    INPUT_FILE = "20191230.BX_ITCH_50"
    # for _ in generate_moldudp_packets(INPUT_FILE, b"MSG_COUNT "):
    #     pass=
    # result: 29156747 ITCH messages

    # generating AMD-only filter:
    filter_itch_file(INPUT_FILE, "20191230_BX_AMD_344", 344)
