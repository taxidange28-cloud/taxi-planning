import streamlit as st
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
    
    # Utiliser l'heure de Paris
    now_paris = datetime.now(TIMEZONE)
    
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
    
    if st.button("🚪 Déconnexion"):
        del st.session_state.user
        st.rerun()
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Planning Global", "👥 Gestion des Comptes", "📈 Statistiques", "💾 Export"])
    
    with tab1:
        st.subheader("Planning Global de toutes les courses")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            show_all = st.checkbox("Afficher toutes les courses", value=False)
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
                if statut_filter != "Tous" and course['statut'].lower() != statut_filter.lower():
                    continue
                
                # Couleur selon le statut
                statut_colors = {
                    'nouvelle': '🔵',
                    'confirmee': '🟡',
                    'pec': '🟠',
                    'deposee': '🟢'
                }
                
                with st.expander(f"{statut_colors.get(course['statut'], '⚪')} {course['heure_prevue'][:16]} - {course['nom_client']} ({course['chauffeur_name']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client :** {course['nom_client']}")
                        st.write(f"**Téléphone :** {course['telephone_client']}")
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
                        st.info(f"✅ Confirmée le : {course['date_confirmation'][:19]}")
                    if course['date_pec']:
                        st.info(f"📍 PEC effectuée le : {course['date_pec'][:19]}")
                    if course['date_depose']:
                        st.success(f"🏁 Déposée le : {course['date_depose'][:19]}")
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

