"""
Weltenbrecher - Stage 3 finish.
Executed inside generate.py's namespace after stage2.py (shares its helpers, MAT, P, GROUSER).

stage3_markings()  adds markings as separate objects (decal meshes and editable Blender text).
stage3_finish()    unwraps each tank, bakes paint, wear and surface texture from procedural source
                   shaders into one texture set per tank, and rewires the materials to those textures
                   so the .blend and the GLBs carry the same finish.
Every value lives in the stage3 block of params.json.
"""
import bpy, bmesh, math, os, time
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

S3 = P["stage3"]

def lin(hexstr):
    """sRGB hex -> linear RGBA for Blender colour sockets."""
    h = hexstr.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)

# ================================================================== markings
MARK_MAT = {}
def mark_mat(name, hexstr, rough=0.7):
    if name not in MARK_MAT:
        m = make_mat(name, lin(hexstr)[:3], rough)
        m.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = lin(hexstr)
        MARK_MAT[name] = m
    return MARK_MAT[name]

def world_hit(ob, origin, direction):
    M = ob.matrix_world
    bvh = BVHTree.FromPolygons([M @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])
    d = Vector(direction).normalized()
    hit, nrm, _, _ = bvh.ray_cast(Vector(origin), d, 20.0)
    assert hit is not None, f"marking ray missed {ob.name}"
    if nrm.dot(d) > 0: nrm = -nrm
    return hit, nrm.normalized()

def surface_frame(p, n):
    """Decal frame: Z = surface normal, X = viewer's right, Y = up along the surface."""
    up = Vector((0, 0, 1))
    right = up.cross(n)
    if right.length < 1e-6: right = Vector((1, 0, 0))
    right.normalize(); upv = n.cross(right).normalized()
    M = Matrix((right, upv, n)).transposed().to_4x4()
    M.translation = p + n * S3["markings"]["proud_m"]
    return M

def attach(ob, parent, M_world):
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = parent.matrix_world.inverted() @ M_world

def poly_offset(pts, d):
    """Mitred outward offset of a CCW simple polygon."""
    pts = np.array(pts, float); n = len(pts); out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1, e2 = b - a, c - b
        n1 = np.array([e1[1], -e1[0]]) / np.linalg.norm(e1); n2 = np.array([e2[1], -e2[0]]) / np.linalg.norm(e2)
        m = n1 + n2; m /= np.linalg.norm(m)
        out.append(b + m * d / max(np.dot(m, n1), 0.3))
    return out

def cross_polys(style, S):
    """Cross as convex pieces (centre square + four arms), so triangulation can't fill the notches."""
    R = S / 2
    c, e = (0.075 * S, 0.21 * S) if style == "pattee" else (0.11 * S, 0.11 * S)
    out = [[(c, -c), (c, c), (-c, c), (-c, -c)]]
    for k in range(4):
        a = k * math.pi / 2; ca, sa = math.cos(a), math.sin(a)
        out.append([(x * ca - y * sa, x * sa + y * ca) for x, y in [(c, -c), (R, -e), (R, e), (c, c)]])
    return out

def star_polys(S):
    """Five-pointed star as a centre pentagon plus five point triangles."""
    R, r = S / 2, S / 2 * 0.382
    pt = lambda rad, i: (rad * math.cos(math.pi / 2 + i * math.pi / 5), rad * math.sin(math.pi / 2 + i * math.pi / 5))
    inner = [pt(r, 2 * k + 1) for k in range(5)]
    return [inner] + [[inner[k - 1], pt(R, 2 * k), inner[k]] for k in range(5)]

def decal(name, layers, coll, parent, M_world, note):
    """layers: [(convex polygons, material)] stacked 0.5 mm apart, first at the back."""
    bm = bmesh.new(); mats = []
    for i, (polys, mat) in enumerate(layers):
        for poly in polys:
            f = bm.faces.new([bm.verts.new((x, y, 0.0005 * i)) for x, y in poly])
            f.material_index = i
        mats.append(mat)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    attach(ob, parent, M_world)
    ob["marking"] = note
    ob["envelope_exclude"] = "paint marking (modeled 1.5 mm proud of the plate so it renders cleanly)"
    return ob

