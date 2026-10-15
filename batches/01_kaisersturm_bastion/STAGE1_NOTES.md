# Weltenbrecher — Stage 1 Measured Blockout (checkpoint)

15 October 2026. Kaisersturm Ausf. B and M12A2 Bastion, flat gray, for silhouette review before Stage 2.

These are production-design concepts. Nothing here validates mass, armour, internal packaging or any engineering claim; a bounding box that hits a number only shows the model was built to that number.

## Files

| File | What it is |
|---|---|
| `weltenbrecher_stage1_blockout.blend` | Native editable scene (Blender 5.2). Collections `KS_B`, `M12A2`, `Reference` (ground plane, 1.80 m figure) |
| `KS_B_stage1.glb`, `M12A2_stage1.glb` | One GLB per tank, hierarchy and pivots intact, track links as shared instances |
| `scale_figure_1p80.glb` | The neutral 1.80 m reference figure |
| `generate.py` + `params.json` | Reproducible build. Edit `params.json`, rerun `python3 generate.py` (needs `pip install bpy`) |
| `render.py` | Review renders made from the exported GLBs |
| `stage1_report.json` | Every measurement and clearance check, machine-readable |
| `renders/` | Comparison sheets A–C plus each view on its own |

**Axes:** metres; +X forward, +Y vehicle left, +Z up; origin at hull centre on the ground plane. GLBs are Y-up per the glTF standard; importers convert back automatically.

**Rigging:** `<TAG>_Turret_Pivot` sits on the traverse axis at hull-roof height (rotate about Z). `<TAG>_Gun_Pivot` sits on the trunnion (rotate about local Y; negative angle raises the muzzle). Everything turret-mounted is parented under these.

**Renderer:** Blender's own renderer can't draw geometry in this cloud workspace (no GPU display), so the review renders are made with a separate OpenGL renderer from the exported GLBs. That doubles as the export check. Stage 3 beauty renders are best done in Blender on a local machine.

## Measured against the retained specs

Measured from the actual mesh vertices in world space, then re-measured from the exported GLBs; both agree.

| | Kaisersturm B target | measured | Bastion target | measured |
|---|---|---|---|---|
| Hull length | 8.20 | **8.20** | 7.50 | **7.50** |
| Gun-forward overall | 10.60 | **10.60** | ~10.00 | **10.00** (10.02 incl. rear-door panels) |
| Width | 4.00 | **4.00** (skirt faces) | 3.65 | **3.65** (track/fender line) |
| Turret roof | — | 2.85 | 2.90 | **2.90** |
| Cupola top | 3.20 | **3.20** | 3.15 | **3.15** |
| Track width | 0.90 | **0.90** | 0.82 | **0.82** |
| Ground contact | — | 5.60 (wheel centres) | 4.70 | **4.70** (wheel centres) |
| Road wheels / side | 8 stations, double wheels | 8 | 8 in 4 paired bogies | **8, 4 bogie modules** |
| Turret ring | — | 2.30 (proposal) | 2.25 | **2.25** |
| Bore | 105 mm | 105 mm | 105 mm | 105 mm |
| Hull ground clearance | — | 0.50 | — | 0.47 |
| Triangles (exported) | | 41,108 | | 42,736 |

Aerials, roof guns and loose stowage don't exist yet. When they're added in Stage 2 they'll be tagged so they stay out of the envelope numbers.

## Clearance checks

- **Neutral pose:** no interpenetration between turret parts and hull or hatches, running gear and hull, tracks and hull, suspension and tracks, or skirts and running gear. Wheels rest exactly on the track inner face, and grouser tips rest on the ground plane.
- **Traverse:** full 360° in 15° steps with the gun level is clear on both tanks.
- **Elevation:** +20° is clear of the hull on both. The upper elevation limit against the turret roof isn't modeled yet, because the mantlet passes through a turret face with no gun port cut. That's Stage 2.
- **Depression limits** (found by stepping 0.5° until the gun touches the hull):

| Traverse | Kaisersturm B | Bastion |
|---|---|---|
| 0° (front) | −13.5° | beyond −20° |
| 45° | −15.0° | −13.5° |
| 90° (side) | −16.0° | beyond −20° |
| 135° | −15.0° | −14.5° |
| 180° (over engine deck) | −7.0° | −8.0° |

## Review gate

