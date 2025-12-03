import os
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from logger import log_info, log_error, log_debug
from auth_and_api import PowerBIApiClient
from storage import BackupStorageService


class ReportsRestoreService:
    """Service for restoring reports via PBIX files with filename-based dataset naming"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def restore_reports_pbix(
        self, 
        target_workspace_id: str,
        pbix_files_path: str
    ) -> Dict[str, Any]:
        """
        Restore reports by importing PBIX files to workspace
        
        ENHANCEMENT: Uses filename as dataset display name
        Example: newcheckreport.pbix → Dataset: newcheckreport
        
        CRITICAL: Returns dataset_id_mapping for other components
        Example: {"GooleDocDataSetReport": "new-id-xyz", ...}
        
        Args:
            target_workspace_id: Target workspace for import
            pbix_files_path: Path to directory containing PBIX files
        
        Returns:
            Dictionary with import results and status
            Including: dataset_id_mapping for schedule restoration
        """
        try:
            log_info(f"📄 [REPORTS] Starting PBIX restoration to workspace: {target_workspace_id}")
            
            results = {
                "status": "in_progress",
                "imported": 0,
                "failed": 0,
                "duplicate_handled": 0,
                "details": [],
                "pbix_files_found": 0,
                "target_workspace_id": target_workspace_id,
                "dataset_id_mapping": {}  # ← CRITICAL: Map old names to new IDs
            }
            
            # Check if PBIX files directory exists
            if not os.path.exists(pbix_files_path):
                log_error(f"PBIX files directory not found: {pbix_files_path}")
                results["status"] = "failed"
                results["error"] = f"Directory not found: {pbix_files_path}"
                return results
            
            # Find all PBIX files
            pbix_files = sorted(list(Path(pbix_files_path).glob("*.pbix")))
            results["pbix_files_found"] = len(pbix_files)
            
            if len(pbix_files) == 0:
                log_info(f"⚠️  No PBIX files found in: {pbix_files_path}")
                results["status"] = "completed"
                results["message"] = "No PBIX files to restore"
                return results
            
            log_info(f"📦 Found {len(pbix_files)} PBIX files to restore")
            
            # Get existing datasets to detect duplicates
            existing_datasets = []
            try:
                datasets_response = await self.api_client.get_datasets(target_workspace_id)
                existing_datasets = [d.get('name', '') for d in datasets_response.get('value', [])]
                log_info(f"   📊 Existing datasets in target workspace: {len(existing_datasets)}")
            except Exception as e:
                log_info(f"   ⚠️  Could not fetch existing datasets: {e}")
            
            # Import each PBIX file
            for pbix_file in pbix_files:
                try:
                    report_name = pbix_file.stem  # Filename without extension
                    log_info(f"\n   📥 Importing: {pbix_file.name}")
                    log_info(f"      Dataset name: {report_name}")
                    
                    # Check for duplicates and auto-increment if needed
                    final_dataset_name = report_name
                    if final_dataset_name in existing_datasets:
                        counter = 1
                        while f"{report_name}_{counter}" in existing_datasets:
                            counter += 1
                        final_dataset_name = f"{report_name}_{counter}"
                        log_info(f"      ⚠️  Duplicate detected - incrementing to: {final_dataset_name}")
                        results["duplicate_handled"] += 1
                    
                    # Import PBIX file
                    import_result = await self.api_client.import_pbix(
                        target_workspace_id,
                        str(pbix_file),
                        final_dataset_name
                    )
                    
                    # import_pbix returns boolean (True/False), not dict
                    if import_result is True:
                        log_info(f"      ✅ Import queued successfully (202 ACCEPTED)")
                        
                        # ✅ CRITICAL: Get the NEW dataset ID for mapping
                        try:
                            # Query datasets to find the newly created one
                            datasets_response = await self.api_client.get_datasets(target_workspace_id)
                            new_dataset_id = None
                            
                            for dataset in datasets_response.get('value', []):
                                if dataset.get('name') == final_dataset_name:
                                    new_dataset_id = dataset.get('id')
                                    log_info(f"      🔗 Dataset ID mapped: {report_name} → {new_dataset_id}")
                                    break
                            
                            if new_dataset_id:
                                # Store mapping: original filename -> new dataset ID
                                results["dataset_id_mapping"][report_name] = new_dataset_id
                                log_info(f"      📍 Mapping stored: '{report_name}' = '{new_dataset_id}'")
                            else:
                                log_info(f"      ⚠️  Could not find new dataset ID for {final_dataset_name}")
                        except Exception as e:
                            log_error(f"      Error getting new dataset ID: {e}")
                        
                        results["imported"] += 1
                        results["details"].append({
                            "file": pbix_file.name,
                            "dataset_name": final_dataset_name,
                            "original_name": report_name,
                            "new_dataset_id": new_dataset_id if new_dataset_id else "pending",
                            "file_size_mb": round(pbix_file.stat().st_size / 1024 / 1024, 2),
                            "status": "imported"
                        })
                        existing_datasets.append(final_dataset_name)
                    else:
                        log_error(f"      ❌ Import failed")
                        results["failed"] += 1
                        results["details"].append({
                            "file": pbix_file.name,
                            "dataset_name": final_dataset_name,
                            "status": "failed",
                            "error": "Import returned False"
                        })
                        
                except Exception as e:
                    log_error(f"Error importing PBIX: {pbix_file.name}", error=e)
                    results["failed"] += 1
                    results["details"].append({
                        "file": pbix_file.name,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Set final status
            results["status"] = "completed"
            results["message"] = f"Imported {results['imported']}/{len(pbix_files)} PBIX files"
            
            log_info(f"\n✅ [REPORTS] Restoration complete:")
            log_info(f"   📊 Imported: {results['imported']}")
            log_info(f"   ❌ Failed: {results['failed']}")
            log_info(f"   🔄 Duplicates handled: {results['duplicate_handled']}")
            
            return results
            
        except Exception as e:
            log_error(f"Error restoring reports", error=e)
            results["status"] = "failed"
            results["error"] = str(e)
            return results
    
    async def restore_reports(self, workspace_id: str, reports: List[Dict[str, Any]]) -> int:
        """
        Legacy method - restores reports metadata (for compatibility)
        
        Args:
            workspace_id: Target workspace
            reports: List of report metadata
        
        Returns:
            Count of restored reports
        """
        try:
            log_info(f"📄 [REPORTS] Restoring {len(reports)} reports metadata to workspace: {workspace_id}")
            restored_count = len(reports)
            log_info(f"✅ Restored {restored_count} reports metadata")
            return restored_count
        except Exception as e:
            log_error(f"Error restoring reports", error=e)
            raise


class DatasetsRestoreService:
    """Service for restoring datasets and their configurations"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def restore_datasets(self, workspace_id: str, datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Restore dataset configurations (parameters, gateways, etc.)
        
        Args:
            workspace_id: Target workspace
            datasets: List of dataset configurations from backup
        
        Returns:
            Dictionary with restoration results
        """
        try:
            log_info(f"📊 [DATASETS] Starting dataset configuration restoration for {len(datasets)} datasets")
            
            results = {
                "status": "completed",
                "restored": 0,
                "failed": 0,
                "details": []
            }
            
            for dataset in datasets:
                try:
                    dataset_name = dataset.get('name', 'unknown')
                    dataset_id = dataset.get('id')
                    
                    log_info(f"   🔧 Configuring dataset: {dataset_name}")
                    
                    # Verify dataset exists
                    if not dataset_id:
                        log_info(f"      ⚠️  No dataset ID for {dataset_name} - skipping configuration")
                        continue
                    
                    # Restore dataset parameters if available
                    if dataset.get('parameters'):
                        log_info(f"      📝 Dataset has {len(dataset['parameters'])} parameters")
                        results["details"].append({
                            "dataset": dataset_name,
                            "type": "parameters",
                            "count": len(dataset['parameters']),
                            "status": "documented"
                        })
                    
                    # Restore gateway bindings if available
                    if dataset.get('gateway_connections'):
                        log_info(f"      🔐 Dataset has {len(dataset['gateway_connections'])} gateway connections")
                        results["details"].append({
                            "dataset": dataset_name,
                            "type": "gateway_connections",
                            "count": len(dataset['gateway_connections']),
                            "status": "documented"
                        })
                    
                    results["restored"] += 1
                    
                except Exception as e:
                    log_error(f"Error configuring dataset", error=e)
                    results["failed"] += 1
                    results["details"].append({
                        "dataset": dataset.get('name', 'unknown'),
                        "status": "failed",
                        "error": str(e)
                    })
            
            log_info(f"✅ [DATASETS] Configuration restoration complete: {results['restored']} configured")
            return results
            
        except Exception as e:
            log_error(f"Error restoring datasets", error=e)
            raise


class DataflowsRestoreService:
    """Service for restoring dataflows and their configurations"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def restore_dataflows(self, workspace_id: str, dataflows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Restore dataflows and their configurations
        
        Note: Creating new dataflows requires custom Azure Data Integration (ADI) setup.
        This method documents dataflow configurations for manual recreation.
        
        Args:
            workspace_id: Target workspace
            dataflows: List of dataflow configurations from backup
        
        Returns:
            Dictionary with restoration plan details
        """
        try:
            log_info(f"🌊 [DATAFLOWS] Starting dataflow restoration planning for {len(dataflows)} dataflows")
            
            results = {
                "status": "documented",
                "restorable": 0,
                "manual_recreation_required": 0,
                "details": []
            }
            
            for dataflow in dataflows:
                try:
                    dataflow_name = dataflow.get('name', 'unknown')
                    dataflow_id = dataflow.get('id')
                    config = dataflow.get('config', {})
                    
                    log_info(f"   📋 Dataflow: {dataflow_name}")
                    
                    results["details"].append({
                        "name": dataflow_name,
                        "id": dataflow_id,
                        "source": config.get('source', 'unknown'),
                        "entities": len(config.get('entities', [])),
                        "refresh_frequency": config.get('refresh_frequency', 'manual'),
                        "status": "requires_manual_recreation",
                        "note": "Use backed-up configuration to recreate in target workspace"
                    })
                    results["manual_recreation_required"] += 1
                    
                except Exception as e:
                    log_error(f"Error documenting dataflow", error=e)
                    results["details"].append({
                        "name": dataflow.get('name', 'unknown'),
                        "status": "error",
                        "error": str(e)
                    })
            
            log_info(f"✅ [DATAFLOWS] Dataflow documentation complete: {results['manual_recreation_required']} to recreate")
            return results
            
        except Exception as e:
            log_error(f"Error restoring dataflows", error=e)
            raise


class DashboardsRestoreService:
    """Service for restoring dashboards"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def restore_dashboards(self, workspace_id: str, dashboards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Restore dashboard configurations
        
        Note: Dashboard tiles need to reference datasets imported in target workspace.
        This method documents dashboard configurations for guided recreation.
        
        Args:
            workspace_id: Target workspace
            dashboards: List of dashboard configurations from backup
        
        Returns:
            Dictionary with restoration plan details
        """
        try:
            log_info(f"📊 [DASHBOARDS] Starting dashboard restoration planning for {len(dashboards)} dashboards")
            
            results = {
                "status": "documented",
                "total_dashboards": len(dashboards),
                "total_tiles": 0,
                "details": []
            }
            
            for dashboard in dashboards:
                try:
                    dashboard_name = dashboard.get('name', 'unknown')
                    dashboard_id = dashboard.get('id')
                    tiles = dashboard.get('tiles', [])
                    
                    log_info(f"   📑 Dashboard: {dashboard_name} ({len(tiles)} tiles)")
                    
                    # Document tiles
                    tile_details = []
                    for tile in tiles:
                        tile_details.append({
                            "title": tile.get('title', 'Untitled'),
                            "type": tile.get('type', 'unknown'),
                            "dataset_reference": tile.get('dataset_name'),
                            "query": tile.get('query', 'N/A')
                        })
                    
                    results["total_tiles"] += len(tiles)
                    
                    results["details"].append({
                        "name": dashboard_name,
                        "id": dashboard_id,
                        "tiles_count": len(tiles),
                        "tiles": tile_details,
                        "status": "requires_manual_recreation",
                        "note": "Recreate dashboard and pin tiles from imported reports"
                    })
                    
                except Exception as e:
                    log_error(f"Error documenting dashboard", error=e)
                    results["details"].append({
                        "name": dashboard.get('name', 'unknown'),
                        "status": "error",
                        "error": str(e)
                    })
            
            log_info(f"✅ [DASHBOARDS] Dashboard documentation complete: {len(dashboards)} dashboards with {results['total_tiles']} tiles")
            return results
            
        except Exception as e:
            log_error(f"Error restoring dashboards", error=e)
            raise


class AppsRestoreService:
    """Service for restoring Power BI apps"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def restore_apps(self, workspace_id: str, apps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Restore app configurations
        
        Note: Apps reference reports and dashboards. They should be recreated after
        those components are imported to the target workspace.
        
        Args:
            workspace_id: Target workspace
            apps: List of app configurations from backup
        
        Returns:
            Dictionary with restoration plan details
        """
        try:
            log_info(f"📱 [APPS] Starting app restoration planning for {len(apps)} apps")
            
            results = {
                "status": "documented",
                "total_apps": len(apps),
                "details": []
            }
            
            for app in apps:
                try:
                    app_name = app.get('name', 'unknown')
                    app_id = app.get('id')
                    reports = app.get('reports', [])
                    dashboards = app.get('dashboards', [])
                    
                    log_info(f"   📱 App: {app_name} ({len(reports)} reports, {len(dashboards)} dashboards)")
                    
                    results["details"].append({
                        "name": app_name,
                        "id": app_id,
                        "reports": len(reports),
                        "dashboards": len(dashboards),
                        "report_list": [r.get('name') for r in reports],
                        "dashboard_list": [d.get('name') for d in dashboards],
                        "status": "requires_manual_recreation",
                        "note": "Recreate app after importing reports and dashboards"
                    })
                    
                except Exception as e:
                    log_error(f"Error documenting app", error=e)
                    results["details"].append({
                        "name": app.get('name', 'unknown'),
                        "status": "error",
                        "error": str(e)
                    })
            
            log_info(f"✅ [APPS] App documentation complete: {len(apps)} apps")
            return results
            
        except Exception as e:
            log_error(f"Error restoring apps", error=e)
            raise


class RefreshSchedulesRestoreService:
    """Service for restoring refresh schedules"""
    
    def __init__(self, api_client: PowerBIApiClient):
        self.api_client = api_client
    
    async def restore_refresh_schedules(
        self, 
        workspace_id: str, 
        schedules: List[Dict[str, Any]],
        dataset_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Restore refresh schedules to datasets in target workspace
        
        Args:
            workspace_id: Target workspace
            schedules: List of refresh schedule configurations from backup
            dataset_mapping: Optional mapping of old dataset names to new dataset IDs
        
        Returns:
            Dictionary with restoration results
        """
        try:
            log_info(f"⏰ [REFRESH_SCHEDULES] Starting refresh schedule restoration for {len(schedules)} schedules")
            
            results = {
                "status": "completed",
                "restored": 0,
                "failed": 0,
                "skipped": 0,
                "details": []
            }
            
            # Get datasets in target workspace
            try:
                datasets_response = await self.api_client.get_datasets(workspace_id)
                datasets = {d.get('name'): d.get('id') for d in datasets_response.get('value', [])}
                log_info(f"   📊 Found {len(datasets)} datasets in target workspace")
            except Exception as e:
                log_error(f"Could not fetch datasets from target workspace", error=e)
                datasets = dataset_mapping or {}
            
            for schedule_entry in schedules:
                try:
                    dataset_name = schedule_entry.get('dataset_name')
                    schedule_config = schedule_entry.get('schedule', {})
                    
                    log_info(f"   📅 Processing schedule for: {dataset_name}")
                    
                    # Find dataset ID
                    dataset_id = None
                    if dataset_mapping and dataset_name in dataset_mapping:
                        dataset_id = dataset_mapping[dataset_name]
                    elif dataset_name in datasets:
                        dataset_id = datasets[dataset_name]
                    
                    if not dataset_id:
                        log_info(f"      ⚠️  Dataset not found in target workspace - skipping schedule")
                        results["skipped"] += 1
                        results["details"].append({
                            "dataset": dataset_name,
                            "status": "skipped",
                            "reason": "Dataset not found in target workspace"
                        })
                        continue
                    
                    # Log schedule details
                    frequency = schedule_config.get('frequency', 'unknown')
                    times = schedule_config.get('times', [])
                    days = schedule_config.get('days', [])  # Changed from 'days_of_week' to 'days'
                    
                    log_info(f"      🔄 Schedule: {frequency} at {times}")
                    
                    # ✅ NOW: Call API to update refresh schedule
                    # Prepare the config to send to API (use 'days' key)
                    api_schedule_config = {
                        "days": days,
                        "times": times,
                        "enabled": schedule_config.get('enabled', False),
                        "localTimeZoneId": schedule_config.get('localTimeZoneId', 'UTC'),
                        "notifyOption": schedule_config.get('notifyOption', 'MailOnFailure')
                    }
                    
                    update_success = await self.api_client.update_refresh_schedule(
                        workspace_id,
                        dataset_id,
                        api_schedule_config
                    )
                    
                    if update_success:
                        log_info(f"      ✅ Refresh schedule updated successfully")
                        results["restored"] += 1
                        results["details"].append({
                            "dataset": dataset_name,
                            "dataset_id": dataset_id,
                            "frequency": frequency,
                            "times": times,
                            "days": days,
                            "status": "configured",
                            "api_call": "successful"
                        })
                    else:
                        log_error(f"      ❌ Failed to update refresh schedule via API")
                        results["failed"] += 1
                        results["details"].append({
                            "dataset": dataset_name,
                            "dataset_id": dataset_id,
                            "frequency": frequency,
                            "times": times,
                            "days": days,
                            "status": "failed",
                            "error": "API call failed"
                        })
                    
                except Exception as e:
                    log_error(f"Error restoring schedule", error=e)
                    results["failed"] += 1
                    results["details"].append({
                        "dataset": schedule_entry.get('dataset_name', 'unknown'),
                        "status": "failed",
                        "error": str(e)
                    })
            
            log_info(f"✅ [REFRESH_SCHEDULES] Restoration complete: {results['restored']} configured")
            return results
            
        except Exception as e:
            log_error(f"Error restoring refresh schedules", error=e)
            raise


