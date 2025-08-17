import random, subprocess, time, serial
import psutil

def get_voltage():
    try:
        import Adafruit_ADS1x15
        adc = Adafruit_ADS1x15.ADS1115()
        GAIN = 1
        val = adc.read_adc(0, gain=GAIN)
        voltage = val * (4.096 / 32767) * 2
        return round(voltage, 2)
    except Exception as e:
        print("Voltage read error:", e)
        return round(random.uniform(4.5, 5.2), 2)

def get_temp_c():
    """Read Raspberry Pi CPU temperature in °C with fallback."""
    try:
        out = subprocess.check_output(["/usr/bin/vcgencmd", "measure_temp"]).decode()
        return float(out.split('=')[1].split("'")[0])
    except Exception as e:
        print(f"[fan] Error reading vcgencmd: {e}. Trying sysfs...", flush=True)
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception as e2:
            print(f"[fan] Error reading sysfs temp: {e2}", flush=True)
            return 0.0

def _fan_loop(port: str, baud: int, temp_on: float, temp_off: float):
    while True:
        try:
            print(f"[fan] Opening serial on {port}...", flush=True)
            with serial.Serial(port, baud, timeout=1) as ser:
                print("[fan] Serial port opened successfully", flush=True)
                fan_on = False
                while True:
                    t = get_temp_c()
                    print(f"[fan] loop, T={t:.1f}", flush=True)
                    if t >= temp_on:
                        ser.write(b"ON 200\n")  
                        if not fan_on:
                            fan_on = True
                            print(f"[fan] Fan ON (T={t:.1f}°C)", flush=True)
                    elif t < temp_off and fan_on:
                        ser.write(b"OFF\n")
                        fan_on = False
                        print(f"[fan] Fan OFF (T={t:.1f}°C)", flush=True)
                    time.sleep(2)
        except Exception as e:
            print(f"[fan] Serial error: {e}, retrying in 3s", flush=True)
            time.sleep(3)

def start_fan_thread(port="/dev/ttyACM0", baud=115200, temp_on=50.0, temp_off=45.0):
    import threading
    th = threading.Thread(target=_fan_loop, args=(port, baud, temp_on, temp_off), daemon=True)
    th.start()
