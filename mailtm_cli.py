# mailtm_cli.py (Version Finale - Standalone, avec compilation Nuitka intégrée)

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
import base64
from datetime import datetime, timedelta
from requests.exceptions import ConnectionError, ReadTimeout, RequestException
import subprocess # AJOUT NÉCESSAIRE POUR NUITKA
import shutil     # AJOUT NÉCESSAIRE POUR NUITKA (Nettoyage)

# --- AJOUT DE COLORAMA POUR LA COMPATIBILITÉ WINDOWS/POWERSHELL ---
try:
    from colorama import init
    init(autoreset=True)
except ImportError:
    pass

# --- COULEURS ANSI (Doivent correspondre) ---
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

# --- FONCTIONS SYSTÈME ET ANIMATIONS ---

def clear_screen():
    """Efface le contenu de la console/terminal."""
    system_name = platform.system()
    if system_name == "Windows":
        os.system('cls') 
    else:
        os.system('clear')

def wait_for_input(prompt_text: str = "Appuyez sur Entrée pour continuer..."):
    """Pause l'exécution en attendant une entrée utilisateur (colorée)."""
    input(f"\n{JAUNE}{GRAS}{prompt_text}{R}")

def cleanup_line():
    """S'assure que la ligne courante est complètement effacée et que le curseur est au début."""
    sys.stdout.write('\r\033[K') 
    sys.stdout.flush()

def loading_spinner(text: str, duration: float = 2.0):
    """Affiche un spinner de chargement professionnel non bloquant (visuel) avec fallback."""
    spinner = ['|', '/', '-', '\\']
    start_time = time.time()
    i = 0
    full_text = f"{CYAN}{GRAS}{text}{R} " 
    
    try:
        while time.time() - start_time < duration:
            current_spin = f"{full_text} {CYAN}{spinner[i % len(spinner)]}{R}"
            cleanup_line() 
            sys.stdout.write(current_spin)           
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        cleanup_line() 
        
    except Exception:
        cleanup_line() 
        sys.stdout.write(f"{full_text} (Attente...)")
        sys.stdout.flush()
        time.sleep(duration)
        cleanup_line()


# --- CONSTANTES MAILTM CLI ---
API_BASE = "https://api.mail.tm"
ACCOUNT_FILE = "mailtm_account.json"
DEVICE_ID_FILE = "mailtm_device_id.txt"
MAX_DISPLAY_MESSAGES = 50
INBOX_REFRESH_INTERVAL = 60 
CURRENT_BINARY_VERSION = "1.0.1" 
REMOTE_VERSION_FILE = "latest_version.txt"
REMOTE_DOWNLOAD_URL = "https://github.com/Elyseproduction/mailtm/releases" 
GITHUB_REPO_RAW_BASE = "https://raw.githubusercontent.com/Elyseproduction/mailtm/main/"
REMOTE_CONFIG_FILENAME = "remote_config.json"
PLUGINS_LOCAL_DIR = "plugins"
CURRENT_BINARY_FILENAME = "mailtm_cli.bin" # <-- CONSTANTE POUR LE NOM DU BINAIRE

# --- CONSTANTES GITHUB ACCESS_MANAGER (Intégrées) ---
GITHUB_USER = "Elyseproduction" 
GITHUB_REPO = "mailtm"           
GITHUB_FILE_PATH = "access_codes.json"       
GITHUB_TOKEN = "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" 

GITHUB_API_URL_BASE = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"


# NOUVELLES CONSTANTES POUR LA COMPILATION (Pour Option 7)
REMOTE_SOURCE_FILENAME = "mailtm_cli.py" 
RAW_SOURCE_URL = "https://raw.githubusercontent.com/Elyseproduction/mailtm/main/mailtm_cli.py" 
# Options Nuitka de base (tirées de nuitka.py)
NUITKA_OPTIONS = ["--onefile", "--standalone", "--remove-output"] 
# Chemin de sortie pour Nuitka (utilisation du répertoire courant du binaire)
DOWNLOAD_PATH = os.path.dirname(os.path.abspath(sys.argv[0])) 


