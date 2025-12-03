from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class PageModel(BaseModel):
    page_name: str
    display_name: str
    order: int

class Report(BaseModel):
    report_id: str
    report_name: str
    dataset_id: str
    embed_url: str
    web_url: str
    pages: List[PageModel]

class Dataset(BaseModel):
    dataset_id: str
    dataset_name: str
    config_refresh_type: Optional[str] = None

class Dataflow(BaseModel):
    dataflow_id: str
    dataflow_name: str
    description: Optional[str] = None

class Dashboard(BaseModel):
    dashboard_id: str
    dashboard_name: str
    display_order: Optional[int] = None

class App(BaseModel):
    app_id: str
    app_name: str
    workspace_id: str

class RefreshSchedule(BaseModel):
    dataset_id: str
    dataset_name: str
    schedule: Dict[str, Any]

class WorkspaceSettings(BaseModel):
    workspace_id: str
    workspace_name: str
    settings: Dict[str, Any]

class CompleteBackup(BaseModel):
    timestamp: datetime
    workspace_id: str
    reports: List[Dict[str, Any]] = []
    datasets: List[Dict[str, Any]] = []
    dataflows: List[Dict[str, Any]] = []
    dashboards: List[Dict[str, Any]] = []
    apps: List[Dict[str, Any]] = []
    workspace_settings: Dict[str, Any] = {}
    refresh_schedules: List[Dict[str, Any]] = []

class BackupRequest(BaseModel):
    workspace_id: str

class RestoreRequest(BaseModel):
    workspace_id: str
    backup_file: Optional[str] = None

class BackupResponse(BaseModel):
    success: bool
    message: str
    backup_id: Optional[str] = None
    timestamp: datetime

class RestoreResponse(BaseModel):
    success: bool
    message: str
    restored_items: Dict[str, int]
    timestamp: datetime
