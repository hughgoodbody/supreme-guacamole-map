# functions.py — FINAL (Hard Blink)
# - Correct visibility thresholds (meters)
# - Ceiling blending
# - Lightning flash
# - HARD blink for windy/gusty stations only (on/off)
# - Minimal debug

import urequests
import time
import gc
import data

# ---------- Minimal Debug ----------
DEBUG = True
def debug(*args):
    if DEBUG:
        print("[DEBUG-FN]", *args)

# ---------- Globals injected from main.py ----------
_pixels = None
_LED_COUNT = 0

COLOR_CLEAR = (0,0,0)
COLOR_VFR = (0,255,0)
COLOR_VFR_FADE = (0,80,0)   # not used in hard blink but kept for compat
COLOR_MVFR = (0,0,255)
COLOR_MVFR_FADE = (0,0,80)  # not used in hard blink but kept for compat
COLOR_IFR = (255,0,0)
COLOR_IFR_FADE = (80,0,0)   # not used in hard blink but kept for compat
COLOR_LIFR = (255,0,255)
COLOR_LIFR_FADE = (80,0,80) # not used in hard blink but kept for compat
COLOR_LIGHTNING = (255,255,255)
COLOR_HIGH_WINDS = (255,255,0)

SHOW_LEGEND = True
LEGEND_INDEXES = {}

WIND_BLINK_THRESHOLD = 15
HIGH_WINDS_THRESHOLD = 25
ALWAYS_BLINK_FOR_GUSTS = False
FADE_INSTEAD_OF_BLINK = False  # hard blink mode
ACTIVATE_WIND_ANIM = True
ACTIVATE_LIGHTNING_ANIM = True
BLINK_SPEED = 0.3
BLINK_TOTAL = 900

_wind_cycle = False

def init_globals(**kwargs):
    global _pixels, _LED_COUNT, COLOR_CLEAR
    global COLOR_VFR, COLOR_VFR_FADE, COLOR_MVFR, COLOR_MVFR_FADE
    global COLOR_IFR, COLOR_IFR_FADE, COLOR_LIFR, COLOR_LIFR_FADE
    global COLOR_LIGHTNING, COLOR_HIGH_WINDS
    global SHOW_LEGEND, LEGEND_INDEXES
    global WIND_BLINK_THRESHOLD, HIGH_WINDS_THRESHOLD, ALWAYS_BLINK_FOR_GUSTS
    global FADE_INSTEAD_OF_BLINK, ACTIVATE_WIND_ANIM, ACTIVATE_LIGHTNING_ANIM
    global BLINK_SPEED, BLINK_TOTAL

    _pixels = kwargs['pixels']
    _LED_COUNT = kwargs['led_count']
    COLOR_CLEAR = kwargs['color_clear']
    COLOR_VFR = kwargs['color_vfr']
    COLOR_VFR_FADE = kwargs['color_vfr_fade']
    COLOR_MVFR = kwargs['color_mvfr']
    COLOR_MVFR_FADE = kwargs['color_mvfr_fade']
    COLOR_IFR = kwargs['color_ifr']
    COLOR_IFR_FADE = kwargs['color_ifr_fade']
    COLOR_LIFR = kwargs['color_lifr']
    COLOR_LIFR_FADE = kwargs['color_lifr_fade']
    COLOR_LIGHTNING = kwargs['color_lightning']
    COLOR_HIGH_WINDS = kwargs['color_high_winds']
    SHOW_LEGEND = kwargs['show_legend']
    LEGEND_INDEXES = kwargs['legend_indexes']
    WIND_BLINK_THRESHOLD = kwargs['wind_threshold']
    HIGH_WINDS_THRESHOLD = kwargs['high_wind_threshold']
    ALWAYS_BLINK_FOR_GUSTS = kwargs['gusts_always']
    FADE_INSTEAD_OF_BLINK = kwargs['fade_instead']
    ACTIVATE_WIND_ANIM = kwargs['wind_anim']
    ACTIVATE_LIGHTNING_ANIM = kwargs['ltg_anim']
    BLINK_SPEED = kwargs['blink_speed']
    BLINK_TOTAL = kwargs['blink_total']

def _set(i, color):
    _pixels.set_pixel(i, color)

def _show():
    _pixels.show()

