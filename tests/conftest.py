import pytest

from amaranth.sim import Simulator


def pytest_addoption(parser):
    parser.addoption(
        "--vcds",
        action="store_true",
        help="generate Value Change Dump (vcds) from simulations",
    )


class SimulatorFixture:
    def __init__(self, req, cfg):
        self.mod = req.node.get_closest_marker("module").args[0]
        # TODO: Perhaps parse node.nodeid instead?
        self.name = req.node.name + "-" + req.module.__name__
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
