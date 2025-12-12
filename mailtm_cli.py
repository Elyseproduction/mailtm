# mailtm_cli.py (Version avec Auto-update + Remote features + Plugin loader)
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
import hashlib
import importlib.util
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
    print("FATAL: Le fichier access_manager.py est manquant ou contient une erreur de syntaxe/indentation. Assurez-vous qu'il est présent et correct.")
    sys.exit(1)

# --- CONSTANTES ---
API_BASE = "https://api.mail.tm"
ACCOUNT_FILE = "mailtm_account.json"
DEVICE_ID_FILE = "mailtm_device_id.txt"
MAX_DISPLAY_MESSAGES = 50
INBOX_REFRESH_INTERVAL = 60  # Intervalle d'actualisation en secondes

# Repo GitHub fourni par l'utilisateur
GITHUB_REPO_RAW_BASE = "https://raw.githubusercontent.com/Elyseproduction/mailtm/main/"

# Remote config name (dans le repo)
REMOTE_CONFIG_FILENAME = "remote_config.json"
PLUGINS_LOCAL_DIR = "plugins"

# --- COULEURS ANSI (Doivent correspondre à access_manager.py) ---
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

# --- FONCTIONS UTILITAIRES ---
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
        return new_id
    except Exception:
        return new_id

# --- Remote helpers ---
def fetch_remote_text(path, timeout=10) -> str or None:
    url = GITHUB_REPO_RAW_BASE + path
    try:
        r = requests.get(url, headers={'User-Agent': get_random_user_agent()}, timeout=timeout)
        if r.status_code == 200:
            return r.text
        else:
            print(f"{JAUNE}⚠️ Récupération remote {path} => status {r.status_code}{R}")
    except Exception as e:
        print(f"{JAUNE}⚠️ Erreur récupération remote {path}: {e}{R}")
    return None

def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# --- Auto-update (CORRIGÉ) ---
def auto_update_if_enabled(current_file_path: str, config: dict):
    try:
        upd = config.get('update', {}) if config else {}
        if not upd.get('enabled', False):
            return

        # Détermine l'URL de mise à jour: soit celle de la config distante (recommandée), 
        # soit le chemin par défaut (si raw_url est manquante).
        remote_url = upd.get('raw_url')
        if not remote_url:
            # Reconstruit l'URL RAW à partir du chemin de base et du nom du fichier
            remote_url = GITHUB_REPO_RAW_BASE + os.path.basename(current_file_path)

        print(f"{CYAN}🔍 Vérification de la nouvelle version à partir de : {remote_url}{R}")

        try:
            # Téléchargement direct de l'URL brute, qui doit maintenant être publique.
            r = requests.get(remote_url, headers={'User-Agent': get_random_user_agent()}, timeout=15)
            remote_code = r.text if r.status_code == 200 else None
        except Exception as req_e:
            print(f"{JAUNE}⚠️ Erreur de requête lors du téléchargement du code distant: {req_e}{R}")
            return

        if not remote_code:
            status = r.status_code if 'r' in locals() else 'N/A'
            print(f"{JAUNE}Aucune mise à jour trouvée (Status HTTP: {status}). Assurez-vous que l'URL est correcte et publique.{R}")
            return

        with open(current_file_path, 'r', encoding='utf-8') as f:
            local_code = f.read()

        if sha256_of_text(local_code) != sha256_of_text(remote_code):
            print(f"{JAUNE}⚠️ Nouvelle version détectée. Mise à jour en cours...{R}")
            backup_path = current_file_path + ".bak"
            try:
                with open(backup_path, 'w', encoding='utf-8') as b:
                    b.write(local_code)
                with open(current_file_path, 'w', encoding='utf-8') as f:
                    f.write(remote_code)
                print(f"{VERT}✅ Mise à jour appliquée. Redémarrage...{R}")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                print(f"{ROUGE}Erreur lors de l'écriture du fichier de mise à jour: {e}{R}")
        else:
            print(f"{VERT}✔️ Script déjà à jour.{R}")
    except Exception as e:
        print(f"{JAUNE}Erreur auto-update globale: {e}{R}")

