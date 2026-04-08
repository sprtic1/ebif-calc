"""Pallet and container bin-packing.

Container sizes (floor positions per layer):
  40ft HC:       11 cols x 2 rows = 22/layer, 2 layers max = 44 pallets, 58,135 lbs
  40ft Standard: 11 cols x 2 rows = 22/layer, 2 layers max = 44 pallets, 58,935 lbs
  20ft HC:        5 cols x 2 rows = 10/layer, 2 layers max = 20 pallets, 47,070 lbs
  20ft Standard:  5 cols x 2 rows = 10/layer, 2 layers max = 20 pallets, 47,840 lbs

Packing rules:
  1. Start with largest container. Fill to 100% — weight or pallet count, whichever first.
  2. Bottom layer fills EVERY floor position before ANY pallet goes on upper layer.
     Left to right, row 1 then row 2.
  3. If weight maxes out before pallet count, stop — no second layer.
  4. Remaining pallets → smallest container that fits by both weight and pallet count.
  5. Same fill order in container 2.
"""

import json
import logging
import math
from dataclasses import dataclass, field

from .aggregator import ProjectTotals
from .block_catalog import BlockCatalog

logger = logging.getLogger(__name__)

PALLET_L = 48
PALLET_W = 40


# ── dataclasses ──────────────────────────────────────────────

@dataclass
class BlockPalletSpec:
    block_id: str
    block_length: int
    block_width: int
    block_height: int
    blocks_per_layer: int
    layers_per_pallet: int
    blocks_per_pallet: int
    pallet_height_in: float


@dataclass
class Pallet:
    pallet_number: int
    block_id: str
    block_count: int
    weight_lbs: float
    height_in: float = 0.0
    container: int = 0
    layer: int = 0
    row: int = 0
    col: int = 0


@dataclass
class ContainerOption:
    containers: list[dict] = field(default_factory=list)
    total_containers: int = 0
    total_capacity: int = 0
    utilization_percent: float = 0.0
    total_payload_lbs: float = 0.0
    is_recommended: bool = False
    label: str = ""


@dataclass
class Consumables:
    total_joint_linear_ft: float = 0.0
    adhesive_cartridges: int = 0
    adhesive_per_cartridge_ft: float = 100.0
    adhesive_confirmed: bool = False
    crew_size: int = 4
    mallets: int = 1


@dataclass
class PackingResult:
    recommended: ContainerOption = field(default_factory=ContainerOption)
    all_options: list[ContainerOption] = field(default_factory=list)
    total_pallets: int = 0
    total_weight_lbs: float = 0.0
    pallets: list[Pallet] = field(default_factory=list)
    pallet_specs: dict = field(default_factory=dict)
    consumables: Consumables = field(default_factory=Consumables)
    warnings: list[str] = field(default_factory=list)
    loaded_pallet_height: int = 48
    container_type: str = ""
    container_name: str = ""
    containers_required: int = 0
    max_pallets_per_container: int = 0
    pallets_per_layer: int = 0
    max_layers: int = 0
    utilization_percent: float = 0.0
    blocks_per_pallet: int = 40


# ── helpers ──────────────────────────────────────────────────

