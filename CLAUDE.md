# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GraphGPT - Ein chatbasierter Microsoft Graph API Agent, der natürlichsprachliche Fragen zur Microsoft 365 Umgebung beantwortet. Das Projekt nutzt Semantic Kernel mit Azure OpenAI (GPT-4) zur Sprachverarbeitung und automatischen API-Generierung.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py

# Set up environment (copy and fill .env.example)
cp .env.example .env
```

## Architecture

### Komponenten
- **Frontend**: Streamlit-basierte Chat-UI (app.py)
- **Agent**: Semantic Kernel orchestriert Skills zur API-Generierung und -Ausführung
- **Skills**:
  - `GraphAPIBuilder`: Prompt-Skill zur Graph API URL-Generierung
  - `GraphAPIRequest`: Native Skill für REST-API-Aufrufe mit OAuth
  - `Summarizer`: Prompt-Skill zur nutzerfreundlichen Aufbereitung

### Datenfluss
1. Benutzerfrage → GPT-4 interpretiert und generiert API-URL
2. Graph API Request mit Azure AD Token
3. JSON-Response → GPT-4 fasst zusammen
4. Nutzerfreundliche Antwort im Chat

### Projektstruktur
```
/
├── app.py                     # Streamlit Chat-Anwendung
├── .env                       # Lokale Konfiguration (nicht committen!)
├── skills/
│   ├── graph_api_builder/     # Semantic Skill für URL-Generierung
│   ├── summarizer/            # Semantic Skill für Zusammenfassungen
│   └── graph_api_request.py   # Native Skill für API-Aufrufe
├── config/
│   └── kernel_builder.py      # Semantic Kernel Konfiguration
└── requirements.txt           # Python Dependencies
```

### Erforderliche Umgebungsvariablen
- `AZURE_OPENAI_KEY`: Azure OpenAI API Key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI Endpoint
- `AZURE_OPENAI_DEPLOYMENT_NAME`: GPT-4 Deployment Name
- `AZURE_TENANT_ID`: Azure AD Tenant ID
- `AZURE_CLIENT_ID`: App Registration Client ID
- `AZURE_CLIENT_SECRET`: App Registration Secret

### Graph API Berechtigungen
Die App Registration benötigt mindestens:
- User.Read.All
- Group.Read.All
- Directory.Read.All