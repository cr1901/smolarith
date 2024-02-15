import json
import subprocess
from string import Template

from io import StringIO
from amaranth import Elaboratable
from amaranth.back import rtlil


class RunnerError(Exception):
    pass


GENERIC_SCRIPT = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} hierarchy -check
${quiet} proc
${quiet} flatten
${quiet} tribuf -logic
${quiet} deminout
${quiet} synth -run coarse
${quiet} memory_map
${quiet} opt -full
${quiet} techmap -map +/techmap.v
${quiet} opt -fast
${quiet} dfflegalize -cell $$_DFF_P_ 0
${quiet} abc -lut 4 -dress
${quiet} clean -purge
stat -json
""")


ICE40_SCRIPT = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_ice40
stat -json
""")


ECP5_SCRIPT = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_lattice -family ecp5
stat -json
""")


def stats(m, script):
    rtlil_text = rtlil.convert(m)

    stdin = script.substitute(rtlil_text=rtlil_text, quiet="tee -q")

    popen = subprocess.Popen(["yosys", "-Q", "-T", "-"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             encoding="utf-8")
    stdout, stderr = popen.communicate(stdin)
    if popen.returncode:
        raise RunnerError(stderr.strip())

    # Find the start of the JSON from the stats command.
    for i, l in enumerate(StringIO(stdout).readlines()):
        if l[0] == "{":
            break

    # Restart read since we can't really put back a line...
    stdout = StringIO(stdout)
    stdout.readlines(i)  # Drain non-JSON lines.
    print(json.load(stdout))


def main():
    pass


if __name__ == "__main__":
    import argparse
    import importlib

    p = argparse.ArgumentParser(description="smolarith benchmarking program using yosys")  # noqa: E501
    p.add_argument("-s", choices=("generic", "ice40", "ecp5"), default="generic", help="script to execute")  # noqa: E501
    p.add_argument("-w", type=int, default=8, help="width of Amaranth component to test")  # noqa: E501
    p.add_argument("import_path", help="relative import path (i.e. Amaranth component) in smolarith to benchmark (include leading '.')")  # noqa: E501

    args = p.parse_args()

    if args.s == "generic":
        script = GENERIC_SCRIPT
    elif args.s == "ice40":
        script = ICE40_SCRIPT
    elif args.s == "ecp5":
        script = ECP5_SCRIPT
    else:
        assert False

    try:
        split_path = args.import_path.split(".")
        implib_path = ".".join(split_path[:-1])
        cls = getattr(importlib.import_module(implib_path, "smolarith"), split_path[-1])  # noqa: E501
    except ImportError as e1:
        raise ImportError("this doesn't look like an import from smolarith") from e1  # noqa: E501

    m = cls(args.w)
    if not isinstance(m, Elaboratable):
        raise ValueError(f"{cls} does not look like an Elaboratable")

    stats(m, script)
