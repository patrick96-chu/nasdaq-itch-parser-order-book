from src.ref_model.structs import *
from src.ref_model.params import config

class BBO:
    """
    Provides price and shares for best buy/sell prices.
    """
    def __init__(self, ideal=False):
        self.ideal = ideal
        self.bid_module = BBOHalf(True, ideal)
        self.off_module = BBOHalf(False, ideal)

        self.bid_entry = None
        self.off_entry = None

        self.initialized = False

    def init_params(self, price_base: int):
        assert not self.initialized, "BBO module already initialized."

        self.initialized = True
        price_max = price_base + 50 * (config.L2_MEM_SIZE - 1)
        self.bid_module.init_params(price_base)
        self.off_module.init_params(price_max)

    def process_msg(self, msg: DownstreamOrderMsg):
        # assume non-matching stock locate msgs already filtered by top level module
        updt_req = False
        updt_req_is_buy = msg.is_buy
        updt_req_mask_enc = 0

        if msg.is_buy:
            bid_result = self.bid_module.process_msg(msg)
            if bid_result.error_flag:
                return BBOResult.error("(BID) " + bid_result.error_code)

            self.bid_entry = bid_result.entry
            updt_req = bid_result.updt_req
            updt_req_mask_enc = bid_result.updt_req_mask_enc

        else:
            off_result = self.off_module.process_msg(msg)
            if off_result.error_flag:
                return BBOResult.error("(OFF) " + off_result.error_code)

            self.off_entry = off_result.entry
            updt_req = off_result.updt_req
            updt_req_mask_enc = off_result.updt_req_mask_enc

        spread = None
        if self.bid_entry and self.off_entry:
            spread = self.off_entry.price - self.bid_entry.price
            assert spread > 0, "Spread should be positive."

        return BBOResult(
            bid_entry=self.bid_entry,
            off_entry=self.off_entry,
            spread=spread,
            updt_req=updt_req,
            updt_req_is_buy=updt_req_is_buy,
            updt_req_mask_enc=updt_req_mask_enc,
        )

    def process_updt(self, is_buy: bool, entry: BBOEntry):
        if is_buy:
            self.bid_module.process_updt(entry)
        else:
            self.off_module.process_updt(entry)

    def print_bbo_state(self):
        """
        TESTING ONLY: prints current bbo
        """
        bid_string = "Bid: None" if self.bid_entry is None else f"Bid: {self.bid_entry.shares} at {self.bid_entry.price}"
        off_string = "Offer: None" if self.off_entry is None else f"Offer: {self.off_entry.shares} for {self.off_entry.price}"
        print(f"{bid_string}, {off_string}.")



