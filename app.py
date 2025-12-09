import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import os
import pytz

# Configuration du fuseau horaire pour la France
TIMEZONE = pytz.timezone('Europe/Paris')

# Configuration de la page
st.set_page_config(
    page_title="Transport DanGE - Planning",
    page_icon="🚖",
    layout="wide"
)

# Connexion à la base de données
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'taxi_planning.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Initialiser la base de données
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table clients réguliers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients_reguliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_complet TEXT NOT NULL,
            telephone TEXT,
            adresse_pec_habituelle TEXT,
            adresse_depose_habituelle TEXT,
            type_course_habituel TEXT,
            tarif_habituel REAL,
            km_habituels REAL,
            remarques TEXT,
            actif BOOLEAN DEFAULT 1,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table courses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chauffeur_id INTEGER NOT NULL,
            nom_client TEXT NOT NULL,
            telephone_client TEXT,
            adresse_pec TEXT NOT NULL,
            lieu_depose TEXT NOT NULL,
            heure_prevue TIMESTAMP NOT NULL,
            heure_pec_prevue TEXT,
            temps_trajet_minutes INTEGER,
            heure_depart_calculee TEXT,
            type_course TEXT NOT NULL,
            tarif_estime REAL,
            km_estime REAL,
            commentaire TEXT,
            commentaire_chauffeur TEXT,
            statut TEXT DEFAULT 'nouvelle',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_confirmation TIMESTAMP,
            date_pec TIMESTAMP,
            date_depose TIMESTAMP,
            created_by INTEGER,
            client_regulier_id INTEGER,
            FOREIGN KEY (chauffeur_id) REFERENCES users (id),
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (client_regulier_id) REFERENCES clients_reguliers (id)
        )
    ''')
    
    # Vérifier et ajouter les colonnes manquantes si nécessaire (migration)
    try:
        # Vérifier si les colonnes de dates existent
        cursor.execute("PRAGMA table_info(courses)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Ajouter les colonnes manquantes
        if 'date_confirmation' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN date_confirmation TIMESTAMP')
            print("✓ Colonne date_confirmation ajoutée")
        
        if 'date_pec' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN date_pec TIMESTAMP')
            print("✓ Colonne date_pec ajoutée")
        
        if 'date_depose' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN date_depose TIMESTAMP')
            print("✓ Colonne date_depose ajoutée")
        
        if 'created_by' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN created_by INTEGER')
            print("✓ Colonne created_by ajoutée")
        
        if 'commentaire_chauffeur' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN commentaire_chauffeur TEXT')
            print("✓ Colonne commentaire_chauffeur ajoutée")
        
        if 'heure_pec_prevue' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN heure_pec_prevue TEXT')
            print("✓ Colonne heure_pec_prevue ajoutée")
        
        if 'temps_trajet_minutes' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN temps_trajet_minutes INTEGER')
            print("✓ Colonne temps_trajet_minutes ajoutée")
        
        if 'heure_depart_calculee' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN heure_depart_calculee TEXT')
            print("✓ Colonne heure_depart_calculee ajoutée")
        
        if 'client_regulier_id' not in columns:
            cursor.execute('ALTER TABLE courses ADD COLUMN client_regulier_id INTEGER')
            print("✓ Colonne client_regulier_id ajoutée")
            
    except Exception as e:
        print(f"Note: Migration des colonnes - {e}")
    
    # Créer le compte admin par défaut si n'existe pas
    try:
        hashed_password = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name)
            VALUES (?, ?, ?, ?)
        ''', ("admin", hashed_password, "admin", "Administrateur"))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # L'admin existe déjà
    
    conn.commit()
    conn.close()

# Fonction de hachage de mot de passe
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Fonction de connexion
def login(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    
    cursor.execute('''
        SELECT id, username, role, full_name
        FROM users
        WHERE username = ? AND password = ?
    ''', (username, hashed_password))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'full_name': user['full_name']
        }
    return None

# Fonction pour obtenir tous les chauffeurs
def get_chauffeurs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, full_name, username
        FROM users
        WHERE role = 'chauffeur'
        ORDER BY full_name
    ''')
    chauffeurs = cursor.fetchall()
    conn.close()
    # Convertir en liste de dictionnaires pour faciliter l'accès
    return [{'id': c['id'], 'full_name': c['full_name'], 'username': c['username']} for c in chauffeurs]

# ============ FONCTIONS CLIENTS RÉGULIERS ============

def create_client_regulier(data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO clients_reguliers (
            nom_complet, telephone, adresse_pec_habituelle, adresse_depose_habituelle,
            type_course_habituel, tarif_habituel, km_habituels, remarques
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['nom_complet'],
        data.get('telephone'),
        data.get('adresse_pec_habituelle'),
        data.get('adresse_depose_habituelle'),
        data.get('type_course_habituel'),
        data.get('tarif_habituel'),
        data.get('km_habituels'),
        data.get('remarques')
    ))
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id

def get_clients_reguliers(search_term=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if search_term:
        cursor.execute('''
            SELECT * FROM clients_reguliers
            WHERE actif = 1 AND nom_complet LIKE ?
            ORDER BY nom_complet
        ''', (f'%{search_term}%',))
    else:
        cursor.execute('''
            SELECT * FROM clients_reguliers
            WHERE actif = 1
            ORDER BY nom_complet
        ''')
    
    clients = cursor.fetchall()
    conn.close()
    
    result = []
    for client in clients:
        result.append({
            'id': client['id'],
            'nom_complet': client['nom_complet'],
            'telephone': client['telephone'],
            'adresse_pec_habituelle': client['adresse_pec_habituelle'],
            'adresse_depose_habituelle': client['adresse_depose_habituelle'],
            'type_course_habituel': client['type_course_habituel'],
            'tarif_habituel': client['tarif_habituel'],
            'km_habituels': client['km_habituels'],
            'remarques': client['remarques']
        })
    
    return result

def get_client_regulier(client_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients_reguliers WHERE id = ?', (client_id,))
    client = cursor.fetchone()
    conn.close()
    
    if client:
        return {
            'id': client['id'],
            'nom_complet': client['nom_complet'],
            'telephone': client['telephone'],
            'adresse_pec_habituelle': client['adresse_pec_habituelle'],
            'adresse_depose_habituelle': client['adresse_depose_habituelle'],
            'type_course_habituel': client['type_course_habituel'],
            'tarif_habituel': client['tarif_habituel'],
            'km_habituels': client['km_habituels'],
            'remarques': client['remarques']
        }
    return None

def update_client_regulier(client_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE clients_reguliers
        SET nom_complet = ?, telephone = ?, adresse_pec_habituelle = ?,
            adresse_depose_habituelle = ?, type_course_habituel = ?,
            tarif_habituel = ?, km_habituels = ?, remarques = ?
        WHERE id = ?
    ''', (
        data['nom_complet'],
        data.get('telephone'),
        data.get('adresse_pec_habituelle'),
        data.get('adresse_depose_habituelle'),
        data.get('type_course_habituel'),
        data.get('tarif_habituel'),
        data.get('km_habituels'),
        data.get('remarques'),
        client_id
    ))
    conn.commit()
    conn.close()

def delete_client_regulier(client_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Soft delete
    cursor.execute('UPDATE clients_reguliers SET actif = 0 WHERE id = ?', (client_id,))
    conn.commit()
    conn.close()

# ============ FIN FONCTIONS CLIENTS RÉGULIERS ============


# Fonction pour créer une course
def create_course(data):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO courses (
            chauffeur_id, nom_client, telephone_client, adresse_pec,
            lieu_depose, heure_prevue, heure_pec_prevue, temps_trajet_minutes,
            heure_depart_calculee, type_course, tarif_estime,
            km_estime, commentaire, created_by, client_regulier_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['chauffeur_id'],
        data['nom_client'],
        data['telephone_client'],
        data['adresse_pec'],
        data['lieu_depose'],
        data['heure_prevue'],
        data.get('heure_pec_prevue'),
        data.get('temps_trajet_minutes'),
        data.get('heure_depart_calculee'),
        data['type_course'],
        data['tarif_estime'],
        data['km_estime'],
        data['commentaire'],
        data['created_by'],
        data.get('client_regulier_id')
    ))
    
    conn.commit()
    course_id = cursor.lastrowid
    conn.close()
    return course_id
    conn.close()
    return True

# Fonction helper pour convertir date au format français
def format_date_fr(date_str):
    """Convertit une date ISO (YYYY-MM-DD) en format français (DD/MM/YYYY)"""
    if not date_str or len(date_str) < 10:
        return date_str
    annee, mois, jour = date_str[0:10].split('-')
    return f"{jour}/{mois}/{annee}"

# Fonction helper pour convertir date+heure au format français
def format_datetime_fr(datetime_str):
    """Convertit une datetime ISO (YYYY-MM-DD HH:MM:SS) en format français (DD/MM/YYYY HH:MM)"""
    if not datetime_str:
        return ""
    try:
        # Format: 2025-12-08 14:30:25 ou 2025-12-08T14:30:25
        datetime_str = datetime_str.replace('T', ' ')
        if len(datetime_str) >= 16:
            date_part = datetime_str[0:10]
            time_part = datetime_str[11:16]  # HH:MM seulement
            annee, mois, jour = date_part.split('-')
            return f"{jour}/{mois}/{annee} {time_part}"
        else:
            return format_date_fr(datetime_str)
    except:
        return datetime_str