def text_marking(name, body, height, mat, coll, parent, M_world, note):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body; cu.size = height / 0.72; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob)
    attach(ob, parent, M_world)
    ob["marking"] = note
    ob["editable_text"] = True
    return ob

def stage3_markings():
    M3 = S3["markings"]; O = bpy.data.objects
    white, black = mark_mat("Marking_White", "#E4E0D2", 0.75), mark_mat("Marking_Black", "#121212", 0.75)
    # --- Kaisersturm: Imperial crosses (black, white border), tactical number
    tag = "KS_B"; K = M3["kaisersturm_b"]; coll = bpy.data.collections[tag]
    tp, hull, turret = O[f"{tag}_Turret_Pivot"], O[f"{tag}_Hull"], O[f"{tag}_Turret"]
    Tw = tp.matrix_world
    tc, tn = K["turret_cross"], K["tactical_number"]
    for side, s in (("L", 1), ("R", -1)):
        p, n = world_hit(turret, Tw @ Vector((tc["x"], s * 3.0, tc["z"])), (0, -s, 0))
        cp = cross_polys(K["cross_style"], tc["size"])
        decal(f"{tag}_Marking_Cross_{side}", [([poly_offset(q, tc["size"] * 0.045) for q in cp], white), (cp, black)], coll, tp,
              surface_frame(p, n), f"Imperial cross ({K['cross_style']})")
        p, n = world_hit(turret, Tw @ Vector((tn["x"], s * 3.0, tn["z"])), (0, -s, 0))
        text_marking(f"{tag}_Marking_Number_{side}", tn["text"], tn["height"], white, coll, tp, surface_frame(p, n), "tactical number")
    xr = -P["kaisersturm_b"]["envelope"]["hull_length"]["value"] / 2
    rc = K["rear_cross"]
    p, n = world_hit(hull, (xr - 3.0, 0.0, rc["z"]), (1, 0, 0))
    cp = cross_polys(K["cross_style"], rc["size"])
    decal(f"{tag}_Marking_Cross_Rear", [([poly_offset(q, rc["size"] * 0.045) for q in cp], white), (cp, black)], coll, O[f"{tag}_Root"],
          surface_frame(p, n), f"Imperial cross ({K['cross_style']})")

    # --- Bastion: white stars, bumper codes front and rear, optional "Okie Gusher" decal
    tag = "M12A2"; B = M3["bastion_m12a2"]; coll = bpy.data.collections[tag]
    hull, root = O[f"{tag}_Hull"], O[f"{tag}_Root"]
    st = B["star"]
    for side, s in (("L", 1), ("R", -1)):
        p, n = world_hit(hull, (st["x"], s * 4.0, st["z"]), (0, -s, 0))
        decal(f"{tag}_Marking_Star_{side}", [(star_polys(st["size"]), white)], coll, root, surface_frame(p, n), "national star")
    bc = B["bumper_codes"]; xr = -P["bastion_m12a2"]["envelope"]["hull_length"]["value"] / 2
    for side, s in (("L", 1), ("R", -1)):
        body = bc["left"] if s > 0 else bc["right"]
        p, n = world_hit(hull, (6.0, s * bc["front_y"], bc["front_z"]), (-1, 0, 0))
        text_marking(f"{tag}_Marking_Bumper_F{side}", body, bc["height"], white, coll, root, surface_frame(p, n), "unit bumper code")
        # seen from behind, the vehicle's right is on the viewer's left
        body = bc["right"] if s > 0 else bc["left"]
        p, n = world_hit(hull, (xr - 3.0, s * bc["rear_y"], bc["rear_z"]), (1, 0, 0))
        text_marking(f"{tag}_Marking_Bumper_R{side}", body, bc["height"], white, coll, root, surface_frame(p, n), "unit bumper code")
    od = B["optional_decal"]; s = 1 if od["side"] == "L" else -1
    oc = bpy.data.collections.new(f"{tag}_Optional_Decals"); coll.children.link(oc)
    p, n = world_hit(hull, (od["x"], s * 4.0, od["z"]), (0, -s, 0))
    ob = text_marking(f"{tag}_Decal_OkieGusher", od["text"], od["height"], white, oc, root, surface_frame(p, n), "optional name decal")
    ob["optional_decal"] = True
    ob["note"] = "Optional decal, kept as editable text and exported as its own GLB, never baked into the base model"