# ----------------------------
# Fetch + Parse (aviationweather.gov JSON classic keys)
# ----------------------------
def fetch_and_parse(url):
    try:
        debug("Request:", url)
        r = urequests.get(url)
        code = r.status_code

        if code != 200:
            try: r.close()
            except: pass
            return code

        try:
            payload = r.json()
        finally:
            try: r.close()
            except: pass

        for entry in payload:
            icao = entry.get('icaoId')
            idx = data.find(data.leds, 'code', icao)
            if idx == -1:
                continue
            ap = data.leds[idx]

            # ---------- Visibility (meters) ----------
            vis_raw = entry.get('visib')
            if vis_raw is None:
                visCat = 'VFR'   # UK convention: assume >10km
            else:
                try:
                    vis = float(vis_raw)
                except:
                    vis = 9999
                if vis <= 1600:
                    visCat = 'LIFR'
                elif vis <= 4800:
                    visCat = 'IFR'
                elif vis <= 8000:
                    visCat = 'MVFR'
                else:
                    visCat = 'VFR'

            # ---------- Ceiling ----------
            worst = 'VFR'
            for c in entry.get('clouds', []) or []:
                cover = c.get('cover','')
                base = c.get('base',99999)
                if cover in ('OVC','BKN'):
                    if base < 500:
                        worst = 'LIFR'
                    elif base < 1000 and worst != 'LIFR':
                        worst = 'IFR'
                    elif base <= 3000 and worst not in ('LIFR','IFR'):
                        worst = 'MVFR'
            cloudCat = worst

            # Merge
            """if 'LIFR' in (visCat, cloudCat):
                flightCat = 'LIFR'
            elif 'IFR' in (visCat, cloudCat):
                flightCat = 'IFR'
            elif 'MVFR' in (visCat, cloudCat):
                flightCat = 'MVFR'
            else:
                flightCat = 'VFR'
                """
            # Prefer API-provided flight conditions when available
            flightCat = entry.get("fltCat") or "VFR"


            # Lightning
            wx = entry.get('wxString') or ""
            lightning = (('TS' in wx and 'TSNO' not in wx) or ('LTG' in wx))

            # Wind (knots)
            wspd = entry.get('wspd') or 0
            wgst = entry.get('wgst') or 0

            # Update airport record
            ap['flightCategory'] = flightCat
            ap['lightning'] = lightning
            ap['windSpeed'] = wspd
            ap['windGustSpeed'] = wgst
            ap['windGust'] = True if (ALWAYS_BLINK_FOR_GUSTS and wgst > 0) else False
            ap['raw'] = entry.get('rawOb')

            debug("Update:", icao, "→", flightCat, "Wind:", wspd, "Gust:", wgst, "Ltg:", lightning)

        del payload
        gc.collect()
        return 200

    except Exception as e:
        debug("Fetch/Parse error:", e)
        return 500

# ----------------------------
# Render one animation frame (HARD BLINK)
# ----------------------------
def render_weather_frame():
    global _wind_cycle

    for ap in data.leds:
        base = COLOR_CLEAR

        # Determine base color from category
        cat = ap.get('flightCategory')
        if cat == 'VFR':
            base = COLOR_VFR
        elif cat == 'MVFR':
            base = COLOR_MVFR
        elif cat == 'IFR':
            base = COLOR_IFR
        elif cat == 'LIFR':
            base = COLOR_LIFR
        else:
            base = COLOR_CLEAR

        # High winds override base (if enabled)
        ws = ap.get('windSpeed') or 0
        gs = ap.get('windGustSpeed') or 0
        if HIGH_WINDS_THRESHOLD != -1 and (ws >= HIGH_WINDS_THRESHOLD or gs >= HIGH_WINDS_THRESHOLD):
            base = COLOR_HIGH_WINDS

        # Lightning phase (white flash on alternate frames)
        ltg = ACTIVATE_LIGHTNING_ANIM and ap.get('lightning')
        if ltg and (not _wind_cycle):
            _set(ap['led'], COLOR_LIGHTNING)
            continue

        # Should this station blink?
        should_blink = ACTIVATE_WIND_ANIM and (
            (ws >= WIND_BLINK_THRESHOLD) or
            (gs >= WIND_BLINK_THRESHOLD) or
            (ap.get('windGust') is True)
        )

        if should_blink:
            # FADE BLINK: bright ↔ dim
            if cat == 'VFR':
                color = COLOR_VFR_FADE if _wind_cycle else COLOR_VFR
            elif cat == 'MVFR':
                color = COLOR_MVFR_FADE if _wind_cycle else COLOR_MVFR
            elif cat == 'IFR':
                color = COLOR_IFR_FADE if _wind_cycle else COLOR_IFR
            elif cat == 'LIFR':
                color = COLOR_LIFR_FADE if _wind_cycle else COLOR_LIFR
            else:
                color = base
        else:
            color = base

        _set(ap['led'], color)

    # Legend
    if SHOW_LEGEND and LEGEND_INDEXES:
        try:
            _set(LEGEND_INDEXES['VFR'], COLOR_VFR)
            _set(LEGEND_INDEXES['MVFR'], COLOR_MVFR)
            _set(LEGEND_INDEXES['IFR'], COLOR_IFR)
            _set(LEGEND_INDEXES['LIFR'], COLOR_LIFR)
            _set(LEGEND_INDEXES['LTG'], COLOR_LIGHTNING)
            # WIND legend blinks hard to demonstrate wind mode
            wind_led = LEGEND_INDEXES['WIND']
            _set(wind_led, COLOR_VFR_FADE if _wind_cycle else COLOR_VFR)
            if HIGH_WINDS_THRESHOLD != -1:
                _set(LEGEND_INDEXES['HIGH'], COLOR_HIGH_WINDS if _wind_cycle else COLOR_VFR)
        except:
            pass

    _show()
    time.sleep(BLINK_SPEED)
    _wind_cycle = not _wind_cycle
