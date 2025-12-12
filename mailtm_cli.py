# mailtm_cli.py (Version Stabilité Mail.tm + Polling)
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
    # Assurez-vous que le fichier access_manager.py est présent
    from access_manager import AccessManager, loading_spinner, clear_screen, wait_for_input
except ImportError:
    print("FATAL: Le fichier access_manager.py est manquant ou contient une erreur de syntaxe/indentation. Assurez-vous qu'il est présent et correct.")
    sys.exit(1)

# --- CONSTANTES ---
API_BASE = "https://api.mail.tm"
ACCOUNT_FILE = "mailtm_account.json"
DEVICE_ID_FILE = "mailtm_device_id.txt" 
MAX_DISPLAY_MESSAGES = 50 
INBOX_REFRESH_INTERVAL = 60 # Intervalle d'actualisation en secondes

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

# --- FONCTIONS DE BASE ---

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
    """Crée un ID unique pour l'appareil local (utilisé pour réclamation du code)."""
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
    except Exception as e:
        return new_id 

def save_last_access_code(code: str):
    pass

def load_last_access_code() -> str:
    return ""


# --- CLASSE MAILTM ---

class MailTmCLI:
    def __init__(self):
        self.account = self.load_account()
        
    def load_account(self) -> dict:
        try:
            if os.path.exists(ACCOUNT_FILE):
                with open(ACCOUNT_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            pass 
        return {}

    def save_account(self):
        try:
            with open(ACCOUNT_FILE, 'w') as f:
                json.dump(self.account, f, indent=4)
        except Exception as e:
            print(f"{ROUGE}Erreur lors de la sauvegarde de {ACCOUNT_FILE}: {e}{R}")

    def get_domains(self):
        """
        Récupère la liste des domaines temporaires Mail.tm.
        Augmentation du timeout pour la stabilité.
        """
        try:
            # Augmentation du temps de spinner pour coller au timeout
            loading_spinner("Contact API Mail.tm pour les domaines...", 3.0) 
            headers = {'User-Agent': get_random_user_agent()}
            # *** FIX : Timeout passé de 10 à 30 secondes ***
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
                    # On ne garde que la partie nom de domaine et vérifie s'ils sont actifs
                    return [d.get('domain') for d in domains_list if d.get('isActive', True)]
                
                print(f"{JAUNE}⚠️ API a retourné un format inattendu ou aucun domaine actif.{R}")
                
            else:
                 # Afficher le code d'erreur de l'API pour un meilleur diagnostic
                 print(f"{ROUGE}❌ Erreur API: Code de statut {response.status_code}. Vérifiez la connexion.{R}")
                 
        except Exception as e:
            # Cette exception attrape les erreurs de connexion, de timeout, etc.
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
        # Cette fonction utilise le get_domains avec timeout=30 maintenant
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
            # Le timeout pour la création de compte reste à 10s car c'est rapide
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
        """
        Version rapide et silencieuse pour le polling.
        Compte le nombre total de messages.
        """
        if not self.account or 'token' not in self.account:
            return 0
            
        try:
            # N'affiche pas de spinner, seulement un petit message sur le terminal
            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            # Timeout très court pour ne pas bloquer le polling
            response = requests.get(f"{API_BASE}/messages", headers=headers, timeout=5) 
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get('hydra:member', []))
                
        except Exception:
            pass # Ignore les erreurs réseau silencieusement pendant le polling
            
        return 0

    def wait_for_message(self, duration=120, poll_interval=5):
        """
        Surveille activement la boîte de réception pendant une durée spécifiée. (OPTION 6)
        """
        if not self.account or 'token' not in self.account:
            print(f"{ROUGE}❌ Aucun compte actif pour surveiller.{R}")
            return
            
        print(f"\n{JAUNE}⏳ Démarrage de la surveillance active pour {self.account['email']}...{R}")
        print(f"{CYAN}Vérification max {duration}s, intervalle {poll_interval}s. Lancez votre inscription MAINTENANT.{R}")

        start_time = time.time()
        initial_message_count = self.silent_get_message_count() 
        
        while time.time() - start_time < duration:
            current_time = int(time.time() - start_time)
            
            # Ticker for active waiting
            sys.stdout.write(f"\r{CYAN}🕰️  Temps écoulé: {current_time}s / {duration}s. Vérification des messages...{R}")
            sys.stdout.flush()

            try:
                current_count = self.silent_get_message_count()
                    
                if current_count > initial_message_count:
                    sys.stdout.write("\n") 
                    print(f"{VERT}{GRAS}✅ NOUVEAU MESSAGE REÇU !{R}")
                    
                    # On prend le dernier message (le plus récent)
                    messages = self.get_messages() 
                    if messages:
                         new_message_id = messages[0].get('id', '') # Mail.tm renvoie le plus récent en premier
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
            """Recherche les codes PIN/OTP courants dans le texte."""
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
        """Vérifie s'il y a de nouveaux messages sans afficher la boîte de réception complète."""
        if not self.account or 'token' not in self.account:
            return 0
            
        try:
            # Utilisez un spinner plus court pour le mode 'check'
            loading_spinner("Vérification rapide des nouveaux messages...", 1.0) 
            headers = {"Authorization": f"Bearer {self.account['token']}", 'User-Agent': get_random_user_agent()}
            response = requests.get(f"{API_BASE}/messages", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return len(data.get('hydra:member', []))
                
        except Exception:
            # En cas d'erreur, on suppose 0 nouveau message pour ne pas bloquer le menu
            pass
            
        return 0


# --- FONCTION PRINCIPALE ---

def main_cli():
    
    clear_screen()
    print(f"{VERT}{GRAS}🤖 Mail.tm CLI - Gestion d'Email Temporaire{R}")
    
    # --- CONTRÔLE D'ACCÈS DISTANT ---
    access_manager = AccessManager() 
    device_id = get_or_create_device_id() 
    cli = MailTmCLI() 

    # 🔑 CODE CLÉ ADMINISTRATEUR (Doit être PERMANENT sur GitHub)
    ADMIN_CODE = "ELISE2006"
    
    start_interface = False
    access_status_display = f"{JAUNE}Accès non validé.{R}"
    
    # --- ÉTAPE 1: VÉRIFICATION AVEC L'ID DE L'APPAREIL RÉCLAMANT (PERSISTANCE DISTANTE) ---
    
    # Recharge les codes pour être sûr d'avoir la dernière version avant de chercher l'accès existant
    access_manager.codes, access_manager.file_sha = access_manager.load_codes_from_github()
    
    valid_access_code = None
    
    for code, data in access_manager.codes.items():
        if data.get('claimed_by_device') == device_id:
            # On trouve un code réclamé par cet appareil, on le vérifie immédiatement
            loading_spinner(f"{CYAN}Vérification de l'accès permanent avec l'ID d'appareil...{R}", 1.5)
            # La fonction is_valid_code vérifie l'expiration
            is_valid, status_message = access_manager.is_valid_code(code, device_id) 
            if is_valid:
                valid_access_code = code 
                # Message d'affichage spécial si c'est le code admin qui a été réclamé
                if code == ADMIN_CODE and "PERMANENT" in status_message.upper():
                    access_status_display = f"{MAGENTA}(ADMINISTRATEUR RÉCLAMÉ). Accès Permanent.{R}"
                else:
                    access_status_display = f"{VERT}{status_message}{R}"
                start_interface = True
                break

    # --- ÉTAPE 2: DEMANDE D'UN NOUVEAU CODE SI NON DÉMARRÉ ---
    if not start_interface:
        clear_screen() # Ajout du clear_screen pour nettoyer l'écran avant le prompt
        print(f"\n{CYAN}--- Aucune session d'accès distante trouvée ou code expiré ---{R}")
        access_code_input = input(f"{GRAS}🔐 Veuillez entrer le code d'accès: {R}").strip()

        if not access_code_input:
            print(f"{ROUGE}❌ Opération annulée. Aucun code entré.{R}")
            return

        # Cette ligne appelle loading_spinner
        loading_spinner("Vérification et réclamation du nouveau code", 2.0)
        
        # L'appel à is_valid_code gère la réclamation pour la première fois, 
        # vérifie si l'appareil est le réclamant, et vérifie l'expiration.
        is_valid, status_message = access_manager.is_valid_code(access_code_input, device_id)
        
        if not is_valid:
            print(f"{ROUGE}❌ ACCÈS REFUSÉ: {status_message}{R}")
            return
            
        # Si le code est le code Admin, nous affichons un message spécial.
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
        
    # Initialisation du minuteur d'actualisation de la boîte de réception
    last_inbox_refresh = time.time()
    
    while True:    
        
        # --- PROTECTION ANTI-CONTournement : RECHECK EXPIRATION ---
        is_valid, msg = access_manager.is_valid_code(valid_access_code, device_id)
        if not is_valid:
            clear_screen()
            print(f"{ROUGE}⛔ Votre abonnement a expiré !{R}")
            print(f"{JAUNE}{msg}{R}")
            print(f"{ROUGE}Veuillez vous réabonner pour continuer à utiliser le service.{R}")
            time.sleep(3)
            sys.exit(0)
# --- Affichage du minuteur d'actualisation ---
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

        # Accès et statut du temps de validation
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
            
        
        # Option 2: Voir la boîte de réception (Actualise implicitement)
        print(f"{CYAN}{GRAS}2. Voir la boîte de réception{R}")
        print(f"{BLEU}{GRAS}3. Lire un message par ID{R}")
        print(f"{MAGENTA}{GRAS}4. Supprimer le compte local{R}")
        
        # Option 5: Actualisation manuelle rapide
        print(f"{BLEU}5. Vérifier/Actualiser les emails rapidement \n{refresh_note}{R}")
        
        # *** NOUVELLE OPTION POUR LE POLLING ***
        print(f"{VERT}{GRAS}6. ⏳ Attendre automatiquement un email de vérification (Polling){R}") 
        
        # Option 0: Quitter
        print(f"{ROUGE}{GRAS}0. Quitter{R}")
        
        # Mise à jour des choix possibles
        choice = input(f"\n{BLEU}Votre choix (0-6): {R}").strip()
        
        if choice == '1':
            if not cli.account:
                cli.create_account()
            else:
                print(f"{JAUNE}❌ Veuillez d'abord {ROUGE}supprimer votre compte actif (Option 4){JAUNE} avant d'en créer un nouveau.{R}")
                time.sleep(3)
                
        elif choice == '2':
            cli.display_inbox()
            last_inbox_refresh = time.time() # Met à jour le temps d'actualisation
            
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
                # Surveillance active (2 minutes max, vérification toutes les 5 secondes)
                cli.wait_for_message(duration=120, poll_interval=5)
                last_inbox_refresh = time.time()
            else:
                print(f"{ROUGE}❌ Veuillez d'abord créer un compte (Option 1).{R}")
                time.sleep(3)
                
        elif choice == '0':
            print(f"{VERT}👋 Au revoir.{R}")
            break
            
        else:
            print(f"{ROUGE}Choix invalide. Veuillez réessayer.{R}")
            
        # Mise à jour pour inclure l'option 6
        if choice not in ['0', '1', '4', '5', '6']: 
            wait_for_input("Appuyez sur Entrée pour revenir au menu...")


if __name__ == '__main__':
    try:
        # Importations nécessaires pour le client
        import requests, html2text, uuid, platform
        main_cli()
    except ImportError as e:
        print(f"\n{ROUGE}--- ERREUR FATALE ---{R}")
        print(f"Dépendance manquante: {e}")
        print(f"Veuillez installer les paquets requis via pip:")
        print("pip install requests html2text colorama") 
        print(f"--------------------{R}\n")