# --- CLASSE AccessManager (Intégrée et Corrigée) ---
class AccessManager:
    # ... (code inchangé) ...
    """Gère la lecture et l'écriture des codes d'accès sur un repo GitHub."""
    def __init__(self):
        self.codes = {}
        self.file_sha = None

    def _get_github_headers(self) -> dict:
        """Retourne les headers d'authentification pour l'API GitHub."""
        return {
            'Authorization': f'token {GITHUB_TOKEN}',
            'User-Agent': 'Elyseproduction-MailTM-CLI'
        }

    def load_codes_from_github(self) -> tuple[dict, str or None]:
        """Télécharge les codes JSON depuis GitHub. Retourne (codes, sha)"""
        cleanup_line()
        sys.stdout.write(f"{CYAN}{GRAS}Vérification des codes d'accès..{R}")
        sys.stdout.flush()
        time.sleep(2) 
        try:
            headers = self._get_github_headers()
            response = requests.get(GITHUB_API_URL_BASE, headers=headers, timeout=10)
            cleanup_line()
            
            if response.status_code == 200:
                data = response.json()
                content_base64 = data.get('content', '')
                self.file_sha = data.get('sha')
                
                content_json = base64.b64decode(content_base64).decode('utf-8')
                self.codes = json.loads(content_json)
                
                sys.stdout.write(f"{VERT}✅ Codes d'accès chargés. {len(self.codes)} codes trouvés.{R}")
                sys.stdout.flush()
                return self.codes, self.file_sha
                
            elif response.status_code == 404:
                sys.stdout.write(f"{JAUNE}⚠️ Fichier de codes non trouvé sur GitHub. Création d'un fichier vide.{R}")
                sys.stdout.flush()
                return {}, None
            else:
                sys.stdout.write(f"{ROUGE}❌ Erreur GitHub ({response.status_code}) lors du chargement des codes.{R}")
                sys.stdout.flush()
                return {}, None
                
        except ConnectionError:
            cleanup_line()
            sys.stdout.write(f"{ROUGE}❌ Erreur de connexion au réseau.{R}")
            sys.stdout.flush()
            return {}, None
        except Exception as e:
            cleanup_line()
            sys.stdout.write(f"{ROUGE}❌ Erreur inattendue au chargement des codes: {e}{R}")
            sys.stdout.flush()
            return {}, None

    def save_codes_to_github(self, commit_message: str) -> bool:
        """Sauvegarde les codes JSON vers GitHub."""
        cleanup_line()
        sys.stdout.write(f"{CYAN}Sauvegarde des codes d'accès distants...{R}")
        sys.stdout.flush()
        
        if not self.file_sha:
            self.load_codes_from_github()
            if not self.file_sha:
                sys.stdout.write(f"{ROUGE}❌ Échec de l'obtention du SHA, impossible de sauvegarder.{R}")
                sys.stdout.flush()
                return False
                
        try:
            content_json = json.dumps(self.codes, indent=4)
            content_base64 = base64.b64encode(content_json.encode('utf-8')).decode('utf-8')

            payload = {
                "message": commit_message,
                "content": content_base64,
                "sha": self.file_sha
            }

            headers = self._get_github_headers()
            response = requests.put(GITHUB_API_URL_BASE, headers=headers, json=payload, timeout=10)
            cleanup_line()

            if response.status_code == 200 or response.status_code == 201:
                self.file_sha = response.json().get('content', {}).get('sha')
                sys.stdout.write(f"{VERT}✅ Codes sauvegardés avec succès sur GitHub.{R}")
                sys.stdout.flush()
                return True
            else:
                sys.stdout.write(f"{ROUGE}❌ Échec de la sauvegarde GitHub ({response.status_code}). Conflict? Réessayez.{R}")
                sys.stdout.flush()
                return False
        except ConnectionError:
            cleanup_line()
            sys.stdout.write(f"{ROUGE}❌ Erreur de connexion au réseau lors de la sauvegarde.{R}")
            sys.stdout.flush()
            return False
        except Exception as e:
            cleanup_line()
            sys.stdout.write(f"{ROUGE}❌ Erreur inattendue à la sauvegarde des codes: {e}{R}")
            sys.stdout.flush()
            return False

    def is_valid_code(self, code_id: str, device_id: str) -> tuple[bool, str]:
        """
        Vérifie si un code est valide en utilisant les clés 'expires_at' et 'duration_str'.
        """
        code_id = code_id.upper().strip()
        if not self.codes:
            self.load_codes_from_github()

        code_data = self.codes.get(code_id)

        if not code_data:
            return False, "Code d'accès non trouvé."

        expires_at = code_data.get('expires_at')
        duration_str = code_data.get('duration_str', 'Inconnu')

        # 1. Vérification de l'expiration
        is_expired = False
        duration_msg = ""
        
        if expires_at is None:
            # Code permanent 
            if duration_str.upper() in ['PERM', 'PERMANENT']:
                duration_msg = "Accès Permanent"
                is_expired = False
            else:
                # État non défini 
                return False, "Code en état invalide (Date d'expiration manquante pour code non PERM)."
        else:
            # Code non permanent 
            try:
                # Utiliser fromisoformat pour gérer les dates ISO 8601 avec microsecondes
                expires_dt = datetime.fromisoformat(expires_at)
                is_expired = expires_dt < datetime.now()
                duration_msg = f"Expiration : {expires_dt.strftime('%d-%m-%Y à %H:%M:%S')}"
            except Exception:
                # Si le format ISO 8601 est cassé
                return False, "Format de date d'expiration invalide (ISO 8601 attendu)."

        if is_expired:
            return False, "Code d'accès expiré."

        # 2. Vérification de la réclamation
        claimed_by = code_data.get('claimed_by_device')

        if claimed_by is None:
            # Code non réclamé, on le réclame
            self.codes[code_id]['claimed_by_device'] = device_id
            if self.save_codes_to_github(f"Claim code {code_id} by device {device_id[:8]}"):
                return True, f"{duration_msg}"
            else:
                # Échec de la sauvegarde, on refuse l'accès pour éviter le double usage
                self.codes[code_id]['claimed_by_device'] = None
                return False, "Échec de la sauvegarde de la réclamation du code. Réessayez."

        elif claimed_by == device_id:
            # Code déjà réclamé par cet appareil
            return True, f"Accès confirmé. {duration_msg}."

        else:
            # Code réclamé par un autre appareil
            return False, f"Ce code d'accès est déjà utilisé par un autre appareil ({claimed_by[:8]}...)."


