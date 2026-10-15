"""
Weltenbrecher - Stage 2 functional detail.
Executed inside generate.py's namespace (shares its helpers, MAT, P, GROUSER).

Moving parts are rigged on named empties:
  <TAG>_HatchHinge_<key>    hatch lids. Open = rotate about local Y by -open_deg (prop "open_deg").
  <TAG>_RearDoorHinge_<L|R> Bastion rear doors. Open = rotate about local Z by open_sign*open_deg.
Anything that should not count toward the measured envelope carries "envelope_exclude"
with a reason; internal clearance placeholders carry "no_export" and are kept out of the GLBs.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Matrix, Vector

S2 = P["stage2"]
MAT["vision"] = make_mat("Blockout_VisionBlock_Dark", (0.04, 0.05, 0.06), rough=0.3)
MAT["recess"] = make_mat("Blockout_Recess_Dark", (0.12, 0.12, 0.12))

# ------------------------------------------------------------------ helpers
def tagged(bm, idx, fn, *a, **k):
    """Run a bmesh builder and give every face it adds material slot idx."""
    bm.faces.ensure_lookup_table(); n0 = len(bm.faces)
    fn(bm, *a, **k)
    bm.faces.ensure_lookup_table()
    for f in bm.faces[n0:]:
        f.material_index = idx

def finish2(name, bm, coll, mats, parent=None, loc=(0, 0, 0), weld=True):
    if weld:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = False
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = loc
    if parent:
        ob.parent = parent
    return ob

def mesh_only(name, bm, mats, weld=True):
    if weld:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    return me

def bm_obox(bm, c, u, v, w, hu, hv, hw):
    """Oriented box: centre c, unit axes u, v, w, half sizes."""
    c, u, v, w = (np.array(x, float) for x in (c, u, v, w))
    vs = {}
    for i in (-1, 1):
        for j in (-1, 1):
            for k in (-1, 1):
                vs[(i, j, k)] = bm.verts.new(tuple(c + i * hu * u + j * hv * v + k * hw * w))
    for f in [((-1,-1,-1),(-1,1,-1),(1,1,-1),(1,-1,-1)), ((-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)),
              ((-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)), ((1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)),
              ((1,1,-1),(-1,1,-1),(-1,1,1),(1,1,1)), ((-1,1,-1),(-1,-1,-1),(-1,-1,1),(-1,1,1))]:
        bm.faces.new([vs[x] for x in f])

def ring_lathe(bm, axis, center, r_in, r_out, a0, a1, seg=24):
    bm_lathe(bm, [(a0, r_in), (a0, r_out), (a1, r_out), (a1, r_in), (a0, r_in)], seg, axis, center)

def unit(v):
    v = np.array(v, float); return v / np.linalg.norm(v)

def hinge_empty(name, coll, parent, loc, yaw, open_deg, axis="Y", open_sign=-1):
    e = empty(name, coll, parent, loc)
    e.rotation_euler = (0, 0, yaw)
    e["open_deg"] = open_deg; e["open_axis"] = axis; e["open_sign"] = open_sign
    e["note"] = f"Hinge. Open = rotate about local {axis} by {'+' if open_sign > 0 else '-'}open_deg"
    return e

def set_open(e, frac=1.0):
    a = math.radians(e["open_deg"]) * frac * e["open_sign"]
    if e["open_axis"] == "Y":
        e.rotation_euler = (0, a, e.rotation_euler.z)
    else:
        e.rotation_euler = (0, 0, e["yaw0"] + a)

def periscope_bm(bm, base, fwd, scale=1.0):
    """Armoured periscope head on a base plate: body slot 0, window slot 1."""
    f = unit((fwd[0], fwd[1], 0)); s = np.array([-f[1], f[0], 0.0]); z = np.array([0, 0, 1.0])
    b = np.array(base, float); k = scale
    tagged(bm, 0, bm_obox, b + z * 0.02 * k, f, s, z, 0.10 * k, 0.13 * k, 0.02 * k)
    tagged(bm, 0, bm_obox, b + z * 0.09 * k, f, s, z, 0.065 * k, 0.11 * k, 0.05 * k)
    tagged(bm, 1, bm_obox, b + z * 0.09 * k + f * 0.066 * k, f, s, z, 0.004 * k, 0.085 * k, 0.026 * k)
    tagged(bm, 0, bm_obox, b + z * 0.145 * k + f * 0.05 * k, f, s, z, 0.04 * k, 0.12 * k, 0.008 * k)

def round_hatch(tag, key, coll, parent, c, r_open, hinge_dir_deg, rim_h, rim_w, lid_t, open_deg, peri_fwd=None,
                peri_scale=0.9, peri_toward_hinge=0.0):
    """Fixed rim on the plate + hinged lid. c = hatch centre on the plate surface (parent space).
    peri_fwd: world-ish forward direction (in parent space) for a periscope in the lid."""
    cx, cy, cz = c
    bm = bmesh.new()
    ring_lathe(bm, 'Z', (cx, cy, cz), r_open, r_open + rim_w, -0.015, rim_h, 28)
    rim = finish2(f"{tag}_HatchRim_{key}", bm, coll, MAT["detail"], parent)
    rim["crew_clear_opening_m"] = round(2 * r_open, 3)
    rim["hatch_top_centre"] = (cx, cy, cz + rim_h)
    hd = math.radians(hinge_dir_deg)
    d = r_open + rim_w * 0.5
    hpos = (cx + d * math.cos(hd), cy + d * math.sin(hd), cz + rim_h + lid_t / 2 + 0.003)
    yaw = hd + math.pi
    h = hinge_empty(f"{tag}_HatchHinge_{key}", coll, parent, hpos, yaw, open_deg)
    bm = bmesh.new()
    rl = r_open + rim_w * 0.85
    tagged(bm, 0, bm_lathe, [(-lid_t / 2, 0.0), (-lid_t / 2, rl), (lid_t / 2, rl), (lid_t / 2 + 0.012, rl - 0.05), (lid_t / 2 + 0.012, 0.0)], 28, 'Z', (d, 0, 0))
    for yy in (-0.13, 0.13):                                   # hinge knuckles
        tagged(bm, 0, bm_lathe, [(yy - 0.05, 0.0), (yy - 0.05, 0.035), (yy + 0.05, 0.035), (yy + 0.05, 0.0)], 12, 'Y', (0, 0, 0))
    tagged(bm, 0, bm_obox, (2 * d - 0.12, 0, lid_t / 2 + 0.03), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.015, 0.09, 0.015)  # grab handle
    if peri_fwd is not None:
        fl = np.array([math.cos(-yaw) * peri_fwd[0] - math.sin(-yaw) * peri_fwd[1],
                       math.sin(-yaw) * peri_fwd[0] + math.cos(-yaw) * peri_fwd[1]])
        periscope_bm(bm, (d - peri_toward_hinge + 0.05 * fl[0], 0.05 * fl[1], lid_t / 2 + 0.012), fl, peri_scale)
    lid = finish2(f"{tag}_HatchLid_{key}", bm, coll, [MAT["detail"], MAT["vision"]], h)
    return h, lid, rim

def rect_hatch(tag, key, coll, parent, c, L, W, hinge_side, rim_h, rim_w, lid_t, open_deg):
    """Rectangular hatch, L along x, W along y. hinge_side: '+y' or '-y'."""
    cx, cy, cz = c
    bm = bmesh.new()
    hx, hy = L / 2, W / 2
    for (x0, x1, y0, y1) in [(-hx - rim_w, hx + rim_w, hy, hy + rim_w), (-hx - rim_w, hx + rim_w, -hy - rim_w, -hy),
                             (hx, hx + rim_w, -hy, hy), (-hx - rim_w, -hx, -hy, hy)]:
        bm_box(bm, (cx + x0, cy + y0, cz - 0.015), (cx + x1, cy + y1, cz + rim_h))
    rim = finish2(f"{tag}_HatchRim_{key}", bm, coll, MAT["detail"], parent, weld=False)
    rim["crew_clear_opening_m"] = [round(L, 3), round(W, 3)]
    rim["hatch_top_centre"] = (cx, cy, cz + rim_h)
    sgn = 1 if hinge_side == "+y" else -1
    d = hy + rim_w * 0.5
    hpos = (cx, cy + sgn * d, cz + rim_h + lid_t / 2 + 0.003)
    yaw = math.atan2(-sgn, 0)                                   # local +X points from hinge toward centre
    h = hinge_empty(f"{tag}_HatchHinge_{key}", coll, parent, hpos, yaw, open_deg)
    bm = bmesh.new()
    bm_chamfer_box(bm, (d, 0, 0), (2 * d + rim_w * 0.4, L + rim_w * 1.7, lid_t), 0.015)
    for xx in (-L * 0.3, L * 0.3):
        bm_lathe(bm, [(xx - 0.05, 0.0), (xx - 0.05, 0.035), (xx + 0.05, 0.035), (xx + 0.05, 0.0)], 12, 'Y', (0, 0, 0))
    bm_obox(bm, (2 * d - 0.10, 0, lid_t / 2 + 0.03), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.015, 0.10, 0.015)
    lid = finish2(f"{tag}_HatchLid_{key}", bm, coll, MAT["detail"], h)
    return h, lid, rim

def cupola(tag, coll, parent, cx, cy, z_roof, z_top, r, n_blocks, hinge_dir_deg, open_deg, band_frac=0.55):
    """Cupola ring with narrow vision blocks under armoured brows, plus a hinged lid whose top is z_top."""
    lid_t = 0.06
    r_in = r - 0.08
    bm = bmesh.new()
    prof = [(z_roof - 0.06, r_in), (z_roof - 0.06, r + 0.045), (z_roof + 0.05, r + 0.045), (z_roof + 0.05, r),
            (z_top - lid_t, r), (z_top - lid_t, r_in), (z_roof - 0.06, r_in)]
    tagged(bm, 0, bm_lathe, prof, 36, 'Z', (cx, cy, 0))
    zb = z_roof + 0.05 + (z_top - lid_t - z_roof - 0.05) * band_frac
    for i in range(n_blocks):
        a = 2 * math.pi * (i + 0.5) / n_blocks
        u = np.array([math.cos(a), math.sin(a), 0]); v = np.array([-u[1], u[0], 0]); w = np.array([0, 0, 1.0])
        base = np.array([cx, cy, zb])
        tagged(bm, 1, bm_obox, base + u * (r + 0.012), u, v, w, 0.016, 0.052, 0.03)       # vision block
        tagged(bm, 0, bm_obox, base + u * (r + 0.03) + w * 0.045, u, v, w, 0.035, 0.07, 0.009)  # brow
    body = finish2(f"{tag}_Cupola", bm, coll, [MAT["detail"], MAT["vision"]], parent)
    body["vision_blocks"] = n_blocks
    body["crew_clear_opening_m"] = round(2 * r_in, 3)
    body["hatch_top_centre"] = (cx, cy, z_top - lid_t)
    hd = math.radians(hinge_dir_deg); d = r - 0.03
    h = hinge_empty(f"{tag}_HatchHinge_cupola", coll, parent, (cx + d * math.cos(hd), cy + d * math.sin(hd), z_top - lid_t / 2),
                    hd + math.pi, open_deg)
    bm = bmesh.new()
    bm_lathe(bm, [(-lid_t / 2, 0.0), (-lid_t / 2, r - 0.01), (lid_t / 2 - 0.015, r - 0.01), (lid_t / 2, r - 0.05), (lid_t / 2, 0.0)], 32, 'Z', (d, 0, 0))
    for yy in (-0.12, 0.12):
        bm_lathe(bm, [(yy - 0.04, 0.0), (yy - 0.04, 0.03), (yy + 0.04, 0.03), (yy + 0.04, 0.0)], 12, 'Y', (0, 0, 0))
    finish2(f"{tag}_Cupola_Lid", bm, coll, MAT["detail"], h)
    return body, h

def mantlet_bm(bm, half_w, half_h, R_back, front_fn, corner, ny=9, narc=13):
    """Mantlet whose rear face is a cylinder about the trunnion (local Y), so it never fouls the port."""
    x_t = math.sqrt(R_back ** 2 - half_h ** 2)
    al = math.atan2(half_h, x_t)
    rings = []
    for y in np.linspace(-half_w, half_w, ny):
        xf = front_fn(y)
        prof = [(xf, -half_h + corner), (xf, half_h - corner), (xf - corner, half_h)]
        prof += [(R_back * math.cos(t), R_back * math.sin(t)) for t in np.linspace(al, 2 * math.pi - al, narc)]
        prof += [(xf - corner, -half_h)]
        rings.append([(x, y, z) for x, z in prof])
    bm_loft(bm, rings)

def port_cut(target, parent, centre_xz, R, half_w):
    """Boolean the gun port (cylinder about the trunnion axis) out of the turret; applied, no modifier left."""
    bm = bmesh.new()
    bm_lathe(bm, [(-half_w, 0.0), (-half_w, R), (half_w, R), (half_w, 0.0)], 48, 'Y', (centre_xz[0], 0, centre_xz[1]))
    cut = finish2(f"{target.name}__portcutter", bm, target.users_collection[0], MAT["detail"], parent)
    bpy.context.view_layer.update()
    mod = target.modifiers.new("port", 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cut; mod.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear()
    old = target.data; target.data = new; new.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cut)
    target["gun_port"] = f"cylindrical port, radius {R} m about the trunnion axis"

def hollow(target, parent, rings):
    """Subtract an inner loft from a solid turret so it becomes a shell open at the turret ring."""
    bm = bmesh.new(); bm_loft(bm, rings)
    cut = finish2(f"{target.name}__hollow", bm, target.users_collection[0], MAT["detail"], parent)
    bpy.context.view_layer.update()
    mod = target.modifiers.new("hollow", 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cut; mod.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear()
    old = target.data; target.data = new; new.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cut)

def lift_eye_mesh(tag):
    bm = bmesh.new()
    bm_box(bm, (-0.055, -0.03, -0.01), (0.055, 0.03, 0.03))
    ring_lathe(bm, 'Y', (0, 0, 0.085), 0.03, 0.058, -0.015, 0.015, 16)
    return mesh_only(f"{tag}_LiftEye", bm, MAT["detail"])

def place(name, me, coll, parent, loc, yaw=0.0):
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    ob.parent = parent; ob.location = loc; ob.rotation_euler = (0, 0, yaw)
    return ob

def ball_mount(tag, coll, parent, centre, normal, r=0.13):
    """Bow MG in an armoured ball: ball half-sunk in the plate, collar, barrel along +X."""
    n = unit(normal)
    c = np.array(centre) - n * r * 0.35
    bm = bmesh.new()
    prof = [(-r, 0.0)] + [(-r * math.cos(t), r * math.sin(t)) for t in np.linspace(0.25, math.pi - 0.25, 9)] + [(r, 0.0)]
    tagged(bm, 0, bm_lathe, prof, 20, 'X', tuple(c))
    tagged(bm, 0, bm_lathe, [(r * 0.6, 0.0), (r * 0.6, 0.045), (r + 0.06, 0.04), (r + 0.06, 0.0)], 14, 'X', tuple(c))
    tagged(bm, 0, bm_lathe, [(r + 0.06, 0.0), (r + 0.06, 0.02), (r + 0.42, 0.018), (r + 0.42, 0.0)], 10, 'X', tuple(c))
    return finish2(f"{tag}_BowMG", bm, coll, MAT["detail"], parent)

def grille_louvre_mesh(name, Lx, Ly, n):
    """Armoured radiator louvres: dark recess (slot 1), frame and slats (slot 0). Centred, base at z=0."""
    bm = bmesh.new()
    tagged(bm, 1, bm_box, (-Lx / 2 + 0.04, -Ly / 2 + 0.04, 0.0), (Lx / 2 - 0.04, Ly / 2 - 0.04, 0.012))
    for (x0, x1, y0, y1) in [(-Lx / 2, Lx / 2, Ly / 2 - 0.05, Ly / 2), (-Lx / 2, Lx / 2, -Ly / 2, -Ly / 2 + 0.05),
                             (Lx / 2 - 0.05, Lx / 2, -Ly / 2, Ly / 2), (-Lx / 2, -Lx / 2 + 0.05, -Ly / 2, Ly / 2)]:
        tagged(bm, 0, bm_box, (x0, y0, 0.0), (x1, y1, 0.06))
    for x in np.linspace(-Lx / 2 + 0.10, Lx / 2 - 0.10, n):
        tagged(bm, 0, bm_obox, (x, 0, 0.035), unit((1, 0, 0.55)), (0, 1, 0), unit((-0.55, 0, 1)), 0.035, Ly / 2 - 0.05, 0.008)
    return mesh_only(name, bm, [MAT["detail"], MAT["recess"]], weld=False)

def grille_mesh_bars(name, Lx, Ly, n):
    """Fine-bar cooling grille (Bastion): bars run fore-aft."""
    bm = bmesh.new()
    tagged(bm, 1, bm_box, (-Lx / 2 + 0.04, -Ly / 2 + 0.04, 0.0), (Lx / 2 - 0.04, Ly / 2 - 0.04, 0.012))
    for (x0, x1, y0, y1) in [(-Lx / 2, Lx / 2, Ly / 2 - 0.045, Ly / 2), (-Lx / 2, Lx / 2, -Ly / 2, -Ly / 2 + 0.045),
                             (Lx / 2 - 0.045, Lx / 2, -Ly / 2, Ly / 2), (-Lx / 2, -Lx / 2 + 0.045, -Ly / 2, Ly / 2)]:
        tagged(bm, 0, bm_box, (x0, y0, 0.0), (x1, y1, 0.05))
    for y in np.linspace(-Ly / 2 + 0.08, Ly / 2 - 0.08, n):
        tagged(bm, 0, bm_box, (-Lx / 2 + 0.04, y - 0.012, 0.012), (Lx / 2 - 0.04, y + 0.012, 0.04))
    for x in np.linspace(-Lx / 2 + 0.3, Lx / 2 - 0.3, 3):
        tagged(bm, 0, bm_box, (x - 0.02, -Ly / 2 + 0.04, 0.012), (x + 0.02, Ly / 2 - 0.04, 0.045))
    return mesh_only(name, bm, [MAT["detail"], MAT["recess"]], weld=False)

def access_panel_bm(bm, c, Lx, Ly, t=0.03, bolts=8, handles=2):
    cx, cy, cz = c
    bm_chamfer_box(bm, (cx, cy, cz + t / 2), (Lx, Ly, t), 0.012)
    pts = []
    for i in range(bolts // 2):
        x = cx - Lx / 2 + 0.06 + i * (Lx - 0.12) / max(bolts // 2 - 1, 1)
        pts += [(x, cy - Ly / 2 + 0.05), (x, cy + Ly / 2 - 0.05)]
    for x, y in pts:
        bm_lathe(bm, [(cz + t - 0.002, 0.0), (cz + t - 0.002, 0.018), (cz + t + 0.012, 0.018), (cz + t + 0.012, 0.0)], 6, 'Z', (x, y, 0))
    for k in range(handles):
        x = cx + (k - (handles - 1) / 2) * Lx * 0.5
        for dy in (-0.07, 0.07):
            bm_box(bm, (x - 0.012, cy + dy - 0.012, cz + t), (x + 0.012, cy + dy + 0.012, cz + t + 0.05))
        bm_box(bm, (x - 0.012, cy - 0.08, cz + t + 0.04), (x + 0.012, cy + 0.08, cz + t + 0.06))

def aerial(tag, i, coll, parent, base, length=2.0):
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, 0.0), (0.0, 0.06), (0.03, 0.06), (0.03, 0.035), (0.12, 0.03), (0.12, 0.0)], 14, 'Z', base)
    finish2(f"{tag}_AerialBase_{i}", bm, coll, MAT["detail"], parent)
    bm = bmesh.new()
    bm_lathe(bm, [(0.12, 0.0), (0.12, 0.008), (0.12 + length, 0.004), (0.12 + length, 0.0)], 6, 'Z', base)
    rod = finish2(f"{tag}_Aerial_{i}", bm, coll, MAT["detail"], parent)
    rod["envelope_exclude"] = "aerial (brief: aerials not part of the envelope)"
    rod["flexible"] = True

def breech_placeholder(tag, coll, gp, x0, x1, hw, hh):
    bm = bmesh.new(); bm_box(bm, (x0, -hw, -hh), (x1, hw, hh))
    ob = finish2(f"{tag}_Breech_Clearance", bm, coll, MAT["recess"], gp)
    ob["no_export"] = True; ob.hide_render = True; ob.display_type = 'WIRE'
    ob["note"] = "Coarse internal clearance placeholder: breech + recoil envelope incl. roof armour allowance"
    return ob

def glacis_frame(hull_ob):
    x0, z0, x1, z1 = hull_ob["glacis_line"]
    u = unit((x1 - x0, 0, z1 - z0)); n = np.array([-u[2], 0, u[0]])
    if n[0] < 0: n = -n
    def at(x):
        return z0 + (x - x0) * (z1 - z0) / (x1 - x0)
    return u, n, at

# ================================================================== KAISERSTURM B detail
def detail_kaisersturm(coll, root):
    tag = "KS_B"; K = P["kaisersturm_b"]; D = S2["kaisersturm_b"]
    E, Hh, T, G = K["envelope"], K["hull"], K["turret"], K["gun"]
    HL = E["hull_length"]["value"]; xr, xf = -HL / 2, HL / 2; zr = Hh["roof_z"]
    hull = bpy.data.objects[f"{tag}_Hull"]
    tp = bpy.data.objects[f"{tag}_Turret_Pivot"]; gp = bpy.data.objects[f"{tag}_Gun_Pivot"]
    turret = bpy.data.objects[f"{tag}_Turret"]
    zt = T["base_gap"] + T["height"]
    u, n, gz = glacis_frame(hull)

    # --- hull hatches: rims, hinged lids (outboard hinges), periscope in each lid
    for key in ("driver", "radio_op"):
        h = K["hatches"][key]; side = 1 if h["y"] > 0 else -1
        round_hatch(tag, key, coll, root, (h["x"], h["y"], zr), h["r"], 90 * side, 0.05, 0.07, 0.06,
                    D["hull_hatch_open_deg"], peri_fwd=(1, 0),
                    peri_scale=D["lid_periscope_scale"], peri_toward_hinge=D["lid_periscope_toward_hinge"])
    # driver's armoured visor block in the glacis (protected opening, small slit)
    vx, vy = D["driver_visor_xy"]
    c = np.array([vx, vy, gz(vx)]) + n * 0.05
    bm = bmesh.new()
    tagged(bm, 0, bm_obox, c, u, (0, 1, 0), n, 0.07, 0.17, 0.05)
    tagged(bm, 1, bm_obox, c + n * 0.051 - u * 0.01, u, (0, 1, 0), n, 0.012, 0.11, 0.003)
    finish2(f"{tag}_DriverVisor", bm, coll, [MAT["detail"], MAT["vision"]], root)
    # bow MG ball (radio operator side)
    bx, by = D["bow_mg_xy"]
    ball_mount(tag, coll, root, (bx, by, gz(bx)), n)

    # --- engine deck: exhaust cowls kept; radiator louvres, fan covers, removable centre panel
    lv = grille_louvre_mesh(f"{tag}_RadiatorLouvre", 0.80, 0.90, 9)
    fan = None
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, 0.0), (0.0, 0.30), (0.05, 0.30), (0.05, 0.26), (0.03, 0.25), (0.03, 0.09), (0.06, 0.08), (0.06, 0.0)], 32, 'Z')
    for k in range(6):
        a = k * math.pi / 3
        bm_obox(bm, (0.17 * math.cos(a), 0.17 * math.sin(a), 0.04), (math.cos(a), math.sin(a), 0), (-math.sin(a), math.cos(a), 0), (0, 0, 1), 0.08, 0.012, 0.012)
    fan = mesh_only(f"{tag}_FanCover", bm, MAT["detail"])
    for side, s in (("L", 1), ("R", -1)):
        place(f"{tag}_RadiatorLouvre_{side}", lv, coll, root, (D["louvre_x"], s * 1.05, zr))
        place(f"{tag}_FanCover_{side}", fan, coll, root, (D["fan_x"], s * 1.05, zr))
    bm = bmesh.new(); access_panel_bm(bm, (D["engine_panel_x"], 0.0, zr), 1.50, 0.78, bolts=10)
    ob = finish2(f"{tag}_EngineAccessPanel", bm, coll, MAT["detail"], root, weld=False)
    ob["removable"] = True

    # --- tow eyes: heavy plate eyes, two front on the lower nose plate, two on the rear plate
    bm = bmesh.new()
    bm_chamfer_box(bm, (0.07, 0, 0), (0.18, 0.10, 0.20), 0.02)
    ring_lathe(bm, 'Y', (0.20, 0, 0), 0.06, 0.13, -0.05, 0.05, 20)
    eye = mesh_only(f"{tag}_TowEye", bm, MAT["detail"])
    lg0 = np.array([Hh["lower_glacis_start_x"], Hh["belly_z"]]); lg1 = np.array([xf, Hh["nose_z"]])
    def lower_glacis_x(z): return lg0[0] + (z - lg0[1]) * (lg1[0] - lg0[0]) / (lg1[1] - lg0[1])
    for i, s in enumerate((1, -1)):
        ob = place(f"{tag}_TowEye_F{i + 1}", eye, coll, root, (lower_glacis_x(0.58) - 0.04, s * 0.72, 0.58))
        ob["envelope_exclude"] = "tow fitting (brief: hull length excludes tow fittings)"
        ob = place(f"{tag}_TowEye_R{i + 1}", eye, coll, root, (xr + 0.04, s * 0.72, 0.90), yaw=math.pi)
        ob["envelope_exclude"] = "tow fitting (brief: hull length excludes tow fittings)"

    # --- spare track links in a bracket on the lower nose plate (shared link mesh)
    lu = unit((lg1[0] - lg0[0], 0, lg1[1] - lg0[1])); ln = np.array([lu[2], 0, -lu[0]])   # outward normal
    link_me = bpy.data.meshes[f"{tag}_TrackLink"]
    RG = K["running_gear"]; off = RG["track_thickness"] / 2 + GROUSER + 0.005
    X = Vector(lu); Y = Vector((0, 1, 0)); Z = X.cross(Y)
    k = 0
    L_len = float(np.linalg.norm(lg1 - lg0))
    for s_along in D["spare_link_rows_s"]:
        for yy in (-0.46, 0.46):
            p = np.array([lg0[0], 0, lg0[1]]) + lu * s_along * L_len + ln * off
            M = Matrix((X, Y, Z)).transposed().to_4x4(); M.translation = (p[0], yy, p[2])
            k += 1
            ob = bpy.data.objects.new(f"{tag}_SpareLink_{k}", link_me); coll.objects.link(ob)
            ob.parent = root; ob.matrix_basis = M
    bm = bmesh.new()
    ss = D["spare_link_rows_s"]
    for s_along in (min(ss) - 0.115, max(ss) + 0.115):
        p = np.array([lg0[0], 0, lg0[1]]) + lu * s_along * L_len + ln * 0.05
        bm_obox(bm, p, lu, (0, 1, 0), ln, 0.02, 0.95, 0.05)
    for yy in (-0.93, 0.0, 0.93):
        p = np.array([lg0[0], 0, lg0[1]]) + lu * (np.mean(ss)) * L_len + ln * 0.15
        bm_obox(bm, p + np.array([0, yy, 0]), lu, (0, 1, 0), ln, (max(ss) - min(ss)) * L_len / 2 + 0.13, 0.02, 0.012)
    finish2(f"{tag}_SpareLink_Rack", bm, coll, MAT["detail"], root, weld=False)

    # --- tools: cleaning-rod tube left, shovel + pick right; aerial bases on the rear deck
    bm = bmesh.new()
    x0, x1 = D["tool_x"]
    bm_lathe(bm, [(x0, 0.0), (x0, 0.045), (x1, 0.045), (x1, 0.0)], 12, 'X', (0, 1.66, zr + 0.07))
    for x in (x0 + 0.2, x1 - 0.2):
        bm_box(bm, (x - 0.03, 1.60, zr), (x + 0.03, 1.72, zr + 0.12))
    bm_box(bm, (x0 + 0.1, -1.76, zr), (x0 + 1.0, -1.56, zr + 0.03))                 # shovel blade + shaft
    bm_lathe(bm, [(x0 + 1.0, 0.0), (x0 + 1.0, 0.02), (x1 - 0.05, 0.02), (x1 - 0.05, 0.0)], 8, 'X', (0, -1.66, zr + 0.025))
    for x in (x0 + 0.3, x1 - 0.3):
        bm_box(bm, (x - 0.025, -1.74, zr), (x + 0.025, -1.58, zr + 0.06))
    finish2(f"{tag}_ToolRack", bm, coll, MAT["detail"], root, weld=False)
    for i, s in enumerate((1, -1)):
        aerial(tag, i + 1, coll, root, (D["aerial_x"], s * 1.62, zr))

    # --- turret: gun port, curved-back mantlet, cupola, loader hatch, periscope, ventilator, lift eyes
    tx, tz = G["trunnion_rel_x"], G["trunnion_rel_z"]
    M_ = G["mantlet"]
    wt = D["turret_wall"]; zin = zt - D["turret_roof_t"]
    pb, pt = np.array(T["plan_bottom"]), np.array(T["plan_top"])
    hollow(turret, tp, [radial_ring(pb, (0, 0), wt + 0.02, -0.40), radial_ring(pb, (0, 0), wt, T["base_gap"] + 0.02),
                        radial_ring(pt, (0, 0), wt - 0.02, zin)])
    port_cut(turret, tp, (tx, tz), D["mantlet_R_back"] + D["port_gap"], M_["half_width"] + 0.03)
    old = bpy.data.objects[f"{tag}_Mantlet"]; me_ = old.data; bpy.data.objects.remove(old); bpy.data.meshes.remove(me_)
    bm = bmesh.new()
    hw = M_["half_width"]
    mantlet_bm(bm, hw, M_["half_height"], D["mantlet_R_back"],
               lambda y: M_["front"] - max(0.0, abs(y) - (hw - 0.10)) * 0.9, 0.08, ny=11)
    # coax port (left) and gunner's sight aperture (right) in the mantlet face
    tagged(bm, 1, bm_lathe, [(M_["front"] - 0.02, 0.0), (M_["front"] - 0.02, 0.05), (M_["front"] + 0.01, 0.05), (M_["front"] + 0.01, 0.0)], 14, 'X', (0, D["coax_y"], 0.02))
    tagged(bm, 1, bm_obox, (M_["front"] + 0.005, D["sight_y"], 0.10), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.01, 0.045, 0.03)
    finish2(f"{tag}_Mantlet", bm, coll, [MAT["armor"], MAT["vision"]], gp)
    bm = bmesh.new()
    bm_lathe(bm, [(M_["front"], 0.0), (M_["front"], 0.024), (M_["front"] + 0.10, 0.02), (M_["front"] + 0.10, 0.0)], 10, 'X', (0, D["coax_y"], 0.02))
    finish2(f"{tag}_CoaxMG", bm, coll, MAT["detail"], gp)
    breech_placeholder(tag, coll, gp, -D["breech_len"], -0.05, 0.24, D["breech_half_h"])

    C = K["cupola"]; ztop = E["cupola_height"]["value"] - zr
    cupola(tag, coll, tp, C["rel_x"], C["rel_y"], zt, ztop, C["r"], D["cupola_blocks"], D["cupola_hinge_dir_deg"], D["turret_hatch_open_deg"])
    h = K["hatches"]["loader"]
    rect_hatch(tag, "loader", coll, tp, (h["rel_x"], h["rel_y"], zt), h["len"], h["wid"], "-y", 0.04, 0.06, 0.05, D["turret_hatch_open_deg"])
    bm = bmesh.new(); px, py = D["loader_periscope_xy"]; periscope_bm(bm, (px, py, zt), (1, 0))
    finish2(f"{tag}_LoaderPeriscope", bm, coll, [MAT["detail"], MAT["vision"]], tp)
    bm = bmesh.new(); vx, vy = D["turret_vent_xy"]
    bm_lathe(bm, [(zt, 0.0), (zt, 0.09), (zt + 0.06, 0.08), (zt + 0.06, 0.17), (zt + 0.11, 0.16), (zt + 0.13, 0.10), (zt + 0.13, 0.0)], 20, 'Z', (vx, vy, 0))
    finish2(f"{tag}_TurretVentilator", bm, coll, MAT["detail"], tp)
    le = lift_eye_mesh(tag)
    for i, (x, y) in enumerate(D["turret_lift_eyes"]):
        place(f"{tag}_LiftEye_T{i + 1}", le, coll, tp, (x, y, zt), yaw=math.atan2(y, x))
    revision1_details(tag, coll, root, K, D)

# ================================================================== BASTION detail
def detail_bastion(coll, root):
    tag = "M12A2"; B = P["bastion_m12a2"]; D = S2["bastion_m12a2"]
    E, Hh, T, G = B["envelope"], B["hull"], B["turret"], B["gun"]
    HL = E["hull_length"]["value"]; xr, xf = -HL / 2, HL / 2
    zr, zd = Hh["roof_z"], Hh["engine_deck_z"]
    hull = bpy.data.objects[f"{tag}_Hull"]
    tp = bpy.data.objects[f"{tag}_Turret_Pivot"]; gp = bpy.data.objects[f"{tag}_Gun_Pivot"]
    turret = bpy.data.objects[f"{tag}_Turret"]
    zt = T["base_gap"] + T["height"]; roof_local = zt - 0.02
    u, n, gz = glacis_frame(hull)

    # --- hull hatches: substantial rims (chemical seal), outboard hinges, rotating periscope in each lid
    for key in ("driver", "bow_gunner"):
        h = B["hatches"][key]; side = 1 if h["y"] > 0 else -1
        round_hatch(tag, key, coll, root, (h["x"], h["y"], zr), h["r"], 90 * side, 0.07, 0.085, 0.065,
                    D["hull_hatch_open_deg"], peri_fwd=(1, 0),
                    peri_scale=D["lid_periscope_scale"], peri_toward_hinge=D["lid_periscope_toward_hinge"])
    bx, by = D["bow_mg_xy"]
    ball_mount(tag, coll, root, (bx, by, gz(bx)), n, r=0.12)

    # --- engine deck: fine-bar cooling grilles, bolted removable centre panel, rear-deck exhaust cowl
    gm = grille_mesh_bars(f"{tag}_CoolingGrille", D["grille_len"], 0.92, 12)
    for side, s in (("L", 1), ("R", -1)):
        place(f"{tag}_CoolingGrille_{side}", gm, coll, root, (D["grille_x"], s * 0.93, zd))
    bm = bmesh.new(); access_panel_bm(bm, (D["grille_x"], 0.0, zd), D["grille_len"], 0.70, bolts=12)
    ob = finish2(f"{tag}_EngineAccessPanel", bm, coll, MAT["detail"], root, weld=False); ob["removable"] = True
    bm = bmesh.new()
    tagged(bm, 0, bm_chamfer_box, (xr + 0.25, 0, zd + 0.06), (0.24, 1.70, 0.12), 0.03)
    tagged(bm, 1, bm_box, (xr + 0.125, -0.78, zd + 0.02), (xr + 0.14, 0.78, zd + 0.09))
    finish2(f"{tag}_ExhaustCowl", bm, coll, [MAT["detail"], MAT["recess"]], root, weld=False)

    # --- crew protected air: armoured intake cowl on a bolted filter/blower box (front-right of the deck),
    #     physically separate from the engine cooling grilles
    fx, fy = D["filter_box_xy"]
    bm = bmesh.new()
    bm_chamfer_box(bm, (fx, fy, zd + 0.08), (0.52, 0.46, 0.16), 0.03)
    access_panel_bm(bm, (fx, fy, zd + 0.16), 0.44, 0.38, t=0.02, bolts=8, handles=1)
    ob = finish2(f"{tag}_CrewAir_FilterBlower", bm, coll, MAT["detail"], root, weld=False)
    ob["note"] = "Service location for the crew air filter and blower: bolted armoured lid, reachable from the deck"
    bm = bmesh.new()
    bm_lathe(bm, [(0.0, 0.0), (0.0, 0.07), (0.07, 0.07), (0.07, 0.15), (0.11, 0.14), (0.12, 0.09), (0.12, 0.0)], 18, 'Z', (fx - 0.12, fy, zd + 0.18))
    ob = finish2(f"{tag}_CrewAir_Intake", bm, coll, MAT["detail"], root)
    ob["note"] = "Protected crew air intake (armoured mushroom cowl). Shape alone is not a claim of effective protection"

    # --- rear automotive doors: hinged at the outer edges, swing outward; kept clear of stowage
    for side, s in (("L", 1), ("R", -1)):
        hy = s * 0.91
        hdg = hinge_empty(f"{tag}_RearDoorHinge_{side}", coll, root, (xr - 0.012, hy, 1.18), 0.0, D["rear_door_open_deg"], axis="Z",
                          open_sign=-s)
        hdg["yaw0"] = 0.0
        bm = bmesh.new()
        bm_chamfer_box(bm, (0, -s * 0.41, 0), (0.024, 0.80, 0.70), 0.008)
        for zz in (-0.24, 0.0, 0.24):
            bm_lathe(bm, [(zz - 0.06, 0.0), (zz - 0.06, 0.022), (zz + 0.06, 0.022), (zz + 0.06, 0.0)], 10, 'Z', (-0.006, 0, 0))
        bm_box(bm, (-0.035, -s * 0.72 - 0.015, -0.08), (-0.012, -s * 0.72 + 0.015, 0.08))
        finish2(f"{tag}_RearDoor_{side}", bm, coll, MAT["detail"], hdg, weld=False)

    # --- consistent tow shackles (one mesh, four places), lifting eyes
    bm = bmesh.new()
    for s in (-1, 1):
        bm_box(bm, (0.0, s * 0.055 - 0.018, -0.06), (0.11, s * 0.055 + 0.018, 0.06))
    bm_lathe(bm, [(-0.08, 0.0), (-0.08, 0.02), (0.08, 0.02), (0.08, 0.0)], 10, 'Y', (0.075, 0, 0))
    ring_lathe(bm, 'Z', (0.16, 0, 0), 0.035, 0.06, -0.018, 0.018, 18)
    shackle = mesh_only(f"{tag}_TowShackle", bm, MAT["detail"], weld=False)
    hv = np.array([[v.co.x, v.co.y, v.co.z] for v in hull.data.vertices])
    nose = hv[hv[:, 0] > hv[:, 0].max() - 1e-4]; zn_front = float(nose[:, 2].mean())
    for i, s in enumerate((1, -1)):
        ob = place(f"{tag}_TowShackle_F{i + 1}", shackle, coll, root, (xf - 0.04, s * 0.72, zn_front))
        ob["envelope_exclude"] = "tow fitting (brief: hull length excludes tow fittings)"
        ob = place(f"{tag}_TowShackle_R{i + 1}", shackle, coll, root, (xr + 0.02, s * 1.45, 1.45), yaw=math.pi)
        ob["envelope_exclude"] = "tow fitting (brief: hull length excludes tow fittings)"
    le = lift_eye_mesh(tag)
    for i, (x, y, z) in enumerate(D["hull_lift_eyes"]):
        place(f"{tag}_LiftEye_H{i + 1}", le, coll, root, (x, y, z), yaw=math.atan2(y, 0.0001))

    # --- pioneer tools on the left deck edge, stowage box on the right (rear doors left clear)
    bm = bmesh.new()
    x0, x1 = D["tool_x"]
    bm_box(bm, (x0, 1.50, zd), (x0 + 0.30, 1.66, zd + 0.025))
    bm_lathe(bm, [(x0 + 0.30, 0.0), (x0 + 0.30, 0.02), (x0 + 1.15, 0.02), (x0 + 1.15, 0.0)], 8, 'X', (0, 1.58, zd + 0.02))
    bm_lathe(bm, [(x0 + 0.1, 0.0), (x0 + 0.1, 0.022), (x1, 0.022), (x1, 0.0)], 8, 'X', (0, 1.66, zd + 0.06))
    for x in (x0 + 0.25, x1 - 0.25):
        bm_box(bm, (x - 0.025, 1.48, zd), (x + 0.025, 1.70, zd + 0.09))
    finish2(f"{tag}_PioneerTools", bm, coll, MAT["detail"], root, weld=False)
    bm = bmesh.new()
    sx = D["stowage_box_x"]
    bm_chamfer_box(bm, ((sx[0] + sx[1]) / 2, -1.53, zd + 0.13), (sx[1] - sx[0], 0.30, 0.26), 0.02)
    bm_box(bm, ((sx[0] + sx[1]) / 2 - 0.05, -1.69, zd + 0.18), ((sx[0] + sx[1]) / 2 + 0.05, -1.68, zd + 0.22))
    finish2(f"{tag}_StowageBox", bm, coll, MAT["detail"], root, weld=False)

    # --- turret: split bustle is already a separate object; port, mantlet, coax, cupola, loader hatch
    tx, tz = G["trunnion_rel_x"], G["trunnion_rel_z"]
    hw, hh = D["mantlet_half_w"], D["mantlet_half_h"]
    wt = D["turret_wall"]; zb_ = T["base_gap"]; ring_r = E["turret_ring_diameter"]["value"] / 2
    plan = chaikin(T["plan_body"], 3)
    hollow(turret, tp, [radial_ring(plan, (0, 0), 0.0, -0.40, clamp=ring_r - 0.02), radial_ring(plan, (0, 0), 0.0, zb_ + 0.02, clamp=ring_r - 0.02),
                        radial_ring(plan, (0, 0), wt + 0.13, zb_ + 0.20), radial_ring(plan, (0, 0), wt, zb_ + 0.50),
                        radial_ring(plan, (0, 0), wt + 0.07, zb_ + 0.82), radial_ring(plan, (0, 0), wt + 0.19, zb_ + 0.95),
                        radial_ring(plan, (0, 0), wt + 0.33, zt - D["turret_roof_t"])])
    port_cut(turret, tp, (tx, tz), D["mantlet_R_back"] + D["port_gap"], hw + 0.03)
    old = bpy.data.objects[f"{tag}_Mantlet"]; me_ = old.data; bpy.data.objects.remove(old); bpy.data.meshes.remove(me_)
    bm = bmesh.new()
    ff = lambda y: 0.20 + 0.12 * math.sqrt(max(0.0, 1 - (y / hw) ** 2))
    mantlet_bm(bm, hw, hh, D["mantlet_R_back"], ff, 0.06, ny=13)
    cy_ = D["coax_y"]
    tagged(bm, 1, bm_lathe, [(ff(cy_) - 0.03, 0.0), (ff(cy_) - 0.03, 0.04), (ff(cy_) + 0.01, 0.04), (ff(cy_) + 0.01, 0.0)], 14, 'X', (0, cy_, 0.03))
    sy = D["sight_y"]
    tagged(bm, 1, bm_obox, (ff(sy) + 0.003, sy, 0.12), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.012, 0.035, 0.025)
    finish2(f"{tag}_Mantlet", bm, coll, [MAT["armor"], MAT["vision"]], gp)
    bm = bmesh.new()
    bm_lathe(bm, [(ff(cy_) - 0.01, 0.0), (ff(cy_) - 0.01, 0.02), (ff(cy_) + 0.09, 0.017), (ff(cy_) + 0.09, 0.0)], 10, 'X', (0, cy_, 0.03))
    finish2(f"{tag}_CoaxMG", bm, coll, MAT["detail"], gp)
    breech_placeholder(tag, coll, gp, -D["breech_len"], -0.05, 0.22, D["breech_half_h"])

    C = B["cupola"]; ztop = E["cupola_height"]["value"] - zr
    cupola(tag, coll, tp, C["rel_x"], C["rel_y"], roof_local, ztop, C["r"], D["cupola_blocks"], D["cupola_hinge_dir_deg"],
           D.get("cupola_open_deg", D["turret_hatch_open_deg"]), band_frac=0.45)
    h = B["hatches"]["loader"]
    rect_hatch(tag, "loader", coll, tp, (h["rel_x"], h["rel_y"], roof_local), h["len"], h["wid"], "+y", 0.06, 0.07, 0.055,
               D["turret_hatch_open_deg"])
    bm = bmesh.new(); px, py = D["loader_periscope_xy"]; periscope_bm(bm, (px, py, roof_local), (1, 0))
    finish2(f"{tag}_LoaderPeriscope", bm, coll, [MAT["detail"], MAT["vision"]], tp)
    bm = bmesh.new(); px, py = D["gunner_periscope_xy"]; periscope_bm(bm, (px, py, roof_local), (1, 0))
    finish2(f"{tag}_GunnerPeriscope", bm, coll, [MAT["detail"], MAT["vision"]], tp)
    bm = bmesh.new(); vx, vy = D["turret_vent_xy"]
    bm_lathe(bm, [(roof_local, 0.0), (roof_local, 0.08), (roof_local + 0.05, 0.07), (roof_local + 0.05, 0.15),
                  (roof_local + 0.09, 0.14), (roof_local + 0.11, 0.09), (roof_local + 0.11, 0.0)], 20, 'Z', (vx, vy, 0))
    ob = finish2(f"{tag}_TurretVentilator", bm, coll, MAT["detail"], tp)
    ob["note"] = "Protected turret ventilator (fume extraction)"
    le = bpy.data.meshes[f"{tag}_LiftEye"]
    for i, (x, y, z) in enumerate(D["turret_lift_eyes"]):
        place(f"{tag}_LiftEye_T{i + 1}", le, coll, tp, (x, y, z), yaw=math.atan2(y, x))
    bz = zt - 0.015
    for i, (x, y) in enumerate(D["aerial_xy"]):
        aerial(tag, i + 1, coll, tp, (x, y, bz - 0.01))

    # --- removable external .50 roof mount, worked by the commander from the cupola.
    #     Fixed pintle post on the roof; gun, cradle and ammunition box traverse on <TAG>_RoofMG50_Pivot.
    #     (Rev. 1: moved forward from the rear roof so the grips sit beside the open cupola.)
    mx, my = D["roof_mg_xy"]
    pz = roof_local + 0.40
    bm = bmesh.new()
    bm_lathe(bm, [(roof_local - 0.02, 0.0), (roof_local - 0.02, 0.09), (roof_local + 0.03, 0.09), (roof_local + 0.03, 0.04),
                  (roof_local + 0.33, 0.035), (roof_local + 0.33, 0.0)], 14, 'Z', (mx, my, 0))
    mount = finish2(f"{tag}_RoofMG50_Mount", bm, coll, MAT["detail"], tp, weld=False)
    piv = empty(f"{tag}_RoofMG50_Pivot", coll, tp, loc=(mx, my, pz))
    piv["note"] = "Pintle axis of the .50: rotate about local Z to traverse the gun"
    bm = bmesh.new()
    gz0 = 0.07
    bm_box(bm, (-0.10, -0.06, -0.07), (0.10, 0.06, 0.0))                                   # cradle on the pintle
    bm_box(bm, (-0.62, -0.06, gz0 - 0.08), (0.18, 0.06, gz0 + 0.08))                       # receiver
    bm_box(bm, (-0.75, -0.02, gz0 - 0.05), (-0.62, 0.02, gz0 + 0.03))                      # spade grips
    bm_lathe(bm, [(0.18, 0.0), (0.18, 0.045), (0.48, 0.045), (0.48, 0.022), (1.08, 0.022), (1.08, 0.0)], 10, 'X', (0, 0, gz0))
    bm_box(bm, (-0.32, 0.06, gz0 - 0.12), (-0.08, 0.18, gz0 + 0.02))                       # ammunition box
    gun = finish2(f"{tag}_RoofMG50", bm, coll, MAT["detail"], piv, weld=False)
    gun["grip_local"] = (-0.685, 0.0, gz0 - 0.01)
    gun["operator"] = D["roof_mg_operator"]
    for ob in (mount, gun):
        ob["envelope_exclude"] = "external .50 roof mount (brief: excluded from height envelope; removable)"
        ob["removable"] = True
    revision1_details(tag, coll, root, B, D)

# ================================================================== Stage 2 revision 1 (review 15 Oct 2026)
# Smoke and gas grenade dischargers, headlights and tail lights, track pins and end connectors,
# and a defined elevating-gear stop. Every value is in the stage2 block of params.json (approved 15 Oct 2026).
from mathutils.bvhtree import BVHTree as _BVH

def bm_lathe_dir(bm, profile, seg, origin, axis, slot=None):
    """bm_lathe about an arbitrary axis through origin. profile: [(a, r)]; r == 0 collapses to the axis."""
    a = unit(axis); ref = np.array([0, 0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = unit(np.cross(a, ref)); e2 = np.cross(a, e1); o = np.array(origin, float)
    bm.faces.ensure_lookup_table(); n0 = len(bm.faces)
    rings = []
    for s_, r in profile:
        if r <= 1e-9:
            rings.append([bm.verts.new(tuple(o + a * s_))]); continue
        rings.append([bm.verts.new(tuple(o + a * s_ + r * (math.cos(t) * e1 + math.sin(t) * e2)))
                      for t in (2 * math.pi * k / seg for k in range(seg))])
    for A, B_ in zip(rings[:-1], rings[1:]):
        if len(A) == 1 and len(B_) == 1: continue
        if len(A) == 1:
            for k in range(seg): bm.faces.new((A[0], B_[k], B_[(k + 1) % seg]))
        elif len(B_) == 1:
            for k in range(seg): bm.faces.new((A[k], B_[0], A[(k + 1) % seg]))
        else:
            for k in range(seg): bm.faces.new((A[k], A[(k + 1) % seg], B_[(k + 1) % seg], B_[k]))
    if slot is not None:
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]: f.material_index = slot

def turret_surface(turret, az_deg, z):
    """Outer turret surface at plan azimuth az (0 = forward, 90 = left) and height z, in turret-pivot space.
    Returns the hit point and the horizontal outward normal."""
    me = turret.data
    bvh = _BVH.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    a = math.radians(az_deg); d = Vector((-math.cos(a), -math.sin(a), 0.0))
    hit, nrm, _, _ = bvh.ray_cast(Vector((0, 0, z)) - d * 6.0, d, 12.0)
    assert hit is not None, f"no turret surface at azimuth {az_deg}"
    n = np.array([nrm.x, nrm.y, 0.0])
    if np.dot(n, -np.array(d)) < 0: n = -n
    return np.array(hit), unit(n)

def discharger_bank(tag, name, coll, tp, turret, spec, side):
    """A bank of grenade discharger cups on a bracket welded to the turret side.
    Smoke and gas use the same cup; gas cups carry a raised band at the mouth so the crew can tell them apart."""
    s = 1 if side == "L" else -1
    p, n = turret_surface(turret, s * spec["mount_az_deg"], spec["mount_z"])
    up = np.array([0, 0, 1.0]); t = unit(np.cross(up, n))
    fa, fe = math.radians(spec["fire_az_deg"]), math.radians(spec["fire_el_deg"])
    d = np.array([math.cos(fe) * math.cos(fa), s * math.cos(fe) * math.sin(fa), math.sin(fe)])
    ro, ri, L, k = spec["tube_r"], spec["tube_r"] - 0.012, spec["tube_len"], spec["tubes"]
    span = (k - 1) * spec["spacing"]
    bm = bmesh.new()
    tagged(bm, 0, bm_obox, p + n * 0.02, n, t, up, 0.02, span / 2 + ro + 0.04, 0.075)           # bracket plate
    tagged(bm, 0, bm_obox, p + n * 0.06 - up * 0.05, n, t, up, 0.045, span / 2 + ro + 0.02, 0.012)  # shelf
    mouths = []
    for i in range(k):
        b = p + n * (0.08 + ro * 0.6) + t * (i * spec["spacing"] - span / 2) - up * 0.03
        tagged(bm, 0, bm_obox, (b + p + n * 0.04) / 2, unit(b - p - n * 0.04), t, up,
               float(np.linalg.norm(b - p - n * 0.04)) / 2, 0.012, 0.03)                        # strut
        bm_lathe_dir(bm, [(0.0, 0.0), (0.0, ro), (L, ro), (L, ri), (0.04, ri), (0.04, 0.0)], 14, b, d, slot=0)
        bm_lathe_dir(bm, [(L - 0.004, 0.0), (L - 0.004, ri), (L - 0.002, ri), (L - 0.002, 0.0)], 14, b, d, slot=1)
        if spec["kind"] == "gas":
            bm_lathe_dir(bm, [(L - 0.065, ro - 0.002), (L - 0.065, ro + 0.014), (L - 0.03, ro + 0.014), (L - 0.03, ro - 0.002),
                              (L - 0.065, ro - 0.002)], 14, b, d, slot=0)
        mouths.append([float(v) for v in (b + d * L)])
    ob = finish2(f"{tag}_Discharger_{name}_{side}", bm, coll, [MAT["detail"], MAT["recess"]], tp)
    ob["discharger"] = spec["kind"]
    ob["tube_mouths"] = mouths; ob["fire_dir"] = [float(v) for v in d]; ob["tube_bore_r"] = ri
    ob["note"] = f"{k} x {spec['kind']} grenade discharger cups, fired electrically from inside the turret"
    return ob

def headlight(tag, name, coll, root, hull, spec, side, style):
    """Headlight on the upper glacis with an armoured hood (KS) or a bar brush guard (Bastion)."""
    s = 1 if side == "L" else -1
    x0, z0, x1, z1 = hull["glacis_line"]
    gx_at = lambda z: x0 + (z - z0) * (x1 - x0) / (z1 - z0)
    zc, y = spec["z"], s * spec["y"]; r = spec["r"]
    xb = gx_at(zc - r) + 0.015                                   # lamp back clears the sloped plate
    lamps = [(zc, r)] + ([(zc - r - spec["blackout_r"] - 0.02, spec["blackout_r"])] if spec.get("blackout_r") else [])
    bm = bmesh.new()
    for zz, rr in lamps:
        xg = gx_at(zz - rr) + 0.015
        tagged(bm, 0, bm_box, (gx_at(zz) - 0.05, y - 0.035, zz - 0.035), (xg + 0.03, y + 0.035, zz + 0.035))     # bracket
        tagged(bm, 0, bm_lathe, [(xg, 0.0), (xg, rr * 0.8), (xg + 0.04, rr), (xg + 0.13, rr), (xg + 0.13, 0.0)], 16, 'X', (0, y, zz))
        tagged(bm, 1, bm_lathe, [(xg + 0.13, 0.0), (xg + 0.13, rr * 0.85), (xg + 0.136, rr * 0.85), (xg + 0.136, 0.0)], 16, 'X', (0, y, zz))
    xf_ = xb + 0.13
    if style == "hood":
        tagged(bm, 0, bm_box, (xb - 0.02, y - r - 0.03, zc + r + 0.005), (xf_ + 0.05, y + r + 0.03, zc + r + 0.03))
        for yy in (y - r - 0.03, y + r + 0.012):
            tagged(bm, 0, bm_box, (xb, yy, zc - r * 0.3), (xf_ + 0.05, yy + 0.018, zc + r + 0.03))
    else:
        zb_ = lamps[-1][0] - lamps[-1][1] - 0.03; zt_ = zc + r + 0.04; xg = xf_ + 0.07
        for yy in (y - r - 0.05, y + r + 0.05):
            tagged(bm, 0, bm_box, (xg - 0.012, yy - 0.012, zb_), (xg + 0.012, yy + 0.012, zt_))
            tagged(bm, 0, bm_box, (gx_at(zt_) - 0.06, yy - 0.012, zt_ - 0.024), (xg + 0.012, yy + 0.012, zt_))
        tagged(bm, 0, bm_box, (xg - 0.012, y - r - 0.06, zt_ - 0.024), (xg + 0.012, y + r + 0.06, zt_))
        tagged(bm, 0, bm_box, (xg - 0.012, y - 0.012, zb_), (xg + 0.012, y + 0.012, zt_))
    ob = finish2(f"{tag}_Headlight_{name}_{side}", bm, coll, [MAT["detail"], MAT["vision"]], root, weld=False)
    ob["note"] = "Driving headlight" + (" with blackout marker lamp" if spec.get("blackout_r") else "")

def tail_light(tag, coll, root, x, y, z, side):
    bm = bmesh.new()
    tagged(bm, 0, bm_box, (x - 0.05, y - 0.07, z), (x + 0.05, y + 0.07, z + 0.10))
    tagged(bm, 1, bm_box, (x - 0.056, y - 0.045, z + 0.03), (x - 0.05, y + 0.045, z + 0.075))
    tagged(bm, 0, bm_box, (x - 0.09, y - 0.08, z + 0.10), (x + 0.05, y + 0.08, z + 0.12))     # rain/armour hood
    ob = finish2(f"{tag}_TailLight_{side}", bm, coll, [MAT["detail"], MAT["vision"]], root, weld=False)
    ob["note"] = "Tail and convoy light under a hood, on the rear deck inside the hull length"

def track_link_detail(tag, R):
    """Rebuild the shared track-link mesh with pins. Every link and spare link uses this mesh."""
    me = bpy.data.meshes[f"{tag}_TrackLink"]
    pitch, t = R["track_pitch"], R["track_thickness"]
    w = P["kaisersturm_b" if tag == "KS_B" else "bastion_m12a2"]["envelope"]["track_width"]["value"]
    TD = S2["kaisersturm_b" if tag == "KS_B" else "bastion_m12a2"]["track_detail"]
    L = pitch * 0.46; hw = w / 2
    bm = bmesh.new()
    if TD["style"] == "dry_pin":
        # plate between the joints; hinge lugs alternate across the width (even lugs at the +x joint,
        # odd lugs at the -x joint) so neighbouring links interleave on one pin per joint
        xm, kr, n = pitch / 2 - 0.045, TD["knuckle_r"], TD["lugs"]
        bm_box(bm, (-xm, -hw, -t / 2), (xm, hw, t / 2))
        bm_box(bm, (-0.025, -hw + 0.02, t / 2), (0.025, hw - 0.02, t / 2 + GROUSER))
        bm_box(bm, (-L * 0.55, -0.03, -t / 2 - 0.09), (min(L * 0.55, xm), 0.03, -t / 2))
        ws = w / n
        for i in range(n):
            y0, y1 = -hw + i * ws + 0.003, -hw + (i + 1) * ws - 0.003
            e = 1 if i % 2 == 0 else -1
            bm_box(bm, (min(e * xm, e * pitch / 2), y0, -kr), (max(e * xm, e * pitch / 2), y1, kr))
            bm_lathe(bm, [(y0, 0.0), (y0, kr), (y1, kr), (y1, 0.0)], 8, 'Y', (e * pitch / 2, 0, 0))
        for a0, a1 in ((-hw, -hw + 0.006), (hw - 0.006, hw)):
            bm_lathe(bm, [(a0, 0.0), (a0, TD["pin_head_r"]), (a1, TD["pin_head_r"]), (a1, 0.0)], 8, 'Y', (pitch / 2, 0, 0))
    else:   # double pin, rubber-bushed, joined by end connectors with wedge bolts at both edges
        ce = TD["connector_w"]; hs = hw - ce - 0.005
        bm_box(bm, (-L, -hs, -t / 2), (L, hs, t / 2))
        bm_box(bm, (-0.025, -hs + 0.02, t / 2), (0.025, hs - 0.02, t / 2 + GROUSER))
        bm_box(bm, (-L * 0.55, -0.03, -t / 2 - 0.09), (L * 0.55, 0.03, -t / 2))
        xp = TD["pin_x"]; ch = TD["connector_h"]
        for sx in (-1, 1):
            for a0, a1 in ((-hw + 0.004, -hs), (hs, hw - 0.004)):
                bm_lathe(bm, [(a0, 0.0), (a0, TD["pin_r"]), (a1, TD["pin_r"]), (a1, 0.0)], 8, 'Y', (sx * xp, 0, 0))
        for a0, a1 in ((-hw, -hw + ce), (hw - ce, hw)):
            bm_box(bm, (xp - 0.03, a0, -ch / 2), (pitch - xp + 0.03, a1, ch / 2))
            bm_lathe(bm, [(ch / 2 - 0.002, 0.0), (ch / 2 - 0.002, 0.016), (ch / 2 + 0.016, 0.016), (ch / 2 + 0.016, 0.0)], 6, 'Z',
                     (pitch / 2, (a0 + a1) / 2, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False

def revision1_details(tag, coll, root, V, D):
    tp = bpy.data.objects[f"{tag}_Turret_Pivot"]; gp = bpy.data.objects[f"{tag}_Gun_Pivot"]
    turret = bpy.data.objects[f"{tag}_Turret"]; hull = bpy.data.objects[f"{tag}_Hull"]
    for name, spec in D["dischargers"].items():
        for side in ("L", "R"):
            discharger_bank(tag, name, coll, tp, turret, spec, side)
    for side in ("L", "R"):
        headlight(tag, "F", coll, root, hull, D["headlights"], side, D["headlights"]["style"])
    TL = D["tail_lights"]; xr = -V["envelope"]["hull_length"]["value"] / 2
    zdeck = V["hull"].get("engine_deck_z", V["hull"]["roof_z"])
    for side, s in (("L", 1), ("R", -1)):
        tail_light(tag, coll, root, xr + TL["x_from_rear"], s * TL["y"], zdeck, side)
    track_link_detail(tag, V["running_gear"])
    gp["elevation_stop_deg"] = D["elevation_stop_deg"]
    gp["note"] = (f"Elevation axis (trunnion) - rotate about local Y. Elevating gear stop +{D['elevation_stop_deg']} deg; "
                  "depression is limited physically (see stage2_report.json)")
