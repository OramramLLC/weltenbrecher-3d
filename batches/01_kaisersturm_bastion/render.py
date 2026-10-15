"""
Render Stage 1 review views from the EXPORTED GLBs (this doubles as an export check).
Orthographic, identical scale for both tanks (PPM pixels per metre).
Run:  PYOPENGL_PLATFORM=egl python3 render.py
"""
import os, json, math
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
import numpy as np, trimesh, pyrender
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out"); REN = os.path.join(HERE, "renders")
os.makedirs(REN, exist_ok=True)
REP = json.load(open(os.path.join(OUT, "stage2_report.json")))
PRM = json.load(open(os.path.join(HERE, "params.json")))
PPM = 80          # output pixels per metre, all orthographic views
SS = 2            # supersampling
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(sz, bold=False): return ImageFont.truetype(FONTB if bold else FONT, sz)

# glTF is Y-up; convert back to the project's Z-up (+X fwd, +Y left)
YUP_TO_ZUP = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)

def load_glb(path, offset=(0, 0, 0)):
    sc = trimesh.load(path, force="scene")
    items = []
    names = []
    T0 = np.eye(4); T0[:3, 3] = offset
    for node in sc.graph.nodes_geometry:
        M, gname = sc.graph[node]
        g = sc.geometry[gname]
        items.append((g, T0 @ YUP_TO_ZUP @ M))
        names.append(node)
    return items, names

def look_at(eye, target, up=(0, 0, 1)):
    eye, target, up = map(lambda v: np.array(v, float), (eye, target, up))
    f = target - eye; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = r, u, -f, eye
    return M

def render(items, cam_pose, w_m, h_m, ground=False, light_dirs=None, ppm=None):
    ppm = ppm or PPM
    W, H = int(round(w_m * ppm * SS)), int(round(h_m * ppm * SS))
    scene = pyrender.Scene(bg_color=[1, 1, 1, 0], ambient_light=[0.33, 0.33, 0.33])
    for g, M in items:
        scene.add(pyrender.Mesh.from_trimesh(g, smooth=False), pose=M)
    if ground:
        gp = trimesh.creation.box((40, 30, 0.02)); gp.apply_translation((0, 0, -0.011))
        gp.visual.face_colors = [205, 205, 205, 255]
        scene.add(pyrender.Mesh.from_trimesh(gp, smooth=False))
    cam = pyrender.OrthographicCamera(xmag=w_m / 2, ymag=h_m / 2, znear=0.1, zfar=300)
    scene.add(cam, pose=cam_pose)
    for d, inten in (light_dirs or [((-0.5, 0.6, 1.0), 3.2), ((0.6, -0.8, 0.4), 1.4)]):
        scene.add(pyrender.DirectionalLight(intensity=inten), pose=look_at(np.array(d) * 10, (0, 0, 0)))
    r = pyrender.OffscreenRenderer(W, H)
    col, dep = r.render(scene, flags=pyrender.RenderFlags.RGBA)
    r.delete()
    return col, dep

def with_edges(col, dep, depth_jump=0.06):
    rgb = col[..., :3].astype(float)
    mask = dep > 0
    lum = rgb.mean(-1)
    e = np.zeros(dep.shape, bool)
    for ax in (0, 1):
        dd = np.abs(np.diff(dep, axis=ax)); dl = np.abs(np.diff(lum, axis=ax)); dm = np.diff(mask.astype(int), axis=ax) != 0
        hit = ((dd > depth_jump) & (np.minimum(*(np.take(mask, range(dep.shape[ax] - 1), axis=ax), np.take(mask, range(1, dep.shape[ax]), axis=ax))))) | (dl > 14) | dm
        if ax == 0:
            e[:-1] |= hit; e[1:] |= hit
        else:
            e[:, :-1] |= hit; e[:, 1:] |= hit
    # drop tiny isolated edge specks (single-pixel rasterisation cracks in the software renderer)
    from scipy import ndimage
    lab, n = ndimage.label(e, structure=np.ones((3, 3)))
    if n:
        sizes = ndimage.sum(e, lab, range(1, n + 1))
        e &= np.isin(lab, np.nonzero(sizes >= 14)[0] + 1)
    out = rgb.copy()
    out[~mask] = 255
    out[e] = out[e] * 0.25 + 15
    img = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS), mask

