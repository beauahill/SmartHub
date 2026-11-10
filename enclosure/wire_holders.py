"""
Stick-on wire management for the inside of the bezel tray (manifold3d). These are separate parts, so
they fit a bezel that is already printed: VHB tape holds them to the inside of the tray's back wall.

Parts (all print flat face down, no supports):
  lever_nut_rack_<n>  rack of n pockets for 2-way lever connectors. Each nut presses down into its
                      pocket. A closed wall at the back end and a low lip at the wire end stop it
                      sliding, and small ribs on the walls hold it by friction. A zip tie through the
                      tunnel in the base can go over the whole row for extra hold.
  tie_anchor          16 x 16 mm zip-tie mount with crossing tunnels, for ties up to 4.6 mm wide

Measure your lever nuts and pass the sizes, or edit the defaults. The defaults are a WAGO 221-412
(13.1 wide across both poles, 18.3 long, 8.1 tall); clones vary by up to a millimeter.

Usage:  python wire_holders.py [out_dir] [--w 13.1] [--l 18.3] [--h 8.1] [--counts 2,3]
"""
import argparse, os
import numpy as np
import manifold3d as m3
import trimesh

M = m3.Manifold

ap = argparse.ArgumentParser()
ap.add_argument("out", nargs="?", default="out")
ap.add_argument("--w", type=float, default=13.1, help="nut width across its poles")
ap.add_argument("--l", type=float, default=18.3, help="nut length, wire end to back end")
ap.add_argument("--h", type=float, default=8.1, help="nut height, base to closed levers")
ap.add_argument("--counts", default="2,3", help="rack sizes to export, comma separated")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)

# ---------------- PARAMETERS ----------------
NUT_W, NUT_L, NUT_H = args.w, args.l, args.h
CLR = 0.25                     # pocket clearance per side
DIV = 1.6                      # wall between pockets and at the outside
BASE_T = 3.0                   # base thickness, room for the zip-tie tunnel
WALL_H = 0.6 * NUT_H           # side walls stand this far above the base; the levers stay free above them
END_T = 1.6                    # closed wall at the back end of the nut
LIP_T, LIP_H = 1.2, 1.5        # low lip at the wire end; below the wire entry holes
RIB_D, RIB_PROUD = 1.2, 0.35   # friction ribs: 0.1 mm interference with CLR = 0.25
TIE_W, TIE_H = 5.0, 1.5        # zip-tie tunnel through the base, across the row
TIE_Z = 0.7                    # tunnel floor above the bed
CH = 0.6                       # lead-in chamfer on the tops of the pocket walls
# ---------------------------------------------


def box(x0, x1, y0, y1, z0, z1):
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def lever_nut_rack(n):
    pw, pl = NUT_W + 2 * CLR, NUT_L + 2 * CLR
    pitch = pw + DIV
    W = n * pitch + DIV
    L = END_T + pl + LIP_T
    top = BASE_T + WALL_H
    body = box(0, W, 0, L, 0, top)
    for i in range(n):
        x0 = DIV + i * pitch
        # pocket, with a 45 deg lead-in at the top of the side walls
        body = body - box(x0, x0 + pw, END_T, END_T + pl, BASE_T, top + 1)
        body = body - M.hull_points([[x0, END_T, top - CH], [x0 + pw, END_T, top - CH],
                                     [x0, END_T + pl, top - CH], [x0 + pw, END_T + pl, top - CH],
                                     [x0 - CH, END_T, top + 0.01], [x0 + pw + CH, END_T, top + 0.01],
                                     [x0 - CH, END_T + pl, top + 0.01], [x0 + pw + CH, END_T + pl, top + 0.01]])
        # ribs on both side walls, halfway along, from the base up to the chamfer
        for xs, sgn in ((x0, +1), (x0 + pw, -1)):
            rib = M.cylinder(top - CH - BASE_T, RIB_D / 2, RIB_D / 2, 24) \
                   .translate([xs + sgn * (RIB_PROUD - RIB_D / 2), END_T + pl / 2, BASE_T])
            body = body + (rib ^ box(x0, x0 + pw, END_T, END_T + pl, BASE_T, top))
    # the wire end is open above the lip
    body = body - box(-1, W + 1, L - LIP_T - 0.01, L + 1, BASE_T + LIP_H, top + 1)
    # keep the walls between pockets, cut the lip down only inside the pockets (done above); round nothing
    # zip-tie tunnel across the row, under the nuts
    body = body - box(-1, W + 1, END_T + pl / 2 - TIE_W / 2, END_T + pl / 2 + TIE_W / 2, TIE_Z, TIE_Z + TIE_H)
    return body, (W, L, top)


def tie_anchor():
    S, B, R = 16.0, 1.6, 0.8                      # base size, base thickness, edge chamfer
    base = M.hull_points([[R, R, 0], [S - R, R, 0], [R, S - R, 0], [S - R, S - R, 0],
                          [0, 0, B - R], [S, 0, B - R], [0, S, B - R], [S, S, B - R],
                          [0, 0, B], [S, 0, B], [0, S, B], [S, S, B]])
    tw, th, roof = 4.6, 1.8, 1.2
    blk = 9.0
    c0, c1 = (S - blk) / 2, (S + blk) / 2
    block = box(c0, c1, c0, c1, 0, B + th + roof)
    block = block - box(-1, S + 1, S / 2 - tw / 2, S / 2 + tw / 2, B, B + th)
    block = block - box(S / 2 - tw / 2, S / 2 + tw / 2, -1, S + 1, B, B + th)
    return base + block


def export(man, name):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts),
                         process=False)
    tm.export(os.path.join(args.out, name + ".stl"))
    bb = tm.bounds
    print(f"{name:18s} vol {tm.volume / 1000:6.2f} cm3  bbox {np.round(bb[1] - bb[0], 1)}  "
          f"watertight={tm.is_watertight}")


for n in sorted({int(c) for c in args.counts.split(",") if c.strip()}):
    rack, (W, L, H) = lever_nut_rack(n)
    export(rack, f"lever_nut_rack_{n}")
export(tie_anchor(), "tie_anchor")
