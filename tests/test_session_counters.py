"""Compile the real YAML accumulator in a host C++ harness (no ESP32 needed).

Run from any directory: python3 tests/test_session_counters.py
Requires g++ (C++17). This does NOT replace ESPHome validation/compilation.
"""
from pathlib import Path
import re
import subprocess
import tempfile

yaml = (Path(__file__).resolve().parents[1] / "wallbox.yaml").read_text()
match = re.search(
    r"// SESSION_COUNTERS_BEGIN[^\n]*\n(.*?)\n\s*// SESSION_COUNTERS_END",
    yaml, re.S,
)
assert match, "Missing session accumulator markers"
core = match.group(1).replace("${poll_interval_s}", "30").replace(
    "${telemetry_stale_s}", "100"
)
source = r'''
#include <array>
#include <cstdint>
#include <cassert>
#include <iostream>
std::array<int32_t, 5> session_accumulator{0,0,-1,-1,0};
bool session_unplug_pending=false;
uint32_t session_unplug_since_ms=0, session_unplug_last_ms=0, clock_ms=0;
uint32_t millis(){return clock_ms;}
#define id(x) (x)
void frame(uint32_t time, int32_t session_status,
           int32_t raw_energy, int32_t raw_minutes){
clock_ms=time;
''' + core + r'''
}
void expect(int e,int m,int active){
  assert(session_accumulator[0]==e);
  assert(session_accumulator[1]==m);
  assert(session_accumulator[4]==active);
}
void clear(){
  session_accumulator={0,0,-1,-1,0};
  session_unplug_pending=false;
}
int main(){
 // Retained raw energy before plug, followed by independent increments.
 clear();frame(0,3,100,0);frame(30000,6,100,0);expect(0,0,1);
 frame(60000,8,0,0);frame(90000,8,50,90);expect(50,90,1);
 // Only duration resets during a pause.
 frame(120000,5,50,0);frame(150000,8,70,40);expect(70,130,1);
 // Only energy resets; its first post-reset value is already positive.
 frame(180000,5,2,40);frame(210000,8,12,50);expect(82,140,1);
 // Both reset, and a duplicate AD frame must add nothing.
 frame(240000,5,0,0);frame(270000,8,5,10);frame(280000,8,5,10);expect(87,150,1);
 // Immediate duration reset at unplug, energy retained.
 frame(300000,3,5,0);frame(330000,3,5,0);expect(87,150,1);
 // Replug inside the 60-second window.
 frame(350000,6,0,0);frame(380000,8,6,10);expect(93,160,1);
 // BLE loss invalidates the timer, but retains totals.
 frame(410000,3,6,0);session_unplug_pending=false;
 frame(490000,3,6,0);frame(520000,3,6,0);expect(93,160,1);
 frame(550000,3,6,0);expect(0,0,0);
 // The next car cannot inherit the old retained energy.
 frame(580000,6,6,0);frame(610000,8,0,0);frame(640000,8,3,4);expect(3,4,1);
 // Restore the same checkpoint after reboot; only new deltas count.
 auto checkpoint=session_accumulator;clear();session_accumulator=checkpoint;
 frame(0,8,3,4);expect(3,4,1);frame(30000,8,5,7);expect(5,7,1);
 // Invalid energy ignored; error/unknown cannot prove cable unplugged.
 frame(60000,8,-1,8);expect(5,8,1);frame(90000,12,0,0);expect(5,8,1);
 frame(120000,3,5,0);frame(150000,12,0,0);frame(180000,3,5,0);expect(5,8,1);
 // A missing AD beyond the permitted gap restarts unplug evidence.
 frame(250000,3,5,0);frame(280000,3,5,0);expect(5,8,1);
 frame(310000,3,5,0);expect(0,0,0);
 // millis rollover is safe.
 clear();frame(0,3,0,0);frame(1000,8,10,20);frame(0xfffffff0u,3,10,0);
 frame(29984,3,10,0);expect(10,20,1);frame(59984,3,10,0);expect(0,0,0);
 // First installation during an ongoing charge: unknown earlier energy
 // must not be attributed to the session without a raw baseline.
 clear();frame(0,8,100,200);expect(0,0,1);frame(30000,8,103,201);expect(3,1,1);
 std::cout<<"Session accumulator scenarios passed\n";
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    (p / "test.cpp").write_text(source)
    subprocess.run(
        ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
         str(p / "test.cpp"), "-o", str(p / "test")],
        check=True,
    )
    subprocess.run([str(p / "test")], check=True)
