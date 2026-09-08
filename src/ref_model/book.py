import heapq

from src.ref_model.structs import *
from src.ref_model.l3_order_table import L3
from src.ref_model.l2_price_table import L2
from src.ref_model.bbo import BBO
from src.ref_model.params import config

class Book:
    """
    Top-level order book module.
    """
    def __init__(self, ideal=False):
        self.l3 = L3(ideal)
        self.l2 = L2(ideal)
        self.bbo = BBO(ideal)

        self.initialized = False

    def init_params(self, price_base: int):
        assert not self.initialized, "Book module already initialized."
        self.l2.init_params(price_base)
        self.bbo.init_params(price_base)

    def process_msg(self, msg: ITCHBookMsg):
        # assume non-matching stock locate msgs already filtered by top level module
        l3_result = self.l3.process_msg(msg)
        if l3_result.error_flag:
            return BookResult.forward_error(l3_result)

        # pass message to L2 before requesting updt
        l2_result = self.l2.process_msg(l3_result.lookup_msg)
        if l2_result.error_flag:
            return BookResult.forward_error(l2_result)

        bbo_result = self.bbo.process_msg(l3_result.lookup_msg)
        if bbo_result.error_flag:
            return BookResult.forward_error(bbo_result)

        if bbo_result.updt_req:
            l2_updt_result = self.l2.get_updt(bbo_result.updt_req_is_buy)
            if l2_updt_result.error_flag:
                return BookResult.forward_error(l2_updt_result)

            self.bbo.process_updt(bbo_result.updt_req_is_buy, l2_updt_result.entry)

        return BookResult(
            bid_entry=bbo_result.bid_entry,
            off_entry=bbo_result.off_entry,
            spread=bbo_result.spread,
        )

    def assert_consistent_state(self):
        """
        - Cumulative shares (L3 to L2 conversion)\n
        - BBO (L2 to BBO direct derivation)\n
        """
        # (price_level, aggregate shares)
        l2_reconstruct = {}
        price_base = self.l2.price_base
        price_max = self.l2.price_max

        for entry in dict(self.l3.memory).values():
            # type int, L3Entry
            if self.l2.ideal or (entry.price >= price_base and entry.price <= price_max):
                l2_reconstruct[entry.price] = l2_reconstruct.get(entry.price, 0) + entry.shares

        l2_dict = dict(self.l2.memory)
        assert l2_reconstruct == l2_dict, "[L2] and [L3's reconstruction of L2] do not match."

        l2_bid_size = len(self.l2.bids)
        l2_bid_prices = heapq.nlargest(min(l2_bid_size, config.BBO_DEPTH), self.l2.bids)
        bbo_bid_reconstruct = [BBOEntry(self.l2.memory[price], price) for price in l2_bid_prices]
        bbo_bid = self.bbo.bid_module.entries
        if not self.l2.ideal:
            # need to remove outside of price range
            bbo_bid = [entry for entry in bbo_bid if entry.price >= price_base]
        assert bbo_bid_reconstruct == bbo_bid

        l2_off_size = len(self.l2.offs)
        l2_off_prices = heapq.nsmallest(min(l2_off_size, config.BBO_DEPTH), self.l2.offs)
        bbo_off_reconstruct = [BBOEntry(self.l2.memory[price], price) for price in l2_off_prices]
        bbo_off = self.bbo.off_module.entries
        if not self.l2.ideal:
            # need to remove outside of price range
            bbo_off = [entry for entry in bbo_off if entry.price <= price_max]
        assert bbo_off_reconstruct == bbo_off
