import machine
import time
from micropython import const
import ustruct as struct

# ILI9341 commands - spezifisch für TPM408-2.8
ILI9341_SWRESET = const(0x01)
ILI9341_RDDID = const(0x04)
ILI9341_RDDST = const(0x09)

ILI9341_SLPIN = const(0x10)
ILI9341_SLPOUT = const(0x11)
ILI9341_PTLON = const(0x12)
ILI9341_NORON = const(0x13)

ILI9341_RDMODE = const(0x0A)
ILI9341_RDMADCTL = const(0x0B)
ILI9341_RDPIXFMT = const(0x0C)
ILI9341_RDIMGFMT = const(0x0D)
ILI9341_RDSELFDIAG = const(0x0F)

ILI9341_INVOFF = const(0x20)
ILI9341_INVON = const(0x21)
ILI9341_GAMMASET = const(0x26)
ILI9341_DISPOFF = const(0x28)
ILI9341_DISPON = const(0x29)

ILI9341_CASET = const(0x2A)
ILI9341_PASET = const(0x2B)
ILI9341_RAMWR = const(0x2C)
ILI9341_RAMRD = const(0x2E)

ILI9341_PTLAR = const(0x30)
ILI9341_MADCTL = const(0x36)
ILI9341_PIXFMT = const(0x3A)

ILI9341_FRMCTR1 = const(0xB1)
ILI9341_FRMCTR2 = const(0xB2)
ILI9341_FRMCTR3 = const(0xB3)
ILI9341_INVCTR = const(0xB4)
ILI9341_DFUNCTR = const(0xB6)

ILI9341_PWCTR1 = const(0xC0)
ILI9341_PWCTR2 = const(0xC1)
ILI9341_PWCTR3 = const(0xC2)
ILI9341_PWCTR4 = const(0xC3)
ILI9341_PWCTR5 = const(0xC4)
ILI9341_VMCTR1 = const(0xC5)
ILI9341_VMCTR2 = const(0xC7)

ILI9341_RDID1 = const(0xDA)
ILI9341_RDID2 = const(0xDB)
ILI9341_RDID3 = const(0xDC)
ILI9341_RDID4 = const(0xDD)

ILI9341_GMCTRP1 = const(0xE0)
ILI9341_GMCTRN1 = const(0xE1)

# MADCTL bits
MADCTL_MY = const(0x80)
MADCTL_MX = const(0x40)
MADCTL_MV = const(0x20)
MADCTL_ML = const(0x10)
MADCTL_BGR = const(0x08)
MADCTL_MH = const(0x04)

# Color definitions
BLACK = const(0x0000)
BLUE = const(0x001F)
RED = const(0xF800)
GREEN = const(0x07E0)
CYAN = const(0x07FF)
MAGENTA = const(0xF81F)
YELLOW = const(0xFFE0)
WHITE = const(0xFFFF)

_ENCODE_PIXEL = ">H"
_ENCODE_POS = ">HH"


def delay_ms(ms):
    time.sleep_ms(ms)


def color565(r, g=0, b=0):
    """Convert red, green and blue values (0-255) into a 16-bit 565 encoding."""
    try:
        r, g, b = r  # see if the first var is a tuple/list
    except TypeError:
        pass
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3


