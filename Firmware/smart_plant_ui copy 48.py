import machine
import time
from micropython import const
import ustruct as struct
import math
import dht  # DHT11/DHT22 Sensor Support
from machine import I2S, Pin
import array

# ILI9341 commands und Setup (vereinfacht)
ILI9341_SWRESET = const(0x01)
ILI9341_SLPOUT = const(0x11)
ILI9341_DISPON = const(0x29)
ILI9341_CASET = const(0x2A)
ILI9341_PASET = const(0x2B)
ILI9341_RAMWR = const(0x2C)
ILI9341_MADCTL = const(0x36)
ILI9341_PIXFMT = const(0x3A)
ILI9341_PWCTR1 = const(0xC0)
ILI9341_PWCTR2 = const(0xC1)
ILI9341_VMCTR1 = const(0xC5)
ILI9341_VMCTR2 = const(0xC7)
ILI9341_FRMCTR1 = const(0xB1)
ILI9341_DFUNCTR = const(0xB6)
ILI9341_GAMMASET = const(0x26)
ILI9341_GMCTRP1 = const(0xE0)
ILI9341_GMCTRN1 = const(0xE1)

MADCTL_MX = const(0x40)
MADCTL_BGR = const(0x08)

# Farbpalette für Pflanzentopf UI
GREEN_LIGHT = const(0x87E0)    # Helles Grün
GREEN_DARK = const(0x0400)     # Dunkles Grün  
BLUE_LIGHT = const(0x3D7F)     # Hellblau für Wasser
BLUE_DARK = const(0x001F)      # Dunkelblau
ORANGE = const(0xFD20)         # Orange für Temperatur
RED = const(0xF800)            # Rot für Warnung
YELLOW = const(0xFFE0)         # Gelb für Sonne
WHITE = const(0xFFFF)
BLACK = const(0x0000)
GRAY_LIGHT = const(0xCE79)     # Hellgrau
GRAY_DARK = const(0x7BEF)      # Dunkelgrau
BROWN = const(0x8200)          # Braun für Erde

# Touch Controller Commands (XPT2046/ADS7843)
TOUCH_CMD_X = const(0x90)  # X position
TOUCH_CMD_Y = const(0xD0)  # Y position

def delay_ms(ms):
    time.sleep_ms(ms)

def color565(r, g=0, b=0):
    """Convert RGB to 565 format"""
    try:
        r, g, b = r
    except TypeError:
        pass
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3

class TouchController:
    def __init__(self, spi, cs, irq):
        self.spi = spi
        self.cs = cs
        self.irq = irq
        self.cs.on()  # CS high (inactive)
        
        # Kalibrierungswerte (müssen eventuell angepasst werden)
        self.cal_x_min = 200
        self.cal_x_max = 3800
        self.cal_y_min = 200
        self.cal_y_max = 3800
        
        # Touch-Controller testen
        self.test_connection()
        
    def test_connection(self):
        """Testet die Verbindung zum Touch-Controller"""
        print("Teste Touch-Controller Verbindung...")
        
        # IRQ Pin testen
        irq_state = self.irq.value()
        print(f"IRQ Pin Status: {irq_state} (1=kein Touch, 0=Touch erkannt)")
        
        # Teste SPI-Kommunikation
        try:
            test_x = self.read_touch_raw(TOUCH_CMD_X)
            test_y = self.read_touch_raw(TOUCH_CMD_Y)
            print(f"Touch Test-Werte: X={test_x}, Y={test_y}")
            
            if test_x == 0 and test_y == 0:
                print("⚠️  Touch-Controller antwortet nicht korrekt")
            else:
                print("✅ Touch-Controller antwortet")
                
        except Exception as e:
            print(f"❌ Touch-Controller Fehler: {e}")
        
    def read_touch_raw(self, cmd):
        """Liest rohe Touch-Daten"""
        self.cs.off()
        delay_ms(1)  # Kleine Verzögerung für stabilen CS
        
        # Sende Kommando
        self.spi.write(bytes([cmd]))
        
        # Warte kurz und lese 2 Bytes
        delay_ms(1)
        result = self.spi.read(2)
        
        delay_ms(1)  # Kleine Verzögerung vor CS high
        self.cs.on()
        
        if len(result) == 2:
            # Korrekte 12-bit Auflösung (ADS7843/XPT2046)
            value = (result[0] << 8 | result[1]) >> 3
            return value & 0x0FFF  # 12-bit Maske
        return 0
    
    def get_touch(self):
        """Gibt Touch-Position zurück oder None falls kein Touch"""
        # Debug: IRQ Status prüfen
        irq_state = self.irq.value()
        
        if irq_state == 1:  # Kein Touch (IRQ ist HIGH wenn nicht gedrückt)
            return None
            
        # Mehrere Messungen für Stabilität
        x_sum = y_sum = 0
        valid_readings = 0
        
        for i in range(3):  # Weniger Messungen für bessere Performance
            x_raw = self.read_touch_raw(TOUCH_CMD_X)
            y_raw = self.read_touch_raw(TOUCH_CMD_Y)
            
            # Debug-Ausgabe für erste Messung
            if i == 0:
                print(f"Touch raw: X={x_raw}, Y={y_raw}, IRQ={irq_state}")
            
            if x_raw > 100 and y_raw > 100 and x_raw < 4000 and y_raw < 4000:  # Gültige Werte
                x_sum += x_raw
                y_sum += y_raw
                valid_readings += 1
                
        if valid_readings == 0:
            print("Keine gültigen Touch-Messungen")
            return None
            
        # Durchschnitt berechnen
        x_avg = x_sum // valid_readings
        y_avg = y_sum // valid_readings
        
        # In Bildschirmkoordinaten umwandeln
        x = int((x_avg - self.cal_x_min) * 320 / (self.cal_x_max - self.cal_x_min))
        y = int((y_avg - self.cal_y_min) * 240 / (self.cal_y_max - self.cal_y_min))
        
        # Touch-Koordinaten für 180° gedrehtes Display anpassen
        # Keine zusätzliche Spiegelung nötig, da Display bereits gedreht ist
        
        # Grenzen prüfen
        x = max(0, min(319, x))
        y = max(0, min(239, y))
        
        print(f"Touch calculated: X={x}, Y={y} (raw avg: {x_avg}, {y_avg})")
        return (x, y)

