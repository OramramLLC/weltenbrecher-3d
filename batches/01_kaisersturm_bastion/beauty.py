"""
Weltenbrecher - Stage 3 beauty renders (Cycles) from the finished .blend.

Run either way:
  python3 beauty.py [path/to/weltenbrecher_stage3_finish.blend] [renders_dir] [samples]
  blender -b out/weltenbrecher_stage3_finish.blend -P beauty.py -- [renders_dir] [samples]
Defaults come from the stage3.beauty block of params.json. Cloud previews use a modest sample count;
raise it (e.g. 512) for final renders on a local machine. The .blend itself is never modified.
"""
import bpy, json, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
if not bpy.data.filepath:
    blend = argv.pop(0) if argv and argv[0].endswith(".blend") else os.path.join(HERE, "out", "weltenbrecher_stage3_finish.blend")
    bpy.ops.wm.open_mainfile(filepath=blend)
REN = argv[0] if argv else os.path.join(HERE, "renders")
P = json.load(open(os.path.join(HERE, "params.json")))
BE = P["stage3"]["beauty"]
SAMPLES = int(argv[1]) if len(argv) > 1 else BE["samples"]
os.makedirs(REN, exist_ok=True)

sc = bpy.context.scene; O = bpy.data.objects
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = BE["resolution"]; sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
try:
    sc.view_settings.view_transform = 'AgX'
except TypeError:
    sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'None'

# --- world, sun, ground (render-only; the .blend on disk is untouched)
world = bpy.data.worlds.new("Beauty_World"); sc.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.55, 0.62, 0.72, 1); bg.inputs["Strength"].default_value = 0.9
sun = bpy.data.objects.new("Beauty_Sun", bpy.data.lights.new("Beauty_Sun", 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 4.2; sun.data.angle = math.radians(1.5); sun.data.color = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
if "Ground_Plane" in O: O["Ground_Plane"].hide_render = True
gm = bpy.data.materials.new("Beauty_Ground"); gm.use_nodes = True; nt = gm.node_tree
bs = nt.nodes["Principled BSDF"]; bs.inputs["Roughness"].default_value = 0.95
nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.35; nz.inputs["Detail"].default_value = 8
cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.20, 0.18, 0.15, 1); cr.color_ramp.elements[1].color = (0.33, 0.30, 0.25, 1)
nt.links.new(nz.outputs["Fac"], cr.inputs[0]); nt.links.new(cr.outputs[0], bs.inputs["Base Color"])
me = bpy.data.meshes.new("Beauty_Ground"); me.from_pydata([(-200, -200, 0), (200, -200, 0), (200, 200, 0), (-200, 200, 0)], [], [(0, 1, 2, 3)])
me.materials.append(gm); ground = bpy.data.objects.new("Beauty_Ground", me); sc.collection.objects.link(ground)

cam = bpy.data.objects.new("Beauty_Cam", bpy.data.cameras.new("Beauty_Cam")); sc.collection.objects.link(cam); sc.camera = cam

def aim(eye, target, lens=50):
    cam.location = Vector(eye); cam.data.lens = lens
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()

ks_root, bs_root, fig = O["KS_B_Root"], O["M12A2_Root"], O["Scale_Figure_1p80m"]
deco = O.get("M12A2_Decal_OkieGusher")
colls = {"KS_B": bpy.data.collections["KS_B"], "M12A2": bpy.data.collections["M12A2"]}

def show(tags, decal=False):
    for t, c in colls.items():
        c.hide_render = t not in tags
    if deco is not None:
        deco.hide_render = not decal

ONLY = [x for x in os.environ.get("BEAUTY_ONLY", "").split(",") if x]   # e.g. BEAUTY_ONLY=KS_B_turret,M12A2_34

def shot(name, tags, eye, target, lens=50, roots=None, fig_at=None, decal=False):
    if ONLY and name not in ONLY:
        return None
    show(tags, decal)
    ks_root.location = (roots or {}).get("KS_B", (0, 0, 0)); bs_root.location = (roots or {}).get("M12A2", (0, 0, 0))
    fig.hide_render = fig_at is None
    if fig_at is not None: fig.location = fig_at
    aim(eye, target, lens)
    sc.render.filepath = os.path.join(REN, f"beauty_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, flush=True)
    return sc.render.filepath

shots = []
shots.append(("KAISERSTURM AUSF. B  —  front three-quarter",
              shot("KS_B_34", ["KS_B"], (13.5, -11.0, 4.2), (0.6, 0.0, 1.45), 50, fig_at=(3.0, -3.3, 0))))
shots.append(("M12A2 BASTION  —  front three-quarter",
              shot("M12A2_34", ["M12A2"], (13.0, 10.5, 4.0), (0.5, 0.0, 1.40), 50, fig_at=(3.0, 3.1, 0))))
shots.append(("KAISERSTURM AUSF. B  —  rear: deck, exhausts, soot",
              shot("KS_B_rear", ["KS_B"], (-12.5, 9.0, 5.5), (-1.6, 0.0, 1.30), 50)))
shots.append(("M12A2 BASTION  —  rear: doors, grime, bumper codes",
              shot("M12A2_rear", ["M12A2"], (-12.0, -9.0, 5.0), (-1.6, 0.0, 1.25), 50)))
shots.append(("SAME SCALE  —  Kaisersturm (left) and Bastion, 1.80 m figure",
              shot("comparison", ["KS_B", "M12A2"], (19.0, -16.0, 5.0), (0.8, 0.0, 1.4), 45,
                   roots={"KS_B": (0, 3.0, 0), "M12A2": (0, -3.0, 0)}, fig_at=(5.6, 0.0, 0))))
shots.append(("M12A2 BASTION  —  optional \"Okie Gusher\" decal (separate GLB)",
              shot("M12A2_okie_gusher", ["M12A2"], (6.5, 6.8, 2.3), (1.2, 1.5, 1.45), 55, decal=True)))
shots.append(("KAISERSTURM AUSF. B  —  turret: Imperial cross, tactical number, gas cups, weld seams",
              shot("KS_B_turret", ["KS_B"], (3.4, 6.2, 3.6), (-0.15, 1.0, 2.35), 60)))
shots.append(("M12A2 BASTION  —  cast turret, smoke and gas cups, .50 at the cupola",
              shot("M12A2_turret", ["M12A2"], (4.2, -5.8, 4.3), (0.0, -0.7, 2.55), 55)))
ks_root.location = bs_root.location = (0, 0, 0)

try:
    from PIL import Image, ImageDraw, ImageFont
    F = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(F, 20) if os.path.exists(F) else ImageFont.load_default()
    W = 960; tiles = []
    for title, path in shots:
        if path is None: continue
        im = Image.open(path).convert("RGB"); im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS)
        t = Image.new("RGB", (W, im.height + 40), "white"); t.paste(im, (0, 40))
        ImageDraw.Draw(t).text((8, 10), title, font=font, fill=(30, 30, 30)); tiles.append(t)
    rows = [tiles[i:i + 2] for i in range(0, len(tiles), 2)]
    H = sum(max(t.height for t in r) for r in rows) + 24 * (len(rows) + 1)
    sheet = Image.new("RGB", (2 * W + 72, H), "white"); y = 24
    for r in rows:
        for j, t in enumerate(r): sheet.paste(t, (24 + j * (W + 24), y))
        y += max(t.height for t in r) + 24
    if not ONLY:
        sheet.save(os.path.join(REN, "sheet_F_finish.png")); print("sheet F done")
except ImportError:
    print("PIL not available: individual beauty renders written, sheet F skipped")