# Fonction pour obtenir les courses
def get_courses(chauffeur_id=None, date_filter=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT c.*, u.full_name as chauffeur_name
        FROM courses c
        JOIN users u ON c.chauffeur_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if chauffeur_id:
        query += ' AND c.chauffeur_id = ?'
        params.append(chauffeur_id)
    
    if date_filter:
        query += ' AND DATE(c.heure_prevue) = ?'
        params.append(date_filter)
    
    query += ' ORDER BY c.heure_prevue DESC'
    
    cursor.execute(query, params)
    courses = cursor.fetchall()
    conn.close()
    
    # Convertir en liste de dictionnaires
    result = []
    for course in courses:
        # Gérer le cas où commentaire_chauffeur n'existe pas encore
        try:
            commentaire_chauffeur = course['commentaire_chauffeur']
        except (KeyError, IndexError):
            commentaire_chauffeur = None
        
        # Gérer le cas où heure_pec_prevue n'existe pas encore
        try:
            heure_pec_prevue = course['heure_pec_prevue']
        except (KeyError, IndexError):
            heure_pec_prevue = None
        
        # Gérer les nouvelles colonnes
        try:
            temps_trajet_minutes = course['temps_trajet_minutes']
        except (KeyError, IndexError):
            temps_trajet_minutes = None
        
        try:
            heure_depart_calculee = course['heure_depart_calculee']
        except (KeyError, IndexError):
            heure_depart_calculee = None
        
        try:
            client_regulier_id = course['client_regulier_id']
        except (KeyError, IndexError):
            client_regulier_id = None
        
        result.append({
            'id': course['id'],
            'chauffeur_id': course['chauffeur_id'],
            'nom_client': course['nom_client'],
            'telephone_client': course['telephone_client'],
            'adresse_pec': course['adresse_pec'],
            'lieu_depose': course['lieu_depose'],
            'heure_prevue': course['heure_prevue'],
            'heure_pec_prevue': heure_pec_prevue,
            'temps_trajet_minutes': temps_trajet_minutes,
            'heure_depart_calculee': heure_depart_calculee,
            'type_course': course['type_course'],
            'tarif_estime': course['tarif_estime'],
            'km_estime': course['km_estime'],
            'commentaire': course['commentaire'],
            'commentaire_chauffeur': commentaire_chauffeur,
            'statut': course['statut'],
            'date_creation': course['date_creation'],
            'date_confirmation': course['date_confirmation'],
            'date_pec': course['date_pec'],
            'date_depose': course['date_depose'],
            'created_by': course['created_by'],
            'client_regulier_id': client_regulier_id,
            'chauffeur_name': course['chauffeur_name']
        })
    
    return result

# Fonction pour mettre à jour le statut d'une course
def update_course_status(course_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Utiliser l'heure de Paris et la convertir en format ISO simple
    now_paris = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
    
    timestamp_field = {
        'confirmee': 'date_confirmation',
        'pec': 'date_pec',
        'deposee': 'date_depose'
    }
    
    if new_status in timestamp_field:
        cursor.execute(f'''
            UPDATE courses
            SET statut = ?, {timestamp_field[new_status]} = ?
            WHERE id = ?
        ''', (new_status, now_paris, course_id))
    else:
        cursor.execute('''
            UPDATE courses
            SET statut = ?
            WHERE id = ?
        ''', (new_status, course_id))
    
    conn.commit()
    conn.close()

# Fonction pour mettre à jour le commentaire du chauffeur
def update_commentaire_chauffeur(course_id, commentaire):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE courses
        SET commentaire_chauffeur = ?
        WHERE id = ?
    ''', (commentaire, course_id))
    
    conn.commit()
    conn.close()

# Fonction pour mettre à jour l'heure PEC prévue
def update_heure_pec_prevue(course_id, nouvelle_heure):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE courses
        SET heure_pec_prevue = ?
        WHERE id = ?
    ''', (nouvelle_heure, course_id))
    
    conn.commit()
    conn.close()
    return True

# Fonction pour supprimer une course
def delete_course(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM courses
        WHERE id = ?
    ''', (course_id,))
    
    conn.commit()
    conn.close()
    return True

# Fonction pour modifier heure PEC et chauffeur
def update_course_details(course_id, nouvelle_heure_pec, nouveau_chauffeur_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE courses
        SET heure_pec_prevue = ?, chauffeur_id = ?
        WHERE id = ?
    ''', (nouvelle_heure_pec, nouveau_chauffeur_id, course_id))
    
    conn.commit()
    conn.close()
    return True

# Fonction pour créer un utilisateur
def create_user(username, password, role, full_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name)
            VALUES (?, ?, ?, ?)
        ''', (username, hashed_password, role, full_name))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

# Fonction pour supprimer un utilisateur
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Vérifier qu'il ne reste pas le dernier admin
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user and user['role'] == 'admin' and admin_count <= 1:
            conn.close()
            return False, "Impossible de supprimer le dernier administrateur"
        
        # Supprimer l'utilisateur
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, "Utilisateur supprimé avec succès"
    except Exception as e:
        conn.close()
        return False, f"Erreur: {str(e)}"

# Fonction pour obtenir tous les utilisateurs
def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, role, full_name, created_at
        FROM users
        ORDER BY role, full_name
    ''')
    users = cursor.fetchall()
    conn.close()
    return users

