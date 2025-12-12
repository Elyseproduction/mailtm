def register(cli):
    def run_auto_skip():
        print("🔥 Plugin Auto-Skip chargé et fonctionnel !")
    cli.remote_plugins_actions.append(("Auto Skip", run_auto_skip))
