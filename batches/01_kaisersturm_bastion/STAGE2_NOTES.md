# Weltenbrecher — Stage 2 Functional Detail (checkpoint)

15 October 2026. Builds on the approved Stage 1 blockout (lowered Kaisersturm skirts, rounded Bastion nose). Still flat gray: materials, wear and markings are Stage 3.

Production-design concepts only. Clearance checks show the parts don't collide as modeled. They say nothing about armour, mass, ballistics or whether a real crew could work the vehicle.

## Files

| File | What it is |
|---|---|
| `weltenbrecher_stage2_detail.blend` | Native scene. Includes the hidden breech clearance placeholders |
| `KS_B_stage2.glb`, `M12A2_stage2.glb` | One GLB per tank, everything closed |
| `KS_B_stage2_hatches_open.glb`, `M12A2_stage2_hatches_open.glb` | Same models posed with every hatch, lid and door open, for review |
| `generate.py`, `stage2.py`, `params.json` | Reproducible build: `stage2.py` adds the detail; every Stage 2 choice is in the `stage2` block of `params.json` |
| `render.py`, `renders/` | Review sheets A–D, made from the exported GLBs |
| `stage2_report.json` | All measurements and clearance results |

## How the moving parts work

- **Turret:** `<TAG>_Turret_Pivot` (rotate about Z). **Gun:** `<TAG>_Gun_Pivot` on the trunnion (rotate about local Y; negative raises the muzzle). Mantlet, barrel, coax and the breech placeholder ride on it.
- **Hatches, lids, cupola lids:** `<TAG>_HatchHinge_<name>` empties sit on each hinge line. Open by rotating about local Y by −`open_deg` (95° hull hatches, 100° turret hatches, stored on the empty).
- **Bastion rear doors:** `M12A2_RearDoorHinge_L/R`, rotate about Z by `open_sign × open_deg` (100°). They swing outward from their outer edges.
- Every hinge carries a note property saying how it opens. The open-pose GLBs show the result.

## What was added

**Both tanks**
- Hinged hatches with fixed rims (coamings), knuckles, grab handles, and periscopes in the hull-hatch lids.
- Commander's cupolas with narrow vision blocks under armoured brows and hinged lids. The Kaisersturm has 7 blocks and the Bastion 6. Lid tops sit exactly at 3.20 m and 3.15 m.
- Gun ports: each mantlet's rear face is a cylinder about the trunnion, seated in a matching port cut into the turret face, so it can elevate without fouling. Coax MG port (left) and gunner's sight aperture (right) in each mantlet.
- Turrets are now hollow armour shells open at the ring (12 cm walls on the Kaisersturm, 10 cm on the Bastion, 6 cm roofs). This was necessary for the breech clearance check; the thicknesses are visual, not armour specs.
- Breech clearance placeholders (breech plus recoil envelope), kept in the .blend only.
- Bow MG ball mounts, loader periscopes, turret ventilators, lifting eyes, two aerial bases with 2 m whip aerials, and tow fittings front and rear.

**Kaisersturm B**
- Driver's armoured visor block in the glacis (a small slit, no large glass).
- Engine deck: two armoured fan covers, two radiator louvre grilles, a bolted removable centre access panel with lifting handles, and low exhaust cowls (from Stage 1).
- Heavy plate tow eyes. Four spare track links (the actual track-link mesh) in a bracket on the lower nose plate, held by retaining bars and straps.
- Modest tool stowage: a cleaning-rod tube on the left deck edge, shovel and pick on the right.
- Cupola lid hinges to the rear; loader's hatch hinges outboard (right).

**Bastion M12A2**
- Taller, wider hatch rims for chemical sealing; outboard hinges; rotating periscope in each hull-hatch lid.
- Engine deck: two fine-bar cooling grilles, a bolted removable centre access panel, and a rear-deck exhaust cowl.
- **Crew air, kept separate from engine cooling:** an armoured filter/blower box with a bolted service lid at the front-right of the engine deck, topped by a protected mushroom intake cowl, well forward of and away from the cooling grilles. A protected ventilator sits on the turret roof. These shapes show where the system lives; they don't claim effective protection.
- Rear automotive doors hinged at the outer edges, opening 100°, with nothing stowed on them.
- **Common-family fittings:** one tow-shackle design used at all four corners; lifting eyes on hull and turret; bolt heads on the deck panels and filter lid.
- Removable external .50 roof mount (pintle, cradle, gun, ammunition box) on the turret roof centre-line behind the hatches. It's well clear of the commander's cupola and its lid.
- Pioneer tools on the left deck edge; stowage box on the right.

