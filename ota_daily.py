# ota_daily.py  —  Simple once-per-day OTA updater for Pico W (MicroPython)
import time, os, machine
import urequests as requests

# ---------- CONFIG ----------
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/hughgoodbody/supreme-guacamole-map/refs/heads/main/"
FILES_TO_UPDATE = ["boot.py", "main.py", "functions.py", "data.py"]  # adjust as you like
LOCAL_VERSION_FILE = "version.txt"          # stored on Pico
REMOTE_VERSION_URL = GITHUB_RAW_BASE + "version.txt"

# When to check each day (24h)
CHECK_HOUR   = 3         # 03:05 local time
CHECK_MINUTE = 5
# Acceptable window in minutes (helps if your loop timing is irregular)
WINDOW_MIN   = 7

# If you want an offset from UTC (because Pico has no RTC battery),
# set TZ offset in hours. e.g., UK winter = 0, summer (BST) = +1.
TZ_OFFSET_HOURS = 0

# NTP (optional but recommended). If you already sync time elsewhere, set to False.
USE_NTP = True

# ---------- TIME HELPERS ----------
def _sync_time_ntp():
    if not USE_NTP:
        return
    try:
        import ntptime
        # ntptime sets RTC to UTC
        for _ in range(3):
            try:
                ntptime.settime()
                break
            except:
                time.sleep(1)
    except:
        pass

def _localtime():
    t = time.localtime()  # returns tuple in current RTC (UTC if not offset)
    if TZ_OFFSET_HOURS:
        # apply fixed offset
        secs = time.mktime(t) + TZ_OFFSET_HOURS * 3600
        t = time.localtime(secs)
    return t

def _today_str():
    y, m, d, *_ = _localtime()
    return f"{y:04d}-{m:02d}-{d:02d}"

def _in_window():
    y,m,d, hh, mm, *_ = _localtime()
    target = CHECK_HOUR * 60 + CHECK_MINUTE
    now    = hh * 60 + mm
    return abs(now - target) <= WINDOW_MIN

# ---------- VERSION HELPERS ----------
def _read_local_version():
    try:
        with open(LOCAL_VERSION_FILE) as f:
            return f.read().strip()
    except:
        return None

def _write_local_version(ver):
    try:
        with open(LOCAL_VERSION_FILE, "w") as f:
            f.write(ver)
    except:
        pass

def _fetch_remote_text(url):
    r = None
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print("OTA: fetch error:", e)
    finally:
        try: r.close()
        except: pass
    return None

def _fetch_remote_json(url):
    r = None
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("OTA: fetch error:", e)
    finally:
        try: r.close()
        except: pass
    return None

# ---------- STATE (runs-once-per-day guard) ----------
_LAST_RUN_FILE = ".ota_last_run.txt"

def _get_last_run_date():
    try:
        with open(_LAST_RUN_FILE) as f:
            return f.read().strip()
    except:
        return ""

def _set_last_run_date(s):
    try:
        with open(_LAST_RUN_FILE, "w") as f:
            f.write(s)
    except:
        pass

# ---------- UPDATER ----------
def _download_and_replace(fname):
    url = GITHUB_RAW_BASE + fname
    print("OTA: downloading", fname)
    r = None
    try:
        r = requests.get(url)
        if r.status_code != 200:
            print("OTA: HTTP", r.status_code, "for", fname)
            return False
        # write atomically (tmp then rename) to avoid partial file if power drops
        tmpname = fname + ".tmp"
        with open(tmpname, "w") as f:
            f.write(r.text)
        try:
            os.remove(fname)
        except:
            pass
        os.rename(tmpname, fname)
        print("OTA: wrote", fname)
        return True
    except Exception as e:
        print("OTA: error writing", fname, e)
        return False
    finally:
        try: r.close()
        except: pass
        time.sleep(0.2)

def _do_update():
    remote_ver = _fetch_remote_text(REMOTE_VERSION_URL)
    if not remote_ver:
        print("OTA: could not read remote version")
        return False

    local_ver = _read_local_version()
    if local_ver == remote_ver:
        print("OTA: already latest version", local_ver)
        return False

    print("OTA: new version available:", remote_ver, "(local:", local_ver or "none", ")")
    ok_all = True
    for fname in FILES_TO_UPDATE:
        if not _download_and_replace(fname):
            ok_all = False
    if ok_all:
        _write_local_version(remote_ver)
        print("OTA: update complete → rebooting")
        time.sleep(1)
        machine.reset()
    else:
        print("OTA: update incomplete (kept old version)")
    return ok_all

# ---------- PUBLIC API ----------
def ota_init_time():
    """Call once after Wi-Fi is up, to ensure the clock is sane."""
    _sync_time_ntp()

def ota_tick():
    """
    Call this frequently (e.g., once per loop iteration).
    It will:
      - run at most once per calendar day,
      - only within the configured HH:MM ± WINDOW_MIN window.
    """
    today = _today_str()

    # if already ran today, skip
    if _get_last_run_date() == today:
        return

    # only run inside window
    if not _in_window():
        return

    print("OTA: daily window open — checking…")
    # mark the day first so we don't keep hammering within the window
    _set_last_run_date(today)
    _do_update()
