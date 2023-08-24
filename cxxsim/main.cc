#include <fstream>
#include <iostream>

#include <backends/cxxrtl/cxxrtl_vcd.h>
#include <build/i2c_obs.cc>

using namespace cxxrtl_design;

void cycle(p_top &top, cxxrtl::vcd_writer &vcd, uint64_t &vcd_time) {
  assert(!top.p_clk);
  top.p_clk.set(true);
  top.step();
  vcd.sample(vcd_time++);

  top.p_clk.set(false);
  top.step();
  vcd.sample(vcd_time++);
}

int main(int argc, char **argv) {
  int ret = 0;
  p_top top;
  debug_items di;
  top.debug_info(di);

  bool do_vcd = argc >= 2 && std::string(argv[1]) == "--vcd";
  cxxrtl::vcd_writer vcd;
  uint64_t vcd_time;
  if (do_vcd)
    vcd.add(di);

  top.p_scl__i.set(true);
  cycle(top, vcd, vcd_time);

  top.p_switch.set(true);
  cycle(top, vcd, vcd_time);

  top.p_switch.set(false);

  const std::vector<int> STRETCHES = {0, 0, 3, 3};

  int stretch_ix = 0;
  for (auto expected : STRETCHES) {
    top.p_scl__i.set(false);
    cycle(top, vcd, vcd_time);
    cycle(top, vcd, vcd_time);
    cycle(top, vcd, vcd_time);

    top.p_scl__i.set(true);
    int actual = 0;
    while (top.p_scl__oe) {
      actual += 1;
      cycle(top, vcd, vcd_time);
    }
    if (actual != expected) {
      std::cerr << "ix " << stretch_ix << " expected " << expected
                << " stretched cycles, got " << actual << std::endl;
      ret = 1;
    }
    cycle(top, vcd, vcd_time);
    cycle(top, vcd, vcd_time);
    cycle(top, vcd, vcd_time);
  }

  if (do_vcd) {
    std::ofstream of("cxxsim.vcd");
    of << vcd.buffer;
  }

  return ret;
}
