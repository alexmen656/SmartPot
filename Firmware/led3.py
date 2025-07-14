import machine
import neopixel
import time

# Zuerst testen wir mit nur 1 LED
NUM_LEDS = 1
pin = machine.Pin(12)
np = neopixel.NeoPixel(pin, NUM_LEDS)

print("Testing with 1 LED first...")
np[0] = (255, 0, 0)  # Rot
np.write()
time.sleep(2)
np[0] = (0, 255, 0)  # Grün  
np.write()
time.sleep(2)
np[0] = (0, 0, 255)  # Blau
np.write()
time.sleep(2)
np[0] = (0, 0, 0)    # Aus
np.write()

print("Now testing with more LEDs...")
# Jetzt schrittweise mehr LEDs testen
for num_test in [2, 3, 4, 8]:
    print(f"Testing with {num_test} LEDs")
    np = neopixel.NeoPixel(pin, num_test)
    
    # Alle LEDs nacheinander rot anmachen
    for i in range(num_test):
        # Alle aus
        for j in range(num_test):
            np[j] = (0, 0, 0)
        # Eine an
        np[i] = (50, 0, 0)  # Schwaches Rot
        np.write()
        print(f"  LED {i} should be on")
        time.sleep(1)
    
    # Alle aus für nächsten Test
    for j in range(num_test):
        np[j] = (0, 0, 0)
    np.write()
    time.sleep(1)
