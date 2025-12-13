# mailtm_cli.py (Version Finale + Option Mise à jour DISTANTE 1.2.0)
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

# --- AJOUT DE COLORAMA POUR LA COMPATIBILITÉ WINDOWS/POWERSHELL ---
try:
    from colorama import init
    init(autoreset=True) 
except ImportError:
    pass 

# Importation du module de gestion des accès DISTANT
try:
    from access_manager import AccessManager, loading_spinner, clear_screen, wait_for_input
except ImportError:
    print("FATAL: Le fichier access_manager.py est manquant ou contient une erreur.")
    sys.exit(1)

# --- CONSTANTES ---
API_BASE = "https://api.mail.tm"
ACCOUNT_FILE = "mailtm_account.json"
DEVICE_ID_FILE = "mailtm_device_id.txt" 
MAX_DISPLAY_MESSAGES = 50 
INBOX_REFRESH_INTERVAL = 60 # Intervalle d'actualisation en secondes
APP_VERSION = "1.1.0"
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/Elyseproduction/mailtm/main/remote_config.json"

# --- COULEURS ANSI ---
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

# --- USER AGENTS ---
MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Android 11; Mobile; rv:88.0) Gecko/88.0 Firefox/88.0',
    'Mozilla/5.0 (Linux; Android 9; Pixel 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Mobile Safari/537.36',
]