class ILI9341:
    def __init__(self, spi, dc, reset, cs=None, width=320, height=240):
        self.spi = spi
        self.dc = dc
        self.reset = reset
        self.cs = cs
        self.width = width
        self.height = height

    def dc_low(self):
        self.dc.off()

    def dc_high(self):
        self.dc.on()

    def reset_low(self):
        if self.reset:
            self.reset.off()

    def reset_high(self):
        if self.reset:
            self.reset.on()

    def cs_low(self):
        if self.cs:
            self.cs.off()

    def cs_high(self):
        if self.cs:
            self.cs.on()

    def write_cmd(self, cmd):
        """Write command"""
        self.cs_low()
        self.dc_low()
        self.spi.write(bytes([cmd]))
        self.cs_high()

    def write_data(self, data):
        """Write data"""
        self.cs_low()
        self.dc_high()
        if isinstance(data, int):
            self.spi.write(bytes([data]))
        else:
            self.spi.write(data)
        self.cs_high()

    def write_cmd_data(self, cmd, data=None):
        """Write command followed by data"""
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

    def hard_reset(self):
        """Hardware reset sequence"""
        print("Hardware Reset...")
        if self.reset:
            self.reset_high()
            delay_ms(10)
            self.reset_low()
            delay_ms(100)
            self.reset_high()
            delay_ms(100)

    def init(self):
        """Initialize ILI9341 display"""
        print("Initialisiere ILI9341...")
        
        # Hardware Reset
        self.hard_reset()
        
        # Software Reset
        print("Software Reset...")
        self.write_cmd(ILI9341_SWRESET)
        delay_ms(150)
        
        # Exit Sleep Mode
        print("Exit Sleep Mode...")
        self.write_cmd(ILI9341_SLPOUT)
        delay_ms(120)
        
        # Power Control A
        print("Power Control A...")
        self.write_cmd_data(0xCB, bytes([0x39, 0x2C, 0x00, 0x34, 0x02]))
        
        # Power Control B
        print("Power Control B...")
        self.write_cmd_data(0xCF, bytes([0x00, 0xC1, 0x30]))
        
        # Driver Timing Control A
        print("Driver Timing Control A...")
        self.write_cmd_data(0xE8, bytes([0x85, 0x00, 0x78]))
        
        # Driver Timing Control B
        print("Driver Timing Control B...")
        self.write_cmd_data(0xEA, bytes([0x00, 0x00]))
        
        # Power on Sequence Control
        print("Power on Sequence Control...")
        self.write_cmd_data(0xED, bytes([0x64, 0x03, 0x12, 0x81]))
        
        # Pump Ratio Control
        print("Pump Ratio Control...")
        self.write_cmd_data(0xF7, 0x20)
        
        # Power Control 1
        print("Power Control 1...")
        self.write_cmd_data(ILI9341_PWCTR1, 0x23)
        
        # Power Control 2
        print("Power Control 2...")
        self.write_cmd_data(ILI9341_PWCTR2, 0x10)
        
        # VCOM Control 1
        print("VCOM Control 1...")
        self.write_cmd_data(ILI9341_VMCTR1, bytes([0x3e, 0x28]))
        
        # VCOM Control 2
        print("VCOM Control 2...")
        self.write_cmd_data(ILI9341_VMCTR2, 0x86)
        
        # Memory Access Control
        print("Memory Access Control...")
        self.write_cmd_data(ILI9341_MADCTL, MADCTL_MX | MADCTL_BGR)
        
        # Pixel Format Set
        print("Pixel Format Set...")
        self.write_cmd_data(ILI9341_PIXFMT, 0x55)  # 16 bit
        
        # Frame Rate Control
        print("Frame Rate Control...")
        self.write_cmd_data(ILI9341_FRMCTR1, bytes([0x00, 0x18]))
        
        # Display Function Control
        print("Display Function Control...")
        self.write_cmd_data(ILI9341_DFUNCTR, bytes([0x08, 0x82, 0x27]))
        
        # Gamma Set
        print("Gamma Set...")
        self.write_cmd_data(ILI9341_GAMMASET, 0x01)
        
        # Positive Gamma Correction
        print("Positive Gamma Correction...")
        self.write_cmd_data(ILI9341_GMCTRP1, bytes([
            0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1,
            0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00
        ]))
        
        # Negative Gamma Correction
        print("Negative Gamma Correction...")
        self.write_cmd_data(ILI9341_GMCTRN1, bytes([
            0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1,
            0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F
        ]))
        
        # Sleep Out
        print("Sleep Out...")
        self.write_cmd(ILI9341_SLPOUT)
        delay_ms(120)
        
        # Display On
        print("Display On...")
        self.write_cmd(ILI9341_DISPON)
        delay_ms(100)
        
        print("ILI9341 Initialisierung abgeschlossen!")

    def set_window(self, x0, y0, x1, y1):
        """Set display window"""
        # Column Address Set
        self.write_cmd_data(ILI9341_CASET, struct.pack(">HH", x0, x1))
        # Page Address Set
        self.write_cmd_data(ILI9341_PASET, struct.pack(">HH", y0, y1))
        # Memory Write
        self.write_cmd(ILI9341_RAMWR)

    def pixel(self, x, y, color):
        """Set single pixel"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.set_window(x, y, x, y)
            self.write_data(struct.pack(">H", color))

    def fill_rect(self, x, y, w, h, color):
        """Fill rectangle with color"""
        if x + w > self.width:
            w = self.width - x
        if y + h > self.height:
            h = self.height - y
        
        self.set_window(x, y, x + w - 1, y + h - 1)
        
        # Send color data
        pixel_data = struct.pack(">H", color)
        total_pixels = w * h
        
        self.cs_low()
        self.dc_high()
        for _ in range(total_pixels):
            self.spi.write(pixel_data)
        self.cs_high()

    def fill(self, color):
        """Fill entire screen with color"""
        self.fill_rect(0, 0, self.width, self.height, color)

    def hline(self, x, y, w, color):
        """Draw horizontal line"""
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        """Draw vertical line"""
        self.fill_rect(x, y, 1, h, color)

    def line(self, x0, y0, x1, y1, color):
        """Draw line using Bresenham algorithm"""
        steep = abs(y1 - y0) > abs(x1 - x0)
        if steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1
        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0
        dx = x1 - x0
        dy = abs(y1 - y0)
        err = dx // 2
        ystep = 1 if y0 < y1 else -1
        
        while x0 <= x1:
            if steep:
                self.pixel(y0, x0, color)
            else:
                self.pixel(x0, y0, color)
            err -= dy
            if err < 0:
                y0 += ystep
                err += dx
            x0 += 1


def main():
    print("=== ILI9341 TPM408-2.8 Test ===")
    
    # Pin-Konfiguration
    print("Konfiguriere Pins...")
    dc_pin = machine.Pin(17, machine.Pin.OUT)
    reset_pin = machine.Pin(20, machine.Pin.OUT)
    cs_pin = machine.Pin(21, machine.Pin.OUT)
    
    # SPI-Konfiguration
    print("Konfiguriere SPI...")
    spi = machine.SPI(0, 
                      baudrate=20000000,  # 20MHz für ILI9341
                      polarity=0, 
                      phase=0)
    
    # Display erstellen
    print("Erstelle Display-Objekt...")
    display = ILI9341(spi=spi,
                      dc=dc_pin,
                      reset=reset_pin,
                      cs=cs_pin,
                      width=320,
                      height=240)
    
    # Display initialisieren
    print("Initialisiere Display...")
    display.init()
    
    # Tests durchführen
    print("Starte Tests...")
    
    try:
        # Test 1: Vollfarben
        print("Test 1: Vollfarben...")
        colors = [BLACK, RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA, WHITE]
        color_names = ["Schwarz", "Rot", "Grün", "Blau", "Gelb", "Cyan", "Magenta", "Weiß"]
        
        for color, name in zip(colors, color_names):
            print(f"  Fülle mit {name}...")
            display.fill(color)
            time.sleep(1)
        
        # Test 2: Pixel in Ecken
        print("Test 2: Pixel in Ecken...")
        display.fill(BLACK)
        display.pixel(0, 0, WHITE)        # Oben links
        display.pixel(319, 0, RED)        # Oben rechts
        display.pixel(0, 239, GREEN)      # Unten links
        display.pixel(319, 239, BLUE)    # Unten rechts
        display.pixel(160, 120, YELLOW)  # Mitte
        time.sleep(2)
        
        # Test 3: Linien
        print("Test 3: Linien...")
        display.fill(BLACK)
        display.hline(0, 120, 320, RED)     # Horizontale Linie
        display.vline(160, 0, 240, GREEN)   # Vertikale Linie
        display.line(0, 0, 319, 239, BLUE) # Diagonale
        display.line(0, 239, 319, 0, YELLOW) # Andere Diagonale
        time.sleep(2)
        
        # Test 4: Rechtecke
        print("Test 4: Rechtecke...")
        display.fill(BLACK)
        display.fill_rect(10, 10, 100, 80, RED)
        display.fill_rect(120, 10, 100, 80, GREEN)
        display.fill_rect(230, 10, 80, 80, BLUE)
        display.fill_rect(10, 100, 100, 80, YELLOW)
        display.fill_rect(120, 100, 100, 80, CYAN)
        display.fill_rect(230, 100, 80, 80, MAGENTA)
        time.sleep(2)
        
        print("Alle Tests abgeschlossen!")
        
    except Exception as e:
        print(f"Fehler bei Tests: {e}")


if __name__ == "__main__":
    main()
