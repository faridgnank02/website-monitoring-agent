# Google Cloud Configuration (Sheets & Gmail)

## Objective

Configure access to Google Sheets API and Gmail API for the Monitor Agent project.

---

## Configuration Steps

### 1. Create a Google Cloud project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click on **"Select a project"** → **"New project"**
3. Name the project: `monitor-agent` (or another name)
4. Click on **"Create"**

---

### 2. Enable required APIs

#### Google Sheets API

1. In the side menu → **APIs & Services** → **Library**
2. Search: `Google Sheets API`
3. Click on **"Enable"**

#### Gmail API

1. In the same library, search: `Gmail API`
2. Click on **"Enable"**

---

### 3. Create a Service Account

1. In the side menu → **APIs & Services** → **Credentials**
2. Click on **"Create credentials"** → **"Service account"**
3. Fill in the information:
   - **Name**: `monitor-agent-service`
   - **ID**: (automatically generated)
   - **Description**: `Service account for Monitor Agent`
4. Click on **"Create and continue"**

5. **Role**: Select `Editor` (or `Owner` for more permissions)
6. Click on **"Continue"** then **"Done"**

---

### 4. Generate JSON key

1. In the service account list, click on the one you just created
2. Go to the **"Keys"** tab
3. Click on **"Add key"** → **"Create new key"**
4. Choose **JSON** format
5. Click on **"Create"**
6. The JSON file will be automatically downloaded

7. **Rename the file** to `credentials.json`
8. **Move the file** to the project root:
   ```bash
   mv ~/Downloads/monitor-agent-*.json /path/to/monitor_agent/credentials.json
   ```

---

### 5. Create a Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new document: **"Blank spreadsheet"**
3. Name the document: `Monitor Agent - Logs`

4. **Get the Sheet ID**:
   - In the document URL:
     ```
     https://docs.google.com/spreadsheets/d/1ABC123XYZ456/edit
                                         ^^^^^^^^^^^^^^^^
                                         This is the ID
     ```
   - Copy this ID (between `/d/` and `/edit`)

---

### 6. Share the Sheet with the service account

**IMPORTANT**: The service account needs access to the Sheet!

1. Open the `credentials.json` file
2. Look for the `"client_email"` line:
   ```json
   "client_email": "monitor-agent-service@project-id.iam.gserviceaccount.com"
   ```
3. Copy this email address

4. In your Google Sheet:
   - Click on **"Share"** (top right)
   - Paste the service account email
   - Set the role: **"Editor"**
   - **Uncheck** "Notify users"
   - Click on **"Send"**

---

### 7. Configure the .env file

Modify your `.env`:

```bash
# Google Sheets
GOOGLE_SHEET_ID=1ABC123XYZ456  # The ID copied in step 5
GOOGLE_CREDENTIALS_FILE=credentials.json

# Gmail
GMAIL_SENDER_EMAIL=your_email@gmail.com
GMAIL_RECIPIENT_EMAIL=recipient@gmail.com
```

---

## Configuration Verification

To test that everything works:

```bash
# Activate venv
source venv/bin/activate

# Run Sheets Manager test
python3 test_sheets_manager.py
```

### Expected result

```
Sheets Manager Test
Authentication successful!
Tabs initialized!
Scraping log saved!
Comparison log saved!
```

---

## Troubleshooting

### Error: "credentials.json not found"

- Verify that the `credentials.json` file is at the project root
- Verify the path in `.env`: `GOOGLE_CREDENTIALS_FILE=credentials.json`

### Error: "Insufficient Permission"

- Verify that you have **shared the Sheet** with the service account email
- Verify that the role is **"Editor"** (not "Viewer")

### Error: "API not enabled"

- Verify that Google Sheets API is enabled in Google Cloud Console
- Wait a few minutes after enabling

### Error: "Invalid credentials"

- Regenerate the JSON key (step 4)
- Replace the old `credentials.json` file

---

## Resources

- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Service Accounts Guide](https://cloud.google.com/iam/docs/service-accounts)
- [Gmail API Documentation](https://developers.google.com/gmail/api)

---

## Note

For **Gmail API**, you will use OAuth2 (different from service account).
The Gmail Notifier module will be created in the next step and will require additional configuration.
