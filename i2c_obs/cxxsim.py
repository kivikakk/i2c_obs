import os
import platform as pyplatform
import subprocess
from argparse import ArgumentParser, Namespace
from enum import Enum
from pathlib import Path
from typing import cast

from amaranth import Elaboratable, Signal
from amaranth._toolchain.yosys import YosysBinary, find_yosys
from amaranth.back import rtlil

from .base import path
from .build import build_top
from .platform import Platform

__all__ = ["add_main_arguments"]


class _Optimize(Enum):
    none = "none"
    rtl = "rtl"

    def __str__(self):
        return self.value

    @property
    def opt_rtl(self) -> bool:
        return self in (self.rtl,)


def add_main_arguments(parser: ArgumentParser):
    parser.set_defaults(func=main)
    parser.add_argument(
        "-t",
        "--top",
        help="which top-level module to build (default: i2c_obs.rtl.Top)",
        default="i2c_obs.rtl.Top",
    )
    parser.add_argument(
        "-c",
        "--compile",
        action="store_true",
        help="compile only; don't run",
    )
    parser.add_argument(
        "-O",
        "--optimize",
        type=_Optimize,
        choices=_Optimize,
        help="build with optimizations (default: rtl)",
        default=_Optimize.rtl,
    )
    parser.add_argument(
        "-v",
        "--vcd",
        action="store_true",
        help="output a VCD file",
    )


def main(args: Namespace):
    if (
        os.environ.get("VIRTUAL_ENV") == "OSS Cad Suite"
        and pyplatform.system() == "Windows"
    ):
        # NOTE: osscad's yosys-config (used by _SystemYosys.data_dir) on Windows
        # (a) doesn't execute as-is (bash script, can't popen directly from
        # native Windows Python), and (b) its answers are wrong anyway (!!!).
        os.environ["AMARANTH_USE_YOSYS"] = "builtin"

    yosys = cast(YosysBinary, find_yosys(lambda ver: ver >= (0, 10)))

    platform = Platform["cxxsim"]
    design = build_top(args, platform)

    cxxrtl_cc_path = path("build/i2c_obs.cc")
    _cxxrtl_convert_with_header(
        yosys,
        cxxrtl_cc_path,
        design,
        platform,
        black_boxes={},
        ports=design.ports(platform),
    )

    main_cc_path = path("cxxsim/main.cc")

    cc_o_paths = {
        path("cxxsim/main.cc"): "build/main.o",    
    }

    for cc_path, o_path in cc_o_paths.items():
        subprocess.run(
            [
                "c++",
                *(["-O3"] if args.optimize.opt_rtl else []),
                "-I" + str(path(".")),
                "-I" + str(cast(Path, yosys.data_dir()) / "include"),
                "-c",
                cc_path,
                "-o",
                o_path,
            ],
            check=True,
        )

    exe_o_path = path("build/cxxsim")
    subprocess.run([
        "c++",
        *(["-O3"] if args.optimize.opt_rtl else []),
        *cc_o_paths.values(),
        "-o",
        exe_o_path,
    ], check=True)

    if not args.compile:
        cmd = [exe_o_path]
        if args.vcd:
            cmd += ["--vcd"]
        subprocess.run(cmd, cwd=path("cxxsim"), check=True)


def _cxxrtl_convert_with_header(
    yosys: YosysBinary,
    cc_out: Path,
    design: Elaboratable,
    platform: Platform,
    *,
    black_boxes: dict[str, str],
    ports: list[Signal],
) -> None:
    if cc_out.is_absolute():
        try:
            cc_out = cc_out.relative_to(Path.cwd())
        except ValueError:
            raise AssertionError(
                "cc_out must be relative to cwd for builtin-yosys to write to it"
            )
    rtlil_text = rtlil.convert(design, platform=platform, ports=ports)
    script = []
    for box_source in black_boxes.values():
        script.append(f"read_rtlil <<rtlil\n{box_source}\nrtlil")
    script.append(f"read_rtlil <<rtlil\n{rtlil_text}\nrtlil")
    script.append(f"write_cxxrtl -header {cc_out}")
    yosys.run(["-q", "-"], "\n".join(script))
