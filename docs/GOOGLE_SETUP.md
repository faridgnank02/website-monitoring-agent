# Configuration Google Cloud (Sheets & Gmail)

## 🎯 Objectif
Configurer l'accès à Google Sheets API et Gmail API pour le projet Monitor Agent.

---

## 📋 Étapes de configuration

### 1. Créer un projet Google Cloud

1. Aller sur [Google Cloud Console](https://console.cloud.google.com)
2. Cliquer sur **"Sélectionner un projet"** → **"Nouveau projet"**
3. Nommer le projet : `monitor-agent` (ou autre nom)
4. Cliquer sur **"Créer"**

---

### 2. Activer les APIs nécessaires

#### Google Sheets API
1. Dans le menu latéral → **APIs et services** → **Bibliothèque**
2. Rechercher : `Google Sheets API`
3. Cliquer sur **"Activer"**

#### Gmail API
1. Dans la même bibliothèque, rechercher : `Gmail API`
2. Cliquer sur **"Activer"**

---

### 3. Créer un compte de service (Service Account)

1. Dans le menu latéral → **APIs et services** → **Identifiants**
2. Cliquer sur **"Créer des identifiants"** → **"Compte de service"**
3. Remplir les informations :
   - **Nom** : `monitor-agent-service`
   - **ID** : (généré automatiquement)
   - **Description** : `Service account pour Monitor Agent`
4. Cliquer sur **"Créer et continuer"**

5. **Rôle** : Sélectionner `Éditeur` (ou `Propriétaire` pour plus de permissions)
6. Cliquer sur **"Continuer"** puis **"OK"**

---

### 4. Générer la clé JSON

1. Dans la liste des comptes de service, cliquer sur celui que vous venez de créer
2. Aller dans l'onglet **"Clés"**
3. Cliquer sur **"Ajouter une clé"** → **"Créer une clé"**
4. Choisir le format **JSON**
5. Cliquer sur **"Créer"**
6. Le fichier JSON sera téléchargé automatiquement

7. **Renommer le fichier** en `credentials.json`
8. **Déplacer le fichier** à la racine du projet :
   ```bash
   mv ~/Downloads/monitor-agent-*.json /chemin/vers/monitor_agent/credentials.json
   ```

---

### 5. Créer un Google Sheet

1. Aller sur [Google Sheets](https://sheets.google.com)
2. Créer un nouveau document : **"Document vierge"**
3. Nommer le document : `Monitor Agent - Logs`

4. **Récupérer l'ID du Sheet** :
   - Dans l'URL du document :
     ```
     https://docs.google.com/spreadsheets/d/1ABC123XYZ456/edit
                                         ^^^^^^^^^^^^^^^^
                                         Ceci est l'ID
     ```
   - Copier cet ID (entre `/d/` et `/edit`)

---

### 6. Partager le Sheet avec le compte de service

⚠️ **IMPORTANT** : Le compte de service a besoin d'accès au Sheet !

1. Ouvrir le fichier `credentials.json`
2. Chercher la ligne `"client_email"` :
   ```json
   "client_email": "monitor-agent-service@project-id.iam.gserviceaccount.com"
   ```
3. Copier cette adresse email

4. Dans votre Google Sheet :
   - Cliquer sur **"Partager"** (en haut à droite)
   - Coller l'email du compte de service
   - Définir le rôle : **"Éditeur"**
   - **Décocher** "Notifier les utilisateurs"
   - Cliquer sur **"Envoyer"**

---

### 7. Configurer le fichier .env

Modifier votre `.env` :

```bash
# Google Sheets
GOOGLE_SHEET_ID=1ABC123XYZ456  # L'ID copié à l'étape 5
GOOGLE_CREDENTIALS_FILE=credentials.json

# Gmail
GMAIL_SENDER_EMAIL=votre_email@gmail.com
GMAIL_RECIPIENT_EMAIL=destinataire@gmail.com
```

---

## ✅ Vérification de la configuration

Pour tester que tout fonctionne :

```bash
# Activer le venv
source venv/bin/activate

# Lancer le test Sheets
python3 test_sheets_manager.py
```

### Résultat attendu :
```
📊 Test Sheets Manager
✅ Authentification réussie!
✅ Onglets initialisés!
✅ Log de scraping enregistré!
✅ Log de comparaison enregistré!
```

---

## 🔧 Troubleshooting

### Erreur : "credentials.json not found"
- Vérifier que le fichier `credentials.json` est bien à la racine du projet
- Vérifier le chemin dans `.env` : `GOOGLE_CREDENTIALS_FILE=credentials.json`

### Erreur : "Insufficient Permission"
- Vérifier que vous avez bien **partagé le Sheet** avec l'email du compte de service
- Vérifier que le rôle est **"Éditeur"** (pas "Lecteur")

### Erreur : "API not enabled"
- Vérifier que Google Sheets API est activée dans Google Cloud Console
- Attendre quelques minutes après l'activation

### Erreur : "Invalid credentials"
- Régénérer la clé JSON (étape 4)
- Remplacer l'ancien fichier `credentials.json`

---

## 📚 Ressources

- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Service Accounts Guide](https://cloud.google.com/iam/docs/service-accounts)
- [Gmail API Documentation](https://developers.google.com/gmail/api)

---

## 🎓 Note

Pour **Gmail API**, vous utiliserez OAuth2 (différent du compte de service).
Le module Gmail Notifier sera créé dans la prochaine étape et nécessitera une configuration supplémentaire.
