"""ArchiCAD JSON API client — all communication batched, never per-wall loops.

Uses the built-in ArchiCAD JSON API + Tapir Add-On commands.
Exactly 5 API calls for a full fetch, 1 call for writeback.
"""

import logging
import math
import time
from collections import defaultdict

import requests

logger = logging.getLogger(__name__)

M2IN = 39.3701  # meters to inches


class ArchiCADClient:
    # Property GUIDs (ArchiCAD built-in)
    P_WIDTH = "3799b10a-61c5-4566-bf9c-eaa9ce49196e"
    P_HEIGHT = "c4b62357-1289-4d43-a3f6-ab02b192864c"
    P_THICKNESS = "a7b55e43-7c56-4c9e-836d-7a56f1d9d760"
    P_ELEMENT_ID = "7e221f33-829b-4fbc-a670-e74dabce6289"
    P_COMPOSITE = "704e9212-3e21-4790-bae4-cf3de2395481"
    P_STRUCTURE = "98a26d3b-3baf-4019-be7a-09285ffa597c"

    def __init__(self, host: str, port: int, timeout: int = 15,
                 report_group: str = "EID GENERAL PROPERTIES",
                 report_name: str = "RENCO REPORT",
                 element_id_guid: str = ""):
        self.url = f"http://{host}:{port}"
        self.timeout = timeout
        self.report_group = report_group
        self.report_name = report_name
        self.report_guid = ""  # auto-detected on first use
        self.eid_guid = element_id_guid or self.P_ELEMENT_ID

    # --- low-level ---

    def _post(self, cmd: str, params: dict | None = None, retries: int = 4) -> dict:
        payload = {"command": cmd}
        if params:
            payload["parameters"] = params
        for attempt in range(retries):
            r = requests.post(self.url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            d = r.json()
            if d.get("succeeded"):
                return d.get("result", {})
            code = d.get("error", {}).get("code", 0)
            msg = d.get("error", {}).get("message", "")
            if code == 4001 and attempt < retries - 1:
                time.sleep(2)
                continue
            raise RuntimeError(msg)
        raise RuntimeError("ArchiCAD API failed after retries")

    def _tapir(self, name: str, params: dict | None = None) -> dict:
        r = self._post("API.ExecuteAddOnCommand", {
            "addOnCommandId": {"commandNamespace": "TapirCommand", "commandName": name},
            "addOnCommandParameters": params or {},
        })
        return r.get("addOnCommandResponse", {})

    def _detect_report_guid(self) -> str:
        """Auto-detect the RENCO REPORT property GUID from ArchiCAD by group+name."""
        if self.report_guid:
            return self.report_guid
        try:
            result = self._post("API.GetPropertyIds", {
                "properties": [{
                    "type": "UserDefined",
                    "localizedName": [self.report_group, self.report_name],
                }]
            })
            props = result.get("properties", [])
            if props and "propertyId" in props[0]:
                self.report_guid = props[0]["propertyId"]["guid"]
                logger.info("Auto-detected RENCO REPORT GUID: %s (group: %s)",
                            self.report_guid, self.report_group)
                return self.report_guid
            logger.warning("RENCO REPORT property not found under group '%s'", self.report_group)
        except Exception as e:
            logger.warning("Failed to detect RENCO REPORT GUID: %s", e)
        return ""

    def get_report_guid(self) -> str:
        """Get the RENCO REPORT GUID, auto-detecting if needed."""
        if not self.report_guid:
            self._detect_report_guid()
        return self.report_guid

    def is_alive(self) -> bool:
        try:
            r = requests.post(self.url, json={"command": "API.IsAlive"}, timeout=5)
            return r.json().get("succeeded", False)
        except Exception:
            return False

    # --- batched fetch (5 calls) ---

    def get_all_walls_batched(self) -> list[dict]:
        """Fetch ALL wall data in exactly 5 API calls. Returns list of wall dicts."""
        # Call 1: all wall GUIDs
        elems = self._post("API.GetElementsByType", {"elementType": "Wall"}).get("elements", [])
        if not elems:
            return []
        n = len(elems)
        logger.info("Call 1/5: %d wall elements", n)

        # Call 2: geometry details (Tapir)
        details = self._tapir("GetDetailsOfElements", {"elements": elems}).get("detailsOfElements", [])
        logger.info("Call 2/5: geometry details for %d walls", len(details))

        # Call 3: properties (7 props × n walls, single call)
        props = [
            {"propertyId": {"guid": self.P_WIDTH}},
            {"propertyId": {"guid": self.P_HEIGHT}},
            {"propertyId": {"guid": self.P_THICKNESS}},
            {"propertyId": {"guid": self.P_ELEMENT_ID}},
            {"propertyId": {"guid": self.P_COMPOSITE}},
            {"propertyId": {"guid": self.P_STRUCTURE}},
        ]
        pv_all = self._post("API.GetPropertyValuesOfElements", {
            "elements": elems, "properties": props,
        }).get("propertyValuesForElements", [])
        logger.info("Call 3/5: properties for %d walls", len(pv_all))

        # Call 4: stories
        stories_raw = self._tapir("GetStories").get("stories", [])
        story_map = {s["index"]: s["name"] for s in stories_raw}
        logger.info("Call 4/5: %d stories", len(story_map))

        # Call 5: doors + windows (2 sub-calls, counted as 1 logical call)
        openings = self._fetch_openings()
        logger.info("Call 5/5: openings mapped to walls")

        # Assemble
        walls = []
        for i, el in enumerate(elems):
            guid = el["elementId"]["guid"]
            det = details[i] if i < len(details) else {}
            dd = det.get("details", {})
            fi = det.get("floorIndex", 0)

            pv = pv_all[i]["propertyValues"] if i < len(pv_all) else []

            def _v(idx):
                if idx < len(pv) and "propertyValue" in pv[idx]:
                    return pv[idx]["propertyValue"].get("value")
                return None

            # Length properties come as meters (float) from built-in API
            width_m = _v(0) or 0
            height_m = _v(1) or 0
            thickness_m = _v(2) or 0
            eid = str(_v(3) or "")
            composite = _v(4)  # None if Basic
            structure = str(_v(5) or "Basic")

            walls.append({
                "guid": guid,
                "element_id": eid,
                "beg": dd.get("begCoordinate", {}),
                "end": dd.get("endCoordinate", {}),
                "arc_angle": dd.get("arcAngle", 0.0) or 0.0,
                "floor_index": int(fi),
                "story_name": story_map.get(int(fi), f"Floor {int(fi)}"),
                "height_m": dd.get("height", 0) or 0,
                "width_m": width_m if isinstance(width_m, (int, float)) else 0,
                "height_prop_m": height_m if isinstance(height_m, (int, float)) else 0,
                "thickness_m": thickness_m if isinstance(thickness_m, (int, float)) else 0,
                "composite_name": composite,
                "structure_type": structure,
                "openings": openings.get(guid.upper(), []),
            })

        logger.info("Assembled %d wall records", len(walls))
        return walls

    def _fetch_openings(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = defaultdict(list)
        for etype in ("Door", "Window"):
            try:
                elems = self._post("API.GetElementsByType", {"elementType": etype}).get("elements", [])
                if not elems:
                    continue
                dets = self._tapir("GetDetailsOfElements", {"elements": elems}).get("detailsOfElements", [])
                pvs = self._post("API.GetPropertyValuesOfElements", {
                    "elements": elems,
                    "properties": [
                        {"propertyId": {"guid": self.P_WIDTH}},
                        {"propertyId": {"guid": self.P_HEIGHT}},
                    ],
                }).get("propertyValuesForElements", [])

                for j, el in enumerate(elems):
                    det = dets[j] if j < len(dets) else {}
                    owner = det.get("details", {}).get("ownerElementId", {}).get("guid", "")
                    if not owner:
                        continue
                    pv = pvs[j]["propertyValues"] if j < len(pvs) else []
                    w = pv[0]["propertyValue"]["value"] if len(pv) > 0 and "propertyValue" in pv[0] else 0
                    h = pv[1]["propertyValue"]["value"] if len(pv) > 1 and "propertyValue" in pv[1] else 0
                    result[owner.upper()].append({
                        "type": etype.lower(),
                        "width_m": w if isinstance(w, (int, float)) else 0,
                        "height_m": h if isinstance(h, (int, float)) else 0,
                    })
                logger.info("  %d %ss fetched", len(elems), etype.lower())
            except Exception as e:
                logger.warning("Failed to fetch %ss: %s", etype.lower(), e)
        return dict(result)

    # --- batched writeback (1 call) ---

    def set_properties_batched(self, entries: list[dict]) -> int:
        """Set property values in one batch. Returns success count."""
        if not entries:
            return 0
        try:
            r = self._post("API.SetPropertyValuesOfElements", {"elementPropertyValues": entries})
            return sum(1 for x in r.get("executionResults", []) if x.get("success"))
        except Exception as e:
            logger.error("Writeback failed: %s", e)
            return 0

    def clear_reports(self, guids: list[str]) -> int:
        """Clear RENCO REPORT on all given GUIDs in one batch."""
        rpt_guid = self.get_report_guid()
        if not rpt_guid or not guids:
            return 0
        entries = [
            {"elementId": {"guid": g}, "propertyId": {"guid": rpt_guid},
             "propertyValue": {"type": "string", "status": "normal", "value": ""}}
            for g in guids
        ]
        return self.set_properties_batched(entries)

    def strip_x_suffixes(self, guids: list[str]) -> int:
        """Read current Element IDs, strip trailing X, write back in one batch."""
        if not guids:
            return 0
        elems = [{"elementId": {"guid": g}} for g in guids]
        try:
            pvs = self._post("API.GetPropertyValuesOfElements", {
                "elements": elems,
                "properties": [{"propertyId": {"guid": self.eid_guid}}],
            }).get("propertyValuesForElements", [])
        except Exception:
            return 0

        import re
        entries = []
        for i, g in enumerate(guids):
            cur = ""
            if i < len(pvs):
                pv = pvs[i].get("propertyValues", [])
                if pv and "propertyValue" in pv[0]:
                    cur = str(pv[0]["propertyValue"].get("value", ""))
            clean = re.sub(r"X+$", "", cur, flags=re.IGNORECASE)
            if clean != cur:
                entries.append({
                    "elementId": {"guid": g}, "propertyId": {"guid": self.eid_guid},
                    "propertyValue": {"type": "string", "status": "normal", "value": clean},
                })
        return self.set_properties_batched(entries) if entries else 0
