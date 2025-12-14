# plugins/example_plugin_1.py

import sys
from time import sleep

# Les couleurs doivent être re-définies ou importées si possible
VERT = '\033[32m'
R = '\033[0m'
CYAN = '\033[36m'
MAGENTA = '\033[35m'

def action_test(cli_instance):
    """
    Action simple pour tester le chargement du plugin.
    Affiche l'email du compte actif.
    """
    print(f"\n{MAGENTA}--- EXÉCUTION DU PLUGIN DE TEST ---{R}")
    if cli_instance.account:
        print(f"{VERT}Compte actif: {cli_instance.account['email']}{R}")
    else:
        print(f"{CYAN}Aucun compte actif trouvé.{R}")
    print(f"{MAGENTA}-----------------------------------{R}")
    sleep(1) 

def register(cli_instance):
    """
    Fonction d'enregistrement du plugin. Ajoute une action au menu principal.
    """
    # L'action apparaîtra dans le menu principal sous l'Option 10
    cli_instance.remote_plugins_actions.append(
        ("Exécuter le Plugin de Test", action_test)
    )
