from machine import ADC, Pin
import time

# ADC-Pin definieren (GP28 = ADC2)
ldr = ADC(Pin(28))

def read_light():
    raw = ldr.read_u16()  # 0 bis 65535
    voltage = raw * 3.3 / 65535  # optional: umrechnen in Volt
    return raw, voltage

while True:
    value, volt = read_light()
    print("Lichtwert:", value, "→", round(volt, 2), "V")
    time.sleep(0.5)
