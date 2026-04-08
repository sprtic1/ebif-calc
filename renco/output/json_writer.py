"""JSON output for BIM6x/Renco webpage."""

import json
import logging
from datetime import datetime

from ..aggregator import ProjectTotals
from ..calculator import WallResult
from ..packing import PackingResult
from ..block_catalog import BlockCatalog
from ..wall_parser import Wall, _ft_in

logger = logging.getLogger(__name__)


def write_json(totals: ProjectTotals, results: list[WallResult], packing: PackingResult,
               catalog: BlockCatalog, excluded_walls: list[Wall], output_path: str,
               pipeline_duration_sec: float = 0.0):
    data = {
        "project": {
            "name": totals.project_name,
            "run_date": datetime.now().isoformat(timespec="seconds"),
            "pipeline_duration_sec": round(pipeline_duration_sec, 1),
            "total_walls": totals.total_walls,
            "walls_with_warnings": totals.walls_with_flags,
            "excluded_walls": totals.excluded_count,
        },
        "summary": {
            "total_blocks": totals.total_blocks,
            "total_weight_lbs": totals.total_weight_lbs,
            "weight_is_estimated": not totals.weight_all_confirmed,
            "containers_required": packing.containers_required,
            "container_recommendation": packing.recommended.label if packing.recommended else "",
            "container_utilization": packing.recommended.utilization_percent if packing.recommended else 0,
            "container_options": [
                {"label": o.label, "containers": o.total_containers,
                 "capacity": o.total_capacity, "utilization": o.utilization_percent,
                 "recommended": o.is_recommended}
                for o in packing.all_options
            ],
        },
        "pallet_specs": {
            bid: {"blocks_per_pallet": s.blocks_per_pallet, "blocks_per_layer": s.blocks_per_layer,
                  "layers": s.layers_per_pallet, "pallet_height_in": s.pallet_height_in}
            for bid, s in packing.pallet_specs.items()
        },
        "consumables": {
            "adhesive_cartridges": packing.consumables.adhesive_cartridges,
            "adhesive_joint_linear_ft": packing.consumables.total_joint_linear_ft,
            "adhesive_confirmed": packing.consumables.adhesive_confirmed,
            "mallets": packing.consumables.mallets,
            "crew_size": packing.consumables.crew_size,
        },
        "blocks": [],
        "walls": [],
        "containers": [],
        "warnings": [],
    }

    # Blocks
    for bid in sorted(totals.blocks_by_type.keys()):
        cnt = totals.blocks_by_type[bid]
        b = catalog.get(bid)
        data["blocks"].append({
            "id": bid,
            "name": b.get("name", bid),
            "series": b["series"],
            "count": cnt,
            "weight_per_block_lbs": b["weight_lbs"],
            "confirmed_weight": b.get("confirmed_weight", False),
            "total_weight_lbs": round(cnt * b["weight_lbs"], 1),
        })

    # Walls
    for wr in results:
        w = wr.wall
        data["walls"].append({
            "id": w.wall_id,
            "guid": w.guid,
            "story": w.story_name,
            "length_ft_in": _ft_in(w.length_in),
            "length_in": round(w.length_in, 1),
            "height_in": round(w.height_in, 1),
            "series": w.series,
            "courses": wr.courses,
            "openings": len(w.openings),
            "blocks": wr.blocks,
            "total_blocks": wr.total_blocks,
            "weight_lbs": wr.weight_lbs,
            "flagged": bool(w.flags),
            "flags": w.flags if w.flags else None,
        })

    # Containers — build spec lookup from recommended combination
    ctr_specs = []
    if packing.recommended and packing.recommended.containers:
        for part in packing.recommended.containers:
            for _ in range(part["count"]):
                ctr_specs.append(part["type"])

    for cnum in range(1, packing.containers_required + 1):
        ctr_pallets = [p for p in packing.pallets if p.container == cnum]
        spec = ctr_specs[cnum - 1] if cnum - 1 < len(ctr_specs) else {}
        data["containers"].append({
            "container_number": cnum,
            "type": spec.get("id", packing.container_type),
            "name": spec.get("name", packing.container_name),
            "interior_length_in": spec.get("interior_length_in", 0),
            "interior_width_in": spec.get("interior_width_in", 0),
            "interior_height_in": spec.get("interior_height_in", 0),
            "max_payload_lbs": spec.get("max_payload_lbs", 0),
            "max_pallets": spec.get("max_pallets", 0),
            "pallets": [
                {
                    "pallet_number": p.pallet_number,
                    "block_id": p.block_id,
                    "block_count": p.block_count,
                    "weight_lbs": p.weight_lbs,
                    "position": {"layer": p.layer, "row": p.row, "col": p.col},
                }
                for p in ctr_pallets
            ],
            "total_pallets": len(ctr_pallets),
            "total_weight_lbs": round(sum(p.weight_lbs for p in ctr_pallets), 1),
            "layers_used": max((p.layer for p in ctr_pallets), default=0),
            "loaded_pallet_height_in": packing.loaded_pallet_height,
            "stack_height_in": packing.loaded_pallet_height * max((p.layer for p in ctr_pallets), default=0),
            "height_exceeds": packing.loaded_pallet_height * max((p.layer for p in ctr_pallets), default=0) > spec.get("interior_height_in", 999),
        })

    # Warnings
    for w in totals.warnings:
        data["warnings"].append({"detail": w})
    for ew in excluded_walls:
        if ew.composite_name and "renco" in ew.composite_name.lower():
            data["warnings"].append({
                "wall_id": ew.wall_id + ("X" if not ew.wall_id.endswith("X") else ""),
                "reason": ew.exclude_reason,
            })

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("JSON: %s", output_path)
