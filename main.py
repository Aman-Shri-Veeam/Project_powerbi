from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import uuid
import os
import json
from typing import List
from pathlib import Path

from config import settings
from models import BackupRequest, RestoreRequest, BackupResponse, RestoreResponse
from auth_and_api import PowerBIAuthService, PowerBIApiClient
from restore_service import CompletePowerBIRestoreService
from storage import BackupStorageService
from enhanced_backup_service import EnhancedBackupService, BackupExportService
from logger import log_info, log_error

# Initialize FastAPI app
app = FastAPI(
    title="Power BI Backup Service",
    description="A service to back up and restore Power BI components",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (CSS, JS, images)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize services
auth_service = PowerBIAuthService()
api_client = PowerBIApiClient(auth_service)
storage_service = BackupStorageService(settings.backup_path)
restore_service = CompletePowerBIRestoreService(api_client, storage_service)

# Initialize backup and export services
enhanced_backup_service = EnhancedBackupService(api_client, storage_service)
backup_export_service = BackupExportService()

# Store for tracking async operations
backup_jobs: dict = {}

@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serve the frontend HTML"""
    frontend_path = Path(__file__).parent / "static" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    else:
        return {
            "status": "ok",
            "service": "Power BI Backup Service",
            "version": "1.0.0",
            "message": "Frontend not found, but API is running"
        }

@app.get("/api/health", tags=["Health"])
async def api_health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Power BI Backup Service",
        "version": "1.0.0"
    }

@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

# ===========================
# Workspaces Endpoints
# ===========================

@app.get("/api/workspaces", tags=["Workspaces"])
async def get_all_workspaces():
    """
    Fetch all Power BI workspaces that the service principal has access to.
    Returns a list of workspaces with their IDs and names.
    """
    try:
        log_info("Fetching all Power BI workspaces")
        workspaces = await api_client.get_workspaces()
        
        return {
            "status": "success",
            "count": len(workspaces),
            "workspaces": workspaces,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        log_error("Error fetching workspaces", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/workspaces/{workspace_id}", tags=["Workspaces"])
async def get_workspace_details(workspace_id: str):
    """
    Get details about a specific workspace, including its reports, datasets, and dashboards.
    """
    try:
        log_info(f"Fetching details for workspace: {workspace_id}")
        
        # Get workspace info
        workspace = await api_client.get_workspace(workspace_id)
        reports = await api_client.get_reports(workspace_id)
        datasets = await api_client.get_datasets(workspace_id)
        dashboards = await api_client.get_dashboards(workspace_id)
        
        return {
            "status": "success",
            "workspace": workspace,
            "reports_count": len(reports),
            "datasets_count": len(datasets),
            "dashboards_count": len(dashboards),
            "reports": reports[:10] if reports else [],  # Return first 10 for preview
            "datasets": datasets[:10] if datasets else [],
            "dashboards": dashboards[:10] if dashboards else [],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        log_error(f"Error fetching workspace details for {workspace_id}", error=e)
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Backup Endpoints
# ===========================

@app.post("/api/backup", response_model=BackupResponse, tags=["Backup"])
async def create_backup(request: BackupRequest, background_tasks: BackgroundTasks):
    """
    Create an enhanced backup of all Power BI components for a workspace.
    
    Features:
    - ✅ Automatically exports all reports as PBIX files
    - ✅ Backs up datasets with configuration
    - ✅ Captures dashboards metadata
    - ✅ Saves refresh schedules
    - ✅ Includes workspace settings
    
    - **workspace_id**: The Power BI workspace ID to backup
    """
    try:
        # Get workspace name for meaningful backup ID
        try:
            workspace_info = await api_client.get_workspace(request.workspace_id)
            workspace_name = workspace_info.get("name", "backup")
            # Sanitize workspace name for use in backup ID (remove spaces and special chars)
            workspace_name = workspace_name.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()[:30]
        except:
            workspace_name = "backup"
        
        # Generate backup ID with format: <workspace_name>_<timestamp>
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{workspace_name}_{timestamp}"
        
        log_info(f"🔄 Starting ENHANCED backup for workspace: {request.workspace_id} with ID: {backup_id}")
        
        # Run backup in background
        async def run_backup():
            try:
                log_info(f"📦 Starting enhanced backup process...")
                
                # Create enhanced backup with automatic PBIX export
                backup_result = await enhanced_backup_service.create_complete_backup(
                    request.workspace_id,
                    backup_name=backup_id
                )
                
                # Store job info
                backup_jobs[backup_id] = {
                    "status": "completed",
                    "timestamp": datetime.now(),
                    "workspace_id": request.workspace_id,
                    "workspace_name": workspace_name,
                    "backup_file": backup_result.get("backup_file"),
                    "items_backed_up": backup_result.get("items_backed_up"),
                    "message": f"✅ Backup complete with PBIX files exported"
                }
                
                log_info(f"✅ Enhanced backup {backup_id} completed successfully")
                log_info(f"  📄 Reports: {backup_result['items_backed_up'].get('reports', 0)} exported")
                log_info(f"  📊 Datasets: {backup_result['items_backed_up'].get('datasets', 0)} backed up")
                log_info(f"  📈 Dashboards: {backup_result['items_backed_up'].get('dashboards', 0)} backed up")
                
            except Exception as e:
                log_error(f"❌ Enhanced backup {backup_id} failed", error=e)
                backup_jobs[backup_id] = {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now()
                }
        
        background_tasks.add_task(run_backup)
        
        backup_jobs[backup_id] = {
            "status": "in_progress",
            "timestamp": datetime.now(),
            "workspace_id": request.workspace_id,
            "workspace_name": workspace_name,
            "message": "Backup in progress - exporting PBIX files..."
        }
        
        return BackupResponse(
            success=True,
            message="Enhanced backup started successfully - reports will be exported as PBIX files",
            backup_id=backup_id,
            timestamp=datetime.now()
        )
    
    except Exception as e:
        log_error("Error creating backup", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backup/{backup_id}", tags=["Backup"])
async def get_backup_status(backup_id: str):
    """Get the status of a backup job"""
    try:
        if backup_id not in backup_jobs:
            raise HTTPException(status_code=404, detail="Backup not found")
        
        job_info = backup_jobs[backup_id]
        return {
            "backup_id": backup_id,
            "status": job_info["status"],
            "timestamp": job_info["timestamp"],
            "workspace_id": job_info.get("workspace_id"),
            "error": job_info.get("error")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error getting backup status", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backups", tags=["Backup"])
async def list_backups():
    """List all available backups"""
    try:
        backups = storage_service.list_backups()
        return {
            "count": len(backups),
            "backups": backups
        }
    except Exception as e:
        log_error("Error listing backups", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backup/{backup_id}/download", tags=["Backup"])
async def download_backup(backup_id: str):
    """Download a backup file"""
    try:
        backup_filepath = os.path.join(settings.backup_path, f"backup_{backup_id}.json")
        
        if not os.path.exists(backup_filepath):
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        return FileResponse(
            path=backup_filepath,
            filename=f"backup_{backup_id}.json",
            media_type='application/json'
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error downloading backup", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backup/{backup_id}/pbix-files", tags=["Backup"])
async def get_pbix_files(backup_id: str):
    """
    Get list of exported PBIX files from a backup.
    Returns the file paths and metadata.
    """
    try:
        # Load backup metadata
        backup_file = os.path.join(settings.backup_path, backup_id, f"backup_{backup_id}.json")
        
        if not os.path.exists(backup_file):
            raise HTTPException(status_code=404, detail="Backup not found")
        
        with open(backup_file, 'r') as f:
            import json
            backup_data = json.load(f)
        
        # Extract PBIX export info
        reports_info = backup_data.get("reports", {})
        exported_reports = reports_info.get("exported_reports", [])
        export_summary = reports_info.get("export_summary", {})
        
        return {
            "status": "success",
            "backup_id": backup_id,
            "pbix_files_count": export_summary.get("successful", 0),
            "pbix_files": exported_reports,
            "export_summary": export_summary,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error getting PBIX files", error=e)
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Restore Endpoints
# ===========================

@app.post("/api/restore", response_model=RestoreResponse, tags=["Restore"])
async def create_restore(request: RestoreRequest, background_tasks: BackgroundTasks):
    """
    Restore Power BI components to a workspace from a backup.
    
    - **workspace_id**: The target Power BI workspace ID
    - **backup_file**: The backup ID to restore from (optional, uses latest if not specified)
    """
    try:
        restore_id = str(uuid.uuid4())
        
        # Get backup ID
        backup_id = request.backup_file
        if not backup_id:
            backups = storage_service.list_backups()
            if not backups:
                raise HTTPException(status_code=404, detail="No backups available to restore")
            backup_id = backups[-1]  # Use latest backup
        
        log_info(f"Starting restore for workspace: {request.workspace_id} from backup: {backup_id}")
        
        # Run restore in background
        async def run_restore():
            try:
                backup_data = storage_service.load_backup_from_file(backup_id)
                restored_items = await restore_service.restore_all_components(
                    request.workspace_id,
                    backup_data
                )
                backup_jobs[restore_id] = {
                    "status": "completed",
                    "timestamp": datetime.now(),
                    "workspace_id": request.workspace_id,
                    "restored_items": restored_items
                }
                log_info(f"Restore {restore_id} completed successfully")
            except Exception as e:
                log_error(f"Restore {restore_id} failed", error=e)
                backup_jobs[restore_id] = {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now()
                }
        
        background_tasks.add_task(run_restore)
        
        backup_jobs[restore_id] = {
            "status": "in_progress",
            "timestamp": datetime.now(),
            "workspace_id": request.workspace_id
        }
        
        return RestoreResponse(
            success=True,
            message="Restore started successfully",
            restored_items={},
            timestamp=datetime.now()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error creating restore", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restore/{restore_id}", tags=["Restore"])
async def get_restore_status(restore_id: str):
    """Get the status of a restore job"""
    try:
        if restore_id not in backup_jobs:
            raise HTTPException(status_code=404, detail="Restore job not found")
        
        job_info = backup_jobs[restore_id]
        return {
            "restore_id": restore_id,
            "status": job_info["status"],
            "timestamp": job_info["timestamp"],
            "workspace_id": job_info.get("workspace_id"),
            "restored_items": job_info.get("restored_items"),
            "error": job_info.get("error")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error getting restore status", error=e)
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Enhanced Restoration Endpoints
# ===========================

@app.post("/api/restore/plan", tags=["Restore"])
async def plan_restoration(backup_id: str, target_workspace_id: str):
    """
    Prepare a restoration plan from a backup.
    
    Returns:
    - What can be automatically restored
    - What requires manual steps
    - Step-by-step restoration guide
    """
    try:
        log_info(f"📋 Preparing restoration plan for {backup_id} → {target_workspace_id}")
        
        # Load backup metadata
        backup_file = os.path.join(settings.backup_path, backup_id, f"backup_{backup_id}.json")
        
        if not os.path.exists(backup_file):
            raise HTTPException(status_code=404, detail="Backup not found")
        
        # Prepare restoration plan
        plan = await restore_service.prepare_restoration(backup_file, target_workspace_id)
        
        return {
            "status": "success",
            "restoration_plan": plan,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error preparing restoration plan", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/restore/components/{workspace_id}", tags=["Restore"])
async def restore_components(
    workspace_id: str, 
    backup_id: str,
    restore_reports: bool = False,
    restore_datasets: bool = False,
    restore_refresh_schedules: bool = False,
    restore_dashboards: bool = False,
    restore_dataflows: bool = False,
    restore_apps: bool = False,
    background_tasks: BackgroundTasks = None
):
    """
    Unified restoration endpoint - restore selected Power BI components.
    
    Parameters:
    - **workspace_id**: Target workspace ID
    - **backup_id**: Backup ID to restore from
    - **restore_reports**: Import PBIX files and create reports (boolean)
    - **restore_datasets**: Restore dataset configurations (boolean)
    - **restore_refresh_schedules**: Restore refresh schedules (boolean)
    - **restore_dashboards**: Restore dashboard metadata (boolean)
    - **restore_dataflows**: Restore dataflow configurations (boolean)
    - **restore_apps**: Restore app configurations (boolean)
    
    Example requests:
    - Import PBIX only: ?restore_reports=true
    - Import PBIX + schedules: ?restore_reports=true&restore_refresh_schedules=true
    - Everything: ?restore_reports=true&restore_datasets=true&restore_refresh_schedules=true&restore_dashboards=true&restore_dataflows=true&restore_apps=true
    
    Returns:
    - Job ID to track progress
    - Status of each requested component
    """
    try:
        # Validate at least one component is selected
        if not any([restore_reports, restore_datasets, restore_refresh_schedules, 
                   restore_dashboards, restore_dataflows, restore_apps]):
            raise HTTPException(
                status_code=400, 
                detail="At least one component must be selected for restoration"
            )
        
        restore_job_id = str(uuid.uuid4())
        
        # Log what will be restored
        selected_components = []
        if restore_reports:
            selected_components.append("Reports (PBIX)")
        if restore_datasets:
            selected_components.append("Datasets")
        if restore_refresh_schedules:
            selected_components.append("Refresh Schedules")
        if restore_dashboards:
            selected_components.append("Dashboards")
        if restore_dataflows:
            selected_components.append("Dataflows")
        if restore_apps:
            selected_components.append("Apps")
        
        log_info(f"🔄 Starting unified restoration (Job: {restore_job_id})")
        log_info(f"   Components: {', '.join(selected_components)}")
        log_info(f"   Target Workspace: {workspace_id}")
        log_info(f"   Backup ID: {backup_id}")
        
        # Validate backup exists
        backup_folder = os.path.join(settings.backup_path, backup_id)
        backup_file = os.path.join(backup_folder, f"backup_{backup_id}.json")
        
        if not os.path.exists(backup_file):
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")
        
        async def run_unified_restore():
            """Run restoration for all selected components"""
            try:
                # Load backup data once
                with open(backup_file, 'r') as f:
                    backup_data = json.load(f)
                
                restoration_results = {
                    "job_id": restore_job_id,
                    "workspace_id": workspace_id,
                    "backup_id": backup_id,
                    "components": {},
                    "summary": {
                        "total_components": len(selected_components),
                        "successful": 0,
                        "failed": 0
                    }
                }
                
                # Dataset ID mapping will be populated by reports restoration
                dataset_id_mapping = {}
                
                # 1. Restore Reports (PBIX files)
                if restore_reports:
                    try:
                        log_info(f"   📋 Restoring reports...")
                        reports_path = os.path.join(backup_folder, "reports")
                        
                        if os.path.exists(reports_path):
                            reports_result = await restore_service.reports_service.restore_reports_pbix(
                                workspace_id, 
                                reports_path
                            )
                            restoration_results["components"]["reports"] = reports_result
                            
                            # Extract dataset ID mapping for later use
                            dataset_id_mapping = reports_result.get("dataset_id_mapping", {})
                            
                            log_info(f"   ✅ Reports: {reports_result.get('imported', 0)} imported")
                            restoration_results["summary"]["successful"] += 1
                        else:
                            log_info(f"   ⚠️  Reports directory not found")
                            restoration_results["components"]["reports"] = {
                                "status": "skipped",
                                "reason": "Reports directory not found"
                            }
                    except Exception as e:
                        log_error(f"Reports restoration failed", error=e)
                        restoration_results["components"]["reports"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        restoration_results["summary"]["failed"] += 1
                
                # 2. Restore Datasets
                if restore_datasets:
                    try:
                        log_info(f"   📊 Restoring datasets...")
                        datasets_result = await restore_service.datasets_service.restore_datasets(
                            workspace_id,
                            backup_data.get('datasets', [])
                        )
                        restoration_results["components"]["datasets"] = datasets_result
                        log_info(f"   ✅ Datasets: {datasets_result.get('status', 'unknown')}")
                        restoration_results["summary"]["successful"] += 1
                    except Exception as e:
                        log_error(f"Datasets restoration failed", error=e)
                        restoration_results["components"]["datasets"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        restoration_results["summary"]["failed"] += 1
                
                # 3. Restore Refresh Schedules (with dataset ID mapping)
                if restore_refresh_schedules:
                    try:
                        log_info(f"   ⏰ Restoring refresh schedules...")
                        schedules_result = await restore_service.refresh_schedules_service.restore_refresh_schedules(
                            workspace_id,
                            backup_data.get('refresh_schedules', []),
                            dataset_id_mapping  # Pass the mapping from reports restoration
                        )
                        restoration_results["components"]["refresh_schedules"] = schedules_result
                        log_info(f"   ✅ Refresh Schedules: {schedules_result.get('restored', 0)} restored")
                        restoration_results["summary"]["successful"] += 1
                    except Exception as e:
                        log_error(f"Refresh schedules restoration failed", error=e)
                        restoration_results["components"]["refresh_schedules"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        restoration_results["summary"]["failed"] += 1
                
                # 4. Restore Dashboards
                if restore_dashboards:
                    try:
                        log_info(f"   📊 Restoring dashboards...")
                        dashboards_result = await restore_service.dashboards_service.restore_dashboards(
                            workspace_id,
                            backup_data.get('dashboards', [])
                        )
                        restoration_results["components"]["dashboards"] = dashboards_result
                        log_info(f"   ✅ Dashboards: {dashboards_result.get('status', 'unknown')}")
                        restoration_results["summary"]["successful"] += 1
                    except Exception as e:
                        log_error(f"Dashboards restoration failed", error=e)
                        restoration_results["components"]["dashboards"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        restoration_results["summary"]["failed"] += 1
                
                # 5. Restore Dataflows
                if restore_dataflows:
                    try:
                        log_info(f"   🌊 Restoring dataflows...")
                        dataflows_result = await restore_service.dataflows_service.restore_dataflows(
                            workspace_id,
                            backup_data.get('dataflows', [])
                        )
                        restoration_results["components"]["dataflows"] = dataflows_result
                        log_info(f"   ✅ Dataflows: {dataflows_result.get('status', 'unknown')}")
                        restoration_results["summary"]["successful"] += 1
                    except Exception as e:
                        log_error(f"Dataflows restoration failed", error=e)
                        restoration_results["components"]["dataflows"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        restoration_results["summary"]["failed"] += 1
                
                # 6. Restore Apps
                if restore_apps:
                    try:
                        log_info(f"   📱 Restoring apps...")
                        apps_result = await restore_service.apps_service.restore_apps(
                            workspace_id,
                            backup_data.get('apps', [])
                        )
                        restoration_results["components"]["apps"] = apps_result
                        log_info(f"   ✅ Apps: {apps_result.get('status', 'unknown')}")
                        restoration_results["summary"]["successful"] += 1
                    except Exception as e:
                        log_error(f"Apps restoration failed", error=e)
                        restoration_results["components"]["apps"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                        restoration_results["summary"]["failed"] += 1
                
                # Store final results
                restoration_results["status"] = "completed"
                restoration_results["timestamp"] = datetime.now().isoformat()
                backup_jobs[restore_job_id] = restoration_results
                
                log_info(f"✅ Unified restoration completed successfully")
                log_info(f"   Successful: {restoration_results['summary']['successful']}")
                log_info(f"   Failed: {restoration_results['summary']['failed']}")
                
            except Exception as e:
                log_error(f"Unified restoration failed", error=e)
                backup_jobs[restore_job_id] = {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        # Start background task
        if background_tasks:
            background_tasks.add_task(run_unified_restore)
        else:
            # If no background_tasks object, create it
            from fastapi import BackgroundTasks as BG
            bg = BG()
            bg.add_task(run_unified_restore)
        
        # Store initial job status
        backup_jobs[restore_job_id] = {
            "status": "in_progress",
            "job_id": restore_job_id,
            "workspace_id": workspace_id,
            "backup_id": backup_id,
            "selected_components": selected_components,
            "timestamp": datetime.now().isoformat(),
            "message": f"Restoring {len(selected_components)} components..."
        }
        
        return {
            "status": "success",
            "job_id": restore_job_id,
            "message": f"Restoration started for: {', '.join(selected_components)}",
            "selected_components": selected_components,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error starting unified restoration", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restore/{backup_id}/guide", tags=["Restore"])
async def get_restoration_guide(backup_id: str):
    """
    Get the restoration guide for a backup.
    Includes step-by-step instructions and metadata.
    """
    try:
        log_info(f"📖 Getting restoration guide for backup {backup_id}")
        
        # Load backup metadata
        backup_file = os.path.join(settings.backup_path, backup_id, f"backup_{backup_id}.json")
        
        if not os.path.exists(backup_file):
            raise HTTPException(status_code=404, detail="Backup not found")
        
        import json
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        return {
            "status": "success",
            "backup_id": backup_id,
            "metadata": backup_data.get("metadata", {}),
            "backup_summary": {
                "reports": backup_data.get("reports", {}).get("count", 0),
                "datasets": backup_data.get("datasets", {}).get("count", 0),
                "dashboards": backup_data.get("dashboards", {}).get("count", 0),
                "refresh_schedules": len(backup_data.get("refresh_schedules", []))
            },
            "restoration_steps": backup_data.get("metadata", {}).get("restoration_steps", []),
            "features_backed_up": backup_data.get("metadata", {}).get("features_backed_up", {}),
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error getting restoration guide", error=e)
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Status Endpoints
# ===========================

@app.get("/api/status", tags=["Status"])
async def get_service_status():
    """Get overall service status"""
    try:
        return {
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "backup_path": settings.backup_path,
            "debug": settings.debug
        }
    except Exception as e:
        log_error("Error getting service status", error=e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs", tags=["Status"])
async def list_jobs():
    """List all backup/restore jobs"""
    try:
        return {
            "total_jobs": len(backup_jobs),
            "jobs": backup_jobs
        }
    except Exception as e:
        log_error("Error listing jobs", error=e)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