1. **Distinct in flat gray?** Yes. The Kaisersturm is a faceted turret on a ring, a heavy box mantlet and deep skirts enclosing the running gear. The Bastion is a rounded turret with a separate bustle, a slim rounded mantlet, four exposed bogie modules and a visible top track run. The side overlay on Sheet A shows the outlines nearly coincide in size, so the difference comes from shape.
2. **Human-scale fittings consistent?** Hull hatches are 0.60 m clear openings on both. Turret hatches are 0.55–0.72 m. The same 1.80 m figure stands beside both at identical scale. Hinges, handles and opening envelopes are Stage 2.
3. **Kaisersturm inside its envelope?** Yes: 10.60 × 4.00 × 3.20 m, including track grousers and exhausts.
4. **Bastion exactly four paired bogies / eight road wheels per side?** Yes. Each bogie is its own module (`M12A2_Bogie_L1`…`R4`) holding one housing and two road wheels, so it can be swapped as a unit.
5. **Crew entry, turret rotation, engine service?** Partly, as Stage 1 intends. Hatches are placed, sized and checked against turret overhang. Turret pivots sit on the ring axes, with the ring visible as a band under each turret. Engine-deck grille and access-panel layouts are blocked in, and the Bastion has two rear automotive doors kept clear of stowage. Working hinges, grilles, the Bastion's filter/blower access and separate crew air intake are Stage 2.
6. **New choices separated from retained specs?** Yes. Every value in `params.json` is tagged RETAINED, PROPOSAL or DERIVED, and the proposals are listed below.

## New design proposals (editable, not canon)

**Kaisersturm B**
- Running gear: 8 stations of 0.76 m double road wheels on trailing torsion-bar arms; front idler, rear sprocket (the brief's provisional layout); 3 return rollers hidden behind the skirts.
- Skirts: five removable panels per side hanging to 0.44 m, just below the wheel hubs, hiding the arms and upper wheels and showing the bottom third of each wheel. (Lowered from 0.58 m at review, 15 Oct.)
- Hull: lower glacis plus a 33° upper glacis; full-width sponsons over the tracks; upper hull sides lean in 13°.
- Turret: 3.1 m long × 2.6 m wide, clipped front corners, sides leaning in about 16°, sloped rear; ring diameter 2.30 m; turret raised 5 cm on a visible ring.
- Gun axis at 2.42 m. Raised from 2.34 m because the mantlet hit the roof at any depression. Box mantlet 1.35 × 0.72 × 0.85 m deep; plain barrel with a muzzle swell and no brake, which keeps it visibly different from the Bastion's.
- Commander's cupola on the turret left; loader hatch turret right; driver and radio operator hatches on the hull roof ahead of the turret.
- Engine deck: two radiator grilles flanking a central access panel; low armoured exhaust cowls on the rear deck, kept inside the 8.2 m hull.

**Bastion M12A2**
- Road wheels 0.56 m, 0.62 m apart within each bogie. Shrunk from 0.60 m so the four pairs read as pairs rather than eight evenly spaced wheels.
- Bogie module: bolted mounting plate on the hull side, spring housing above the wheel pair, two arms. Deliberately not a Sherman VVSS copy: no return roller on the bogie, since the 3 return rollers are on the hull.
- Idler raised to 0.78 m to keep the top track run level and clear of the bogie housings.
- Turret: rounded cast-looking body with an undercut base, and a separate bustle starting 0.32 m above the turret base so it clears the engine deck and hull hatches when traversed.
- Rounded mantlet; double-baffle muzzle brake, no bore evacuator.
- Hull: rounded cast nose (0.30 m radius) in place of the sharp V where the lower and upper glacis met, added at review on 15 Oct. The nose is pushed forward so the hull stays exactly 7.50 m long, which flattens the upper glacis from 22° to about 18°. The largest radius that fits under the sponson line is about 0.32 m. Engine deck stepped 6 cm below the crew roof.

## Review decisions (15 Oct 2026)

- Approved as proposed: Kaisersturm cupola on the turret left, plain Kaisersturm muzzle with no brake, Bastion road wheels at 0.56 m.
- Changed: Kaisersturm skirts lowered to 0.44 m; Bastion nose rounded.
- Clearance checks and envelopes re-run after both changes; all still on target and clear.

## Changes made during the build

Each was found by the clearance checks or by looking at the renders:
- Kaisersturm gun axis raised 8 cm and mantlet made shorter, because it hit the hull roof at −4° depression.
- Hull hatches on both tanks moved forward/outward, because turret overhangs swept across them during traverse.
- Kaisersturm turret narrowed from 2.9 to 2.6 m and set on a visible ring, because the first version read as a fixed casemate in the three-quarter view.
- Bastion turret base undercut steepened to clear its hatches.
- Kaisersturm exhausts moved from the rear plate to the deck, because they pushed the length to 10.82 m.
- Kaisersturm sprocket pulled in 1.5 cm and shrunk 1 cm in radius, because grousers pushed the rear 2.5 cm past the hull.
- Wheels lifted by the grouser height, because grousers were sinking 2.5 cm into the ground.
- Bastion right-side bogie housings rebuilt as true mirrored meshes instead of negative scale, which some glTF viewers misplace.

## Not yet in the model (Stage 2 scope)

Hatch hinges and opening envelopes, vision blocks, periscopes, grilles as real louvres, tow eyes, spare track links, tool racks, aerial bases, coaxial and bow MGs, the Bastion's .50 roof mount, its filter/blower access and crew air intake, lifting eyes, and the gun port opening in each turret face.
