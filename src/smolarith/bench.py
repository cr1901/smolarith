import subprocess
import re

from amaranth.back import rtlil


class RunnerError(Exception):
    pass


def stats(m):
    raise NotImplementedError

    # if args.action == "size":
    # fragment = Fragment.get(design, platform)
    # rtlil_text = rtlil.convert(fragment, name=name, ports=ports)
    rtlil_text = rtlil.convert(m, ports=[m.a, m.b, m.o])

    # Created from a combination of amaranth._toolchain.yosys and
    # amaranth.back.verilog. Script comes from nextpnr-generic.
    script = []
    script.append("read_ilang <<rtlil\n{}\nrtlil".format(rtlil_text))
    script.append("hierarchy -check")
    script.append("proc")
    script.append("flatten")
    script.append("tribuf -logic")
    script.append("deminout")
    script.append("synth -run coarse")
    script.append("memory_map")
    script.append("opt -full")
    script.append("techmap -map +/techmap.v")
    script.append("opt -fast")
    script.append("dfflegalize -cell $_DFF_P_ 0")
    script.append("abc -lut 4 -dress")
    script.append("clean -purge")
    # if args.show:
    script.append("show")
    script.append("hierarchy -check")
    script.append("stat")

    stdin = "\n".join(script)

    popen = subprocess.Popen(["yosys", "-"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             encoding="utf-8")
    stdout, stderr = popen.communicate(stdin)
    if popen.returncode:
        raise RunnerError(stderr.strip())

    # if args.verbose:
    #    print(stdout)
    # else:
    begin_re = re.compile(r"[\d.]+ Printing statistics.")
    end_re = re.compile(r"End of script.")
    capture = False
    # begin_l = 0
    # end_l = 0

    for i, l in enumerate(stdout.split("\n")):
        if begin_re.match(l):
            capture = True

        if end_re.match(l):
            capture = False

        if capture:
            print(l)
