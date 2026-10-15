"""
Weltenbrecher - Stage 1 measured blockouts (Kaisersturm Ausf. B, M12A2 Bastion).

Run:  python3 generate.py [params.json] [out_dir]
Needs Blender's Python module (pip install bpy).

Conventions: metres, +X forward, +Y vehicle left, +Z up, origin at hull centre on the
ground plane. Every tank is one hierarchy:
  <TAG>_Root
    Hull, Hull_* details, Turret_Ring (marker)
    Turret_Pivot (empty at the vertical traverse axis, z = hull roof)
      Turret, Cupola, Hatch_*
      Gun_Pivot (empty at the trunnion axis)
        Mantlet, Barrel
    RunningGear_L / _R (empties) -> wheels, arms or bogie modules, sprocket, idler, rollers
    Track_L / _R (empties) -> instanced links (shared mesh data)
    Skirt_* (Kaisersturm only, removable panels)
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
import numpy as np
from scipy.spatial import ConvexHull

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "params.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
P = json.load(open(PARAMS))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# ------------------------------------------------------------------ materials
def make_mat(name, rgb, rough=0.85):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    m.diffuse_color = (*rgb, 1.0)
    return m

MAT = {
    "armor":   make_mat("Blockout_Armor_Gray",   (0.42, 0.42, 0.42)),
    "running": make_mat("Blockout_Running_Gray", (0.20, 0.20, 0.20)),
    "detail":  make_mat("Blockout_Detail_Gray",  (0.30, 0.30, 0.30)),
    "figure":  make_mat("Reference_Figure",      (0.70, 0.62, 0.50)),
    "ground":  make_mat("Reference_Ground",      (0.75, 0.75, 0.75)),
}

# ------------------------------------------------------------------ helpers
def new_coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c

def finish_mesh(name, bm, coll, mat, parent=None, loc=(0, 0, 0), recalc=True):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = loc
    if parent:
        ob.parent = parent
    return ob

def instance(name, mesh, coll, parent=None, matrix=None, loc=None):
    ob = bpy.data.objects.new(name, mesh)  # shares mesh data -> instanced
    coll.objects.link(ob)
    if parent:
        ob.parent = parent
    if matrix is not None:
        ob.matrix_basis = matrix
    if loc is not None:
        ob.location = loc
    return ob

def empty(name, coll, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = 0.3
    coll.objects.link(e)
    e.location = loc
    if parent:
        e.parent = parent
    return e

def bm_prism_xz(bm, profile, hw_fn):
    """Extrude an XZ profile symmetric about y=0; half width may vary linearly with z."""
    L = [bm.verts.new((x, hw_fn(z), z)) for x, z in profile]
    R = [bm.verts.new((x, -hw_fn(z), z)) for x, z in profile]
    n = len(profile)
    bm.faces.new(L)
    bm.faces.new(list(reversed(R)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((L[i], L[j], R[j], R[i]))

def bm_loft(bm, rings, cap=True):
    """rings: list of lists of 3D points (same count, same winding)."""
    V = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(V[:-1], V[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap:
        bm.faces.new(list(reversed(V[0])))
        bm.faces.new(V[-1])

def bm_lathe(bm, profile, seg=32, axis='X', center=(0, 0, 0)):
    """profile: [(a, r)] along axis; r == 0 collapses to an axis vertex. Closed if ends on axis."""
    cx, cy, cz = center
    rings = []
    for a, r in profile:
        if r <= 1e-9:
            if axis == 'X': p = (cx + a, cy, cz)
            elif axis == 'Y': p = (cx, cy + a, cz)
            else: p = (cx, cy, cz + a)
            rings.append([bm.verts.new(p)])
            continue
        ring = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            u, v = r * math.cos(t), r * math.sin(t)
            if axis == 'X': p = (cx + a, cy + u, cz + v)
            elif axis == 'Y': p = (cx + u, cy + a, cz + v)
            else: p = (cx + u, cy + v, cz + a)
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for A, B in zip(rings[:-1], rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for k in range(seg):
                bm.faces.new((A[0], B[k], B[(k + 1) % seg]))
        elif len(B) == 1:
            for k in range(seg):
                bm.faces.new((A[k], B[0], A[(k + 1) % seg]))
        else:
            for k in range(seg):
                bm.faces.new((A[k], A[(k + 1) % seg], B[(k + 1) % seg], B[k]))

def octagon(cx, cy, hx, hy, c, z):
    return [(cx + hx, cy - hy + c, z), (cx + hx, cy + hy - c, z), (cx + hx - c, cy + hy, z),
            (cx - hx + c, cy + hy, z), (cx - hx, cy + hy - c, z), (cx - hx, cy - hy + c, z),
            (cx - hx + c, cy - hy, z), (cx + hx - c, cy - hy, z)]

def bm_chamfer_box(bm, center, size, c):
    cx, cy, cz = center; sx, sy, sz = size
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    c = min(c, hx * 0.9, hy * 0.9, hz * 0.9)
    rings = [octagon(cx, cy, hx - c, hy - c, c * 0.5, cz - hz),
             octagon(cx, cy, hx, hy, c, cz - hz + c),
             octagon(cx, cy, hx, hy, c, cz + hz - c),
             octagon(cx, cy, hx - c, hy - c, c * 0.5, cz + hz)]
    bm_loft(bm, rings)

def bm_box(bm, mn, mx):
    (x0, y0, z0), (x1, y1, z1) = mn, mx
    v = [bm.verts.new(p) for p in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                     (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([v[i] for i in f])

def bm_beam_xz(bm, p0, p1, y0, y1, th):
    """Rectangular bar between two XZ points, spanning y0..y1, thickness th in the XZ plane."""
    (x0, z0), (x1, z1) = p0, p1
    d = np.array([x1 - x0, z1 - z0]); d /= np.linalg.norm(d)
    n = np.array([-d[1], d[0]]) * th / 2
    quad = [(x0 + n[0], z0 + n[1]), (x1 + n[0], z1 + n[1]), (x1 - n[0], z1 - n[1]), (x0 - n[0], z0 - n[1])]
    A = [bm.verts.new((x, y0, z)) for x, z in quad]
    B = [bm.verts.new((x, y1, z)) for x, z in quad]
    bm.faces.new(A); bm.faces.new(list(reversed(B)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((A[i], A[j], B[j], B[i]))

def chaikin(pts, it=2):
    P_ = np.array(pts, float)
    for _ in range(it):
        Q = []
        for i in range(len(P_)):
            a, b = P_[i], P_[(i + 1) % len(P_)]
            Q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
        P_ = np.array(Q)
    return P_

def radial_ring(plan, centre, inset, z, clamp=None):
    out = []
    c = np.array(centre)
    for p in plan:
        v = p - c; r = np.linalg.norm(v)
        rr = max(r - inset, 0.05)
        if clamp is not None:
            rr = min(rr, clamp)
        q = c + v / r * rr
        out.append((q[0], q[1], z))
    return out

GROUSER = 0.025   # grouser height; wheels are lifted by this so grouser tips rest on z = 0

# ------------------------------------------------------------------ track geometry
def track_loop(circles, t, pitch):
    """circles: [(x, z, r)] the track wraps (wheels touch the inner face).
    Returns link poses on the track centreline as (x, z, dx, dz), CCW in XZ."""
    pts = []
    for x, z, r in circles:
        R = r + t / 2
        for k in range(96):
            a = 2 * math.pi * k / 96
            pts.append((x + R * math.cos(a), z + R * math.sin(a)))
    pts = np.array(pts)
    hull = ConvexHull(pts)
    loop = pts[hull.vertices]               # CCW for 2D
    seg = np.diff(np.vstack([loop, loop[:1]]), axis=0)
    seglen = np.linalg.norm(seg, axis=1)
    per = seglen.sum()
    n = int(round(per / pitch))
    step = per / n
    cum = np.concatenate([[0], np.cumsum(seglen)])
    out = []
    for i in range(n):
        s = i * step
        k = np.searchsorted(cum, s, side='right') - 1
        f = (s - cum[k]) / seglen[k]
        p = loop[k] + f * seg[k]
        # tangent from a small central difference along the loop
        s2 = (s + step * 0.5) % per; s1 = (s - step * 0.5) % per
        def at(sv):
            kk = np.searchsorted(cum, sv, side='right') - 1
            ff = (sv - cum[kk]) / seglen[kk]
            return loop[kk] + ff * seg[kk]
        d = at(s2) - at(s1); d /= np.linalg.norm(d)
        out.append((p[0], p[1], d[0], d[1]))
    return out, per, step

def link_mesh(name, pitch, width, t, horn_w, horn_h, grouser_h):
    bm = bmesh.new()
    L = pitch * 0.46
    bm_box(bm, (-L, -width / 2, -t / 2), (L, width / 2, t / 2))              # shoe
    bm_box(bm, (-0.025, -width / 2 + 0.02, t / 2), (0.025, width / 2 - 0.02, t / 2 + grouser_h))  # grouser (outer)
    bm_box(bm, (-L * 0.55, -horn_w / 2, -t / 2 - horn_h), (L * 0.55, horn_w / 2, -t / 2))      # guide horn (inner)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(MAT["running"])
    return me

def build_tracks(tag, coll, root, circles, rg, side):
    t, pitch = rg["track_thickness"], rg["track_pitch"]
    width = P_tank["envelope"]["track_width"]["value"]
    if f"{tag}_TrackLink" not in bpy.data.meshes:
        link_mesh(f"{tag}_TrackLink", pitch, width, t, 0.06, 0.09, GROUSER)
    me = bpy.data.meshes[f"{tag}_TrackLink"]
    sgn = 1 if side == "L" else -1
    yc = sgn * rg["track_centre_y"]
    parent = empty(f"{tag}_Track_{side}", coll, root)
    poses, per, step = track_loop(circles, t, pitch)
    for i, (x, z, dx, dz) in enumerate(poses):
        X = Vector((dx, 0, dz)); Z = Vector((dz, 0, -dx)); Y = Z.cross(X)
        M = Matrix((X, Y, Z)).transposed().to_4x4()
        M.translation = (x, yc, z)
        instance(f"{tag}_TrackLink_{side}_{i:03d}", me, coll, parent, matrix=M)
    return len(poses), per, step

# ------------------------------------------------------------------ wheels
def double_wheel_mesh(name, r, th, off, hub_r=0.16, axle_r=0.06, seg=32):
    bm = bmesh.new()
    for s in (-1, 1):
        a0, a1 = s * off - th / 2, s * off + th / 2
        prof = [(a0, 0.0), (a0, hub_r), (a0 + 0.035, hub_r + 0.02), (a0 + 0.035, r - 0.07),
                (a0, r - 0.055), (a0, r), (a1, r), (a1, r - 0.055), (a1 - 0.035, r - 0.07),
                (a1 - 0.035, hub_r + 0.02), (a1, hub_r), (a1, 0.0)]
        bm_lathe(bm, prof, seg, 'Y')
    bm_lathe(bm, [(-off, 0.0), (-off, axle_r), (off, axle_r), (off, 0.0)], 12, 'Y')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(MAT["running"])
    return me

def sprocket_mesh(name, r, off, teeth=13, th=0.07):
    bm = bmesh.new()
    for s in (-1, 1):
        prof = []
        for k in range(teeth * 2):
            a = math.pi * k / teeth
            rr = r + (0.045 if k % 2 == 0 else -0.01)
            prof.append((rr * math.cos(a), rr * math.sin(a)))
        A = [bm.verts.new((x, s * off - th / 2, z)) for x, z in prof]
        B = [bm.verts.new((x, s * off + th / 2, z)) for x, z in prof]
        bm.faces.new(A); bm.faces.new(list(reversed(B)))
        n = len(prof)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((A[i], A[j], B[j], B[i]))
        bm_lathe(bm, [(s * off - 0.10, 0.0), (s * off - 0.10, r * 0.55), (s * off + 0.10, r * 0.55), (s * off + 0.10, 0.0)], 24, 'Y')
    bm_lathe(bm, [(-off, 0.0), (-off, 0.12), (off, 0.12), (off, 0.0)], 16, 'Y')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(MAT["running"])
    return me

# ------------------------------------------------------------------ scale figure
def build_figure(coll, loc):
    bm = bmesh.new()
    H = P["scale_figure_height"]
    # legs
    for y in (-0.10, 0.10):
        bm_lathe(bm, [(0.0, 0.0), (0.0, 0.075), (0.86, 0.07), (0.86, 0.0)], 12, 'Z', (0, y, 0))
    # torso
    bm_lathe(bm, [(0.84, 0.0), (0.84, 0.17), (1.10, 0.19), (1.42, 0.21), (1.50, 0.12), (1.50, 0.0)], 16, 'Z', (0, 0, 0))
    # arms
    for y in (-0.27, 0.27):
        bm_lathe(bm, [(0.80, 0.0), (0.80, 0.05), (1.44, 0.055), (1.46, 0.0)], 10, 'Z', (0, y, 0))
    # neck + head (top of head = H)
    bm_lathe(bm, [(1.48, 0.0), (1.48, 0.05), (1.56, 0.05), (1.56, 0.0)], 10, 'Z')
    head = [(H - 0.24 + 0.24 * (1 - math.cos(a)) / 2, 0.11 * math.sin(a)) for a in np.linspace(0, math.pi, 9)]
    head = [(z, r) for z, r in head]
    bm_lathe(bm, [(head[0][0], 0.0)] + head[1:-1] + [(head[-1][0], 0.0)], 14, 'Z')
    ob = finish_mesh("Scale_Figure_1p80m", bm, coll, MAT["figure"], loc=loc)
    ob["note"] = "Neutral 1.80 m reference figure, top of head at z = 1.80"
    return ob

# ================================================================== KAISERSTURM B
def build_kaisersturm():
    global P_tank
    P_tank = K = P["kaisersturm_b"]
    tag = "KS_B"
    coll = new_coll(tag)
    root = empty(f"{tag}_Root", coll)
    E, Hh, RG, T, G = K["envelope"], K["hull"], K["running_gear"], K["turret"], K["gun"]
    HL = E["hull_length"]["value"]; xr, xf = -HL / 2, HL / 2

    # --- hull: lower tub between the tracks + full-width upper hull over the tracks
    gx = Hh["glacis_top_x"]; zr = Hh["roof_z"]; zf = Hh["sponson_floor_z"]; zn = Hh["nose_z"]
    x_glacis_at_floor = xf - (zf - zn) / (zr - zn) * (xf - gx)
    lower = [(xr + 0.05, 0.58), (xr + 0.25, Hh["belly_z"]), (Hh["lower_glacis_start_x"], Hh["belly_z"]),
             (xf, zn), (x_glacis_at_floor, zf), (xr, zf)]
    upper = [(xr, zf), (x_glacis_at_floor, zf), (gx, zr), (xr + 0.15, zr), (xr, zr - 0.20)]
    bm = bmesh.new()
    bm_prism_xz(bm, lower, lambda z: Hh["lower_half_width"])
    w0, w1 = Hh["upper_half_width_at_floor"], Hh["upper_half_width_at_roof"]
    bm_prism_xz(bm, upper, lambda z: w0 + (w1 - w0) * (z - zf) / (zr - zf))
    hull = finish_mesh(f"{tag}_Hull", bm, coll, MAT["armor"], root)
    hull["includes"] = "hull armour shell (upper + lower), no fittings"
    hull["glacis_line"] = [xf, zn, gx, zr]
    # exhausts: low armoured cowls on the rear deck venting rearward, kept inside the hull length
    bm = bmesh.new()
    for s in (-1, 1):
        bm_chamfer_box(bm, (xr + 0.32, s * 0.62, zr + 0.09), (0.40, 0.36, 0.18), 0.04)
        bm_lathe(bm, [(0.0, 0.0), (0.0, 0.085), (-0.16, 0.085), (-0.16, 0.06), (-0.02, 0.06), (-0.02, 0.0)], 16, 'X', (xr + 0.17, s * 0.62, zr + 0.09))
    finish_mesh(f"{tag}_Exhausts", bm, coll, MAT["detail"], root)

    # --- running gear
    yc = RG["track_centre_y"]; rw = RG["road_wheel_radius"]; t = RG["track_thickness"]
    zc = rw + t + GROUSER
    xs = list(np.linspace(RG["first_station_x"], RG["last_station_x"], RG["stations_per_side"]))
    wheel_me = double_wheel_mesh(f"{tag}_RoadWheel_Double", rw, RG["disc_thickness"], RG["double_wheel_offset"])
    spr = RG["sprocket"]; idl = RG["idler"]
    spr_me = sprocket_mesh(f"{tag}_Sprocket", spr["r"], RG["double_wheel_offset"])
    idl_me = double_wheel_mesh(f"{tag}_Idler", idl["r"], RG["disc_thickness"], RG["double_wheel_offset"], hub_r=0.14)
    # return rollers sit under the top run (line between sprocket top and idler top)
    def top_run_z(x):
        za = spr["z"] + spr["r"] + t / 2; zb = idl["z"] + idl["r"] + t / 2
        return za + (zb - za) * (x - spr["x"]) / (idl["x"] - spr["x"])
    rr = RG["return_roller_r"]
    rol_me = double_wheel_mesh(f"{tag}_ReturnRoller", rr, 0.12, RG["double_wheel_offset"], hub_r=0.06, axle_r=0.04, seg=20)
    arm_me = None
    for side, s in (("L", 1), ("R", -1)):
        rgp = empty(f"{tag}_RunningGear_{side}", coll, root)
        for i, x in enumerate(xs):
            instance(f"{tag}_RoadWheel_{side}{i + 1}", wheel_me, coll, rgp, loc=(x, s * yc, zc))
            # torsion-bar trailing arm: pivot ahead of the wheel, on the hull side
            bm = bmesh.new()
            y0, y1 = (Hh["lower_half_width"] + 0.01, yc - RG["double_wheel_offset"] - RG["disc_thickness"] / 2 - 0.03)
            if s < 0: y0, y1 = -y1, -y0
            bm_beam_xz(bm, (x + RG["arm_pivot_offset_x"], RG["arm_pivot_z"]), (x, zc), y0, y1, 0.13)
            bm_lathe(bm, [(0.0, 0.0), (0.0, 0.09), (0.10 * s, 0.09), (0.10 * s, 0.0)] if s > 0 else [(-0.10, 0.0), (-0.10, 0.09), (0.0, 0.09), (0.0, 0.0)],
                     12, 'Y', (x + RG["arm_pivot_offset_x"], s * (Hh["lower_half_width"] + 0.02) - (0.0 if s > 0 else 0.0), RG["arm_pivot_z"]))
            finish_mesh(f"{tag}_SuspensionArm_{side}{i + 1}", bm, coll, MAT["running"], rgp)
        instance(f"{tag}_Sprocket_{side}", spr_me, coll, rgp, loc=(spr["x"], s * yc, spr["z"]))
        instance(f"{tag}_Idler_{side}", idl_me, coll, rgp, loc=(idl["x"], s * yc, idl["z"]))
        for j, x in enumerate(RG["return_rollers_x"]):
            zrr = top_run_z(x) - t / 2 - rr - 0.005
            instance(f"{tag}_ReturnRoller_{side}{j + 1}", rol_me, coll, rgp, loc=(x, s * yc, zrr))
        circles = [(x, zc, rw) for x in xs] + [(spr["x"], spr["z"], spr["r"]), (idl["x"], idl["z"], idl["r"])]
        nlinks, per, step = build_tracks(tag, coll, root, circles, RG, side)

    # --- skirts (removable panels) + hanger rail
    S = K["skirts"]
    edges = np.linspace(S["x_from"], S["x_to"], S["panels_per_side"] + 1)
    for side, s in (("L", 1), ("R", -1)):
        for i in range(S["panels_per_side"]):
            bm = bmesh.new()
            ya, yb = S["inner_y"], S["inner_y"] + S["thickness"]
            if s < 0: ya, yb = -yb, -ya
            bm_chamfer_box(bm, ((edges[i] + edges[i + 1]) / 2, (ya + yb) / 2, (S["bottom_z"] + S["top_z"]) / 2),
                           (edges[i + 1] - edges[i] - 0.03, S["thickness"], S["top_z"] - S["bottom_z"]), 0.015)
            ob = finish_mesh(f"{tag}_Skirt_{side}{i + 1}", bm, coll, MAT["armor"], root)
            ob["removable"] = True
        bm = bmesh.new()
        ya, yb = Hh["upper_half_width_at_floor"] - 0.005, S["inner_y"] + 0.005
        if s < 0: ya, yb = -yb, -ya
        bm_box(bm, (S["x_from"], ya, S["top_z"] - 0.16), (S["x_to"], yb, S["top_z"] - 0.04))
        finish_mesh(f"{tag}_SkirtRail_{side}", bm, coll, MAT["detail"], root)

    # --- turret
    tp = empty(f"{tag}_Turret_Pivot", coll, root, loc=(T["ring_centre_x"], 0, zr))
    tp["note"] = "Vertical traverse axis (turret ring centre) at hull roof height"
    bm = bmesh.new()
    zb, zt = T["base_gap"], T["base_gap"] + T["height"]
    bm_loft(bm, [[(x, y, zb) for x, y in T["plan_bottom"]], [(x, y, zt) for x, y in T["plan_top"]]])
    finish_mesh(f"{tag}_Turret", bm, coll, MAT["armor"], tp)
    bm = bmesh.new()
    rr_ = T["ring_diameter"] / 2
    bm_lathe(bm, [(-0.02, 0.0), (-0.02, rr_ + 0.06), (zb, rr_ + 0.06), (zb, 0.0)], 48, 'Z')
    ring = finish_mesh(f"{tag}_Turret_Ring", bm, coll, MAT["detail"], tp)
    ring["turret_ring_diameter_m"] = T["ring_diameter"]
    # cupola and turret hatches are built in stage2.py

    # --- gun
    gp = empty(f"{tag}_Gun_Pivot", coll, tp, loc=(G["trunnion_rel_x"], 0, G["trunnion_rel_z"]))
    gp["note"] = "Elevation axis (trunnion) - rotate about local Y"
    M_ = G["mantlet"]
    bm = bmesh.new()
    bm_chamfer_box(bm, ((M_["back"] + M_["front"]) / 2, 0, 0), (M_["front"] - M_["back"], 2 * M_["half_width"], 2 * M_["half_height"]), M_["chamfer"])
    finish_mesh(f"{tag}_Mantlet", bm, coll, MAT["armor"], gp)
    muzzle_world = xr + E["overall_length_gun_fwd"]["value"]
    a_m = muzzle_world - (T["ring_centre_x"] + G["trunnion_rel_x"])
    bore = E["main_gun_bore"]["value"] / 2
    prof = [(M_["front"] - 0.05, 0.0), (M_["front"] - 0.05, G["sleeve_r"]), (G["sleeve_to"], G["sleeve_r"]),
            (G["sleeve_to"] + 0.05, G["barrel_r_breech"]), (a_m - G["muzzle_swell_len"] - 0.05, G["barrel_r_muzzle"]),
            (a_m - G["muzzle_swell_len"], G["muzzle_swell_r"]), (a_m, G["muzzle_swell_r"]), (a_m, bore), (a_m - 0.5, bore), (a_m - 0.5, 0.0)]
    bm = bmesh.new(); bm_lathe(bm, prof, 28, 'X')
    finish_mesh(f"{tag}_Barrel", bm, coll, MAT["armor"], gp)
    return coll, root

# ================================================================== BASTION M12A2
def build_bastion():
    global P_tank
    P_tank = B = P["bastion_m12a2"]
    tag = "M12A2"
    coll = new_coll(tag)
    root = empty(f"{tag}_Root", coll)
    E, Hh, RG, T, G = B["envelope"], B["hull"], B["running_gear"], B["turret"], B["gun"]
    HL = E["hull_length"]["value"]; xr, xf = -HL / 2, HL / 2
    zr, zf, zn, gx = Hh["roof_z"], Hh["sponson_floor_z"], Hh["nose_z"], Hh["glacis_top_x"]
    zd, xs_ = Hh["engine_deck_z"], Hh["deck_step_x"]
    # Rounded cast nose: the lower and upper glacis lines meet at a virtual vertex V, which is
    # replaced by a fillet of radius nose_radius. V is pushed forward until the front of the
    # rounded nose lands exactly on the hull-length station xf, so hull length is unchanged.
    rn = Hh.get("nose_radius", 0.0)
    P0 = np.array([Hh["lower_glacis_start_x"], Hh["belly_z"]]); P2 = np.array([gx, zr])
    def fillet(xv, n=12):
        V = np.array([xv, zn])
        a = (P0 - V) / np.linalg.norm(P0 - V); b = (P2 - V) / np.linalg.norm(P2 - V)
        th = math.acos(np.clip(a @ b, -1, 1))
        d = rn / math.tan(th / 2)
        bis = (a + b) / np.linalg.norm(a + b)
        C = V + bis * rn / math.sin(th / 2)
        T1, T2 = V + a * d, V + b * d
        a1 = math.atan2(*(T1 - C)[::-1]); a2 = math.atan2(*(T2 - C)[::-1])
        if a2 < a1: a2 += 2 * math.pi
        arc = [tuple(C + rn * np.array([math.cos(t), math.sin(t)])) for t in np.linspace(a1, a2, n)]
        return arc, V
    if rn > 0:
        lo, hi = xf, xf + 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            arc, V = fillet(mid)
            if max(p[0] for p in arc) < xf: lo = mid
            else: hi = mid
        arc, V = fillet(hi)
        assert arc[-1][1] < zf - 0.02, "nose fillet runs above the sponson floor; reduce nose_radius"
    else:
        arc, V = [(xf, zn)], np.array([xf, zn])
    x_glacis_at_floor = V[0] - (zf - zn) / (zr - zn) * (V[0] - gx)
    lower = [(xr + 0.13, Hh["belly_z"]), (Hh["lower_glacis_start_x"], Hh["belly_z"])] + arc + \
            [(x_glacis_at_floor, zf), (xr, zf), (xr, 0.75)]
    upper = [(xr, zf), (x_glacis_at_floor, zf), (gx, zr), (xs_, zr), (xs_ - 0.10, zd), (xr + 0.13, zd), (xr, zd - 0.18)]
    bm = bmesh.new()
    bm_prism_xz(bm, lower, lambda z: Hh["lower_half_width"])
    w0, w1 = Hh["upper_half_width_at_floor"], Hh["upper_half_width_at_roof"]
    bm_prism_xz(bm, upper, lambda z: w0 + (w1 - w0) * (z - zf) / (zr - zf))
    hull = finish_mesh(f"{tag}_Hull", bm, coll, MAT["armor"], root)
    hull["includes"] = "hull armour shell (upper + lower), no fittings"
    hull["glacis_line"] = [float(V[0]), zn, gx, zr]
    # deck, rear doors and hatches are built in stage2.py

    # --- running gear: four paired bogie modules per side
    yc = RG["track_centre_y"]; rw = RG["road_wheel_radius"]; t = RG["track_thickness"]; zc = rw + t + GROUSER
    nb = RG["bogies_per_side"]; sp = RG["in_bogie_spacing"]
    first, last = RG["contact_first_x"], RG["contact_last_x"]
    bogie_x = list(np.linspace(first - sp / 2, last + sp / 2, nb))
    wheel_me = double_wheel_mesh(f"{tag}_RoadWheel_Double", rw, RG["disc_thickness"], RG["double_wheel_offset"], hub_r=0.13)
    spr, idl = RG["sprocket"], RG["idler"]
    spr_me = sprocket_mesh(f"{tag}_Sprocket", spr["r"], RG["double_wheel_offset"], teeth=12)
    idl_me = double_wheel_mesh(f"{tag}_Idler", idl["r"], RG["disc_thickness"], RG["double_wheel_offset"], hub_r=0.12)
    rr = RG["return_roller_r"]
    rol_me = double_wheel_mesh(f"{tag}_ReturnRoller", rr, 0.11, RG["double_wheel_offset"], hub_r=0.05, axle_r=0.04, seg=20)
    # bogie housing mesh (built for the left side, mirrored by scale for the right)
    yin = Hh["lower_half_width"] + 0.005
    yout = yc - RG["double_wheel_offset"] - RG["disc_thickness"] / 2 - 0.025
    bm = bmesh.new()
    wtop = zc + rw
    bm_chamfer_box(bm, (0.0, yin + 0.03, wtop + 0.06), (0.74, 0.06, 0.46), 0.02)              # bolted mounting plate
    hz0, hz1 = wtop + 0.03, wtop + 0.27
    bm_chamfer_box(bm, (0.0, (yin + 0.06 + yc + 0.20) / 2, (hz0 + hz1) / 2), (0.44, yc + 0.20 - yin - 0.06, hz1 - hz0), 0.04)  # spring housing over the pair
    for s_ in (-1, 1):
        bm_beam_xz(bm, (s_ * 0.12, hz0 + 0.02), (s_ * sp / 2, zc), yin + 0.06, yout, 0.10)      # wheel arms
        bm_lathe(bm, [(yin + 0.06, 0.0), (yin + 0.06, 0.07), (yc + RG["double_wheel_offset"] + RG["disc_thickness"] / 2 + 0.03, 0.07),
                      (yc + RG["double_wheel_offset"] + RG["disc_thickness"] / 2 + 0.03, 0.0)], 12, 'Y', (s_ * sp / 2, 0, zc))  # axle
    bogie_me = bpy.data.meshes.new(f"{tag}_Bogie_Housing_L")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(bogie_me); bm.free()
    bogie_me.materials.append(MAT["running"])
    # right-hand housing: a true mirrored mesh (no negative object scale, which some glTF viewers misplace)
    bogie_me_R = bogie_me.copy(); bogie_me_R.name = f"{tag}_Bogie_Housing_R"
    bogie_me_R.transform(Matrix.Scale(-1, 4, (0, 1, 0)))
    bogie_me_R.flip_normals()
    def top_run_z(x):
        za = spr["z"] + spr["r"] + t / 2; zb = idl["z"] + idl["r"] + t / 2
        return za + (zb - za) * (x - spr["x"]) / (idl["x"] - spr["x"])
    wheel_xs = []
    for side, s in (("L", 1), ("R", -1)):
        rgp = empty(f"{tag}_RunningGear_{side}", coll, root)
        for i, bx in enumerate(bogie_x):
            bmod = empty(f"{tag}_Bogie_{side}{i + 1}", coll, rgp, loc=(bx, 0, 0))
            bmod["module"] = "replaceable bogie module: housing + 2 road wheels"
            instance(f"{tag}_BogieHousing_{side}{i + 1}", bogie_me if s > 0 else bogie_me_R, coll, bmod)
            for k, dx in enumerate((sp / 2, -sp / 2)):
                instance(f"{tag}_RoadWheel_{side}{i + 1}{'ab'[k]}", wheel_me, coll, bmod, loc=(dx, s * yc, zc))
                if side == "L":
                    wheel_xs.append(bx + dx)
        instance(f"{tag}_Sprocket_{side}", spr_me, coll, rgp, loc=(spr["x"], s * yc, spr["z"]))
        instance(f"{tag}_Idler_{side}", idl_me, coll, rgp, loc=(idl["x"], s * yc, idl["z"]))
        for j, x in enumerate(RG["return_rollers_x"]):
            zrr = top_run_z(x) - t / 2 - rr - 0.005
            instance(f"{tag}_ReturnRoller_{side}{j + 1}", rol_me, coll, rgp, loc=(x, s * yc, zrr))
        circles = [(x, zc, rw) for x in sorted(set(round(w, 4) for w in wheel_xs))] + \
                  [(spr["x"], spr["z"], spr["r"]), (idl["x"], idl["z"], idl["r"])]
        build_tracks(tag, coll, root, circles, RG, side)

    # --- turret: rounded cast-looking body + defined rear bustle
    tp = empty(f"{tag}_Turret_Pivot", coll, root, loc=(T["ring_centre_x"], 0, zr))
    tp["note"] = "Vertical traverse axis (turret ring centre) at hull roof height"
    zb = T["base_gap"]; H = T["height"]; zt = zb + H
    ring_r = E["turret_ring_diameter"]["value"] / 2
    plan = chaikin(T["plan_body"], 3)
    c0 = (0.0, 0.0)
    rings = [radial_ring(plan, c0, 0.0, zb, clamp=ring_r + 0.095),    # undercut base, clears hull hatches
             radial_ring(plan, c0, 0.0, zb + 0.075, clamp=ring_r + 0.175),
             radial_ring(plan, c0, 0.10, zb + 0.20),
             radial_ring(plan, c0, 0.0, zb + 0.50),
             radial_ring(plan, c0, 0.07, zb + 0.82),
             radial_ring(plan, c0, 0.18, zb + 0.95),
             radial_ring(plan, c0, 0.34, zt)]
    bm = bmesh.new(); bm_loft(bm, rings)
    finish_mesh(f"{tag}_Turret", bm, coll, MAT["armor"], tp)
    bplan = chaikin(T["plan_bustle"], 2)
    cb = (-1.55, 0.0); bz = zb + T["bustle_bottom_rel_z"]
    rings = [radial_ring(bplan, cb, 0.10, bz), radial_ring(bplan, cb, 0.0, bz + 0.10),
             radial_ring(bplan, cb, 0.0, zb + 0.80), radial_ring(bplan, cb, 0.10, zb + 0.95),
             radial_ring(bplan, cb, 0.22, zt - 0.015)]
    bm = bmesh.new(); bm_loft(bm, rings)
    finish_mesh(f"{tag}_Turret_Bustle", bm, coll, MAT["armor"], tp)
    bm = bmesh.new()
    bm_lathe(bm, [(-0.02, 0.0), (-0.02, ring_r + 0.06), (zb, ring_r + 0.06), (zb, 0.0)], 48, 'Z')
    ring = finish_mesh(f"{tag}_Turret_Ring", bm, coll, MAT["detail"], tp)
    ring["turret_ring_diameter_m"] = E["turret_ring_diameter"]["value"]
    # cupola and turret hatches are built in stage2.py

    # --- gun: rounded mantlet, long 105, double-baffle brake (proposal)
    gp = empty(f"{tag}_Gun_Pivot", coll, tp, loc=(G["trunnion_rel_x"], 0, G["trunnion_rel_z"]))
    gp["note"] = "Elevation axis (trunnion) - rotate about local Y"
    arc = [(-0.15 + 0.45 * math.cos(a) * 0 + 0.0, 0.0) for a in []]
    mplan = [(-0.15, -0.54), (0.12, -0.54)] + [(0.12 + 0.20 * math.cos(a), 0.54 * math.sin(a)) for a in np.linspace(-math.pi / 2, math.pi / 2, 11)[1:-1]] + [(0.12, 0.54), (-0.15, 0.54)]
    def mring(inset, z):
        return [(x - (inset if x > 0.1 else 0), y * (1 - inset / 0.54), z) for x, y in mplan]
    bm = bmesh.new()
    bm_loft(bm, [mring(0.06, -0.31), mring(0.0, -0.24), mring(0.0, 0.24), mring(0.06, 0.31)])
    finish_mesh(f"{tag}_Mantlet", bm, coll, MAT["armor"], gp)
    muzzle_world = xr + E["overall_length_gun_fwd"]["value"]
    a_m = muzzle_world - (T["ring_centre_x"] + G["trunnion_rel_x"])
    bore = E["main_gun_bore"]["value"] / 2
    b0 = a_m - 0.45
    prof = [(0.28, 0.0), (0.28, G["sleeve_r"]), (G["sleeve_to"], G["sleeve_r"]), (G["sleeve_to"] + 0.05, G["barrel_r_breech"]),
            (b0, G["barrel_r_muzzle"]), (b0, 0.165), (b0 + 0.13, 0.165), (b0 + 0.13, 0.11), (b0 + 0.25, 0.11),
            (b0 + 0.25, 0.165), (b0 + 0.38, 0.165), (b0 + 0.38, 0.11), (a_m, 0.11), (a_m, bore), (a_m - 0.6, bore), (a_m - 0.6, 0.0)]
    bm = bmesh.new(); bm_lathe(bm, prof, 28, 'X')
    finish_mesh(f"{tag}_Barrel", bm, coll, MAT["armor"], gp)
    return coll, root

# ================================================================== build
ks_coll, ks_root = build_kaisersturm()
bs_coll, bs_root = build_bastion()
exec(open(os.path.join(HERE, "stage2.py")).read())
detail_kaisersturm(ks_coll, ks_root)
detail_bastion(bs_coll, bs_root)
ref = new_coll("Reference")
bm = bmesh.new(); bm_box(bm, (-12, -9, -0.02), (12, 9, 0.0))
ground = finish_mesh("Ground_Plane", bm, ref, MAT["ground"])
fig = build_figure(ref, (0, 0, 0))
bpy.context.view_layer.update()

# ------------------------------------------------------------------ measurement
def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons) if ob.type == 'MESH' else 0

def world_bounds(objs):
    mn = np.full(3, np.inf); mx = np.full(3, -np.inf)
    for ob in objs:
        if ob.type != 'MESH':
            continue
        M = ob.matrix_world
        co = np.array([tuple(M @ v.co) for v in ob.data.vertices])
        mn = np.minimum(mn, co.min(0)); mx = np.maximum(mx, co.max(0))
    return mn, mx

def by_prefix(coll, pref):
    return [o for o in coll.all_objects if o.name.startswith(pref)]

RUN_KEYS = ("RoadWheel", "Sprocket", "Idler", "ReturnRoller", "BogieHousing", "SuspensionArm")

def desc_meshes(ob):
    out = []
    for c in ob.children:
        if c.type == 'MESH' and not c.get("no_export"):
            out.append(c)
        out += desc_meshes(c)
    return out

def is_desc(ob, anc):
    p = ob.parent
    while p:
        if p == anc:
            return True
        p = p.parent
    return False

def measure(tag, coll):
    meshes = [o for o in coll.all_objects if o.type == 'MESH' and not o.get("no_export")]
    core = [o for o in meshes if not o.get("envelope_exclude")]
    mn, mx = world_bounds(core)
    amn, amx = world_bounds(meshes)
    hmn, hmx = world_bounds([bpy.data.objects[f"{tag}_Hull"]])
    bmn, bmx = world_bounds([bpy.data.objects[f"{tag}_Barrel"]])
    cmn, cmx = world_bounds(by_prefix(coll, f"{tag}_Cupola"))
    tmn, tmx = world_bounds([bpy.data.objects[f"{tag}_Turret"]])
    lmn, lmx = world_bounds(by_prefix(coll, f"{tag}_TrackLink_L"))
    wheels_L = [o for o in coll.all_objects if o.name.startswith(f"{tag}_RoadWheel_L")]
    wx = sorted(o.matrix_world.translation.x for o in wheels_L)
    links_L = by_prefix(coll, f"{tag}_TrackLink_L")
    zmin = min(o.matrix_world.translation.z for o in links_L)
    gx_ = sorted(o.matrix_world.translation.x for o in links_L if o.matrix_world.translation.z < zmin + 0.02)
    rep = {
        "hull_length": round(hmx[0] - hmn[0], 3),
        "overall_length_gun_fwd": round(bmx[0] - hmn[0], 3),
        "core_envelope_LxWxH": [round(v, 3) for v in (mx - mn)],
        "bbox_incl_fittings_LxWxH": [round(v, 3) for v in (amx - amn)],
        "overall_width": round(mx[1] - mn[1], 3),
        "cupola_height": round(cmx[2], 3),
        "core_max_height": round(mx[2], 3),
        "turret_roof_height": round(tmx[2], 3),
        "hull_roof_height": round(hmx[2], 3),
        "track_width": round(lmx[1] - lmn[1], 3),
        "road_wheels_per_side": len(wheels_L),
        "first_to_last_road_wheel_centre": round(wx[-1] - wx[0], 3),
        "flat_ground_run_of_links": round(gx_[-1] - gx_[0], 3),
        "track_links_per_side": len(links_L),
        "muzzle_x": round(bmx[0], 3), "hull_rear_x": round(hmn[0], 3),
        "ground_clearance_hull": round(hmn[2], 3),
        "triangles_exported": sum(tris(o) for o in meshes),
        "objects_exported": len([o for o in coll.all_objects if not o.get("no_export")]),
        "excluded_from_envelope": sorted({o.name: o["envelope_exclude"] for o in meshes if o.get("envelope_exclude")}.items()),
        "crew_openings": {o.name: (list(o["crew_clear_opening_m"]) if hasattr(o["crew_clear_opening_m"], "to_list") else o["crew_clear_opening_m"])
                          for o in meshes if "crew_clear_opening_m" in o},
    }
    if tag == "M12A2":
        rep["bogie_modules_per_side"] = len([o for o in coll.all_objects if o.name.startswith(f"{tag}_Bogie_L")])
    return rep

report = {"KS_B": measure("KS_B", ks_coll), "M12A2": measure("M12A2", bs_coll),
          "figure_height": round(world_bounds([fig])[1][2], 3)}

# ------------------------------------------------------------------ clearances
def bvh_world(ob):
    M = ob.matrix_world
    return BVHTree.FromPolygons([M @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])

def overlaps(a_objs, b_objs):
    A = [(o, bvh_world(o)) for o in a_objs]; B_ = [(o, bvh_world(o)) for o in b_objs]
    return sorted({(oa.name, ob.name) for oa, ta in A for ob, tb in B_ if oa != ob and ta.overlap(tb)})

def arcs(degs, step=15):
    if not degs:
        return []
    ds = sorted(degs); groups = [[ds[0], ds[0]]]
    for d in ds[1:]:
        if d - groups[-1][1] <= step: groups[-1][1] = d
        else: groups.append([d, d])
    if len(groups) > 1 and groups[0][0] == 0 and groups[-1][1] == 360 - step:
        groups[0][0] = groups[-1][0] - 360; groups.pop()
    return [f"{a}..{b} deg" for a, b in groups]

OPEN_STEP = 5   # traverse sampling (deg) for open-hatch and pintle sweeps

def collision_suite(tag, coll):
    O = bpy.data.objects
    root, tp, gp = O[f"{tag}_Root"], O[f"{tag}_Turret_Pivot"], O[f"{tag}_Gun_Pivot"]
    breech = O[f"{tag}_Breech_Clearance"]
    ring = O[f"{tag}_Turret_Ring"]
    turret_all = [o for o in desc_meshes(tp) if o != ring and not o.get("flexible")]
    gun_all = desc_meshes(gp)
    turret_body = [o for o in turret_all if o not in gun_all]
    hinges = [o for o in coll.all_objects if o.type == 'EMPTY' and "open_deg" in o]
    t_hinges = [h for h in hinges if is_desc(h, tp)]
    h_hinges = [h for h in hinges if h not in t_hinges]
    lids = {h.name: desc_meshes(h) for h in hinges}
    hull_lids = [o for h in h_hinges for o in lids[h.name]]
    tset = set(turret_all) | {ring}
    hull_fixed = [o for o in desc_meshes(root) if o not in tset and not is_desc(o, tp) and o not in hull_lids
                  and not any(k in o.name for k in RUN_KEYS) and "TrackLink" not in o.name and not o.get("flexible")]
    hull_all = hull_fixed + hull_lids
    run = [o for o in desc_meshes(root) if any(k in o.name for k in RUN_KEYS)]
    links = [o for o in desc_meshes(root) if "TrackLink" in o.name]
    skirts = [o for o in coll.all_objects if o.type == 'MESH' and "Skirt_" in o.name]
    hull = O[f"{tag}_Hull"]
    upd = bpy.context.view_layer.update
    res = {}
    res["neutral_turret_vs_hull"] = overlaps(turret_all, hull_all)
    res["neutral_gun_vs_turret"] = overlaps(gun_all, turret_body)
    res["neutral_breech_vs_turret"] = overlaps([breech], turret_body)
    res["neutral_running_gear_vs_hull"] = overlaps(run, [hull])
    res["neutral_tracks_vs_hull"] = overlaps(links, [hull])
    res["neutral_suspension_vs_tracks"] = overlaps([o for o in run if any(k in o.name for k in ("BogieHousing", "SuspensionArm", "ReturnRoller"))], links)
    res["neutral_tracks_vs_skirts"] = overlaps(links, skirts) if skirts else []
    res["neutral_wheels_vs_skirts"] = overlaps(run, skirts) if skirts else []
    sweep = []
    for deg in range(0, 360, 15):
        tp.rotation_euler = (0, 0, math.radians(deg)); upd()
        h = overlaps(turret_all, hull_all)
        if h: sweep.append({"traverse_deg": deg, "pairs": h})
    res["traverse_sweep_closed_hatches"] = sweep
    lim = []
    stop = gp.get("elevation_stop_deg")
    for deg in (0, 45, 90, 135, 180):
        tp.rotation_euler = (0, 0, math.radians(deg))
        out = {"traverse_deg": deg}
        for sign, key, nmax in ((-1, "depression", 40), (1, "elevation", 60)):
            best, why = 0.0, "scan limit"
            for k in range(1, nmax + 1):
                e = sign * 0.5 * k
                if sign > 0 and stop is not None and e > stop:
                    why = "elevating gear stop"
                    break
                gp.rotation_euler = (0, math.radians(-e), 0); upd()
                hit = overlaps(gun_all, hull_all) + overlaps(gun_all, turret_body)
                if sign < 0:
                    hit += overlaps([breech], turret_body)
                if hit:
                    why = "; ".join(f"{x.replace(tag + '_', '')} x {y.replace(tag + '_', '')}" for x, y in sorted(set(hit))[:4])
                    break
                best = e
            out[f"max_{key}_deg"] = best; out[f"{key}_limited_by"] = why
        lim.append(out)
    gp.rotation_euler = (0, 0, 0); tp.rotation_euler = (0, 0, 0); upd()
    res["gun_limits"] = lim
    hatch = {}
    for h in h_hinges:
        key = h.name.split("Hinge_")[-1]
        own = [o for o in hull_fixed if o.name.endswith(f"HatchRim_{key}")]
        if "RearDoor" in h.name:
            own.append(hull)
        set_open(h); upd()
        static = overlaps(lids[h.name], [o for o in hull_fixed if o not in own])
        blocked = []
        for deg in range(0, 360, OPEN_STEP):
            tp.rotation_euler = (0, 0, math.radians(deg)); upd()
            if overlaps(turret_all, lids[h.name]): blocked.append(deg)
        # if the gun fouls the open lid, find the smallest elevation that clears a full 1-deg traverse sweep
        need = None
        if blocked:
            for k in range(0, int(2 * (stop or 20)) + 1):
                gp.rotation_euler = (0, math.radians(-0.5 * k), 0)
                if not any((setattr(tp, "rotation_euler", (0, 0, math.radians(d))), upd(), overlaps(turret_all, lids[h.name]))[2]
                           for d in range(360)):
                    need = 0.5 * k
                    break
            gp.rotation_euler = (0, 0, 0)
        tp.rotation_euler = (0, 0, 0)
        h.rotation_euler = (0, 0, h.get("yaw0", h.rotation_euler.z)) if h["open_axis"] == "Z" else (0, 0, h.rotation_euler.z)
        upd()
        hatch[h.name] = {"open_deg": h["open_deg"], "fouls_fixed_parts_when_open": static,
                         "turret_traverse_blocked_while_open": arcs(blocked, OPEN_STEP)}
        if blocked:
            hatch[h.name]["gun_elevation_for_clear_traverse_deg"] = need
    for h in t_hinges:
        own = set(lids[h.name])
        key = h.name.split("Hinge_")[-1]
        own |= {o for o in turret_all if o.name.endswith(f"HatchRim_{key}") or (key == "cupola" and o.name == f"{tag}_Cupola")}
        set_open(h); upd()
        static = overlaps(lids[h.name], [o for o in turret_all if o not in own] + hull_all)
        h.rotation_euler = (0, 0, h.rotation_euler.z); upd()
        hatch[h.name] = {"open_deg": h["open_deg"], "fouls_parts_when_open": static}
    res["hatches"] = hatch
    return res

def set_all_hatches(coll, opened):
    for h in [o for o in coll.all_objects if o.type == 'EMPTY' and "open_deg" in o]:
        if opened: set_open(h)
        else: h.rotation_euler = (0, 0, h.get("yaw0", h.rotation_euler.z))
    bpy.context.view_layer.update()

def discharger_paths(tag, coll, length=3.0):
    """Ray-test the first 3 m of each grenade's flight (bore centre + 4 rays at 80 % bore radius) against the
    vehicle, hatches closed and all open, turret at 45 deg steps. Whip aerials are ignored (they flex)."""
    O = bpy.data.objects; tp = O[f"{tag}_Turret_Pivot"]
    banks = [o for o in coll.all_objects if o.get("discharger")]
    obst = [o for o in coll.all_objects if o.type == 'MESH' and not o.get("no_export") and not o.get("flexible")
            and "TrackLink" not in o.name and not any(k in o.name for k in RUN_KEYS) and "Skirt" not in o.name]
    out = {b.name.replace(tag + "_", ""): {"kind": b["discharger"], "tubes": len(b["tube_mouths"]),
           "fire_direction_turret_space": [round(v, 3) for v in b["fire_dir"]], "blocked": []} for b in banks}
    for opened in (False, True):
        set_all_hatches(coll, opened)
        for deg in range(0, 360, 45):
            tp.rotation_euler = (0, 0, math.radians(deg)); bpy.context.view_layer.update()
            trees = [(o, bvh_world(o)) for o in obst]
            R3 = tp.matrix_world.to_3x3()
            for b in banks:
                d = (R3 @ Vector(b["fire_dir"])).normalized()
                e1 = d.orthogonal().normalized(); e2 = d.cross(e1); rr = b["tube_bore_r"] * 0.8
                hits = set()
                for m in b["tube_mouths"]:
                    c = tp.matrix_world @ Vector(m)
                    for off in (Vector((0, 0, 0)), e1 * rr, -e1 * rr, e2 * rr, -e2 * rr):
                        for o, tr in trees:
                            if o != b and tr.ray_cast(c + off, d, length)[0] is not None:
                                hits.add(o.name.replace(tag + "_", ""))
                if hits:
                    out[b.name.replace(tag + "_", "")]["blocked"].append(
                        {"hatches": "open" if opened else "closed", "traverse_deg": deg, "by": sorted(hits)})
    tp.rotation_euler = (0, 0, 0); set_all_hatches(coll, False)
    return out

def roof_mg_checks(tag, coll):
    """Operator reach to the .50 grips from each turret hatch, and the pintle traverse arcs."""
    O = bpy.data.objects; tp = O[f"{tag}_Turret_Pivot"]
    piv, gun, mount = O[f"{tag}_RoofMG50_Pivot"], O[f"{tag}_RoofMG50"], O[f"{tag}_RoofMG50_Mount"]
    RC = P["stage2"]["bastion_m12a2"]["roof_mg_reach_check"]
    bpy.context.view_layer.update()
    grip = piv.matrix_world @ Vector(gun["grip_local"])
    reach = {}
    for o in desc_meshes(tp):
        if "hatch_top_centre" in o:
            sh = tp.matrix_world @ (Vector(o["hatch_top_centre"]) + Vector((0, 0, RC["shoulder_above_hatch_top_m"])))
            key = o.name.replace(tag + "_", "").replace("HatchRim_", "")
            reach[key] = {"shoulder_to_grips_m": round((grip - sh).length, 3),
                          "within_reach": (grip - sh).length <= RC["max_reach_m"]}
    others = [o for o in desc_meshes(tp) if o not in (gun, mount) and not o.get("flexible")]
    arcs_ = {}
    for opened in (False, True):
        set_all_hatches(coll, opened)
        blocked = []
        for deg in range(0, 360, OPEN_STEP):
            piv.rotation_euler = (0, 0, math.radians(deg)); bpy.context.view_layer.update()
            if overlaps([gun], others): blocked.append(deg)
        arcs_["hatches_open" if opened else "hatches_closed"] = arcs(blocked, OPEN_STEP)
    piv.rotation_euler = (0, 0, 0); set_all_hatches(coll, False)
    return {"operator": gun["operator"], "pintle_xy_turret_space": [round(v, 3) for v in piv.location[:2]],
            "grip_height_above_ground_m": round(grip.z, 3),
            "reach_rule": f"shoulder {RC['shoulder_above_hatch_top_m']} m above the hatch top, grips within {RC['max_reach_m']} m",
            "reach_from_hatches": reach, "pintle_traverse_blocked_deg": arcs_}

report["clearances"] = {"KS_B": collision_suite("KS_B", ks_coll), "M12A2": collision_suite("M12A2", bs_coll)}
report["clearances"]["KS_B"]["discharger_launch_paths"] = discharger_paths("KS_B", ks_coll)
report["clearances"]["M12A2"]["discharger_launch_paths"] = discharger_paths("M12A2", bs_coll)
report["clearances"]["M12A2"]["roof_mg50"] = roof_mg_checks("M12A2", bs_coll)

# ------------------------------------------------------------------ save + export
for o in bpy.data.objects:
    if o.get("no_export"):
        o.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "weltenbrecher_stage2_detail.blend"))

def export_tree(root, path):
    bpy.ops.object.select_all(action='DESELECT')
    def sel(o):
        if o.get("no_export"):
            return
        o.select_set(True)
        for c in o.children:
            sel(c)
    sel(root)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_apply=False, export_yup=True, export_extras=True)

export_tree(ks_root, os.path.join(OUT, "KS_B_stage2.glb"))
export_tree(bs_root, os.path.join(OUT, "M12A2_stage2.glb"))
export_tree(fig, os.path.join(OUT, "scale_figure_1p80.glb"))
# review pose: every hatch, lid and door open (neutral GLBs above stay closed)
all_h = [o for o in bpy.data.objects if o.type == 'EMPTY' and "open_deg" in o]
for h in all_h: set_open(h)
bpy.context.view_layer.update()
export_tree(ks_root, os.path.join(OUT, "KS_B_stage2_hatches_open.glb"))
export_tree(bs_root, os.path.join(OUT, "M12A2_stage2_hatches_open.glb"))
for h in all_h:
    h.rotation_euler = (0, 0, h.get("yaw0", h.rotation_euler.z))
json.dump(report, open(os.path.join(OUT, "stage2_report.json"), "w"), indent=2)
print(json.dumps({k: v for k, v in report.items() if k != "clearances"}, indent=1)[:3000])
