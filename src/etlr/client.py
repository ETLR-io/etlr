"""API client for ETLR workflows."""

import os
from typing import Any, Optional

import requests

from . import API_BASE_URL


class APIError(Exception):
    """Exception raised for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class WorkflowsClient:
    """Client for the ETLR Workflows API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the workflows client.

        Args:
            api_key: API key for authentication. If not provided, reads from ETLR_API_KEY env var.
            base_url: Base URL for the API. Defaults to production URL.
        """
        self.api_key = api_key or os.getenv("ETLR_API_KEY")
        self.base_url = base_url or API_BASE_URL

        if not self.api_key:
            raise APIError("API key not provided. Set ETLR_API_KEY environment variable or pass api_key parameter.")

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a request to the API.

        Args:
            payload: JSON payload to send

        Returns:
            Response data

        Raises:
            APIError: If the request fails
        """
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)

            # Try to parse JSON response
            try:
                data = response.json()
            except ValueError:
                data = {"text": response.text}

            # Check for errors
            if not response.ok:
                error_msg = data.get("error", f"HTTP {response.status_code}")
                raise APIError(error_msg, status_code=response.status_code, details=data.get("details"))

            return data

        except requests.RequestException as e:
            raise APIError(f"Request failed: {str(e)}") from e

    def list_workflows(self) -> dict[str, Any]:
        """List all workflows.

        Returns:
            Dictionary with 'workflows' key containing list of workflows
        """
        return self._request({"action": "list"})

    def get_workflow(
        self, workflow_id: Optional[str] = None, name: Optional[str] = None, stage: Optional[str] = None
    ) -> dict[str, Any]:
        """Get workflow details.

        Args:
            workflow_id: Workflow UUID (if provided, name/stage are ignored)
            name: Workflow name (requires stage)
            stage: Workflow stage (requires name)

        Returns:
            Workflow details including workflow_yaml
        """
        if workflow_id:
            payload = {"action": "get", "workflow_id": workflow_id}
        elif name and stage:
            payload = {"action": "get", "name": name, "stage": stage}
        else:
            raise APIError("Must provide either workflow_id or both name and stage")

        return self._request(payload)

    def upsert_workflow(
        self, yaml: str, env: Optional[dict[str, str]] = None, stage: Optional[str] = None
    ) -> dict[str, Any]:
        """Create or update a workflow.

        Args:
            yaml: Workflow YAML content
            env: Optional environment variables dictionary
            stage: Optional stage override (overrides stage in YAML)

        Returns:
            Response with workflow details and created flag
        """
        payload: dict[str, Any] = {
            "action": "upsert",
            "workflow_yaml": yaml,
        }

        if env:
            payload["env"] = env

        if stage:
            payload["stage"] = stage

        return self._request(payload)

    def delete_workflow(
        self, workflow_id: Optional[str] = None, name: Optional[str] = None, stage: Optional[str] = None
    ) -> dict[str, Any]:
        """Delete a workflow.

        Args:
            workflow_id: Workflow UUID (if provided, name/stage are ignored)
            name: Workflow name (requires stage)
            stage: Workflow stage (requires name)

        Returns:
            Deletion confirmation
        """
        if workflow_id:
            payload = {"action": "delete", "workflow_id": workflow_id}
        elif name and stage:
            payload = {"action": "delete", "name": name, "stage": stage}
        else:
            raise APIError("Must provide either workflow_id or both name and stage")

        return self._request(payload)

    def deploy_workflow(
        self, workflow_id: Optional[str] = None, name: Optional[str] = None, stage: Optional[str] = None
    ) -> dict[str, Any]:
        """Deploy (start) a workflow.

        Args:
            workflow_id: Workflow UUID (if provided, name/stage are ignored)
            name: Workflow name (requires stage)
            stage: Workflow stage (requires name)

        Returns:
            Deployment response
        """
        if workflow_id:
            payload = {"action": "deploy", "workflow_id": workflow_id}
        elif name and stage:
            payload = {"action": "deploy", "name": name, "stage": stage}
        else:
            raise APIError("Must provide either workflow_id or both name and stage")

        return self._request(payload)

    def stop_workflow(
        self, workflow_id: Optional[str] = None, name: Optional[str] = None, stage: Optional[str] = None
    ) -> dict[str, Any]:
        """Stop a running workflow.

        Args:
            workflow_id: Workflow UUID (if provided, name/stage are ignored)
            name: Workflow name (requires stage)
            stage: Workflow stage (requires name)

        Returns:
            Stop confirmation
        """
        if workflow_id:
            payload = {"action": "stop", "workflow_id": workflow_id}
        elif name and stage:
            payload = {"action": "stop", "name": name, "stage": stage}
        else:
            raise APIError("Must provide either workflow_id or both name and stage")

        return self._request(payload)

    def get_status(
        self, workflow_id: Optional[str] = None, name: Optional[str] = None, stage: Optional[str] = None
    ) -> dict[str, Any]:
        """Get workflow deployment status.

        Args:
            workflow_id: Workflow UUID (if provided, name/stage are ignored)
            name: Workflow name (requires stage)
            stage: Workflow stage (requires name)

        Returns:
            Status information including runtime_health
        """
        if workflow_id:
            payload = {"action": "status", "workflow_id": workflow_id}
        elif name and stage:
            payload = {"action": "status", "name": name, "stage": stage}
        else:
            raise APIError("Must provide either workflow_id or both name and stage")

        return self._request(payload)

    def list_versions(self, workflow_id: str) -> dict[str, Any]:
        """List all versions of a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            List of workflow versions
        """
        payload = {"action": "list_versions", "workflow_id": workflow_id}
        return self._request(payload)

    def get_version(self, workflow_id: str, version: int) -> dict[str, Any]:
        """Get a specific version of a workflow.

        Args:
            workflow_id: Workflow UUID
            version: Version number

        Returns:
            Workflow version details including workflow_yaml
        """
        payload = {"action": "get_version", "workflow_id": workflow_id, "version": version}
        return self._request(payload)

    def restore_version(self, workflow_id: str, version: int) -> dict[str, Any]:
        """Restore a workflow to a specific version.

        Args:
            workflow_id: Workflow UUID
            version: Version number to restore

        Returns:
            Restored workflow details
        """
        payload = {"action": "restore_version", "workflow_id": workflow_id, "version": version}
        return self._request(payload)
