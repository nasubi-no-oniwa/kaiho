# 解放戦力：Blender で「防衛隊スーツの人型」と「怪獣の体」を作る
# もとの人型は three.js の見本に入っている X Bot（Mixamo のキャラクター）。ポーズを焼きこみ、装備・トゲ・尾などを足して GLB に書きだす
import bpy, bmesh, json, math, random, sys
from mathutils import Vector, Matrix, Quaternion
SRC = '/home/claude/work/three-sparse/examples/models/gltf/Xbot.glb'
OUT = sys.argv[-1] if sys.argv[-1].endswith('/') else '/home/claude/work/bl/out/'
B = 'mixamorig:'
random.seed(8)

def load(action, frame, pose=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    for o in list(bpy.data.objects):
        if o.name.startswith('Icosphere'): bpy.data.objects.remove(o)
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    act = bpy.data.actions[action]
    if not arm.animation_data: arm.animation_data_create()
    arm.animation_data.action = act
    try:
        if getattr(arm.animation_data, 'action_slot', None) is None and len(act.slots): arm.animation_data.action_slot = act.slots[0]
    except Exception as e: print('slot', e)
    bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
    if pose:   # もとのポーズに、骨ごとの曲げを足す（怪獣の前かがみ・ひざ曲げ・腕の構え）
        basis = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
        arm.animation_data.action = None
        for pb in arm.pose.bones: pb.matrix_basis = basis[pb.name]
        for name, rots in pose.items():
            pb = arm.pose.bones[B + name]
            for ax, deg in rots: pb.matrix_basis = pb.matrix_basis @ Quaternion(ax, math.radians(deg)).to_matrix().to_4x4()
        bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = {}
    for o in bpy.data.objects:
        if o.type != 'MESH': continue
        ev = o.evaluated_get(dg); me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg); me.transform(o.matrix_world); meshes[o.name] = me
    arme = arm.evaluated_get(dg); bones = {}
    for pb in arme.pose.bones: bones[pb.name[len(B):]] = (arm.matrix_world @ pb.head, arm.matrix_world @ (pb.children[0].head if pb.children else pb.tail))  # 先の位置は、つぎの骨の根元を使う
    return meshes, bones

def setcol(me, rgb):
    ca = me.color_attributes.get('Color') or me.color_attributes.new(name='Color', type='BYTE_COLOR', domain='CORNER')
    for d in ca.data: d.color = (rgb[0], rgb[1], rgb[2], 1.0)
    return ca

def prim(kind, M, col=(0, 1, 0), **kw):
    bm = bmesh.new()
    if kind == 'cone': bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=kw.get('seg', 10), radius1=kw['r'], radius2=kw.get('r2', 0.0), depth=kw['d'])
    elif kind == 'sphere': bmesh.ops.create_uvsphere(bm, u_segments=kw.get('seg', 16), v_segments=kw.get('seg2', 10), radius=kw['r'])
    elif kind == 'cube':
        bmesh.ops.create_cube(bm, size=1.0)
        if kw.get('bevel'): bmesh.ops.bevel(bm, geom=list(bm.edges), offset=kw['bevel'], segments=2, affect='EDGES', profile=.5)
    elif kind == 'torus':
        R, r, n, m = kw['R'], kw['r'], 28, 8
        vs = [[bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))) for b in [j / m * 6.2831853 for j in range(m)]] for a in [i / n * 6.2831853 for i in range(n)]]
        for i in range(n):
            for j in range(m): bm.faces.new((vs[i][j], vs[(i + 1) % n][j], vs[(i + 1) % n][(j + 1) % m], vs[i][(j + 1) % m]))
    me = bpy.data.meshes.new(kind); bm.to_mesh(me); bm.free(); me.transform(M); setcol(me, col); return me

def along(p, d, depth):  # +Z を d の向きにして、根元を p に置く
    d = Vector(d).normalized(); return Matrix.Translation(Vector(p) + d * depth / 2) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
