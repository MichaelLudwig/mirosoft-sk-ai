# Global Reader Rechte für App Registration

## Methode 1: Über Azure Portal (Empfohlen)

1. **Azure Portal öffnen**
   - Gehe zu https://portal.azure.com
   - Navigiere zu "Azure Active Directory"

2. **App Registration finden**
   - Klicke auf "App registrations"
   - Suche deine App

3. **API Permissions hinzufügen**
   - Klicke auf "API permissions"
   - Klicke auf "Add a permission"
   - Wähle "Microsoft Graph"
   - Wähle "Application permissions"
   - Füge folgende Permissions hinzu:
     - `AuditLog.Read.All` (für Aktivitätslogs)
     - `Directory.Read.All` (bereits vorhanden)
     - `Reports.Read.All` (für Nutzungsberichte)
     - `User.Read.All` (bereits vorhanden)

4. **Admin Consent erteilen**
   - Klicke auf "Grant admin consent for [Tenant]"
   - Bestätige mit "Yes"

## Methode 2: Global Reader Role zuweisen

1. **Azure AD Roles and administrators**
   - Gehe zu "Azure Active Directory" > "Roles and administrators"
   - Suche nach "Global Reader"
   - Klicke darauf

2. **Assignment hinzufügen**
   - Klicke auf "Add assignments"
   - Suche deine App (Service Principal Name)
   - Klicke auf "Add"

## PowerShell Alternative

```powershell
# Connect to Azure AD
Connect-AzureAD

# Get your Service Principal
$sp = Get-AzureADServicePrincipal -Filter "displayName eq 'YOUR_APP_NAME'"

# Get Global Reader role
$role = Get-AzureADDirectoryRole | Where-Object {$_.displayName -eq "Global Reader"}

# Assign role
Add-AzureADDirectoryRoleMember -ObjectId $role.ObjectId -RefObjectId $sp.ObjectId
```

## Wichtige API Endpoints für Aktivitäten

Nach dem Hinzufügen der Berechtigungen kannst du folgende Abfragen nutzen:

- **Letzte Anmeldungen**: `/auditLogs/signIns?$top=10&$orderby=createdDateTime desc`
- **Benutzeraktivitäten**: `/reports/getOffice365ActiveUserDetail(period='D7')`
- **App-Nutzung**: `/reports/getOffice365ActiveUserDetail(date=2025-06-15)`

## Hinweis
Nach dem Ändern der Berechtigungen kann es bis zu 10 Minuten dauern, bis sie aktiv sind.