# Interface de connexion
def login_page():
    st.title("Transport DanGE - Planning des courses")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("Connexion")
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter", use_container_width=True):
            user = login(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Nom d'utilisateur ou mot de passe incorrect")

# Interface Admin
def admin_page():
    st.title("🔧 Administration - Transport DanGE")
    st.markdown(f"**Connecté en tant que :** {st.session_state.user['full_name']} (Admin)")
    
    col_deconnexion, col_refresh = st.columns([1, 6])
    with col_deconnexion:
        if st.button("🚪 Déconnexion"):
            del st.session_state.user
            st.rerun()
    with col_refresh:
        if st.button("🔄 Actualiser", help="Recharger pour voir les dernières modifications"):
            st.rerun()
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Planning Global", "👥 Gestion des Comptes", "📈 Statistiques", "💾 Export"])
    
    with tab1:
        st.subheader("Planning Global de toutes les courses")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            show_all = st.checkbox("Afficher toutes les courses", value=True)
            if not show_all:
                date_filter = st.date_input("Filtrer par date", value=datetime.now())
            else:
                date_filter = None
        with col2:
            chauffeur_filter = st.selectbox("Filtrer par chauffeur", ["Tous"] + [c['full_name'] for c in get_chauffeurs()])
        with col3:
            statut_filter = st.selectbox("Filtrer par statut", ["Tous", "Nouvelle", "Confirmée", "PEC", "Déposée"])
        with col4:
            st.metric("Total courses", len(get_courses()))
        
        # Récupérer les courses
        chauffeur_id = None
        if chauffeur_filter != "Tous":
            chauffeurs = get_chauffeurs()
            for c in chauffeurs:
                if c['full_name'] == chauffeur_filter:
                    chauffeur_id = c['id']
                    break
        
        # Appliquer le filtre de date seulement si show_all est False
        date_filter_str = None
        if not show_all and date_filter:
            date_filter_str = date_filter.strftime('%Y-%m-%d')
        
        courses = get_courses(chauffeur_id=chauffeur_id, date_filter=date_filter_str)
        
        st.info(f"📊 {len(courses)} course(s) trouvée(s)")
        
        if courses:
            for course in courses:
                # Mapping des filtres affichés vers les statuts réels en base
                statut_mapping = {'Nouvelle': 'nouvelle', 'Confirmée': 'confirmee', 'PEC': 'pec', 'Déposée': 'deposee'}
                
                if statut_filter != "Tous":
                    statut_reel = statut_mapping.get(statut_filter, statut_filter.lower())
                    if course['statut'].lower() != statut_reel.lower():
                        continue
                    continue
                
                # Couleur selon le statut
                statut_colors = {
                    'nouvelle': '🔵',
                    'confirmee': '🟡',
                    'pec': '🔴',
                    'deposee': '🟢'
                }
                
                # Format français pour la date
                date_fr = format_date_fr(course['heure_prevue'])
                heure_affichage = course.get('heure_pec_prevue', course['heure_prevue'][11:16])
                titre_course = f"{statut_colors.get(course['statut'], '⚪')} {date_fr} {heure_affichage} - {course['nom_client']} ({course['chauffeur_name']})"
                
                with st.expander(titre_course):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client :** {course['nom_client']}")
                        st.write(f"**Téléphone :** {course['telephone_client']}")
                        st.write(f"**📅 Date PEC :** {format_date_fr(course['heure_prevue'])}")
                        if course.get('heure_pec_prevue'):
                            st.success(f"⏰ **Heure PEC prévue : {course['heure_pec_prevue']}**")
                        st.write(f"**PEC :** {course['adresse_pec']}")
                        st.write(f"**Dépose :** {course['lieu_depose']}")
                        st.write(f"**Type :** {course['type_course']}")
                    with col2:
                        st.write(f"**Chauffeur :** {course['chauffeur_name']}")
                        st.write(f"**Tarif estimé :** {course['tarif_estime']}€")
                        st.write(f"**Km estimé :** {course['km_estime']} km")
                        st.write(f"**Statut :** {course['statut'].upper()}")
                        if course['commentaire']:
                            st.write(f"**Commentaire secrétaire :** {course['commentaire']}")
                    
                    # Afficher le commentaire du chauffeur s'il existe
                    if course.get('commentaire_chauffeur'):
                        st.warning(f"💭 **Commentaire chauffeur** : {course['commentaire_chauffeur']}")
                    
                    # Afficher les horodatages
                    if course['date_confirmation']:
                        st.info(f"✅ Confirmée le : {format_datetime_fr(course['date_confirmation'])}")
                    if course['date_pec']:
                        st.info(f"📍 PEC effectuée le : {format_datetime_fr(course['date_pec'])}")
                    if course['date_depose']:
                        st.success(f"🏁 Déposée le : {format_datetime_fr(course['date_depose'])}")
        else:
            st.info("Aucune course pour cette sélection")
    
    with tab2:
        st.subheader("Gestion des comptes utilisateurs")
        
        # Créer un nouvel utilisateur
        with st.expander("➕ Créer un nouveau compte"):
            new_username = st.text_input("Nom d'utilisateur", key="new_user")
            new_password = st.text_input("Mot de passe", type="password", key="new_pass")
            new_full_name = st.text_input("Nom complet", key="new_name")
            new_role = st.selectbox("Rôle", ["chauffeur", "secretaire", "admin"], key="new_role")
            
            if st.button("Créer le compte"):
                if new_username and new_password and new_full_name:
                    if create_user(new_username, new_password, new_role, new_full_name):
                        st.success(f"Compte créé avec succès pour {new_full_name}")
                        st.rerun()
                    else:
                        st.error("Ce nom d'utilisateur existe déjà")
                else:
                    st.warning("Veuillez remplir tous les champs")
        
        # Liste des utilisateurs
        st.markdown("### Liste des utilisateurs")
        users = get_all_users()
        
        for user in users:
            role_icons = {
                'admin': '👑',
                'secretaire': '📝',
                'chauffeur': '🚖'
            }
            
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"{role_icons.get(user['role'], '👤')} **{user['full_name']}** - {user['username']} ({user['role']})")
            with col2:
                # Ne pas permettre de supprimer soi-même
                if user['id'] != st.session_state.user['id']:
                    if st.button("🗑️ Supprimer", key=f"delete_{user['id']}"):
                        success, message = delete_user(user['id'])
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.info("(Vous)")

    
    with tab3:
        st.subheader("📈 Statistiques")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Statistiques globales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cursor.execute("SELECT COUNT(*) FROM courses")
            total_courses = cursor.fetchone()[0]
            st.metric("Total courses", total_courses)
        
        with col2:
            cursor.execute("SELECT COUNT(*) FROM courses WHERE statut = 'deposee'")
            courses_terminees = cursor.fetchone()[0]
            st.metric("Courses terminées", courses_terminees)
        
        with col3:
            cursor.execute("SELECT COUNT(*) FROM courses WHERE statut IN ('nouvelle', 'confirmee', 'pec')")
            courses_en_cours = cursor.fetchone()[0]
            st.metric("Courses en cours", courses_en_cours)
        
        with col4:
            cursor.execute("SELECT SUM(tarif_estime) FROM courses WHERE statut = 'deposee'")
            ca_total = cursor.fetchone()[0] or 0
            st.metric("CA réalisé", f"{ca_total:.2f}€")
        
        conn.close()
    
    with tab4:
        st.subheader("💾 Export des données")
        st.write("Exporter les courses en CSV pour analyse ou comptabilité")
        
        export_date_debut = st.date_input("Date de début", value=datetime.now() - timedelta(days=30))
        export_date_fin = st.date_input("Date de fin", value=datetime.now())
        
        if st.button("Exporter en CSV"):
            conn = get_db_connection()
            query = '''
                SELECT 
                    c.id,
                    c.heure_prevue as "Date/Heure",
                    u.full_name as "Chauffeur",
                    c.nom_client as "Client",
                    c.telephone_client as "Téléphone",
                    c.adresse_pec as "Adresse PEC",
                    c.lieu_depose as "Lieu dépose",
                    c.type_course as "Type",
                    c.tarif_estime as "Tarif",
                    c.km_estime as "Km",
                    c.statut as "Statut",
                    c.date_confirmation as "Date confirmation",
                    c.date_pec as "Date PEC",
                    c.date_depose as "Date dépose"
                FROM courses c
                JOIN users u ON c.chauffeur_id = u.id
                WHERE DATE(c.heure_prevue) BETWEEN ? AND ?
                ORDER BY c.heure_prevue
            '''
            df = pd.read_sql_query(query, conn, params=(export_date_debut, export_date_fin))
            conn.close()
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Télécharger le CSV",
                data=csv,
                file_name=f"courses_export_{export_date_debut}_{export_date_fin}.csv",
                mime="text/csv"
            )

# Fonction callback pour les boutons du Planning du Jour (V1.13.6)
def set_delete_confirmation(course_id):
    """Active la confirmation de suppression pour une course"""
    st.session_state[f'confirm_del_jour_{course_id}'] = True

