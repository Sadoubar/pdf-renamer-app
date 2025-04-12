import streamlit as st
import os
import zipfile
import tempfile
import shutil
import re
import fitz # PyMuPDF
import time

# --- Configuration Streamlit ---
st.set_page_config(
    page_title="Renommeur PDF Greenprime",
    page_icon="📄", # Optionnel: Mettre une icone dans l'onglet navigateur
    layout="wide"
)

# --- Sidebar ---
logo_url = "https://www.shutterstock.com/shutterstock/photos/1938588211/display_1500/stock-photo-green-zone-dark-scary-green-colour-with-bright-white-fond-in-a-double-outline-circle-on-dark-1938588211.jpg"
st.sidebar.image(logo_url, width=150) # Ajuster la largeur si nécessaire
st.sidebar.title("Options & Infos")
st.sidebar.info("""
    ℹ️ **Mode Regex Local:**
    Extraction rapide et locale des références sans besoin d'API externe.
    Recherche le texte "Référence du rapport" dans les PDF.
    """)
# Vous pouvez ajouter d'autres options ou infos dans la sidebar plus tard

# --- Titre Principal ---
st.title("📄 Renommeur Automatique de Rapports PDF")
st.markdown("Optimisé par Greenprime") # Petit sous-titre

st.divider() # Séparateur visuel

# --- Instructions Utilisateur Clarifiées ---
st.markdown("### Comment utiliser cet outil :")
st.markdown("""
1.  **Déposez vos fichiers** dans la zone ci-dessous :
    *   Fichiers PDF individuels.
    *   **OU** une archive ZIP contenant vos PDF (même dans des sous-dossiers).
    *   *(Note : Pour traiter un dossier complet, compressez-le en ZIP d'abord.)*
2.  Cliquez sur **"🚀 Lancer le Traitement Regex"**.
3.  **Patientez** pendant l'analyse et le renommage (la barre de progression indique l'avancement).
4.  **Consultez le résumé** et **téléchargez** l'archive ZIP contenant les résultats.
""")

st.divider() # Séparateur visuel