## Measured envelopes

| | Kaisersturm B | Bastion |
|---|---|---|
| Hull length | 8.20 | 7.50 |
| Gun-forward (hull rear plate to muzzle) | 10.60 | 10.00 |
| Core envelope L × W × H | 10.60 × 4.00 × 3.20 | 10.05 × 3.65 × 3.15 |
| Including tow fittings, aerials and the .50 | 10.89 × 4.00 × 4.04 | 10.20 × 3.65 × 5.00 |
| Triangles (exported) | 47,080 | 50,838 |

The Bastion's core length is 4.7 cm over its 10.00 m figure because the rear-door hinges and handles stand proud of the rear plate. The gun-forward and hull measurements are unchanged. The "including" row is tall because of the whip aerials.

## Clearance results

**Neutral pose:** clean on both. Turret, gun and breech against hull, hatches and turret shell; running gear, tracks, skirts.

**Full 360° traverse with hatches closed:** clean on both.

**Gun limits** (stepped 0.5° until something touches):

| Traverse | Kaisersturm depression | Kaisersturm elevation | Bastion depression | Bastion elevation |
|---|---|---|---|---|
| 0° (front) | −7.5° (breech meets roof) | 30°+ | −16.0° (mantlet in port) | +24.5° (mantlet in port) |
| 45° | −7.5° | 30°+ | **−3.5° (barrel over driver's lid periscope)** | +24.5° |
| 90° (side) | −7.5° | 30°+ | −16.0° | +24.5° |
| 135° | −7.5° | 30°+ | −15.0° (barrel over hull) | +24.5° |
| 180° (rear) | −7.0° (engine deck) | 30°+ | −6.0° (exhaust cowl) | +24.5° |

The Kaisersturm's 30°+ is the end of the scan, not a limit: nothing on the exterior stops it, and with no turret floor modeled the true elevation stop is undefined.

**Hatches open:**
- No lid, door or hatch fouls any fixed part when open, and the turret lids clear the .50 mount, aerials and cupola.
- Open hull hatches block turret traverse where the gun or turret passes over them (sampled every 15°, so the arcs are approximate):
  - Kaisersturm driver's lid at about 30°, radio operator's at about 330°: the gun barrel.
  - Bastion driver's lid at 45–60° and 210–270°; bow gunner's at 90–150° and 300–315°: the mantlet in front, the turret body and bustle behind.
- That's a real crew-drill constraint (don't traverse with hull hatches open), not a modeling fault.

**Crew openings:** hull hatches 0.60 m on both. Cupola openings 0.60 m (Kaisersturm) and 0.56 m (Bastion). Loader's hatches 0.72 × 0.62 m and 0.65 × 0.55 m.

## Changes to the approved Stage 1 geometry

Each was forced by a clearance check. None changes the approved silhouette or any measured envelope.
- Trunnions moved toward the turret face, 10 cm on the Kaisersturm and 6 cm on the Bastion, so the mantlets elevate without hitting the face. Gun axis height and muzzle position are unchanged.
- Bastion hull hatches moved 21 cm outboard, still front-left and front-right, because the taller chemical-seal rims and lid periscopes hit the turret base.
- The lowest 20 cm of the Bastion turret body is slightly more undercut, for the same reason.

## Stage 2 proposals (editable, not canon)

Everything in the `stage2` block of `params.json`. The ones most likely to matter:
- **Kaisersturm bow MG and driver's visor.** Not in the brief, which only fixes the Bastion's bow gun. Added because a German heavy of this lineage plausibly carries both.
- **Kaisersturm spare links on the nose** and the heavy plate tow eyes.
- **Bastion crew-air layout:** filter/blower box and intake on the deck front-right, ventilator on the turret roof.
- **Bastion .50 on the turret roof centre-line** rather than on the cupola.
- Hinge sides: hull hatches outboard on both; Kaisersturm cupola hinged rear, Bastion cupola outboard right; loader's hatches outboard.
- Cupola vision-block counts (7 / 6), louvre and grille styles, and tool layouts.

## Not modeled yet

Turret interior beyond the hollow shell (no basket, floor or ammunition, so no internal elevation stop), track pins and end connectors, headlights, smoke dischargers, and markings and decals (Stage 3).