# --- Remote config loader ---
def load_remote_config() -> dict:
    txt = fetch_remote_text(REMOTE_CONFIG_FILENAME, timeout=10)
    if not txt:
        return {}
    try:
        cfg = json.loads(txt)
        return cfg
    except Exception as e:
        print(f"{JAUNE}⚠️ Erreur parsing remote_config.json: {e}{R}")
        return {}

# --- Plugin loader (télécharge puis importe de façon sûre) ---
def ensure_local_plugins_dir():
    if not os.path.isdir(PLUGINS_LOCAL_DIR):
        os.makedirs(PLUGINS_LOCAL_DIR, exist_ok=True)

def download_plugin(plugin_name: str) -> str or None:
    """
    Télécharge le plugin depuis le repo raw et le sauvegarde localement.
    Retourne le chemin local du fichier ou None.
    """
    ensure_local_plugins_dir()
    remote_path = "plugins/" + plugin_name
    txt = fetch_remote_text(remote_path, timeout=15)
    if not txt:
        return None
    local_path = os.path.join(PLUGINS_LOCAL_DIR, plugin_name)
    try:
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(txt)
        return local_path
    except Exception as e:
        print(f"{JAUNE}⚠️ Erreur sauvegarde plugin {plugin_name}: {e}{R}")
        return None

