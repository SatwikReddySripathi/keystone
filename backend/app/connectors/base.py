"""
Base connector interface.

Every external tool (ServiceNow, Jira, Salesforce, etc.) implements
these 4 methods. Keystone's engine code ONLY talks to this interface,
never to a specific tool directly.

This means:
- Adding a new tool = one new file implementing these 4 methods
- Swapping simulator for real API = same interface, different implementation
- The preview engine, canary engine, etc. don't change at all
"""
from abc import ABC, abstractmethod


class BaseConnector(ABC):

    @abstractmethod
    def query(self, filters: dict) -> list[dict]:
        """
        Return records matching the filters.
        Example filters: {"state": "open", "priority": {"op": "in", "value": ["P3", "P4"]}}
        Returns: list of record dicts with at minimum a 'sys_id' field.
        """
        ...

    @abstractmethod
    def compute_diffs(self, records: list[dict], changes: dict) -> list[dict]:
        """
        WITHOUT executing anything, compute what would change.
        Returns: list of {sys_id, number, fields: {field: {before, after}}}
        This powers the diff view in the UI.
        """
        ...

    @abstractmethod
    def execute_update(self, sys_ids: list[str], changes: dict) -> list[dict]:
        """
        Actually apply changes to specific records.
        Returns: list of per-record results {sys_id, success, error?, changes_applied}
        """
        ...

    @abstractmethod
    def get_record(self, sys_id: str) -> dict | None:
        """Fetch a single record by ID."""
        ...