# --- FONCTIONS UTILITAIRES POUR LA COMPILATION (Ajoutées ici) ---

def print_section_separator_cli(color):
    """Affiche une ligne de séparation colorée de 46 caractères, adaptée pour mailtm_cli menu."""
    print(f"{color}{'=' * 46}{R}")

def _run_nuitka_command(command: list, task_name: str) -> bool:
    """Exécute une commande Nuitka de manière non interactive et gère le feedback."""
    
    print_section_separator_cli(JAUNE)
    print(f"{JAUNE}{GRAS}⏳ Exécution : {task_name}...{R}")
    print(f"{CYAN}Commande: {' '.join(command)}{R}")
    print_section_separator_cli(JAUNE)
    
    try:
        # Exécution de Nuitka (doit être accessible dans le PATH)
        process = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True, # Capture la sortie pour l'afficher en cas d'erreur
            timeout=480 # Timeout de 8 minutes pour la compilation
        )
        print_section_separator_cli(VERT)
        print(f"{VERT}✅ Commande '{task_name}' réussie.{R}")
        print_section_separator_cli(VERT)
        return True
    except subprocess.CalledProcessError as e:
        print_section_separator_cli(ROUGE)
        print(f"{ROUGE}{GRAS}❌ Échec de la compilation '{task_name}'. Code d'erreur: {e.returncode}{R}")
        error_output = e.stderr if e.stderr else "Aucune sortie d'erreur détaillée."
        print(f"{ROUGE}Sortie STDERR (derniers 1000 chars):\n{error_output[-1000:]}{R}")
        print_section_separator_cli(ROUGE)
        return False
    except FileNotFoundError:
        print_section_separator_cli(ROUGE)
        print(f"{ROUGE}{GRAS}❌ Commande Nuitka introuvable. Assurez-vous que Nuitka est installé et dans votre PATH (pip install nuitka).{R}")
        print_section_separator_cli(ROUGE)
        return False
    except subprocess.TimeoutExpired:
        print_section_separator_cli(ROUGE)
        print(f"{ROUGE}{GRAS}❌ Timeout de compilation expiré (plus de 8 minutes).{R}")
        print_section_separator_cli(ROUGE)
        return False
# --- FIN DES FONCTIONS UTILITAIRES POUR LA COMPILATION ---


# --- FONCTIONS UTILITAIRES (mailtm_cli) ---
# ... (fonctions inchangées) ...

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
            pass
    except Exception:
        pass
    return None

