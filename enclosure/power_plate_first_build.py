"""
USB-C power plate for the first-build spine (55 mm deep at the lid), with an Adafruit HUSB238 breakout
(product 5807). Separate from enclosure.py because that script now builds the deeper spine for the HUNSOOL
trigger; this one only has to fit a lid and spine that are already printed.

The plate sits in the spine's existing 44 x 26 mm pocket on the same two M3 inserts. Instead of a flat
plate with the board on a long sled inside the spine, a tapered snout stands 9 mm out of the rear face
and holds the front of the board. The socket's mouth sits just behind the snout's face, in a hole that
hugs the receptacle shell, so the plug's overmold seats against the face and never has to enter an
opening. Moving the board out also pulls it back off the speaker-wire bore in the cavity floor: the
original wire hole is clear again and can be glued shut around the wires.

Board, from Adafruit's CAD model (Adafruit_CAD_Parts/5807 HUSB238 Breakout): PCB 20.32 x 23.5 x 1.57,
receptacle shell 8.94 x 3.21 sitting on top of the PCB with its mouth 1.11 past the edge, two 2.5 mm
mounting holes 15.24 apart and 2.55 behind the USB edge, screw terminal 7.0 x 7.3 at the far end standing
8.61 above the PCB with its pins 1.92 below it.

World axes and spine numbers are the same as enclosure.py at 565ad77 (the first build).
Usage:  python power_plate_first_build.py [out_dir]
"""
import math, os, sys
import numpy as np
import manifold3d as m3
import trimesh

M, CS = m3.Manifold, m3.CrossSection
SEG = 96
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)

# ---------------- first-build spine (already printed; do not change) ----------------
TOPZ, LID_Z0 = 120.0, 116.0                  # lid top and bottom
REAR_FACE = 98.08                            # spine rear face (Y)
SPINE_X = 30.0                               # spine half width
SPINE_FRONT = 42.68                          # spine front edge at the lid (Y): 55.4 mm deep
REAR_FACE_TOP = TOPZ + 32.0                  # top of the flat rear face
PWR_ZW = TOPZ + 16.0                         # pocket centre height
POCKET = (44.4, 26.4, 3.2, 3.0)              # w, h, corner r, depth
INSERT_X, M3_INSERT, INSERT_DEPTH = 17.0, 4.0, 6.0
CAV_X = 12.36                                # trigger cavity half width
CAV_Y0 = 59.13                               # cavity front (Y); it runs back to the pocket floor
CAV_Z = (129.0, 147.8)
WIRE_HOLE, WIRE_HOLE_D = (0.0, 74.0), 8.0    # original speaker-wire hole through the lid
WIRE_BORE_D, WIRE_BORE_TOP = 12.0, 132.0     # its throat up into the cavity
REWORK_HOLE = (0.0, 62.0)                    # the hole the old README said to drill instead
P_LOW, P_HIGH = (0.0, 74.0, 125.0), (0.0, 58.41, 183.51)   # cable channel: hull of two 6 mm spheres
CLIP_Y = 132.0                               # cable clip on the lid behind the spine (first build: centre line)

# ---------------- board: Adafruit 5807 ----------------
PCB_W, PCB_L, PCB_T = 20.32, 23.5, 1.57
USB_W, USB_H, USB_OVERHANG = 8.94, 3.21, 1.11
HOLE_X, HOLE_BACK = 7.62, 2.55               # mounting holes: +-x from centre, distance behind the USB edge
TERM = (-3.56, 3.44, 0.73, 8.03)             # terminal x0, x1 (from centre), y0, y1 (from the far edge)
TERM_TALL, PIN_TAIL = 8.61, 1.92

