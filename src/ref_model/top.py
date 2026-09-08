from src.ref_model.structs import *
from src.ref_model.axis_interpreter import AxisInterpreter
from src.ref_model.moldudp64_parser import MoldUDP64Parser
from src.ref_model.itch_parser import ITCHParser
from src.ref_model.control import Control
from src.ref_model.book import Book

class Top:
    """
    Top-level module for reference model.
    """

    def __init__(self, ideal=False):
        self.axis = AxisInterpreter(self.process_pkt)
        self.np = MoldUDP64Parser()
        self.ip = ITCHParser()
        self.ctrl = Control()
        self.book = Book(ideal)

        self.initialized = False

        self.stock_active = False
        self.stock_locate = None

    def init_params(self, market_code: str, stock_symbol: str, price_base: int):
        # returns true if initialization error
        # use assertions in submodules to catch reinitialization.
        self.ctrl.init_params(market_code, stock_symbol)
        self.book.init_params(price_base)

        init_error = self.initialized
        self.initialized = True
        return init_error

    def process_bus_cycle(self, tdata: int, tlast: bool, tvalid: bool, tkeep: int):
        """
        Processes single input cycle. Yields TopResults if packet was completed.
        """
        # tvalid always True
        yield from self.axis.process_bus_cycle(tdata, tlast, tvalid, tkeep, True)

    def process_pkt(self, pkt: bytes):
        """
        Yields result for each individual ITCH message in the packet.
        BBO results are not-None only if ITCH message is a book message.
        """
        np_result = self.np.process_pkt(pkt)
        if np_result.error_flag:
            yield TopResult.forward_error(np_result)
            return

        for unparsed_msg in np_result.payload:
            output_flag = False

            bid_entry = None
            off_entry = None
            spread = None

            # ip_results may yield 2 valid results in case of REPLACE order operation.
            ip_results = self.ip.parse_msg(unparsed_msg)
            for ip_result in ip_results:
                if ip_result.error_flag:
                    yield TopResult.forward_error(ip_result)
                    return

                # if ip_result.parsed_msg.msg_type == ITCHMsgType.IGNORE:
                #     ignore_flag = True
                #     break

                ctrl_result = self.ctrl.process_msg(ip_result.parsed_msg)
                if ctrl_result.error_flag:
                    yield TopResult.forward_error(ctrl_result)
                    return

                self.stock_active = ctrl_result.stock_active
                if ctrl_result.stock_locate is not None:
                    # duplication detection in control module
                    assert self.stock_locate is None, "Top-level stock_locate already initialized."
                    self.stock_locate = ctrl_result.stock_locate
                    print(f"Initializing stock_locate: {self.stock_locate}")

                if isinstance(ip_result.parsed_msg, ITCHBookMsg):
                    # assert self.stock_locate is not None, "Top-level stock_locate not initialized before book msg."
                    if self.stock_locate is None:
                        # in rtl this error is asserted by itch parser module
                        yield TopResult.error("Top-level stock_locate not initialized before book msg.")
                        return

                    if ip_result.parsed_msg.stock_locate == self.stock_locate:
                        book_result = self.book.process_msg(ip_result.parsed_msg)
                        output_flag = True
                        if book_result.error_flag:
                            yield TopResult.forward_error(book_result)
                            return

                        # in case of replace msg, intermediate state between delete and replace not valid.
                        # the below for delete half would get overwritten by replace half.
                        bid_entry = book_result.bid_entry
                        off_entry = book_result.off_entry
                        spread    = book_result.spread

            if output_flag:
                yield TopResult(
                    bid_entry=bid_entry if self.stock_active else None,
                    off_entry=off_entry if self.stock_active else None,
                    spread   =spread if self.stock_active else None,
                )

    @staticmethod
    def get_test_parser():
        """
        TESTING ONLY: sets callback to test_parse_pkt to end pipeline at ITCH parser.
        Returns Top instance.
        """
        ref = Top()
        ref.axis = AxisInterpreter(ref.test_parse_pkt)
        return ref

    def test_parse_pkt(self, pkt: bytes):
        """
        TESTING ONLY: yields ITCHParserResult from bytes
        """
        np_result = self.np.process_pkt(pkt)
        if np_result.error_flag:
            yield ITCHParserResult.forward_error(np_result)
            return

        for unparsed_msg in np_result.payload:
            ip_results = self.ip.parse_msg(unparsed_msg)
            yield from ip_results

    def test_process_ctrl_msg(self, msg: ITCHMsg):
        """
        TESTING ONLY: returns ControlResult from ITCHMsg.
        """
        ctrl_result = self.ctrl.process_msg(msg)
        return ctrl_result

    @staticmethod
    def get_test_process_book_msg(ideal: bool, stock_locate: int, price_base: int):
        """
        TESTING ONLY: returns Top intstance initialized with stock_locate and price_base
        """
        ref = Top(ideal)
        ref.initialized = True
        ref.book.init_params(price_base)
        ref.stock_locate = stock_locate
        return ref

    def test_process_book_msg(self, parsed_msgs):
        """
        TESTING ONLY: returns BookResult from ITCHBookMsg.
        Assumes stock locate matches and stock active.
        Input msgs may be a single msg OR a list of 2 msgs (must be delete + replace).
        """
        msgs = parsed_msgs
        # converting to list
        if isinstance(parsed_msgs, ITCHMsg):
            msgs = []
            msgs.append(parsed_msgs)

        bid_entry = None
        off_entry = None
        spread = None

        for msg in msgs:
            assert isinstance(msg, ITCHBookMsg), "Did not receive book msg."

            book_result = self.book.process_msg(msg)
            if book_result.error_flag:
                return book_result

            # in case of replace msg, intermediate state between delete and replace not valid.
            # the below for delete half would get overwritten by replace half.
            bid_entry = book_result.bid_entry
            off_entry = book_result.off_entry
            spread    = book_result.spread

        return BookResult(
            bid_entry=bid_entry,
            off_entry=off_entry,
            spread=spread,
        )

    def assert_consistent_book_state(self):
        """
        TESTING ONLY: ensures consistency across book modules.
        """
        self.book.assert_consistent_state()
