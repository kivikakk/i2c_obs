# i2c_obs

I²C, oh! Big stretch.

## Usage

The only board this is configured to run with right now is the iCEBreaker, but
it only needs a single GPIO to interface with the I²C bus clock and a button to
toggle stretching on and off, so it's easy to add support.

It can optionally write diagnostic information to UART.  The iCEBreaker channels
its UART over USB, but you could also just put it on a GPIO and use your own
FTDI cable.

* Connect PMOD1A1 to I²C SCL.
* Optional: run `py -m i2c_obs debugger` to monitor.
* Press the button.
* (The debugger will report the measured bus speed.)
* The bus is streeeeeeetched.
* Press the button to stop.

## Notes

* I've templated this from [sh1107](https://github.com/charlottia/sh1107), so
  maybe the repo in the state it is as of this line being written is a good
  source for an actual template/common base, future me?
