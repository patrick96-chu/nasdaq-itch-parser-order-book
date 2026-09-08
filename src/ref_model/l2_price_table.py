from collections.abc import Iterator, MutableMapping
import heapq

from src.ref_model.structs import *
from src.ref_model.params import config

class L2:
    """
    Provides access to shares at the BBO_DEPTHth best price level.
    """

    def __init__(self, ideal=False):
        self.initialized = False
        self.price_base = None
        self.price_max = None

        self.ideal = ideal

        self.memory = {} if ideal else L2Memory()
        self.bids = set()
        self.offs = set()

    def init_params(self, price_base: int):
        assert not self.initialized, "L2 module already initialized."

        self.initialized = True
        self.price_base = price_base
        self.price_max = price_base + 50 * (config.L2_MEM_SIZE - 1)

        if not self.ideal:
            self.memory.init_params(price_base)

    def process_msg(self, msg: DownstreamOrderMsg):
        msg_type = msg.msg_type
        is_buy   = msg.is_buy
        shares   = msg.shares
        price    = msg.price

        # assume non-matching stock locate msgs already filtered by top level module
        if not self.initialized:
            return L2OrderResult.error("L2Order module received msg while not initialized")

        if price % 50 != 0:
            return L2OrderResult.error("Invalid price not on tick increment.")

        if not self.ideal and (price < self.price_base or price > self.price_max):
            # price out of range, ignore.
            if is_buy and price > self.price_max:
                assert False, "Bid larger than price_max, choose higher price_base."
            elif not is_buy and price < self.price_base:
                assert False, "Offer less than price_base, choose lower price_base."
            return L2OrderResult()

        assert shares > 0, "Zero shares."

        match msg_type:
            case ITCHMsgType.ADD | ITCHMsgType.REPLACE:
                if price in self.memory:
                    self.memory[price] += shares
                else:
                    self.memory[price] = shares

                if is_buy:
                    self.bids.add(price)
                else:
                    self.offs.add(price)

            case ITCHMsgType.REDUCE | ITCHMsgType.DELETE:
                assert price in self.memory, f"Expected price {price} in memory."
                new_shares = self.memory[price] - shares
                if new_shares == 0:
                    del self.memory[price]
                else:
                    self.memory[price] = new_shares

                if is_buy:
                    assert price in self.bids, f"Expected price {price} in bids"
                    if (new_shares == 0):
                        self.bids.remove(price)
                else:
                    assert price in self.offs, f"Expected price {price} in offs"
                    if (new_shares == 0):
                        self.offs.remove(price)

        return L2OrderResult()

    def get_updt(self, is_buy: bool):
        return self.get_bid_updt() if is_buy else self.get_off_updt()

    def get_bid_updt(self):
        get_idx = config.BBO_DEPTH - 1
        # if self.ideal:
        #     # in ideal memory no bids are ignored. BBO should not send a updt request.
        #     assert len(self.bids) > get_idx, "Not enough bids in L2 price table."
        # if not self.ideal and len(self.bids) <= get_idx:
        #     # in non-ideal memory out of range bids ignored. BBO does not know this.
        #     return L2UpdtReqResult.error("Not enough bids in L2 price table.")

        # shares in range tracking added to bbo, bbo should never request when no shares in range
        assert len(self.bids) > get_idx, "Not enough bids in L2 price table."

        sorted_keys = heapq.nlargest(get_idx + 1, self.bids)
        price = sorted_keys[get_idx]
        return L2UpdtReqResult(entry=BBOEntry(
            shares = self.memory[price],
            price = price,
        ))

    def get_off_updt(self):
            get_idx = config.BBO_DEPTH - 1
            # if self.ideal:
            #     assert len(self.offs) > get_idx, "Not enough offers in L2 price table."
            # if not self.ideal and len(self.offs) <= get_idx:
            #     return L2UpdtReqResult.error("Not enough offers in L2 price table.")

            assert len(self.offs) > get_idx, "Not enough offers in L2 price table."

            sorted_keys = heapq.nsmallest(get_idx + 1, self.offs)
            price = sorted_keys[get_idx]
            return L2UpdtReqResult(entry=BBOEntry(
                shares = self.memory[price],
                price = price,
            ))

class L2Memory(MutableMapping):
    """
    Size-limited price-index direct access array
    """
    def __init__(self):
        self.initialized = False
        self.price_base = None

        self.arr = [0 for _ in range(config.L2_MEM_SIZE)]
        self.inverse_hash_lut = {}

    def init_params(self, price_base: int):
        assert not self.initialized, "L2Memory already initialized"

        self.initialized = True
        self.price_base = price_base

        for tick in range(price_base, price_base + 50 * config.L2_MEM_SIZE, 50):
            self.inverse_hash_lut[L2Memory.price_hash(tick)] = tick

    @staticmethod
    def price_hash(price: int):
        assert price % 50 == 0, f"Invalid price {price} received by L2Memory"
        return (price >> 1) & (config.L2_MEM_SIZE - 1)

    def price_inverse_hash(self, hash_key: int):
        return self.inverse_hash_lut[hash_key]

    def __contains__(self, key: int):
        return self.arr[L2Memory.price_hash(key)] > 0

    def __getitem__(self, key: int):
        return self.arr[L2Memory.price_hash(key)]

    def __setitem__(self, key: int, value: int):
        self.arr[self.price_hash(key)] = value

    def __delitem__(self, key: int):
        old_val = self.arr[L2Memory.price_hash(key)]
        if old_val <= 0:
            raise KeyError
        self.arr[L2Memory.price_hash(key)] = 0

    def __len__(self):
        count = 0
        for val in self.arr:
            if val > 0:
                count += 1
        return count

    def __iter__(self):
        combined_items = [
            self.price_inverse_hash(key)
            for key in range(len(self.arr))
            if self.arr[key] > 0
        ]
        return L2MemoryIterator(combined_items)

class L2MemoryIterator(Iterator):
    def __init__(self, items):
        self._items = items
        self._index = 0

    def __next__(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item

        raise StopIteration
