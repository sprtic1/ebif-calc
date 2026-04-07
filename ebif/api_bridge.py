"""Archicad API Bridge — connects to Tapir Add-On via HTTP/JSON.

Provides methods to discover elements, fetch properties, and resolve
zone/room assignments. All Archicad communication goes through this module.
"""

import json
import logging
import requests
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Common built-in property GUIDs (Archicad 29)
P_ELEMENT_ID = "7e221f33-829b-4fbc-a670-e74dabce6289"
P_LIBRARY_PART = "3f30d753-d86e-4ca3-9a0e-a11e73e9fdcb"


class ArchicadConnection:
    """HTTP connection to Archicad via Tapir Add-On."""

    def __init__(self, port: int, timeout: int = 30):
        self.base_url = f"http://localhost:{port}"
        self.timeout = timeout
        self._verify_connection()

    def _verify_connection(self):
        """Verify Archicad is reachable."""
        try:
            resp = self._call("API.GetProductInfo")
            ver = resp.get("version", "?")
            build = resp.get("buildNumber", "?")
            logger.info("Connected to Archicad %s (build %s) on %s", ver, build, self.base_url)
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Archicad at {self.base_url}: {e}") from e

    def _call(self, command: str, parameters: dict | None = None) -> dict:
        """Send a JSON command to Archicad and return the result."""
        payload: dict[str, Any] = {"command": command}
        if parameters:
            payload["parameters"] = parameters
        resp = requests.post(self.base_url, json=payload, timeout=self.timeout)
        data = resp.json()
        if not data.get("succeeded", True):
            err = data.get("error", {})
            raise RuntimeError(f"Archicad command '{command}' failed: {err.get('message', err)}")
        return data.get("result", data)

    # ------------------------------------------------------------------
    # Element queries
    # ------------------------------------------------------------------

    def get_elements_by_type(self, element_type: str) -> list[dict]:
        """Return all element GUIDs of a given type."""
        result = self._call("API.GetElementsByType", {"elementType": element_type})
        return result.get("elements", [])

    def get_all_elements(self, element_types: list[str]) -> list[dict]:
        """Return all element GUIDs across multiple types."""
        all_elems = []
        for et in element_types:
            elems = self.get_elements_by_type(et)
            # Tag each element with its type for downstream use
            for e in elems:
                e["_type"] = et
            all_elems.extend(elems)
        return all_elems

    # ------------------------------------------------------------------
    # Property queries
    # ------------------------------------------------------------------

    def get_property_ids(self, properties: list[dict]) -> list[dict]:
        """Resolve property names to GUIDs.

        Args:
            properties: List of dicts, each with 'type' and either
                'nonLocalizedName' (BuiltIn) or 'localizedName' (UserDefined).
        """
        return self._call("API.GetPropertyIds", {"properties": properties}).get("properties", [])

    def get_property_values(self, elements: list[dict], properties: list[dict]) -> list[dict]:
        """Fetch property values for elements.

        Args:
            elements: List of {"elementId": {"guid": "..."}}
            properties: List of {"propertyId": {"guid": "..."}}

        Returns:
            List of {"propertyValues": [{"propertyValue": {"value": ...}}, ...]}
        """
        # Strip internal fields (like _type) that Archicad API won't accept
        clean_elements = [{"elementId": e["elementId"]} for e in elements]
        result = self._call("API.GetPropertyValuesOfElements", {
            "elements": clean_elements,
            "properties": properties,
        })
        return result.get("propertyValuesForElements", [])

    def resolve_user_property(self, group_name: str, property_name: str) -> str | None:
        """Resolve a user-defined property to its GUID.

        Returns the GUID string or None if not found.
        """
        try:
            result = self._call("API.GetPropertyIds", {
                "properties": [{
                    "type": "UserDefined",
                    "localizedName": [group_name, property_name],
                }]
            })
            props = result.get("properties", [])
            if props and "propertyId" in props[0]:
                return props[0]["propertyId"]["guid"]
        except RuntimeError:
            logger.warning("Property not found: %s / %s", group_name, property_name)
        return None

    # ------------------------------------------------------------------
    # Convenience: batch property fetch
    # ------------------------------------------------------------------

    def fetch_element_properties(
        self,
        elements: list[dict],
        property_guids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch multiple properties for a list of elements.

        Returns a list of dicts, one per element, mapping property GUID -> value.
        """
        if not elements or not property_guids:
            return []

        prop_ids = [{"propertyId": {"guid": g}} for g in property_guids]
        raw = self.get_property_values(elements, prop_ids)

        results = []
        for i, elem in enumerate(elements):
            row = {"_guid": elem["elementId"]["guid"]}
            if elem.get("_type"):
                row["_type"] = elem["_type"]
            if i < len(raw):
                pvs = raw[i].get("propertyValues", [])
                for j, guid in enumerate(property_guids):
                    if j < len(pvs):
                        pv = pvs[j].get("propertyValue", {})
                        val = pv.get("value")
                        # Handle enum values
                        if isinstance(val, dict):
                            val = val.get("nonLocalizedValue", val.get("displayValue", str(val)))
                        row[guid] = val
                    else:
                        row[guid] = None
            results.append(row)
        return results

    # ------------------------------------------------------------------
    # Zone/room queries
    # ------------------------------------------------------------------

    def get_zones(self) -> list[dict]:
        """Return all zone elements with their names and numbers."""
        return self.get_elements_by_type("Zone")


def load_connection(settings: dict) -> ArchicadConnection:
    """Create an ArchicadConnection from settings.json config."""
    port = settings.get("archicad_port", 19723)
    return ArchicadConnection(port=port)
