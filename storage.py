from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
from pathlib import Path

class BackupStorageService:
    """Service for managing backup data in memory and file system"""
    
    def __init__(self, backup_path: str = "./backups"):
        self.backup_path = backup_path
        self._ensure_backup_directory()
        self.backup_data = self._initialize_backup_data()
    
    def _ensure_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        Path(self.backup_path).mkdir(parents=True, exist_ok=True)
    
    def _initialize_backup_data(self) -> Dict[str, Any]:
        """Initialize empty backup data structure"""
        return {
            "reports": [],
            "datasets": [],
            "dataflows": [],
            "dashboards": [],
            "apps": [],
            "workspace_settings": {},
            "refresh_schedules": [],
            "timestamp": None,
            "workspace_id": None
        }
    
    def store_reports(self, reports: List[Dict[str, Any]]):
        """Store reports data"""
        self.backup_data["reports"] = reports
    
    def store_datasets(self, datasets: List[Dict[str, Any]]):
        """Store datasets data"""
        self.backup_data["datasets"] = datasets
    
    def store_dataflows(self, dataflows: List[Dict[str, Any]]):
        """Store dataflows data"""
        self.backup_data["dataflows"] = dataflows
    
    def store_dashboards(self, dashboards: List[Dict[str, Any]]):
        """Store dashboards data"""
        self.backup_data["dashboards"] = dashboards
    
    def store_apps(self, apps: List[Dict[str, Any]]):
        """Store apps data"""
        self.backup_data["apps"] = apps
    
    def store_workspace_settings(self, settings: Dict[str, Any]):
        """Store workspace settings"""
        self.backup_data["workspace_settings"] = settings
    
    def store_refresh_schedules(self, schedules: List[Dict[str, Any]]):
        """Store refresh schedules"""
        self.backup_data["refresh_schedules"] = schedules
    
    def set_metadata(self, workspace_id: str, timestamp: datetime):
        """Set backup metadata"""
        self.backup_data["workspace_id"] = workspace_id
        self.backup_data["timestamp"] = timestamp.isoformat()
    
    def get_backup_data(self) -> Dict[str, Any]:
        """Get all backup data"""
        return self.backup_data.copy()
    
    def clear_backup_data(self):
        """Clear all backup data"""
        self.backup_data = self._initialize_backup_data()
    
    def save_backup_to_file(self, backup_id: str) -> str:
        """Save backup data to file and return the file path"""
        backup_filename = f"backup_{backup_id}.json"
        backup_filepath = os.path.join(self.backup_path, backup_filename)
        
        with open(backup_filepath, 'w') as f:
            json.dump(self.backup_data, f, indent=2, default=str)
        
        return backup_filepath
    
    def load_backup_from_file(self, backup_id: str) -> Dict[str, Any]:
        """Load backup data from file"""
        backup_filename = f"backup_{backup_id}.json"
        backup_filepath = os.path.join(self.backup_path, backup_filename)
        
        if not os.path.exists(backup_filepath):
            raise FileNotFoundError(f"Backup file not found: {backup_filepath}")
        
        with open(backup_filepath, 'r') as f:
            return json.load(f)
    
    def list_backups(self) -> List[str]:
        """List all available backups - supports both old and new format"""
        backups = []
        
        try:
            items = os.listdir(self.backup_path)
            
            # Old format: backup_*.json files at root level
            backup_files = [f for f in items if f.startswith("backup_") and f.endswith(".json")]
            for f in backup_files:
                backup_id = f.replace("backup_", "").replace(".json", "")
                backups.append(backup_id)
            
            # New format: backup folders with meaningful names
            for item in items:
                item_path = os.path.join(self.backup_path, item)
                # Check if it's a directory and contains a backup_*.json file
                if os.path.isdir(item_path):
                    # Check for backup metadata file inside
                    backup_file = os.path.join(item_path, f"backup_{item}.json")
                    if os.path.exists(backup_file):
                        backups.append(item)
        
        except Exception as e:
            print(f"Error listing backups: {e}")
            return []
        
        return backups
    
    def create_backup_folder(self, backup_id: str, subfolder: str = None) -> str:
        """Create a folder for backup files (e.g., for PBIX exports)"""
        if subfolder:
            backup_folder = os.path.join(self.backup_path, backup_id, subfolder)
        else:
            backup_folder = os.path.join(self.backup_path, backup_id)
        
        Path(backup_folder).mkdir(parents=True, exist_ok=True)
        return backup_folder
    
    def save_backup(self, backup_data: Dict[str, Any], backup_id: str) -> str:
        """Save backup data to JSON file"""
        backup_filename = f"backup_{backup_id}.json"
        backup_filepath = os.path.join(self.backup_path, backup_id, backup_filename)
        
        # Create backup folder
        Path(backup_filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(backup_filepath, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        return backup_filepath
