# GraphGPT - Microsoft 365 Chat Agent

Ein intelligenter Chat-Agent, der natürlichsprachliche Fragen zu Ihrer Microsoft 365 Umgebung beantwortet. Nutzt Azure OpenAI (GPT-4) und Microsoft Graph API.

## 🚀 Features

- **Natürlichsprachliche Abfragen**: Stellen Sie Fragen wie "Welche Benutzer wurden letzte Woche erstellt?"
- **Automatische API-Generierung**: GPT-4 übersetzt Ihre Fragen in Graph API Requests
- **Verständliche Antworten**: Technische API-Antworten werden nutzerfreundlich aufbereitet
- **Streamlit Chat-UI**: Moderne, benutzerfreundliche Chat-Oberfläche

## 📋 Voraussetzungen

- Python 3.8+
- Azure OpenAI Zugang mit GPT-4 Deployment
- Azure App Registration mit Graph API Berechtigungen
- Microsoft 365 Tenant

## 🛠️ Installation

1. **Repository klonen**
   ```bash
   git clone <repository-url>
   cd mirosoft-sk-ai
   ```

2. **Python-Umgebung erstellen**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # oder
   venv\Scripts\activate  # Windows
   ```

3. **Dependencies installieren**
   ```bash
   pip install -r requirements.txt
   ```

4. **Umgebungsvariablen konfigurieren**
   ```bash
   cp .env.example .env
   ```
   
   Bearbeiten Sie die `.env` Datei mit Ihren Azure-Zugangsdaten:
   - `AZURE_OPENAI_KEY`: Ihr Azure OpenAI API Key
   - `AZURE_OPENAI_ENDPOINT`: Ihr Azure OpenAI Endpoint
   - `AZURE_OPENAI_DEPLOYMENT_NAME`: Name Ihres GPT-4 Deployments
   - `AZURE_TENANT_ID`: Ihre Azure AD Tenant ID
   - `AZURE_CLIENT_ID`: Client ID Ihrer App Registration
   - `AZURE_CLIENT_SECRET`: Client Secret Ihrer App Registration

## 🔐 Azure Setup

### App Registration erstellen

1. Gehen Sie zum [Azure Portal](https://portal.azure.com)
2. Navigieren Sie zu "Azure Active Directory" → "App registrations" → "New registration"
3. Konfigurieren Sie:
   - Name: `GraphGPT`
   - Supported account types: "Single tenant"
4. Nach der Erstellung:
   - Kopieren Sie die `Application (client) ID`
   - Kopieren Sie die `Directory (tenant) ID`
5. Erstellen Sie ein Client Secret:
   - "Certificates & secrets" → "New client secret"
   - Kopieren Sie den Wert sofort (wird nur einmal angezeigt!)

### Graph API Berechtigungen

Fügen Sie unter "API permissions" folgende Application permissions hinzu:
- `User.Read.All`
- `Group.Read.All`
- `Directory.Read.All`

Klicken Sie auf "Grant admin consent".

## 🚀 Starten

```bash
streamlit run app.py
```

Die Anwendung öffnet sich automatisch im Browser unter `http://localhost:8501`.

## 💬 Verwendung

Beispiele für Fragen, die Sie stellen können:

- "Zeige alle Benutzer"
- "Welche Benutzer wurden letzte Woche erstellt?"
- "Finde Benutzer mit Namen Michael"
- "Zeige alle deaktivierten Benutzer"
- "Liste alle Microsoft 365 Gruppen auf"
- "Welche Sicherheitsgruppen gibt es?"

## 🏗️ Architektur

```
app.py                      # Streamlit UI
config/
  └── kernel_builder.py     # Semantic Kernel Setup
  └── date_helper.py        # Datums-Berechnungen
skills/
  ├── graph_api_builder/    # GPT-4 Prompt für API-URLs
  ├── summarizer/           # GPT-4 Prompt für Zusammenfassungen
  └── graph_api_request.py  # Native Skill für API-Calls
```

## 🐛 Troubleshooting

**"Konfigurationsfehler" beim Start**
- Überprüfen Sie, ob alle Umgebungsvariablen in `.env` gesetzt sind
- Stellen Sie sicher, dass die Azure-Zugangsdaten korrekt sind

**"Failed to execute Graph API request"**
- Überprüfen Sie die App Registration Berechtigungen
- Stellen Sie sicher, dass Admin Consent erteilt wurde
- Prüfen Sie, ob das Client Secret noch gültig ist

## 📝 Lizenz

MIT