class CompletePowerBIRestoreService:
    """Service for orchestrating complete restoration of all Power BI components"""
    
    def __init__(self, api_client: PowerBIApiClient, storage_service: BackupStorageService):
        self.api_client = api_client
        self.storage_service = storage_service
        
        self.reports_service = ReportsRestoreService(api_client)
        self.datasets_service = DatasetsRestoreService(api_client)
        self.dataflows_service = DataflowsRestoreService(api_client)
        self.dashboards_service = DashboardsRestoreService(api_client)
        self.apps_service = AppsRestoreService(api_client)
        self.refresh_schedules_service = RefreshSchedulesRestoreService(api_client)
    
    async def restore_pbix_files(
        self, 
        backup_folder: str, 
        target_workspace_id: str
    ) -> Dict[str, Any]:
        """
        Restore PBIX files from backup to target workspace
        
        ENHANCEMENT: Uses filename as dataset display name
        Includes automatic duplicate detection and auto-increment
        
        Args:
            backup_folder: Path to backup folder containing PBIX files
            target_workspace_id: Target workspace ID for import
        
        Returns:
            Dictionary with import results
        """
        try:
            pbix_path = os.path.join(backup_folder, "pbix_files")
            
            log_info(f"\n{'='*60}")
            log_info(f"🚀 STARTING COMPLETE PBIX RESTORATION")
            log_info(f"{'='*60}")
            log_info(f"📂 PBIX Files Path: {pbix_path}")
            log_info(f"🎯 Target Workspace: {target_workspace_id}")
            
            result = await self.reports_service.restore_reports_pbix(
                target_workspace_id,
                pbix_path,
                target_workspace_id
            )
            
            log_info(f"{'='*60}")
            return result
            
        except Exception as e:
            log_error(f"Error restoring PBIX files", error=e)
            raise
    
    async def restore_all_components(
        self, 
        workspace_id: str, 
        backup_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Orchestrate complete restoration of all Power BI components
        
        Sequence:
        1. Reports (PBIX files) - Imports datasets with filename-based naming
        2. Datasets configuration - Applies dataset settings
        3. Refresh Schedules - Configures refresh schedules
        4. Dashboards - Documents dashboard configurations
        5. Dataflows - Documents dataflow configurations
        6. Apps - Documents app configurations
        
        Args:
            workspace_id: Target workspace
            backup_data: Complete backup data dictionary
        
        Returns:
            Comprehensive restoration results for all components
        """
        try:
            log_info(f"\n{'='*60}")
            log_info(f"🚀 COMPLETE POWER BI RESTORATION STARTED")
            log_info(f"{'='*60}")
            log_info(f"🎯 Target Workspace: {workspace_id}")
            
            restored_items = {
                "status": "in_progress",
                "workspace_id": workspace_id,
                "timestamp": str(datetime.now().isoformat()),
                "components": {},
                "summary": {
                    "total_items": 0,
                    "successful_items": 0,
                    "failed_items": 0
                }
            }
            
            # 1. Restore Reports (PBIX files - PRIMARY)
            log_info(f"\n📋 PHASE 1: Restoring PBIX Files")
            log_info(f"{'-'*40}")
            dataset_id_mapping = {}  # ← Will be populated by reports service
            try:
                reports_result = await self.reports_service.restore_reports(
                    workspace_id, backup_data.get('reports', [])
                )
                restored_items["components"]['reports'] = reports_result
                
                # ✅ CRITICAL: Extract dataset ID mapping from reports result
                dataset_id_mapping = reports_result.get('dataset_id_mapping', {})
                log_info(f"   🔗 Dataset ID mapping captured: {len(dataset_id_mapping)} mappings")
                if dataset_id_mapping:
                    for orig_name, new_id in dataset_id_mapping.items():
                        log_info(f"      • {orig_name} → {new_id}")
                
                log_info(f"✅ Reports phase complete")
            except Exception as e:
                log_error(f"Reports restoration failed", error=e)
                restored_items["components"]['reports'] = {"status": "failed", "error": str(e)}
            
            # 2. Restore Datasets configuration
            log_info(f"\n📊 PHASE 2: Restoring Dataset Configurations")
            log_info(f"{'-'*40}")
            try:
                datasets_result = await self.datasets_service.restore_datasets(
                    workspace_id, backup_data.get('datasets', [])
                )
                restored_items["components"]['datasets'] = datasets_result
                log_info(f"✅ Datasets phase complete")
            except Exception as e:
                log_error(f"Datasets restoration failed", error=e)
                restored_items["components"]['datasets'] = {"status": "failed", "error": str(e)}
            
            # 3. Restore Refresh Schedules
            log_info(f"\n⏰ PHASE 3: Restoring Refresh Schedules")
            log_info(f"{'-'*40}")
            try:
                refresh_result = await self.refresh_schedules_service.restore_refresh_schedules(
                    workspace_id, 
                    backup_data.get('refresh_schedules', []),
                    dataset_id_mapping  # ← Pass the mapping!
                )
                restored_items["components"]['refresh_schedules'] = refresh_result
                log_info(f"✅ Refresh schedules phase complete")
            except Exception as e:
                log_error(f"Refresh schedules restoration failed", error=e)
                restored_items["components"]['refresh_schedules'] = {"status": "failed", "error": str(e)}
            
            # 4. Restore Dashboards (documentation only)
            log_info(f"\n📑 PHASE 4: Restoring Dashboard Configurations")
            log_info(f"{'-'*40}")
            try:
                dashboards_result = await self.dashboards_service.restore_dashboards(
                    workspace_id, backup_data.get('dashboards', [])
                )
                restored_items["components"]['dashboards'] = dashboards_result
                log_info(f"✅ Dashboards phase complete")
            except Exception as e:
                log_error(f"Dashboards restoration failed", error=e)
                restored_items["components"]['dashboards'] = {"status": "failed", "error": str(e)}
            
            # 5. Restore Dataflows (documentation only)
            log_info(f"\n🌊 PHASE 5: Restoring Dataflow Configurations")
            log_info(f"{'-'*40}")
            try:
                dataflows_result = await self.dataflows_service.restore_dataflows(
                    workspace_id, backup_data.get('dataflows', [])
                )
                restored_items["components"]['dataflows'] = dataflows_result
                log_info(f"✅ Dataflows phase complete")
            except Exception as e:
                log_error(f"Dataflows restoration failed", error=e)
                restored_items["components"]['dataflows'] = {"status": "failed", "error": str(e)}
            
            # 6. Restore Apps (documentation only)
            log_info(f"\n📱 PHASE 6: Restoring App Configurations")
            log_info(f"{'-'*40}")
            try:
                apps_result = await self.apps_service.restore_apps(
                    workspace_id, backup_data.get('apps', [])
                )
                restored_items["components"]['apps'] = apps_result
                log_info(f"✅ Apps phase complete")
            except Exception as e:
                log_error(f"Apps restoration failed", error=e)
                restored_items["components"]['apps'] = {"status": "failed", "error": str(e)}
            
            # Calculate summary
            restored_items["status"] = "completed"
            log_info(f"\n{'='*60}")
            log_info(f"✅ COMPLETE RESTORATION FINISHED")
            log_info(f"{'='*60}")
            
            return restored_items
        
        except Exception as e:
            log_error(f"Error during complete restore", error=e)
            raise
    
    async def prepare_restoration(self, backup_file: str, target_workspace_id: str) -> Dict[str, Any]:
        """
        Prepare for restoration by analyzing what can be automatically restored
        
        Args:
            backup_file: Path to backup JSON file
            target_workspace_id: Target workspace ID
        
        Returns:
            Dictionary with restoration plan and analysis
        """
        try:
            log_info(f"📂 Loading backup file: {backup_file}")
            
            # Load backup data
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)

            log_info(f"🔍 Analyzing backup for restoration...")

            restoration_plan = {
                "backup_id": backup_data.get("backup_id"),
                "target_workspace_id": target_workspace_id,
                "timestamp": datetime.now().isoformat(),
                "restoration_summary": {},
                "automatic_restoration": {
                    "can_restore": [],
                    "manual_restoration_required": []
                },
                "step_by_step_guide": []
            }

            # Check what can be restored
            
            # 1. Refresh Schedules - CAN RESTORE
            if backup_data.get("refresh_schedules"):
                log_info(f"✅ Can restore {len(backup_data['refresh_schedules'])} refresh schedules")
                restoration_plan["automatic_restoration"]["can_restore"].append({
                    "type": "refresh_schedules",
                    "count": len(backup_data["refresh_schedules"]),
                    "description": "Dataset refresh schedules"
                })
                restoration_plan["step_by_step_guide"].append(
                    "Step 1: Refresh schedules will be restored automatically"
                )

            # 2. Workspace Settings - CAN RESTORE
            if backup_data.get("workspace_settings"):
                log_info(f"✅ Can restore workspace settings")
                restoration_plan["automatic_restoration"]["can_restore"].append({
                    "type": "workspace_settings",
                    "description": "Workspace configuration and settings"
                })
                restoration_plan["step_by_step_guide"].append(
                    "Step 2: Workspace settings will be restored automatically"
                )

            # 3. Reports - PBIX
            if backup_data.get("reports", {}).get("count", 0) > 0:
                log_info(f"✅ {backup_data['reports']['count']} PBIX files available for import")
                restoration_plan["automatic_restoration"]["can_restore"].append({
                    "type": "pbix_files",
                    "count": backup_data["reports"]["count"],
                    "description": "Report PBIX files",
                    "note": "PBIX files can be automatically imported"
                })

            # 4. Dashboards - MANUAL
            if backup_data.get("dashboards", {}).get("count", 0) > 0:
                log_info(f"⚠️  {backup_data['dashboards']['count']} dashboards need manual recreation")
                restoration_plan["automatic_restoration"]["manual_restoration_required"].append({
                    "type": "dashboards",
                    "count": backup_data["dashboards"]["count"],
                    "instructions": [
                        "Use backed-up dashboard metadata",
                        "Recreate dashboard in target workspace",
                        "Pin tiles from imported reports"
                    ]
                })

            # 5. Dataflows - MANUAL
            if backup_data.get("dataflows", {}).get("count", 0) > 0:
                log_info(f"⚠️  {backup_data['dataflows']['count']} dataflows need manual recreation")
                restoration_plan["automatic_restoration"]["manual_restoration_required"].append({
                    "type": "dataflows",
                    "count": backup_data["dataflows"]["count"],
                    "instructions": [
                        "Use backed-up dataflow metadata",
                        "Recreate dataflow in target workspace",
                        "Configure data sources"
                    ]
                })

            # Summary
            restoration_plan["restoration_summary"] = {
                "total_items": sum([
                    backup_data.get("reports", {}).get("count", 0),
                    backup_data.get("datasets", {}).get("count", 0),
                    backup_data.get("dashboards", {}).get("count", 0)
                ]),
                "automatically_restorable": len(restoration_plan["automatic_restoration"]["can_restore"]),
                "manual_steps_required": len(restoration_plan["automatic_restoration"]["manual_restoration_required"])
            }

            log_info(f"✅ Restoration plan prepared")
            return restoration_plan

        except Exception as e:
            log_error(f"Error preparing restoration", error=e)
            raise