# ---------------- plate ----------------
OUT_D = 9.0                                  # snout face beyond the spine's rear face
FACE_T = 1.3                                 # snout face; the PCB's USB edge stops against its inside
FACE_HOLE_CLR = 0.3                          # around the receptacle shell, per side
FACE_HOLE_CHAMFER = 0.4
FACE_W, FACE_Z = 26.0, (-8.0, 5.0)           # snout face outline (z from the socket centre)
FACE_R = 4.0
EDGE_CHAMFER = 0.4                           # round the face's bed edge (elephant's foot)
PLATE_W, PLATE_H, PLATE_T, PLATE_R = 44.0, 26.0, 3.0, 3.0
BOARD_CLR = 0.3                              # board to snout side walls, per side
TOP_CLR = 0.6                                # receptacle shell to the snout's ceiling
M3_CLR, PIT_D = 3.4, 7.0                     # plate screws, and the wells through the snout down to their heads
PILOT = 2.1                                  # M2.5 thread-forming screws into the floor
ACCESS_D = 5.5                               # screwdriver and head access through the snout's top
TONGUE_CLR = 0.6                             # tongue to the cavity floor
TONGUE_BEYOND = 0.8                          # tongue past the board's far edge
PIN_RELIEF = 0.8                             # around the terminal's pins
# ------------------------------------------------------

FACE_Y = REAR_FACE + OUT_D
MOUTH_Y = FACE_Y - (FACE_T - USB_OVERHANG)   # socket mouth, just behind the face
EDGE_Y = MOUTH_Y - USB_OVERHANG              # PCB's USB edge (against the inside of the face)
FAR_Y = EDGE_Y - PCB_L                       # PCB's far edge, inside the spine
SOCK_Z = PWR_ZW                              # socket centre on the pocket centre
PCB_TOP = SOCK_Z - USB_H / 2
PCB_BOT = PCB_TOP - PCB_T
CEIL = SOCK_Z + USB_H / 2 + TOP_CLR
POCKET_FLOOR = REAR_FACE - POCKET[3]

def rrect(x0, x1, y0, y1, r, n=24):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return CS([pts])

def xz_slab(cs, y0, y1):
    """an X-Z profile (drawn as X-Y, Y = world Z) extruded along world +Y from y0 to y1"""
    return cs.extrude(y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])

def box(x0, x1, y0, y1, z0, z1):
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])

def cyl_y(x, z, y0, y1, d):
    return M.cylinder(y1 - y0, d / 2, d / 2, SEG).rotate([-90, 0, 0]).translate([x, y0, z])

def cyl_z(x, y, z0, z1, d):
    return M.cylinder(z1 - z0, d / 2, d / 2, SEG).translate([x, y, z0])

def outline(w, z0, z1, r):
    return rrect(-w / 2, w / 2, PWR_ZW + z0, PWR_ZW + z1, r)

# xz_slab check: the profile's Y must come out as world Z
_t = xz_slab(rrect(-1, 1, 10, 12, 0.5), 0, 5).bounding_box()
assert abs(_t[2] - 10) < 1e-6 and abs(_t[5] - 12) < 1e-6 and abs(_t[1]) < 1e-6 and abs(_t[4] - 5) < 1e-6, _t

# ---- snout: a hull from the face outline out at FACE_Y back to the full plate outline at the rear face.
# Printed face down, its sides overhang at about 45 deg, so it needs no supports.
c = EDGE_CHAMFER
snout = M.batch_hull([
    xz_slab(outline(FACE_W - 2 * c, FACE_Z[0] + c, FACE_Z[1] - c, FACE_R - c), FACE_Y - 0.01, FACE_Y),
    xz_slab(outline(FACE_W, FACE_Z[0], FACE_Z[1], FACE_R), FACE_Y - c - 0.01, FACE_Y - c),
    xz_slab(outline(PLATE_W, -PLATE_H / 2, PLATE_H / 2, PLATE_R), REAR_FACE - 0.01, REAR_FACE)])
flange = xz_slab(outline(PLATE_W, -PLATE_H / 2, PLATE_H / 2, PLATE_R), POCKET_FLOOR, REAR_FACE)
# floor under the board continues into the spine as a tongue that carries the board's far end
tongue_y0 = FAR_Y - TONGUE_BEYOND
tongue = box(-PCB_W / 2 - BOARD_CLR, PCB_W / 2 + BOARD_CLR, tongue_y0, POCKET_FLOOR + 0.01,
             CAV_Z[0] + TONGUE_CLR, PCB_BOT)
