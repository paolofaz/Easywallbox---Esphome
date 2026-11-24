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
offline_match = re.search(
    r"// SESSION_OFFLINE_BEGIN[^\n]*\n(.*?)\n\s*// SESSION_OFFLINE_END",
    yaml, re.S,
)
assert offline_match, "Missing offline fallback markers"
offline_core = offline_match.group(1)
source = r'''
#include <array>
#include <cstdint>
#include <cassert>
#include <iostream>
std::array<int32_t, 5> session_accumulator{0,0,-1,-1,0};
bool session_unplug_pending=false, session_offline_pending=false;
bool ad_stale=true;
struct Link { bool state=false; } wallbox_connected;
struct Sensor { float state=0; void publish_state(float v){state=v;} };
Sensor wallbox_session_kwh, wallbox_charge_minutes;
uint32_t session_offline_since_ms=0;
uint32_t session_unplug_since_ms=0, session_unplug_last_ms=0, clock_ms=0;
#define ESP_LOGW(...) ((void)0)
uint32_t millis(){return clock_ms;}
#define id(x) (x)
void frame(uint32_t time, int32_t session_status,
           int32_t raw_energy, int32_t raw_minutes){
clock_ms=time;
ad_stale=false;
wallbox_connected.state=true;
''' + core + r'''
}
void tick(uint32_t time){
clock_ms=time;
''' + offline_core + r'''
}
void lose_ble(){
  wallbox_connected.state=false;
  ad_stale=true;
  session_unplug_pending=false;
}
void expect(int e,int m,int active){
  assert(session_accumulator[0]==e);
  assert(session_accumulator[1]==m);
  assert((session_accumulator[4]!=0)==(active!=0));
}
void clear(){
  session_accumulator={0,0,-1,-1,0};
  session_unplug_pending=false;
  session_offline_pending=false;
  ad_stale=true;
  wallbox_connected.state=false;
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
 // Physical unplug, then power off before the 60-second AD confirmation.
 clear();frame(0,3,0,0);frame(30000,8,50,90);
 frame(60000,3,50,0);assert(session_accumulator[4]==2);
 lose_ble();tick(65000);tick(364999);expect(50,90,1);
 tick(365000);expect(0,0,0);
 assert(wallbox_session_kwh.state==0 && wallbox_charge_minutes.state==0);
 tick(700000);expect(0,0,0);
 // No unplug was seen: even hours offline never erase a connected session.
 clear();frame(0,3,0,0);frame(30000,8,12,20);
 lose_ble();tick(35000);tick(400000);tick(3600000);expect(12,20,1);
 // Reconnect before fallback timeout, with the car plugged again.
 frame(3630000,8,14,22);frame(3660000,3,14,0);
 lose_ble();tick(3665000);frame(3800000,6,14,0);tick(4000000);
 expect(14,22,1);assert(session_accumulator[4]==1);
 // Error or unknown AD cannot keep a previous unplug as evidence.
 frame(4030000,3,14,0);frame(4060000,12,14,0);
 lose_ble();tick(4065000);tick(4400000);expect(14,22,1);
 // Reboot preserves unplug evidence but restarts the full offline timer.
 frame(4430000,3,14,0);checkpoint=session_accumulator;clear();
 session_accumulator=checkpoint;tick(5000);tick(304999);expect(14,22,1);
 tick(305000);expect(0,0,0);
 // Authenticated BLE without valid AD is still unavailable telemetry.
 clear();frame(0,3,0,0);frame(30000,8,10,20);frame(60000,3,10,0);
 session_unplug_pending=false;ad_stale=true;
 tick(165000);tick(465000);expect(0,0,0);
 // Offline timer rollover is safe.
 clear();frame(0,3,0,0);frame(30000,8,10,20);frame(60000,3,10,0);
 lose_ble();tick(0xfffffff0u);tick(299983);expect(10,20,1);
 tick(299984);expect(0,0,0);
 std::cout<<"Session accumulator and offline fallback scenarios passed\n";
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
