#include <fstream>
#include <iostream>

#include <backends/cxxrtl/cxxrtl_vcd.h>
#include <build/i2c_obs.cc>

using namespace cxxrtl_design;

int main(int argc, char **argv) {
  p_top top;
  debug_items di;
  top.debug_info(di);

  bool do_vcd = argc >= 2 && std::string(argv[1]) == "--vcd";
  cxxrtl::vcd_writer vcd;
  if (do_vcd)
    vcd.add(di);

  uint64_t time;
  vcd.sample(time++);

  for (; time < 80;) {
    if (time % 5 == 0) {
      top.p_scl__i.set(!top.p_scl__i);
    }

    switch (time >> 1) {
    case 1:
      top.p_switch.set(true);
      break;
    case 2:
      top.p_switch.set(false);
      break;
    }

    top.p_clk.set(!top.p_clk);
    top.step();
    vcd.sample(time++);

    top.p_clk.set(!top.p_clk);
    top.step();
    vcd.sample(time++);
  }

  if (do_vcd) {
    std::ofstream of("cxxsim.vcd");
    of << vcd.buffer;
  }

  return 0;
}
