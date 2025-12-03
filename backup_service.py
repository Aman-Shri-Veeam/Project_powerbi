from typing import Dict, Any, List
from datetime import datetime
from logger import log_info, log_error
from auth_and_api import PowerBIApiClient
from storage import BackupStorageService

class ReportsBackupService:
    """Service for backing up reports"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def backup_reports(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Backup all reports from a workspace"""
        try:
            log_info(f"Backing up reports for workspace: {workspace_id}")
            response = await self.api_client.get_reports(workspace_id)
            reports = response.get('value', [])
            log_info(f"Successfully backed up {len(reports)} reports")
            return reports
        except Exception as e:
            log_error(f"Error backing up reports", error=e)
            raise

class DatasetsBackupService:
    """Service for backing up datasets"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def backup_datasets(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Backup all datasets from a workspace"""
        try:
            log_info(f"Backing up datasets for workspace: {workspace_id}")
            response = await self.api_client.get_datasets(workspace_id)
            datasets = response.get('value', [])
            log_info(f"Successfully backed up {len(datasets)} datasets")
            return datasets
        except Exception as e:
            log_error(f"Error backing up datasets", error=e)
            raise

class DataflowsBackupService:
    """Service for backing up dataflows"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def backup_dataflows(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Backup all dataflows from a workspace"""
        try:
            log_info(f"Backing up dataflows for workspace: {workspace_id}")
            response = await self.api_client.get_dataflows(workspace_id)
            dataflows = response.get('value', [])
            log_info(f"Successfully backed up {len(dataflows)} dataflows")
            return dataflows
        except Exception as e:
            log_error(f"Error backing up dataflows", error=e)
            raise

class DashboardsBackupService:
    """Service for backing up dashboards"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def backup_dashboards(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Backup all dashboards from a workspace"""
        try:
            log_info(f"Backing up dashboards for workspace: {workspace_id}")
            response = await self.api_client.get_dashboards(workspace_id)
            dashboards = response.get('value', [])
            log_info(f"Successfully backed up {len(dashboards)} dashboards")
            return dashboards
        except Exception as e:
            log_error(f"Error backing up dashboards", error=e)
            raise

class AppsBackupService:
    """Service for backing up apps"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def backup_apps(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Backup all apps linked to a workspace"""
        try:
            log_info(f"Backing up apps for workspace: {workspace_id}")
            response = await self.api_client.get_apps()
            all_apps = response.get('value', [])
            filtered_apps = [app for app in all_apps if app.get('workspaceId') == workspace_id]
            log_info(f"Successfully backed up {len(filtered_apps)} apps")
            return filtered_apps
        except Exception as e:
            log_error(f"Error backing up apps (this is optional)", error=e)
            # Apps backup is optional - return empty list if not accessible
            log_info("Continuing backup without apps (permission not granted for /apps endpoint)")
            return []

class WorkspaceSettingsBackupService:
    """Service for backing up workspace settings"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def backup_workspace_settings(self, workspace_id: str) -> Dict[str, Any]:
        """Backup workspace settings"""
        try:
            log_info(f"Backing up workspace settings for workspace: {workspace_id}")
            workspace = await self.api_client.get_workspace_settings(workspace_id)
            log_info(f"Successfully backed up workspace settings")
            return workspace
        except Exception as e:
            log_error(f"Error backing up workspace settings", error=e)
            raise

class RefreshSchedulesBackupService:
    """Service for backing up refresh schedules"""
    
    def __init__(self, api_client: PowerBIApiClient, datasets_service: 'DatasetsBackupService'):
        self.api_client = api_client
        self.datasets_service = datasets_service
    
    async def backup_refresh_schedules(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Backup all refresh schedules for datasets"""
        try:
            log_info(f"Backing up refresh schedules for workspace: {workspace_id}")
            datasets = await self.datasets_service.backup_datasets(workspace_id)
            schedules = []
            
            for dataset in datasets:
                try:
                    schedule = await self.api_client.get_refresh_schedule(workspace_id, dataset['id'])
                    schedules.append({
                        'dataset_id': dataset['id'],
                        'dataset_name': dataset.get('name', 'Unknown'),
                        'schedule': schedule
                    })
                except Exception as e:
                    log_error(f"Error backing up refresh schedule for dataset {dataset['id']}", error=e)
            
            log_info(f"Successfully backed up {len(schedules)} refresh schedules")
            return schedules
        except Exception as e:
            log_error(f"Error backing up refresh schedules", error=e)
            raise

class CompletePowerBIBackupService:
    """Service for backing up all Power BI components"""
    
    def __init__(self, api_client: PowerBIApiClient, storage_service: BackupStorageService):
        self.api_client = api_client
        self.storage_service = storage_service
        
        self.reports_service = ReportsBackupService(api_client)
        self.datasets_service = DatasetsBackupService(api_client)
        self.dataflows_service = DataflowsBackupService(api_client)
        self.dashboards_service = DashboardsBackupService(api_client)
        self.apps_service = AppsBackupService(api_client)
        self.workspace_settings_service = WorkspaceSettingsBackupService(api_client)
        self.refresh_schedules_service = RefreshSchedulesBackupService(api_client, self.datasets_service)
    
    async def backup_all_components(self, workspace_id: str) -> Dict[str, Any]:
        """Backup all Power BI components"""
        try:
            log_info(f"Starting complete backup for workspace: {workspace_id}")
            
            # Backup all components concurrently where possible
            reports = await self.reports_service.backup_reports(workspace_id)
            datasets = await self.datasets_service.backup_datasets(workspace_id)
            dataflows = await self.dataflows_service.backup_dataflows(workspace_id)
            dashboards = await self.dashboards_service.backup_dashboards(workspace_id)
            apps = await self.apps_service.backup_apps(workspace_id)
            workspace_settings = await self.workspace_settings_service.backup_workspace_settings(workspace_id)
            refresh_schedules = await self.refresh_schedules_service.backup_refresh_schedules(workspace_id)
            
            # Store in storage service
            self.storage_service.store_reports(reports)
            self.storage_service.store_datasets(datasets)
            self.storage_service.store_dataflows(dataflows)
            self.storage_service.store_dashboards(dashboards)
            self.storage_service.store_apps(apps)
            self.storage_service.store_workspace_settings(workspace_settings)
            self.storage_service.store_refresh_schedules(refresh_schedules)
            self.storage_service.set_metadata(workspace_id, datetime.now())
            
            backup_data = self.storage_service.get_backup_data()
            log_info(f"Complete backup finished for workspace: {workspace_id}")
            
            return backup_data
        
        except Exception as e:
            log_error(f"Error during complete backup", error=e)
            raise