def place(p, s=(1, 1, 1), rot=None):
    M = Matrix.Translation(Vector(p));
    if rot is not None: M = M @ rot.to_matrix().to_4x4()
    return M @ Matrix.Diagonal((s[0], s[1], s[2], 1))

def merge(list_me, name):
    bm = bmesh.new()
    for me in list_me: bm.from_mesh(me)
    out = bpy.data.meshes.new(name); bm.to_mesh(out); bm.free(); return out

def with_mods(me, mods, name):
    ob = bpy.data.objects.new(name + '_tmp', me); bpy.context.scene.collection.objects.link(ob)
    for kind, props in mods:
        m = ob.modifiers.new(kind, kind)
        for k, v in props.items(): setattr(m, k, v)
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    bpy.data.objects.remove(ob); return out

def finish(me, name, scale, cx, cy, tris):
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    if n > tris: me = with_mods(me, [('DECIMATE', {'ratio': tris / n})], name)
    zmin = min(v.co.z for v in me.vertices)
    me.transform(Matrix.Diagonal((scale, scale, scale, 1)) @ Matrix.Translation((-cx, -cy, -zmin)))
    for p in me.polygons: p.use_smooth = True
    ca = me.color_attributes.get('Color') or setcol(me, (0, 0, 0))
    try: me.color_attributes.active_color = ca; me.color_attributes.render_color_index = list(me.color_attributes).index(ca)
    except Exception as e: print('ca', e)
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for o in bpy.data.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    kw = dict(filepath=OUT + name + '.glb', export_format='GLB', use_selection=True, export_animations=False, export_materials='NONE', export_normals=True, export_texcoords=False, export_yup=True)
    for extra in ({'export_vertex_color': 'ACTIVE', 'export_active_vertex_color_when_no_material': True}, {'export_vertex_color': 'ACTIVE'}, {'export_colors': True}, {}):
        try: bpy.ops.export_scene.gltf(**kw, **extra); print('export ok', name, extra); break
        except TypeError as e: print('retry export', e)
    print(name, 'verts', len(me.vertices), 'tris', sum(len(p.vertices) - 2 for p in me.polygons), 'zmin', zmin)
    return zmin

def conv(p, scale, cx, cy, zmin):  # Blender の座標 → ゲームの座標（Y が上、手前が +Z）
    return [round((p[0] - cx) * scale, 4), round((p[2] - zmin) * scale, 4), round(-(p[1] - cy) * scale, 4)]

info = {}
# 怪獣の姿勢（骨ごとに [軸, 角度]）
KPOSE = {'Spine': [((1, 0, 0), 13)], 'Spine1': [((1, 0, 0), 13)], 'Spine2': [((1, 0, 0), 13)], 'Neck': [((1, 0, 0), -20)], 'Head': [((1, 0, 0), -24)],
         'LeftUpLeg': [((1, 0, 0), -26)], 'RightUpLeg': [((1, 0, 0), -26)], 'LeftLeg': [((1, 0, 0), 46)], 'RightLeg': [((1, 0, 0), 46)], 'LeftFoot': [((1, 0, 0), -20)], 'RightFoot': [((1, 0, 0), -20)],
         'LeftArm': [((0, 0, 1), 16)], 'RightArm': [((0, 0, 1), -16)], 'LeftForeArm': [((0, 0, 1), 40)], 'RightForeArm': [((0, 0, 1), -40)]}   # 前かがみ・ひざ曲げ・腕を広げて構える
def silhouette(me, path):   # 形の確認用：正面と横から見た点の絵
    from PIL import Image
    im = Image.new('RGB', (800, 500), '#111'); px = im.load()
    for v in me.vertices:
        x, y, z = v.co
        for ox, u in ((200, x), (600, y)):
            a, b = int(ox + u * 200), int(480 - z * 200)
            if 0 <= a < 800 and 0 <= b < 500: px[a, b] = (255, 120, 80)
    im.save(path)

