import urequests, os, machine

REPO_BASE = "https://raw.githubusercontent.com/hughgoodbody/automatic-octo-bassoon-map/main/"
FILES_TO_UPDATE = ["main.py", "functions.py", "data.py"]
LOCAL_VERSION_FILE = "version.txt"

def get_local_version():
    try:
        with open(LOCAL_VERSION_FILE) as f:
            return f.read().strip()
    except:
        return "0"

def save_local_version(v):
    with open(LOCAL_VERSION_FILE, "w") as f:
        f.write(v)

def update_from_github():
    try:
        # get remote version
        r = urequests.get(REPO_BASE + "version.txt")
        remote_ver = r.text.strip()
        r.close()
        local_ver = get_local_version()

        if remote_ver != local_ver:
            print("New version available:", remote_ver)
            for fname in FILES_TO_UPDATE:
                print("Downloading", fname)
                resp = urequests.get(REPO_BASE + fname)
                with open(fname, "w") as f:
                    f.write(resp.text)
                resp.close()
            save_local_version(remote_ver)
            print("Update complete — rebooting")
            machine.reset()
        else:
            print("Already up to date:", local_ver)
    except Exception as e:
        print("Update check failed:", e)