# Fonction de réattribution de course (V1.14.0)
def reassign_course_to_driver(course_id, new_chauffeur_id):
    """Réattribue une course à un nouveau chauffeur"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Récupérer les infos avant modification
    cursor.execute('''
        SELECT c.chauffeur_id, c.nom_client, u.full_name 
        FROM courses c
        JOIN users u ON c.chauffeur_id = u.id
        WHERE c.id = ?
    ''', (course_id,))
    result = cursor.fetchone()
    
    if result:
        old_chauffeur_id, nom_client, old_chauffeur_name = result
        
        # Récupérer le nom du nouveau chauffeur
        cursor.execute('SELECT full_name FROM users WHERE id = ?', (new_chauffeur_id,))
        new_chauffeur_name = cursor.fetchone()[0]
        
        # Mettre à jour la course
        cursor.execute('''
            UPDATE courses 
            SET chauffeur_id = ?
            WHERE id = ?
        ''', (new_chauffeur_id, course_id))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'course_id': course_id,
            'nom_client': nom_client,
            'old_chauffeur_id': old_chauffeur_id,
            'old_chauffeur_name': old_chauffeur_name,
            'new_chauffeur_id': new_chauffeur_id,
            'new_chauffeur_name': new_chauffeur_name
        }
    else:
        conn.close()
        return {'success': False, 'error': 'Course non trouvée'}

# Interface Secrétaire
def secretaire_page():
    st.title("📝 Secrétariat - Planning des courses")
    st.markdown(f"**Connecté en tant que :** {st.session_state.user['full_name']} (Secrétaire)")
    
    col_deconnexion, col_refresh = st.columns([1, 6])
    with col_deconnexion:
        if st.button("🚪 Déconnexion"):
            del st.session_state.user
            st.rerun()
    with col_refresh:
        if st.button("🔄 Actualiser", help="Recharger pour voir les dernières modifications"):
            st.rerun()
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Nouvelle Course", "📊 Planning Global", "📅 Planning Semaine", "📆 Planning du Jour"])
    
    with tab1:
        st.subheader("Créer une nouvelle course")
        
        # Gestion duplication
        course_dupliquee = None
        if 'course_to_duplicate' in st.session_state:
            course_dupliquee = st.session_state.course_to_duplicate
            st.success(f"📋 Duplication de : {course_dupliquee['nom_client']} - {course_dupliquee['adresse_pec']} → {course_dupliquee['lieu_depose']}")
            if st.button("❌ Annuler la duplication"):
                del st.session_state.course_to_duplicate
                st.rerun()
        
        # Récupérer les chauffeurs AVANT le formulaire
        chauffeurs = get_chauffeurs()
        
        if not chauffeurs:
            st.error("⚠️ Aucun chauffeur disponible. Veuillez d'abord créer des comptes chauffeurs dans l'interface Admin.")
        else:
            # Recherche client régulier
            col_search1, col_search2 = st.columns([3, 1])
            with col_search1:
                search_client = st.text_input("🔍 Rechercher un client régulier (tapez le début du nom)", key="search_client")
            
            client_selectionne = None
            if search_client and len(search_client) >= 2:
                clients_trouves = get_clients_reguliers(search_client)
                if clients_trouves:
                    with col_search2:
                        st.write("")  # Espace
                        st.write("")  # Espace
                        st.info(f"✓ {len(clients_trouves)} client(s) trouvé(s)")
                    
                    # Afficher les suggestions
                    for client in clients_trouves[:5]:  # Max 5 suggestions
                        with st.expander(f"👤 {client['nom_complet']} - {client['telephone'] or 'Pas de tél'}", expanded=False):
                            st.write(f"**PEC habituelle :** {client['adresse_pec_habituelle']}")
                            st.write(f"**Dépose habituelle :** {client['adresse_depose_habituelle']}")
                            st.write(f"**Type :** {client['type_course_habituel']} | **Tarif :** {client['tarif_habituel']}€ | **Km :** {client['km_habituels']} km")
                            if st.button(f"✅ Utiliser ce client", key=f"select_{client['id']}"):
                                client_selectionne = client
                                st.rerun()
            
            st.markdown("---")
            
            with st.form("new_course_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Créer les options pour le selectbox
                    chauffeur_names = [c['full_name'] for c in chauffeurs]
                    selected_chauffeur = st.selectbox("Chauffeur *", chauffeur_names)
                    
                    # Pré-remplir si client sélectionné ou course dupliquée
                    if course_dupliquee:
                        default_nom = course_dupliquee['nom_client']
                        default_tel = course_dupliquee['telephone_client']
                        default_pec = course_dupliquee['adresse_pec']
                        default_depose = course_dupliquee['lieu_depose']
                    elif client_selectionne:
                        default_nom = client_selectionne['nom_complet']
                        default_tel = client_selectionne['telephone']
                        default_pec = client_selectionne['adresse_pec_habituelle']
                        default_depose = client_selectionne['adresse_depose_habituelle']
                    else:
                        default_nom = ""
                        default_tel = ""
                        default_pec = ""
                        default_depose = ""
                    
                    nom_client = st.text_input("Nom du client *", value=default_nom)
                    telephone_client = st.text_input("Téléphone du client", value=default_tel)
                    adresse_pec = st.text_input("Adresse de prise en charge *", value=default_pec)
                    lieu_depose = st.text_input("Lieu de dépose *", value=default_depose)
                
                with col2:
                    # Pré-remplir les valeurs par défaut AVANT de les utiliser
                    if course_dupliquee:
                        default_type = course_dupliquee['type_course']
                        default_tarif = course_dupliquee['tarif_estime']
                        default_km = course_dupliquee['km_estime']
                        default_heure_pec = course_dupliquee.get('heure_pec_prevue', '')
                    elif client_selectionne:
                        default_type = client_selectionne['type_course_habituel']
                        default_tarif = client_selectionne['tarif_habituel']
                        default_km = client_selectionne['km_habituels']
                        default_heure_pec = ''
                    else:
                        default_type = "CPAM"
                        default_tarif = 0.0
                        default_km = 0.0
                        default_heure_pec = ''
                    
                    # Utiliser l'heure de Paris pour les valeurs par défaut
                    now_paris = datetime.now(TIMEZONE)
                    date_course = st.date_input("Date de la course *", value=now_paris.date())
                    heure_pec_prevue = st.text_input("Heure PEC prévue (HH:MM)", value=default_heure_pec, placeholder="Ex: 17:50", help="Heure à laquelle le chauffeur doit arriver chez le client")
                    
                    type_course = st.selectbox("Type de course *", ["CPAM", "Privé"], index=0 if default_type == "CPAM" else 1)
                    tarif_estime = st.number_input("Tarif estimé (€)", min_value=0.0, step=5.0, value=float(default_tarif) if default_tarif else 0.0)
                    km_estime = st.number_input("Kilométrage estimé", min_value=0.0, step=1.0, value=float(default_km) if default_km else 0.0)
                    commentaire = st.text_area("Commentaire")
                    
                    # Option sauvegarde client régulier
                    sauvegarder_client = False
                    if not client_selectionne:
                        sauvegarder_client = st.checkbox("💾 Sauvegarder comme client régulier", help="Ce client pourra être réutilisé rapidement")
                
                submitted = st.form_submit_button("✅ Créer la course", use_container_width=True)
                
                if submitted:
                    if nom_client and adresse_pec and lieu_depose and selected_chauffeur:
                        # Trouver l'ID du chauffeur sélectionné
                        chauffeur_id = None
                        for c in chauffeurs:
                            if c['full_name'] == selected_chauffeur:
                                chauffeur_id = c['id']
                                break
                        
                        if chauffeur_id is None:
                            st.error("❌ Erreur : Chauffeur non trouvé")
                        else:
                            # Sauvegarder comme client régulier si demandé
                            client_id = None
                            if sauvegarder_client and not client_selectionne:
                                client_data = {
                                    'nom_complet': nom_client,
                                    'telephone': telephone_client,
                                    'adresse_pec_habituelle': adresse_pec,
                                    'adresse_depose_habituelle': lieu_depose,
                                    'type_course_habituel': type_course,
                                    'tarif_habituel': tarif_estime,
                                    'km_habituels': km_estime,
                                    'remarques': commentaire
                                }
                                client_id = create_client_regulier(client_data)
                            elif client_selectionne:
                                client_id = client_selectionne['id']
                            
                            # Utiliser l'heure actuelle de Paris pour heure_prevue
                            # Stocker en format ISO simple (sans timezone) pour compatibilité SQLite
                            heure_prevue_naive = datetime.combine(date_course, datetime.now(TIMEZONE).time())
                            heure_prevue = heure_prevue_naive.strftime('%Y-%m-%d %H:%M:%S')
                            
                            course_data = {
                                'chauffeur_id': chauffeur_id,
                                'nom_client': nom_client,
                                'telephone_client': telephone_client,
                                'adresse_pec': adresse_pec,
                                'lieu_depose': lieu_depose,
                                'heure_prevue': heure_prevue,
                                'heure_pec_prevue': heure_pec_prevue if heure_pec_prevue else None,
                                'type_course': type_course,
                                'tarif_estime': tarif_estime,
                                'km_estime': km_estime,
                                'commentaire': commentaire,
                                'created_by': st.session_state.user['id'],
                                'client_regulier_id': client_id
                            }
                            
                            course_id = create_course(course_data)
                            if course_id:
                                msg = f"✅ Course créée avec succès pour {selected_chauffeur}"
                                if sauvegarder_client:
                                    msg += f" | Client '{nom_client}' enregistré"
                                if course_dupliquee:
                                    msg += " | Duplication réussie"
                                    # Nettoyer la session
                                    if 'course_to_duplicate' in st.session_state:
                                        del st.session_state.course_to_duplicate
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la création de la course")
                    else:
                        st.error("Veuillez remplir tous les champs obligatoires (*)")
    
    with tab2:
        st.subheader("Planning Global")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            show_all_sec = st.checkbox("Afficher toutes les courses", value=True, key="sec_show_all")
            if not show_all_sec:
                date_filter = st.date_input("Date", value=datetime.now(), key="sec_date")
            else:
                date_filter = None
        with col2:
            chauffeur_filter = st.selectbox("Chauffeur", ["Tous"] + [c['full_name'] for c in get_chauffeurs()], key="sec_chauff")
        with col3:
            statut_filter = st.selectbox("Statut", ["Tous", "Nouvelle", "Confirmée", "PEC", "Déposée"], key="sec_statut")
        with col4:
            st.metric("Total courses", len(get_courses()))
        
        # Récupérer les courses
        chauffeur_id = None
        if chauffeur_filter != "Tous":
            chauffeurs = get_chauffeurs()
            for c in chauffeurs:
                if c['full_name'] == chauffeur_filter:
                    chauffeur_id = c['id']
                    break
        
        # Appliquer le filtre de date seulement si show_all est False
        date_filter_str = None
        if not show_all_sec and date_filter:
            date_filter_str = date_filter.strftime('%Y-%m-%d')
        
        courses = get_courses(chauffeur_id=chauffeur_id, date_filter=date_filter_str)
        
        st.info(f"📊 {len(courses)} course(s) trouvée(s)")
        
        if courses:
            for course in courses:
                # Mapping des filtres affichés vers les statuts réels en base
                statut_mapping = {'Nouvelle': 'nouvelle', 'Confirmée': 'confirmee', 'PEC': 'pec', 'Déposée': 'deposee'}
                
                if statut_filter != "Tous":
                    statut_reel = statut_mapping.get(statut_filter, statut_filter.lower())
                    if course['statut'].lower() != statut_reel.lower():
                        continue
                    continue
                
                # Couleur selon le statut
                statut_colors = {
                    'nouvelle': '🔵',
                    'confirmee': '🟡',
                    'pec': '🔴',
                    'deposee': '🟢'
                }
                
                # Format français pour la date
                date_fr = format_date_fr(course['heure_prevue'])
                heure_affichage = course.get('heure_pec_prevue', course['heure_prevue'][11:16])
                titre_course = f"{statut_colors.get(course['statut'], '⚪')} {date_fr} {heure_affichage} - {course['nom_client']} ({course['chauffeur_name']})"
                
                with st.expander(titre_course):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client :** {course['nom_client']}")
                        st.write(f"**Téléphone :** {course['telephone_client']}")
                        st.write(f"**📅 Date PEC :** {format_date_fr(course['heure_prevue'])}")
                        if course.get('heure_pec_prevue'):
                            st.success(f"⏰ **Heure PEC prévue : {course['heure_pec_prevue']}**")
                        st.write(f"**PEC :** {course['adresse_pec']}")
                        st.write(f"**Dépose :** {course['lieu_depose']}")
                        st.write(f"**Type :** {course['type_course']}")
                    with col2:
                        st.write(f"**Chauffeur :** {course['chauffeur_name']}")
                        st.write(f"**Tarif estimé :** {course['tarif_estime']}€")
                        st.write(f"**Km estimé :** {course['km_estime']} km")
                        st.write(f"**Statut :** {course['statut'].upper()}")
                        if course['commentaire']:
                            st.write(f"**Commentaire secrétaire :** {course['commentaire']}")
                    
                    # Afficher le commentaire du chauffeur s'il existe
                    if course.get('commentaire_chauffeur'):
                        st.warning(f"💭 **Commentaire chauffeur** : {course['commentaire_chauffeur']}")
                    
                    # Afficher les horodatages
                    if course['date_confirmation']:
                        st.info(f"✅ Confirmée le : {format_datetime_fr(course['date_confirmation'])}")
                    if course['date_pec']:
                        st.info(f"📍 PEC effectuée le : {format_datetime_fr(course['date_pec'])}")
                    if course['date_depose']:
                        st.success(f"🏁 Déposée le : {format_datetime_fr(course['date_depose'])}")
                    
                    # Boutons Supprimer et Modifier
                    st.markdown("---")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    # Bouton Supprimer avec confirmation
                    with col_btn1:
                        if st.button(f"🗑️ Supprimer cette course", key=f"del_sec_{course['id']}", use_container_width=True):
                            st.session_state[f'confirmer_suppression_{course["id"]}'] = True
                            st.rerun()
                    
                    # Bouton Modifier
                    with col_btn2:
                        if st.button(f"✏️ Modifier", key=f"mod_sec_{course['id']}", use_container_width=True):
                            st.session_state[f'modifier_course_{course["id"]}'] = True
                            st.rerun()
                    
                    # Confirmation de suppression
                    if st.session_state.get(f'confirmer_suppression_{course["id"]}', False):
                        st.markdown("---")
                        st.warning("⚠️ Êtes-vous sûr de vouloir supprimer cette course ?")
                        st.caption(f"Course : {course['nom_client']} - {course['adresse_pec']} → {course['lieu_depose']}")
                        
                        col_conf1, col_conf2 = st.columns(2)
                        with col_conf1:
                            if st.button("❌ Annuler", key=f"cancel_del_{course['id']}", use_container_width=True):
                                del st.session_state[f'confirmer_suppression_{course["id"]}']
                                st.rerun()
                        with col_conf2:
                            if st.button("✅ Confirmer la suppression", key=f"confirm_del_{course['id']}", use_container_width=True):
                                delete_course(course['id'])
                                st.success("✅ Course supprimée avec succès")
                                del st.session_state[f'confirmer_suppression_{course["id"]}']
                                st.rerun()
                    
                    # Formulaire de modification (heure PEC + chauffeur)
                    if st.session_state.get(f'modifier_course_{course["id"]}', False):
                        st.markdown("---")
                        st.subheader("✏️ Modifier la course")
                        
                        # Récupérer tous les chauffeurs
                        chauffeurs = get_chauffeurs()
                        
                        # Heure PEC
                        heure_actuelle = course.get('heure_pec_prevue', '')
                        nouvelle_heure_pec = st.text_input(
                            "Heure PEC (format HH:MM)",
                            value=heure_actuelle,
                            placeholder="Ex: 14:30",
                            key=f"input_heure_mod_{course['id']}"
                        )
                        
                        # Chauffeur
                        chauffeur_actuel_id = course['chauffeur_id']
                        # Trouver l'index du chauffeur actuel
                        chauffeur_actuel_index = 0
                        for i, ch in enumerate(chauffeurs):
                            if ch['id'] == chauffeur_actuel_id:
                                chauffeur_actuel_index = i
                                break
                        
                        nouveau_chauffeur = st.selectbox(
                            "Chauffeur",
                            options=chauffeurs,
                            format_func=lambda x: x['full_name'],
                            index=chauffeur_actuel_index,
                            key=f"select_chauffeur_mod_{course['id']}"
                        )
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 Enregistrer", key=f"save_mod_{course['id']}", use_container_width=True):
                                # Valider le format de l'heure
                                heure_valide = True
                                nouvelle_heure_normalisee = None
                                
                                if nouvelle_heure_pec:
                                    parts = nouvelle_heure_pec.split(':')
                                    if len(parts) == 2:
                                        try:
                                            h = int(parts[0])
                                            m = int(parts[1])
                                            if 0 <= h <= 23 and 0 <= m <= 59:
                                                nouvelle_heure_normalisee = f"{h:02d}:{m:02d}"
                                            else:
                                                st.error("❌ Heure invalide (0-23h et 0-59min)")
                                                heure_valide = False
                                        except ValueError:
                                            st.error("❌ Format invalide. Utilisez HH:MM (ex: 14:30)")
                                            heure_valide = False
                                    else:
                                        st.error("❌ Format invalide. Utilisez HH:MM (ex: 14:30)")
                                        heure_valide = False
                                
                                if heure_valide:
                                    # Mise à jour
                                    update_course_details(course['id'], nouvelle_heure_normalisee, nouveau_chauffeur['id'])
                                    
                                    # Message de confirmation
                                    msg_heure = f"Heure PEC = {nouvelle_heure_normalisee}" if nouvelle_heure_normalisee else "Heure PEC supprimée"
                                    msg_chauffeur = f"Chauffeur = {nouveau_chauffeur['full_name']}"
                                    st.success(f"✅ Course modifiée : {msg_heure}, {msg_chauffeur}")
                                    
                                    del st.session_state[f'modifier_course_{course["id"]}']
                                    st.rerun()
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_mod_{course['id']}", use_container_width=True):
                                del st.session_state[f'modifier_course_{course["id"]}']
                                st.rerun()
        else:
            st.info("Aucune course pour cette sélection")
    
    with tab3:
        st.subheader("📅 Planning Hebdomadaire")
        
        # Sélection de la semaine
        col_week1, col_week2, col_week3 = st.columns([1, 2, 1])
        
        # Initialiser la date de référence
        if 'week_start_date' not in st.session_state:
            st.session_state.week_start_date = datetime.now(TIMEZONE).date()
            # Ajuster au lundi
            days_to_monday = st.session_state.week_start_date.weekday()
            st.session_state.week_start_date = st.session_state.week_start_date - timedelta(days=days_to_monday)
        
        with col_week1:
            if st.button("⬅️ Semaine précédente"):
                st.session_state.week_start_date = st.session_state.week_start_date - timedelta(days=7)
                st.rerun()
        
        with col_week2:
            week_end_date = st.session_state.week_start_date + timedelta(days=6)
            st.markdown(f"### Semaine du {st.session_state.week_start_date.strftime('%d/%m')} au {week_end_date.strftime('%d/%m/%Y')}")
            
            if st.button("📅 Aujourd'hui"):
                today = datetime.now(TIMEZONE).date()
                days_to_monday = today.weekday()
                st.session_state.week_start_date = today - timedelta(days=days_to_monday)
                st.rerun()
        
        with col_week3:
            if st.button("Semaine suivante ➡️"):
                st.session_state.week_start_date = st.session_state.week_start_date + timedelta(days=7)
                st.rerun()
        
        # Récupérer toutes les courses de la semaine
        week_courses = []
        for day_offset in range(7):
            day_date = st.session_state.week_start_date + timedelta(days=day_offset)
            day_courses = get_courses(date_filter=day_date.strftime('%Y-%m-%d'))
            for course in day_courses:
                course['day_offset'] = day_offset
                week_courses.append(course)
        
        # Afficher le planning
        st.markdown("---")
        
        # Vérifier si on veut afficher le détail d'un jour
        if 'view_day_detail' in st.session_state and st.session_state.view_day_detail:
            # AFFICHAGE DÉTAILLÉ DU JOUR (Page séparée)
            selected_day = st.session_state.selected_day_date
            
            jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            jour_semaine = jours_fr[selected_day.weekday()]
            
            col_back, col_title = st.columns([1, 5])
            with col_back:
                if st.button("⬅️ Retour au planning semaine"):
                    st.session_state.view_day_detail = False
                    st.rerun()
            with col_title:
                st.markdown(f"## 📅 {jour_semaine} {selected_day.strftime('%d/%m/%Y')}")
            
            st.markdown("---")
            
            # Récupérer tous les chauffeurs
            chauffeurs = get_chauffeurs()
            
            # Récupérer toutes les courses de ce jour
            courses_jour = get_courses(date_filter=selected_day.strftime('%Y-%m-%d'))
            
            # Créer 4 colonnes fixes pour les chauffeurs
            nb_colonnes = 4
            cols_chauffeurs = st.columns(nb_colonnes)
            
            for i in range(nb_colonnes):
                with cols_chauffeurs[i]:
                    if i < len(chauffeurs):
                        chauffeur = chauffeurs[i]
                        st.markdown(f"### 🚗 {chauffeur['full_name']}")
                        
                        # Filtrer les courses de ce chauffeur
                        courses_chauffeur = [c for c in courses_jour if c['chauffeur_id'] == chauffeur['id']]
                        
                        # Trier par heure PEC prévue
                        courses_chauffeur.sort(key=lambda c: c.get('heure_pec_prevue') or c['heure_prevue'][11:16] or '')
                        
                        if courses_chauffeur:
                            for course in courses_chauffeur:
                                statut_emoji = {
                                    'nouvelle': '🔵',
                                    'confirmee': '🟡',
                                    'pec': '🔴',
                                    'deposee': '🟢'
                                }
                                emoji = statut_emoji.get(course['statut'], '⚪')
                                
                                # Heure à afficher
                                heure_affichage = course.get('heure_pec_prevue')
                                if not heure_affichage:
                                    heure_affichage = course['heure_prevue'][11:16]
                                
                                # Normaliser l'heure
                                if heure_affichage:
                                    parts = heure_affichage.split(':')
                                    if len(parts) == 2:
                                        h, m = parts
                                        heure_affichage = f"{int(h):02d}:{m}"
                                
                                # Affichage avec popup
                                with st.popover(f"{emoji} {heure_affichage} - {course['nom_client']}", use_container_width=True):
                                    st.markdown(f"**{course['nom_client']}**")
                                    st.caption(f"📞 {course['telephone_client']}")
                                    
                                    if course.get('heure_pec_prevue'):
                                        heure_pec = course['heure_pec_prevue']
                                        parts = heure_pec.split(':')
                                        if len(parts) == 2:
                                            h, m = parts
                                            heure_pec = f"{int(h):02d}:{m}"
                                        st.caption(f"⏰ **Heure PEC:** {heure_pec}")
                                    
                                    st.caption(f"📍 **PEC:** {course['adresse_pec']}")
                                    st.caption(f"🏁 **Dépose:** {course['lieu_depose']}")
                                    st.caption(f"💼 {course['type_course']}")
                                    st.caption(f"💰 {course['tarif_estime']}€ | {course['km_estime']} km")
                                    
                                    # Boutons d'action selon le statut
                                    st.markdown("---")
                                    col_actions = st.columns(3)
                                    
                                    if course['statut'] == 'nouvelle':
                                        with col_actions[0]:
                                            if st.button("✅ Confirmer", key=f"confirm_detail_{course['id']}", use_container_width=True):
                                                update_course_status(course['id'], 'confirmee')
                                                st.rerun()
                                    
                                    elif course['statut'] == 'confirmee':
                                        with col_actions[1]:
                                            if st.button("📍 PEC", key=f"pec_detail_{course['id']}", use_container_width=True):
                                                update_course_status(course['id'], 'pec')
                                                st.rerun()
                                    
                                    elif course['statut'] == 'pec':
                                        with col_actions[2]:
                                            if st.button("🏁 Déposé", key=f"depose_detail_{course['id']}", use_container_width=True):
                                                update_course_status(course['id'], 'deposee')
                                                st.rerun()
                                    
                                    # Afficher les horodatages
                                    if course['date_confirmation']:
                                        st.caption(f"✅ Confirmée le : {format_datetime_fr(course['date_confirmation'])}")
                                    if course['date_pec']:
                                        st.caption(f"📍 PEC effectuée le : {format_datetime_fr(course['date_pec'])}")
                                    if course['date_depose']:
                                        st.caption(f"🏁 Déposée le : {format_datetime_fr(course['date_depose'])}")
                                    
                                    # Boutons Supprimer et Modifier (Secrétaire/Admin)
                                    st.markdown("---")
                                    col_btn_detail1, col_btn_detail2 = st.columns(2)
                                    
                                    with col_btn_detail1:
                                        if st.button("🗑️ Supprimer", key=f"del_detail_{course['id']}", use_container_width=True):
                                            st.session_state[f'confirm_del_detail_{course["id"]}'] = True
                                            st.rerun()
                                    
                                    with col_btn_detail2:
                                        if st.button("✏️ Modifier", key=f"mod_detail_{course['id']}", use_container_width=True):
                                            st.session_state[f'mod_detail_{course["id"]}'] = True
                                            st.rerun()
                                    
                                    # Confirmation suppression
                                    if st.session_state.get(f'confirm_del_detail_{course["id"]}', False):
                                        st.warning("⚠️ Confirmer la suppression ?")
                                        col_c1, col_c2 = st.columns(2)
                                        with col_c1:
                                            if st.button("❌ Annuler", key=f"cancel_del_detail_{course['id']}", use_container_width=True):
                                                del st.session_state[f'confirm_del_detail_{course["id"]}']
                                                st.rerun()
                                        with col_c2:
                                            if st.button("✅ Confirmer", key=f"ok_del_detail_{course['id']}", use_container_width=True):
                                                delete_course(course['id'])
                                                st.success("✅ Course supprimée")
                                                del st.session_state[f'confirm_del_detail_{course["id"]}']
                                                st.rerun()
                                    
                                    # Formulaire modification
                                    if st.session_state.get(f'mod_detail_{course["id"]}', False):
                                        st.subheader("✏️ Modifier")
                                        chauffeurs_list = get_chauffeurs()
                                        
                                        h_actuelle = course.get('heure_pec_prevue', '')
                                        new_h = st.text_input("Heure PEC", value=h_actuelle, key=f"h_detail_{course['id']}")
                                        
                                        ch_idx = 0
                                        for i, ch in enumerate(chauffeurs_list):
                                            if ch['id'] == course['chauffeur_id']:
                                                ch_idx = i
                                                break
                                        new_ch = st.selectbox("Chauffeur", chauffeurs_list, format_func=lambda x: x['full_name'], index=ch_idx, key=f"ch_detail_{course['id']}")
                                        
                                        col_s, col_c = st.columns(2)
                                        with col_s:
                                            if st.button("💾 Enregistrer", key=f"save_detail_{course['id']}", use_container_width=True):
                                                h_ok = True
                                                h_norm = None
                                                if new_h:
                                                    parts = new_h.split(':')
                                                    if len(parts) == 2:
                                                        try:
                                                            h_int, m_int = int(parts[0]), int(parts[1])
                                                            if 0 <= h_int <= 23 and 0 <= m_int <= 59:
                                                                h_norm = f"{h_int:02d}:{m_int:02d}"
                                                            else:
                                                                st.error("❌ Heure invalide")
                                                                h_ok = False
                                                        except:
                                                            st.error("❌ Format invalide")
                                                            h_ok = False
                                                    else:
                                                        st.error("❌ Format invalide")
                                                        h_ok = False
                                                
                                                if h_ok:
                                                    update_course_details(course['id'], h_norm, new_ch['id'])
                                                    st.success(f"✅ Course modifiée")
                                                    del st.session_state[f'mod_detail_{course["id"]}']
                                                    st.rerun()
                                        with col_c:
                                            if st.button("❌ Annuler", key=f"cancel_detail_{course['id']}", use_container_width=True):
                                                del st.session_state[f'mod_detail_{course["id"]}']
                                                st.rerun()
                        else:
                            st.info("Aucune course")
                    else:
                        st.markdown(f"### ⚪ Chauffeur {i+1}")
                        st.info("Non assigné")
            
            st.markdown("---")
            st.caption("🔵 Nouvelle | 🟡 Confirmée | 🔴 PEC | 🟢 Terminée")
            
        else:
            # AFFICHAGE NORMAL DU PLANNING SEMAINE (Vue tableau)
            
            # Header avec les jours - DATES CLIQUABLES
            cols_days = st.columns(8)
            jours = ["Heure", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            for i, jour in enumerate(jours):
                with cols_days[i]:
                    if i == 0:
                        st.markdown(f"**{jour}**")
                    else:
                        day_date = st.session_state.week_start_date + timedelta(days=i-1)
                        # Bouton cliquable sur la date
                        if st.button(f"{jour} {day_date.strftime('%d/%m')}", key=f"day_btn_{i}"):
                            st.session_state.view_day_detail = True
                            st.session_state.selected_day_date = day_date
                            st.rerun()
        
        # Plages horaires
        heures = list(range(6, 23))  # De 6h à 22h
        
        for heure in heures:
            cols_hours = st.columns(8)
            with cols_hours[0]:
                st.markdown(f"**{heure:02d}:00**")
            
            # Pour chaque jour de la semaine
            for day_num in range(7):
                with cols_hours[day_num + 1]:
                    # Trouver les courses pour cette heure et ce jour
                    # Utiliser heure_pec_prevue si disponible, sinon heure_prevue
                    courses_slot = []
                    for c in week_courses:
                        if c['day_offset'] != day_num:
                            continue
                        
                        # Déterminer quelle heure utiliser
                        heure_a_afficher = c.get('heure_pec_prevue')
                        if not heure_a_afficher:
                            # Si pas d'heure PEC, utiliser l'heure de création
                            heure_a_afficher = c['heure_prevue'][11:16] if len(c['heure_prevue']) > 11 else None
                        
                        # Normaliser l'heure au format HH:MM (avec 2 chiffres)
                        if heure_a_afficher:
                            parts = heure_a_afficher.split(':')
                            if len(parts) == 2:
                                h, m = parts
                                heure_normalisee = f"{int(h):02d}:{m}"
                            else:
                                heure_normalisee = heure_a_afficher
                        else:
                            heure_normalisee = None
                        
                        # Vérifier si cette course correspond à cette plage horaire
                        if heure_normalisee and heure_normalisee.startswith(f"{heure:02d}:"):
                            courses_slot.append(c)
                    
                    # TRIER les courses par ordre chronologique (heure croissante)
                    if courses_slot:
                        courses_slot.sort(key=lambda c: c.get('heure_pec_prevue') or c['heure_prevue'][11:16] or '')
                    
                    if courses_slot:
                        for course in courses_slot:
                            statut_emoji = {
                                'nouvelle': '🔵',
                                'confirmee': '🟡',
                                'pec': '🔴',  # ROUGE pour Prise En Charge
                                'deposee': '🟢'
                            }
                            emoji = statut_emoji.get(course['statut'], '⚪')
                            
                            # Déterminer l'heure à afficher dans le bouton
                            heure_affichage = course.get('heure_pec_prevue')
                            if not heure_affichage:
                                heure_affichage = course['heure_prevue'][11:16]
                            
                            # Normaliser l'heure au format HH:MM
                            if heure_affichage:
                                parts = heure_affichage.split(':')
                                if len(parts) == 2:
                                    h, m = parts
                                    heure_affichage = f"{int(h):02d}:{m}"
                            
                            # Affichage ultra-compact avec popup au clic
                            # Extraire le prénom du chauffeur
                            chauffeur_prenom = course['chauffeur_name'].split()[0]
                            # Créer le label avec prénom au-dessus (police réduite)
                            with st.popover(f"{chauffeur_prenom}\n{emoji} {heure_affichage}", use_container_width=True):
                                st.markdown(f"**{course['nom_client']}**")
                                st.caption(f"📞 {course['telephone_client']}")
                                
                                # Afficher l'heure PEC si disponible
                                if course.get('heure_pec_prevue'):
                                    # Normaliser l'heure PEC
                                    heure_pec = course['heure_pec_prevue']
                                    parts = heure_pec.split(':')
                                    if len(parts) == 2:
                                        h, m = parts
                                        heure_pec = f"{int(h):02d}:{m}"
                                    st.caption(f"⏰ **Heure PEC:** {heure_pec}")
                                else:
                                    st.caption(f"⏰ Heure création: {course['heure_prevue'][11:16]}")
                                
                                st.caption(f"📍 **PEC:** {course['adresse_pec']}")
                                st.caption(f"🏁 **Dépose:** {course['lieu_depose']}")
                                st.caption(f"🚗 {course['chauffeur_name']}")
                                st.caption(f"💰 {course['tarif_estime']}€ | {course['km_estime']} km")
                                st.caption(f"📅 Créée le: {course['heure_prevue'][:16]}")
                    else:
                        st.write("")  # Case vide
        
        st.markdown("---")
        st.caption("🔵 Nouvelle | 🟡 Confirmée | 🔴 PEC | 🟢 Terminée")
    
    with tab4:
        st.subheader("📆 Planning du Jour")
        
        # Gestion des réattributions Drag & Drop (V1.14.1)
        query_params = st.query_params
        if query_params.get("action") == "reassign":
            try:
                course_id = int(query_params.get("course_id"))
                new_chauffeur_id = int(query_params.get("new_chauffeur_id"))
                old_chauffeur_name = query_params.get("old_chauffeur_name", "")
                new_chauffeur_name = query_params.get("new_chauffeur_name", "")
                
                # Sauvegarder en base de données
                result = reassign_course_to_driver(course_id, new_chauffeur_id)
                
                if result['success']:
                    st.success(f"✅ Course réattribuée : **{old_chauffeur_name}** → **{new_chauffeur_name}**")
                else:
                    st.error(f"❌ Erreur lors de la réattribution : {result.get('error', 'Erreur inconnue')}")
                
                # Nettoyer les query params
                st.query_params.clear()
                
            except (ValueError, TypeError) as e:
                st.error(f"❌ Erreur : paramètres invalides")
                st.query_params.clear()
        
        # Initialiser la date
        if 'planning_jour_date' not in st.session_state:
            st.session_state.planning_jour_date = datetime.now(TIMEZONE).date()
        
        # Sélecteur de date
        selected_date = st.date_input(
            "Date",
            value=st.session_state.planning_jour_date,
            key="date_picker_jour"
        )
        if selected_date != st.session_state.planning_jour_date:
            st.session_state.planning_jour_date = selected_date
            st.rerun()
        
        # Afficher la date en français
        jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        jour_semaine = jours_fr[selected_date.weekday()]
        st.markdown(f"### {jour_semaine} {selected_date.strftime('%d/%m/%Y')}")
        
        st.markdown("---")
        
        # Mode Réattribution Rapide (V1.15.0 - Python pur)
        mode_reattribution = st.checkbox("🔄 Mode Réattribution Rapide", value=False, 
                                        help="Sélectionnez une ou plusieurs courses pour les réattribuer à un autre chauffeur")
        
        if mode_reattribution:
            st.info("💡 **Sélectionnez les courses à réattribuer, choisissez le nouveau chauffeur, puis cliquez sur Réattribuer**")
            
            # Récupérer toutes les courses du jour
            courses_jour = get_courses(date_filter=st.session_state.planning_jour_date.strftime('%Y-%m-%d'))
            chauffeurs = get_chauffeurs()
            
            if not courses_jour:
                st.warning("Aucune course pour ce jour")
            else:
                # Initialiser la sélection dans session_state
                if 'selected_courses' not in st.session_state:
                    st.session_state.selected_courses = []
                
                # Section de sélection des courses
                st.markdown("#### 1️⃣ Sélectionner les courses à réattribuer")
                
                # Grouper par chauffeur
                courses_par_chauffeur = {}
                for course in courses_jour:
                    chauffeur_id = course['chauffeur_id']
                    if chauffeur_id not in courses_par_chauffeur:
                        courses_par_chauffeur[chauffeur_id] = []
                    courses_par_chauffeur[chauffeur_id].append(course)
                
                # Afficher les courses par chauffeur
                selected_course_ids = []
                
                for chauffeur in chauffeurs:
                    if chauffeur['id'] in courses_par_chauffeur:
                        with st.expander(f"🚗 {chauffeur['full_name']} ({len(courses_par_chauffeur[chauffeur['id']])} course(s))", expanded=True):
                            courses = courses_par_chauffeur[chauffeur['id']]
                            courses.sort(key=lambda c: c.get('heure_pec_prevue') or c['heure_prevue'][11:16] or '')
                            
                            for course in courses:
                                statut_emoji = {
                                    'nouvelle': '🔵',
                                    'confirmee': '🟡',
                                    'pec': '🔴',
                                    'deposee': '🟢'
                                }
                                emoji = statut_emoji.get(course['statut'], '⚪')
                                
                                # Heure à afficher
                                heure_affichage = course.get('heure_pec_prevue')
                                if not heure_affichage:
                                    heure_affichage = course['heure_prevue'][11:16]
                                
                                # Normaliser l'heure
                                if heure_affichage:
                                    parts = heure_affichage.split(':')
                                    if len(parts) == 2:
                                        h, m = parts
                                        heure_affichage = f"{int(h):02d}:{m}"
                                
                                # Checkbox pour sélectionner la course
                                label = f"{emoji} {heure_affichage} - {course['nom_client']} ({course['adresse_pec']} → {course['lieu_depose']})"
                                
                                if st.checkbox(label, key=f"select_course_{course['id']}"):
                                    selected_course_ids.append(course['id'])
                
                # Section de choix du nouveau chauffeur
                if selected_course_ids:
                    st.markdown(f"#### 2️⃣ Nouveau chauffeur ({len(selected_course_ids)} course(s) sélectionnée(s))")
                    
                    # Créer la liste des chauffeurs pour le selectbox
                    chauffeur_options = {f"{ch['full_name']}": ch['id'] for ch in chauffeurs}
                    nouveau_chauffeur_name = st.selectbox(
                        "Choisir le nouveau chauffeur",
                        options=list(chauffeur_options.keys()),
                        key="nouveau_chauffeur_select"
                    )
                    nouveau_chauffeur_id = chauffeur_options[nouveau_chauffeur_name]
                    
                    # Bouton de réattribution
                    st.markdown("#### 3️⃣ Confirmer")
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("🔄 Réattribuer", type="primary", use_container_width=True):
                            # Réattribuer chaque course sélectionnée
                            success_count = 0
                            for course_id in selected_course_ids:
                                result = reassign_course_to_driver(course_id, nouveau_chauffeur_id)
                                if result['success']:
                                    success_count += 1
                            
                            if success_count == len(selected_course_ids):
                                st.success(f"✅ {success_count} course(s) réattribuée(s) à {nouveau_chauffeur_name} !")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"❌ Erreur : seulement {success_count}/{len(selected_course_ids)} course(s) réattribuée(s)")
                    
                    with col2:
                        if st.button("❌ Annuler", use_container_width=True):
                            st.rerun()
                else:
                    st.info("👆 Sélectionnez au moins une course ci-dessus")
            
            st.markdown("---")
        
        st.markdown("---")
        
        
        # Récupérer tous les chauffeurs
        chauffeurs = get_chauffeurs()
        
        # Fixer à 4 colonnes maximum
        nb_colonnes = 4
        
        # Récupérer toutes les courses du jour sélectionné
        courses_jour = get_courses(date_filter=st.session_state.planning_jour_date.strftime('%Y-%m-%d'))
        
        # Créer 4 colonnes pour les chauffeurs
        nb_colonnes = 4
        
        # ==========================================
        # AFFICHAGE CLASSIQUE
        # ==========================================
        cols_chauffeurs = st.columns(nb_colonnes)
        
        for i in range(nb_colonnes):
            with cols_chauffeurs[i]:
                if i < len(chauffeurs):
                    chauffeur = chauffeurs[i]
                    st.markdown(f"### 🚗 {chauffeur['full_name']}")
                    
                    # Filtrer les courses de ce chauffeur pour ce jour
                    courses_chauffeur = [c for c in courses_jour if c['chauffeur_id'] == chauffeur['id']]
                    
                    # Trier par heure PEC prévue
                    courses_chauffeur.sort(key=lambda c: c.get('heure_pec_prevue') or c['heure_prevue'][11:16] or '')
                    
                    if courses_chauffeur:
                        for course in courses_chauffeur:
                            statut_emoji = {
                                'nouvelle': '🔵',
                                'confirmee': '🟡',
                                'pec': '🔴',
                                'deposee': '🟢'
                            }
                            emoji = statut_emoji.get(course['statut'], '⚪')
                            
                            # Heure à afficher
                            heure_affichage = course.get('heure_pec_prevue')
                            if not heure_affichage:
                                heure_affichage = course['heure_prevue'][11:16]
                            
                            # Normaliser l'heure
                            if heure_affichage:
                                parts = heure_affichage.split(':')
                                if len(parts) == 2:
                                    h, m = parts
                                    heure_affichage = f"{int(h):02d}:{m}"
                            
                            # Affichage avec popup compact
                            with st.popover(f"{emoji} {heure_affichage} - {course['nom_client']}", use_container_width=True):
                                # Format compact : nom + tel sur une ligne
                                st.markdown(f"**{course['nom_client']}** - {course['telephone_client']}")
                                
                                # Heure PEC + trajet sur une ligne
                                if course.get('heure_pec_prevue'):
                                    heure_pec = course['heure_pec_prevue']
                                    parts = heure_pec.split(':')
                                    if len(parts) == 2:
                                        h, m = parts
                                        heure_pec = f"{int(h):02d}:{m}"
                                    st.caption(f"⏰ {heure_pec} • {course['adresse_pec']} → {course['lieu_depose']}")
                                else:
                                    st.caption(f"📍 {course['adresse_pec']} → {course['lieu_depose']}")
                                
                                # Tarif et km sur une ligne
                                st.caption(f"💰 {course['tarif_estime']}€ | {course['km_estime']} km")
                                
                                # Ligne de boutons selon le statut (action + Supp)
                                st.markdown("---")
                                
                                if course['statut'] == 'nouvelle':
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("Confirmer", key=f"confirm_jour_{course['id']}", use_container_width=True):
                                            update_course_status(course['id'], 'confirmee')
                                            st.rerun()
                                    with col2:
                                        st.button("Supp", key=f"del_jour_{course['id']}", use_container_width=True,
                                                 on_click=set_delete_confirmation, args=(course['id'],))
                                
                                elif course['statut'] == 'confirmee':
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("📍 PEC", key=f"pec_jour_{course['id']}", use_container_width=True):
                                            update_course_status(course['id'], 'pec')
                                            st.rerun()
                                    with col2:
                                        st.button("Supp", key=f"del_jour_{course['id']}", use_container_width=True,
                                                 on_click=set_delete_confirmation, args=(course['id'],))
                                
                                elif course['statut'] == 'pec':
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("🏁 Déposé", key=f"depose_jour_{course['id']}", use_container_width=True):
                                            update_course_status(course['id'], 'deposee')
                                            st.rerun()
                                    with col2:
                                        st.button("Supp", key=f"del_jour_{course['id']}", use_container_width=True,
                                                 on_click=set_delete_confirmation, args=(course['id'],))
                                
                                elif course['statut'] == 'deposee':
                                    st.button("Supp", key=f"del_jour_{course['id']}", use_container_width=True,
                                             on_click=set_delete_confirmation, args=(course['id'],))
                                
                                # Confirmation suppression
                                if st.session_state.get(f'confirm_del_jour_{course["id"]}', False):
                                    st.warning("⚠️ Confirmer la suppression ?")
                                    col_c1, col_c2 = st.columns(2)
                                    with col_c1:
                                        if st.button("❌ Annuler", key=f"cancel_del_jour_{course['id']}", use_container_width=True):
                                            del st.session_state[f'confirm_del_jour_{course["id"]}']
                                            st.rerun()
                                    with col_c2:
                                        if st.button("✅ Confirmer", key=f"ok_del_jour_{course['id']}", use_container_width=True):
                                            delete_course(course['id'])
                                            st.success("✅ Course supprimée")
                                            del st.session_state[f'confirm_del_jour_{course["id"]}']
                                            st.rerun()
                                
                    else:
                        st.info("Aucune course")
                else:
                    st.markdown(f"### ⚪ Chauffeur {i+1}")
                    st.info("Non assigné")
        
        st.markdown("---")
        st.caption("🔵 Nouvelle | 🟡 Confirmée | 🔴 PEC | 🟢 Terminée")

# Interface Chauffeur
def chauffeur_page():
    st.title("Mes courses")
    st.markdown(f"**Connecté en tant que :** {st.session_state.user['full_name']} (Chauffeur)")
    
    col_deconnexion, col_refresh = st.columns([1, 6])
    with col_deconnexion:
        if st.button("🚪 Déconnexion"):
            del st.session_state.user
            st.rerun()
    with col_refresh:
        if st.button("🔄 Actualiser", help="Recharger pour voir les dernières modifications"):
            st.rerun()
    
    st.markdown("---")
    
    # Filtre de date
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        show_all_chauff = st.checkbox("Afficher toutes mes courses", value=True)
        if not show_all_chauff:
            date_filter = st.date_input("Date", value=datetime.now())
        else:
            date_filter = None
    with col2:
        date_filter_str = None
        if not show_all_chauff and date_filter:
            date_filter_str = date_filter.strftime('%Y-%m-%d')
        courses = get_courses(chauffeur_id=st.session_state.user['id'], date_filter=date_filter_str)
        st.metric("Mes courses", len([c for c in courses if c['statut'] != 'deposee']))
    with col3:
        st.metric("Terminées", len([c for c in courses if c['statut'] == 'deposee']))
    
    # Récupérer les courses du chauffeur
    if not courses:
        st.info("Aucune course pour cette sélection")
    else:
        for course in courses:
            # Couleur selon le statut
            statut_colors = {
                'nouvelle': '🔵',
                'confirmee': '🟡',
                'pec': '🔴',
                'deposee': '🟢'
            }
            
            statut_text = {
                'nouvelle': 'NOUVELLE',
                'confirmee': 'CONFIRMÉE',
                'pec': 'PRISE EN CHARGE',
                'deposee': 'TERMINÉE'
            }
            
            # Formater la date au format français pour le titre
            date_str = course['heure_prevue'][0:10]
            annee, mois, jour = date_str.split('-')
            date_fr = f"{jour}/{mois}/{annee}"
            
            # Titre avec date + heure PEC
            heure_affichage = course.get('heure_pec_prevue', course['heure_prevue'][11:16])
            titre = f"{statut_colors.get(course['statut'], '⚪')} {date_fr} {heure_affichage} - {course['nom_client']} - {statut_text.get(course['statut'], course['statut'].upper())}"
            
            with st.expander(titre):
                # Informations de la course
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Client :** {course['nom_client']}")
                    st.write(f"**Téléphone :** {course['telephone_client']}")
                    
                    # Afficher la date PEC au format français
                    st.write(f"**📅 Date PEC :** {date_fr}")
                    
                    if course.get('heure_pec_prevue'):
                        st.success(f"⏰ **Heure PEC prévue : {course['heure_pec_prevue']}**")
                    st.write(f"**PEC :** {course['adresse_pec']}")
                
                with col2:
                    st.write(f"**Dépose :** {course['lieu_depose']}")
                    st.write(f"**Type :** {course['type_course']}")
                    st.write(f"**Tarif estimé :** {course['tarif_estime']}€")
                    st.write(f"**Km estimé :** {course['km_estime']} km")
                
                # Afficher les horodatages
                if course['date_confirmation']:
                    st.caption(f"✅ Confirmée le : {format_datetime_fr(course['date_confirmation'])}")
                if course['date_pec']:
                    st.info(f"📍 **Heure de PEC : {course['date_pec'][11:19]}**")
                if course['date_depose']:
                    st.caption(f"🏁 Déposée le : {format_datetime_fr(course['date_depose'])}")
                
                if course['commentaire']:
                    st.info(f"💬 **Commentaire secrétaire :** {course['commentaire']}")
                
                # Section commentaire chauffeur
                st.markdown("---")
                st.markdown("**💭 Commentaire pour la secrétaire**")
                
                # Afficher le commentaire existant s'il y en a un
                if course.get('commentaire_chauffeur'):
                    st.success(f"📝 Votre commentaire : {course['commentaire_chauffeur']}")
                
                # Zone de texte pour ajouter/modifier le commentaire
                new_comment = st.text_area(
                    "Ajouter ou modifier un commentaire",
                    value=course.get('commentaire_chauffeur', ''),
                    key=f"comment_{course['id']}",
                    placeholder="Ex: Client en retard, bagages supplémentaires, problème d'accès...",
                    height=80
                )
                
                if st.button("💾 Enregistrer commentaire", key=f"save_comment_{course['id']}"):
                    update_commentaire_chauffeur(course['id'], new_comment)
                    st.success("✅ Commentaire enregistré")
                    st.rerun()
                
                st.markdown("---")
                
                # Boutons d'action selon le statut
                col1, col2, col3, col4 = st.columns(4)
                
                if course['statut'] == 'nouvelle':
                    with col1:
                        if st.button("✅ Confirmer", key=f"confirm_{course['id']}", use_container_width=True):
                            update_course_status(course['id'], 'confirmee')
                            st.rerun()  # Rerun immédiat sans message
                
                elif course['statut'] == 'confirmee':
                    with col2:
                        if st.button("📍 PEC effectuée", key=f"pec_{course['id']}", use_container_width=True):
                            update_course_status(course['id'], 'pec')
                            st.rerun()  # Rerun immédiat sans message
                
                elif course['statut'] == 'pec':
                    with col3:
                        if st.button("🏁 Client déposé", key=f"depose_{course['id']}", use_container_width=True):
                            update_course_status(course['id'], 'deposee')
                            st.rerun()  # Rerun immédiat sans message
                
                elif course['statut'] == 'deposee':
                    st.success("✅ Course terminée")
                
                # Afficher les horodatages
                if course['date_confirmation']:
                    st.caption(f"✅ Confirmée le : {format_datetime_fr(course['date_confirmation'])}")
                if course['date_pec']:
                    st.caption(f"📍 PEC le : {course['date_pec'][:19]}")
                if course['date_depose']:
                    st.caption(f"🏁 Déposée le : {format_datetime_fr(course['date_depose'])}")

# Main
def main():
    # Initialiser la base de données
    init_db()
    
    # Vérifier si l'utilisateur est connecté
    if 'user' not in st.session_state:
        login_page()
    else:
        # Rediriger selon le rôle
        if st.session_state.user['role'] == 'admin':
            admin_page()
        elif st.session_state.user['role'] == 'secretaire':
            secretaire_page()
        elif st.session_state.user['role'] == 'chauffeur':
            chauffeur_page()

if __name__ == "__main__":
    main()