def _calc_blocks_per_pallet(block: dict, max_h: int = 48) -> BlockPalletSpec:
    bl, bw, bh = block["length_in"], block["width_in"], block["height_in"]
    per_layer = max((PALLET_L // bl) * (PALLET_W // bw),
                    (PALLET_L // bw) * (PALLET_W // bl), 1)
    layers = max(max_h // bh, 1) if bh > 0 else 1
    return BlockPalletSpec(
        block_id=block["id"], block_length=bl, block_width=bw, block_height=bh,
        blocks_per_layer=per_layer, layers_per_pallet=layers,
        blocks_per_pallet=per_layer * layers, pallet_height_in=layers * bh)


def _calc_consumables(totals: ProjectTotals, catalog: BlockCatalog, settings: dict) -> Consumables:
    cc = settings.get("consumables", {})
    apt = cc.get("adhesive_linear_ft_per_cartridge", 100)
    crew = cc.get("crew_size", 4)
    jft = sum(cnt * catalog.get(bid)["length_in"]
              for bid, cnt in totals.blocks_by_type.items()) / 12.0
    cartridges = math.ceil(jft / apt) if apt > 0 else 0
    # 1 rubber mallet per 20 glue guns (cartridges), minimum 1
    mallets = max(1, math.ceil(cartridges / 20))
    return Consumables(
        total_joint_linear_ft=round(jft, 0),
        adhesive_cartridges=cartridges,
        adhesive_per_cartridge_ft=apt,
        adhesive_confirmed=cc.get("adhesive_confirmed", False),
        crew_size=crew,
        mallets=mallets)


def _fill_container(pallet_list: list[Pallet], start: int, ctr: dict,
                    ctr_num: int, pack_tight: bool = False) -> int:
    """Fill one container from pallet_list[start:] following the rules.

    pack_tight=False (container 1):
      Bottom layer fills every floor position L-to-R, row 1 then row 2,
      before any pallet goes on upper layer. Stops at weight or pallet max.

    pack_tight=True (overflow containers):
      Stack pallets to the LEFT. Bottom layer fills only as many columns as
      needed, then upper layer stacks on the same columns. Right side of
      container stays empty for other cargo.

    Returns number of pallets placed.
    """
    ppl = ctr["pallets_per_layer"]   # floor positions (22 or 10)
    max_pal = ctr["max_pallets"]     # 44 or 20
    max_wt = ctr["max_payload_lbs"]
    n_available = len(pallet_list) - start
    to_place = min(n_available, max_pal)

    # Grid: 40ft = 11 cols × 2 rows, 20ft = 5 cols × 2 rows
    n_cols = ppl // 2 if ppl > 1 else 1
    n_rows = 2
    max_layers = 2

    placed = 0
    weight = 0.0

    if pack_tight:
        # Split pallets evenly between 2 layers, both pushed left.
        # Fill column-first: each column gets both rows before moving right.
        per_layer = math.ceil(to_place / max_layers)  # e.g. 14 → 7 per layer

        for layer in (1, 2):
            layer_placed = 0
            layer_target = per_layer if layer == 1 else to_place - placed
            for col in range(1, n_cols + 1):
                for row in range(1, n_rows + 1):
                    if layer_placed >= layer_target or placed >= to_place:
                        break
                    p = pallet_list[start + placed]
                    if weight + p.weight_lbs > max_wt:
                        return placed
                    p.container = ctr_num
                    p.layer = layer
                    p.row = row
                    p.col = col
                    weight += p.weight_lbs
                    placed += 1
                    layer_placed += 1
    else:
        # Standard: fill entire bottom layer, then upper layer
        for layer in (1, 2):
            for row in range(1, n_rows + 1):
                for col in range(1, n_cols + 1):
                    if placed >= max_pal or placed >= n_available:
                        return placed
                    p = pallet_list[start + placed]
                    if weight + p.weight_lbs > max_wt:
                        return placed
                    p.container = ctr_num
                    p.layer = layer
                    p.row = row
                    p.col = col
                    weight += p.weight_lbs
                    placed += 1

    return placed


# ── main entry point ─────────────────────────────────────────

def calculate_packing(totals: ProjectTotals, catalog: BlockCatalog,
                      container_config_path: str, loaded_pallet_height: int = 48,
                      settings: dict | None = None) -> PackingResult:
    with open(container_config_path) as f:
        cfg = json.load(f)

    containers = cfg["containers"]
    pallet_wt = cfg["pallet"]["weight_lbs"]
    result = PackingResult(loaded_pallet_height=loaded_pallet_height)

    # ── build pallet list ──
    pallet_specs: dict[str, BlockPalletSpec] = {}
    for bid in totals.blocks_by_type:
        pallet_specs[bid] = _calc_blocks_per_pallet(catalog.get(bid), loaded_pallet_height)
    result.pallet_specs = pallet_specs

    pallet_list: list[Pallet] = []
    pnum = 1
    for bid in sorted(totals.blocks_by_type):
        count = totals.blocks_by_type[bid]
        if count == 0:
            continue
        b = catalog.get(bid)
        spec = pallet_specs[bid]
        bpp = spec.blocks_per_pallet
        for _ in range(count // bpp):
            pallet_list.append(Pallet(
                pallet_number=pnum, block_id=bid, block_count=bpp,
                weight_lbs=round(bpp * b["weight_lbs"] + pallet_wt, 1),
                height_in=spec.pallet_height_in))
            pnum += 1
        rem = count % bpp
        if rem > 0:
            pallet_list.append(Pallet(
                pallet_number=pnum, block_id=bid, block_count=rem,
                weight_lbs=round(rem * b["weight_lbs"] + pallet_wt, 1),
                height_in=spec.pallet_height_in))
            pnum += 1

    result.total_pallets = len(pallet_list)
    result.total_weight_lbs = round(sum(p.weight_lbs for p in pallet_list), 1)
    result.pallets = pallet_list
    result.blocks_per_pallet = max((s.blocks_per_pallet for s in pallet_specs.values()), default=40)

    if not pallet_list:
        result.consumables = _calc_consumables(totals, catalog, settings or {})
        return result

    n_pallets = len(pallet_list)

    # ── sort containers: largest first, then smallest first ──
    by_largest = sorted(containers,
                        key=lambda c: (c["pallets_per_layer"], c["interior_height_in"]),
                        reverse=True)
    by_smallest = sorted(containers,
                         key=lambda c: (c["max_pallets"], c["pallets_per_layer"]))

    # ── Container 1: largest available ──
    largest = by_largest[0]
    c1_placed = _fill_container(pallet_list, 0, largest, 1)
    c1_wt = sum(pallet_list[i].weight_lbs for i in range(c1_placed))
    chosen = [{"type": largest, "placed": c1_placed}]
    logger.info("Container 1 (%s): %d/%d pallets, %.0f/%.0f lbs",
                largest["name"], c1_placed, largest["max_pallets"],
                c1_wt, largest["max_payload_lbs"])

    remaining = n_pallets - c1_placed
    pi = c1_placed

    # ── Container 2+: smallest type that fits overflow ──
    while remaining > 0:
        overflow_wt = sum(pallet_list[pi + i].weight_lbs for i in range(remaining))
        picked = None
        for ctr in by_smallest:
            if ctr["max_pallets"] >= remaining and ctr["max_payload_lbs"] >= overflow_wt:
                picked = ctr
                break
        if picked is None:
            picked = by_largest[0]  # fallback to largest

        ctr_num = len(chosen) + 1
        placed = _fill_container(pallet_list, pi, picked, ctr_num, pack_tight=True)
        ctr_wt = sum(pallet_list[pi + i].weight_lbs for i in range(placed))
        chosen.append({"type": picked, "placed": placed})
        logger.info("Container %d (%s): %d/%d pallets, %.0f/%.0f lbs",
                    ctr_num, picked["name"], placed, picked["max_pallets"],
                    ctr_wt, picked["max_payload_lbs"])
        pi += placed
        remaining -= placed
        if placed == 0:
            logger.error("Could not place any pallets — aborting")
            break

    # ── build result ──
    parts: list[dict] = []
    for c in chosen:
        if parts and parts[-1]["type"]["id"] == c["type"]["id"]:
            parts[-1]["count"] += 1
        else:
            parts.append({"type": c["type"], "count": 1})

    total_ctrs = len(chosen)
    total_cap = sum(c["type"]["max_pallets"] for c in chosen)
    util = round(n_pallets / total_cap * 100, 1) if total_cap > 0 else 0
    label = " + ".join(f"{p['count']}x {p['type']['name']}" for p in parts)

    result.recommended = ContainerOption(
        containers=parts, total_containers=total_ctrs, total_capacity=total_cap,
        utilization_percent=util,
        total_payload_lbs=sum(c["type"]["max_payload_lbs"] for c in chosen),
        is_recommended=True, label=label)
    result.all_options = [result.recommended]
    result.containers_required = total_ctrs
    result.utilization_percent = util
    primary = chosen[0]["type"]
    result.container_type = primary["id"]
    result.container_name = primary["name"]
    result.max_pallets_per_container = primary["max_pallets"]
    result.pallets_per_layer = primary["pallets_per_layer"]
    result.max_layers = primary["max_layers"]

    result.consumables = _calc_consumables(totals, catalog, settings or {})
    logger.info("Packing: %d pallets -> %s (%.1f%% util)", n_pallets, label, util)
    return result