# ================================================================== procedural source shaders (bake only)
class NB:
    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree; self.nt.nodes.clear(); self.n = self.nt.nodes; self.l = self.nt.links
    def node(self, t, **kw):
        nd = self.n.new(t)
        for k, v in kw.items(): setattr(nd, k, v)
        return nd
    def put(self, sock, x):
        if isinstance(x, (int, float)): sock.default_value = x
        elif isinstance(x, tuple): sock.default_value = x
        else: self.l.new(x, sock)
    def math(self, op, a, b=None, clamp=False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(nd.inputs[0], a)
        if b is not None: self.put(nd.inputs[1], b)
        return nd.outputs[0]
    def vmath(self, op, a, b=None):
        scale = op == 'SCALE_V'
        nd = self.node("ShaderNodeVectorMath", operation='SCALE' if scale else op)
        self.put(nd.inputs[0], a)
        if b is not None: self.put(nd.inputs["Scale"] if scale else nd.inputs[1], b)
        return nd.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else nd.outputs["Vector"]
    def smooth(self, x, a, b):
        nd = self.node("ShaderNodeMapRange", interpolation_type='SMOOTHSTEP', clamp=True)
        self.put(nd.inputs["Value"], x); nd.inputs["From Min"].default_value = a; nd.inputs["From Max"].default_value = b
        return nd.outputs["Result"]
    def noise(self, vec, scale, detail=4.0, rough=0.55, distortion=0.0):
        nd = self.node("ShaderNodeTexNoise")
        self.put(nd.inputs["Vector"], vec); nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail; nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = distortion
        return nd.outputs["Fac"]
    def mixc(self, fac, a, b, blend='MIX'):
        nd = self.node("ShaderNodeMix", data_type='RGBA', blend_type=blend, clamp_factor=True)
        self.put(nd.inputs[0], fac); self.put(nd.inputs[6], a); self.put(nd.inputs[7], b)
        return nd.outputs[2]
    def mixv(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type='VECTOR', clamp_factor=True)
        self.put(nd.inputs[0], fac); self.put(nd.inputs[4], a); self.put(nd.inputs[5], b)
        return nd.outputs[1]
    def mixf(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type='FLOAT', clamp_factor=True)
        self.put(nd.inputs[0], fac); self.put(nd.inputs[2], a); self.put(nd.inputs[3], b)
        return nd.outputs[0]
    def attr(self, name):
        return self.node("ShaderNodeAttribute", attribute_type='OBJECT', attribute_name=name).outputs["Fac"]
    def maxall(self, xs):
        out = xs[0]
        for x in xs[1:]: out = self.math('MAXIMUM', out, x)
        return out
    def point_mask(self, P, pts, r, scale=(1, 1, 1)):
        ms = []
        for c in pts:
            d = self.vmath('LENGTH', self.vmath('MULTIPLY', self.vmath('SUBTRACT', P, tuple(c)), tuple(scale)))
            ms.append(self.math('SUBTRACT', 1.0, self.math('DIVIDE', d, r), clamp=True))
        return self.maxall(ms) if ms else 0.0

def build_source(mat, tag, cat, ctx):
    """Procedural finish for one tank/category. Returns the bake hookups."""
    F = S3["finish"]; T = F[ctx["key"]]; SF = S3["surface"]
    nb = NB(mat)
    geo = nb.node("ShaderNodeNewGeometry"); P_, N_, TN = geo.outputs["Position"], geo.outputs["Normal"], geo.outputs["True Normal"]
    Nz = nb.node("ShaderNodeSeparateXYZ"); nb.put(Nz.inputs[0], N_)
    Pz = nb.node("ShaderNodeSeparateXYZ"); nb.put(Pz.inputs[0], P_)
    OB = nb.node("ShaderNodeTexCoord").outputs["Object"]
    out = {"bump": None}
    if cat in ("vision", "recess"):
        out["color"] = lin(F["glass_srgb"]) if cat == "vision" else (0.012, 0.012, 0.012, 1.0)
        out["rough"], out["metal"] = (0.08, 0.0) if cat == "vision" else (0.92, 0.0)
        return nb, out

    dust_amt, mud_amt = T["dust_amount"], T["mud_amount"]
    dn = nb.noise(P_, 2.2, 6.0, 0.6)
    lowz = nb.smooth(Pz.outputs[2], 0.95, 0.15)

    if cat == "track":
        no = nb.node("ShaderNodeVectorTransform", vector_type='NORMAL', convert_from='WORLD', convert_to='OBJECT')
        nb.put(no.inputs[0], N_)
        nos = nb.node("ShaderNodeSeparateXYZ"); nb.put(nos.inputs[0], no.outputs[0])
        pol = nb.math('MULTIPLY', nb.smooth(nb.math('ABSOLUTE', nos.outputs[2]), 0.6, 0.85),
                      nb.smooth(nb.noise(OB, 18.0, 4.0), 0.25, 0.45))
        col = nb.mixc(pol, lin(F["track_steel_srgb"]), lin(F["track_polished_srgb"]))
        rough = nb.mixf(pol, 0.72, 0.3); metal = nb.mixf(pol, 0.6, 1.0)
        d = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, pol), nb.smooth(dn, 0.3, 0.8)), dust_amt * 1.4, clamp=True)
        col = nb.mixc(d, col, lin(F["dust_srgb"])); rough = nb.mixf(d, rough, F["dust_roughness"]); metal = nb.mixf(d, metal, 0.0)
        m = nb.math('MULTIPLY', nb.math('MULTIPLY', lowz, nb.smooth(dn, 0.35, 0.7)), mud_amt * 1.5, clamp=True)
        out.update(color=nb.mixc(m, col, lin(F["mud_srgb"])), rough=nb.mixf(m, rough, 0.95), metal=nb.mixf(m, metal, 0.0))
        return nb, out

    # --- paint with gentle mottling; the replaced panel is a fresher shade
    replaced = nb.attr("fin_replaced")
    paint = lin(T["paint_srgb"])
    if T.get("replaced_panel_srgb"):
        paint = nb.mixc(replaced, paint, lin(T["replaced_panel_srgb"]))
    mott = nb.math('ADD', 0.93, nb.math('MULTIPLY', nb.noise(P_, 0.7, 3.0), 0.14))
    col = nb.mixc(1.0, paint, mott, blend='MULTIPLY')
    rough, metal = F["paint_roughness"], 0.0

    # --- rubber tyres on road wheels, idlers and return rollers (object space, so every instance matches)
    tyre_r = nb.attr("fin_tyre_r")
    obs = nb.node("ShaderNodeSeparateXYZ"); nb.put(obs.inputs[0], OB)
    rad = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', obs.outputs[0], obs.outputs[0]), nb.math('MULTIPLY', obs.outputs[2], obs.outputs[2])))
    tyre = nb.math('MULTIPLY', nb.math('GREATER_THAN', tyre_r, 0.01),
                   nb.math('GREATER_THAN', rad, nb.math('SUBTRACT', tyre_r, 0.058)))
    col = nb.mixc(tyre, col, lin(F["rubber_srgb"])); rough = nb.mixf(tyre, rough, 0.88)

    # --- edge wear and scratches at access points -> bare steel
    bev = nb.node("ShaderNodeBevel", samples=8); bev.inputs["Radius"].default_value = 0.012
    edge = nb.math('SUBTRACT', 1.0, nb.vmath('DOT_PRODUCT', bev.outputs[0], TN))
    edge_m = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.smooth(edge, 0.02, 0.09), nb.smooth(nb.noise(P_, 9.0, 6.0), 0.48, 0.62)),
                     nb.math('MULTIPLY', T["edge_wear"], nb.math('SUBTRACT', 1.0, replaced)))
    acc = nb.point_mask(P_, ctx["access"], 0.65)
    scr = nb.math('MULTIPLY', nb.math('MULTIPLY', acc, nb.smooth(nb.noise(P_, 38.0, 2.0, 0.5, 5.0), 0.64, 0.7)), T["access_scratches"])
    wear = nb.math('MAXIMUM', nb.math('MULTIPLY', edge_m, nb.math('SUBTRACT', 1.0, tyre)), scr)
    col = nb.mixc(wear, col, lin(F["bare_steel_srgb"])); rough = nb.mixf(wear, rough, 0.45); metal = nb.mixf(wear, metal, 0.75)

    # --- fender abrasion (Bastion): bottom edge of the sponsons, where the tracks throw grit
    if T.get("fender_abrasion"):
        zf = P[ctx["key"]]["hull"]["sponson_floor_z"]
        ay = nb.node("ShaderNodeSeparateXYZ"); nb.put(ay.inputs[0], P_)
        band = nb.math('MULTIPLY', nb.smooth(nb.math('ABSOLUTE', ay.outputs[1]), 1.55, 1.78),
                       nb.math('MULTIPLY', nb.smooth(Pz.outputs[2], zf - 0.03, zf + 0.01), nb.smooth(Pz.outputs[2], zf + 0.20, zf + 0.08)))
        fa = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('MULTIPLY', band, nb.attr("fin_fender")),
                                         nb.smooth(nb.noise(P_, 24.0, 3.0, 0.5, 3.0), 0.5, 0.62)), T["fender_abrasion"])
        col = nb.mixc(fa, col, lin(F["bare_steel_srgb"])); rough = nb.mixf(fa, rough, 0.4); metal = nb.mixf(fa, metal, 0.8)

    # --- exhaust soot and rear-engine grime
    if T.get("exhaust_soot"):
        so = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.point_mask(P_, ctx["exhaust"], 0.75, (0.8, 1.7, 1.0)),
                                         nb.smooth(nb.noise(P_, 4.0, 5.0), 0.3, 0.7)), T["exhaust_soot"])
        col = nb.mixc(so, col, lin(F["soot_srgb"])); rough = nb.mixf(so, rough, 0.95)
    if T.get("rear_grime"):
        xr = ctx["xr"]; px = nb.node("ShaderNodeSeparateXYZ"); nb.put(px.inputs[0], P_)
        gr = nb.math('MAXIMUM', nb.math('MULTIPLY', nb.smooth(px.outputs[0], xr + 1.5, xr + 0.1), nb.smooth(dn, 0.35, 0.8)),
                     nb.point_mask(P_, ctx["exhaust"], 0.8, (0.8, 1.2, 1.0)))
        gr = nb.math('MULTIPLY', gr, T["rear_grime"])
        col = nb.mixc(gr, col, nb.mixc(0.5, lin(F["soot_srgb"]), lin(F["mud_srgb"]))); rough = nb.mixf(gr, rough, 0.88)

    # --- grease at service points and wheel hubs (dark, glossy)
    if T.get("grease"):
        hub_r = nb.attr("fin_hub_r")
        hub = nb.math('MULTIPLY', nb.math('GREATER_THAN', hub_r, 0.01), nb.math('LESS_THAN', rad, nb.math('MULTIPLY', hub_r, 1.15)))
        gs = nb.math('MAXIMUM', nb.math('MULTIPLY', nb.point_mask(P_, ctx["grease"], 0.45), nb.smooth(nb.noise(P_, 7.0, 4.0), 0.45, 0.62)),
                     nb.math('MULTIPLY', hub, nb.smooth(nb.noise(OB, 10.0, 3.0), 0.4, 0.6)))
        gs = nb.math('MULTIPLY', gs, T["grease"])
        col = nb.mixc(gs, col, lin(F["grease_srgb"])); rough = nb.mixf(gs, rough, 0.28); metal = nb.mixf(gs, metal, 0.0)

    # --- dust: horizontal surfaces, lower hull, dusty hatch seals; fresher replaced panel carries less
    up = nb.smooth(Nz.outputs[2], 0.45, 0.85)
    dmask = nb.math('ADD', nb.math('ADD', up, nb.math('MULTIPLY', lowz, 0.6)), nb.math('MULTIPLY', nb.attr("fin_dust_boost"), 0.6))
    dmask = nb.math('MULTIPLY', nb.math('MULTIPLY', dmask, nb.smooth(dn, 0.32, 0.78)),
                    nb.math('MULTIPLY', dust_amt * 1.6, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', replaced, 0.7))), clamp=True)
    col = nb.mixc(dmask, col, lin(F["dust_srgb"])); rough = nb.mixf(dmask, rough, F["dust_roughness"]); metal = nb.mixf(dmask, metal, 0.0)
    mud = nb.math('MULTIPLY', nb.math('MULTIPLY', lowz, nb.smooth(nb.noise(P_, 3.0, 6.0), 0.4, 0.7)), mud_amt * 1.5, clamp=True)
    col = nb.mixc(mud, col, lin(F["mud_srgb"])); rough = nb.mixf(mud, rough, 0.95)

    # --- surface relief: cast texture and weld beads (normal map only). Cycles' Bump node has no effect
    #     while baking, so the shading normal is built directly: noise-perturbed for cast surfaces, the
    #     Bevel node's rounded-edge normal (with a ripple) for weld beads along plate joints.
    def noisevec(scale, detail):
        nd = nb.node("ShaderNodeTexNoise"); nb.put(nd.inputs["Vector"], P_)
        nd.inputs["Scale"].default_value = scale; nd.inputs["Detail"].default_value = detail
        return nb.vmath('SUBTRACT', nd.outputs["Color"], (0.5, 0.5, 0.5))
    cast_k = nb.math('MULTIPLY', nb.attr("fin_cast"), SF["cast_bump_strength"])
    n_cast = nb.vmath('NORMALIZE', nb.vmath('ADD', N_, nb.vmath('SCALE_V', noisevec(SF["cast_bump_scale"], 8.0), cast_k)))
    bev2 = nb.node("ShaderNodeBevel", samples=8); bev2.inputs["Radius"].default_value = SF["weld_bead_width"]
    e2 = nb.math('SUBTRACT', 1.0, nb.vmath('DOT_PRODUCT', bev2.outputs[0], TN))
    bead = nb.math('MULTIPLY', nb.smooth(e2, 0.01, 0.08), nb.attr("fin_weld"))
    n_weld = nb.vmath('NORMALIZE', nb.vmath('ADD', bev2.outputs[0],
                                            nb.vmath('SCALE_V', noisevec(150.0, 1.0), nb.math('MULTIPLY', bead, SF["weld_strength"]))))
    n_out = nb.vmath('NORMALIZE', nb.mixv(nb.math('MULTIPLY', bead, 1.0, clamp=True), n_cast, n_weld))
    # the bead also reads as a slightly darker, rougher line so seams show at close range
    wl = nb.math('MULTIPLY', bead, nb.math('ADD', 0.6, nb.math('MULTIPLY', nb.noise(P_, 90.0, 2.0), 0.6)))
    col = nb.mixc(nb.math('MULTIPLY', wl, SF["weld_darken"]), col, (0.45, 0.45, 0.45, 1.0), blend='MULTIPLY'); rough = nb.mixf(wl, rough, 0.9)
    out.update(color=col, rough=rough, metal=metal, bump=n_out)
    return nb, out

def wire_pass(nb, out, which, img):
    """Point the material output at one bake pass and make img the active bake target."""
    for nd in list(nb.n):
        if nd.bl_idname in ("ShaderNodeOutputMaterial", "ShaderNodeEmission", "ShaderNodeBsdfPrincipled", "ShaderNodeCombineColor") or nd.name == "BAKE_TARGET":
            nb.n.remove(nd)
    mo = nb.node("ShaderNodeOutputMaterial")
    if which == "normal":
        bs = nb.node("ShaderNodeBsdfPrincipled")
        if out["bump"] is not None: nb.put(bs.inputs["Normal"], out["bump"])
        nb.put(mo.inputs["Surface"], bs.outputs[0])
    else:
        em = nb.node("ShaderNodeEmission")
        if which == "color":
            nb.put(em.inputs["Color"], out["color"])
        else:
            cc = nb.node("ShaderNodeCombineColor"); cc.inputs[0].default_value = 1.0
            nb.put(cc.inputs[1], out["rough"]); nb.put(cc.inputs[2], out["metal"])
            nb.put(em.inputs["Color"], cc.outputs[0])
        nb.put(mo.inputs["Surface"], em.outputs[0])
    t = nb.node("ShaderNodeTexImage"); t.name = "BAKE_TARGET"; t.image = img
    nb.n.active = t

def final_material(mat, cat, imgs):
    nb = NB(mat)
    mo = nb.node("ShaderNodeOutputMaterial"); bs = nb.node("ShaderNodeBsdfPrincipled")
    nb.put(mo.inputs["Surface"], bs.outputs[0])
    F = S3["finish"]
    if cat in ("vision", "recess"):
        bs.inputs["Base Color"].default_value = lin(F["glass_srgb"]) if cat == "vision" else (0.012, 0.012, 0.012, 1.0)
        bs.inputs["Roughness"].default_value = 0.08 if cat == "vision" else 0.92
        mat.diffuse_color = bs.inputs["Base Color"].default_value
        return
    tc = nb.node("ShaderNodeTexImage"); tc.image = imgs["color"]
    to = nb.node("ShaderNodeTexImage"); to.image = imgs["orm"]
    tn = nb.node("ShaderNodeTexImage"); tn.image = imgs["normal"]
    sep = nb.node("ShaderNodeSeparateColor"); nm = nb.node("ShaderNodeNormalMap")
    nb.put(bs.inputs["Base Color"], tc.outputs["Color"])
    nb.put(sep.inputs[0], to.outputs["Color"]); nb.put(bs.inputs["Roughness"], sep.outputs[1]); nb.put(bs.inputs["Metallic"], sep.outputs[2])
    nb.put(nm.inputs["Color"], tn.outputs["Color"]); nb.put(bs.inputs["Normal"], nm.outputs["Normal"])

# ================================================================== finish: unwrap, bake, rewire
CATS = ("armor", "detail", "running", "track", "vision", "recess")

def tank_context(tag, key, coll):
    O = bpy.data.objects
    def centre(o):
        M = o.matrix_world; co = np.array([tuple(M @ v.co) for v in o.data.vertices]); return tuple((co.min(0) + co.max(0)) / 2)
    acc_keys = ("HatchRim_", "Cupola", "EngineAccessPanel", "ToolRack", "PioneerTools", "StowageBox", "CrewAir_FilterBlower",
                "RadiatorLouvre", "FanCover", "RearDoor_")
    access = [centre(o) for o in coll.all_objects if o.type == 'MESH' and any(k in o.name for k in acc_keys) and not o.name.endswith("_Lid")]
    H = P[key]["hull"]; xr = -P[key]["envelope"]["hull_length"]["value"] / 2
    if key == "kaisersturm_b":
        exhaust = [(xr + 0.02, s * 0.62, H["roof_z"] + 0.09) for s in (1, -1)]
        grease = []
    else:
        zd = H["engine_deck_z"]
        exhaust = [(xr + 0.12, y, zd + 0.05) for y in (-0.55, 0.0, 0.55)]
        grease = [centre(O[f"{tag}_CrewAir_FilterBlower"]), centre(O[f"{tag}_EngineAccessPanel"])] + \
                 [(xr - 0.01, s * 0.91, 1.18) for s in (1, -1)]
    return dict(key=key, access=access, exhaust=exhaust, grease=grease, xr=xr)

def set_finish_attributes(tag, key, coll):
    SF = S3["surface"]; RG = P[key]["running_gear"]
    weld = [f"{tag}_{n}" for n in SF["welded"][key]]; cast = [f"{tag}_{n}" for n in SF["cast"][key]]
    tyre = {"RoadWheel": RG["road_wheel_radius"], "Idler": RG["idler"]["r"], "ReturnRoller": RG["return_roller_r"]}
    hub = {"RoadWheel": 0.16 if tag == "KS_B" else 0.13, "Idler": 0.14 if tag == "KS_B" else 0.12, "ReturnRoller": 0.06, "Sprocket": RG["sprocket"]["r"] * 0.55}
    rep = S3["finish"][key].get("replaced_panel")
    for o in coll.all_objects:
        if o.type != 'MESH': continue
        o["fin_weld"] = 1.0 if o.name in weld else 0.0
        o["fin_cast"] = 1.0 if (o.name in cast or any(o.name == c + "_Lid" for c in cast)) else 0.0
        o["fin_dust_boost"] = 1.0 if "HatchRim_" in o.name else 0.0
        o["fin_replaced"] = 1.0 if (rep and o.name == f"{tag}_{rep}") else 0.0
        o["fin_fender"] = 1.0 if o.name == f"{tag}_Hull" else 0.0
        o["fin_tyre_r"] = next((v for k, v in tyre.items() if f"_{k}_" in o.name), 0.0)
        o["fin_hub_r"] = next((v for k, v in hub.items() if f"_{k}_" in o.name), 0.0)

def stage3_finish(out_dir):
    B3 = S3["bake"]; scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = B3["samples"]
    scene.render.bake.margin = B3["margin_px"]; scene.render.bake.use_clear = True; scene.render.bake.target = 'IMAGE_TEXTURES'
    tex_dir = os.path.join(out_dir, "textures"); os.makedirs(tex_dir, exist_ok=True)
    O = bpy.data.objects; info = {}
    base = {MAT["armor"]: "armor", MAT["detail"]: "detail", MAT["running"]: "running", MAT["vision"]: "vision", MAT["recess"]: "recess"}
    for tag, key in (("KS_B", "kaisersturm_b"), ("M12A2", "bastion_m12a2")):
        coll = bpy.data.collections[tag]
        objs = [o for o in coll.all_objects if o.type == 'MESH' and not o.get("no_export") and not o.get("marking")]
        set_finish_attributes(tag, key, coll)
        mats = {c: bpy.data.materials.new(f"{tag}_{c}") for c in CATS}
        uniq = {}
        for o in objs:
            uniq.setdefault(o.data.name, o)
        for me_name, o in uniq.items():
            me = o.data
            for i, m in enumerate(me.materials):
                c = base.get(m, "detail")
                if c == "running" and me_name.endswith("TrackLink"): c = "track"
                me.materials[i] = mats[c]
        SM = S3["surface"]["smooth_shaded"]
        for me_name, o in uniq.items():
            short = o.name[len(tag) + 1:]
            if any(short == k or short.startswith(k + "_") for k in SM[key]):
                o.data.shade_smooth()
                o.data.set_sharp_from_angle(angle=math.radians(S3["surface"]["smooth_angle_deg"]))
        # one UV layout per tank: every unique mesh unwrapped and packed together
        bpy.ops.object.select_all(action='DESELECT')
        U = list(uniq.values())
        for o in U: o.select_set(True)
        bpy.context.view_layer.objects.active = U[0]
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0015, area_weight=0.0, scale_to_bounds=False)
        bpy.ops.uv.pack_islands(margin=0.0015)
        bpy.ops.object.mode_set(mode='OBJECT')
        ctx = tank_context(tag, key, coll)
        srcs = {c: build_source(mats[c], tag, c, ctx) for c in CATS}
        imgs = {}
        for which, px, cs in (("color", B3["basecolor_px"], 'sRGB'), ("orm", B3["orm_px"], 'Non-Color'), ("normal", B3["normal_px"], 'Non-Color')):
            img = bpy.data.images.new(f"{tag}_{which}", px, px, alpha=False)
            img.colorspace_settings.name = cs
            for c in CATS: wire_pass(*srcs[c], which, img)
            bpy.ops.object.select_all(action='DESELECT')
            for o in U: o.select_set(True)
            bpy.context.view_layer.objects.active = U[0]
            t0 = time.time()
            if which == "normal":
                bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=B3["margin_px"])
            else:
                bpy.ops.object.bake(type='EMIT', margin=B3["margin_px"])
            print(f"baked {tag} {which} {px}px in {time.time() - t0:.0f} s", flush=True)
            ext = "png" if which == "orm" else "jpg"
            path = os.path.join(tex_dir, f"{tag}_{which}.{ext}")
            img.filepath_raw = path; img.file_format = 'PNG' if ext == "png" else 'JPEG'
            try:
                img.save(quality=92)
            except TypeError:
                img.save()
            img.source = 'FILE'; img.filepath = path; img.reload()   # made relative when the .blend is saved
            imgs[which] = img
        for c in CATS:
            final_material(mats[c], c, imgs)
        info[tag] = {"textures": {k: os.path.relpath(bpy.path.abspath(v.filepath), out_dir) for k, v in imgs.items()},
                     "texture_px": {k: v.size[0] for k, v in imgs.items()},
                     "unique_meshes_unwrapped": len(U),
                     "materials": [m.name for m in mats.values()]}
    return info
