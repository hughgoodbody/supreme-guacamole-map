# boot.py — simple, robust Wi-Fi setup portal for Pico W

from phew import access_point, dns, server
import network, machine, utime, json, _thread, os
network.WLAN(network.AP_IF).active(False)
network.WLAN(network.STA_IF).active(False)
utime.sleep_ms(200)

AP_NAME        = "WEATHER_MAP"
AP_DOMAIN      = "weathermap.setup"       # not a real domain
WIFI_FILE      = "wifi.json"

# ---------------------------------------------------------------
def machine_reset():
    utime.sleep(1)
    print("Resetting...")
    machine.reset()

# ---------------------------------------------------------------
def try_connect_saved():
    """Try to connect with saved wifi.json. Return True if connected."""
    try:
        with open(WIFI_FILE) as f:
            creds = json.load(f)
    except Exception as e:
        print("⚠️ No wifi.json found:", e)
        return False

    ssid = creds.get("ssid", "")
    password = creds.get("password", "")
    if isinstance(ssid, str): ssid = ssid.encode()
    if isinstance(password, str): password = password.encode()

    print("Connecting to", ssid, "…")

    # Make sure AP is down and STA reset
    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    utime.sleep_ms(200)
    wlan.active(True)

    # Check interface really came up
    if not wlan.active():
        print("⚠️ WLAN interface failed to start, retrying…")
        utime.sleep(0.5)
        wlan.active(True)
    utime.sleep(0.3)

    try:
        wlan.connect(ssid, password)
    except OSError as e:
        print("⚠️ wlan.connect() raised:", e)
        return False

    for _ in range(40):
        if wlan.isconnected():
            print("✅ Connected:", wlan.ifconfig())
            return True
        utime.sleep(0.5)

    print("❌ Connection failed.")
    wlan.active(False)
    return False


# ---------------------------------------------------------------
def setup_mode():
    print("Entering setup mode…")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    nets = wlan.scan()
    ssids = []
    for n in nets:
        try:
            name = n[0].decode("utf-8").strip()
        except:
            name = ""
        if name:
            ssids.append(name)
    ssids = sorted(set(ssids))
    print("Found networks:", ssids)

    # ---------- Handlers ----------
    def ap_index(request):
        opts = "".join(f'<option value="{s}">{s}</option>' for s in ssids)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Select Wi-Fi</title></head>
<body>
<h2>Select Wi-Fi Network</h2>
<form action="/configure" method="get">
<select name="ssid">{opts}</select><br><br>
Password: <input type="password" name="password"><br><br>
<button type="submit">Connect</button>
</form></body></html>"""
        return html

    def ap_configure(request):
        print("Saving Wi-Fi credentials…")

        # Extract parameters manually for maximum compatibility
        ssid = ""
        password = ""

        # Try POST form first
        if hasattr(request, "form") and request.form:
            ssid = request.form.get("ssid", "")
            password = request.form.get("password", "")
        # Then try GET query params
        elif hasattr(request, "query") and request.query:
            ssid = request.query.get("ssid", "")
            password = request.query.get("password", "")
        # Finally, parse manually from raw query string (edge case)
        elif "?" in request.path:
            raw = request.path.split("?", 1)[1]
            for part in raw.split("&"):
                if "=" in part:
                    key, value = part.split("=", 1)
                    if key == "ssid":
                        ssid = value
                    elif key == "password":
                        password = value

        print("Parsed SSID:", ssid)
        print("Parsed password length:", len(password))

        if not ssid:
            return "<h3>Error: missing SSID or password.</h3>"

        creds = {"ssid": ssid, "password": password}

        try:
            with open(WIFI_FILE, "w") as f:
                json.dump(creds, f)
                f.flush()
            print("✅ Wi-Fi credentials saved:", creds)
        except Exception as e:
            print("⚠️ Failed to save Wi-Fi credentials:", e)
            return "<h3>Error saving Wi-Fi credentials.</h3>"

        def delayed_reset():
            utime.sleep(1)
            print("Resetting…")
            machine.reset()

        _thread.start_new_thread(delayed_reset, ())
        return "<h3>Saved! Rebooting…</h3>"



    def portal_probe(request):
        # Redirect captive portal probes to the setup page
        return '<meta http-equiv="refresh" content="0; url=/">'

    def ap_catch_all(request):
        return "Not found", 404

    # ---------- Routes ----------
    server.add_route("/", ap_index)
    server.add_route("/configure", ap_configure)
    server.add_route("/generate_204", portal_probe)
    server.add_route("/gen_204", portal_probe)
    server.add_route("/hotspot-detect.html", portal_probe)
    server.add_route("/connecttest.txt", portal_probe)
    server.add_route("/ncsi.txt", portal_probe)
    server.set_callback(ap_catch_all)

    # ---------- Start AP ----------
    ap = access_point(AP_NAME)
    ip = ap.ifconfig()[0]
    print(f"Access point active at http://{ip}  (or http://{AP_DOMAIN})")
    dns.run_catchall(ip)
    server.run()

# ---------------------------------------------------------------
# Startup logic
if try_connect_saved():
    print("Wi-Fi connected — launching main.py soon…")
    try:
        import main
        if hasattr(main, "run"):
            main.run()
        elif hasattr(main, "main"):
            main.main()
    except Exception as e:
        import sys
        sys.print_exception(e)
        print("Falling back to setup mode.")
        try:
            os.remove(WIFI_FILE)
        except:
            pass
        setup_mode()
else:
    setup_mode()