def import_plugin_from_path(path: str):
    """
    Import dynamique d'un module Python depuis un chemin de fichier.
    Retourne le module ou None.
    """
    try:
        name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(name, path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    except Exception as e:
        print(f"{JAUNE}⚠️ Erreur import plugin {path}: {e}{R}")
    return None

# --- CLASSE MAILTM ---
class MailTmCLI:
    def __init__(self, remote_config=None):
        self.account = self.load_account()
        self.remote_config = remote_config or {}
        # container to which plugins can register actions
        self.remote_plugins_actions = []
        # load plugins if enabled in config
        try:
            if self.remote_config.get('features', {}).get('plugin_loader', True):
                self.load_remote_plugins()
        except Exception:
            pass

    def load_account(self) -> dict:
        try:
            if os.path.exists(ACCOUNT_FILE):
                with open(ACCOUNT_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_account(self):
        try:
            with open(ACCOUNT_FILE, 'w') as f:
                json.dump(self.account, f, indent=4)
        except Exception as e:
            print(f"{ROUGE}Erreur lors de la sauvegarde de {ACCOUNT_FILE}: {e}{R}")

    def get_domains(self):
        try:
            loading_spinner("Contact API Mail.tm pour les domaines...", 3.0)
            headers = {'User-Agent': get_random_user_agent()}
            response = requests.get(f"{API_BASE}/domains", headers=headers, timeout=30)
            if response.status_code == 200:
                domains_data = response.json()
                if domains_data and 'hydra:member' in domains_data:
                    domains_list = domains_data.get('hydra:member')
                elif domains_data and isinstance(domains_data, list):
                    domains_list = domains_data
                else:
                    domains_list = []
                if domains_list:
                    return [d.get('domain') for d in domains_list if d.get('isActive', True)]
                print(f"{JAUNE}⚠️ API a retourné un format inattendu ou aucun domaine actif.{R}")
            else:
                print(f"{ROUGE}❌ Erreur API: Code de statut {response.status_code}. Vérifiez la connexion.{R}")
        except Exception as e:
            print(f"{ROUGE}❌ Erreur de connexion/timeout (le problème pourrait être votre Pare-feu/Antivirus ou un réseau instable): {e}{R}")
        return []

    def login(self, email, password):
        try:
            loading_spinner("Authentification en cours...", 1.5)
            headers = {'User-Agent': get_random_user_agent()}
            data = {"address": email, "password": password}
            response = requests.post(f"{API_BASE}/token", json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('token')
        except Exception as e:
            print(f"{ROUGE}Erreur login: {e}{R}")
        return None

    def create_account(self):
        print(f"{JAUNE}🔍 Préparation de la création de compte...{R}")
        domains = self.get_domains()
        if not domains:
            print(f"{ROUGE}❌ Aucun domaine disponible. Vérifiez la connexion API.{R}")
            return
        domain = random.choice(domains)
        username = generate_random_string(8)
        email = f"{username}@{domain}"
        password = generate_random_string(12)
        data = {"address": email, "password": password}
        delay = random.uniform(1.5, 4.0)
        loading_spinner(f"Création de {email} (Attente : {delay:.1f}s)", delay)
        try:
            headers = {'User-Agent': get_random_user_agent()}
            response = requests.post(
                f"{API_BASE}/accounts",
                json=data,
                headers=headers,
                timeout=10
            )
            if response.status_code == 201:
                token = self.login(email, password)
                if token:
                    self.account = {
                        "email": email,
                        "password": password,
                        "token": token
                    }
                    self.save_account()
                    print(f"\n{VERT}{GRAS}✅ Compte créé avec succès !{R}")
                    clear_screen()
                    return
        except Exception as e:
            print(f"{ROUGE}❌ Erreur lors de la création du compte: {e}{R}")
        print(f"{ROUGE}❌ Échec de la création du compte.{R}")

    def get_messages(self) -> list:
        if not self.account or 'token' not in self.account:
            print(f"{JAUNE}⚠️ Erreur: Aucun jeton actif. Veuillez créer un compte d'abord.{R}")
            return []
        try:
            loading_spinner("Récupération des messages...", 2.0)
            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            response = requests.get(f"{API_BASE}/messages", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('hydra:member', [])
            elif response.status_code == 401:
                print(f"{JAUNE}⚠️ Jeton expiré ou invalide. Essayez de recréer un compte.{R}")
                return []
        except Exception as e:
            print(f"{ROUGE}❌ Erreur récupération messages: {e}{R}")
        return []

    def get_message(self, message_id: str) -> dict or None:
        if not self.account or 'token' not in self.account:
            return None
        try:
            loading_spinner("Téléchargement du message...", 1.5)
            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            response = requests.get(
                f"{API_BASE}/messages/{message_id}",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"{ROUGE}❌ Erreur lecture message: {e}{R}")
        return None

    def silent_get_message_count(self) -> int:
        if not self.account or 'token' not in self.account:
            return 0
        try:
            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            response = requests.get(f"{API_BASE}/messages", headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('hydra:member', []))
        except Exception:
            pass
        return 0

    def wait_for_message(self, duration=120, poll_interval=5):
        if not self.account or 'token' not in self.account:
            print(f"{ROUGE}❌ Aucun compte actif pour surveiller.{R}")
            return
        print(f"\n{JAUNE}⏳ Démarrage de la surveillance active pour {self.account['email']}...{R}")
        print(f"{CYAN}Vérification max {duration}s, intervalle {poll_interval}s. Lancez votre inscription MAINTENANT.{R}")
        start_time = time.time()
        initial_message_count = self.silent_get_message_count()
        while time.time() - start_time < duration:
            current_time = int(time.time() - start_time)
            sys.stdout.write(f"\r{CYAN}🕰️  Temps écoulé: {current_time}s / {duration}s. Vérification des messages...{R}")
            sys.stdout.flush()
            try:
                current_count = self.silent_get_message_count()
                if current_count > initial_message_count:
                    sys.stdout.write("\n")
                    print(f"{VERT}{GRAS}✅ NOUVEAU MESSAGE REÇU !{R}")
                    messages = self.get_messages()
                    if messages:
                        new_message_id = messages[0].get('id', '')
                        self.display_message_content(new_message_id)
                    return
            except Exception:
                pass
            time.sleep(poll_interval)
        sys.stdout.write("\n")
        print(f"{JAUNE}⏱️  Temps d'attente écoulé ({duration}s). Aucun nouveau message trouvé.{R}")

    def display_inbox(self):
        clear_screen()
        if not self.account:
            print(f"{JAUNE}⚠️ Aucun compte actif. Veuillez créer un compte (option 1).{R}")
            return
        print(f"\n{VERT}🔍 Actualisation de la boîte de réception pour: {self.account['email']}...{R}")
        messages = self.get_messages()
        if not messages:
            print(f"{JAUNE}📭 Aucun email reçu.{R}")
            return
        print(f"\n📬 {len(messages)} message(s) reçu(s) (Affichage des {min(len(messages), MAX_DISPLAY_MESSAGES)} premiers):")
        print(f"{BLEU}=" * 50 + R)
        for i, msg_data in enumerate(messages[:MAX_DISPLAY_MESSAGES], 1):
            sender = msg_data.get('from', {}).get('address', 'Inconnu')
            subject = msg_data.get('subject', 'Sans objet')
            date = msg_data.get('createdAt', '')[:10]
            msg_id = msg_data.get('id', '')
            print(f"{MAGENTA}{i}. De: {R}{sender}")
            print(f"   Objet: {subject}")
            print(f"   Date: {date}")
            print(f"   {GRAS}{CYAN}ID:{R} {msg_id}")
            print("-" * 50)

    def display_message_content(self, msg_id: str):
        clear_screen()
        if not msg_id:
            print(f"{ROUGE}❌ L'ID du message ne peut pas être vide.{R}")
            return
        print(f"\n{JAUNE}📖 Préparation de l'affichage du message ID: {msg_id}...{R}")
        message = self.get_message(msg_id)
        if not message:
            print(f"{ROUGE}❌ Impossible de charger le message (non trouvé ou erreur réseau).{R}")
            return
        sender = message.get('from', {}).get('address', 'Inconnu')
        subject = message.get('subject', 'Sans objet')
        text_content = message.get('text', 'Pas de contenu texte')
        html_content = message.get('html', [''])[0] if message.get('html') and message['html'] else ''
        h = html2text.HTML2Text()
        h.body_width = 0
        h.inline_links = True
        h.ignore_images = True
        content = h.handle(html_content) if html_content else text_content

        def extract_confirmation_code(text: str) -> str or None:
            pattern_num = r'\b(\d{4,8})\b'
            match_num = re.search(pattern_num, text)
            if match_num:
                return match_num.group(1)
            pattern_alphanum = r'\b([A-Z0-9]{6,8})\b'
            match_alphanum = re.search(pattern_alphanum, text)
            if match_alphanum:
                return match_alphanum.group(1)
            return None

        code = extract_confirmation_code(content)
        print("\n" + f"{BLEU}={R}" * 50)
        print(f"De: {MAGENTA}{sender}{R}")
        print(f"Objet: {GRAS}{subject}{R}")
        if code:
            print(f"{VERT}{GRAS}🔥 CODE DE CONFIRMATION DÉTECTÉ: {code} 🔥{R}")
        print(f"{BLEU}={R}" * 50)
        print("\nCONTENU DU MESSAGE:\n")
        print(content)
        print("\n" + f"{BLEU}={R}" * 50)

    def check_new_messages(self) -> int:
        if not self.account or 'token' not in self.account:
            return 0
        try:
            loading_spinner("Vérification rapide des nouveaux messages...", 1.0)
            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            response = requests.get(f"{API_BASE}/messages", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('hydra:member', []))
        except Exception:
            pass
        return 0

    # --- Plugins: download + import + register ---
    def load_remote_plugins(self):
        cfg = self.remote_config or {}
        plugins = cfg.get('plugins', [])
        if not isinstance(plugins, list):
            return
        for plugin in plugins:
            try:
                local = download_plugin(plugin)
                if local:
                    mod = import_plugin_from_path(local)
                    if mod and hasattr(mod, 'register'):
                        try:
                            mod.register(self)
                            print(f"{VERT}Plugin chargé: {plugin}{R}")
                        except Exception as e:
                            print(f"{JAUNE}Erreur during register() for {plugin}: {e}{R}")
                    else:
                        print(f"{JAUNE}Le plugin {plugin} ne définit pas la fonction register(cli).{R}")
                else:
                    print(f"{JAUNE}Impossible de télécharger le plugin: {plugin}{R}")
            except Exception as e:
                print(f"{JAUNE}Erreur chargement plugin {plugin}: {e}{R}")

# --- FONCTION PRINCIPALE ---
def main_cli():
    clear_screen()
    print(f"{VERT}{GRAS}🤖 Mail.tm CLI - Gestion d'Email Temporaire (with Remote Control){R}")

    # --- CHARGEMENT CONFIG DISTANTE ---
    remote_cfg = load_remote_config()

    # Auto-update initial (si activé)
    try:
        if remote_cfg.get('features', {}).get('auto_update', True):
            auto_update_if_enabled(os.path.abspath(__file__), remote_cfg)
    except Exception:
        pass

    # --- CONTRÔLE D'ACCÈS DISTANT ---
    access_manager = AccessManager()
    device_id = get_or_create_device_id()
    cli = MailTmCLI(remote_config=remote_cfg)

    # 🔑 CODE CLÉ ADMINISTRATEUR (Doit être PERMANENT sur GitHub)
    ADMIN_CODE = "ELISE2006"

    start_interface = False
    access_status_display = f"{JAUNE}Accès non validé.{R}"

    # Recharge les codes pour être sûr d'avoir la dernière version avant de chercher l'accès existant
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
        print(f"\n{CYAN}--- Aucune session d'accès distante trouvée ou code expiré ---{R}")
        access_code_input = input(f"{GRAS}🔐 Veuillez entrer le code d'accès: {R}").strip()
        if not access_code_input:
            print(f"{ROUGE}❌ Opération annulée. Aucun code entré.{R}")
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
        # Re-check expiration
        is_valid, msg = access_manager.is_valid_code(valid_access_code, device_id)
        if not is_valid:
            clear_screen()
            print(f"{ROUGE}⛔ Votre abonnement a expiré !{R}")
            print(f"{JAUNE}{msg}{R}")
            print(f"{ROUGE}Veuillez vous réabonner pour continuer à utiliser le service.{R}")
            time.sleep(3)
            sys.exit(0)

        time_since_refresh = time.time() - last_inbox_refresh
        if time_since_refresh > INBOX_REFRESH_INTERVAL:
            refresh_note = f"{JAUNE} (Actualisation nécessaire - {int(time_since_refresh)}s écoulées){R}"
        else:
            refresh_note = f"{VERT} (Actualisé il y a {int(time_since_refresh)}s){R}"

        clear_screen()
        print(CYAN + GRAS + "="*55 + R)
        print(CYAN + GRAS + "="*55 + R)
        print(f"{GRAS}         M  E  N  U    P  R  I  N  C  I  P  A  L      {R}")
        print(CYAN + GRAS + "="*55 + R)
        print(VERT + GRAS + "-"*55 + R)
        print(f"{BLEU}||{R}{access_status_display}")
        print(VERT + GRAS + "-"*55 + R)

        if cli.account:
            print(VERT + GRAS + "-"*55 + R)
            print(f"|{MAGENTA}📧 Compte actif: {JAUNE}{GRAS}{cli.account['email']}{R}")
            print(VERT + GRAS + "-"*55 + R)
            print(f"{VERT}{GRAS}1. {ROUGE}[Désactivé] (Supprimer le compte actif d'abord){R}")
        else:
            print(f"{JAUNE}\n⚠️  Pas de compte actif. Vous devez en créer un (sur \nl'option 1){R}")
            print(f"{VERT}{GRAS}\n1. Créer une nouvelle adresse email{R}")

        print(f"{CYAN}{GRAS}2. Voir la boîte de réception{R}")
        print(f"{BLEU}{GRAS}3. Lire un message par ID{R}")
        print(f"{MAGENTA}{GRAS}4. Supprimer le compte local{R}")
        print(f"{BLEU}5. Vérifier/Actualiser les emails rapidement \n{refresh_note}{R}")
        print(f"{VERT}{GRAS}6. ⏳ Attendre automatiquement un email de vérification (Polling){R}")

        # Show plugin actions if any
        if cli.remote_plugins_actions:
            print(f"\n{MAGENTA}--- Actions plugins distants ---{R}")
            for idx, (title, _) in enumerate(cli.remote_plugins_actions, start=10):
                print(f"{MAGENTA}{idx}. {title}{R}")

        print(f"{ROUGE}{GRAS}0. Quitter{R}")

        choice = input(f"\n{BLEU}Votre choix (0-9 / 10+ pour plugins): {R}").strip()

        if choice == '1':
            if not cli.account:
                cli.create_account()
            else:
                print(f"{JAUNE}❌ Veuillez d'abord {ROUGE}supprimer votre compte actif (Option 4){JAUNE} avant d'en créer un nouveau.{R}")
                time.sleep(3)

        elif choice == '2':
            cli.display_inbox()
            last_inbox_refresh = time.time()

        elif choice == '3':
            msg_id = input("Entrez l'ID du message à lire (ex: 1d9e...c7b): ").strip()
            if msg_id:
                cli.display_message_content(msg_id)

        elif choice == '4':
            if os.path.exists(ACCOUNT_FILE):
                email_to_print = cli.account.get('email', 'précédent')
                os.remove(ACCOUNT_FILE)
                cli.account = {}
                print(f"{VERT}✅ Compte local supprimé. Le mail {email_to_print} restera actif sur Mail.tm jusqu'à sa purge.{R}")
                time.sleep(3)
            else:
                print(f"{JAUNE}❌ Aucun fichier de compte à supprimer.{R}")

        elif choice == '5':
            if cli.account:
                count = cli.check_new_messages()
                last_inbox_refresh = time.time()
                if count > 0:
                    print(f"{VERT}✅ Actualisation terminée. Vous avez {GRAS}{count}{R}{VERT} message(s) dans votre boîte de réception.{R}")
                else:
                    print(f"{JAUNE}✅ Actualisation terminée. Aucun nouveau message trouvé.{R}")
            else:
                print(f"{ROUGE}❌ Veuillez d'abord créer un compte (Option 1).{R}")
                time.sleep(3)

        elif choice == '6':
            if cli.account:
                # use remote-config to set polling if present
                polling_cfg = remote_cfg.get('features', {}).get('polling', True)
                if not polling_cfg:
                    print(f"{JAUNE}⛔ Polling désactivé par la configuration distante.{R}")
                else:
                    cli.wait_for_message(duration=120, poll_interval=5)
                last_inbox_refresh = time.time()
            else:
                print(f"{ROUGE}❌ Veuillez d'abord créer un compte (Option 1).{R}")
                time.sleep(3)

        elif choice == '0':
            print(f"{VERT}👋 Au revoir.{R}")
            break

        else:
            # plugin actions start at 10, 11, 12...
            try:
                num = int(choice)
                if num >= 10 and cli.remote_plugins_actions:
                    idx = num - 10
                    if 0 <= idx < len(cli.remote_plugins_actions):
                        _, action = cli.remote_plugins_actions[idx]
                        try:
                            action()
                        except Exception as e:
                            print(f"{JAUNE}Erreur execution action plugin: {e}{R}")
                        wait_for_input("Appuyez sur Entrée pour revenir au menu...")
                        continue
            except Exception:
                pass
            print(f"{ROUGE}Choix invalide. Veuillez réessayer.{R}")

        if choice not in ['0', '1', '4', '5', '6']:
            wait_for_input("Appuyez sur Entrée pour revenir au menu...")

if __name__ == '__main__':
    try:
        import requests, html2text, uuid, platform
        main_cli()
    except ImportError as e:
        print(f"\n{ROUGE}--- ERREUR FATALE ---{R}")
        print(f"Dépendance manquante: {e}")
        print(f"Veuillez installer les paquets requis via pip:")
        print("pip install requests html2text colorama")
        print(f"--------------------{R}\n")