# ---------- 防衛隊スーツ ----------
meshes, bn = load('idle', 12)
surf, joints = meshes['Beta_Surface'], meshes['Beta_Joints']
setcol(surf, (0, 0, 0)); setcol(joints, (1, 0, 0))          # 関節のパーツ＝光る筋
eye = (bn['LeftEye'][0] + bn['RightEye'][0]) / 2; headz = bn['Head'][0].z
ca = surf.color_attributes['Color']                        # 顔の前の帯＝バイザー
for poly in surf.polygons:
    for li in poly.loop_indices:
        v = surf.vertices[surf.loops[li].vertex_index].co
        if v.z > headz and abs(v.z - eye.z - .012) < .03 and v.y < eye.y + .075: ca.data[li].color = (0, 0, 1, 1)
parts = [surf, joints]
H = bn['Hips'][0]; S2 = bn['Spine2'][0]; NK = bn['Neck'][0]
fwd = Vector((0, -1, 0)); upv = Vector((0, 0, 1))
# 背中の装置（動力部）と左右の筒
parts.append(prim('cube', place(S2 + Vector((0, .135, .03)), (.26, .11, .34)), bevel=.18))
parts.append(prim('cube', place(S2 + Vector((0, .19, .05)), (.12, .05, .22)), col=(1, 0, 0), bevel=.2))
for s in (-1, 1):
    parts.append(prim('cone', along(S2 + Vector((s * .085, .16, -.2)), (0, .05, 1), .36), r=.035, r2=.035, d=.36, seg=12))
    parts.append(prim('sphere', place(S2 + Vector((s * .085, .178, .17)), (.036, .036, .036)), col=(1, 0, 0), r=1.0, seg=12, seg2=8))
# 肩・前腕・すね・ひざ・腰まわり
for side in ('Left', 'Right'):
    s = 1 if side == 'Left' else -1
    a0, a1 = bn[side + 'Arm']; f0, f1 = bn[side + 'ForeArm']; l0, l1 = bn[side + 'Leg']; u0 = bn[side + 'UpLeg'][0]
    out = Vector((s, 0, 0))
    parts.append(prim('sphere', place(a0 + out * .035 + upv * .03, (.105, .1, .075), (out + upv * 1.2).to_track_quat('Z', 'Y')), r=1.0, seg=18, seg2=10))
    parts.append(prim('torus', place(a0 + (a1 - a0) * .28, (1, 1, 1.6), (a1 - a0).to_track_quat('Z', 'Y')), col=(1, 0, 0), R=.058, r=.012))
    d = f1 - f0; parts.append(prim('cone', along(f0 + d * .22, d, d.length * .62), r=.052, r2=.043, d=d.length * .62, seg=14))
    parts.append(prim('torus', place(f0 + d * .86, (1, 1, 1.5), d.to_track_quat('Z', 'Y')), col=(1, 0, 0), R=.04, r=.009))
    d = l1 - l0; parts.append(prim('cone', along(l0 + d * .16 + fwd * .012, d, d.length * .66), r=.068, r2=.052, d=d.length * .66, seg=14))
    parts.append(prim('sphere', place(l0 + fwd * .045, (.06, .04, .075)), r=1.0, seg=14, seg2=8))
    parts.append(prim('cube', place(u0 + out * .075 + Vector((0, 0, -.1)), (.035, .13, .2)), bevel=.25))
parts.append(prim('torus', place(H + Vector((0, 0, .055)), (1, .78, 1.9)), R=.165, r=.02))
parts.append(prim('cube', place(H + Vector((0, -.125, .05)), (.11, .04, .07)), col=(1, 0, 0), bevel=.25))
# 胸の芯（光るところ）と首まわり
parts.append(prim('sphere', place(S2 + Vector((0, -.118, .05)), (.045, .02, .045)), col=(1, 0, 0), r=1.0, seg=16, seg2=8))
parts.append(prim('torus', place(NK + Vector((0, .005, .0)), (1, 1.05, 2.2)), R=.068, r=.013))
suit = merge(parts, 'suit')
zs = [v.co.z for v in suit.vertices]; hgt = max(zs) - min(zs); SC = 2.78 / hgt; cx, cy = H.x, H.y
zmin = finish(suit, 'suit', SC, cx, cy, 15000)
info['suit'] = {'head': conv((bn['Head'][0] + bn['HeadTop_End'][0]) / 2, SC, cx, cy, zmin), 'eye': conv(eye, SC, cx, cy, zmin), 'chest': conv(S2 + Vector((0, -.12, .05)), SC, cx, cy, zmin), 'top': conv(bn['HeadTop_End'][0], SC, cx, cy, zmin)}

