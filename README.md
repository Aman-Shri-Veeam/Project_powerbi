# Power BI Backup & Restore - Working Directory

This is a clean working directory containing only the essential files needed to run the Power BI Backup & Restore project. All documentation (.md), shell scripts (.sh), and batch files (.bat) have been excluded.

## Directory Structure

```
Working/
├── Core Application Files
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration settings
│   ├── logger.py                  # Logging utilities
│   ├── models.py                  # Data models
│   ├── auth_and_api.py            # Power BI API authentication and calls
│   ├── backup_service.py          # Backup logic and services
│   ├── restore_service.py         # Restoration logic and services
│   ├── storage.py                 # File storage management
│   └── quickstart.py              # Quick start utilities
│
├── Configuration Files
│   ├── requirements.txt            # Python dependencies
│   └── .env                        # Environment variables (configure this!)
│
├── Frontend (UI)
│   └── static/
│       ├── index.html             # Web UI interface
│       ├── app.js                 # JavaScript logic
│       └── style.css              # Styling
│
├── Data Directories (auto-created)
│   ├── backups/                   # Backup storage location
│   └── logs/                      # Application logs
```

## Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit `.env` file with your Power BI credentials:

```env
POWERBI_CLIENT_ID=your_client_id
POWERBI_CLIENT_SECRET=your_client_secret
POWERBI_TENANT_ID=your_tenant_id
API_BASE_URL=https://api.powerbi.com/v1.0/myorg
BACKUP_PATH=./backups
DEBUG=false
```

### 3. Run the Application

```bash
# Start the FastAPI server and UI
python main.py
```

The UI will be available at: `http://localhost:8000`

### 4. Alternative: Quick Start

```bash
# Run the quick start module
python quickstart.py
```

## API Endpoints

### Backup Operations
- `GET /api/workspaces` - List all workspaces
- `POST /api/backup/start/{workspace_id}` - Start backup of a workspace
- `GET /api/backups` - List all backups

### Restore Operations
- `POST /api/restore/components/{workspace_id}` - Restore backup components to workspace
- `GET /api/backup/{backup_id}` - Get backup details

### Query Parameters for Restoration
```
?backup_id=BACKUP_ID
&restore_reports=true|false
&restore_datasets=true|false
&restore_refresh_schedules=true|false
&restore_dashboards=true|false
&restore_dataflows=true|false
&restore_apps=true|false
```

## Project Features

✅ **Backup Operations**
- Backup all Power BI reports (PBIX files)
- Backup dataset configurations
- Backup refresh schedules
- Backup workspace metadata

✅ **Restore Operations**
- Restore PBIX reports to target workspace
- Restore dataset configurations
- Restore enabled refresh schedules (disabled are skipped)
- Selective component restoration

✅ **Web UI**
- List backups
- View backup details
- Select components to restore
- Monitor restoration progress

## File Descriptions

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application with all REST endpoints |
| `auth_and_api.py` | Power BI API client with Azure AD authentication |
| `backup_service.py` | Services for backing up workspaces |
| `restore_service.py` | Services for restoring components |
| `storage.py` | Backup file storage and retrieval |
| `models.py` | Pydantic models for request/response validation |
| `logger.py` | Centralized logging utilities |
| `config.py` | Configuration settings from environment variables |
| `quickstart.py` | Utilities for quick testing and setup |
| `index.html` | Web UI home page |
| `app.js` | Frontend logic and API calls |
| `style.css` | UI styling |

## Refresh Schedule Behavior

**Important:** Refresh schedules are **only restored if they are ENABLED** in the backup.

### Backup Data Example
```json
{
  "schedule": {
    "enabled": true,
    "days": ["Monday", "Wednesday", "Friday"],
    "times": ["02:00"],
    "localTimeZoneId": "UTC",
    "notifyOption": "MailOnFailure"
  }
}
```

### Restoration
- ✅ If `enabled=true` and has `days` and `times` → **RESTORED**
- ⏭️ If `enabled=false` → **SKIPPED**
- ⏭️ If `enabled=true` but no `days`/`times` → **SKIPPED**

## Logging

Logs are saved to the `logs/` directory. Check logs for:
- Backup progress
- Restoration status
- API errors
- Configuration issues

Access logs from:
```bash
# View latest logs
tail -f logs/app.log

# Or on Windows
Get-Content -Path logs/app.log -Wait
```

## Requirements

- Python 3.8+
- Dependencies: See `requirements.txt`
- Power BI Service Principal credentials
- Azure AD App Registration

## Troubleshooting

### "Access token failed"
- Verify `POWERBI_CLIENT_ID`, `POWERBI_CLIENT_SECRET`, `POWERBI_TENANT_ID` in `.env`
- Check Azure AD app has Power BI API permissions

### "PBIX import failed"
- Verify workspace ID exists
- Check file path is correct
- Ensure service principal has workspace access

### "Refresh schedule error"
- Only enabled schedules are restored
- Check schedule has valid days and times
- Verify dataset exists in target workspace

## Next Steps

1. Configure `.env` with your credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python main.py`
4. Open browser: `http://localhost:8000`
5. Start creating backups and restoring!

## Support

For issues, check:
- `logs/` directory for detailed error logs
- API response messages in the UI
- Power BI API documentation: https://learn.microsoft.com/en-us/rest/api/power-bi/
