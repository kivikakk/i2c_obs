import subprocess
from argparse import ArgumentParser, Namespace
from typing import Tuple

from amaranth import Module, Signal, Value
from amaranth.back import rtlil

from ..base import path
from ..platform import Platform


def add_main_arguments(parser: ArgumentParser):
    parser.set_defaults(func=main)
    parser.add_argument(
        "tasks",
        help="tasks to run; defaults to all",
        nargs="*",
    )


def main(args: Namespace):
    design, ports = prep_formal()
    output = rtlil.convert(
        design, platform=Platform["test"], name="formal_top", ports=ports
    )
    with open(path("build/i2c_obs.il"), "w") as f:
        f.write(output)

    sby_file = path("i2c_obs/formal/i2c_obs.sby")
    subprocess.run(
        ["sby", "--prefix", "build/i2c_obs", "-f", sby_file, *args.tasks], check=True
    )


def prep_formal() -> Tuple[Module, list[Signal | Value]]:
    m = Module()

    # I2C, oh! WIP.
    # sync_clk = ClockSignal("sync")
    # sync_rst = ResetSignal("sync")

    return m, [
        # sync_clk,
        # sync_rst,
    ]
