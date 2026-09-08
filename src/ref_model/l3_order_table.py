import logging
from collections.abc import Iterator, MutableMapping

from src.ref_model.structs import *
from src.ref_model.params import config

log = logging.getLogger("ref.l3")
log.setLevel("DEBUG")

class L3:
    """
    Provides lookup order data from order id.
    """

    def __init__(self, ideal=False):
        """
        If ideal is set to True, the underlying memory structure has no limitations.
        Otherwise, a memory structure mirroring that of hardware is used.
        """
        self.memory = {} if ideal else L3Memory()
        self.last_del_is_buy = None

    def process_msg(self, msg: ITCHBookMsg):
        # assume non-matching stock locate msgs already filtered by top level module
        match msg.msg_type:
            case ITCHMsgType.ADD:
                assert isinstance(msg, AddOrderMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.order_id in self.memory:
                    return L3Result.error("Attempted to add with existing order ID.")

                try:
                    self.memory[msg.order_id] = L3Entry(is_buy=msg.is_buy, shares=msg.shares, price=msg.price)
                except MemoryError as e:
                    return L3Result.error(str(e))

                return L3Result(lookup_msg=DownstreamOrderMsg(
                    msg_type = msg.msg_type,
                    is_buy   = msg.is_buy,
                    shares   = msg.shares,
                    price    = msg.price,
                ))

            case ITCHMsgType.REDUCE:
                assert isinstance(msg, ReduceOrderMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.order_id not in self.memory:
                    return L3Result.error("Attempted to reduce shares of missing order ID.")

                old_entry = self.memory[msg.order_id]

                new_shares = old_entry.shares - msg.shares
                if new_shares > 0:
                    self.memory[msg.order_id] = L3Entry(is_buy=old_entry.is_buy, shares=new_shares, price=old_entry.price)
                elif new_shares == 0:
                    del self.memory[msg.order_id]
                else:
                    return L3Result.error("Unexpected negative shares after reducing.")

                return L3Result(lookup_msg=DownstreamOrderMsg(
                    msg_type = msg.msg_type,
                    is_buy   = old_entry.is_buy,
                    shares   = msg.shares,
                    price    = old_entry.price,
                ))

            case ITCHMsgType.DELETE:
                assert isinstance(msg, DeleteOrderMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.order_id not in self.memory:
                    return L3Result.error("Attempted to delete missing order ID.")

                old_entry = self.memory[msg.order_id]

                del self.memory[msg.order_id]

                self.last_del_is_buy = old_entry.is_buy

                return L3Result(lookup_msg=DownstreamOrderMsg(
                    msg_type = msg.msg_type,
                    is_buy   = old_entry.is_buy,
                    shares   = old_entry.shares,
                    price    = old_entry.price,
                ))

            case ITCHMsgType.REPLACE:
                assert isinstance(msg, ReplaceOrderMsg), f"Incorrect msg object type for {msg.msg_type}."

                if msg.order_id in self.memory:
                    return L3Result.error("Attempted to replace-add with existing order ID.")

                assert self.last_del_is_buy is not None, "last_del_is_buy is None."

                try:
                    self.memory[msg.order_id] = L3Entry(is_buy=self.last_del_is_buy, shares=msg.shares, price=msg.price)
                except MemoryError as e:
                    return L3Result.error(str(e))

                return L3Result(lookup_msg=DownstreamOrderMsg(
                    msg_type = msg.msg_type,
                    is_buy   = self.last_del_is_buy,
                    shares   = msg.shares,
                    price    = msg.price,
                ))

            case _:
                assert False, "L3 received non-book msg."


class L3Memory(MutableMapping):
    """
    Size-limited hash table + CAM reflecting actual hardware limitations
    """
    def __init__(self):
        self.ram = [{} for _ in range(1 << config.L3_LOG_ADDR_SIZE)]
        self.cam = {}

    @staticmethod
    def oid_hash(order_id: int):
        mask = ((1 << config.L3_LOG_ADDR_SIZE) - 1)
        lower_bits = order_id & mask
        # upper_bits = (order_id >> config.L3_LOG_ADDR_SIZE) & mask

        return lower_bits
        # return lower_bits ^ upper_bits

    def __contains__(self, item: int):
        return item in self.ram[self.oid_hash(item)] or item in self.cam

    def __getitem__(self, key: int):
        # access hash table
        key_hash = self.oid_hash(key)
        line = self.ram[key_hash]
        if key in line:
            return line[key]

        # access cam
        if key in self.cam:
            return self.cam[key]

        # key not found
        raise KeyError(f"Key 0x{key:X} not in L3 memory.")

    def __setitem__(self, key: int, value: L3Entry):
        # search hash table
        key_hash = self.oid_hash(key)
        line = self.ram[key_hash]

        if key in line:
            line[key] = value
            return

        # search cam
        if key in self.cam:
            self.cam[key] = value
            return

        # no existing matches, so attempt ram line insertion
        if len(line) < (1 << config.L3_LOG_LINE_SIZE):
            line[key] = value
            return

        log.debug(f"Attempted insertion for full line at {key_hash:h}.")
        log.debug(line)
        log.debug("Current CAM state:")
        log.debug(self.cam)
        # ram line full, attempt add to cam
        if len(self.cam) < config.L3_CAM_SIZE:
            self.cam[key] = value
            return

        raise MemoryError(f"L3 Hash Table out of memory slots for hash 0x{key_hash:X}")

    def __delitem__(self, key: int):
        # search hash table
        key_hash = self.oid_hash(key)
        line = self.ram[key_hash]
        if key in line:
            del line[key]
            return

        # search cam
        if key in self.cam:
            del self.cam[key]
            return

        raise KeyError(f"L3 hash table does not contain key 0x{key:X} to delete.")

    def __len__(self):
        count = 0
        for bucket in self.ram:
            count += len(bucket)
        count += len(self.cam)
        return count

    def __iter__(self):
        combined_items = [
            key for bucket in self.ram
            for key in bucket
        ] + list(self.cam)
        return L3MemoryIterator(combined_items)

class L3MemoryIterator(Iterator):
    def __init__(self, items):
        self._items = items
        self._index = 0

    def __next__(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item

        raise StopIteration