TANKS = {
    "KS_B": dict(glb="KS_B_stage2.glb", glb_open="KS_B_stage2_hatches_open.glb", label="KAISERSTURM AUSF. B", key="kaisersturm_b"),
    "M12A2": dict(glb="M12A2_stage2.glb", glb_open="M12A2_stage2_hatches_open.glb", label="M12A2 BASTION", key="bastion_m12a2"),
}
FIG = os.path.join(OUT, "scale_figure_1p80.glb")

# view frames (metres, shared by both tanks)
SIDE = dict(x0=-6.2, x1=7.2, z0=-0.35, z1=3.75)
FRONT = dict(y0=-3.5, y1=3.5, z0=-0.35, z1=3.75)
TOP = dict(x0=-6.2, x1=7.2, y0=-3.5, y1=3.5)

views = {}
counts = {}
for tag, t in TANKS.items():
    items, names = load_glb(os.path.join(OUT, t["glb"]))
    counts[tag] = dict(mesh_nodes=len(names), track_links=sum("TrackLink" in n for n in names),
                       road_wheels=sum("RoadWheel" in n for n in names))
    # verify exported bounds against the Blender report
    allv = np.vstack([trimesh.transform_points(g.vertices, M) for g, M in items])
    counts[tag]["glb_bounds_min"] = allv.min(0).round(3).tolist()
    counts[tag]["glb_bounds_max"] = allv.max(0).round(3).tolist()
    counts[tag]["glb_triangles"] = int(sum(len(g.faces) for g, M in items))
    rep = REP[tag]
    figx = rep["hull_rear_x"] - 1.0
    figy = -(rep["overall_width"] / 2 + 0.9)
    rep["cupola_height"] = rep["cupola_height"]
    fig_items, _ = load_glb(FIG, offset=(figx, figy, 0))
    allit = items + fig_items
    t["fig"] = (figx, figy)

    w, h = SIDE["x1"] - SIDE["x0"], SIDE["z1"] - SIDE["z0"]
    cx, cz = (SIDE["x0"] + SIDE["x1"]) / 2, (SIDE["z0"] + SIDE["z1"]) / 2
    views[(tag, "side")] = with_edges(*render(allit, look_at((cx, -60, cz), (cx, 0, cz)), w, h,
                                              light_dirs=[((-0.3, -1.0, 0.8), 3.0), ((0.5, -0.4, -0.2), 0.8)]))
    w, h = FRONT["y1"] - FRONT["y0"], FRONT["z1"] - FRONT["z0"]
    cz = (FRONT["z0"] + FRONT["z1"]) / 2
    views[(tag, "front")] = with_edges(*render(allit, look_at((60, 0, cz), (0, 0, cz)), w, h,
                                               light_dirs=[((1.0, 0.4, 0.8), 3.0), ((0.4, -0.8, -0.2), 0.8)]))
    w, h = TOP["x1"] - TOP["x0"], TOP["y1"] - TOP["y0"]
    cx = (TOP["x0"] + TOP["x1"]) / 2
    views[(tag, "top")] = with_edges(*render(allit, look_at((cx, 0, 60), (cx, 0, 0), up=(0, 1, 0)), w, h,
                                             light_dirs=[((-0.4, 0.5, 1.0), 3.0), ((0.5, -0.5, 0.6), 0.9)]))
    d = np.array([1.0, -1.15, 0.75]); d /= np.linalg.norm(d)
    tgt = np.array([0.6, 0, 1.2])
    views[(tag, "34")] = with_edges(*render(allit, look_at(tgt + d * 60, tgt), 14.5, 7.6, ground=True,
                                            light_dirs=[((0.3, -1.0, 1.2), 3.2), ((1.0, 0.6, 0.5), 1.0)]), depth_jump=0.10)

