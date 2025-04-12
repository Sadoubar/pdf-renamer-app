from pyngrok import ngrok
import time

# Configurer le token d'authentification
ngrok.set_auth_token("2vUZWpWhFv9TIrwprvKyHzi3U0V_ZgfwzUeq5iinZZHiT6Tk")

# Ouvrir un tunnel HTTP vers le port où Streamlit fonctionne
public_url = ngrok.connect(8501)
print(f"URL publique: {public_url}")
print("Partagez cette URL avec vos collègues!")
print("Appuyez sur Ctrl+C pour arrêter le tunnel")

# Gardez le tunnel ouvert
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Fermeture du tunnel")
    ngrok.kill()