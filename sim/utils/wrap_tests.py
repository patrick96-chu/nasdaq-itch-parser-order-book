import functools
import inspect
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Event, RisingEdge, First

from sim.utils.monitors import *

def extend_test(output_monitor_class: type[OutputMonitor], extend_amt: int = 5):
    """
    Decorator that adds extra cycles to end of test.
    """
    def decorator(test_func):
        @functools.wraps(test_func)
        async def wrapper(dut, *args, **kwargs):
            error_event = Event()
            error_monitor = None
            output_monitor = None
            test_exception = None

            sig = inspect.signature(test_func)
            # if 'error_event' in sig.parameters and 'error_event' not in kwargs:
            #     kwargs['error_event'] = error_event
            if 'error_monitor' in sig.parameters and 'error_monitor' not in kwargs:
                error_monitor = ErrorMonitor(dut.clk_i, dut.error_o, error_event)
                kwargs['error_monitor'] = error_monitor
            if 'output_monitor' in sig.parameters and 'output_monitor' not in kwargs:
                assert output_monitor_class is not None, "Need to specify output monitor in decorator."
                output_monitor = output_monitor_class(dut, error_event)
                kwargs['output_monitor'] = output_monitor

            try:
                Clock(dut.clk_i, 1, unit="ns").start()
                test_task = cocotb.start_soon(test_func(dut, *args, **kwargs))
                result = await First(test_task, error_event.wait())

                # Check if background monitor tripped during a "passing" test
                if error_event.is_set():
                    await RisingEdge(dut.clk_i)
                    test_task.cancel()
                    # if error_monitor is not None:
                    #     error_monitor.stop()
                    # if output_monitor is not None:
                    #     output_monitor.stop()
                    test_exception = AssertionError("Test failed due to background monitor flag.")

            except Exception as e:
                test_exception = e

            finally:
                if error_monitor is not None:
                    error_monitor.stop()
                if output_monitor is not None:
                    output_monitor.stop()
                for _ in range(extend_amt):
                    await RisingEdge(dut.clk_i)

                if test_exception is not None:
                    raise test_exception

        return wrapper
    return decorator
