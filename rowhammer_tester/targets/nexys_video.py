#!/user/bin/env python3

from migen import *

from litex_boards.platforms import digilent_nexys_video
from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock import S7PLL, S7IDELAYCTRL

from litedram.phy import s7ddrphy

# TODO: Verify that this is the correct ethernet PHY.
from liteeth.phy.s7rgmii import LiteEthPHYRGMII

from rowhammer_tester.targets import common


# CRG ----------------------------------------------------------------------------------------------

class CRG(Module):
   def __init__(self, platform, sys_clk_freq):
        # TODO: What is speedgrade and does it apply here?
        self.submodules.pll = pll = S7PLL()
        self.comb += pll.reset.eq(~platform.request("cpu_reset"))
        pll.register_clkin(platform.request("clk100"), 100e6)

        self.clock_domains.cd_sys = ClockDomain()
        pll.create_clkout(self.cd_sys, sys_clk_freq)

        # Etherbone --------------------------------------------------------------------------------
        # TODO: Double check that this is correct.
        # self.clock_domains.cd_eth = ClockDomain()
        # pll.create_clkout(self.cd_eth, 25e6)
        # self.comb += platform.request("eth_ref_clk").eq(self.cd_eth.clk)

        # DDRPHY -----------------------------------------------------------------------------------
        # TODO: Double check that this is correct.
        self.clock_domains.cd_sys4x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)

        pll.create_clkout(self.cd_sys4x,     4*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)

        self.clock_domains.cd_clk200 = ClockDomain()
        pll.create_clkout(self.cd_clk200, 200e6)
        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

# SoC ----------------------------------------------------------------------------------------------
class SoC(common.RowHammerSoC):
    def __init__(self, toolchain="vivado", **kwargs):
        self.toolchain = toolchain
        super().__init__(**kwargs)

    def get_platform(self):
        return digilent_nexys_video.Platform(toolchain=self.toolchain)

    def get_crg(self):
        return CRG(self.platform, self.sys_clk_freq)

    def get_ddrphy(self):
        return s7ddrphy.A7DDRPHY(
            self.platform.request("ddram"),
            memtype = "DDR3",
            nphases = 4,
            sys_clk_freq = self.sys_clk_freq
        )

    def get_sdram_ratio(self):
        return "1:4"

    def add_host_bridge(self):
        self.submodules.ethphy = LiteEthPHYRGMII(
            clock_pads = self.platform.request("eth_clocks"),
            pads = self.platform.request("eth")
        )
        self.add_csr("ethphy")
        self.add_etherbone(
            phy         = self.ethphy,
            ip_address  = self.ip_address,
            mac_address = self.mac_address,
            udp_port    = self.udp_port,
            buffer_depth=256)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = common.ArgumentParser(
        description     = "LiteX SoC on Nexys Video",
        sys_clk_freq    = "100e6",
        module          = "MT41K256M16",
    )
    g = parser.add_argument_group(title="Nexys Video")
    parser.add(g, "--toolchain", default="vivado", choices=['vivado', 'symbiflow'],
        help="Gateware toolchain to use")
    vivado_build_args(g)
    args = parser.parse_args()

    soc_kwargs = common.get_soc_kwargs(args)
    soc = SoC(toolchain=args.toolchain, **soc_kwargs)

    target_name = 'nexys_video'
    builder_kwargs = common.get_builder_kwargs(args, target_name=target_name)
    builder = Builder(soc, **builder_kwargs)
    build_kwargs = vivado_build_argdict(args) if not args.sim else {}

    common.run(args, builder, build_kwargs, target_name=target_name)

if __name__ == "__main__":
    main()
