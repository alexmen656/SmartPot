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

def delay_ms(ms):
    time.sleep_ms(ms)

def color565(r, g=0, b=0):
    """Convert RGB to 565 format"""
    try:
        r, g, b = r
    except TypeError:
        pass
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3

class SmartPlantDisplay:
    def __init__(self, spi, dc, reset, cs=None):
        self.spi = spi
        self.dc = dc
        self.reset = reset
        self.cs = cs
        self.width = 320
        self.height = 240
        self.current_screen = 0
        self.last_update = 0
        
        # Simulierte Sensordaten
        self.sensor_data = {
            'temperature': 22.5,
            'humidity': 65,
            'soil_moisture': 45,
            'light': 750,
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
        digit_width = size * 7
        
        for i, digit_char in enumerate(num_str):
            digit = int(digit_char)
            self.draw_digit(x + i * digit_width, y, digit, size, color)

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

    def show_main_screen(self):
        """Hauptbildschirm mit Übersicht"""
        self.fill(BLACK)
        
        # Header
        self.fill_rect(0, 0, 320, 40, GREEN_DARK)
        
        # Titel-Text (vereinfacht)
        for i, char in enumerate("SMART PLANT"):
            x = 20 + i * 25
            if char != ' ':
                self.fill_rect(x, 10, 20, 20, WHITE)
        
        # Haupt-Widgets
        y_start = 50
        
        # Temperatur Widget
        self.draw_rounded_rect(10, y_start, 90, 80, 8, GRAY_LIGHT)
        self.draw_icon_temperature(20, y_start + 10, 30, ORANGE)
        self.draw_number(20, y_start + 45, self.sensor_data['temperature'], 2, ORANGE)
        
        # Luftfeuchtigkeit Widget  
        self.draw_rounded_rect(110, y_start, 90, 80, 8, GRAY_LIGHT)
        self.draw_icon_water(120, y_start + 10, 30, BLUE_LIGHT)
        self.draw_number(120, y_start + 45, self.sensor_data['humidity'], 2, BLUE_LIGHT)
        
        # Bodenfeuchtigkeit Widget
        self.draw_rounded_rect(210, y_start, 90, 80, 8, GRAY_LIGHT)
        self.draw_icon_plant(220, y_start + 10, 30, GREEN_LIGHT)
        self.draw_number(220, y_start + 45, self.sensor_data['soil_moisture'], 2, GREEN_LIGHT)
        
        # Licht Widget
        self.draw_rounded_rect(10, y_start + 90, 90, 80, 8, GRAY_LIGHT)
        self.draw_icon_sun(20, y_start + 100, 30, YELLOW)
        self.draw_number(20, y_start + 135, self.sensor_data['light'], 1, YELLOW)
        
        # Pflanzenstatus
        self.draw_rounded_rect(110, y_start + 90, 190, 80, 8, GRAY_LIGHT)
        health = self.sensor_data['plant_health']
        
        if health > 80:
            status_color = GREEN_LIGHT
        elif health > 60:
            status_color = YELLOW
        else:
            status_color = RED
            
        # Gesundheits-Fortschrittsbalken
        self.draw_progress_bar(120, y_start + 110, 170, 20, health, 100, GRAY_DARK, status_color)
        
        # Status-Text (vereinfacht)
        if health > 80:
            status_text = "EXCELLENT"
        elif health > 60:
            status_text = "GOOD"
        else:
            status_text = "NEEDS CARE"
            
        for i, char in enumerate(status_text):
            x = 130 + i * 12
            if char != ' ' and x < 290:
                self.fill_rect(x, y_start + 140, 8, 15, status_color)

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
        
        # Wassertank-Level
        self.fill_rect(10, y, 300, 40, GRAY_LIGHT)
        self.draw_icon_water(20, y + 5, 30, BLUE_LIGHT)
        water_level = self.sensor_data['water_level']
        self.draw_progress_bar(70, y + 10, 200, 20, water_level, 100, GRAY_DARK, BLUE_LIGHT)
        self.draw_number(280, y + 15, water_level, 2, BLUE_LIGHT)

    def show_settings_screen(self):
        """Einstellungsbildschirm"""
        self.fill(BLACK)
        
        # Header
        self.fill_rect(0, 0, 320, 35, RED)
        
        # Einstellungsoptionen (vereinfacht als Buttons)
        options = [
            ("WATERING", GREEN_LIGHT),
            ("LIGHTING", YELLOW),
            ("ALERTS", ORANGE),
            ("CALIBRATE", BLUE_LIGHT)
        ]
        
        y = 50
        for i, (option, color) in enumerate(options):
            self.draw_rounded_rect(20, y + i * 40, 280, 30, 5, color)
            
            # Option Text (vereinfacht)
            for j, char in enumerate(option):
                x = 40 + j * 20
                if char != ' ' and x < 280:
                    self.fill_rect(x, y + i * 40 + 8, 15, 15, BLACK)

    def update_sensor_data(self):
        """Simuliert Sensor-Updates"""
        import random
        
        # Simuliere realistische Schwankungen
        self.sensor_data['temperature'] += random.uniform(-0.5, 0.5)
        self.sensor_data['temperature'] = max(15, min(35, self.sensor_data['temperature']))
        
        self.sensor_data['humidity'] += random.uniform(-2, 2)
        self.sensor_data['humidity'] = max(30, min(90, self.sensor_data['humidity']))
        
        self.sensor_data['soil_moisture'] += random.uniform(-1, 1)
        self.sensor_data['soil_moisture'] = max(20, min(80, self.sensor_data['soil_moisture']))
        
        self.sensor_data['light'] += random.uniform(-50, 50)
        self.sensor_data['light'] = max(100, min(1000, self.sensor_data['light']))
        
        # Berechne Pflanzengesundheit basierend auf Sensordaten
        health = 100
        if self.sensor_data['soil_moisture'] < 30:
            health -= 20
        if self.sensor_data['temperature'] < 18 or self.sensor_data['temperature'] > 28:
            health -= 15
        if self.sensor_data['light'] < 300:
            health -= 10
        
        self.sensor_data['plant_health'] = max(0, min(100, health))

    def run_ui(self):
        """Hauptschleife für das UI"""
        screen_count = 3
        last_screen_change = time.ticks_ms()
        screen_duration = 5000  # 5 Sekunden pro Screen
        
        while True:
            current_time = time.ticks_ms()
            
            # Sensordaten alle 2 Sekunden aktualisieren
            if time.ticks_diff(current_time, self.last_update) > 2000:
                self.update_sensor_data()
                self.last_update = current_time
            
            # Screen alle 5 Sekunden wechseln
            if time.ticks_diff(current_time, last_screen_change) > screen_duration:
                self.current_screen = (self.current_screen + 1) % screen_count
                last_screen_change = current_time
            
            # Entsprechenden Screen anzeigen
            if self.current_screen == 0:
                self.show_main_screen()
            elif self.current_screen == 1:
                self.show_detail_screen()
            else:
                self.show_settings_screen()
            
            time.sleep(0.1)  # Kurze Pause


def main():
    print("=== Smart Plant UI ===")
    
    # Pin-Konfiguration
    dc_pin = machine.Pin(17, machine.Pin.OUT)
    reset_pin = machine.Pin(20, machine.Pin.OUT)
    cs_pin = machine.Pin(21, machine.Pin.OUT)
    
    # SPI-Konfiguration
    spi = machine.SPI(0, 
                      baudrate=20000000,
                      polarity=0, 
                      phase=0)
    
    # Display erstellen und initialisieren
    plant_ui = SmartPlantDisplay(spi, dc_pin, reset_pin, cs_pin)
    plant_ui.init()
    
    print("Starte Pflanzentopf UI...")
    
    try:
        plant_ui.run_ui()
    except KeyboardInterrupt:
        print("UI beendet")
        plant_ui.fill(BLACK)


if __name__ == "__main__":
    main()