plate = snout + flange + tongue

# board bay: open from the tongue to the inside of the face
bay = box(-PCB_W / 2 - BOARD_CLR, PCB_W / 2 + BOARD_CLR, tongue_y0 - 1, FACE_Y - FACE_T, PCB_BOT, CEIL)
# the receptacle's hole through the face, a stadium, with a small chamfer on the outside
hw, hh = USB_W / 2 + FACE_HOLE_CLR, USB_H / 2 + FACE_HOLE_CLR
hole = M.batch_hull([xz_slab(rrect(-hw, hw, SOCK_Z - hh, SOCK_Z + hh, hh * 0.999), FACE_Y - FACE_T - 0.5, FACE_Y + 0.01),
                     xz_slab(rrect(-hw - FACE_HOLE_CHAMFER, hw + FACE_HOLE_CHAMFER, SOCK_Z - hh - FACE_HOLE_CHAMFER,
                                   SOCK_Z + hh + FACE_HOLE_CHAMFER, (hh + FACE_HOLE_CHAMFER) * 0.999), FACE_Y, FACE_Y + 0.01)])
# relief in the tongue under the terminal's pins, open out of the tongue's end so it prints without a bridge
pins = box(TERM[0] - PIN_RELIEF, TERM[1] + PIN_RELIEF, tongue_y0 - 1, FAR_Y + TERM[3] + PIN_RELIEF,
           PCB_BOT - PIN_TAIL - 0.5, PCB_BOT + 0.01)
plate = plate - bay - hole - pins
# board screws: pilots down into the floor, access holes down through the snout's top
hole_y = EDGE_Y - HOLE_BACK
for sx in (-HOLE_X, HOLE_X):
    plate = plate - cyl_z(sx, hole_y, PWR_ZW + FACE_Z[0] + 0.8, PCB_BOT + 0.01, PILOT) \
                  - cyl_z(sx, hole_y, CEIL - 0.01, PWR_ZW + PLATE_H, ACCESS_D)
# plate screws: clearance, 90 deg countersink in the flange's outer face, and a well through the snout
for sx in (-INSERT_X, INSERT_X):
    plate = plate - cyl_y(sx, PWR_ZW, POCKET_FLOOR - 1, REAR_FACE + 1, M3_CLR) \
                  - M.cylinder(1.7, M3_CLR / 2, 3.4, SEG).rotate([-90, 0, 0]).translate([sx, REAR_FACE - 1.7 + 0.01, PWR_ZW]) \
                  - cyl_y(sx, PWR_ZW, REAR_FACE, FACE_Y + 1, PIT_D)

# ---- the first-build spine around the power port, for the fit checks. A plain block of spine material from
# the lid up to the top of the rear face, with the pocket, cavity, inserts, wire hole and channel cut out.
# It is more solid than the real spine (no sloped front), so the checks err on the safe side.
pw, ph, pr, pd = POCKET
spine = box(-SPINE_X, SPINE_X, SPINE_FRONT, REAR_FACE, TOPZ - 0.5, REAR_FACE_TOP)
lid = box(-150, 150, 0, 150, LID_Z0, TOPZ)
chan = M.batch_hull([M.sphere(6, 48).translate(list(P_LOW)), M.sphere(6, 48).translate(list(P_HIGH))])
spine = (spine + lid) - xz_slab(outline(pw, -ph / 2, ph / 2, pr), POCKET_FLOOR, REAR_FACE + 1) \
        - box(-CAV_X, CAV_X, CAV_Y0, POCKET_FLOOR + 0.01, CAV_Z[0], CAV_Z[1]) - chan \
        - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], LID_Z0 - 1, P_LOW[2], WIRE_HOLE_D) \
        - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], TOPZ, WIRE_BORE_TOP, WIRE_BORE_D)
for sx in (-INSERT_X, INSERT_X):
    spine = spine - cyl_y(sx, PWR_ZW, POCKET_FLOOR - INSERT_DEPTH, POCKET_FLOOR + 0.01, M3_INSERT)

