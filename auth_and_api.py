import aiohttp
import asyncio
from typing import Dict, Any, Optional
from logger import log_info, log_error, log_debug
from config import settings
import urllib.parse
import os
from pathlib import Path

class PowerBIAuthService:
    """Service for authenticating with Power BI API"""
    
    def __init__(self, client_id: str = None, client_secret: str = None, tenant_id: str = None):
        self.client_id = client_id or settings.powerbi_client_id
        self.client_secret = client_secret or settings.powerbi_client_secret
        self.tenant_id = tenant_id or settings.powerbi_tenant_id
        self.resource = settings.resource
        self.authority_url = f"{settings.authority_url}/{self.tenant_id}/oauth2/token"
        self._token_cache: Optional[str] = None
    
    async def get_access_token(self) -> str:
        """Get access token for Power BI API"""
        try:
            if self._token_cache:
                return self._token_cache
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'resource': self.resource
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.authority_url,
                    data=urllib.parse.urlencode(data),
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to obtain access token: {error_text}")
                    
                    response_data = await response.json()
                    self._token_cache = response_data['access_token']
                    
                    log_info("Access token obtained successfully")
                    return self._token_cache
        
        except Exception as e:
            log_error("Error obtaining access token", error=e)
            raise

class PowerBIApiClient:
    """Client for interacting with Power BI REST API"""
    
    def __init__(self, auth_service: PowerBIAuthService, base_url: str = None):
        self.auth_service = auth_service
        self.base_url = base_url or settings.api_base_url
    
    async def _fetch_with_auth(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Helper method to make authenticated API requests"""
        try:
            token = await self.auth_service.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=data,
                    params=params
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"Error fetching {endpoint}: {response.status} - {error_text}")
                    
                    return await response.json()
        
        except Exception as e:
            log_error(f"Error in API call to {endpoint}", error=e)
            raise
    
    async def get_reports(self, workspace_id: str) -> Dict[str, Any]:
        """Get all reports from a workspace"""
        return await self._fetch_with_auth(f"/groups/{workspace_id}/reports")
    
    async def get_datasets(self, workspace_id: str) -> Dict[str, Any]:
        """Get all datasets from a workspace"""
        return await self._fetch_with_auth(f"/groups/{workspace_id}/datasets")
    
    async def get_dataflows(self, workspace_id: str) -> Dict[str, Any]:
        """Get all dataflows from a workspace"""
        return await self._fetch_with_auth(f"/groups/{workspace_id}/dataflows")
    
    async def get_dashboards(self, workspace_id: str) -> Dict[str, Any]:
        """Get all dashboards from a workspace"""
        return await self._fetch_with_auth(f"/groups/{workspace_id}/dashboards")
    
    async def get_apps(self) -> Dict[str, Any]:
        """Get all apps"""
        return await self._fetch_with_auth("/apps")
    
    async def get_workspace_settings(self, workspace_id: str) -> Dict[str, Any]:
        """Get workspace settings"""
        return await self._fetch_with_auth(f"/groups/{workspace_id}")
    
    async def get_gateways(self) -> Dict[str, Any]:
        """Get all gateways"""
        return await self._fetch_with_auth("/gateways")
    
    async def get_refresh_schedule(self, workspace_id: str, dataset_id: str) -> Dict[str, Any]:
        """Get refresh schedule for a dataset"""
        return await self._fetch_with_auth(f"/groups/{workspace_id}/datasets/{dataset_id}/refreshSchedule")
    
    async def update_refresh_schedule(
        self, 
        workspace_id: str, 
        dataset_id: str, 
        schedule_config: Dict[str, Any]
    ) -> bool:
        """
        Update the refresh schedule for a dataset - RESTORES EXACT BACKUP DATA ONLY
        
        Args:
            workspace_id: Target workspace ID
            dataset_id: Target dataset ID
            schedule_config: Dictionary with schedule details from backup
                {
                    "days": ["Sunday", "Monday", ...],
                    "times": ["01:00", "13:00"],
                    "enabled": true,
                    "localTimeZoneId": "UTC",
                    "notifyOption": "MailOnFailure"
                }
        
        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"[REFRESH_SCHEDULE] Restoring refresh schedule for dataset {dataset_id}")
            
            # Extract schedule data exactly as backed up
            days = schedule_config.get('days', [])
            times = schedule_config.get('times', [])
            enabled = schedule_config.get('enabled', False)
            timezone = schedule_config.get('localTimeZoneId', 'UTC')
            notify = schedule_config.get('notifyOption', 'MailOnFailure')
            
            log_info(f"   [BACKUP_DATA] Backup data: enabled={enabled}, days={len(days)}, times={len(times)}")
            
            # Skip if schedule is disabled
            if not enabled:
                log_info(f"   [SKIPPED] Schedule is disabled in backup - skipping restoration")
                return True
            
            # If no schedule in backup (empty days and times), skip restoration
            if not days and not times:
                log_info(f"   [SKIPPED] No schedule in backup (empty days/times) - skipping restoration")
                return True
            
            # Ensure both days AND times exist for enabled refresh
            if not days or not times:
                log_info(f"   [INVALID] Schedule marked enabled but missing days/times - skipping restoration")
                return True
            
            # Build the payload for enabled schedule
            # At this point, we know: enabled=true, days exist, times exist
            payload = {
                "days": days,
                "times": times,
                "enabled": True,
                "localTimeZoneId": timezone,
                "notifyOption": notify
            }
            
            log_info(f"   [RESTORING] Restoring enabled schedule: days={len(days)}, times={len(times)}")
            
            # Call the update endpoint
            endpoint = f"/groups/{workspace_id}/datasets/{dataset_id}/refreshSchedule"
            
            token = await self.auth_service.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.base_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=headers, json=payload) as response:
                    log_info(f"   [RESPONSE] Response status: {response.status}")
                    
                    if response.status in [200, 201, 202]:
                        log_info(f"   [SUCCESS] Refresh schedule restored successfully")
                        return True
                    else:
                        error_text = await response.text()
                        log_error(f"   [ERROR] Failed to restore refresh schedule: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            log_error(f"Error restoring refresh schedule", error=e)
            return False
    
    async def export_report(self, workspace_id: str, report_id: str, file_path: str) -> bool:
        """
        Export a report as PBIX file
        Returns True if successful, False otherwise
        """
        try:
            token = await self.auth_service.get_access_token()
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            url = f"{self.base_url}/groups/{workspace_id}/reports/{report_id}/Export"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        # Write the PBIX file to disk
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())
                        log_info(f"[SUCCESS] Exported report to: {file_path}")
                        return True
                    else:
                        error_text = await response.text()
                        log_error(f"Failed to export report: {response.status} - {error_text}")
                        return False
        except Exception as e:
            log_error(f"Error exporting report", error=e)
            return False
    
    async def import_pbix(self, workspace_id: str, pbix_file_path: str, report_name: str = None) -> bool:
        """
        Import a PBIX file to a workspace
        
        Args:
            workspace_id: Target workspace ID
            pbix_file_path: Path to PBIX file
            report_name: Name for the imported report (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(pbix_file_path):
                log_error(f"PBIX file not found: {pbix_file_path}")
                return False
            
            report_name = report_name or Path(pbix_file_path).stem
            
            # Sanitize report name - Power BI has strict requirements
            report_name = report_name.replace(' ', '_').replace('/', '_').replace('\\', '_').replace('"', '').replace("'", "")
            if not report_name:
                report_name = "ImportedReport"
            
            # If report name starts with digit (like "3report"), add prefix
            if report_name and report_name[0].isdigit():
                report_name = f"Report_{report_name}"
                log_info(f"  Renamed to avoid leading digit: {report_name}")
            
            token = await self.auth_service.get_access_token()
            
            # Validate token
            if not token or len(token) < 100:
                log_error(f"Invalid token received: {token[:20] if token else 'None'}")
                return False
            
            log_info(f"  DEBUG: Token obtained (length: {len(token)})")
            
            # Read PBIX file and upload
            with open(pbix_file_path, 'rb') as f:
                pbix_data = f.read()
            
            log_info(f"  Uploading PBIX: {report_name}")
            log_info(f"  File size: {len(pbix_data) / 1024 / 1024:.2f} MB")
            
            # Use the filename (without extension) as the dataset display name
            # This preserves the original report name from backup
            filename_only = Path(pbix_file_path).stem
            dataset_display_name = filename_only
            
            log_info(f"  Dataset name from filename: {dataset_display_name}")
            
            # Try to get existing datasets to avoid name conflicts
            try:
                existing_datasets = await self.get_datasets(workspace_id)
                dataset_names = [d['name'] for d in existing_datasets.get('value', [])]
                
                # If the name already exists, increment the number
                counter = 1
                original_name = dataset_display_name
                while dataset_display_name in dataset_names:
                    counter += 1
                    dataset_display_name = f"{original_name}_{counter}"
                    log_info(f"  Incrementing dataset name to avoid duplicates: {dataset_display_name}")
            except:
                # If we can't check, just use the original name
                pass
            
            # CRITICAL: skipReport=true is the KEY parameter that makes this work!
            url = f"{self.base_url}/groups/{workspace_id}/imports?datasetDisplayName={dataset_display_name}"
            
            log_info(f"  API URL: {url}")
            
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            # FormData with generic filename - this is the working approach
            data = aiohttp.FormData()
            data.add_field('file', pbix_data, filename='report.pbix', content_type='application/octet-stream')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    response_text = await response.text()
                    log_info(f"  Response status: {response.status}")
                    log_info(f"  Response headers: {dict(response.headers)}")
                    log_info(f"  Response body: {response_text[:500]}")
                    
                    if response.status in [200, 201, 202]:
                        log_info(f"SUCCESS: PBIX imported: {report_name} -> Dataset: {dataset_display_name}")
                        return True
                    else:
                        log_error(f"Failed to import PBIX: {response.status} - {response_text}")
                        return False
        except Exception as e:
            log_error(f"Error importing PBIX", error=e)
            import traceback
            log_error(f"  Traceback: {traceback.format_exc()}")
            return False
    
    async def get_workspaces(self) -> list:
        """Get all workspaces the service principal has access to"""
        try:
            log_debug("Calling /groups endpoint to fetch workspaces")
            response = await self._fetch_with_auth("/groups")
            
            log_debug(f"Raw response from /groups: {response}")
            
            # Extract workspace list and format it nicely
            workspaces = []
            if isinstance(response, dict) and 'value' in response:
                log_debug(f"Response contains 'value' key with {len(response['value'])} items")
                for workspace in response['value']:
                    workspace_obj = {
                        'id': workspace.get('id'),
                        'name': workspace.get('name'),
                        'type': workspace.get('type'),
                        'state': workspace.get('state'),
                        'is_ondemdpremium_enabled': workspace.get('isOnDemandPremiumEnabled'),
                        'is_premium_capacity': workspace.get('capacityId') is not None
                    }
                    log_debug(f"Adding workspace: {workspace_obj['name']} ({workspace_obj['id']})")
                    workspaces.append(workspace_obj)
            else:
                log_debug(f"Response structure: {type(response)}, keys: {response.keys() if isinstance(response, dict) else 'N/A'}")
            
            log_info(f"Found {len(workspaces)} workspaces")
            return workspaces
        except Exception as e:
            log_error("Error fetching workspaces", error=e)
            raise
    
    async def get_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """Get details about a specific workspace"""
        try:
            response = await self._fetch_with_auth(f"/groups/{workspace_id}")
            
            if isinstance(response, dict):
                return {
                    'id': response.get('id'),
                    'name': response.get('name'),
                    'type': response.get('type'),
                    'state': response.get('state'),
                    'is_ondemdpremium_enabled': response.get('isOnDemandPremiumEnabled'),
                    'is_premium_capacity': response.get('capacityId') is not None,
                    'capacity_id': response.get('capacityId')
                }
            
            return response
        except Exception as e:
            log_error(f"Error fetching workspace {workspace_id}", error=e)
            raise
