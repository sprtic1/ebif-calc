"""Load and query the Renco block catalog from config/blocks.json."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BlockCatalog:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self._data = json.load(f)
        self._index: dict[str, dict] = {}
        for sname, sdata in self._data["series"].items():
            w = sdata["width_in"]
            h = sdata["height_in"]
            for b in sdata["blocks"]:
                b["width_in"] = w
                b["height_in"] = h
                b["series"] = sname
                self._index[b["id"]] = b
        logger.info("Loaded block catalog v%s — %d block types", self._data.get("version", "?"), len(self._index))

    @property
    def module_height(self) -> int:
        return self._data["module_height_inches"]

    def get(self, block_id: str) -> dict:
        return self._index[block_id]

    def series_blocks(self, series: str) -> list[dict]:
        return [b for b in self._index.values() if b["series"] == series]

    def blocks_longest_first(self, series: str) -> list[dict]:
        return sorted(self.series_blocks(series), key=lambda b: b["length_in"], reverse=True)

    def closure_len(self, series: str) -> float:
        blocks = self.series_blocks(series)
        return min(b["length_in"] for b in blocks)

    def field_block(self, series: str) -> dict:
        mapping = {"residential": "RES-12", "commercial": "COM-16"}
        return self.get(mapping[series])

    def half_block(self, series: str) -> dict:
        mapping = {"residential": "RES-6", "commercial": "COM-8"}
        return self.get(mapping[series])

    def all_ids(self) -> list[str]:
        return sorted(self._index.keys())

    def all_ids_for_series(self, series: str) -> list[str]:
        return sorted(b["id"] for b in self._index.values() if b["series"] == series)
