# mailtm_cli.py (Version Finale + Option Mise à jour DISTANTE)

import json
import os
import requests
import random
import string
import re
import html2text
import time
import sys
import uuid
import platform
from requests.exceptions import ConnectionError, ReadTimeout

# ===================== VERSION APP =====================
APP_VERSION = "1.1.0"
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/Elyseproduction/mailtm/main/remote_config.json"

# ===================== COLORAMA =====================
try:
    from colorama import init
    init(autoreset=True)
except ImportError:
    pass

# ===================== IMPORTS LOCAUX =====================
try:
    from access_manager import AccessManager, loading_spinner, clear_screen, wait_for_input
except ImportError:
    print("FATAL: access_manager.py manquant ou invalide.")
    sys.exit(1)

# ===================== CONSTANTES =====================
API_BASE = "https://api.mail.tm"
ACCOUNT_FILE = "mailtm_account.json"
DEVICE_ID_FILE = "mailtm_device_id.txt"
MAX_DISPLAY_MESSAGES = 50
INBOX_REFRESH_INTERVAL = 60

# ===================== COULEURS =====================
R = '\033[0m'
NOIR = '\033[30m'
ROUGE = '\033[31m'
VERT = '\033[32m'
JAUNE = '\033[33m'
BLEU = '\033[34m'
MAGENTA = '\033[35m'
CYAN = '\033[36m'
BLANC = '\033[37m'
GRAS = '\033[1m'

# ===================== USER AGENTS =====================
MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 10)',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6)',
    'Mozilla/5.0 (Android 11)',
]

def get_random_user_agent():
    return random.choice(MOBILE_USER_AGENTS)

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_or_create_device_id():
    if os.path.exists(DEVICE_ID_FILE):
        with open(DEVICE_ID_FILE, 'r') as f:
            content = f.read().strip()
            if content:
                return content
    new_id = str(uuid.uuid4())
    with open(DEVICE_ID_FILE, 'w') as f:
        f.write(new_id)
    return new_id

# ===================== MISE À JOUR DISTANTE =====================
def check_remote_update():
    try:
        loading_spinner("Vérification des mises à jour...", 2.0)
        r = requests.get(REMOTE_CONFIG_URL, timeout=10)

        if r.status_code != 200:
            print(f"{JAUNE}⚠️ Impossible de vérifier les mises à jour.{R}")
            return

        cfg = r.json()
        remote_version = cfg.get("latest_version")
        script_url = cfg.get("script_url")
        message = cfg.get("message", "")

        if remote_version == APP_VERSION:
            print(f"{VERT}✅ Version à jour ({APP_VERSION}).{R}")
            return

        print(f"""
{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 MISE À JOUR DISPONIBLE
Version actuelle : {APP_VERSION}
Nouvelle version  : {remote_version}

📝 {message}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}
""")

        if input("Mettre à jour maintenant ? (o/n): ").lower() != 'o':
            return

        download_and_update(script_url)

    except Exception as e:
        print(f"{ROUGE}❌ Erreur mise à jour: {e}{R}")

def download_and_update(script_url):
    r = requests.get(script_url, timeout=15)
    if r.status_code != 200:
        print(f"{ROUGE}❌ Téléchargement échoué.{R}")
        return

    script_path = os.path.realpath(sys.argv[0])
    backup_path = script_path + ".bak"

    if os.path.exists(script_path):
        os.replace(script_path, backup_path)

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(r.text)

    print(f"{VERT}✅ Mise à jour installée. Redémarrage...{R}")
    time.sleep(2)
    os.execv(sys.executable, [sys.executable, script_path])

# ===================== CLASSE MAILTM =====================
class MailTmCLI:
    def __init__(self):
        self.account = self.load_account()

    def load_account(self):
        if os.path.exists(ACCOUNT_FILE):
            with open(ACCOUNT_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_account(self):
        with open(ACCOUNT_FILE, 'w') as f:
            json.dump(self.account, f, indent=4)

    def create_account(self):
        domains = requests.get(f"{API_BASE}/domains").json()["hydra:member"]
        domain = random.choice(domains)["domain"]
        email = f"{generate_random_string(8)}@{domain}"
        password = generate_random_string(12)

        requests.post(f"{API_BASE}/accounts", json={
            "address": email,
            "password": password
        })

        token = requests.post(f"{API_BASE}/token", json={
            "address": email,
            "password": password
        }).json()["token"]

        self.account = {"email": email, "password": password, "token": token}
        self.save_account()

# ===================== MAIN =====================
def main_cli():
    clear_screen()
    print(f"{VERT}{GRAS}🤖 Mail.tm CLI — v{APP_VERSION}{R}")

    access_manager = AccessManager()
    device_id = get_or_create_device_id()
    cli = MailTmCLI()

    while True:
        clear_screen()
        print(CYAN + GRAS + "=" * 55 + R)
        print(CYAN + GRAS + "=" * 55 + R)
        print(f"{GRAS}         M  E  N  U    P  R  I  N  C  I  P  A  L      {R}")
        print(f"{JAUNE}{GRAS}                 Version : v{APP_VERSION}{R}")
        print(CYAN + GRAS + "=" * 55 + R)
        print(CYAN + GRAS + "=" * 55 + R)
        print("")
        print(f"{CYAN}{GRAS}1. Créer une nouvelle adresse email{R}")
        print(f"{CYAN}{GRAS}2. Voir la boîte de réception{R}")
        print(f"{CYAN}{GRAS}3. Lire un message par ID{R}")
        print(f"{CYAN}{GRAS}4. Supprimer le compte local{R}")
        print(f"{CYAN}{GRAS}5. Vérifier les emails rapidement{R}")
        print(f"{CYAN}{GRAS}6. 🔄 Vérifier les mises à jour{R}")
        print(f"{ROUGE}{GRAS}0. Quitter{R}")

        choice = input("Votre choix: ").strip()

        if choice == '1':
            cli.create_account()
            wait_for_input("Compte créé. Entrée pour continuer...")
        elif choice == '6':
            check_remote_update()
            wait_for_input("Entrée pour revenir au menu...")
        elif choice == '0':
            break
        else:
            wait_for_input("Option non implémentée. Entrée pour continuer...")

if __name__ == "__main__":
    main_cli()