for (tag, v), (img, mask) in views.items():
    img.save(os.path.join(REN, f"{tag}_{v}.png"))
json.dump(counts, open(os.path.join(OUT, "glb_inspection.json"), "w"), indent=2)
print(json.dumps(counts, indent=1))

# ------------------------------------------------------------------ comparison sheet
INK = (30, 30, 30); SOFT = (150, 150, 150); ACC = (150, 60, 30); BLUE = (40, 80, 140)

def px_side(x, z): return ((x - SIDE["x0"]) * PPM, (SIDE["z1"] - z) * PPM)

def annotate_side(img, tag):
    rep = REP[tag]
    d = ImageDraw.Draw(img)
    W, H = img.size
    # ground line and 1 m ticks
    gx0, gy = px_side(SIDE["x0"], 0)
    d.line([(0, gy), (W, gy)], fill=INK, width=1)
    for m in range(int(math.ceil(SIDE["x0"])), int(SIDE["x1"]) + 1):
        x, _ = px_side(m, 0)
        d.line([(x, gy), (x, gy + (8 if m % 5 == 0 else 4))], fill=INK)
    f = font(13)
    # overall length (hull rear -> muzzle)
    xr, xm = rep["hull_rear_x"], rep["muzzle_x"]
    ya = gy + 22
    a, _ = px_side(xr, 0); b, _ = px_side(xm, 0)
    d.line([(a, ya), (b, ya)], fill=ACC, width=1); d.line([(a, ya - 5), (a, ya + 5)], fill=ACC); d.line([(b, ya - 5), (b, ya + 5)], fill=ACC)
    d.text(((a + b) / 2, ya + 3), f"{rep['overall_length_gun_fwd']:.2f} m  gun forward", font=f, fill=ACC, anchor="mt")
    # hull length
    xh = xr + rep["hull_length"]
    ya2 = gy + 44
    c, _ = px_side(xh, 0)
    d.line([(a, ya2), (c, ya2)], fill=BLUE); d.line([(a, ya2 - 5), (a, ya2 + 5)], fill=BLUE); d.line([(c, ya2 - 5), (c, ya2 + 5)], fill=BLUE)
    d.text(((a + c) / 2, ya2 + 3), f"hull {rep['hull_length']:.2f} m", font=f, fill=BLUE, anchor="mt")
    # height to cupola
    xx, ytop = px_side(SIDE["x1"] - 0.55, rep["cupola_height"])
    d.line([(xx, gy), (xx, ytop)], fill=ACC); d.line([(xx - 5, ytop), (xx + 5, ytop)], fill=ACC)
    d.line([(px_side(-2.5, 0)[0], ytop), (xx, ytop)], fill=(225, 190, 175))
    d.text((xx - 6, (gy + ytop) / 2), f"{rep['cupola_height']:.2f} m\ncupola", font=f, fill=ACC, anchor="rm")
    return img

def pad(img, top=0, bottom=0, left=0, right=0):
    out = Image.new("RGB", (img.width + left + right, img.height + top + bottom), "white")
    out.paste(img, (left, top)); return out

def label(img, text, sub=None):
    out = pad(img, top=46)
    d = ImageDraw.Draw(out)
    d.text((10, 8), text, font=font(18, True), fill=INK)
    if sub: d.text((10, 30), sub, font=font(12), fill=(100, 100, 100))
    return out

def stack(imgs, gap=16, horizontal=False):
    if horizontal:
        W = sum(i.width for i in imgs) + gap * (len(imgs) - 1); H = max(i.height for i in imgs)
    else:
        W = max(i.width for i in imgs); H = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGB", (W, H), "white"); p = 0
    for i in imgs:
        out.paste(i, (p, 0) if horizontal else (0, p)); p += (i.width if horizontal else i.height) + gap
    return out

