# Weltenbrecher — Stage 3 Finish (checkpoint)

15 October 2026. Builds on the approved Stage 2 model; every Stage 2 decision is recorded in `STAGE2_NOTES.md`. Stage 3 adds paint, wear, surface texture and markings, and delivers the finished files.

These are production-design concepts. A finished-looking render shows what the model looks like; it validates nothing about mass, armour, ballistics or crew workload.

## Files

| File | What it is |
|---|---|
| `out/weltenbrecher_stage3_finish.blend` | Native editable scene. Textures load from `out/textures/` next to it |
| `out/KS_B_stage3.glb`, `out/M12A2_stage3.glb` | One finished GLB per tank: geometry, rigging, markings and embedded textures |
| `out/M12A2_decal_okie_gusher.glb` | The optional "Okie Gusher" name decal on its own, in the same coordinate frame as the Bastion |
| `out/KS_B_stage3_hatches_open.glb`, `out/M12A2_stage3_hatches_open.glb` | Open-hatch review pose, untextured (clearance review only) |
| `out/textures/` | Per tank: `_color.jpg` (base colour), `_orm.png` (G = roughness, B = metallic), `_normal.jpg` (tangent-space normal) |
| `out/stage3_report.json` | All measurements and clearance results, plus texture and marking lists |
| `generate.py`, `stage2.py`, `stage3.py`, `params.json` | Reproducible build. Every Stage 3 choice is in the `stage3` block of `params.json` |
| `render.py`, `renders/sheet_A`–`E` | Measured gray review sheets, unchanged in approach (markings left out so the comparison stays in gray) |
| `beauty.py`, `renders/beauty_*.png`, `renders/sheet_F_finish.png` | Cycles beauty renders and the finish sheet |

## How the finish is built

- **Procedural, then baked.** `stage3.py` builds a procedural source shader for each tank and material category. It unwraps each tank into one UV layout and bakes base colour, roughness/metallic and normal maps. Then it rewires the materials to those textures. The `.blend` and the GLBs show exactly the same finish, and changing a number in `params.json` and re-running rebuilds it.
- **Instanced parts share textures.** Track links, road wheels and other instanced parts share one mesh, so every instance carries the same texture. Rubber tyres, hub grease and polished track faces are computed in each part's own coordinates, so they line up on every instance.
- **Markings are separate objects**, never baked into the paint.
  - Crosses and stars are thin decal meshes, 1.5 mm proud of the plate and excluded from the envelope.
  - Numbers and stencils are Blender text objects, so their text stays editable in the `.blend`. They export to the GLB as geometry.
- **The optional decal** sits in its own collection (`M12A2_Optional_Decals`). It is left out of the main Bastion GLB and exported on its own, as the brief asks.
- **Weld seams and cast texture live in the normal map.** Weld beads follow the plate joints of the Kaisersturm hull and turret and the Bastion hull, using a rounded-edge normal plus a faint darker line. Cast texture is a fine mottle on the Bastion turret, bustle and mantlet and on both cupolas and the Kaisersturm mantlet. Neither changes any geometry or measured envelope.
- **Smooth shading on cast and turned parts.** Barrels, wheels, cupolas, discharger cups, lamps and the Bastion's cast turret, bustle and mantlet are now smooth-shaded, with edges sharper than 35° kept crisp. This is shading only: no vertex moved.

## Kaisersturm Ausf. B finish

- **Paint:** muted gray-green (`#5E6658`), matte.
- **Markings:**
  - Black Imperial crosses with a white border, in the 1914–18 Iron Cross form (cross pattée), on both turret sides and the rear plate. The straight-armed 1918 form is one parameter away.
  - Tactical number **214** in white on both turret sides.
  - No other markings.
- **Wear:**
  - dust on horizontal surfaces and the lower hull
  - worn paint edges
  - scratches around the hatches, engine deck panels and tool stowage
  - polished track contact faces
  - restrained exhaust soot behind the two deck exhaust cowls
