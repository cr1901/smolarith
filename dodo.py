# ruff: noqa: D100, D101, D103

import importlib
import inspect
from amaranth import Elaboratable
from amaranth.back.verilog import convert

import subprocess
from string import Template
from io import StringIO
import json


ICE40_SCRIPT = Template("""
${quiet} read_verilog << verilog
${verilog_text}
verilog
${quiet} synth_ice40 -run ${from_}:${to} ${extra}
${emit}
""")


def find_module_create_verilog(module, width):
    mod_name, cls_name = module.split(":")
    cls = getattr(importlib.import_module(mod_name), cls_name)  # noqa: E501

    p = inspect.signature(cls.__init__).parameters
    kwargs = dict()
    if "width" in p:
        kwargs["width"] = width

    m = cls(**kwargs)
    if not isinstance(m, Elaboratable):
        raise ValueError(f"{cls} does not look like an Elaboratable")
    
    v = convert(m)
    return { "verilog": v }


def run_yosys(v_file, from_="begin", to="blif", emit="stat -json", extra=""):
    stdin = ICE40_SCRIPT.substitute(verilog_text=v_file, quiet="tee -q",
                                    from_=from_, to=to, emit=emit,
                                    extra=extra)
    p = subprocess.Popen(["yosys", "-Q", "-T", "-"],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         encoding="utf-8")

    stdout, stderr = p.communicate(stdin)
    if p.returncode:
        raise subprocess.SubprocessError
    
    return { "stdout": stdout }


def print_verilog(v_file, preprocess="none", extra=""):
    if preprocess in ("none",):
        # No point in invoking yosys for a no-op.
        print(v_file)
    else:
        if preprocess == "coarse":
            to = "map_gates"
        elif preprocess == "fine":
            to = "map_ffs"
        else:
            to = ""

        raw_out = run_yosys(v_file, to=to,
                            emit="tee -q write_verilog -",
                            extra=extra)["stdout"]
        
        for i, line in enumerate(StringIO(raw_out).readlines()):
            if line[0:2] == "/*":
                break

        # Restart read since we can't really put back a line...
        stdout = StringIO(raw_out)
        stdout.readlines(i)  # Drain yosys stdout.

        rest = stdout.read()
        print(rest)


def print_stats(raw_stats):
    # Find the start of the JSON from the stats command.
    for i, line in enumerate(StringIO(raw_stats).readlines()):
        if line[0] == "{":
            break

    # Restart read since we can't really put back a line...
    stdout = StringIO(raw_stats)
    stdout.readlines(i)  # Drain non-JSON lines.
    
    print(json.dumps(json.load(stdout), indent=4))


def task_find_module():
    return {
        "params": [
            {
                "name": "module",
                "short": "m",
                "type": str,
                "default": None,
                "help": "smolarith module to test"
            },
            {
                "name": "width",
                "short": "w",
                "type": int,
                "default": -1,
                "help": "module input port width (if present)"
            },
        ],
        "actions": [(find_module_create_verilog,)],
    }


def task_emit_verilog():
    return {
        "params": [
            {
                "name": "preprocess",
                "short": "p",
                "type": str,
                "choices": (("none", ""),
                            ("coarse", "to map_gates"),
                            ("fine", "to map_ffs"),
                            ("all", "")),
                "default": "none",
                "help": "yosys preprocessing for Amaranth output"
            },
            {
                "name": "extra",
                "short": "e",
                "type": str,
                "default": "",
                "help": "extra args for yosys synthesis pass"
            }
        ],
        "uptodate": [False],
        "actions": [(print_verilog, (), {})],
        "getargs": { "v_file": ("find_module", "verilog") },
        "verbosity": 2
    }


def task_run_yosys():
    return {
        "params": [
            {
                "name": "extra",
                "short": "e",
                "type": str,
                "default": "",
                "help": "extra args for yosys synthesis pass"
            }
        ],
        "uptodate": [False],
        "actions": [(run_yosys, (), {})],
        "getargs": { "v_file": ("find_module", "verilog") },
    }


def task_stats():
    return {
        "uptodate": [False],
        "actions": [(print_stats, (), {})],
        "getargs": { "raw_stats": ("run_yosys", "stdout") },
        "verbosity": 2
    }
