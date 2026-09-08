import os
import sys
from pathlib import Path
from cocotb_tools.runner import get_runner

def test_runner(source_func, hdl_toplevel, test_module):
    sim = os.getenv("SIM", "verilator")

    proj_path = Path("/mnt/c/Users/patri/Documents/NASDAQ_ITCH_PARSER")
    rtl_dir = proj_path / "rtl"
    target_build_dir = proj_path / "sim" / "sim_build"

    os.environ["PYTHONPATH"] = str(proj_path)

    includes = [(rtl_dir / "include")]
    sources = source_func(rtl_dir)

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        includes=includes,
        hdl_toplevel=hdl_toplevel,
        build_args=["--timing", "--build", "--trace", "--trace-structs"], #, "--trace-fst"
        build_dir=target_build_dir,
    )

    test_dir = proj_path / "sim" / "tests"
    if str(test_dir) not in sys.path:
        sys.path.append(str(test_dir))

    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module=test_module,
        extra_env={
            "PYTHONPATH": str(proj_path)},
        build_dir=target_build_dir,
        waves=True,
    )

def test_moldudp64_parser_runner():
    def source_func(rtl_dir):
        return [rtl_dir / "module" / "moldudp64_parser.sv"]

    hdl_toplevel = "moldudp64_parser_interface"
    test_module = "sim_moldudp64_parser"

    test_runner(source_func, hdl_toplevel, test_module)

def test_itch_parser_runner():
    def source_func(rtl_dir):
        return [
            rtl_dir / "module" / "moldudp64_parser.sv",
            rtl_dir / "module" / "itch_parser.sv",
        ]

    hdl_toplevel = "itch_parser_interface"
    test_module = "sim_itch_parser"

    test_runner(source_func, hdl_toplevel, test_module)

def test_control_runner():
    def source_func(rtl_dir):
        return [
            rtl_dir / "module" / "moldudp64_parser.sv",
            rtl_dir / "module" / "itch_parser.sv",
            rtl_dir / "module" / "control.sv",
        ]

    hdl_toplevel = "control_interface"
    test_module = "sim_control"

    test_runner(source_func, hdl_toplevel, test_module)

def test_top_runner():
    def source_func(rtl_dir):
        return (list(Path(rtl_dir / "module").rglob('*.sv'))
                + [ rtl_dir / "top.sv" ])

    hdl_toplevel = "top"
    test_module = "sim_top"

    test_runner(source_func, hdl_toplevel, test_module)

if __name__ == "__main__":
    # test_moldudp64_parser_runner()
    # test_itch_parser_runner()
    # test_control_runner()
    test_top_runner()