- **Caucasus finish later:** `mud_amount` (0 now) adds a mud layer on the lower hull and running gear without touching geometry. `dust_amount` scales the dust.

## M12A2 Bastion finish

- **Paint:** olive (`#5A5838`), matte.
- **Markings:**
  - White stars on both sponson sides.
  - White unit bumper codes **3A-7I** / **B-12** on the upper glacis and rear plate (vehicle left / right).
  - Optional **Okie Gusher** name decal on the left sponson, separate and editable.
- **Wear:**
  - rear-engine grime around the deck and exhaust
  - grease at the filter/blower lid, the engine access panel, the rear-door hinges and every wheel hub
  - fender abrasion along the sponson bottom edges
  - dusty hatch seals
  - polished track contact faces
- **One subtly replaced panel:** the bolted engine access panel is a fresher olive with less dust and no edge wear.
- **No rust and no battle damage**, as the brief asks.

## Measured envelopes and checks

Stage 3 changed no geometry. Every figure matches Stage 2:

| | Kaisersturm B | Bastion |
|---|---|---|
| Hull length | 8.20 | 7.50 |
| Gun-forward (hull rear plate to muzzle) | 10.60 | 10.00 |
| Core envelope L × W × H | 10.60 × 4.00 × 3.20 | 10.05 × 3.65 × 3.15 |
| Triangles (Blender meshes) | 117,528 | 93,470 |
| Triangles in the GLB, including text markings | 117,736 | 94,196 |
| GLB size with embedded textures | 6.5 MB | 7.7 MB |

Markings add 60 and 16 mesh triangles, plus the text converted at export. The decal meshes are excluded from the envelope because they stand 1.5 mm proud of the plate.

Checks, all re-run:
- **Clearance results** are identical to Stage 2: neutral pose, traverse, gun limits, hatches (with the +3° Kaisersturm drill), discharger launch paths, and the .50 reach and pintle traverse.
- **Exported GLB bounds** are identical to Stage 2.
- **Mirrored parts:** none of the 636 objects in the .blend has negative scale.
- **Textures:** every tank mesh in the GLBs is textured (306 Kaisersturm, 283 Bastion). Markings and the optional decal keep plain materials.

## Stage 3 proposals (editable, not canon)

Everything in the `stage3` block of `params.json` tagged `"proposal": true`:
- **Paint shades:** Kaisersturm `#5E6658` gray-green; Bastion `#5A5838` olive, with the replaced panel `#5E6140`.
- **Kaisersturm markings:** the cross form (Iron Cross pattée vs straight-armed Balkenkreuz), the cross positions and sizes, and the number 214 and its position.
- **Bastion markings:** star positions and size, bumper-code text and positions, and the Okie Gusher position and lettering (Blender's default font for now).
- **Weathering amounts and placement:** dust, edge wear, scratches, soot, grime, grease and fender abrasion.
- **Which panel is the replaced one:** the engine access panel.
- **Surface treatment:** which parts carry weld seams or cast texture, bead width and strength, cast texture scale and strength, and the 35° smooth-shading angle.

## Not done, and limits

- **Weld beads are not modeled as geometry.** They show in renders but won't come out in a print taken straight from the mesh. If the miniatures need raised beads, that's a separate geometry pass.
- **Text uses Blender's default font.** A stencil font would be more correct. Any font can be swapped into the text objects in the `.blend` without rebuilding.
- **Texture resolution:** 4096 px base colour and normal, 2048 px roughness/metallic, about 5 mm per texel. Close-ups tighter than the turret views in sheet F will start to soften.
- **Run times on this 4-core cloud machine:** the bake takes about an hour of the `generate.py` run (each 4K map 13–18 minutes). `beauty.py` takes about 10 minutes for all eight shots.
- **The beauty renders are previews:** 64 samples with denoising. For final renders, run `beauty.py` locally with more samples, e.g. `python3 beauty.py out/weltenbrecher_stage3_finish.blend renders 512`.

## Review gate

Stage 3 asks: is it ready to show someone?

## Review decisions
