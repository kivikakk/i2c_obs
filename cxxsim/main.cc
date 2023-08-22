#include <fstream>
#include <iostream>

#include <backends/cxxrtl/cxxrtl_vcd.h>
#include <build/i2c_obs.cc>

using namespace cxxrtl_design;

int main(int argc, char **argv) {
  p_top top;
  debug_items di;
  top.debug_info(di);

  cxxrtl::vcd_writer vcd;
  vcd.add(di);

  uint64_t time;
  vcd.sample(time++);

  //

  top.p_scl__i.set(true);
  top.p_clk.set(true);
  top.step();
  vcd.sample(time++);

  top.p_clk.set(false);
  top.step();
  vcd.sample(time++);

  //

  top.p_switch.set(true);
  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  //

  top.p_switch.set(false);
  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  //

  top.p_scl__i.set(false);
  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  //

  for (int i = 0; i < 4 * 2; ++i) {
    top.p_clk.set(!top.p_clk);
    top.step();
    vcd.sample(time++);
  }

  //

  top.p_scl__i.set(true);
  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  top.p_clk.set(!top.p_clk);
  top.step();
  vcd.sample(time++);

  {
    std::ofstream of("cxxsim.vcd");
    of << vcd.buffer;
  }

  return 0;
}