sides = []
for tag, t in TANKS.items():
    img = pad(views[(tag, "side")][0], bottom=64)
    img = annotate_side(img, tag)
    sides.append(label(img, f"{t['label']}  —  right side", "orthographic, 80 px = 1 m; figure 1.80 m"))

# silhouette overlay, aligned at hull rear (x=0 at each hull's rear plate)
mk = views[("KS_B", "side")][1]; mb = views[("M12A2", "side")][1]
def shift_mask(mask, dx_m):
    m = Image.fromarray((mask * 255).astype(np.uint8)).resize((mask.shape[1] // SS, mask.shape[0] // SS))
    a = np.array(m) > 127
    s = int(round(dx_m * PPM))
    out = np.zeros_like(a)
    if s >= 0: out[:, s:] = a[:, :a.shape[1] - s]
    else: out[:, :s] = a[:, -s:]
    return out
# remove the figures from the masks so only vehicles compare
def strip_fig(mask, tag):
    m = mask.copy(); fx = TANKS[tag]["fig"][0]
    x0 = int((fx - 0.5 - SIDE["x0"]) * PPM * SS); x1 = int((fx + 0.5 - SIDE["x0"]) * PPM * SS)
    m[:, max(x0, 0):x1] = False; return m
A = shift_mask(strip_fig(mk, "KS_B"), -REP["KS_B"]["hull_rear_x"] - 4.6)
Bm = shift_mask(strip_fig(mb, "M12A2"), -REP["M12A2"]["hull_rear_x"] - 4.6)
ov = np.full(A.shape + (3,), 255, np.uint8)
ov[A & ~Bm] = (205, 150, 120); ov[Bm & ~A] = (120, 150, 205); ov[A & Bm] = (175, 175, 175)
ovimg = Image.fromarray(ov)
edge = lambda m: np.array(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)) > 0
arr = np.array(ovimg); arr[edge(A)] = (150, 60, 30); arr[edge(Bm)] = (40, 80, 140)
ovimg = pad(Image.fromarray(arr), bottom=20)
d = ImageDraw.Draw(ovimg)
gy = (SIDE["z1"]) * PPM
d.line([(0, gy), (ovimg.width, gy)], fill=INK)
d.text((ovimg.width - 10, gy + 4), "orange = Kaisersturm B only   blue = Bastion only   gray = both   (aligned at hull rear plate)",
       font=font(12), fill=INK, anchor="ra")
ovimg = label(ovimg, "SIDE SILHOUETTE OVERLAY", "same scale; shape, not size, has to separate them")

fronts = stack([label(views[(t, "front")][0], f"{TANKS[t]['label']}  —  front") for t in TANKS], horizontal=True, gap=30)
tops = stack([label(views[(t, "top")][0], f"{TANKS[t]['label']}  —  top (front to the right)") for t in TANKS])
sheet1 = stack([sides[0], sides[1], ovimg])
sheet1 = pad(sheet1, top=70, left=20, right=20, bottom=20)
dd = ImageDraw.Draw(sheet1)
dd.text((20, 14), "WELTENBRECHER — STAGE 2 FUNCTIONAL DETAIL", font=font(24, True), fill=INK)
dd.text((20, 46), "Flat gray review render from exported GLBs. Production-design concept; not a mass, armour or engineering validation.", font=font(13), fill=(90, 90, 90))
sheet1.save(os.path.join(REN, "sheet_A_side_comparison.png"))
sheet2 = pad(stack([fronts, tops], gap=24), top=20, left=20, right=20, bottom=20)
sheet2.save(os.path.join(REN, "sheet_B_front_top.png"))
q = stack([label(views[(t, "34")][0], f"{TANKS[t]['label']}  —  three-quarter (orthographic)") for t in TANKS])
pad(q, top=20, left=20, right=20, bottom=20).save(os.path.join(REN, "sheet_C_three_quarter.png"))
print("done")

# ------------------------------------------------------------------ Stage 2 detail sheet
DPPM = 120
detail = {}
for tag, t in TANKS.items():
    items_open, _ = load_glb(os.path.join(OUT, t["glb_open"]))
    items, _ = load_glb(os.path.join(OUT, t["glb"]))
    rep = REP[tag]
    fx = rep["hull_rear_x"] + 1.2
    fig_items, _ = load_glb(FIG, offset=(1.2, -(rep["overall_width"] / 2 + 0.7), 0))
    d = np.array([1.0, -1.0, 0.95]); d /= np.linalg.norm(d); tgt = np.array([1.0, 0, 1.9])
    detail[(tag, "front_open")] = with_edges(*render(items_open + fig_items, look_at(tgt + d * 60, tgt), 8.0, 5.0, ground=True, ppm=DPPM,
                                             light_dirs=[((0.4, -1.0, 1.2), 3.2), ((1.0, 0.6, 0.5), 1.0)]), depth_jump=0.06)
    d = np.array([-1.0, 1.1, 0.9]); d /= np.linalg.norm(d); tgt = np.array([-2.2, 0, 1.6])
    detail[(tag, "rear")] = with_edges(*render(items_open, look_at(tgt + d * 60, tgt), 8.0, 5.0, ground=True, ppm=DPPM,
                                       light_dirs=[((-0.8, 1.0, 1.2), 3.2), ((1.0, 0.4, 0.6), 1.0)]), depth_jump=0.06)
    tgt = np.array([-0.4, 0, 0])
    detail[(tag, "roof")] = with_edges(*render(items_open, look_at((tgt[0], 0, 60), tgt, up=(0, 1, 0)), 9.0, 4.6, ppm=DPPM,
                                       light_dirs=[((-0.4, 0.5, 1.0), 3.0), ((0.5, -0.5, 0.6), 0.9)]), depth_jump=0.05)
for (tag, v), (img, mask) in detail.items():
    img.save(os.path.join(REN, f"{tag}_{v}.png"))
rows = []
for tag, t in TANKS.items():
    a = label(detail[(tag, "front_open")][0], f"{t['label']}  —  hatches, lids and doors open", "front three-quarter, 120 px = 1 m")
    b = label(detail[(tag, "rear")][0], f"{t['label']}  —  rear: engine deck, exhausts, tow gear", "rear three-quarter, hatches open")
    rows.append(stack([a, b], horizontal=True, gap=24))
    rows.append(label(detail[(tag, "roof")][0], f"{t['label']}  —  top, hatches open", "front to the right"))
sheet4 = pad(stack(rows, gap=24), top=20, left=20, right=20, bottom=20)
sheet4.save(os.path.join(REN, "sheet_D_stage2_detail.png"))
print("detail done")

# ------------------------------------------------------------------ Stage 2 revision 1 sheet
# .50 operated from the cupola (figure standing in the hatch), dischargers and lights, track pins.
RC = PRM["stage2"]["bastion_m12a2"]["roof_mg_reach_check"]
CL = REP["clearances"]
rev = {}
EP = 0.03
bs_open, _ = load_glb(os.path.join(OUT, TANKS["M12A2"]["glb_open"]))
bs_closed, _ = load_glb(os.path.join(OUT, TANKS["M12A2"]["glb"]))
ks_closed, _ = load_glb(os.path.join(OUT, TANKS["KS_B"]["glb"]))
B_ = PRM["bastion_m12a2"]; zr_b = B_["hull"]["roof_z"]
cup = B_["cupola"]; lid_top = B_["envelope"]["cupola_height"]["value"] - 0.06
feet_z = lid_top + RC["shoulder_above_hatch_top_m"] - 1.45          # figure's shoulders sit ~1.45 m above its feet
cdr, _ = load_glb(FIG, offset=(B_["turret"]["ring_centre_x"] + cup["rel_x"], cup["rel_y"], feet_z))
d = np.array([-1.0, -1.25, 0.9]); d /= np.linalg.norm(d); tgt = np.array([-0.15, -0.3, 3.0])
rev["mg"] = with_edges(*render(bs_open + cdr, look_at(tgt + d * 60, tgt), 4.0, 3.0, ppm=240,
                               light_dirs=[((-0.6, -1.0, 1.2), 3.2), ((1.0, 0.5, 0.6), 1.0)]), depth_jump=EP)
tgt = np.array([-0.3, 0, 0])
rev["mg_top"] = with_edges(*render(bs_open + cdr, look_at((tgt[0], 0, 60), tgt, up=(0, 1, 0)), 4.2, 3.2, ppm=228,
                                   light_dirs=[((-0.4, 0.5, 1.0), 3.0), ((0.5, -0.5, 0.6), 0.9)]), depth_jump=EP)
for tag, items_, tgt_ in (("KS_B", ks_closed, (2.0, 0, 1.8)), ("M12A2", bs_closed, (1.8, 0, 1.8))):
    d = np.array([1.0, -1.15, 0.65]); d /= np.linalg.norm(d); tgt = np.array(tgt_)
    rev[(tag, "front")] = with_edges(*render(items_, look_at(tgt + d * 60, tgt), 6.0, 4.0, ground=True, ppm=160,
                                             light_dirs=[((0.4, -1.0, 1.2), 3.2), ((1.0, 0.6, 0.5), 1.0)]), depth_jump=EP)
for tag, items_ in (("KS_B", ks_closed), ("M12A2", bs_closed)):
    RG = PRM[TANKS[tag]["key"]]["running_gear"]
    d = np.array([1.0, -0.55, 0.3]); d /= np.linalg.norm(d)
    tgt = np.array([RG["idler"]["x"] - 0.1, -RG["track_centre_y"], 0.5])
    rev[(tag, "track")] = with_edges(*render(items_, look_at(tgt + d * 60, tgt), 2.4, 1.6, ground=True, ppm=400,
                                             light_dirs=[((0.4, -1.0, 1.0), 3.2), ((1.0, 0.3, 0.3), 1.0)]), depth_jump=0.02)
for k, (img, mask) in rev.items():
    img.save(os.path.join(REN, ("rev1_" + ("_".join(k) if isinstance(k, tuple) else k)) + ".png"))
mg = CL["M12A2"]["roof_mg50"]; rc = mg["reach_from_hatches"]["Cupola"]["shoulder_to_grips_m"]
rows = [stack([label(rev["mg"][0], "M12A2 BASTION  —  .50 worked from the cupola (Rev. 1: moved forward)",
                     f"1.80 m figure standing in the open cupola; shoulder to grips {rc:.2f} m (rule: within {RC['max_reach_m']} m)"),
               label(rev["mg_top"][0], "M12A2 BASTION  —  turret roof, hatches open", "front to the right; pintle beside the cupola, clear of both lids")],
              horizontal=True, gap=24),
        stack([label(rev[("KS_B", "front")][0], "KAISERSTURM AUSF. B  —  dischargers and headlights",
                     "smoke cups on the turret cheeks, gas cups (banded) on the sides; hooded headlights"),
               label(rev[("M12A2", "front")][0], "M12A2 BASTION  —  dischargers and headlights",
                     "common cup design, smoke forward bank, gas (banded) side bank; guarded lights")], horizontal=True, gap=24),
        stack([label(rev[("KS_B", "track")][0], "KAISERSTURM AUSF. B  —  dry-pin track", "hinge knuckles and pin heads, 400 px = 1 m"),
               label(rev[("M12A2", "track")][0], "M12A2 BASTION  —  double-pin track", "end connectors with wedge bolts, 400 px = 1 m")],
              horizontal=True, gap=24)]
pad(stack(rows, gap=24), top=20, left=20, right=20, bottom=20).save(os.path.join(REN, "sheet_E_stage2_rev1.png"))
print("rev1 done")
