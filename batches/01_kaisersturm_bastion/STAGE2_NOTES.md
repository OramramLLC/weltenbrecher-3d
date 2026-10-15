# Weltenbrecher — Stage 2 Functional Detail (checkpoint)

15 October 2026. Builds on the approved Stage 1 blockout (lowered Kaisersturm skirts, rounded Bastion nose). Still flat gray: materials, wear and markings are Stage 3.

**Revision 1 (15 Oct 2026, after Nate's review):** Bastion .50 moved forward beside the cupola; smoke and gas dischargers, headlights and tail lights, track pins and end connectors, and an elevating-gear stop added to both tanks. See "Revision 1" below. 

**Revision 2 (15 Oct 2026):** Nate allowed hatches to open further. Hull hatch lids now open to 155° (Kaisersturm) and 165° (Bastion), and the Bastion cupola lid to 155°. See "Revision 2" below. Stage 2 is awaiting review again.

Production-design concepts only. Clearance checks show the parts don't collide as modeled. They say nothing about armour, mass, ballistics or whether a real crew could work the vehicle.

## Files

| File | What it is |
|---|---|
| `weltenbrecher_stage2_detail.blend` | Native scene. Includes the hidden breech clearance placeholders |
| `KS_B_stage2.glb`, `M12A2_stage2.glb` | One GLB per tank, everything closed |
| `KS_B_stage2_hatches_open.glb`, `M12A2_stage2_hatches_open.glb` | Same models posed with every hatch, lid and door open, for review |
| `generate.py`, `stage2.py`, `params.json` | Reproducible build: `stage2.py` adds the detail; every Stage 2 choice is in the `stage2` block of `params.json` |
| `render.py`, `renders/` | Review sheets A–E, made from the exported GLBs. Sheet E and the `rev1_*` images cover Revision 1 |
| `stage2_report.json` | All measurements and clearance results |

## How the moving parts work

- **Turret:** `<TAG>_Turret_Pivot` (rotate about Z). **Gun:** `<TAG>_Gun_Pivot` on the trunnion (rotate about local Y; negative raises the muzzle). Mantlet, barrel, coax and the breech placeholder ride on it.
- **Hatches, lids, cupola lids:** `<TAG>_HatchHinge_<name>` empties sit on each hinge line. Open by rotating about local Y by −`open_deg`, stored on the empty. Hull hatches open to 155° (Kaisersturm) and 165° (Bastion), the Bastion cupola to 155°, and the other turret hatches to 100°.
- **Bastion rear doors:** `M12A2_RearDoorHinge_L/R`, rotate about Z by `open_sign × open_deg` (100°). They swing outward from their outer edges.
- Every hinge carries a note property saying how it opens. The open-pose GLBs show the result.
- **Bastion .50:** `M12A2_RoofMG50_Pivot` sits on the pintle axis (rotate about Z to traverse the gun). The post is fixed to the roof.
- **Elevation stop:** each `<TAG>_Gun_Pivot` carries `elevation_stop_deg` (+18° Kaisersturm, +20° Bastion). Depression is still limited by what the gun physically hits.

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
- Removable external .50 roof mount (pintle, cradle, gun, ammunition box). Moved forward in Revision 1; see below.
- Pioneer tools on the left deck edge; stowage box on the right.

## Measured envelopes

| | Kaisersturm B | Bastion |
|---|---|---|
| Hull length | 8.20 | 7.50 |
| Gun-forward (hull rear plate to muzzle) | 10.60 | 10.00 |
| Core envelope L × W × H | 10.60 × 4.00 × 3.20 | 10.05 × 3.65 × 3.15 |
| Including tow fittings, aerials and the .50 | 10.89 × 4.00 × 4.04 | 10.20 × 3.65 × 5.00 |
| Triangles (exported) | 117,468 (47,080 before Rev. 1) | 93,454 (50,838 before Rev. 1) |

Revision 1 left every envelope figure unchanged. The triangle increase is almost all track pins: each tank uses one shared link mesh, so the GLBs grew only from 0.61 to 0.77 MB (Kaisersturm) and 0.74 to 0.93 MB (Bastion).

The Bastion's core length is 4.7 cm over its 10.00 m figure because the rear-door hinges and handles stand proud of the rear plate. The gun-forward and hull measurements are unchanged. The "including" row is tall because of the whip aerials.

## Clearance results

**Neutral pose:** clean on both. Turret, gun and breech against hull, hatches and turret shell; running gear, tracks, skirts.

**Full 360° traverse with hatches closed:** clean on both.

**Gun limits** (stepped 0.5° until something touches):

| Traverse | Kaisersturm depression | Kaisersturm elevation | Bastion depression | Bastion elevation |
|---|---|---|---|---|
| 0° (front) | −7.5° (breech meets roof) | +18° (gear stop) | −16.0° (mantlet in port) | +20° (gear stop) |
| 45° | −7.5° | +18° | **−3.5° (barrel over driver's lid periscope)** | +20° |
| 90° (side) | −7.5° | +18° | −16.0° | +20° |
| 135° | −7.5° | +18° | −15.0° (barrel over hull) | +20° |
| 180° (rear) | −7.0° (engine deck) | +18° | −6.0° (exhaust cowl) | +20° |

Revision 1 added the elevating-gear stops (proposals). Before that, nothing on the exterior stopped the Kaisersturm's gun before the 30° end of the scan, and the Bastion's mantlet met its port at +24.5°. Depression limits are unchanged: none of the new parts is in the gun's path.

**Hatches open:**
- No lid, door or hatch fouls any fixed part when open, and the turret lids clear the .50 mount, aerials and cupola.
- Open hull hatches and turret traverse (Revision 2 angles, sampled every 5° in the report and re-checked at 1°):
  - **Bastion** (lids at 165°): the turret traverses a full 360° with both hull hatches open. At the old 95° the driver's lid blocked 45–60° and 210–270°, and the bow gunner's 90–150° and 300–315°.
  - **Kaisersturm** (lids at 155°): with the gun level, the barrel still clips the driver's lid at about 32–40° and the radio operator's at about 320–328°. With the gun raised 2.5° the turret clears a full 360°. At the old 95° no elevation up to the stop cleared it. Crew drill: lay the gun at about +3° before traversing with hull hatches open.

**Crew openings:** hull hatches 0.60 m on both. Cupola openings 0.60 m (Kaisersturm) and 0.56 m (Bastion). Loader's hatches 0.72 × 0.62 m and 0.65 × 0.55 m.

## Changes to the approved Stage 1 geometry

Each was forced by a clearance check. None changes the approved silhouette or any measured envelope.
- Trunnions moved toward the turret face, 10 cm on the Kaisersturm and 6 cm on the Bastion, so the mantlets elevate without hitting the face. Gun axis height and muzzle position are unchanged.
- Bastion hull hatches moved 21 cm outboard, still front-left and front-right, because the taller chemical-seal rims and lid periscopes hit the turret base.
- The lowest 20 cm of the Bastion turret body is slightly more undercut, for the same reason.

## Revision 1 (15 Oct 2026)

Made after Nate's review of the first Stage 2 checkpoint. All values are in the `stage2` block of `params.json`.

**Bastion .50 moved forward** (Nate: it didn't look easy to operate from the hatch). The pintle went from the rear roof centre-line (turret x −0.85, y 0) to beside the commander's cupola (x +0.15, y −0.25). Before, the grips were about 1.4 m from either hatch. Now:
- **Reach:** with the commander standing in the open cupola, shoulder to grips is **0.44 m**. The rule is shoulders 0.40 m above the hatch top and grips within 0.70 m. The loader's hatch is 0.92 m away, so this is the commander's gun.
- **Clearances:** the gun still clears the cupola, both lids, the periscopes, the ventilator and the main gun through its full elevation.
- **Traverse on the pintle:** the full 360° is clear with hatches closed and, since Revision 2, with all hatches open. In Revision 1 the cupola lid at 100° fouled it at about 75° and 225–255°. Those notes credited the 75° clash to the loader's lid, but the re-check showed it was the cupola lid.
- **Height:** the grips sit 3.34 m above the ground. The mount is still removable and still excluded from the height envelope.

**Smoke and gas grenade dischargers**, prompted by the setting's routine chemical warfare. Both are fired electrically from inside the turret.
- **Kaisersturm:** three smoke cups on each turret cheek, firing 30° outboard of forward. Two larger gas cups on each turret side, firing 70° outboard. All are elevated 45°.
- **Bastion:** two banks of three per side using one common cup, in keeping with common-family parts. The smoke bank fires 35° outboard and the gas bank 75°, both at 45°.
- **Telling them apart:** gas cups carry a raised band at the mouth so a crew can tell them from smoke by feel. Colour bands are Stage 3.
- **Launch-path check:** the first 3 m of every cup's flight was ray-tested against the vehicle (centre plus four rays at 80 % bore). It was run with hatches closed and all open, turret at 45° steps. Clear on both tanks.

**Headlights and tail lights.**
- **Kaisersturm:** a hooded headlight at each upper-glacis corner.
- **Bastion:** a headlight and a blackout marker lamp at each upper-glacis corner, inside a bar brush guard.
- **Both:** hooded tail and convoy lights on the rear deck, kept inside the hull length. None of these changes any envelope or gun limit.

**Track pins.** Each tank's one shared link mesh was rebuilt, so the spare links on the Kaisersturm's nose match.
- **Kaisersturm (dry pin):** hinge lugs alternate across the width and interleave with the next link on a single pin, with pin heads at both edges.
- **Bastion (double pin):** rubber-bushed, joined at both edges by end connectors with wedge bolts. The shoe body is 6 cm narrower each side to make room for the connectors, so the overall track width is still 0.82 m.
- **Unchanged:** grouser tips still rest on the ground, track widths are unchanged, and every track, wheel and suspension clearance is still clean.

**Elevation stop.** An elevating-gear stop of +18° (Kaisersturm) and +20° (Bastion), recorded on each gun pivot. A full turret interior (basket, seats, ammunition) is still not modeled; for an exterior model the stop is the part that matters.

## Revision 2 (15 Oct 2026)

Nate allowed the hatches to open further, so that lids lying flatter would clear the turret, gun and .50. Each lid's angle was scanned in 5° steps from its old value to 180°, checking whether the lid fouls anything and what it still blocks. The change is only how far each lid opens; hinge lines, lids and every closed-pose measurement are unchanged.

| Hatch | Was | Now | Why this angle |
|---|---|---|---|
| Kaisersturm driver, radio operator | 95° | 155° | Widest before the lid's periscope meets the hull roof (159–160°). The gun still clips the lid when level; +2.5° elevation clears it |
| Bastion driver, bow gunner | 95° | 165° | First angle at which the turret traverses a full 360° with the lid open. Nothing fouled up to 180° |
| Bastion cupola | 100° | 155° | First angle at which the .50 traverses a full 360° on its pintle with all lids open |
| Kaisersturm cupola and loader, Bastion loader | 100° | 100° | No conflicts, so unchanged |

What this solves: every Bastion open-hatch conflict (turret traverse and .50 traverse). For the Kaisersturm it shrinks the conflict to a small window over each hull hatch, cleared with 2.5° of gun elevation.

What it doesn't solve: the Bastion's −3.5° depression at 45° traverse. That comes from the closed driver's-lid periscope, so opening angles can't change it.

Side effect: open at 165°, the Bastion's hull lids reach 2.30 m from the centre-line, about 0.48 m past the track edge. They hang out over the tracks with the lid's top surface facing down. The Kaisersturm's lids at 155° stay over the hull roof. The opening angles are proposals; real hatches this wide would need a stop or catch, which isn't modeled.

## Review decisions (15 Oct 2026)

- Nate liked most of the first checkpoint and flagged only the .50. Treated as approved: Kaisersturm bow MG and driver's visor; spare links and plate tow eyes; Bastion crew-air layout; hinge sides; vision-block counts, grille styles and tool layouts; and the three forced changes to Stage 1 geometry (trunnions, Bastion hull hatches, turret undercut).
- Changed: Bastion .50 moved forward to the cupola (Revision 1).
- Asked for before Stage 3: the "not modeled yet" items, with smoke **and gas** dischargers (Revision 1).
- Not flagged, left as modeled pending confirmation: Kaisersturm −7.5° depression, Bastion −3.5° at 45°, Bastion 10.05 m core length.
- Revision 1 follow-up: Nate confirmed gas grenade launchers are what he meant. He allowed hatches to open further where that clears parts (Revision 2).

## Stage 2 proposals (editable, not canon)

Everything in the `stage2` block of `params.json`. The ones most likely to matter:
- **Kaisersturm bow MG and driver's visor.** Not in the brief, which only fixes the Bastion's bow gun. Added because a German heavy of this lineage plausibly carries both.
- **Kaisersturm spare links on the nose** and the heavy plate tow eyes.
- **Bastion crew-air layout:** filter/blower box and intake on the deck front-right, ventilator on the turret roof.
- **Bastion .50 on the turret roof centre-line** rather than on the cupola.
- Hinge sides: hull hatches outboard on both; Kaisersturm cupola hinged rear, Bastion cupola outboard right; loader's hatches outboard.
- Cupola vision-block counts (7 / 6), louvre and grille styles, and tool layouts.
- **Revision 1 proposals:** discharger layouts, cup counts and firing angles; using a banded cup for gas; elevating-gear stops of +18° / +20°; headlight and guard styles; track-pin styles. The .50 position is the change Nate asked for. Its exact spot (x +0.15, y −0.25) and the 0.70 m reach rule are proposals.

## Not modeled yet

Turret interior beyond the hollow shell (no basket, seats or ammunition; the elevation stop is defined as a gear limit instead), and markings and decals (Stage 3). Track pins, lights and dischargers were added in Revision 1.