def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

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

# --- CLASSE MAILTM CLI ---
class MailTmCLI:
    def __init__(self, remote_config=None):
        self.account = self.load_account()
        self.remote_config = remote_config or {}
        self.binary_update_status = f"{JAUNE}Vérification...{R}" 
        self.remote_plugins_actions = []
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

    # MODIFICATION: Retourne remote_version
    def check_remote_binary_version(self) -> tuple[bool, str or None]:
        """Vérifie la version du script distant. Retourne (is_update_available, remote_version)"""
        url = f"{GITHUB_REPO_RAW_BASE}{REMOTE_VERSION_FILE}"
        remote_version = None
        
        try:
            loading_spinner("Vérification de la version du script..", duration=3)
            headers = {'User-Agent': get_random_user_agent()}
            response = requests.get(url, headers=headers, timeout=5)
            cleanup_line()

            if response.status_code == 200:
                remote_version = response.text.strip()
                
                if remote_version != CURRENT_BINARY_VERSION:
                    self.binary_update_status = (
                        f"{ROUGE}{GRAS}🚨 NOUVELLE VERSION BINAIRE ({remote_version}) DISPONIBLE !{R}"
                    )
                    return True, remote_version
                else:
                    self.binary_update_status = f"{VERT}Binaire à jour ({CURRENT_BINARY_VERSION}).{R}"
                    return False, remote_version
            else:
                self.binary_update_status = f"{JAUNE}⚠️ Vérif. version binaire échouée (HTTP {response.status_code}).{R}"
                return False, remote_version
        except (ConnectionError, ReadTimeout):
            cleanup_line()
            self.binary_update_status = f"{JAUNE}⚠️ Connexion échouée pour vérification de version.{R}"
            return False, remote_version
        except Exception:
            cleanup_line()
            self.binary_update_status = f"{JAUNE}⚠️ Erreur lors de la vérification de version.{R}"
            return False, remote_version

    # Méthode perform_binary_update gardée pour compatibilité mais non utilisée par l'option 7
    def perform_binary_update(self) -> bool:
        # ... (code inchangé pour cette méthode) ...
        """
        Télécharge le dernier binaire compilé depuis GitHub et le sauvegarde localement 
        sous un nom temporaire pour remplacement manuel.
        Retourne True si le téléchargement a réussi, False sinon.
        """
        remote_path = CURRENT_BINARY_FILENAME
        local_target_file = CURRENT_BINARY_FILENAME + ".temp" 
        url = GITHUB_REPO_RAW_BASE + remote_path
        
        print(f"\n{CYAN}Téléchargement du nouveau binaire ({CURRENT_BINARY_FILENAME}) depuis GitHub...{R}")
        
        try:
            headers = {'User-Agent': get_random_user_agent()}
            # Utilisation de stream=True pour gérer potentiellement de gros fichiers binaires
            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status() # Lève une exception pour 4xx/5xx
                
                with open(local_target_file, 'wb') as f:
                    # Écriture par morceaux pour l'efficacité mémoire
                    for chunk in r.iter_content(chunk_size=8192): 
                        f.write(chunk)
            
            print(f"{VERT}{GRAS}✅ TÉLÉCHARGEMENT DU NOUVEAU BINAIRE RÉUSSI !{R}")
            print(f"{JAUNE}Le nouveau fichier est disponible sous le nom temporaire : {local_target_file}{R}")
            self.binary_update_status = f"{VERT}Nouveau binaire téléchargé. Remplacement nécessaire.{R}"
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"{ROUGE}❌ Échec du téléchargement du binaire. Erreur: {e}{R}")
            self.binary_update_status = f"{JAUNE}⚠️ Échec du téléchargement du binaire.{R}"
            return False
        except Exception as e:
            print(f"{ROUGE}❌ Erreur inattendue: {e}{R}")
            return False

    # NOUVELLE MÉTHODE POUR L'OPTION 7 : COMPILATION NUITKA (Ajoutée ici)
    def compile_remote_source_and_replace(self, remote_version: str) -> bool:
        """
        Télécharge le code source depuis GitHub, le compile avec Nuitka,
        et remplace le binaire actuel par le nouveau.
        """
        
        current_exe_path = os.path.abspath(sys.argv[0])
        exe_filename = os.path.basename(current_exe_path)
        
        # Détermine le nom de base du binaire attendu (sans extension, ex: mailtm_cli)
        base_name = os.path.splitext(REMOTE_SOURCE_FILENAME)[0] # base_name = 'mailtm_cli'
        
        temp_source_filename = REMOTE_SOURCE_FILENAME 
        temp_source_path = os.path.join(DOWNLOAD_PATH, temp_source_filename)
        
        # 1. Téléchargement du code source
        print(f"\n{CYAN}🔄 1/4 - Téléchargement du code source v{remote_version} depuis GitHub...{R}")
        
        url = RAW_SOURCE_URL 
        try:
            headers = {'User-Agent': get_random_user_agent()}
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status() 
            source_code_txt = r.text
        except Exception as e:
            print(f"{ROUGE}❌ Échec du téléchargement du code source depuis GitHub: {e}{R}")
            return False

        # 2. Sauvegarde dans un fichier temporaire
        try:
            with open(temp_source_path, 'w', encoding='utf-8') as f:
                f.write(source_code_txt)
            print(f"{VERT}✅ Code source sauvegardé dans le fichier temporaire: {temp_source_path}{R}")
        except Exception as e:
            print(f"{ROUGE}❌ Échec de l'écriture du fichier temporaire: {e}{R}")
            try: os.remove(temp_source_path)
            except Exception: pass
            return False
            
        # 3. Compilation avec Nuitka
        print(f"\n{CYAN}⚙️ 2/4 - Compilation du binaire avec Nuitka... (Ceci peut prendre du temps){R}")
        
        nuitka_command = ["nuitka"] + NUITKA_OPTIONS + [temp_source_path]
        nuitka_command.append(f"--output-dir={DOWNLOAD_PATH}") 
        
        # Exécution de Nuitka
        if not _run_nuitka_command(nuitka_command, f"Compilation de {temp_source_filename}"):
            try: os.remove(temp_source_path)
            except Exception: pass
            return False
        
        # Détermination du chemin du binaire compilé
        compiled_dir_name = f"{base_name}.dist"
        compiled_dir_path = os.path.join(DOWNLOAD_PATH, compiled_dir_name)
        
        compiled_exe_name = base_name 
        if platform.system() == "Windows":
            compiled_exe_name += ".exe"
            
        compiled_exe_path = os.path.join(compiled_dir_path, compiled_exe_name)

        # 4. Remplacement atomique
        print(f"\n{CYAN}📦 3/4 - Remplacement du binaire actuel par le nouveau...{R}")

        if not os.path.exists(compiled_exe_path):
             print(f"{ROUGE}❌ Échec: Binaire compilé introuvable. Attendu à : {compiled_exe_path}{R}")
             try: os.remove(temp_source_path)
             except Exception: pass
             try: shutil.rmtree(compiled_dir_path)
             except Exception: pass
             return False

        try:
            # 1. Remplacement atomique: Renommer l'ancien, puis le nouveau.
            temp_old_path = current_exe_path + ".old"
            os.replace(current_exe_path, temp_old_path) 
            os.replace(compiled_exe_path, current_exe_path)
            
            # 2. Nettoyage
            os.remove(temp_source_path) 
            shutil.rmtree(compiled_dir_path, ignore_errors=True) 
            os.remove(temp_old_path) 

            print(f"{VERT}✅ Mise à jour par compilation réussie ! Le nouveau binaire est à : {current_exe_path}{R}")
            print(f"{JAUNE}{GRAS}--------------------------------------------------{R}")
            print(f"{ROUGE}{GRAS}⚠️ IMPORTANT: Veuillez redémarrer l'application pour utiliser la nouvelle version.{R}")
            print(f"{JAUNE}{GRAS}--------------------------------------------------{R}")
            return True
            
        except Exception as e:
            print(f"{ROUGE}❌ Erreur inattendue lors du remplacement/nettoyage: {e}{R}")
            print(f"{JAUNE}Si l'erreur persiste, redémarrez l'application et réessayez.{R}")
            return False


    def get_domains(self):
        # ... (code inchangé) ...
        try:
            loading_spinner("Contact API Mail.tm pour les domaines...", 3.0)
            cleanup_line() 
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
            print(f"{ROUGE}❌ Erreur de connexion/timeout: {e}{R}")
        return []

    def login(self, email, password):
        # ... (code inchangé) ...
        try:
            loading_spinner("Authentification en cours...", 1.5)
            cleanup_line() 
            headers = {'User-Agent': get_random_user_agent()}
            data = {"address": email, "password": password}
            response = requests.post(f"{API_BASE}/token", json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('token')
        except Exception as e:
            print(f"{ROUGE}Erreur login: {e}{R}")
        return None

    def create_account(self):
        # ... (code inchangé) ...
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
        cleanup_line() 
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
        # ... (code inchangé) ...
        if not self.account or 'token' not in self.account:
            print(f"{JAUNE}⚠️ Erreur: Aucun jeton actif. Veuillez créer un compte d'abord.{R}")
            return []
        try:
            loading_spinner("Récupération des messages...", 2.0)
            cleanup_line() 
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
        # ... (code inchangé) ...
        if not self.account or 'token' not in self.account:
            return None
        try:
            loading_spinner("Téléchargement du message...", 1.5)
            cleanup_line() 
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
        # ... (code inchangé) ...
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
        # ... (code inchangé) ...
        if not self.account or 'token' not in self.account:
            print(f"{ROUGE}❌ Aucun compte actif pour surveiller.{R}")
            return
        
        print(f"\n{JAUNE}⏳ Démarrage de la surveillance active pour {self.account['email']}...{R}")
        print(f"{CYAN}Vérification max {duration}s, intervalle {poll_interval}s. Lancez votre inscription MAINTENANT.{R}")
        start_time = time.time()
        initial_message_count = self.silent_get_message_count()
        
        while time.time() - start_time < duration:
            current_time = int(time.time() - start_time)
            
            cleanup_line() 
            sys.stdout.write(f"{CYAN}🕰️  Temps écoulé: {current_time}s / {duration}s. Vérification des messages...{R}")
            sys.stdout.flush()
            
            try:
                current_count = self.silent_get_message_count()
                if current_count > initial_message_count:
                    cleanup_line() 
                    print(f"{VERT}{GRAS}✅ NOUVEAU MESSAGE REÇU !{R}")
                    messages = self.get_messages()
                    if messages:
                        new_message_id = messages[0].get('id', '')
                        self.display_message_content(new_message_id)
                    return
            except Exception:
                pass
            time.sleep(poll_interval)
            
        cleanup_line() 
        print(f"{JAUNE}⏱️  Temps d'attente écoulé ({duration}s). Aucun nouveau message trouvé.{R}")

    def display_inbox(self):
        # ... (code inchangé) ...
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
            print(f"   Objet: {subject}")
            print(f"   Date: {date}")
            print(f"   {GRAS}{CYAN}ID:{R} {msg_id}")
            print("-" * 50)

    def display_message_content(self, msg_id: str):
        # ... (code inchangé) ...
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
        # ... (code inchangé) ...
        if not self.account or 'token' not in self.account:
            return 0
        try:
            print("Vérification rapide des nouveaux messages...")
            time.sleep(3)
            clear_screen()

            cleanup_line() 

            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            response = requests.get(f"{API_BASE}/messages", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('hydra:member', []))
        except Exception:
            pass
        return 0

    def load_remote_plugins(self):
        # ... (code inchangé) ...
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
    print(f"{VERT}{GRAS}🤖 Mail.tm CLI - Gestion d'Email Temporaire {R}")

    remote_cfg = load_remote_config()
    # Utilisation de la classe AccessManager intégrée et corrigée
    access_manager = AccessManager() 
    device_id = get_or_create_device_id()
    cli = MailTmCLI(remote_config=remote_cfg)
    ADMIN_CODE = "ELISE2006"

    start_interface = False
    access_status_display = f"{JAUNE}Accès non validé.{R}"

    # Charger les codes et le SHA via la méthode de la classe intégrée
    access_manager.codes, access_manager.file_sha = access_manager.load_codes_from_github() 
    cleanup_line() 

    valid_access_code = None

    # --- VERIFICATION DU STATUT DE MISE À JOUR BINAIRE AU DÉMARRAGE ---
    update_available, remote_version = cli.check_remote_binary_version() # Récupère la version distante
    # ------------------------------------------------------------------

    # --- GESTION DE L'ACCÈS INITIAL / RECONNEXION ---
    for code, data in access_manager.codes.items():
        if data.get('claimed_by_device') == device_id:
            print(f"{CYAN}{GRAS}Vérification de l'accès permanent avec l'ID d'appareil..{R}")
            time.sleep(3)
            clear_screen()

            cleanup_line() 

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
        cleanup_line() 

        is_valid, status_message = access_manager.is_valid_code(access_code_input, device_id)
        if not is_valid:
            print(f"{ROUGE}❌ ACCÈS REFUSÉ: {status_message}{R}")
            return
        if access_code_input == ADMIN_CODE and "PERMANENT" in status_message.upper():
            status_display = f"{MAGENTA}VALIDÉ (ADMINISTRATEUR RÉCLAMÉ). Accès Permanent.{R}"
        else:
            status_display = f"{VERT}|| {status_message}{R}"
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
        print(CYAN + GRAS + "="*46 + R)
        print(CYAN + GRAS + "="*46 + R)
        print(f"{GRAS}\n    {JAUNE}M  E  N  U   {ROUGE}P  R  I  N  C  I  P  A  L{GRAS}  \n{R}")
        print(CYAN + GRAS + "="*46 + R)
        
        # --- AFFICHAGE DU STATUT BINAIRE DANS LE MENU ---
        print(f"{access_status_display}")
        print(f"{JAUNE}{GRAS}----------------------------------------------{R}") 
        print(f"{CYAN}Version : {R}{VERT}{CURRENT_BINARY_VERSION}{R}")
        # Affiche le statut d'alerte ou le statut normal
        if "🚨 NOUVELLE VERSION BINAIRE" in cli.binary_update_status:
            print(cli.binary_update_status) 
        else:
            print(f"{CYAN}Statut MàJ:{R} {cli.binary_update_status}")
        print(CYAN + GRAS + "="*46 + R)
        # -------------------------------------------------------

        if cli.account:
            print(f"\n|{MAGENTA}{GRAS}📧 COMPTE ACTIF : {JAUNE}{GRAS}{cli.account['email']}\n{R}")
            print(f"{VERT}[1] {ROUGE}[Désactivé] (Supprimer le compte actif){R}")
        else:
            print(f"{JAUNE}\n⚠️  Pas de compte actif. Vous devez en créer un (sur \nl'option 1){R}")
            print(f"{VERT}{GRAS}\n[1] Créer une nouvelle adresse email{R}")

        print(f"{CYAN}{GRAS}[2] Voir la boîte de réception{R}")
        print(f"{BLEU}{GRAS}[3] Lire un message par ID{R}")
        print(f"{MAGENTA}{GRAS}[4] Supprimer le compte email actuel{R}")
        print(f"{BLEU}[5] Vérifier et Actualiser les emails rapidement{R}")
        print(f"{VERT}{GRAS}[6] ⏳ Attendre automatiquement un email de vérification{R}")
        
        # MISE À JOUR DU TEXTE DE L'OPTION 7
        if update_available and remote_version:
             print(f"{ROUGE}{GRAS}[7] ⚡ Mettre à jour par compilation (v{remote_version}){R}")
        else:
             print(f"{CYAN}{GRAS}[7] 🔁 Vérifier l'état de mise à jour du binaire (Compilation){R}") 


        # Show plugin actions if any
        if cli.remote_plugins_actions:
            print(f"\n{MAGENTA}--- Actions plugins distants ---{R}")
            for idx, (title, _) in enumerate(cli.remote_plugins_actions, start=10):
                print(f"{MAGENTA}{idx}. {title}{R}")

        print(f"{ROUGE}{GRAS}0. Quitter{R}")

        choice = input(f"\n{BLEU}Votre choix (0-8): {R}").strip()

        if choice == '1':
            if not cli.account:
                cli.create_account()
            else:
                print(f"{JAUNE}❌ Veuillez d'abord {ROUGE}supprimer votre compte actif (Option 4){JAUNE} avant d'en créer un nouveau.{R}")
                time.sleep(3)

        elif choice == '2':
            cli.display_inbox()
            last_inbox_refresh = time.time()
            wait_for_input() 

        elif choice == '3':
            msg_id = input(f"{JAUNE}Entrez l'ID du message à lire (ou laissez vide pour annuler): {R}").strip() 
            if msg_id:
                cli.display_message_content(msg_id)
                wait_for_input() 

        elif choice == '4':
            if cli.account:
                confirm = input(f"{ROUGE}Êtes-vous sûr de vouloir supprimer les données locales du compte {cli.account['email']}? (oui/non): {R}").lower()
                if confirm == 'oui':
                    try:
                        os.remove(ACCOUNT_FILE)
                        cli.account = {}
                        print(f"{VERT}✅ Compte local supprimé.{R}")
                    except OSError as e:
                        print(f"{ROUGE}❌ Erreur de suppression du fichier {ACCOUNT_FILE}: {e}{R}")
                else:
                    print(f"{JAUNE}Opération annulée.{R}")
            else:
                print(f"{JAUNE}⚠️ Aucun compte actif à supprimer.{R}")
            time.sleep(2)

        elif choice == '5':
            if cli.account:
                new_count = cli.check_new_messages()
                if new_count > 0:
                    print(f"{VERT}🔔 {new_count} messages trouvés !{R}")
                else:
                    print(f"{VERT}✅ Aucune nouveauté.{R}")
                last_inbox_refresh = time.time()
            else:
                print(f"{JAUNE}⚠️ Créez un compte pour actualiser l'inbox.{R}")
            time.sleep(2)

        elif choice == '6':
            cli.wait_for_message(duration=120, poll_interval=5)
            wait_for_input() 

        # DÉBUT DE LA MODIFICATION DE L'OPTION 7 (Nuitka)
        elif choice == '7':
            sys.stdout.write(f"{CYAN}Vérification de l'état des mises à jour du binaire...{R}")
            sys.stdout.flush()
            
            # Mise à jour du statut et récupération de la version distante
            is_new_version_available, remote_version = cli.check_remote_binary_version()
            clear_screen()
            
            if not is_new_version_available:
                print(f"\n{VERT}✅ {cli.binary_update_status}{R}")
                time.sleep(3)
                continue # Retour au menu si déjà à jour

            print(f"\n{ROUGE}{GRAS}🚨 NOUVELLE VERSION ({remote_version}) DISPONIBLE !{R}")
            
            # Instructions pour la compilation et remplacement
            print(f"\n{JAUNE}{GRAS}--- PROCÉDURE DE MISE À JOUR PAR COMPILATION ---{R}")
            print(f"{CYAN}1. Téléchargement du code source v{remote_version} depuis GitHub.{R}")
            print(f"{CYAN}2. Compilation du code source en un nouveau binaire (Nuitka).{R}")
            print(f"{CYAN}3. Remplacement du binaire actuel par le nouveau.{R}")
            print(f"{CYAN}Le programme va {ROUGE}QUITER AUTOMATIQUEMENT{R} après un remplacement réussi.{R}")
            print(f"{JAUNE}{GRAS}------------------------------------------{R}")

            confirm = input(f"{VERT}Voulez-vous lancer la compilation et le remplacement maintenant ? (oui/non): {R}").lower()
            
            if confirm == 'oui':
                if cli.compile_remote_source_and_replace(remote_version): # APPEL DE LA FONCTION NUITKA
                    print(f"\n{VERT}{GRAS}✅ Compilation/Remplacement réussi. Sortie immédiate...{R}")
                    time.sleep(3)
                    sys.exit(0) # <-- SORTIE AUTOMATIQUE
                else:
                    wait_for_input("Échec de la mise à jour par compilation. Appuyez sur Entrée pour continuer...")
            else:
                print(f"{JAUNE}Mise à jour annulée.{R}")
                time.sleep(2)
        # FIN DE LA MODIFICATION DE L'OPTION 7

        elif choice == '0':
            print(f"{CYAN}Au revoir ! Merci d'utiliser Mail.tm CLI.{R}")
            sys.exit(0)

        elif choice.isdigit() and int(choice) >= 10:
            plugin_index = int(choice) - 10
            if 0 <= plugin_index < len(cli.remote_plugins_actions):
                title, func = cli.remote_plugins_actions[plugin_index]
                print(f"\n{MAGENTA}--- Exécution de l'action: {title} ---{R}")
                try:
                    func(cli) 
                except Exception as e:
                    print(f"{ROUGE}❌ Erreur d'exécution du plugin: {e}{R}")
                wait_for_input()
            else:
                print(f"{ROUGE}❌ Choix invalide.{R}")
                time.sleep(1)

        else:
            print(f"{ROUGE}❌ Choix invalide.{R}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main_cli()
    except KeyboardInterrupt:
        print(f"\n{CYAN}Interruption par l'utilisateur. Sortie.{R}")
        sys.exit(0)