# the board, with its receptacle (a stadium, as the real shell), terminal and pin tails
board = box(-PCB_W / 2, PCB_W / 2, FAR_Y, EDGE_Y, PCB_BOT, PCB_TOP) \
      + xz_slab(rrect(-USB_W / 2, USB_W / 2, SOCK_Z - USB_H / 2, SOCK_Z + USB_H / 2, USB_H / 2 * 0.999), MOUTH_Y - 7.9, MOUTH_Y) \
      + box(TERM[0], TERM[1], FAR_Y + TERM[2], FAR_Y + TERM[3], PCB_BOT - PIN_TAIL, PCB_TOP + TERM_TALL)

def hit(a, b):
    return (a ^ b).volume()

checks = {}
checks["plate in spine"] = hit(plate, spine)
# the PCB rests on the floor and its USB edge against the face by design: check it 0.02 mm off those seats
check_board = board.translate([0, -0.02, 0.02])
checks["board in plate"] = hit(check_board, plate)
checks["board in spine"] = hit(board, spine)
# the plate goes in straight from behind with the board on it, tongue first, over the lid
path = M.batch_boolean([(plate + check_board).translate([0, k, 0]) for k in np.arange(0.0, REAR_FACE - tongue_y0 + 6.0, 1.0)],
                       m3.OpType.Add)
checks["slide-in path"] = hit(path, spine)
# speaker wires: a 7 mm bundle from under the lid up through either hole and along the channel
def wires(hx, hy):
    s = lambda p: M.sphere(3.5, 24).translate(list(p))
    return M.batch_hull([s((hx, hy, LID_Z0 - 3)), s((hx, hy, P_LOW[2]))]) + M.batch_hull([s((hx, hy, P_LOW[2])), s(P_HIGH)])
for name, (hx, hy) in (("original hole", WIRE_HOLE), ("rework hole", REWORK_HOLE)):
    w = wires(hx, hy)
    checks[f"wires ({name}) vs plate+board"] = hit(w, plate + check_board)
# the original hole's 12 mm throat stays open above, so it can be glued shut around the wires
checks["wire throat vs plate+board"] = hit(cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], TOPZ, CAV_Z[1], WIRE_BORE_D), plate + check_board)
for k, v in checks.items():
    print(f"  {k:34s} {v:7.2f} mm3")
assert max(checks.values()) < 0.05, "fit check failed"

print(f"socket mouth {FACE_Y - MOUTH_Y:.2f} mm behind the face, face {OUT_D:.1f} mm out of the spine")
print(f"board far edge at Y {FAR_Y:.2f}, tongue to Y {tongue_y0:.2f}; wire throat ends at Y {WIRE_HOLE[1] + WIRE_BORE_D / 2:.1f}")
print(f"board screws: access holes {CEIL:.1f} -> {PWR_ZW + PLATE_H:.1f}, floor {PWR_ZW + FACE_Z[0]:.2f} -> {PCB_BOT:.2f} "
      f"({PCB_BOT - PWR_ZW - FACE_Z[0]:.1f} mm of thread)")
print(f"tongue {PCB_BOT - CAV_Z[0] - TONGUE_CLR:.2f} mm thick, {CAV_Z[0] + TONGUE_CLR - CAV_Z[0]:.1f} mm off the cavity floor; "
      f"terminal top {PCB_TOP + TERM_TALL:.1f} under the cavity roof {CAV_Z[1]:.1f}")

def export(man, name):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=False)
    tm.export(os.path.join(OUT, name + ".stl"))
    bb = tm.bounds
    print(f"{name:34s} vol {tm.volume/1000:6.2f} cm3  bbox {np.round(bb[1]-bb[0],1)}  watertight={tm.is_watertight}")
    return tm

export(plate, "power_plate_adafruit_first_build_world")
export(board, "_render_husb238_world")
export(spine, "_check_first_build_spine")
# print orientation: snout face down on the bed, tongue standing up
export(plate.rotate([-90, 0, 0]).translate([0, 0, FACE_Y]), "print_power_plate_adafruit_first_build")
