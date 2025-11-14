
# main.py — RESTORED (no math breathing, WDT disabled, Hugh=GRB, correct colors)
# Requires: functions.py, data.py, argbled_lib

import network
import time
import gc
from argbled_lib import Argbled
import data
import functions as fn
from machine import WDT
# ------------------------- DEBUG -------------------------
DEBUG = True
def debug(*args):
    if DEBUG:
        print('[DEBUG]', *args)

# ------------------------- USER CONFIG -------------------------
SSID = 'iSpiWiFi'               # << change
PASSWORD = 'cbx2evq.zvd!HCE!dty' # << change

# Hardware selection
mapType = 'Hugh'   # change to 'Archie' for alt config

if mapType == 'Hugh':
    LED_COUNT      = 100
    LED_PIN        = 1
    LED_BRIGHTNESS = 20
    LED_ORDER      = 'GRB'   # corrected
else:
    LED_COUNT      = 100
    LED_PIN        = 0
    LED_BRIGHTNESS = 75
    LED_ORDER      = 'GRB'

# METAR fetch settings
API_BASE = 'https://aviationweather.gov/api/data/metar?ids={ids}&format=json'

# Chunking
CHUNK_SIZE = 25
FETCH_INTERVAL_S = 900

# Wind/LTG animation
ACTIVATE_WIND_ANIM      = True
ACTIVATE_LIGHTNING_ANIM = True
FADE_INSTEAD_OF_BLINK   = True
WIND_BLINK_THRESHOLD    = 15
HIGH_WINDS_THRESHOLD    = 30
ALWAYS_BLINK_FOR_GUSTS  = False
BLINK_SPEED_S           = 0.3
BLINK_TOTAL_TIME_S      = 900

# Dimming (time-window only; no sun calc)
ACTIVATE_DAYTIME_DIMMING = True
BRIGHT_TIME_START = (7, 0)
DIM_TIME_START    = (21, 0)
LED_BRIGHTNESS_DIM = 0.5
USE_SUNRISE_SUNSET  = False

# Legend control (optional)
SHOW_LEGEND = True
LEGEND_INDEXES = {
    "VFR": 92, "MVFR": 93, "IFR": 94, "LIFR": 95, "LTG": 96, "WIND": 97, "HIGH": 98
}

# ------------------------- STATE MACHINE -------------------------
STATE_WIFI_CONNECTING   = 0
STATE_NORMAL            = 1
STATE_API_CLIENT_ERROR  = 2   # 400/404
STATE_API_RATE_LIMIT    = 3   # 429
STATE_API_SERVER_ERROR  = 4   # 5xx + unknown

system_state = STATE_WIFI_CONNECTING
backoff_seconds = 30

# ------------------------- COLORS (Correct RGB) -------------------------
COLOR_VFR         = (0, 255, 0)     # Green
COLOR_VFR_FADE    = (0, 80, 0)
COLOR_MVFR        = (0, 0, 255)     # Blue
COLOR_MVFR_FADE   = (0, 0, 80)
COLOR_IFR         = (255, 0, 0)     # Red
COLOR_IFR_FADE    = (80, 0, 0)
COLOR_LIFR        = (255, 0, 255)   # Magenta
COLOR_LIFR_FADE   = (80, 0, 80)
COLOR_CLEAR       = (0, 0, 0)
COLOR_LIGHTNING   = (255, 255, 255) # White
COLOR_HIGH_WINDS  = (255, 255, 0)   # Yellow

# Status palette (all-LEDs)
COLOR_TEAL        = (0, 40, 40)     # WiFi connecting
COLOR_ORANGE      = (255, 80, 0)    # 400/404
COLOR_AMBER       = (255, 150, 0)   # 429
COLOR_WARMWHITE   = (80, 70, 50)    # 5xx

# ------------------------- SETUP -------------------------
gc.enable()
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

pixels = Argbled(LED_COUNT, 0, LED_PIN, LED_ORDER)
pixels.brightness(LED_BRIGHTNESS)
pixels.fill(COLOR_CLEAR)
pixels.show()

# Watchdog DISABLED for development
class DummyWDT:
    def feed(self): pass
wdt = DummyWDT()

# Provide colors to functions module
fn.init_globals(
    pixels=pixels,
    led_count=LED_COUNT,
    color_clear=COLOR_CLEAR,
    color_vfr=COLOR_VFR, color_mvfr=COLOR_MVFR, color_ifr=COLOR_IFR, color_lifr=COLOR_LIFR,
    color_vfr_fade=COLOR_VFR_FADE, color_mvfr_fade=COLOR_MVFR_FADE,
    color_ifr_fade=COLOR_IFR_FADE, color_lifr_fade=COLOR_LIFR_FADE,
    color_lightning=COLOR_LIGHTNING, color_high_winds=COLOR_HIGH_WINDS,
    show_legend=SHOW_LEGEND, legend_indexes=LEGEND_INDEXES,
    wind_threshold=WIND_BLINK_THRESHOLD, high_wind_threshold=HIGH_WINDS_THRESHOLD,
    gusts_always=ALWAYS_BLINK_FOR_GUSTS, fade_instead=FADE_INSTEAD_OF_BLINK,
    wind_anim=ACTIVATE_WIND_ANIM, ltg_anim=ACTIVATE_LIGHTNING_ANIM,
    blink_speed=BLINK_SPEED_S, blink_total=BLINK_TOTAL_TIME_S
)

