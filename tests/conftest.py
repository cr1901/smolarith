import pytest

from amaranth.sim import Simulator


def pytest_addoption(parser):
    parser.addoption(
        "--vcds",
        action="store_true",
        help="generate Value Change Dump (vcds) from simulations",
    )
    parser.addini(
        "long_vcd_filenames",
        type="bool",
        default=False,
        help="if set, vcd files get longer, but less ambiguous, filenames"
    )


class SimulatorFixture:
    def __init__(self, req, cfg):
        mod = req.node.get_closest_marker("module").args[0]

        if hasattr(req, "param"):
            args, kwargs = req.param
            self.mod = mod(*args, **kwargs)
        else:
            self.mod = mod

        if cfg.getini("long_vcd_filenames"):
            self.name = req.node.name + "-" + req.module.__name__
        else:
            self.name = req.node.name

        self.sim = Simulator(self.mod)
        self.vcds = cfg.getoption("vcds")

        for clk in req.node.get_closest_marker("clks").args[0]:
            self.sim.add_clock(clk)

    def run(self, testbenches=[], sync_processes=[], comb_processes=[]):
        for t in testbenches:
            self.sim.add_testbench(t)

        for s in sync_processes:
            self.sim.add_process(s)

        for p in comb_processes:
            self.sim.add_process(p)

        if self.vcds:
            with self.sim.write_vcd(self.name + ".vcd", self.name + ".gtkw"):
                self.sim.run()
        else:
            self.sim.run()


@pytest.fixture
def sim_mod(request, pytestconfig):
    simfix = SimulatorFixture(request, pytestconfig)
    return (simfix, simfix.mod)
