import machine
import time
from micropython import const
import ustruct as struct
import math

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
        
    def read_touch_raw(self, cmd):
        """Liest rohe Touch-Daten"""
        self.cs.off()
        self.spi.write(bytes([cmd]))
        
        # Warte auf Antwort und lese 2 Bytes
        result = self.spi.read(2)
        self.cs.on()
        
        if len(result) == 2:
            return (result[0] << 8 | result[1]) >> 3
        return 0
    
    def get_touch(self):
        """Gibt Touch-Position zurück oder None falls kein Touch"""
        if self.irq.value() == 1:  # Kein Touch
            return None
            
        # Mehrere Messungen für Stabilität
        x_sum = y_sum = 0
        valid_readings = 0
        
        for _ in range(5):
            x_raw = self.read_touch_raw(TOUCH_CMD_X)
            y_raw = self.read_touch_raw(TOUCH_CMD_Y)
            
            if x_raw > 100 and y_raw > 100:  # Gültige Werte
                x_sum += x_raw
                y_sum += y_raw
                valid_readings += 1
                
        if valid_readings == 0:
            return None
            
        # Durchschnitt berechnen
        x_avg = x_sum // valid_readings
        y_avg = y_sum // valid_readings
        
        # In Bildschirmkoordinaten umwandeln
        x = int((x_avg - self.cal_x_min) * 320 / (self.cal_x_max - self.cal_x_min))
        y = int((y_avg - self.cal_y_min) * 240 / (self.cal_y_max - self.cal_y_min))
        
        # Grenzen prüfen
        x = max(0, min(319, x))
        y = max(0, min(239, y))
        
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
        
        # Lichtsensor (ADC) initialisieren
        self.light_sensor = machine.ADC(machine.Pin(28))  # GP28 = ADC2
        
        # Simulierte Sensordaten
        self.sensor_data = {
            'temperature': 22.5,
            'humidity': 65,
            'soil_moisture': 45,
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
        self.write_cmd_data(ILI9341_MADCTL, MADCTL_MX | MADCTL_BGR)
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

    def show_main_screen(self):
        """Hauptbildschirm mit Übersicht"""
        self.fill(BLACK)
        
        # Header mit Touch-Indikator
        self.fill_rect(0, 0, 320, 40, GREEN_DARK)
        
        # Touch-Modus Indikator
        if self.manual_mode:
            self.fill_rect(280, 5, 30, 30, YELLOW)
            # "M" für Manual
            self.fill_rect(285, 10, 3, 20, BLACK)
            self.fill_rect(292, 10, 3, 20, BLACK)
            self.fill_rect(288, 10, 4, 5, BLACK)
        
        # Titel-Text (vereinfacht)
        for i, char in enumerate("SMART PLANT"):
            x = 20 + i * 25
            if char != ' ':
                self.fill_rect(x, 10, 20, 20, WHITE)
        
        # Touch-Bereiche für Widgets (mit visueller Hervorhebung)
        y_start = 50
        
        # Temperatur Widget (Touch-Bereich 1)
        color = GRAY_LIGHT if not self.manual_mode else WHITE
        self.draw_rounded_rect(10, y_start, 90, 80, 8, color)
        self.draw_icon_temperature(20, y_start + 10, 30, ORANGE)
        self.draw_number(20, y_start + 45, self.sensor_data['temperature'], 2, ORANGE)
        
        # Luftfeuchtigkeit Widget (Touch-Bereich 2)
        self.draw_rounded_rect(110, y_start, 90, 80, 8, color)
        self.draw_icon_water(120, y_start + 10, 30, BLUE_LIGHT)
        self.draw_number(120, y_start + 45, self.sensor_data['humidity'], 2, BLUE_LIGHT)
        
        # Bodenfeuchtigkeit Widget (Touch-Bereich 3)
        self.draw_rounded_rect(210, y_start, 90, 80, 8, color)
        self.draw_icon_plant(220, y_start + 10, 30, GREEN_LIGHT)
        self.draw_number(220, y_start + 45, self.sensor_data['soil_moisture'], 2, GREEN_LIGHT)
        
        # Licht Widget (mit echten Daten) - Touch-Bereich 4
        self.draw_rounded_rect(10, y_start + 90, 90, 80, 8, color)
        self.draw_icon_sun(20, y_start + 100, 30, YELLOW)
        # Zeige echte Lichtwerte - kleinere Größe für mehrstellige Zahlen
        light_val = int(self.sensor_data['light'])
        if light_val >= 100:
            self.draw_number(15, y_start + 135, light_val, 1, YELLOW)  # Kleine Ziffern für große Zahlen
        else:
            self.draw_number(25, y_start + 135, light_val, 2, YELLOW)  # Größere Ziffern für kleine Zahlen
        
        # Pflanzenstatus Widget
        self.draw_rounded_rect(110, y_start + 90, 190, 80, 8, color)
        health = self.sensor_data['plant_health']
        
        if health > 80:
            status_color = GREEN_LIGHT
        elif health > 60:
            status_color = YELLOW
        else:
            status_color = RED
            
        # Gesundheits-Fortschrittsbalken
        self.draw_progress_bar(120, y_start + 110, 170, 20, health, 100, GRAY_DARK, status_color)
        
        # Navigation-Buttons unten (nur im Manual-Modus)
        if self.manual_mode:
            # Zurück Button
            self.draw_rounded_rect(10, 200, 60, 30, 5, RED)
            self.fill_rect(20, 210, 40, 10, WHITE)  # "BACK" 
            
            # Weiter Button  
            self.draw_rounded_rect(250, 200, 60, 30, 5, GREEN_LIGHT)
            self.fill_rect(260, 210, 40, 10, WHITE)  # "NEXT"

    def show_detail_screen(self):
        """Detailansicht mit großen Sensordaten"""
        self.fill(BLACK)
        
        # Header
        self.fill_rect(0, 0, 320, 35, BLUE_DARK)
        
        # Große Anzeigen
        y = 50
        
        # Temperatur
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_temperature(20, y + 5, 30, ORANGE)
        temp_str = f"{self.sensor_data['temperature']:.1f}"
        self.draw_number(200, y + 5, float(temp_str), 3, ORANGE)
        
        y += 50
        
        # Bodenfeuchtigkeit mit Fortschrittsbalken
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_plant(20, y + 5, 30, GREEN_LIGHT)
        moisture = self.sensor_data['soil_moisture']
        self.draw_progress_bar(70, y + 10, 200, 20, moisture, 100, GRAY_DARK, GREEN_LIGHT)
        self.draw_number(280, y + 15, moisture, 2, GREEN_LIGHT)
        
        y += 50
        
        # Echte Lichtsensor-Daten mit Details
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_sun(20, y + 5, 30, YELLOW)
        light_value = self.sensor_data['light']
        self.draw_progress_bar(70, y + 10, 200, 20, light_value, 1000, GRAY_DARK, YELLOW)
        # Bessere Positionierung der Lichtwerte
        if light_value >= 100:
            self.draw_number(275, y + 15, light_value, 1, YELLOW)  # 3-4 stellige Zahlen
        else:
            self.draw_number(280, y + 15, light_value, 2, YELLOW)  # 1-2 stellige Zahlen
        
        y += 50
        
        # Wassertank-Level
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_water(20, y + 5, 30, BLUE_LIGHT)
        water_level = self.sensor_data['water_level']
        self.draw_progress_bar(70, y + 10, 200, 20, water_level, 100, GRAY_DARK, BLUE_LIGHT)
        self.draw_number(280, y + 15, water_level, 2, BLUE_LIGHT)
        
        # Touch-Navigation (nur im Manual-Modus)
        if self.manual_mode:
            # Back Button
            self.draw_rounded_rect(20, 200, 80, 30, 5, RED)
            self.fill_rect(30, 210, 60, 10, WHITE)  # "BACK"
            
            # Settings Button
            self.draw_rounded_rect(220, 200, 80, 30, 5, ORANGE)
            self.fill_rect(230, 210, 60, 10, WHITE)  # "SETTINGS"

    def show_settings_screen(self):
        """Einstellungsbildschirm"""
        self.fill(BLACK)
        
        # Header
        self.fill_rect(0, 0, 320, 35, RED)
        
        # Lichtsensor-Info oben
        info_y = 45
        self.fill_rect(10, info_y, 300, 25, GRAY_DARK)
        # Einfache Info-Anzeige (vereinfacht)
        info_text = f"Light: {self.sensor_data['light']} Lux {self.sensor_data['light_voltage']:.2f}V"
        for i, char in enumerate(info_text[:35]):  # Max 35 Zeichen
            if i * 8 < 280:
                self.fill_rect(15 + i * 8, info_y + 5, 6, 15, WHITE)
        
        # Einstellungsoptionen (vereinfacht als Buttons)
        options = [
            ("WATERING", GREEN_LIGHT),
            ("LIGHTING", YELLOW),
            ("ALERTS", ORANGE),
            ("CALIBRATE", BLUE_LIGHT)
        ]
        
        y = 80
        for i, (option, color) in enumerate(options):
            self.draw_rounded_rect(20, y + i * 40, 280, 30, 5, color)
            
            # Option Text (vereinfacht)
            for j, char in enumerate(option):
                x = 40 + j * 20
                if char != ' ' and x < 280:
                    self.fill_rect(x, y + i * 40 + 8, 15, 15, BLACK)
        
        # Touch-Navigation (nur im Manual-Modus)
        if self.manual_mode:
            # Back Button
            self.draw_rounded_rect(20, 210, 80, 30, 5, RED)
            self.fill_rect(30, 220, 60, 10, WHITE)  # "BACK"
            
            # Details Button
            self.draw_rounded_rect(220, 210, 80, 30, 5, BLUE_LIGHT)
            self.fill_rect(230, 220, 60, 10, WHITE)  # "DETAILS"

    def update_sensor_data(self):
        """Aktualisiert Sensordaten - kombiniert echte und simulierte Werte"""
        import random
        
        # Echte Lichtsensor-Daten lesen
        light_value, light_voltage, light_raw = self.read_light_sensor()
        self.sensor_data['light'] = light_value
        self.sensor_data['light_voltage'] = light_voltage
        self.sensor_data['light_raw'] = light_raw
        
        # Debug-Ausgabe für Lichtsensor
        print(f"Licht: {light_value} Lux, {light_voltage:.2f}V, Raw: {light_raw}")
        
        # Simuliere andere Sensordaten
        self.sensor_data['temperature'] += random.uniform(-0.5, 0.5)
        self.sensor_data['temperature'] = max(15, min(35, self.sensor_data['temperature']))
        
        self.sensor_data['humidity'] += random.uniform(-2, 2)
        self.sensor_data['humidity'] = max(30, min(90, self.sensor_data['humidity']))
        
        self.sensor_data['soil_moisture'] += random.uniform(-1, 1)
        self.sensor_data['soil_moisture'] = max(20, min(80, self.sensor_data['soil_moisture']))
        
        # Berechne Pflanzengesundheit basierend auf echten und simulierten Sensordaten
        health = 100
        if self.sensor_data['soil_moisture'] < 30:
            health -= 20
        if self.sensor_data['temperature'] < 18 or self.sensor_data['temperature'] > 28:
            health -= 15
        if light_value < 300:  # Verwende echte Lichtwerte
            health -= 10
        
        self.sensor_data['plant_health'] = max(0, min(100, health))

    def handle_touch(self, x, y):
        """Behandelt Touch-Eingaben basierend auf aktuellem Screen"""
        print(f"Touch at: {x}, {y} on screen {self.current_screen}")
        
        # Touch aktiviert manuellen Modus
        old_screen = self.current_screen
        self.manual_mode = True
        self.last_touch_time = time.ticks_ms()
        
        if self.current_screen == 0:  # Main Screen
            # Widget-Bereiche prüfen
            if 50 <= y <= 130:  # Erste Widget-Reihe
                if 10 <= x <= 100:      # Temperatur-Widget
                    self.current_screen = 1  # Zu Details
                elif 110 <= x <= 200:   # Humidity-Widget  
                    self.current_screen = 1
                elif 210 <= x <= 300:   # Soil-Widget
                    self.current_screen = 1
            elif 140 <= y <= 220:  # Zweite Widget-Reihe  
                if 10 <= x <= 100:      # Licht-Widget
                    self.current_screen = 1  # Zu Details
                elif 110 <= x <= 300:   # Pflanzenstatus-Widget
                    self.current_screen = 1
                    
            # Navigation-Buttons
            elif 200 <= y <= 230:  # Button-Reihe
                if 10 <= x <= 70:      # Back Button
                    self.current_screen = 2  # Zu Settings
                elif 250 <= x <= 310:  # Next Button
                    self.current_screen = 1  # Zu Details
                    
        elif self.current_screen == 1:  # Detail Screen
            # Navigation-Buttons prüfen
            if 200 <= y <= 230:  # Button-Reihe
                if 20 <= x <= 100:     # Back Button
                    self.current_screen = 0  # Zu Main
                elif 220 <= x <= 300:  # Settings Button
                    self.current_screen = 2  # Zu Settings
            # Tippen irgendwo anders geht auch zurück
            elif y > 150:
                self.current_screen = 0
                
        elif self.current_screen == 2:  # Settings Screen  
            # Settings-Optionen
            if 50 <= y <= 210:
                option_index = (y - 50) // 40
                if 0 <= option_index <= 3 and 20 <= x <= 300:
                    print(f"Settings option {option_index} selected")
                    # Hier könnten Settings-Aktionen implementiert werden
                    
            # Navigation-Buttons prüfen
            elif 210 <= y <= 240:  # Button-Reihe
                if 20 <= x <= 100:     # Back Button
                    self.current_screen = 0  # Zu Main
                elif 220 <= x <= 300:  # Details Button
                    self.current_screen = 1  # Zu Details
        
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
        screen_count = 3
        last_screen_change = time.ticks_ms()
        screen_duration = 180000  # 3 Minuten pro Screen (nur im Auto-Modus)
        last_touch_pos = None
        
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
            
            # Screen nur im Auto-Modus automatisch wechseln
            if not self.manual_mode and time.ticks_diff(current_time, last_screen_change) > screen_duration:
                old_screen = self.current_screen
                self.current_screen = (self.current_screen + 1) % screen_count
                last_screen_change = current_time
                print(f"Auto-Wechsel zu Screen {self.current_screen}")
                if old_screen != self.current_screen:
                    self.screen_needs_redraw = True
            
            # Screen nur neu zeichnen wenn nötig
            if self.screen_needs_redraw or self.last_drawn_screen != self.current_screen:
                if self.current_screen == 0:
                    self.show_main_screen()
                elif self.current_screen == 1:
                    self.show_detail_screen()
                else:
                    self.show_settings_screen()
                
                self.last_drawn_screen = self.current_screen
                self.screen_needs_redraw = False
                print(f"Screen {self.current_screen} neu gezeichnet")
            
            time.sleep(0.2)  # Längere Pause für weniger Last


def main():
    print("=== Smart Plant UI mit Touch ===")
    
    # Display Pin-Konfiguration
    dc_pin = machine.Pin(17, machine.Pin.OUT)
    reset_pin = machine.Pin(20, machine.Pin.OUT)
    cs_pin = machine.Pin(21, machine.Pin.OUT)
    
    # Touch Pin-Konfiguration
    touch_cs_pin = machine.Pin(1, machine.Pin.OUT)   # T_CS
    touch_irq_pin = machine.Pin(6, machine.Pin.IN)   # T_IRQ
    
    # SPI-Konfiguration für Display
    display_spi = machine.SPI(0, 
                      baudrate=20000000,
                      polarity=0, 
                      phase=0)
    
    # SPI-Konfiguration für Touch (langsamere Geschwindigkeit)
    touch_spi = machine.SPI(0,
                      baudrate=1000000,  # Langsamere Geschwindigkeit für Touch
                      polarity=0,
                      phase=0)
    
    # Touch-Controller erstellen
    touch = TouchController(touch_spi, touch_cs_pin, touch_irq_pin)
    
    # Display erstellen und initialisieren
    plant_ui = SmartPlantDisplay(display_spi, dc_pin, reset_pin, cs_pin, touch)
    plant_ui.init()
    
    print("Touch-Controller konfiguriert:")
    print("  T_CS: GP1")
    print("  T_IRQ: GP6") 
    print("  T_CLK: GP2 (SPI SCK)")
    print("  T_DIN: GP3 (SPI TX)")
    print("  T_DO: GP5 (SPI RX)")
    
    print("Lichtsensor konfiguriert:")
    print("  LDR: GP28 (ADC2)")
    
    print("Starte Pflanzentopf UI mit Touch und Lichtsensor...")
    print("Tippen Sie auf das Display für manuelle Steuerung!")
    print("Lichtsensor zeigt echte Werte an!")
    
    try:
        plant_ui.run_ui()
    except KeyboardInterrupt:
        print("UI beendet")
        plant_ui.fill(BLACK)


if __name__ == "__main__":
    main()
