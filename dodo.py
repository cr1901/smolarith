# ruff: noqa: D100, D101, D103

import importlib
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
${quiet} synth_ice40
stat -json
""")


def find_module_create_verilog(module, width):
    mod_name, cls_name = module.split(":")
    cls = getattr(importlib.import_module(mod_name), cls_name)  # noqa: E501

    m = cls(width)
    if not isinstance(m, Elaboratable):
        raise ValueError(f"{cls} does not look like an Elaboratable")
    
    v = convert(m)
    return { "verilog": v }


def run_yosys(v_file):
    stdin = ICE40_SCRIPT.substitute(verilog_text=v_file, quiet="tee -q")
    p = subprocess.Popen(["yosys", "-Q", "-T", "-"],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         encoding="utf-8")

    stdout, stderr = p.communicate(stdin)
    if p.returncode:
        raise subprocess.SubprocessError
    
    return { "stdout": stdout }


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
                "help": "module input port width"
            }
        ],
        "actions": [(find_module_create_verilog,)],
    }


def task_run_yosys():
    return {
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