# --- Fonctions (Inchangées) ---
def extraire_reference_avec_regex(pdf_path):
    """Extrait la référence d'un PDF en utilisant Regex. Moins verbeux."""
    pattern = re.compile(r"Référence du rapport\s+(.*)", re.IGNORECASE)
    reference_trouvee = None
    doc = None
    nom_fichier = os.path.basename(pdf_path) # Pour les logs d'erreur

    try:
        doc = fitz.open(pdf_path)
        max_pages_to_check = 5
        pages_checked = 0

        for page_num in range(min(len(doc), max_pages_to_check)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            match = pattern.search(text)
            if match:
                reference_brute = match.group(1).strip()
                reference_trouvee = reference_brute.split('\n')[0].strip()
                break
            pages_checked += 1
        return reference_trouvee
    except fitz.fitz.FileNotFoundError:
        # Log seulement si critique
        # st.error(f"❌ Erreur Fitz: Fichier non trouvé '{nom_fichier}'.")
        return None # Retourne None pour indiquer l'échec
    except Exception as e:
        st.error(f"❌ Erreur lecture/analyse Regex PDF '{nom_fichier}' : {type(e).__name__} - {e}")
        return None
    finally:
        if doc:
            try: doc.close()
            except: pass

def traiter_pdf(pdf_path, dossier_sortie):
    """
    Traite un PDF: extrait ref (Regex), renomme/copie. Moins verbeux.
    Retourne: status, nom_original
    """
    nom_fichier_original = os.path.basename(pdf_path)
    status = "unknown_error"

    if "REFERENCE" not in nom_fichier_original.upper():
        return "skipped_name", nom_fichier_original

    ref = extraire_reference_avec_regex(pdf_path)

    if ref is None:
         # La raison exacte (non trouvé vs erreur lecture) n'est pas différenciée ici
         # pour garder le retour simple. Les erreurs critiques sont logguées par extraire_reference.
        return "no_ref_or_error", nom_fichier_original

    ref_clean = "".join(c for c in ref if c.isalnum() or c in ('-', '_', '.')).strip()
    if not ref_clean:
         return "invalid_ref", nom_fichier_original

    nouveau_nom = f"RAPPORT - {ref_clean}.pdf"
    nouveau_chemin = os.path.join(dossier_sortie, nouveau_nom)

    count = 1
    base_name = f"RAPPORT - {ref_clean}"
    while os.path.exists(nouveau_chemin):
        nouveau_nom = f"{base_name}_{count}.pdf"
        nouveau_chemin = os.path.join(dossier_sortie, nouveau_nom)
        count += 1
        if count > 20:
             # Log l'erreur critique mais ne bloque pas tout
             st.error(f"❌ Trop de conflits de nom pour '{ref_clean}' ({nom_fichier_original}).")
             return "conflict_max", nom_fichier_original
    try:
        shutil.copy2(pdf_path, nouveau_chemin)
        return "success", nom_fichier_original
    except Exception as e:
        st.error(f"❌ Erreur copie '{nom_fichier_original}' → '{nouveau_nom}': {e}")
        return "copy_error", nom_fichier_original

def creer_zip_avec_resultats(dossier_source, nom_zip_final):
    """Crée une archive ZIP à partir du contenu du dossier source."""
    fichiers_ajoutes = 0
    try:
        with zipfile.ZipFile(nom_zip_final, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(dossier_source):
                for file in files:
                    if file.lower().endswith(".pdf"):
                        chemin_complet = os.path.join(root, file)
                        zipf.write(chemin_complet, arcname=file)
                        fichiers_ajoutes += 1
            if fichiers_ajoutes == 0:
                # Warning géré dans le flux principal
                if os.path.exists(nom_zip_final): os.remove(nom_zip_final)
                return None, 0
        return nom_zip_final, fichiers_ajoutes
    except Exception as e:
        st.error(f"❌ Erreur critique lors de la création de l'archive ZIP : {e}")
        if os.path.exists(nom_zip_final):
            try: os.remove(nom_zip_final)
            except OSError: pass
        return None, 0

# --- Interface Principale Streamlit ---

# Initialisation Session State (inchangé)
if 'zip_path' not in st.session_state:
    st.session_state['zip_path'] = None
if 'processing_done' not in st.session_state:
    st.session_state['processing_done'] = False
if 'summary_stats' not in st.session_state:
    st.session_state['summary_stats'] = {}

# --- Section 1: Dépôt des Fichiers ---
st.subheader("1. Déposer les fichiers")
uploaded_files = st.file_uploader(
    "Sélectionnez des PDF ou une archive ZIP",
    accept_multiple_files=True,
    type=['zip', 'pdf'],
    help="Vous pouvez déposer plusieurs PDF ou une seule archive ZIP contenant vos PDF (et leurs sous-dossiers).",
    label_visibility="collapsed" # Cache le label par défaut pour ne garder que le subheader
)

st.divider() # Séparateur visuel

# --- Section 2: Lancement du Traitement ---
st.subheader("2. Lancer le traitement")
# Créer des colonnes pour centrer le bouton (optionnel)
col1, col2, col3 = st.columns([1, 2, 1]) # Crée 3 colonnes, celle du milieu est 2x plus large
with col2: # Placer le bouton dans la colonne du milieu
    lancer_traitement = st.button(
        "🚀 Lancer le Traitement Regex",
        disabled=(not uploaded_files),
        use_container_width=True, # Le bouton prend la largeur de sa colonne
        type="primary" # Style de bouton principal (souvent bleu)
    )

# Diviseur après le bouton, avant les résultats potentiels
st.divider()

# --- Section 3: Traitement (si bouton cliqué) ---
if lancer_traitement:
    st.session_state['zip_path'] = None
    st.session_state['processing_done'] = False
    st.session_state['summary_stats'] = {}

    files_found_count = 0
    files_attempted_count = 0
    files_succeeded_count = 0
    files_failed_count = 0
    failed_files_details = []
    all_pdf_paths_to_process = []

    if uploaded_files:
        with tempfile.TemporaryDirectory() as temp_input_dir, \
             tempfile.TemporaryDirectory() as temp_output_dir:

            # Message de préparation général
            prep_placeholder = st.info("📁 Préparation des fichiers...")

            with st.spinner("Analyse des fichiers uploadés..."):
                zip_extracted_count = 0
                pdf_saved_count = 0
                # Boucle de sauvegarde/extraction (pas de messages individuels ici)
                for uploaded_file in uploaded_files:
                    temp_file_path = os.path.join(temp_input_dir, uploaded_file.name)
                    try:
                        with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                    except Exception as e:
                        st.error(f"❌ Erreur sauvegarde '{uploaded_file.name}': {e}")
                        continue

                    if uploaded_file.type == "application/zip" or temp_file_path.lower().endswith(".zip"):
                        try:
                            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_input_dir)
                            zip_extracted_count +=1
                            os.remove(temp_file_path)
                        except Exception as e: # Attraper toutes les erreurs d'extraction
                             st.error(f"❌ Erreur extraction '{uploaded_file.name}' : {e}")
                             try: os.remove(temp_file_path)
                             except OSError: pass
                    else:
                        pdf_saved_count += 1 # Compter les PDF individuels sauvegardés

            # Mise à jour du message de préparation après analyse
            prep_placeholder.info(f"📁 Préparation terminée. {pdf_saved_count} PDF direct(s), {zip_extracted_count} ZIP(s) extrait(s).")

            # Lister les PDF (silencieux)
            for root, dirs, files in os.walk(temp_input_dir):
                 dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
                 for file in files:
                    if file.lower().endswith(".pdf"):
                        all_pdf_paths_to_process.append(os.path.join(root, file))
            files_found_count = len(all_pdf_paths_to_process)

            if files_found_count == 0:
                 st.warning("⚠️ Aucun fichier PDF trouvé à traiter après préparation.")
            else:
                st.info(f"⚙️ Traitement de {files_found_count} fichier(s) PDF...")
                progress_placeholder = st.empty()
                with st.spinner(f"Analyse Regex en cours..."): # Spinner plus générique
                    progress_bar = progress_placeholder.progress(0, text="Analyse en cours...")

                    for i, pdf_path in enumerate(all_pdf_paths_to_process):
                        status, original_name = traiter_pdf(pdf_path, temp_output_dir)
                        if status != "skipped_name":
                             files_attempted_count += 1
                             if status == "success": files_succeeded_count += 1
                             else:
                                 files_failed_count += 1
                                 # Simplifier les raisons pour le résumé
                                 reason = status.replace("_", " ").capitalize()
                                 if status == "no_ref_or_error": reason = "Référence non trouvée ou erreur lecture"
                                 failed_files_details.append({"file": original_name, "reason": reason})

                        # Mise à jour de la barre de progression avec texte
                        progress_text = f"Analyse PDF {i+1}/{files_found_count}"
                        progress_bar.progress((i + 1) / files_found_count, text=progress_text)

                    progress_placeholder.empty() # Nettoyer la barre à la fin
                # st.info("🏁 Fin de l'analyse Regex.") # Remplacé par le résumé

                st.session_state['summary_stats'] = {
                    "found": files_found_count, "attempted": files_attempted_count,
                    "succeeded": files_succeeded_count, "failed": files_failed_count,
                    "failures": failed_files_details
                }

                # Création ZIP (silencieuse, sauf erreur critique)
                if files_succeeded_count > 0:
                    fd, final_zip_path_temp = tempfile.mkstemp(suffix=".zip", prefix="resultats_renommage_regex_")
                    os.close(fd)
                    zip_path, zip_count = creer_zip_avec_resultats(temp_output_dir, final_zip_path_temp)
                    st.session_state['zip_path'] = zip_path
                    if zip_path is None:
                         st.error("❌ Échec critique lors de la création de l'archive ZIP finale.")
                    # else: st.success(f"📦 Archive ZIP créée avec {zip_count} fichier(s).") # Optionnel
                # else:
                    # Le résumé indiquera 0 succès, pas besoin de warning ici
                    # st.warning("Aucun fichier renommé avec succès. Archive ZIP non créée.")
            st.session_state['processing_done'] = True
    # else: # Cas "not uploaded_files" déjà géré par disabled button
    #     st.warning("Veuillez déposer au moins un fichier ZIP ou PDF.")


# --- Section 4: Affichage du Résumé et du Bouton de Téléchargement (si traitement effectué) ---
if st.session_state['processing_done']:

    stats = st.session_state.get('summary_stats', {})
    if not stats and not uploaded_files: # Si on arrive ici sans avoir cliqué et sans fichier
         pass # Ne rien afficher
    elif not stats and uploaded_files: # Si on a cliqué mais aucune stat (ex: 0 pdf trouvé)
         st.warning("Aucune donnée à résumer (aucun PDF trouvé ou traité).")
    elif stats: # Si on a des stats
        st.subheader("📊 Résumé du Traitement")
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="PDF Trouvés", value=f"{stats.get('found', 0)}")
            st.metric(label="PDF Tentés (avec 'REFERENCE')", value=f"{stats.get('attempted', 0)}")
        with col2:
            st.metric(label="✅ Succès", value=f"{stats.get('succeeded', 0)}")
            st.metric(label="❌ Échecs", value=f"{stats.get('failed', 0)}", delta=f"-{stats.get('failed', 0)}", delta_color="inverse")


        failed_count = stats.get('failed', 0)
        if failed_count > 0:
             # Utiliser st.table pour un affichage plus structuré des erreurs si peu nombreuses
             # Ou garder l'expander si la liste peut être longue
             with st.expander(f"🔍 Voir les détails des {failed_count} échec(s)"):
                 # Créer un petit DataFrame pour un meilleur affichage
                 import pandas as pd
                 df_failures = pd.DataFrame(stats.get('failures', []))
                 df_failures.columns = ["Fichier", "Raison de l'échec"]
                 st.table(df_failures)
                 # Ou si on préfère la liste simple :
                 # for failure in stats.get('failures', []):
                 #     st.write(f"  - `{failure['file']}` ({failure['reason']})")


    # Afficher le bouton de téléchargement si le ZIP existe
    zip_path_final = st.session_state.get('zip_path')
    if zip_path_final and os.path.exists(zip_path_final):
        st.divider() # Séparateur avant le téléchargement
        st.subheader("3. Télécharger les résultats")
        with open(zip_path_final, "rb") as fp:
            # Utiliser des colonnes pour centrer le bouton de téléchargement
            dl_col1, dl_col2, dl_col3 = st.columns([1, 2, 1])
            with dl_col2:
                st.download_button(
                    label="📥 Télécharger l'archive ZIP",
                    data=fp,
                    file_name="rapports_renommes_greenprime.zip", # Nom de fichier personnalisé
                    mime="application/zip",
                    use_container_width=True, # Prend la largeur de sa colonne
                    type="primary" # Style de bouton principal
                )
    elif st.session_state['processing_done'] and stats.get('succeeded', 0) == 0:
        # Afficher un message si le traitement est fini mais 0 succès
        st.info("ℹ️ Aucun fichier n'a été renommé avec succès, l'archive ZIP n'a donc pas été générée.")