class SmartPlantDisplay:
    def __init__(self, spi, dc, reset, cs=None, touch=None):
        self.spi = spi
        self.dc = dc
        self.reset = reset
        self.cs = cs
        self.touch = touch
        self.width = 320
        self.height = 240
        self.current_screen = 0
        self.last_update = 0
        self.last_touch_time = 0
        self.manual_mode = False  # Touch-Steuerung aktiviert Auto-Wechsel aus
        self.last_drawn_screen = -1  # Merkt sich welcher Screen zuletzt gezeichnet wurde
        self.screen_needs_redraw = True  # Flag ob Screen neu gezeichnet werden muss
        self.last_light_value = 0  # Letzter Lichtwert für Change-Detection
        self.data_needs_update = False  # Flag nur für Daten-Updates ohne komplettes Redraw
        
        # Motion-Sensor Tracking
        self.last_motion_time = 0  # Zeitpunkt der letzten Motion
        self.motion_timeout = 30000  # 30 Sekunden in Millisekunden (einstellbar)
        self.motion_timeout_seconds = 30  # Sekunden für UI-Anzeige (einstellbar)
        self.last_motion_check = 0  # Letzter Check-Zeitpunkt
        self.audio_played = False  # Flag ob Audio bereits abgespielt wurde
        self.reward_played = False  # Flag ob Belohnungs-Sound bereits abgespielt wurde
        
        # I2S Audio-System für Bestrafung
        self.i2s = None
        self.setup_audio_system()
        
        # Letzte angezeigte Werte für Update-Detection
        self.last_displayed_values = {
            'light': 0,
            'temperature': 0,
            'humidity': 0,
            'plant_health': 0
        }
        
        # Sensoren initialisieren
        self.light_sensor = machine.ADC(machine.Pin(28))  # GP28 = ADC2 (Lichtsensor)
        self.dht_sensor = dht.DHT11(machine.Pin(27))  # GP26 = DHT11 Temp/Feuchtigkeit Sensor
        self.motion_pin = machine.Pin(26, machine.Pin.IN)  # GP27 = Motion Sensor
        
        # Motion-Sensor beim Start initialisieren
        current_time = time.ticks_ms()
        self.last_motion_time = current_time  # Starte mit "gerade Motion erkannt"
        print(f"Motion-Sensor initialisiert - {self.motion_timeout_seconds}s Timer gestartet")
        
        # Simulierte Sensordaten
        self.sensor_data = {
            'temperature': 22.5,
            'humidity': 65,
            'light': 750,
            'light_voltage': 1.65,  # Lichtsensor Spannung
            'light_raw': 32767,     # Roher ADC-Wert
            'water_level': 80,
            'plant_health': 85
        }

    # Display Grundfunktionen
    def dc_low(self):
        self.dc.off()

    def dc_high(self):
        self.dc.on()

    def cs_low(self):
        if self.cs:
            self.cs.off()

    def cs_high(self):
        if self.cs:
            self.cs.on()

    def write_cmd(self, cmd):
        self.cs_low()
        self.dc_low()
        self.spi.write(bytes([cmd]))
        self.cs_high()

    def write_data(self, data):
        self.cs_low()
        self.dc_high()
        if isinstance(data, int):
            self.spi.write(bytes([data]))
        else:
            self.spi.write(data)
        self.cs_high()

    def write_cmd_data(self, cmd, data=None):
        self.cs_low()
        self.dc_low()
        self.spi.write(bytes([cmd]))
        if data is not None:
            self.dc_high()
            if isinstance(data, int):
                self.spi.write(bytes([data]))
            else:
                self.spi.write(data)
        self.cs_high()

    def init(self):
        """Schnelle Initialisierung"""
        print("Initialisiere Display...")
        
        if self.reset:
            self.reset.off()
            delay_ms(100)
            self.reset.on()
            delay_ms(100)
        
        self.write_cmd(ILI9341_SWRESET)
        delay_ms(150)
        
        self.write_cmd(ILI9341_SLPOUT)
        delay_ms(120)
        
        # Basis-Konfiguration
        self.write_cmd_data(0xCB, bytes([0x39, 0x2C, 0x00, 0x34, 0x02]))
        self.write_cmd_data(0xCF, bytes([0x00, 0xC1, 0x30]))
        self.write_cmd_data(ILI9341_PWCTR1, 0x23)
        self.write_cmd_data(ILI9341_PWCTR2, 0x10)
        self.write_cmd_data(ILI9341_VMCTR1, bytes([0x3e, 0x28]))
        self.write_cmd_data(ILI9341_VMCTR2, 0x86)
        # Korrigierte Rotation: MY + BGR für richtige Ausrichtung (270° gedreht)
        self.write_cmd_data(ILI9341_MADCTL, 0x88)  # MY(0x80) | BGR(0x08) = 0x88
        self.write_cmd_data(ILI9341_PIXFMT, 0x55)
        self.write_cmd_data(ILI9341_FRMCTR1, bytes([0x00, 0x18]))
        
        self.write_cmd(ILI9341_DISPON)
        delay_ms(100)
        
        print("Display bereit!")

    def set_window(self, x0, y0, x1, y1):
        self.write_cmd_data(ILI9341_CASET, struct.pack(">HH", x0, x1))
        self.write_cmd_data(ILI9341_PASET, struct.pack(">HH", y0, y1))
        self.write_cmd(ILI9341_RAMWR)

    def fill_rect(self, x, y, w, h, color):
        if x + w > self.width:
            w = self.width - x
        if y + h > self.height:
            h = self.height - y
        
        self.set_window(x, y, x + w - 1, y + h - 1)
        pixel_data = struct.pack(">H", color)
        
        self.cs_low()
        self.dc_high()
        for _ in range(w * h):
            self.spi.write(pixel_data)
        self.cs_high()

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)

    def pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.set_window(x, y, x, y)
            self.write_data(struct.pack(">H", color))

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    # UI-spezifische Funktionen
    def draw_rounded_rect(self, x, y, w, h, radius, color):
        """Zeichnet ein abgerundetes Rechteck"""
        # Hauptrechteck
        self.fill_rect(x + radius, y, w - 2*radius, h, color)
        self.fill_rect(x, y + radius, radius, h - 2*radius, color)
        self.fill_rect(x + w - radius, y + radius, radius, h - 2*radius, color)
        
        # Ecken (vereinfacht)
        for i in range(radius):
            for j in range(radius):
                if i*i + j*j <= radius*radius:
                    self.pixel(x + radius - i, y + radius - j, color)
                    self.pixel(x + w - radius + i, y + radius - j, color)
                    self.pixel(x + radius - i, y + h - radius + j, color)
                    self.pixel(x + w - radius + i, y + h - radius + j, color)

    def draw_circle(self, cx, cy, radius, color):
        """Zeichnet einen Kreis"""
        for x in range(-radius, radius + 1):
            for y in range(-radius, radius + 1):
                if x*x + y*y <= radius*radius:
                    self.pixel(cx + x, cy + y, color)

    def draw_progress_bar(self, x, y, w, h, value, max_value, bg_color, fg_color):
        """Zeichnet einen Fortschrittsbalken"""
        # Hintergrund
        self.draw_rounded_rect(x, y, w, h, 3, bg_color)
        
        # Fortschritt
        progress_w = int((value / max_value) * (w - 4))
        if progress_w > 0:
            self.draw_rounded_rect(x + 2, y + 2, progress_w, h - 4, 2, fg_color)

    def draw_digit(self, x, y, digit, size, color):
        """Einfache 7-Segment-Anzeige für Zahlen"""
        segments = [
            [1,1,1,1,1,1,0], # 0
            [0,1,1,0,0,0,0], # 1
            [1,1,0,1,1,0,1], # 2
            [1,1,1,1,0,0,1], # 3
            [0,1,1,0,0,1,1], # 4
            [1,0,1,1,0,1,1], # 5
            [1,0,1,1,1,1,1], # 6
            [1,1,1,0,0,0,0], # 7
            [1,1,1,1,1,1,1], # 8
            [1,1,1,1,0,1,1]  # 9
        ]
        
        if 0 <= digit <= 9:
            seg = segments[digit]
            w = size * 6
            h = size * 10
            
            # Segment-Positionen (vereinfacht)
            if seg[0]: self.fill_rect(x+size, y, w-2*size, size, color)           # oben
            if seg[1]: self.fill_rect(x+w-size, y+size, size, h//2-size, color)  # rechts oben
            if seg[2]: self.fill_rect(x+w-size, y+h//2, size, h//2-size, color)  # rechts unten
            if seg[3]: self.fill_rect(x+size, y+h-size, w-2*size, size, color)   # unten
            if seg[4]: self.fill_rect(x, y+h//2, size, h//2-size, color)         # links unten
            if seg[5]: self.fill_rect(x, y+size, size, h//2-size, color)         # links oben
            if seg[6]: self.fill_rect(x+size, y+h//2-size//2, w-2*size, size, color) # mitte

    def draw_number(self, x, y, number, size, color):
        """Zeichnet eine mehrstellige Zahl"""
        num_str = str(int(number))
        digit_width = size * 8  # Etwas mehr Abstand zwischen Ziffern
        
        for i, digit_char in enumerate(num_str):
            digit = int(digit_char)
            digit_x = x + i * digit_width
            self.draw_digit(digit_x, y, digit, size, color)

    def draw_icon_plant(self, x, y, size, color):
        """Zeichnet ein Pflanzen-Icon"""
        # Stiel
        stem_x = x + size // 2
        self.vline(stem_x, y + size//3, size//2, GREEN_DARK)
        
        # Blätter
        self.draw_circle(x + size//4, y + size//4, size//6, color)
        self.draw_circle(x + 3*size//4, y + size//4, size//6, color)
        self.draw_circle(x + size//2, y + size//6, size//5, color)

    def draw_icon_water(self, x, y, size, color):
        """Zeichnet ein Wasser-Icon"""
        # Wassertropfen-Form (vereinfacht als Kreis)
        self.draw_circle(x + size//2, y + size//2, size//3, color)

    def draw_icon_temperature(self, x, y, size, color):
        """Zeichnet ein Temperatur-Icon"""
        # Thermometer (vereinfacht)
        therm_x = x + size//2
        self.vline(therm_x, y + size//4, size//2, color)
        self.draw_circle(therm_x, y + 3*size//4, size//8, color)

    def draw_icon_sun(self, x, y, size, color):
        """Zeichnet ein Sonnen-Icon"""
        center_x, center_y = x + size//2, y + size//2
        radius = size//4
        
        # Sonnenstrahlen
        for angle in range(0, 360, 45):
            angle_rad = angle * 3.14159 / 180
            x1 = center_x + int(radius * 1.5 * math.cos(angle_rad))
            y1 = center_y + int(radius * 1.5 * math.sin(angle_rad))
            x2 = center_x + int(radius * 2 * math.cos(angle_rad))
            y2 = center_y + int(radius * 2 * math.sin(angle_rad))
            
            # Einfache Linie (nur ein paar Pixel)
            for i in range(3):
                if 0 <= x1+i < self.width and 0 <= y1 < self.height:
                    self.pixel(x1+i, y1, color)
        
        # Sonne selbst
        self.draw_circle(center_x, center_y, radius, color)

    def read_light_sensor(self):
        """Liest den realen Lichtsensor (ADC)"""
        try:
            raw = self.light_sensor.read_u16()  # 0 bis 65535
            voltage = raw * 3.3 / 65535  # Umrechnen in Volt
            
            # Umrechnung in Lux-ähnliche Werte (0-1000)
            # Diese Kalibrierung muss eventuell angepasst werden
            light_value = int((raw / 65535) * 1000)
            
            return light_value, voltage, raw
        except Exception as e:
            print(f"Lichtsensor Fehler: {e}")
            return 500, 1.65, 32767  # Fallback-Werte

    def read_temp_humidity_sensor(self):
        """Liest den echten DHT11 Temperatur/Feuchtigkeitssensor (GP26)"""
        try:
            # DHT11 Sensor auslesen
            self.dht_sensor.measure()
            temperature = self.dht_sensor.temperature()  # Celsius
            humidity = self.dht_sensor.humidity()        # Prozent
            
            print(f"DHT11 - Temp: {temperature}°C, Humidity: {humidity}%")
            return temperature, humidity
            
        except OSError as e:
            print(f"DHT11 Sensor Fehler: {e} (Sensor nicht angeschlossen oder defekt?)")
            return None, None
        except Exception as e:
            print(f"DHT11 unbekannter Fehler: {e}")
            return None, None

    def read_motion_sensor(self):
        """Liest den Motion-Sensor (GP27) mit 30s Timeout und Audio-Bestrafung/Belohnung"""
        try:
            current_time = time.ticks_ms()
            motion_state = self.motion_pin.value()
            
            # Motion erkannt - BELOHNUNG!
            if motion_state == 1:
                self.last_motion_time = current_time
                self.audio_played = False  # Reset Audio-Flag bei neuer Motion
                
                # Belohnungs-Sound nur einmal pro Motion-Event abspielen
                if not self.reward_played:
                    print("✅ Motion detected - Gießen erkannt!")
                    self.play_reward_sound()
                    self.reward_played = True
                
                return True
            else:
                # Kein Motion mehr - Reset Belohnungs-Flag für nächstes Event
                self.reward_played = False
            
            # Prüfe Motion-Timeout (alle 5 Sekunden prüfen um nicht zu spammen)
            if time.ticks_diff(current_time, self.last_motion_check) > 5000:
                self.last_motion_check = current_time
                
                # Wenn länger als eingestellte Zeit keine Motion
                if time.ticks_diff(current_time, self.last_motion_time) > self.motion_timeout:
                    print(f"⚠️  Keine Motion seit {self.motion_timeout_seconds}+ Sekunden - BESTRAFUNG!")
                    
                    # Audio-Bestrafung nur einmal pro Timeout-Periode abspielen
                    if not self.audio_played:
                        self.play_punishment_sound()
                        self.audio_played = True
                        
            return False
            
        except Exception as e:
            print(f"Motion Sensor Fehler: {e}")
            return False

    def setup_audio_system(self):
        """Initialisiert das I2S Audio-System für die Bestrafung"""
        try:
            self.i2s = I2S(
                0,
                sck=Pin(10),    # BCLK
                ws=Pin(11),     # LRC / WS
                sd=Pin(12),     # DIN
                mode=I2S.TX,
                bits=16,
                format=I2S.MONO,
                rate=22050,
                ibuf=20000,
            )
            print("I2S Audio-System initialisiert (GP10=BCLK, GP11=WS, GP12=DIN)")
        except Exception as e:
            print(f"I2S Audio-System Fehler: {e}")
            self.i2s = None

    def play_punishment_sound(self):
        """Spielt Bestrafungs-Sound ab (5s Sinuswelle bei 3000 Hz)"""
        if not self.i2s:
            print("I2S nicht verfügbar - kein Sound")
            return
            
        try:
            print("🎵 BESTRAFUNG: Spiele Sinuswelle ab (5 Sekunden, 3000 Hz)")
            
            # Sinuswellen-Parameter
            sample_rate = 22050
            frequency = 3000  # Kammerton A
            amplitude = 32767  # max für 16-bit Audio
            duration = 5  # Sekunden
            samples_per_cycle = sample_rate // frequency

            # Erzeuge eine Sinuswelle
            sine_wave = array.array("h", [
                int(amplitude * math.sin(2 * math.pi * i / samples_per_cycle))
                for i in range(samples_per_cycle)
            ])

            # Wiederhole die Welle für die gewünschte Dauer
            num_cycles = int(sample_rate * duration // samples_per_cycle)
            for cycle in range(num_cycles):
                self.i2s.write(sine_wave)
                # Kurze Pause alle 50 Zyklen um responsive zu bleiben
                if cycle % 50 == 0:
                    time.sleep_ms(1)
            
            print("🎵 Bestrafungs-Sound beendet")
            
        except Exception as e:
            print(f"Audio-Wiedergabe Fehler: {e}")

    def play_reward_sound(self):
        """Spielt Belohnungs-Sound ab (angenehme Melodie für gutes Verhalten)"""
        if not self.i2s:
            print("I2S nicht verfügbar - kein Belohnungs-Sound")
            return
            
        try:
            print("🎵 BELOHNUNG: Spiele angenehme Melodie ab (Gute Pflanzenpflege!)")
            
            # Belohnungs-Melodie Parameter
            sample_rate = 22050
            amplitude = 16383  # Etwas leiser als Bestrafung (50% Amplitude)
            duration = 2  # Kürzere, angenehme Belohnung
            
            # Angenehme Akkord-Progression: C-E-G (C-Dur Dreiklang)
            frequencies = [
                261.63,  # C4
                329.63,  # E4
                392.00,  # G4
                523.25   # C5 (Oktave höher)
            ]
            
            # Jede Note für 0.5 Sekunden spielen
            note_duration = 0.5
            
            for freq in frequencies:
                samples_per_cycle = sample_rate // int(freq)
                
                # Erzeuge Sinuswelle für diese Note
                sine_wave = array.array("h", [
                    int(amplitude * math.sin(2 * math.pi * i / samples_per_cycle))
                    for i in range(samples_per_cycle)
                ])
                
                # Spiele Note für die gewünschte Dauer
                num_cycles = int(sample_rate * note_duration // samples_per_cycle)
                for cycle in range(num_cycles):
                    self.i2s.write(sine_wave)
                    # Kurze Pause für Responsivität
                    if cycle % 20 == 0:
                        time.sleep_ms(1)
            
            print("🎵 Belohnungs-Melodie beendet - Gut gemacht!")
            
        except Exception as e:
            print(f"Belohnungs-Audio Fehler: {e}")

    def cleanup_audio(self):
        """Räumt das Audio-System auf"""
        if self.i2s:
            try:
                self.i2s.deinit()
                print("I2S Audio-System beendet")
            except:
                pass
            self.i2s = None

    # ...existing code...

    def show_main_screen(self):
        """Hauptbildschirm mit Übersicht"""
        self.fill(BLACK)
        
        # Touch-Bereiche für Widgets (ohne Header, mehr Platz)
        y_start = 20
        
        # Erste Reihe: Temperature (1 Box) + Light (2 Boxen)
        color = GRAY_LIGHT  # Kacheln sollen immer grau sein
        
        # Temperatur Widget (Touch-Bereich 1)
        self.draw_rounded_rect(10, y_start, 90, 80, 8, color)
        self.draw_icon_temperature(20, y_start + 10, 30, ORANGE)
        self.draw_number(20, y_start + 45, self.sensor_data['temperature'], 2, ORANGE)
        
        # Licht Widget (erweitert über 2 Boxen) - Touch-Bereich 2 & 3
        light_value = int(self.sensor_data['light'])
        light_color = self.get_light_quality_color(light_value)
        light_description = self.get_light_quality_description(light_value)
        
        # Erweiterte Lichtbox (200 Pixel breit für 2 Boxen)
        self.draw_rounded_rect(110, y_start, 200, 80, 8, color)
        self.draw_icon_sun(120, y_start + 10, 60, light_color)  # 2x größer: 30 -> 60
        
        # Lichtqualität als Text rechts neben dem Icon anzeigen (gleiche Zeile)
        # Text rechts neben dem Icon positionieren
        text_x = 190  # Nach dem Icon (120 + 60 + 10 Pixel Abstand)
        text_y = y_start + 20  # Vertikal zentriert zum Icon
        
        if len(light_description) > 10:
            # Lange Beschreibungen verkürzen oder umbruch
            words = light_description.split()
            if len(words) >= 2:
                self.draw_simple_text_2x(text_x, text_y, words[0], light_color)
                self.draw_simple_text_2x(text_x, text_y + 20, words[1], light_color)  # 2x spacing: 10 -> 20
            else:
                # Zu lang für eine Zeile - verkürzen
                short_desc = light_description[:10]
                self.draw_simple_text_2x(text_x, text_y, short_desc, light_color)
        else:
            # Kurze Beschreibungen in einer Zeile neben dem Icon
            self.draw_simple_text_2x(text_x, text_y, light_description, light_color)
        
        # Zweite Reihe: Humidity (1 Box) + Plant Health (2 Boxen)
        # Luftfeuchtigkeit Widget 
        self.draw_rounded_rect(10, y_start + 90, 90, 80, 8, color)
        self.draw_icon_water(20, y_start + 100, 30, BLUE_LIGHT)
        self.draw_number(20, y_start + 135, self.sensor_data['humidity'], 2, BLUE_LIGHT)
        
        # Plant Health Widget (erweitert über 2 Boxen)
        self.draw_rounded_rect(110, y_start + 90, 200, 80, 8, color)
        health = self.sensor_data['plant_health']
        
        if health > 80:
            status_color = GREEN_LIGHT
        elif health > 60:
            status_color = YELLOW
        else:
            status_color = RED
            
        # Gesundheits-Fortschrittsbalken
        self.draw_progress_bar(120, y_start + 110, 180, 25, health, 100, GRAY_DARK, status_color)
        
        # "HEALTH" Text oben links
        self.draw_simple_text(115, y_start + 95, "HEALTH", status_color)
        
        # Gesundheitswert als Zahl rechts oben
        self.draw_number(270, y_start + 95, health, 1, status_color)
        
        # Touch-Navigation-Bar unten
        self.draw_bottom_navigation_bar()

    def show_detail_screen(self):
        """Detailansicht mit großen Sensordaten"""
        self.fill(BLACK)
        
        # Große Anzeigen (ohne Header, starte direkt oben)
        y = 20
        
        # Temperatur
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_temperature(20, y + 5, 30, ORANGE)
        temp_str = f"{self.sensor_data['temperature']:.1f}"
        self.draw_number(200, y + 5, float(temp_str), 3, ORANGE)
        
        y += 50
        
        # Lichtsensor-Daten mit qualitativer Anzeige
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        light_value = self.sensor_data['light']
        light_color = self.get_light_quality_color(light_value)
        light_description = self.get_light_quality_description(light_value)
        
        self.draw_icon_sun(20, y + 5, 30, light_color)
        self.draw_progress_bar(70, y + 10, 150, 20, light_value, 1000, GRAY_DARK, light_color)
        
        # Lichtqualität als Text anzeigen
        self.draw_simple_text(230, y + 15, light_description, light_color)
        
        y += 50
        
        # Wassertank-Level
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_water(20, y + 5, 30, BLUE_LIGHT)
        water_level = self.sensor_data['water_level']
        self.draw_progress_bar(70, y + 10, 200, 20, water_level, 100, GRAY_DARK, BLUE_LIGHT)
        self.draw_number(280, y + 15, water_level, 2, BLUE_LIGHT)
        
        # Touch-Navigation-Bar unten
        self.draw_bottom_navigation_bar()

    def show_settings_screen(self):
        """Einstellungsbildschirm mit Motion-Timeout Einstellung"""
        self.fill(BLACK)
        
        # Header mit aktueller Motion-Timeout Anzeige
        header_y = 10
        self.fill_rect(10, header_y, 300, 30, GRAY_DARK)
        
        # "Motion Timeout:" Text links
        self.draw_simple_text(15, header_y + 8, "MOTION:", WHITE)
        
        # Aktuelle Sekunden rechts mit 7-Segment Anzeige
        timeout_x = 200
        self.draw_number(timeout_x, header_y + 5, self.motion_timeout_seconds, 2, WHITE)
        # "s" für Sekunden
        self.draw_simple_text(timeout_x + 50, header_y + 15, "s", WHITE)
        
        # Motion-Timeout Einstellung (große Buttons)
        settings_y = 50
        
        # Minus Button (-10s)
        self.draw_rounded_rect(20, settings_y, 60, 40, 8, RED)
        self.draw_simple_text(35, settings_y + 18, "-10", WHITE)
        
        # Aktueller Wert (großer Anzeigebereich) 
        self.draw_rounded_rect(90, settings_y, 140, 40, 8, BLUE_LIGHT)
        # Große Anzeige der aktuellen Sekunden
        center_x = 90 + 70 - (len(str(self.motion_timeout_seconds)) * 8)  # Zentriert
        self.draw_number(center_x, settings_y + 10, self.motion_timeout_seconds, 3, BLACK)
        
        # Plus Button (+10s)
        self.draw_rounded_rect(240, settings_y, 60, 40, 8, GREEN_LIGHT)
        self.draw_simple_text(255, settings_y + 18, "+10", BLACK)
        
        # Feineinstellung Buttons (±5s)
        fine_y = settings_y + 50
        
        # Minus Button (-5s)
        self.draw_rounded_rect(50, fine_y, 50, 30, 5, ORANGE)
        self.draw_simple_text(65, fine_y + 12, "-5", BLACK)
        
        # Plus Button (+5s)
        self.draw_rounded_rect(220, fine_y, 50, 30, 5, ORANGE)
        self.draw_simple_text(235, fine_y + 12, "+5", BLACK)
        
        # Preset-Buttons für häufige Werte
        preset_y = fine_y + 40
        presets = [15, 30, 60, 120]  # 15s, 30s, 1min, 2min
        preset_colors = [YELLOW, GREEN_LIGHT, BLUE_LIGHT, GRAY_LIGHT]
        preset_labels = ["15s", "30s", "1m", "2m"]
        
        for i, (preset, color, label) in enumerate(zip(presets, preset_colors, preset_labels)):
            x = 20 + i * 70
            self.draw_rounded_rect(x, preset_y, 60, 25, 5, color)
            
            # Preset-Label zentriert
            label_x = x + 30 - (len(label) * 4)
            self.draw_simple_text(label_x, preset_y + 10, label, BLACK)
        
        # Info-Text
        info_y = preset_y + 35
        self.fill_rect(10, info_y, 300, 20, GRAY_DARK)
        self.draw_simple_text(15, info_y + 6, "Touch buttons to change timeout", WHITE)
        
        # Touch-Navigation-Bar unten
        self.draw_bottom_navigation_bar()
    
    def draw_simple_text(self, x, y, text, color):
        """Zeichnet einfachen Text mit Pixel-Matrix"""
        # Vereinfachte 5x7 Pixel-Font für wichtige Zeichen
        font = {
            'A': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'B': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'C': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'D': [[1,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'E': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            'F': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [0,0,0,0,0]],
            'G': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,0], [1,0,1,1,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'H': [[1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'I': [[0,1,1,1,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,0,0,0]],
            'L': [[1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            'M': [[1,0,0,0,1], [1,1,0,1,1], [1,0,1,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'N': [[1,0,0,0,1], [1,1,0,0,1], [1,0,1,0,1], [1,0,0,1,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'O': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'P': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [0,0,0,0,0]],
            'R': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,1,0,0], [1,0,0,1,0], [1,0,0,0,1], [0,0,0,0,0]],
            'S': [[0,1,1,1,1], [1,0,0,0,0], [0,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'T': [[1,1,1,1,1], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,0,0,0]],
            'U': [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'V': [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,0,1,0], [0,0,1,0,0], [0,0,0,0,0]],
            'Y': [[1,0,0,0,1], [1,0,0,0,1], [0,1,0,1,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,0,0,0]],
            '0': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            '1': [[0,0,1,0,0], [0,1,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,0,0,0]],
            '2': [[0,1,1,1,0], [1,0,0,0,1], [0,0,0,1,0], [0,0,1,0,0], [0,1,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            '3': [[1,1,1,1,0], [0,0,0,0,1], [0,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            '4': [[1,0,0,1,0], [1,0,0,1,0], [1,0,0,1,0], [1,1,1,1,1], [0,0,0,1,0], [0,0,0,1,0], [0,0,0,0,0]],
            '5': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            '+': [[0,0,0,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            '-': [[0,0,0,0,0], [0,0,0,0,0], [0,1,1,1,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            's': [[0,0,0,0,0], [0,1,1,1,0], [1,0,0,0,0], [0,1,1,0,0], [0,0,0,1,0], [1,1,1,0,0], [0,0,0,0,0]],
            'm': [[0,0,0,0,0], [1,1,0,1,0], [1,0,1,0,1], [1,0,1,0,1], [1,0,1,0,1], [1,0,1,0,1], [0,0,0,0,0]],
            ' ': [[0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            ':': [[0,0,0,0,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
        }
        
        char_x = x
        for char in text.upper():
            if char in font:
                char_pattern = font[char]
                for row_idx, row in enumerate(char_pattern):
                    for col_idx, pixel in enumerate(row):
                        if pixel:
                            self.pixel(char_x + col_idx, y + row_idx, color)
                char_x += 6  # 5 pixels width + 1 pixel spacing
            else:
                char_x += 6  # Fallback für unbekannte Zeichen

    def draw_simple_text_2x(self, x, y, text, color):
        """Zeichnet einfachen Text mit Pixel-Matrix in 2x Größe"""
        # Vereinfachte 5x7 Pixel-Font für wichtige Zeichen (gleiche wie draw_simple_text)
        font = {
            'A': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'B': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'C': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'D': [[1,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'E': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            'F': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [0,0,0,0,0]],
            'G': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,0], [1,0,1,1,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'H': [[1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'I': [[0,1,1,1,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,0,0,0]],
            'L': [[1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            'M': [[1,0,0,0,1], [1,1,0,1,1], [1,0,1,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'N': [[1,0,0,0,1], [1,1,0,0,1], [1,0,1,0,1], [1,0,0,1,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'O': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'P': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [0,0,0,0,0]],
            'R': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,1,0,0], [1,0,0,1,0], [1,0,0,0,1], [0,0,0,0,0]],
            'S': [[0,1,1,1,1], [1,0,0,0,0], [0,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'T': [[1,1,1,1,1], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,0,0,0]],
            'U': [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'V': [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,0,1,0], [0,0,1,0,0], [0,0,0,0,0]],
            'Y': [[1,0,0,0,1], [1,0,0,0,1], [0,1,0,1,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,0,0,0]],
            '0': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            '1': [[0,0,1,0,0], [0,1,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,0,0,0]],
            '2': [[0,1,1,1,0], [1,0,0,0,1], [0,0,0,1,0], [0,0,1,0,0], [0,1,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            '3': [[1,1,1,1,0], [0,0,0,0,1], [0,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            '4': [[1,0,0,1,0], [1,0,0,1,0], [1,0,0,1,0], [1,1,1,1,1], [0,0,0,1,0], [0,0,0,1,0], [0,0,0,0,0]],
            '5': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            '+': [[0,0,0,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            '-': [[0,0,0,0,0], [0,0,0,0,0], [0,1,1,1,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            's': [[0,0,0,0,0], [0,1,1,1,0], [1,0,0,0,0], [0,1,1,0,0], [0,0,0,1,0], [1,1,1,0,0], [0,0,0,0,0]],
            'm': [[0,0,0,0,0], [1,1,0,1,0], [1,0,1,0,1], [1,0,1,0,1], [1,0,1,0,1], [1,0,1,0,1], [0,0,0,0,0]],
            ' ': [[0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            ':': [[0,0,0,0,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
        }
        
        char_x = x
        for char in text.upper():
            if char in font:
                char_pattern = font[char]
                for row_idx, row in enumerate(char_pattern):
                    for col_idx, pixel in enumerate(row):
                        if pixel:
                            # Zeichne 2x2 Pixel Block für jeden ursprünglichen Pixel
                            for dx in range(2):
                                for dy in range(2):
                                    self.pixel(char_x + col_idx*2 + dx, y + row_idx*2 + dy, color)
                char_x += 12  # (5 pixels width + 1 pixel spacing) * 2
            else:
                char_x += 12  # Fallback für unbekannte Zeichen

    def show_detail_screen(self):
        """Detailansicht mit großen Sensordaten"""
        self.fill(BLACK)
        
        # Große Anzeigen (ohne Header, starte direkt oben)
        y = 20
        
        # Temperatur
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_temperature(20, y + 5, 30, ORANGE)
        temp_str = f"{self.sensor_data['temperature']:.1f}"
        self.draw_number(200, y + 5, float(temp_str), 3, ORANGE)
        
        y += 50
        
        # Lichtsensor-Daten mit qualitativer Anzeige
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        light_value = self.sensor_data['light']
        light_color = self.get_light_quality_color(light_value)
        light_description = self.get_light_quality_description(light_value)
        
        self.draw_icon_sun(20, y + 5, 30, light_color)
        self.draw_progress_bar(70, y + 10, 150, 20, light_value, 1000, GRAY_DARK, light_color)
        
        # Lichtqualität als Text anzeigen
        self.draw_simple_text(230, y + 15, light_description, light_color)
        
        y += 50
        
        # Wassertank-Level
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_water(20, y + 5, 30, BLUE_LIGHT)
        water_level = self.sensor_data['water_level']
        self.draw_progress_bar(70, y + 10, 200, 20, water_level, 100, GRAY_DARK, BLUE_LIGHT)
        self.draw_number(280, y + 15, water_level, 2, BLUE_LIGHT)
        
        # Touch-Navigation-Bar unten
        self.draw_bottom_navigation_bar()

    def show_settings_screen(self):
        """Einstellungsbildschirm mit Motion-Timeout Einstellung"""
        self.fill(BLACK)
        
        # Header mit aktueller Motion-Timeout Anzeige
        header_y = 10
        self.fill_rect(10, header_y, 300, 30, GRAY_DARK)
        
        # "Motion Timeout:" Text links
        self.draw_simple_text(15, header_y + 8, "MOTION:", WHITE)
        
        # Aktuelle Sekunden rechts mit 7-Segment Anzeige
        timeout_x = 200
        self.draw_number(timeout_x, header_y + 5, self.motion_timeout_seconds, 2, WHITE)
        # "s" für Sekunden
        self.draw_simple_text(timeout_x + 50, header_y + 15, "s", WHITE)
        
        # Motion-Timeout Einstellung (große Buttons)
        settings_y = 50
        
        # Minus Button (-10s)
        self.draw_rounded_rect(20, settings_y, 60, 40, 8, RED)
        self.draw_simple_text(35, settings_y + 18, "-10", WHITE)
        
        # Aktueller Wert (großer Anzeigebereich) 
        self.draw_rounded_rect(90, settings_y, 140, 40, 8, BLUE_LIGHT)
        # Große Anzeige der aktuellen Sekunden
        center_x = 90 + 70 - (len(str(self.motion_timeout_seconds)) * 8)  # Zentriert
        self.draw_number(center_x, settings_y + 10, self.motion_timeout_seconds, 3, BLACK)
        
        # Plus Button (+10s)
        self.draw_rounded_rect(240, settings_y, 60, 40, 8, GREEN_LIGHT)
        self.draw_simple_text(255, settings_y + 18, "+10", BLACK)
        
        # Feineinstellung Buttons (±5s)
        fine_y = settings_y + 50
        
        # Minus Button (-5s)
        self.draw_rounded_rect(50, fine_y, 50, 30, 5, ORANGE)
        self.draw_simple_text(65, fine_y + 12, "-5", BLACK)
        
        # Plus Button (+5s)
        self.draw_rounded_rect(220, fine_y, 50, 30, 5, ORANGE)
        self.draw_simple_text(235, fine_y + 12, "+5", BLACK)
        
        # Preset-Buttons für häufige Werte
        preset_y = fine_y + 40
        presets = [15, 30, 60, 120]  # 15s, 30s, 1min, 2min
        preset_colors = [YELLOW, GREEN_LIGHT, BLUE_LIGHT, GRAY_LIGHT]
        preset_labels = ["15s", "30s", "1m", "2m"]
        
        for i, (preset, color, label) in enumerate(zip(presets, preset_colors, preset_labels)):
            x = 20 + i * 70
            self.draw_rounded_rect(x, preset_y, 60, 25, 5, color)
            
            # Preset-Label zentriert
            label_x = x + 30 - (len(label) * 4)
            self.draw_simple_text(label_x, preset_y + 10, label, BLACK)
        
        # Info-Text
        info_y = preset_y + 35
        self.fill_rect(10, info_y, 300, 20, GRAY_DARK)
        self.draw_simple_text(15, info_y + 6, "Touch buttons to change timeout", WHITE)
        
        # Touch-Navigation-Bar unten
        self.draw_bottom_navigation_bar()
    
    def draw_simple_text(self, x, y, text, color):
        """Zeichnet einfachen Text mit Pixel-Matrix"""
        # Vereinfachte 5x7 Pixel-Font für wichtige Zeichen
        font = {
            'A': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'B': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'C': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'D': [[1,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'E': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            'F': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [0,0,0,0,0]],
            'G': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,0], [1,0,1,1,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'H': [[1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'I': [[0,1,1,1,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,0,0,0]],
            'L': [[1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            'M': [[1,0,0,0,1], [1,1,0,1,1], [1,0,1,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'N': [[1,0,0,0,1], [1,1,0,0,1], [1,0,1,0,1], [1,0,0,1,1], [1,0,0,0,1], [1,0,0,0,1], [0,0,0,0,0]],
            'O': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'P': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [0,0,0,0,0]],
            'R': [[1,1,1,1,0], [1,0,0,0,1], [1,1,1,1,0], [1,0,1,0,0], [1,0,0,1,0], [1,0,0,0,1], [0,0,0,0,0]],
            'S': [[0,1,1,1,1], [1,0,0,0,0], [0,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            'T': [[1,1,1,1,1], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,0,0,0]],
            'U': [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            'V': [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,0,1,0], [0,0,1,0,0], [0,0,0,0,0]],
            '0': [[0,1,1,1,0], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [0,1,1,1,0], [0,0,0,0,0]],
            '1': [[0,0,1,0,0], [0,1,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,0,0,0]],
            '2': [[0,1,1,1,0], [1,0,0,0,1], [0,0,0,1,0], [0,0,1,0,0], [0,1,0,0,0], [1,1,1,1,1], [0,0,0,0,0]],
            '3': [[1,1,1,1,0], [0,0,0,0,1], [0,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            '4': [[1,0,0,1,0], [1,0,0,1,0], [1,0,0,1,0], [1,1,1,1,1], [0,0,0,1,0], [0,0,0,1,0], [0,0,0,0,0]],
            '5': [[1,1,1,1,1], [1,0,0,0,0], [1,1,1,1,0], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,0], [0,0,0,0,0]],
            '+': [[0,0,0,0,0], [0,0,1,0,0], [0,1,1,1,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            '-': [[0,0,0,0,0], [0,0,0,0,0], [0,1,1,1,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            's': [[0,0,0,0,0], [0,1,1,1,0], [1,0,0,0,0], [0,1,1,0,0], [0,0,0,1,0], [1,1,1,0,0], [0,0,0,0,0]],
            'm': [[0,0,0,0,0], [1,1,0,1,0], [1,0,1,0,1], [1,0,1,0,1], [1,0,1,0,1], [1,0,1,0,1], [0,0,0,0,0]],
            ' ': [[0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
            ':': [[0,0,0,0,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,1,0,0], [0,0,0,0,0], [0,0,0,0,0], [0,0,0,0,0]],
        }
        
        char_x = x
        for char in text.upper():
            if char in font:
                char_pattern = font[char]
                for row_idx, row in enumerate(char_pattern):
                    for col_idx, pixel in enumerate(row):
                        if pixel:
                            # Zeichne 2x2 Pixel Block für jeden ursprünglichen Pixel
                            for dx in range(2):
                                for dy in range(2):
                                    self.pixel(char_x + col_idx*2 + dx, y + row_idx*2 + dy, color)
                char_x += 12  # (5 pixels width + 1 pixel spacing) * 2
            else:
                char_x += 12  # Fallback für unbekannte Zeichen

    def update_sensor_data(self):
        """Aktualisiert Sensordaten - kombiniert echte und simulierte Werte"""
        
        # Echte Lichtsensor-Daten lesen (GP28)
        light_value, light_voltage, light_raw = self.read_light_sensor()
        
        # Echte Temperatur/Feuchtigkeits-Daten lesen (GP26)
        real_temp, real_humidity = self.read_temp_humidity_sensor()
        
        # Motion-Sensor Status lesen (GP27) - jetzt mit 30s Timeout
        motion_detected = self.read_motion_sensor()
        # Motion-Handling ist jetzt in der read_motion_sensor() Funktion integriert
        
        # Prüfen ob sich Werte geändert haben
        values_changed = False
        
        # Lichtwerte prüfen (Toleranz von 5 Lux)
        if abs(light_value - self.last_light_value) > 5:
            self.data_needs_update = True
            values_changed = True
            print(f"Lichtwert geändert: {self.last_light_value} -> {light_value}")
        
        # Echte Sensordaten verwenden falls verfügbar, sonst simulierte Werte
        if real_temp is not None:
            if abs(real_temp - self.sensor_data['temperature']) > 0.1:
                self.sensor_data['temperature'] = real_temp
                values_changed = True
        else:
            # Simuliere Temperatur falls Sensor nicht verfügbar
            self.sensor_data['temperature'] += random.uniform(-0.5, 0.5)
            self.sensor_data['temperature'] = max(15, min(35, self.sensor_data['temperature']))
        
        if real_humidity is not None:
            if abs(real_humidity - self.sensor_data['humidity']) > 1:
                self.sensor_data['humidity'] = real_humidity
                values_changed = True
        else:
            # Simuliere Luftfeuchtigkeit falls Sensor nicht verfügbar
            self.sensor_data['humidity'] += random.uniform(-2, 2)
            self.sensor_data['humidity'] = max(30, min(90, self.sensor_data['humidity']))
        
        # Prüfen ob andere Werte Update brauchen
        if (abs(self.sensor_data['temperature'] - self.last_displayed_values.get('temperature', 0)) > 0.1 or
            abs(self.sensor_data['humidity'] - self.last_displayed_values.get('humidity', 0)) > 1):
            self.data_needs_update = True
        
        self.sensor_data['light'] = light_value
        self.sensor_data['light_voltage'] = light_voltage
        self.sensor_data['light_raw'] = light_raw
        self.last_light_value = light_value
        
        # Debug-Ausgabe für alle Sensoren
        print(f"Sensoren - Licht: {light_value} Lux ({light_voltage:.2f}V), Temp: {self.sensor_data['temperature']:.1f}°C, Humidity: {self.sensor_data['humidity']:.1f}%")
        
        # Berechne Pflanzengesundheit basierend auf echten Sensordaten
        health = 100
        if self.sensor_data['temperature'] < 18 or self.sensor_data['temperature'] > 28:
            health -= 15
        if light_value < 300:  # Verwende echte Lichtwerte
            health -= 20
        if self.sensor_data['humidity'] < 40 or self.sensor_data['humidity'] > 80:
            health -= 15
        
        self.sensor_data['plant_health'] = max(0, min(100, health))

    def handle_touch(self, x, y):
        """Behandelt Touch-Eingaben basierend auf aktuellem Screen"""
        print(f"Touch at: {x}, {y} on screen {self.current_screen}")
        
        # Touch aktiviert manuellen Modus
        old_screen = self.current_screen
        self.manual_mode = True
        self.last_touch_time = time.ticks_ms()
        
        # Navigation-Bar Touch-Bereiche (unten)
        nav_y = self.height - 40  # Navigation-Bar ist 40px hoch
        if y >= nav_y:
            button_width = self.width // 2
            if x < button_width:  # Dashboard Button
                self.current_screen = 0
            else:  # Settings Button  
                self.current_screen = 2
        else:
            # Touch in den Hauptbereichen der verschiedenen Screens
            if self.current_screen == 0:  # Main Screen
                # Widget-Bereiche prüfen (angepasste Y-Koordinaten wegen fehlendem Header)
                if 20 <= y <= 100:  # Erste Widget-Reihe
                    if 10 <= x <= 100:      # Temperatur-Widget
                        self.current_screen = 1  # Zu Details
                    elif 110 <= x <= 200:   # Humidity-Widget  
                        self.current_screen = 1
                    elif 210 <= x <= 300:   # Soil-Widget
                        self.current_screen = 1
                elif 110 <= y <= 190:  # Zweite Widget-Reihe  
                    if 10 <= x <= 100:      # Licht-Widget
                        self.current_screen = 1  # Zu Details
                    elif 110 <= x <= 300:   # Pflanzenstatus-Widget
                        self.current_screen = 1
                        
            elif self.current_screen == 1:  # Detail Screen
                # Tippen irgendwo (außer Navigation-Bar) geht zurück zum Dashboard
                self.current_screen = 0
                    
            elif self.current_screen == 2:  # Settings Screen  
                # Motion-Timeout Einstellungen
                settings_y = 50
                fine_y = settings_y + 50
                preset_y = fine_y + 40
                
                if settings_y <= y <= settings_y + 40:  # Hauptbuttons
                    if 20 <= x <= 80:  # -10s Button
                        self.motion_timeout_seconds = max(5, self.motion_timeout_seconds - 10)
                        self.motion_timeout = self.motion_timeout_seconds * 1000
                        print(f"Motion-Timeout auf {self.motion_timeout_seconds}s gesetzt")
                        self.screen_needs_redraw = True
                    elif 240 <= x <= 300:  # +10s Button
                        self.motion_timeout_seconds = min(300, self.motion_timeout_seconds + 10)
                        self.motion_timeout = self.motion_timeout_seconds * 1000
                        print(f"Motion-Timeout auf {self.motion_timeout_seconds}s gesetzt")
                        self.screen_needs_redraw = True
                        
                elif fine_y <= y <= fine_y + 30:  # Feineinstellung
                    if 50 <= x <= 100:  # -5s Button
                        self.motion_timeout_seconds = max(5, self.motion_timeout_seconds - 5)
                        self.motion_timeout = self.motion_timeout_seconds * 1000
                        print(f"Motion-Timeout auf {self.motion_timeout_seconds}s gesetzt")
                        self.screen_needs_redraw = True
                    elif 220 <= x <= 270:  # +5s Button
                        self.motion_timeout_seconds = min(300, self.motion_timeout_seconds + 5)
                        self.motion_timeout = self.motion_timeout_seconds * 1000
                        print(f"Motion-Timeout auf {self.motion_timeout_seconds}s gesetzt")
                        self.screen_needs_redraw = True
                        
                elif preset_y <= y <= preset_y + 25:  # Preset-Buttons
                    presets = [15, 30, 60, 120]
                    for i, preset in enumerate(presets):
                        button_x = 20 + i * 70
                        if button_x <= x <= button_x + 60:
                            self.motion_timeout_seconds = preset
                            self.motion_timeout = preset * 1000
                            print(f"Motion-Timeout Preset auf {preset}s gesetzt")
                            self.screen_needs_redraw = True
                            break
        
        # Screen hat sich geändert - neu zeichnen erforderlich
        if old_screen != self.current_screen:
            self.screen_needs_redraw = True

    def check_auto_mode_timeout(self):
        """Prüft ob nach Touch-Timeout wieder in Auto-Modus gewechselt werden soll"""
        if self.manual_mode:
            current_time = time.ticks_ms()
            if time.ticks_diff(current_time, self.last_touch_time) > 60000:  # 1 Minute
                self.manual_mode = False
                print("Zurück zu Auto-Modus")

    def run_ui(self):
        """Hauptschleife für das UI mit Touch-Unterstützung"""
        screen_count = 2  # Nur Dashboard (0) und Settings (2)
        last_screen_change = time.ticks_ms()
        screen_duration = 180000  # 3 Minuten pro Screen (nur im Auto-Modus)
        last_touch_pos = None
        
        try:
            while True:
                current_time = time.ticks_ms()
                
                # Touch-Input prüfen
                if self.touch:
                    touch_pos = self.touch.get_touch()
                    if touch_pos and touch_pos != last_touch_pos:
                        x, y = touch_pos
                        self.handle_touch(x, y)
                        last_touch_pos = touch_pos
                    elif not touch_pos:
                        last_touch_pos = None
                
                # Auto-Modus Timeout prüfen
                self.check_auto_mode_timeout()
                
                # Sensordaten alle 5 Sekunden aktualisieren (weniger häufig)
                if time.ticks_diff(current_time, self.last_update) > 5000:
                    self.update_sensor_data()
                    self.last_update = current_time
                
                # Screen nur neu zeichnen wenn wirklich nötig (Screen-Wechsel oder erste Anzeige)
                if self.screen_needs_redraw or self.last_drawn_screen != self.current_screen:
                    if self.current_screen == 0:
                        self.show_main_screen()
                    elif self.current_screen == 1:
                        self.show_detail_screen()
                    else:
                        self.show_settings_screen()
                    
                    # Angezeigte Werte zurücksetzen nach kompletter Neuzeichnung
                    for key in self.last_displayed_values:
                        self.last_displayed_values[key] = self.sensor_data.get(key, 0)
                    
                    self.last_drawn_screen = self.current_screen
                    self.screen_needs_redraw = False
                    self.data_needs_update = False
                    print(f"Screen {self.current_screen} komplett neu gezeichnet")
                    
                # Nur Daten-Updates ohne komplettes Redraw
                elif self.data_needs_update:
                    self.update_display_values_only()
                    self.data_needs_update = False
                    print("Nur Sensordaten aktualisiert (kein komplettes Redraw)")
                
                # Screen nur im Auto-Modus automatisch wechseln (nur zwischen 0 und 2)
                if not self.manual_mode and time.ticks_diff(current_time, last_screen_change) > screen_duration:
                    old_screen = self.current_screen
                    if self.current_screen == 0:
                        self.current_screen = 2  # Dashboard -> Settings
                    else:
                        self.current_screen = 0  # Settings -> Dashboard
                    last_screen_change = current_time
                    print(f"Auto-Wechsel zu Screen {self.current_screen}")
                    if old_screen != self.current_screen:
                        self.screen_needs_redraw = True
                
                time.sleep(0.2)  # Längere Pause für weniger Last
                
        except KeyboardInterrupt:
            print("UI wird beendet...")
            self.cleanup_audio()
            raise
        except Exception as e:
            print(f"UI Fehler: {e}")
            self.cleanup_audio()
            raise

    def update_display_values_only(self):
        """Aktualisiert nur die Zahlenwerte auf dem Display ohne komplettes Neuzeichnen"""
        if self.current_screen == 0:  # Main Screen
            y_start = 20  # Muss mit show_main_screen() übereinstimmen
            
            # Temperatur-Wert aktualisieren
            if abs(self.sensor_data['temperature'] - self.last_displayed_values['temperature']) > 0.1:
                # Überschreibe alten Wert mit Hintergrundfarbe (größerer Bereich)
                self.fill_rect(20, y_start + 45, 65, 30, GRAY_LIGHT)
                # Zeichne neuen Wert
                self.draw_number(20, y_start + 45, self.sensor_data['temperature'], 2, ORANGE)
                self.last_displayed_values['temperature'] = self.sensor_data['temperature']
            
            # Luftfeuchtigkeit-Wert aktualisieren (neue Position in zweiter Reihe)
            if abs(self.sensor_data['humidity'] - self.last_displayed_values['humidity']) > 1:
                self.fill_rect(20, y_start + 135, 65, 30, GRAY_LIGHT)
                self.draw_number(20, y_start + 135, self.sensor_data['humidity'], 2, BLUE_LIGHT)
                self.last_displayed_values['humidity'] = self.sensor_data['humidity']
            
            # Lichtqualität-Text und Icon aktualisieren
            if abs(self.sensor_data['light'] - self.last_displayed_values['light']) > 5:
                light_value = int(self.sensor_data['light'])
                light_color = self.get_light_quality_color(light_value)
                light_description = self.get_light_quality_description(light_value)
                
                # Clear den gesamten Licht-Widget Bereich (Icon + Text)
                self.fill_rect(110, y_start, 200, 80, GRAY_LIGHT)  # Gesamte Lichtbox löschen
                
                # Icon neu zeichnen mit aktueller Farbe
                self.draw_icon_sun(120, y_start + 10, 60, light_color)  # 2x größer: 30 -> 60
                
                # Text neu zeichnen
                text_x = 190  # Nach dem Icon (120 + 60 + 10 Pixel Abstand)
                text_y = y_start + 20  # Vertikal zentriert zum Icon
                
                # Neue Beschreibung zeichnen (mit gleicher Logik wie show_main_screen)
                if len(light_description) > 10:
                    # Lange Beschreibungen verkürzen oder umbruch
                    words = light_description.split()
                    if len(words) >= 2:
                        self.draw_simple_text_2x(text_x, text_y, words[0], light_color)
                        self.draw_simple_text_2x(text_x, text_y + 20, words[1], light_color)  # 2x spacing: 10 -> 20
                    else:
                        # Zu lang für eine Zeile - verkürzen
                        short_desc = light_description[:10]
                        self.draw_simple_text_2x(text_x, text_y, short_desc, light_color)
                else:
                    # Kurze Beschreibungen in einer Zeile neben dem Icon
                    self.draw_simple_text_2x(text_x, text_y, light_description, light_color)
                
                self.last_displayed_values['light'] = light_value
            
            # Pflanzengesundheit-Balken aktualisieren
            if abs(self.sensor_data['plant_health'] - self.last_displayed_values['plant_health']) > 1:
                health = self.sensor_data['plant_health']
                if health > 80:
                    status_color = GREEN_LIGHT
                elif health > 60:
                    status_color = YELLOW
                else:
                    status_color = RED
                # Nur den Fortschrittsbalken neu zeichnen (angepasste Position)
                self.draw_progress_bar(120, y_start + 110, 180, 25, health, 100, GRAY_DARK, status_color)
                self.last_displayed_values['plant_health'] = health
                
        elif self.current_screen == 1:  # Detail Screen
            y = 20  # Muss mit show_detail_screen() übereinstimmen
            
            # Temperatur Detail-Wert
            if abs(self.sensor_data['temperature'] - self.last_displayed_values['temperature']) > 0.1:
                self.fill_rect(200, y + 5, 80, 30, GRAY_LIGHT)
                temp_str = f"{self.sensor_data['temperature']:.1f}"
                self.draw_number(200, y + 5, float(temp_str), 3, ORANGE)
                self.last_displayed_values['temperature'] = self.sensor_data['temperature']
            
            y += 50
            
            # Licht Detail
            if abs(self.sensor_data['light'] - self.last_displayed_values['light']) > 5:
                light_value = self.sensor_data['light']
                light_color = self.get_light_quality_color(light_value)
                light_description = self.get_light_quality_description(light_value)
                
                self.draw_progress_bar(70, y + 10, 150, 20, light_value, 1000, GRAY_DARK, light_color)
                self.fill_rect(230, y + 15, 75, 15, GRAY_LIGHT)
                self.draw_simple_text(230, y + 15, light_description, light_color)
                self.last_displayed_values['light'] = light_value

    def draw_bottom_navigation_bar(self):
        """Zeichnet die Touch-Navigation-Bar am unteren Bildschirmrand"""
        nav_height = 40
        nav_y = self.height - nav_height
        
        # Navigation-Bar Hintergrund
        self.fill_rect(0, nav_y, self.width, nav_height, GRAY_DARK)
        
        # Button-Bereiche
        button_width = self.width // 2
        
        # Dashboard Button (links)
        dashboard_active = self.current_screen == 0
        dashboard_color = GREEN_LIGHT if dashboard_active else GRAY_LIGHT
        self.draw_rounded_rect(5, nav_y + 5, button_width - 10, nav_height - 10, 8, dashboard_color)
        
        # Dashboard Icon und Text nebeneinander
        icon_start_x = 15  # Links im Button
        text_start_x = icon_start_x + 30  # Text rechts vom Icon
        center_y = nav_y + 15  # Vertikal zentriert
        
        # Dashboard Icon (vereinfachtes Grid)
        icon_x = icon_start_x
        icon_y = center_y - 8
        for i in range(2):
            for j in range(2):
                rect_x = icon_x + i * 8
                rect_y = icon_y + j * 8
                icon_color = BLACK if dashboard_active else WHITE
                self.fill_rect(rect_x, rect_y, 6, 6, icon_color)
        
        # "Dashboard" Text rechts vom Icon
        text_color = BLACK if dashboard_active else WHITE
        self.draw_simple_text(text_start_x, center_y - 3, "Dashboard", text_color)
        
        # Settings Button (rechts)
        settings_active = self.current_screen == 2
        settings_color = ORANGE if settings_active else GRAY_LIGHT
        self.draw_rounded_rect(button_width + 5, nav_y + 5, button_width - 10, nav_height - 10, 8, settings_color)
        
        # Settings Icon und Text nebeneinander
        settings_icon_start_x = button_width + 15  # Links im Settings-Button
        settings_text_start_x = settings_icon_start_x + 25  # Text rechts vom Icon
        
        # Settings Icon (Zahnrad-vereinfacht)
        settings_icon_x = settings_icon_start_x
        settings_icon_y = center_y - 6
        icon_color = BLACK if settings_active else WHITE
        self.draw_circle(settings_icon_x + 6, settings_icon_y + 6, 6, icon_color)
        self.fill_rect(settings_icon_x + 4, settings_icon_y + 4, 4, 4, GRAY_DARK if settings_active else GRAY_DARK)
        
        # "Settings" Text rechts vom Icon
        text_color = BLACK if settings_active else WHITE
        self.draw_simple_text(settings_text_start_x, center_y - 3, "Settings", text_color)

    def get_light_quality_description(self, light_value):
        """Konvertiert Lichtwerte in qualitative Beschreibungen"""
        if light_value >= 800:
            return "EXCELLENT"
        elif light_value >= 600:
            return "VERY GOOD"
        elif light_value >= 400:
            return "GOOD"
        elif light_value >= 200:
            return "POOR"
        else:
            return "VERY POOR"

    def get_light_quality_color(self, light_value):
        """Gibt passende Farbe für Lichtqualität zurück"""
        if light_value >= 800:
            return GREEN_LIGHT  # Excellent
        elif light_value >= 600:
            return YELLOW  # Very Good
        elif light_value >= 400:
            return ORANGE  # Good
        elif light_value >= 200:
            return RED  # Poor
        else:
            return GRAY_DARK  # Very Poor

def main():
    print("=== Smart Plant UI mit Touch ===")
    
    # Display Pin-Konfiguration
    dc_pin = machine.Pin(17, machine.Pin.OUT)
    reset_pin = machine.Pin(20, machine.Pin.OUT)
    cs_pin = machine.Pin(21, machine.Pin.OUT)
    
    # Touch Pin-Konfiguration
    touch_cs_pin = machine.Pin(1, machine.Pin.OUT)   # T_CS
    touch_irq_pin = machine.Pin(6, machine.Pin.IN)   # T_IRQ
    
    # SPI-Konfiguration für Display (SPI 0)
    display_spi = machine.SPI(0, 
                      baudrate=20000000,
                      polarity=0, 
                      phase=0)
    
    # Software-SPI für Touch (BitBang) - exakt Ihre Hardware-Pins
    # Definiere Touch-Pins (exakt wie Sie sie verkabelt haben)
    touch_sck = machine.Pin(2, machine.Pin.OUT)   # T_CLK = GP2
    touch_mosi = machine.Pin(3, machine.Pin.OUT)  # T_DIN = GP3  
    touch_miso = machine.Pin(5, machine.Pin.IN)   # T_DO = GP5 (wie verkabelt)
    
    # Software-SPI erstellen
    touch_spi = machine.SoftSPI(
        baudrate=100000,  # Langsamere Geschwindigkeit für stabilere Kommunikation
        polarity=0,
        phase=0,
        sck=touch_sck,
        mosi=touch_mosi,
        miso=touch_miso
    )
    
    # Touch-Controller erstellen
    touch = TouchController(touch_spi, touch_cs_pin, touch_irq_pin)
    
    # Display erstellen und initialisieren
    plant_ui = SmartPlantDisplay(display_spi, dc_pin, reset_pin, cs_pin, touch)
    plant_ui.init()
    
    print("Touch-Controller konfiguriert:")
    print("  T_CS: GP1")
    print("  T_IRQ: GP6") 
    print("  T_CLK: GP2 (Software SPI)")
    print("  T_DIN: GP3 (Software SPI)")
    print("  T_DO: GP5 (Software SPI)")
    print("  ✅ Verwendet Software-SPI (BitBang) - exakt Ihre Hardware-Pins")
    print("  ⚡ Baudrate reduziert für stabilere Touch-Kommunikation")
    
    print("Sensoren konfiguriert:")
    print("  LDR: GP28 (ADC2) - Lichtsensor") 
    print("  DHT11: GP26 - Temperatur und Luftfeuchtigkeit")
    print(f"  Motion: GP27 - aktiv mit {plant_ui.motion_timeout_seconds}s Timeout (einstellbar)")
    
    print("Audio-System konfiguriert:")
    print("  I2S BCLK: GP10")
    print("  I2S WS/LRC: GP11") 
    print("  I2S DIN: GP12")
    print(f"  🎵 Bestrafung: 5s Sinuswelle (3000 Hz) bei {plant_ui.motion_timeout_seconds}s ohne Motion")
    print("  🎶 Belohnung: C-Dur Melodie (2s) bei Motion-Erkennung")
    
    print("Starte Pflanzentopf UI mit Touch und echten Sensoren...")
    print("Tippen Sie auf das Display für manuelle Steuerung!")
    print(f"Motion-Sensor: Belohnung bei Gießen, Bestrafung nach {plant_ui.motion_timeout_seconds}s ohne Motion!")
    print("⚙️  Settings-Tab: Motion-Timeout einstellbar (5-300 Sekunden)")
    
    try:
        plant_ui.run_ui()
    except KeyboardInterrupt:
        print("UI beendet")
        plant_ui.cleanup_audio()
        plant_ui.fill(BLACK)


if __name__ == "__main__":
    main()