class BBOHalf:
    """
    Provides price and shares for one buy/sell side.
    """
    def __init__(self, is_buy: bool, ideal=False):
        self.is_buy = is_buy
        self.ideal = ideal

        self.entries: list[BBOEntry] = []
        self.outside_shares_in_range = 0
        self.outside_shares = 0

    def init_params(self, price_bound: int):
        self.price_bound = price_bound

    def process_msg(self, msg: DownstreamOrderMsg):
        msg_type = msg.msg_type
        shares   = msg.shares
        price    = msg.price

        # assume non-matching stock locate msgs already filtered by book top level module
        # also assume buy/sell side already filtered by bbo top level module
        assert msg.is_buy == self.is_buy, "Non-matching buy/sell side received in BBOHalf module."

        modify_flag = False
        modify_idx = 0
        modify_entry = None
        depletion_flag = False
        depletion_idx = 0
        insertion_flag = False
        insertion_idx = 0
        outside_flag = True

        for idx, entry in enumerate(self.entries):
            if price == entry.price:
                match msg_type:
                    case ITCHMsgType.ADD | ITCHMsgType.REPLACE:
                        modify_flag = True
                        modify_idx = idx
                        modify_entry = BBOEntry(entry.shares + shares, entry.price)
                    case ITCHMsgType.REDUCE | ITCHMsgType.DELETE:
                        new_shares = entry.shares - shares
                        # this should be caught in L3
                        assert new_shares >= 0, f"Unexpected negative quantity of shares at price: {price}."
                        # if entry.shares < 0:
                        #     return BBOHalfResult.error(f"Unexpected negative quantity of shares at price: {price}.")

                        if new_shares == 0:
                            depletion_flag = True
                            depletion_idx = idx
                        else:
                            modify_flag = True
                            modify_idx = idx
                            modify_entry = BBOEntry(new_shares, entry.price)
                    case _:
                        assert False, "Unexpected msg_type in BBOHalf process_msg"

                outside_flag = False
                break

            elif (self.is_buy and price > entry.price) or (not self.is_buy and price < entry.price):
                # this should be caught in L3
                assert msg_type == ITCHMsgType.ADD or msg_type == ITCHMsgType.REPLACE, f"Unexpected reduction of non-existing price: {price}."
                # if not (msg_type == ITCHMsgType.ADD or msg_type == ITCHMsgType.REPLACE):
                #     return BBOHalfResult.error(f"Unexpected reduction of non-existing price: {price}.")

                insertion_flag = True
                insertion_idx = idx
                outside_flag = False
                break

        # assert ((not (depletion_flag and insertion_flag)) and
        #         (not (depletion_flag and outside_flag)) and
        #         (not (insertion_flag and outside_flag))), "Unexpected multiple flags true in BBOHalf module."

        updt_req = False
        updt_req_mask_enc = 0

        if modify_flag:
            self.entries[modify_idx] = modify_entry
        elif depletion_flag:
            self.entries.pop(depletion_idx)
            if self.outside_shares_in_range > 0:
                assert len(self.entries) == (config.BBO_DEPTH - 1), f"Unexpected entries length for updt req."
                updt_req = True
                updt_req_mask_enc = self.entries[config.BBO_DEPTH - 2].price

            elif self.outside_shares > 0:
                return BBOHalfResult.error("No shares in range for updt.")

        elif insertion_flag:
            self.entries.insert(insertion_idx, BBOEntry(shares, price))
            if len(self.entries) > config.BBO_DEPTH:
                add_entry = self.entries.pop()
                self.outside_shares += add_entry.shares
                if (self.ideal or
                    (self.is_buy and add_entry.price >= self.price_bound) or
                    (not self.is_buy and add_entry.price <= self.price_bound)):
                    self.outside_shares_in_range += add_entry.shares


        elif outside_flag:
            if len(self.entries) < config.BBO_DEPTH:
                self.entries.append(BBOEntry(shares, price))
            else:
                in_range = (self.ideal or
                            (self.is_buy and price >= self.price_bound) or
                            (not self.is_buy and price <= self.price_bound))
                match msg_type:
                    case ITCHMsgType.ADD | ITCHMsgType.REPLACE:
                        self.outside_shares += shares
                        if in_range:
                            self.outside_shares_in_range += shares
                    case ITCHMsgType.REDUCE | ITCHMsgType.DELETE:
                        self.outside_shares -= shares
                        if in_range:
                            self.outside_shares_in_range -= shares
                    case _:
                        assert False, "Unexpected msg_type in BBOHalf process_msg"

        if not self.entries:
            return BBOHalfResult(
                entry=None,
                updt_req=False,
                updt_req_mask_enc=0,
            )

        return BBOHalfResult(
            entry=self.entries[0],
            updt_req=updt_req,
            updt_req_mask_enc=updt_req_mask_enc,
        )

    def process_updt(self, entry: BBOEntry):
        assert len(self.entries) == config.BBO_DEPTH - 1, "Unexpected number of entries for process_updt."
        self.entries.append(entry)
        self.outside_shares -= entry.shares
        self.outside_shares_in_range -= entry.shares

# @dataclass
# class BBOEntry:
#     shares: int
#     price: int

    # def __add__(self, other):
    #     if not isinstance(other, BBOEntry):
    #         raise TypeError("Cannot add non-BBOEntry object.")
    #     if other.price != self.price:
    #         raise ValueError("Attempted to add non-matching price BBO entries.")
    #     return BBOEntry(self.shares + other.shares, self.price, self.is_buy)

    # def __sub__(self, other):
    #     if not isinstance(other, BBOEntry):
    #         raise TypeError("Cannot add non-BBOEntry object.")
    #     if other.price != self.price:
    #         raise ValueError("Attempted to add non-matching price BBO entries.")
    #     return BBOEntry(self.shares - other.shares, self.price, self.is_buy)
    # def __eq__(self, other):
    #     if not isinstance(other, BBOEntry):
    #         raise TypeError("Cannot compare with non-BBOEntry object.")
    #     return self.price == other.price

    # def __gt__(self, other):
    #     if not isinstance(other, BBOEntry):
    #         raise TypeError("Cannot compare with non-BBOEntry object.")
    #     # if is_buy, then we consider higher price (closer to top) as higher value.
    #     # thus, if not is_buy, __gt__ is equivalent to self.price < other.price
    #     return self.price > other.price if self.is_buy else self.price < other.price

    # def __lt__(self, other):
    #     if not isinstance(other, BBOEntry):
    #         raise TypeError("Cannot compare with non-BBOEntry object.")
    #     return self.price < other.price if self.is_buy else self.price > other.price
