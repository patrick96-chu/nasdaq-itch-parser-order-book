import cocotb
import logging
import asyncio
from queue import Queue, Empty
from cocotb.triggers import RisingEdge, ReadOnly, First, Event
from cocotb.handle import LogicObject

from src.utils.axis_driver import *

class OutputMonitor:
    """
    Only monitors data outputs.
    For each message, collect complete output and construct corresponding python dataclass.
    Compare against expected queue.
    """

    def __init__(self, module, error_event: Event):
        self.module = module
        self._fail_event = error_event
        self._log = logging.getLogger("monitor.output")
        self._task = None
        self.expected_outputs = Queue()

    def start(self):
        if self._task is None:
            self.expected_outputs = Queue()
            self._task = cocotb.start_soon(self._loop())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def wait_for_expected_outputs(self, outputs, send_pkt_co, timeout=10):
        """
        Sets expectation, starts the packet-sending coroutine.
        """
        if not self.expected_outputs.empty():
            self._log.warning("Attempted to add expectation with non-empty queue")
            self._fail_event.set()

        self._log.debug(f"Expecting {len(outputs)} outputs.")
        for msg in outputs:
            self.expected_outputs.put(msg)

        await send_pkt_co

        for _ in range(timeout):
            if self.expected_outputs.empty():
                self._log.debug("All expected outputs received after pkt end.")
                break
            await RisingEdge(self.module.clk_i)
            await ReadOnly()
        else:
            self._log.warning("Timeout: Expected outputs were not received after packet finished.")
            self._fail_event.set()

    async def _loop(self):
        self._log.info("Monitor started.")
        try:
            while True:
                await RisingEdge(self.module.clk_i)
                await ReadOnly()

                self._process_cycle()

        except asyncio.CancelledError:
            self._log.info("Monitor stopped.")
            raise

    def _process_cycle(self):
        pass

class ErrorMonitor:
    def __init__(self, clk, dut_error, fail_event: Event):
        self.clk = clk
        self.dut_error = dut_error
        self._task = None
        self._fail_event = fail_event

        self._log = logging.getLogger("monitor.error")

        self.expected_error_wire = None
        self.error_received_event = Event()

    def start(self):
        if self._task is None:
            self.error_received_event.clear()
            self._task = cocotb.start_soon(self._loop())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def expect_error(self, error_wire: LogicObject):
        self._log.info(f"Expecting error from {error_wire._name}.")
        self.expected_error_wire = error_wire
        self.error_received_event.clear()

    async def wait_no_error(self, timeout=10):
        for _ in range(timeout):
            await RisingEdge(self.clk)
            await ReadOnly()
            if self.dut_error.value == 1:
                self._log.warning("Unexpected DUT error.")
                self._fail_event.set()

    async def wait_for_expect_error(self, error_wire, send_pkt_co, timeout=10):
        """
        Sets expectation, starts the packet-sending coroutine, races it against
        either the expected error triggering or a cycle timeout, and kills the
        sender if an error aborts it.
        """
        self.expect_error(error_wire)

        async def wait_for_error_received_event():
            await self.error_received_event.wait()
        # Start sending the packet as a background task
        sender_task = cocotb.start_soon(send_pkt_co)
        error_wait_task = cocotb.start_soon(wait_for_error_received_event())

        # Race the sender against the error event
        completed_task = await First(sender_task, error_wait_task)

        # Handle outcomes
        if error_wait_task.done():
            # Error triggered mid-packet! Abort the sender.
            error_wait_task.cancel()
            await RisingEdge(self.clk)
            sender_task.cancel()
            self._log.info("Expected error received mid-packet. Transmission aborted.")
        else:
            # Packet finished sending completely without an error triggering yet
            error_wait_task.cancel()

            # Now, we give it a few more clock cycles to see if the error triggers
            for _ in range(timeout):
                if self.error_received_event.is_set():
                    self._log.info("Expected error received post-packet.")
                    break
                await RisingEdge(self.clk)
                await ReadOnly()
            else:
                # If loop finishes without breaking, it timed out
                if sender_task.done() and not self.error_received_event.is_set():
                    self._log.warning("Timeout: Expected error did not occur after packet finished.")
                    self._fail_event.set()

        # Cleanup expectation state for the next run
        self.expected_error_wire = None

    async def _loop(self):
        self._log.info("Error monitor started.")
        try:
            while True:
                await RisingEdge(self.clk)
                await ReadOnly()

                if self.dut_error.value == 1:
                    if self.expected_error_wire is not None:
                        if self.dut_error.value != self.expected_error_wire.value:
                            self._log.warning(f"Encountered incorrect error type. Expected: {self.expected_error_wire._name}")
                            self._fail_event.set()

                        self.error_received_event.set()
                    else:
                        self._log.warning("Unexpected DUT error.")
                        self._fail_event.set()

        except asyncio.CancelledError:
            self._log.info("Error monitor stopped.")
            raise