# Interface Secrétaire
def secretaire_page():
    st.title("📝 Secrétariat - Planning des courses")
    st.markdown(f"**Connecté en tant que :** {st.session_state.user['full_name']} (Secrétaire)")
    
    if st.button("🚪 Déconnexion"):
        del st.session_state.user
        st.rerun()
    
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["➕ Nouvelle Course", "📊 Planning Global", "📅 Planning Semaine"])
    
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
                            heure_prevue_naive = datetime.combine(date_course, datetime.now(TIMEZONE).time())
                            heure_prevue = TIMEZONE.localize(heure_prevue_naive)
                            
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
            show_all_sec = st.checkbox("Afficher toutes les courses", value=False, key="sec_show_all")
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
                if statut_filter != "Tous" and course['statut'].lower() != statut_filter.lower():
                    continue
                
                # Couleur selon le statut
                statut_colors = {
                    'nouvelle': '🔵',
                    'confirmee': '🟡',
                    'pec': '🟠',
                    'deposee': '🟢'
                }
                
                with st.expander(f"{statut_colors.get(course['statut'], '⚪')} {course['heure_prevue'][:16]} - {course['nom_client']} ({course['chauffeur_name']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client :** {course['nom_client']}")
                        st.write(f"**Téléphone :** {course['telephone_client']}")
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
                        st.info(f"✅ Confirmée le : {course['date_confirmation'][:19]}")
                    if course['date_pec']:
                        st.info(f"📍 PEC effectuée le : {course['date_pec'][:19]}")
                    if course['date_depose']:
                        st.success(f"🏁 Déposée le : {course['date_depose'][:19]}")
                    
                    # Bouton duplication
                    st.markdown("---")
                    if st.button(f"📋 Dupliquer cette course", key=f"dup_sec_{course['id']}", use_container_width=True):
                        st.session_state.course_to_duplicate = course
                        st.success("✅ Course prête à dupliquer ! Allez dans l'onglet 'Nouvelle Course'")
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
        
        # Header avec les jours
        cols_days = st.columns(8)
        jours = ["Heure", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        for i, jour in enumerate(jours):
            with cols_days[i]:
                if i == 0:
                    st.markdown(f"**{jour}**")
                else:
                    day_date = st.session_state.week_start_date + timedelta(days=i-1)
                    st.markdown(f"**{jour} {day_date.strftime('%d/%m')}**")
        
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
                    courses_slot = [c for c in week_courses 
                                   if c['day_offset'] == day_num 
                                   and c.get('heure_pec_prevue') 
                                   and c['heure_pec_prevue'].startswith(f"{heure:02d}:")]
                    
                    if courses_slot:
                        for course in courses_slot:
                            statut_emoji = {
                                'nouvelle': '🔵',
                                'confirmee': '🟡',
                                'pec': '🟠',
                                'deposee': '🟢'
                            }
                            emoji = statut_emoji.get(course['statut'], '⚪')
                            
                            # Affichage ultra-compact avec popup au clic
                            with st.popover(f"{emoji} {course['heure_pec_prevue']}", use_container_width=True):
                                st.markdown(f"**{course['nom_client']}**")
                                st.caption(f"📞 {course['telephone_client']}")
                                st.caption(f"📍 **PEC:** {course['adresse_pec']}")
                                st.caption(f"🏁 **Dépose:** {course['lieu_depose']}")
                                st.caption(f"🚗 {course['chauffeur_nom']}")
                                st.caption(f"💰 {course['tarif_estime']}€ | {course['km_estime']} km")
                                st.caption(f"📅 Créée le: {course['heure_prevue'][:16]}")
                    else:
                        st.write("")  # Case vide
        
        st.markdown("---")
        st.caption("🔵 Nouvelle | 🟡 Confirmée | 🟠 PEC | 🟢 Terminée")

# Interface Chauffeur
def chauffeur_page():
    st.title("Mes courses")
    st.markdown(f"**Connecté en tant que :** {st.session_state.user['full_name']} (Chauffeur)")
    
    if st.button("🚪 Déconnexion"):
        del st.session_state.user
        st.rerun()
    
    st.markdown("---")
    
    # Filtre de date
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        show_all_chauff = st.checkbox("Afficher toutes mes courses", value=False)
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
                'pec': '🟠',
                'deposee': '🟢'
            }
            
            statut_text = {
                'nouvelle': 'NOUVELLE',
                'confirmee': 'CONFIRMÉE',
                'pec': 'PRISE EN CHARGE',
                'deposee': 'TERMINÉE'
            }
            
            with st.expander(f"{statut_colors.get(course['statut'], '⚪')} {course['heure_prevue'][11:16]} - {course['nom_client']} - {statut_text.get(course['statut'], course['statut'].upper())}"):
                # Informations de la course
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Client :** {course['nom_client']}")
                    st.write(f"**Téléphone :** {course['telephone_client']}")
                    st.write(f"**Heure prévue :** {course['heure_prevue'][11:16]}")
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
                    st.caption(f"✅ Confirmée le : {course['date_confirmation'][:19]}")
                if course['date_pec']:
                    st.info(f"📍 **Heure de PEC : {course['date_pec'][11:19]}**")
                if course['date_depose']:
                    st.caption(f"🏁 Déposée le : {course['date_depose'][:19]}")
                
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
                            st.success("Course confirmée !")
                            st.rerun()
                
                elif course['statut'] == 'confirmee':
                    with col2:
                        if st.button("📍 PEC effectuée", key=f"pec_{course['id']}", use_container_width=True):
                            update_course_status(course['id'], 'pec')
                            st.success("Prise en charge enregistrée !")
                            st.rerun()
                
                elif course['statut'] == 'pec':
                    with col3:
                        if st.button("🏁 Client déposé", key=f"depose_{course['id']}", use_container_width=True):
                            update_course_status(course['id'], 'deposee')
                            st.success("Course terminée !")
                            st.rerun()
                
                elif course['statut'] == 'deposee':
                    st.success("✅ Course terminée")
                
                # Afficher les horodatages
                if course['date_confirmation']:
                    st.caption(f"✅ Confirmée le : {course['date_confirmation'][:19]}")
                if course['date_pec']:
                    st.caption(f"📍 PEC le : {course['date_pec'][:19]}")
                if course['date_depose']:
                    st.caption(f"🏁 Déposée le : {course['date_depose'][:19]}")

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