def get_random_user_agent() -> str:
    return random.choice(MOBILE_USER_AGENTS)

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_or_create_device_id() -> str:
    if os.path.exists(DEVICE_ID_FILE):
        try:
            with open(DEVICE_ID_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass
    new_id = str(uuid.uuid4())
    try:
        with open(DEVICE_ID_FILE, 'w') as f:
            f.write(new_id)
    except Exception:
        pass
    return new_id

# --- MISE À JOUR DISTANTE ---
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

        # Comparaison des versions
        if version:
            if version.parse(remote_version) <= version.parse(APP_VERSION):
                print(f"{VERT}✅ Version à jour ({APP_VERSION}).{R}")
                return
        else:
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

# --- CLASSE MAILTM (inchangée) ---
# (Tout le contenu de MailTmCLI est exactement comme dans ton dernier script)
# Les fonctions create_account, display_inbox, display_message_content, check_new_messages restent intactes.

# --- FONCTION PRINCIPALE ---
def main_cli():
    clear_screen()
    print(f"{VERT}{GRAS}🤖 Mail.tm CLI - Gestion d'Email Temporaire{R}")
    
    access_manager = AccessManager() 
    device_id = get_or_create_device_id() 
    cli = MailTmCLI() 

    ADMIN_CODE = "ELISE2006"
    
    start_interface = False
    access_status_display = f"{JAUNE}Accès non validé.{R}"
    
    access_manager.codes, access_manager.file_sha = access_manager.load_codes_from_github()
    valid_access_code = None
    
    for code, data in access_manager.codes.items():
        if data.get('claimed_by_device') == device_id:
            loading_spinner(f"{CYAN}Vérification de l'accès permanent avec l'ID d'appareil...{R}", 1.5)
            is_valid, status_message = access_manager.is_valid_code(code, device_id) 
            if is_valid:
                valid_access_code = code 
                if code == ADMIN_CODE and "PERMANENT" in status_message.upper():
                    access_status_display = f"{MAGENTA}(ADMINISTRATEUR RÉCLAMÉ). Accès Permanent.{R}"
                else:
                    access_status_display = f"{VERT}{status_message}{R}"
                start_interface = True
                break

    if not start_interface:
        clear_screen()
        access_code_input = input(f"{GRAS}🔐 Veuillez entrer le code d'accès: {R}").strip()
        if not access_code_input:
            print(f"{ROUGE}❌ Opération annulée.{R}")
            return
        loading_spinner("Vérification et réclamation du nouveau code", 2.0)
        is_valid, status_message = access_manager.is_valid_code(access_code_input, device_id)
        if not is_valid:
            print(f"{ROUGE}❌ ACCÈS REFUSÉ: {status_message}{R}")
            return
        if access_code_input == ADMIN_CODE and "PERMANENT" in status_message.upper():
             status_display = f"{MAGENTA}VALIDÉ (ADMINISTRATEUR RÉCLAMÉ). Accès Permanent.{R}"
        else:
             status_display = f"{VERT}✅ Code d'accès valide. {status_message}.{R}"
        print(status_display)
        access_status_display = status_display
        valid_access_code = access_code_input
        start_interface = True

    if not start_interface:
        return

    last_inbox_refresh = time.time()
    
    while True:    
        time_since_refresh = time.time() - last_inbox_refresh
        refresh_note = f"{JAUNE} (Actualisation nécessaire - {int(time_since_refresh)}s écoulées){R}" if time_since_refresh > INBOX_REFRESH_INTERVAL else f"{VERT} (Actualisé il y a {int(time_since_refresh)}s){R}"
        
        clear_screen()
        print(CYAN + GRAS + "="*55 + R)
        print(f"{GRAS}         M  E  N  U    P  R  I  N  C  I  P  A  L      {R}")
        print(CYAN + GRAS + "="*55 + R)
        print(VERT + GRAS + "-"*55 + R)
        print(f"{BLEU}||{R}{access_status_display}")
        print(VERT + GRAS + "-"*55 + R)
        if cli.account:
            print(f"|{MAGENTA}📧 Compte actif: {JAUNE}{GRAS}{cli.account['email']}{R}")
        else:
            print(f"{JAUNE}\n⚠️  Pas de compte actif.{R}")
        
        print(f"{VERT}{GRAS}\n1. Créer une nouvelle adresse email{R}")
        print(f"{CYAN}{GRAS}2. Voir la boîte de réception{R}")
        print(f"{BLEU}{GRAS}3. Lire un message par ID{R}")
        print(f"{MAGENTA}{GRAS}4. Supprimer le compte local{R}")
        print(f"{BLEU}5. Vérifier/Actualiser les emails rapidement \n{refresh_note}{R}")
        print(f"{ROUGE}{GRAS}6. 🔄 Vérifier les mises à jour{R}")
        print(f"{ROUGE}{GRAS}0. Quitter{R}")
        
        choice = input(f"\n{BLEU}Votre choix (0-6): {R}").strip()
        
        if choice == '1':
            if not cli.account:
                cli.create_account()
            else:
                print(f"{JAUNE}❌ Supprimez le compte actif avant d'en créer un nouveau.{R}")
                time.sleep(3)
                
        elif choice == '2':
            cli.display_inbox()
            last_inbox_refresh = time.time()
            
        elif choice == '3':
            msg_id = input("Entrez l'ID du message à lire: ").strip()
            if msg_id:
                cli.display_message_content(msg_id)
            
        elif choice == '4':
            if os.path.exists(ACCOUNT_FILE):
                email_to_print = cli.account.get('email', 'précédent') 
                os.remove(ACCOUNT_FILE)
                cli.account = {}
                print(f"{VERT}✅ Compte local supprimé.{R}")
                time.sleep(3)
            else:
                print(f"{JAUNE}❌ Aucun fichier de compte à supprimer.{R}")

        elif choice == '5':
            if cli.account:
                count = cli.check_new_messages()
                last_inbox_refresh = time.time()
                if count > 0:
                     print(f"{VERT}✅ Vous avez {GRAS}{count}{R}{VERT} message(s) dans votre boîte.{R}")
                else:
                     print(f"{JAUNE}✅ Aucun nouveau message trouvé.{R}")
            else:
                print(f"{ROUGE}❌ Veuillez d'abord créer un compte (Option 1).{R}")
                time.sleep(3)
                
        elif choice == '6':
            check_remote_update()
            wait_for_input(f"{CYAN}Appuyez sur Entrée pour revenir au menu...{R}")
            
        elif choice == '0':
            print(f"{VERT}👋 Au revoir.{R}")
            break
            
        else:
            print(f"{ROUGE}Choix invalide. Veuillez réessayer.{R}")
            
        if choice not in ['0', '1', '4', '5']: 
            wait_for_input("Appuyez sur Entrée pour revenir au menu...")

if __name__ == '__main__':
    try:
        import requests, html2text, uuid, platform
        main_cli()
    except ImportError as e:
        print(f"\n{ROUGE}--- ERREUR FATALE ---{R}")
        print(f"Dépendance manquante: {e}")
        print("pip install requests html2text colorama") 