# ---------- 怪獣 ----------
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
POSE = json.load(open('/home/claude/work/bl/pose.json')) if len(sys.argv) > 2 and sys.argv[-2] == 'posefile' else None
POSE = {k: [(tuple(a), d) for a, d in v] for k, v in POSE.items()} if POSE else KPOSE
meshes, bn = load('sneak_pose', 1, POSE)
body = merge([meshes['Beta_Surface'], meshes['Beta_Joints']], 'kbody')
parts = [body]
def spike(p, d, depth, r, seg=9): parts.append(prim('cone', along(Vector(p) - Vector(d).normalized() * depth * .12, d, depth), r=r, d=depth, seg=seg))
def blob(p, s): parts.append(prim('sphere', place(p, s), r=1.0, seg=14, seg2=10))
H = bn['Hips'][0]; S0 = bn['Spine'][0]; S1 = bn['Spine1'][0]; S2 = bn['Spine2'][0]; NK = bn['Neck'][0]; HD = bn['Head'][0]; HT = bn['HeadTop_End'][0]
spine = [H, S0, S1, S2, NK, HD, HT]
fw = (HT - HD).cross(Vector((1, 0, 0))).normalized()   # 頭の前向き（だいたい）
if fw.y > 0: fw = -fw
# 背びれ（背骨にそって大きなトゲ）
pts = []
for i in range(len(spine) - 2):
    for t in (0.0, .5): pts.append(spine[i].lerp(spine[i + 1], t))
pts.append(spine[-2])
for i, p in enumerate(pts):
    k = math.sin((i + 1) / (len(pts) + 1) * math.pi); tang = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized(); back = tang.cross(Vector((1, 0, 0))).normalized()
    if back.y < 0: back = -back
    spike(p + back * .07, back + tang * .25, .16 + .22 * k, .035 + .03 * k)
    for s in (-1, 1): spike(p + back * .06 + Vector((s * .07, 0, 0)), back + Vector((s * .7, 0, 0)) + tang * .2, .09 + .1 * k, .024 + .014 * k)
# 肩・ひじ・ひざのトゲ、厚い胸と肩
for side in ('Left', 'Right'):
    s = 1 if side == 'Left' else -1; out = Vector((s, 0, 0))
    a0, a1 = bn[side + 'Arm']; f0, f1 = bn[side + 'ForeArm']; l0, l1 = bn[side + 'Leg']; u0, u1 = bn[side + 'UpLeg']; hd = bn[side + 'Hand'][0]
    blob(a0 + out * .03, (.13, .12, .12)); blob(a0.lerp(a1, .5), (.085, .085, .085)); blob(f0.lerp(f1, .45), (.075, .075, .075)); blob(u0.lerp(u1, .45), (.115, .115, .115)); blob(l0.lerp(l1, .4), (.085, .085, .085))
    spike(a0 + out * .09 + Vector((0, 0, .06)), out + Vector((0, .2, .9)), .22, .045); spike(a0 + out * .12, out * 1.0 + Vector((0, .3, .35)), .16, .035); spike(a0 + Vector((0, .08, .08)), Vector((s * .3, .7, .8)), .15, .03)
    spike(f0, (f0 - a0).normalized() + Vector((0, .6, 0)), .2, .034)                      # ひじ
    for t in (.3, .55, .8): spike(f0.lerp(f1, t), (f1 - f0).cross(out).normalized() * (1 if (f1 - f0).cross(out).y > 0 else -1) + out * .3, .09, .02)
    spike(l0, Vector((0, -1, .25)), .13, .032)                                           # ひざ
    # 爪
    for fng in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'):
        b3 = bn[side + 'Hand' + fng + '3'][0]; b4 = bn[side + 'Hand' + fng + '4'][0]; d = (b4 - b3).normalized()
        spike(b3, d + Vector((0, 0, -.25)), .15, .017, 7)
    blob(hd + (bn[side + 'HandMiddle1'][0] - hd) * .6, (.06, .05, .06))
    t0 = bn[side + 'ToeBase'][0]; ft = bn[side + 'Foot'][0]; d = (t0 - ft); d.z = 0; d.normalize()
    for k in (-1, 0, 1): spike(t0 + Vector((k * .035, 0, .0)), d + Vector((k * .25, 0, -.12)), .13, .022, 7)
    blob(ft.lerp(t0, .5) + Vector((0, 0, -.01)), (.075, .11, .06))