# ------------------------- STATUS HELPERS -------------------------
def show_all(color):
    for i in range(LED_COUNT):
        pixels.set_pixel(i, color)
    pixels.show()

def blink_all(color, interval=0.6):
    show_all(color)
    time.sleep(interval)
    show_all(COLOR_CLEAR)
    time.sleep(interval)

def pulse_all(color, steps=40, delay=0.01):
    r,g,b = color
    for i in range(steps):
        level = i / steps
        pixels.fill((int(r*level), int(g*level), int(b*level)))
        pixels.show()
        time.sleep(delay)
    for i in range(steps, -1, -1):
        level = i / steps
        pixels.fill((int(r*level), int(g*level), int(b*level)))
        pixels.show()
        time.sleep(delay)

def update_display():
    if system_state == STATE_WIFI_CONNECTING:
        blink_all(COLOR_TEAL, 0.4)
    elif system_state == STATE_API_CLIENT_ERROR:
        show_all(COLOR_ORANGE)
        time.sleep(0.4)
    elif system_state == STATE_API_RATE_LIMIT:
        pulse_all(COLOR_AMBER, steps=25, delay=0.02)
    elif system_state == STATE_API_SERVER_ERROR:
        show_all(COLOR_WARMWHITE)
        time.sleep(0.4)
    elif system_state == STATE_NORMAL:
        fn.render_weather_frame()
    else:
        show_all(COLOR_WARMWHITE)

# ------------------------- WIFI -------------------------
def connect_wifi():
    global system_state
    debug("WiFi: Starting connection to", SSID)
    wlan.connect(SSID, PASSWORD)
    system_state = STATE_WIFI_CONNECTING

    for _ in range(80):
        if wlan.isconnected():
            debug('WiFi connected:', wlan.ifconfig())
            return True
        update_display()
        wdt.feed()
    debug("WiFi connection timeout")
    return False

# ------------------------- DIMMING -------------------------
def maybe_dim():
    if not USE_SUNRISE_SUNSET:
        if not ACTIVATE_DAYTIME_DIMMING:
            return
        hh = time.localtime()[3]
        mm = time.localtime()[4]
        debug('Hour:', hh, 'Minutes:', mm)
        bright_h, bright_m = BRIGHT_TIME_START
        dim_h, dim_m = DIM_TIME_START
        after_bright = (hh, mm) >= (bright_h, bright_m)
        after_dim = (hh, mm) >= (dim_h, dim_m)
        if after_dim or not after_bright:
            pixels.brightness(LED_BRIGHTNESS_DIM)
        else:
            pixels.brightness(LED_BRIGHTNESS)
        return
    # If sun-based dimming was enabled earlier, it's now disabled per request.

# ------------------------- FETCH -------------------------
def fetch_all_chunks():
    """Fetch METARs in chunks; updates data.leds in-place."""
    return_code = 200
    next_idx = 0
    total = len(data.leds)

    while next_idx < total:
        end = next_idx + CHUNK_SIZE
        if end > total:
            end = total

        ids = []
        for i in range(next_idx, end):
            ids.append(data.leds[i]['code'])
        ids_str = '%2C'.join(ids)

        url = API_BASE.format(ids=ids_str)
        code = fn.fetch_and_parse(url)

        if code != 200 and return_code == 200:
            return_code = code

        if code != 200:
            update_display()

        next_idx = end
        wdt.feed()
        gc.collect()

    return return_code

# ------------------------- MAIN -------------------------
def main():
    global system_state, backoff_seconds

    if not wlan.isconnected():
        ok = connect_wifi()
        if not ok:
            return

    maybe_dim()

    code = fetch_all_chunks()

    debug('Fetch result code:', code)
    if code == 200:
        system_state = STATE_NORMAL
        debug('STATE → NORMAL (data OK)')
        backoff_seconds = 30
    elif code in (400, 404):
        system_state = STATE_API_CLIENT_ERROR
        debug('STATE → CLIENT ERROR (400/404)')
    elif code == 429:
        system_state = STATE_API_RATE_LIMIT
        debug('STATE → RATE LIMIT (429), backoff:', backoff_seconds)
        time.sleep(backoff_seconds)
        backoff_seconds = backoff_seconds * 2 if backoff_seconds < 900 else 900
    elif code in (500, 502, 504):
        system_state = STATE_API_SERVER_ERROR
        debug('STATE → SERVER ERROR (5xx or unknown)')
    else:
        system_state = STATE_API_SERVER_ERROR
        debug('STATE → SERVER ERROR (5xx or unknown)')

    update_display()

# ------------------------- LOOP -------------------------
while True:
    try:
        main()
        if system_state == STATE_NORMAL:
            # keep animation going while waiting
            for _ in range(FETCH_INTERVAL_S):
                update_display()
                time.sleep(1)
                wdt.feed()
        else:
            time.sleep(1)
            wdt.feed()
    except Exception as e:
        system_state = STATE_API_SERVER_ERROR
        debug('STATE → SERVER ERROR (exception)')
        update_display()
        time.sleep(2)
        if not wlan.isconnected():
            connect_wifi()
        wdt.feed()
        gc.collect()


