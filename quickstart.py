#!/usr/bin/env python3
"""
Power BI Backup Service - Python Implementation
This script demonstrates how to use the backup and restore services
"""

import asyncio
from auth_and_api import PowerBIAuthService, PowerBIApiClient
from backup_service import CompletePowerBIBackupService
from restore_service import CompletePowerBIRestoreService
from storage import BackupStorageService
from config import settings

async def main():
    """Example usage of the backup and restore services"""
    
    print("=" * 60)
    print("Power BI Backup Service - Quick Start")
    print("=" * 60)
    
    try:
        # Initialize services
        print("\n1. Initializing services...")
        auth_service = PowerBIAuthService()
        api_client = PowerBIApiClient(auth_service)
        storage_service = BackupStorageService(settings.backup_path)
        backup_service = CompletePowerBIBackupService(api_client, storage_service)
        restore_service = CompletePowerBIRestoreService(api_client, storage_service)
        
        # Example workspace ID - replace with your actual workspace ID
        workspace_id = "your-workspace-id"
        
        # Backup all components
        print(f"\n2. Starting backup for workspace: {workspace_id}")
        backup_data = await backup_service.backup_all_components(workspace_id)
        
        print(f"\n   Backup Summary:")
        print(f"   - Reports: {len(backup_data['reports'])}")
        print(f"   - Datasets: {len(backup_data['datasets'])}")
        print(f"   - Dataflows: {len(backup_data['dataflows'])}")
        print(f"   - Dashboards: {len(backup_data['dashboards'])}")
        print(f"   - Apps: {len(backup_data['apps'])}")
        print(f"   - Refresh Schedules: {len(backup_data['refresh_schedules'])}")
        
        # To restore, you would call:
        # print(f"\n3. Restoring components to workspace: {workspace_id}")
        # restored_items = await restore_service.restore_all_components(workspace_id, backup_data)
        # print(f"   Restore completed: {restored_items}")
        
        print("\n" + "=" * 60)
        print("Backup completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("\nPlease ensure:")
        print("1. You have a .env file with valid Power BI credentials")
        print("2. All required packages are installed: pip install -r requirements.txt")
        print("3. Your workspace_id is correct")

if __name__ == "__main__":
    asyncio.run(main())
