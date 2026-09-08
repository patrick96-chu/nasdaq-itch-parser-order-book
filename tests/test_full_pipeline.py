from src.ref_model.top import Top
from src.utils.rst_init import *
from src.utils.axis_driver import ref_axis_send_packet
from sim.data.stream_pkt import generate_moldudp_packets
from tests.assertions import *

def test_20191230_BX_AMD():
    print()
    fast = True
    INPUT_FILE = "sim/data/20191230_BX_AMD_344" if fast else "sim/data/20191230.BX_ITCH_50"
    ITCH_MESSAGE_COUNT = 108965 if fast else 29156747
    APPROX_PACKET_COUNT = ITCH_MESSAGE_COUNT / 10
    pkt_generator = generate_moldudp_packets(INPUT_FILE, b"20191230BX", seed=0)

    ref_ideal = ref_rst_init("B", "AMD     ", 40_0000, True)
    ref_not_i = ref_rst_init("B", "AMD     ", 40_0000, False)

    progress = 1
    count = 0
    for pkt in pkt_generator:
        if count > APPROX_PACKET_COUNT / 100:
            # print(f"Testing packets: {progress}% done.")
            ref_ideal.book.bbo.print_bbo_state()
            progress += 1
            count = 0
        res_ideal = list(ref_axis_send_packet(ref_ideal, pkt))
        res_not_i = list(ref_axis_send_packet(ref_not_i, pkt))
        assert_no_error(res_ideal)
        assert_no_error(res_not_i)
        assert res_ideal == res_not_i
        ref_ideal.assert_consistent_book_state()
        ref_not_i.assert_consistent_book_state()
        count += 1

if __name__ == "__main__":
    test_20191230_BX_AMD()