blob(S2 + Vector((0, -.02, .02)), (.21, .17, .19)); blob(S1, (.17, .15, .15)); blob(H, (.17, .15, .14)); blob(NK.lerp(HD, .5), (.085, .09, .1))
# 頭：角・あご・眉の出っぱり
side_v = Vector((1, 0, 0)); hu = (HT - HD).normalized(); hc = HD.lerp(HT, .5)
for s in (-1, 1):
    spike(hc + hu * .06 + side_v * s * .07 - fw * .01, hu * .9 + side_v * s * .55 - fw * .25, .26, .04)       # 角
    spike(hc + hu * .02 + side_v * s * .1 - fw * .03, side_v * s + hu * .3 - fw * .5, .12, .026)
    spike(hc - hu * .07 + side_v * s * .045 + fw * .085, fw + side_v * s * .15 - hu * .7, .075, .014, 7)        # 牙
blob(hc - hu * .06 + fw * .06, (.07, .075, .05))                                            # あご
blob(hc + hu * .035 + fw * .075, (.085, .04, .028))                                         # 眉
# 尾
tp = []; p = H + Vector((0, .1, -.02)); d = Vector((0, 1, -.35)).normalized()
for i in range(15):
    tp.append((p.copy(), .13 * (1 - i / 15) ** 1.1 + .012)); p = p + d * .095; d = (d + Vector((math.sin(i * .5) * .05, 0, .075 if p.z < .2 else -.02))).normalized()
for i, (p, r) in enumerate(tp):
    blob(p, (r, r, r))
    if i % 2 == 0 and i < 12: spike(p + Vector((0, 0, r * .7)), Vector((0, .35, 1)), r * 1.7, r * .38, 7)
spike(tp[-1][0], d, .2, .03)
raw = merge(parts, 'kaiju_raw'); silhouette(raw, OUT + 'kaiju_sil.png')
tex = bpy.data.textures.new('bump', 'CLOUDS'); tex.noise_scale = .07; tex.noise_depth = 2
tex2 = bpy.data.textures.new('bump2', 'VORONOI'); tex2.noise_scale = .12
kai = with_mods(raw, [('REMESH', {'mode': 'VOXEL', 'voxel_size': .0115, 'use_smooth_shade': True}), ('SMOOTH', {'factor': .5, 'iterations': 6}), ('DISPLACE', {'strength': .03, 'mid_level': .35, 'texture': tex2}), ('DISPLACE', {'strength': .014, 'mid_level': .5, 'texture': tex}), ('SMOOTH', {'factor': .35, 'iterations': 2})], 'kaiju')
SCK = SC * 1.12; cx, cy = H.x, H.y
eye = (bn['LeftEye'][0] + bn['RightEye'][0]) / 2
zmin = finish(kai, 'kaiju', SCK, cx, cy, 20000)
info['kaiju'] = {'head': conv(hc, SCK, cx, cy, zmin), 'eyeL': conv(bn['LeftEye'][0] + fw * .02, SCK, cx, cy, zmin), 'eyeR': conv(bn['RightEye'][0] + fw * .02, SCK, cx, cy, zmin), 'chest': conv(S2 + fw * .16, SCK, cx, cy, zmin), 'top': conv(HT, SCK, cx, cy, zmin)}
json.dump(info, open(OUT + 'info.json', 'w'), indent=1); print(json.dumps(info))
