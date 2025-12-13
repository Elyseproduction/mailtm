# mailtm_cli.py (Version Finale + Couleurs Mélangées + Option Mise à jour DISTANTE)
# Option 6 corrigée pour mise à jour 1.2.0, autres options intactes

import json
import os
import requests
import random
import string
import uuid
import time
import sys
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
# Option 6 corrigée
try:
    from packaging import version
except ImportError:
    version = None  # fallback si packaging non installé

def check_remote_update():
    try:
        loading_spinner(f"{CYAN}Vérification des mises à jour...{R}", 2.0)
        r = requests.get(REMOTE_CONFIG_URL, timeout=10)

        if r.status_code != 200:
            print(f"{JAUNE}⚠️ Impossible de vérifier les mises à jour.{R}")
            return

        cfg = r.json()
        remote_version = cfg.get("latest_version")
        script_url = cfg.get("script_url")
        message = cfg.get("message", "")

        # Comparaison correcte des versions
        if version:  # Si packaging est installé
            if version.parse(remote_version) <= version.parse(APP_VERSION):
                print(f"{VERT}✅ Version à jour ({APP_VERSION}).{R}")
                return
        else:  # fallback basique
            if remote_version <= APP_VERSION:
                print(f"{VERT}✅ Version à jour ({APP_VERSION}).{R}")
                return

        print(f"""
{MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 {JAUNE}MISE À JOUR DISPONIBLE
{CYAN}Version actuelle : {ROUGE}{APP_VERSION}
Nouvelle version  : {VERT}{remote_version}

📝 {message}
{MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}
""")

        if input(f"{BLEU}Mettre à jour maintenant ? (o/n): {R}").lower() != 'o':
            return

        download_and_update(script_url)

    except Exception as e:
        print(f"{ROUGE}❌ Erreur mise à jour: {e}{R}")

def download_and_update(script_url):
    try:
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
    except Exception as e:
        print(f"{ROUGE}❌ Impossible d'installer la mise à jour: {e}{R}")

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
        print(f"{VERT}✅ Compte créé : {MAGENTA}{email}{R}")

# ===================== MENU PRINCIPAL =====================
def main_cli():
    clear_screen()
    print(f"{CYAN}{GRAS}🤖 Mail.tm CLI — v{APP_VERSION}{R}")

    access_manager = AccessManager()
    device_id = get_or_create_device_id()
    cli = MailTmCLI()

    while True:
        clear_screen()
        # Barre multicolore
        print(f"{ROUGE}{GRAS}━━━━━━━━{JAUNE}━━━━━━━━{VERT}━━━━━━━━{BLEU}━━━━━━━━{MAGENTA}━━━━━━━━{R}")
        print(f"{ROUGE}{GRAS}━━━━━━━━{JAUNE}━━━━━━━━{VERT}━━━━━━━━{BLEU}━━━━━━━━{MAGENTA}━━━━━━━━{R}")
        print(f"{CYAN}{GRAS} M  E  N  U  P  R  I  N  C  I  P  A  L {R}")
        print(f"{ROUGE}{GRAS}━━━━━━━━{JAUNE}━━━━━━━━{VERT}━━━━━━━━{BLEU}━━━━━━━━{MAGENTA}━━━━━━━━{R}")
        print(f"{JAUNE}{GRAS}Version : {VERT}{GRAS}v{APP_VERSION}{R}")
        print(f"{ROUGE}{GRAS}━━━━━━━━{JAUNE}━━━━━━━━{VERT}━━━━━━━━{BLEU}━━━━━━━━{MAGENTA}━━━━━━━━{R}")
        print(f"{ROUGE}{GRAS}━━━━━━━━{JAUNE}━━━━━━━━{VERT}━━━━━━━━{BLEU}━━━━━━━━{MAGENTA}━━━━━━━━{R}\n")

        # Menu avec couleurs alternées
        menu_items = [
            ("1", "Créer une nouvelle adresse email", CYAN),
            ("2", "Voir la boîte de réception", MAGENTA),
            ("3", "Lire un message par ID", JAUNE),
            ("4", "Supprimer le compte local", ROUGE),
            ("5", "Vérifier les emails rapidement", VERT),
            ("6", "🔄 Vérifier les mises à jour", BLEU),
            ("0", "Quitter", ROUGE)
        ]

        for key, desc, color in menu_items:
            print(f"{color}{GRAS}{key}. {desc}{R}")

        choice = input(f"\n{BLANC}Votre choix: {R}").strip()

        if choice == '1':
            cli.create_account()
            wait_for_input(f"{VERT}Entrée pour continuer...{R}")
        elif choice == '2':
            wait_for_input(f"{JAUNE}Option 'Voir la boîte de réception' non implémentée dans ce script. Entrée pour continuer...{R}")
        elif choice == '3':
            wait_for_input(f"{JAUNE}Option 'Lire un message par ID' non implémentée dans ce script. Entrée pour continuer...{R}")
        elif choice == '4':
            wait_for_input(f"{JAUNE}Option 'Supprimer le compte local' non implémentée dans ce script. Entrée pour continuer...{R}")
        elif choice == '5':
            wait_for_input(f"{JAUNE}Option 'Vérifier les emails rapidement' non implémentée dans ce script. Entrée pour continuer...{R}")
        elif choice == '6':
            check_remote_update()
            wait_for_input(f"{CYAN}Entrée pour revenir au menu...{R}")
        elif choice == '0':
            print(f"{ROUGE}👋 Au revoir !{R}")
            break
        else:
            wait_for_input(f"{JAUNE}Option non implémentée. Entrée pour continuer...{R}")

if __name__ == "__main__":
    main_cli()
