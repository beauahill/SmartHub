"""
Counter Display enclosure - parametric model (manifold3d)
Units: mm.  World axes: X = width, Y = depth (front face at Y=0, back is +Y), Z = up.

Parts exported (world position as <name>.stl, print orientation as print_<name>.stl):
  base_tub       speaker box with full range sub chambers, open top
  lid_spine      top plate (seals all three chambers) printed in one piece with the tilted
                 spine that joins it to the bezel tray and carries the cable channel
  grille_ring    ring frame that the linen wraps around, slides on from below, magnets to the tub
  bezel_front    tablet frame, front lip + pocket
  bezel_tray     back housing for the KABD-430 amp, PD module, 5 V buck, ESP32-C3 and audio adapter
  dc_plate       flush plate that carries the 24 V panel jack, screws into the spine's rear face
  _render_fabric linen skin, for renders only
Measure your tablet and drivers and edit the PARAMETERS block before printing.

Usage:  python enclosure.py [out_dir]      (needs manifold3d, trimesh, numpy; see requirements.txt)
"""
import math, os, sys
import numpy as np
import manifold3d as m3
import trimesh

M, CS = m3.Manifold, m3.CrossSection
SEG = 96
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)

# ---------------- PARAMETERS ----------------
# Base
BW, BD = 300.0, 150.0          # outer width, depth
TUB_H, LID_T = 116.0, 4.0      # tub height, lid thickness (total base height 120)
R_FRONT, R_REAR = 24.0, 12.0   # plan view corner radii
WALL_SIDE, WALL_REAR, FLOOR = 7.0, 10.0, 5.0
FRONT_INNER_Y = 12.0           # front baffle inner face (outer face at Y=0, recess to Y=3 -> 9 mm baffle)
RECESS = 3.0                   # grille recess depth (2.4 frame + 0.6 fabric)
REC_Z1 = 113.0                 # linen band runs from the counter up to here
FABRIC = 0.6
CHAMBER_WALL = 4.0
FR_CH_X0 = 58.0                # full range chamber inner wall starts at |X| = 58
FR_CH_Y1 = 80.0                # full range chamber back wall outer face

# Drivers, from the Dayton Audio spec sheets and the ND65 3D model.
# Each frame is a round body with four mounting ears on the diagonals:
#   body_r     radius of the round part of the frame
#   ear_c, ear_r   ear tip modeled as a circle of radius ear_r centered ear_c from the axis
#   flange_t   frame flange thickness
#   proud      how far the surround stands in front of the mounting face, at rest
#   cut        baffle cutout
#   tab_notch  (half width, reach from the axis, depth behind the mounting face where it starts):
#              relief on the top side for solder tabs that stick out past the cutout
#   bc         screw bolt circle (4 x 4.2 mm holes at 45 deg)
#   fabric_clear   gap from the surround (at rest) to the fabric, for cone excursion
#   well_clr   clearance around the frame in its recess
DRIVERS = {
    # ND65-4: 64 mm frame, 52 mm cutout, 48 mm deep (43 behind the mounting face), Xmax 3.5 mm.
    # Outline, proud height and solder tabs measured from Dayton's STEP/STL. The tabs reach 27 mm from
    # the axis within +-15.7 mm, from 2.5 mm behind the flange. Mount the ND65s with the tabs up.
    "nd65":   dict(body_r=32.45, ear_c=34.5, ear_r=3.4, flange_t=1.0, proud=4.1, cut=52.6, tab_notch=(16.5, 28.0, 2.0),
                   bc=66.0, fabric_clear=4.0, well_clr=0.5),
    # ND105-4: 105 mm frame, ears to 120 mm, 93 mm cutout, 67 mm deep (57 behind the mounting face),
    # Xmax 4 mm. Ear shape inferred from the drawing, so the recess has extra clearance.
    "nd105":  dict(body_r=52.5, ear_c=55.0, ear_r=5.0, flange_t=1.7, proud=10.0, cut=93.4, tab_notch=None,
                   bc=108.5, fabric_clear=5.0, well_clr=1.0),
    # ND105-PR: same frame as the ND105-4, 40.5 mm deep (30.5 behind the mounting face), Xmax 11 mm.
    "nd105pr": dict(body_r=52.5, ear_c=55.0, ear_r=5.0, flange_t=1.7, proud=10.0, cut=93.4, tab_notch=None,
                   bc=108.5, fabric_clear=9.0, well_clr=1.0),
}
FR_X = 96.0                            # full range centers at +/-X
DRV_Z = (FLOOR + TUB_H) / 2.0          # driver center height
MOUNT_MEAT = 7.0                       # baffle material behind each mounting face, for the screws
GASKET_T = 1.0                         # foam gasket under each flange (compressed); seats sit this much deeper
PILOT_D = 2.5                          # blind pilots for M3 thread-forming or #4 screws
PILOT_DEPTH = 6.0                      # leaves 1 mm before the chamber

# Tablet (Galaxy Tab A9+ : 257.1 x 168.7 x 6.9)
TAB_W, TAB_H, TAB_T, TAB_R = 257.1, 168.7, 6.9, 10.0
TAB_CLR = 0.4
WIN_W, WIN_H, WIN_R = 238.0, 149.5, 3.0     # visible window (11" 16:10 active area is ~237 x 148)
FRAME = 9.0                                  # bezel border width above and below the pocket
FRAME_SIDE = 13.0                            # bezel border width left and right of the pocket
USB_CLEAR = 10.0                             # room past the tablet's USB-C edge for a right-angle adapter
CHIN = 12.0                                  # extra bottom border that houses the mmWave sensor
RADAR_W, RADAR_H = 23.0, 17.0                # pocket for HLK-LD2410C (22 x 16 mm board)
LIP = 2.4
USB_NOTCH_H = 22.0                           # height of the USB-C notch, centered on the tablet
POCKET_D = TAB_T + 0.4
TRAY_WALL = 2.4
# Amplifier: Dayton Audio KABD-430. Board 91.4 x 68.6 mm, M3 holes on 83.8 x 61.0 mm.
# Height: the user guide says 20 mm, retail listings say 0.9 in (23 mm). Measure yours and set AMP_H.
AMP_HOLES = (83.8, 61.0)                     # hole spacing, x by z
AMP_H = 23.0                                 # tallest part above the PCB bottom, including the PCB
AMP_STANDOFF = 3.5                           # PCB bottom above the tray back wall
AMP_CLEAR = 1.0                              # gap between the tallest part and the tablet back
# Tray depth follows the amp: wall + standoff + amp + clearance, never less than the original 26 mm.
TRAY_D = max(26.0, math.ceil(TRAY_WALL + AMP_STANDOFF + AMP_H + AMP_CLEAR))
# Cradles on the inside of the tray back wall: (name, x, z, width, height) of the board itself, in
# bezel coordinates (z from the bezel bottom edge). Low walls locate each part; VHB tape holds it.
# Set the PD module size to the module you buy.
CRADLE_WALL, CRADLE_H, CRADLE_CLR = 1.6, 3.0, 0.4
# Each cradle also gets a raised label, printed above or below it.
CRADLES = [
    ("pd_module",      85.0,  75.0, 40.0, 25.0, "PD MODULE",     "below"),   # 24 V -> USB-C PD output
    ("audio_adapter",  85.0, 120.0, 45.0, 30.0, "AUDIO ADAPTER", "above"),   # UGREEN 2-in-1 USB-C to 3.5 mm + PD body
    ("buck_5v",        40.0, 120.0, 22.0, 17.0, "5V BUCK",       "above"),   # MP1584EN
    ("esp32_c3",       45.0,  80.0, 22.5, 18.0, "ESP32-C3",      "below"),   # ESP32-C3 SuperMini
]
# Raised labels inside the bezel, one per component. They face up in both print orientations.
LABELS = True
LABEL_SIZE = 5.5                             # font size in mm; capitals come out about 4 mm tall
LABEL_RAISE = 0.6                            # height above the surface
LABEL_GAP = 1.5                              # space between a cradle wall and its label
LABEL_FONT = "DejaVu Sans"                   # bundled with matplotlib, so every machine gets the same STL
CAMERA_HOLE = True
USB_SIDE = +1                                # +1 = tablet USB-C at right end, -1 = left
TILT = 15.0                                  # screen tilt back, degrees
BEZ_Y0 = 14.0                                # bezel bottom-front edge Y
BEZ_GAP = 4.0                                # air gap between lid and lowest bezel corner

# Hardware
M3_CLR, M3_INSERT, INSERT_DEPTH = 3.4, 4.0, 6.0
# 24 V input: a panel-mount DC-099 barrel jack (5.5 x 2.1 mm, 11 mm hole, 6 mm max panel, hex nut).
# The jack nuts onto a small printed plate, which sits flush in a pocket on the spine's rear face and
# is held by two M3 countersunk screws in heat-set inserts. The cavity behind it clears the nut.
DC_JACK_HOLE = 11.3                          # 11 mm nominal; printed holes run small
DC_JACK_Z = 16.0                             # jack center above the lid top
DC_PLATE_W, DC_PLATE_H, DC_PLATE_T, DC_PLATE_R = 40.0, 24.0, 3.0, 3.0
DC_PLATE_CLR = 0.2                           # pocket clearance per side
DC_CAVITY_D = 19.0                           # clears a 14 mm hex nut across its corners
DC_SCREW_X = 15.0                            # plate screws at +-X
# Magnet pairs: a 6x2 mm disc in the tub and a 6x1 mm disc in the grille ring at each position.
MAG_D = 6.4                                  # pocket diameter for 6 mm discs
MAG_T_TUB, MAG_T_FRAME = 2.0, 1.0            # magnet thicknesses
MAG_GLUE = 0.2                               # tub magnet sits this far below the surface
RING_GAP = 0.15                              # clearance between the grille ring and the tub recess
MAG_TUB = MAG_T_TUB + MAG_GLUE               # pocket depth into the tub
MAG_FRAME = MAG_T_FRAME + RING_GAP           # pocket cut, measured from the tub surface; flush in the ring
# ---------------------------------------------

def rrect(x0, x1, y0, y1, rf, rr, n=24):
    """Rounded rectangle, front (low y) corners radius rf, rear corners rr."""
    pts = []
    def arc(cx, cy, r, a0, a1):
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    arc(x1 - rf, y0 + rf, rf, -90, 0)
    arc(x1 - rr, y1 - rr, rr, 0, 90)
    arc(x0 + rr, y1 - rr, rr, 90, 180)
    arc(x0 + rf, y0 + rf, rf, 180, 270)
    return CS([pts])

def box(x0, x1, y0, y1, z0, z1):
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])

def cyl_z(x, y, z0, z1, d):
    return M.cylinder(z1 - z0, d / 2, d / 2, SEG).translate([x, y, z0])

def cyl_y(x, z, y0, y1, d):
    # cylinder along +Y
    return M.cylinder(y1 - y0, d / 2, d / 2, SEG).rotate([-90, 0, 0]).translate([x, y0, z])

def cyl_x(y, z, x0, x1, d):
    return M.cylinder(x1 - x0, d / 2, d / 2, SEG).rotate([0, 90, 0]).translate([x0, y, z])

def union(parts):
    return M.batch_boolean(parts, m3.OpType.Add)

def extrude(cs, z0, z1):
    return cs.extrude(z1 - z0).translate([0, 0, z0])

def text_cs(s, size=None):
    """Text outline as a CrossSection, centered on the origin (bold DejaVu from matplotlib)."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    tp = TextPath((0, 0), s, size=size or LABEL_SIZE, prop=FontProperties(family=LABEL_FONT, weight="bold"))
    cs = CS([p.tolist() for p in tp.to_polygons(closed_only=True)], m3.FillRule.EvenOdd)
    cs = cs.offset(0.02, m3.JoinType.Miter)    # merges glyph contours that touch at a point (the K)
    x0, y0, x1, y1 = cs.bounds()
    return cs.translate([-(x0 + x1) / 2, -(y0 + y1) / 2])

def bezel_label(s, x, z, a_face, toward, angle=0.0):
    """Raised label on a bezel face at depth a_face, standing LABEL_RAISE proud toward -a (toward=-1)
    or +a (toward=+1). Text reads correctly when viewed from the side it stands out toward."""
    cs = text_cs(s).rotate(angle)
    if toward > 0:
        cs = cs.mirror([1, 0])                 # seen from behind, so flip left-right
    h = LABEL_RAISE + 0.2                      # 0.2 mm sunk into the face so they fuse
    solid = cs.extrude(h).rotate([90, 0, 0])   # profile y -> z, extrusion -> -a, spanning a = -h..0
    shift = a_face + 0.2 if toward < 0 else a_face + LABEL_RAISE
    return solid.translate([x, shift, z])

# ======================= BASE TUB =======================
# Linen wraps the whole base (front, sides, rear). The tub is recessed RECESS mm all the way
# around from the floor up to REC_Z1; a one piece ring frame slides on from below and is held by magnets.
outline = rrect(-BW/2, BW/2, 0, BD, R_FRONT, R_REAR)
inset = rrect(-BW/2 + RECESS, BW/2 - RECESS, RECESS, BD - RECESS, R_FRONT - RECESS, R_REAR - RECESS)
inner = rrect(-BW/2 + WALL_SIDE, BW/2 - WALL_SIDE, FRONT_INNER_Y, BD - WALL_REAR,
              R_FRONT - WALL_SIDE, max(R_REAR - WALL_REAR, 2))
IX = BW/2 - WALL_SIDE
IY0, IY1 = FRONT_INNER_Y, BD - WALL_REAR

tub = extrude(inset, 0, REC_Z1) + extrude(outline, REC_Z1, TUB_H)
tub = tub - extrude(inner, FLOOR, TUB_H + 1)

# full range sub chambers (one per side)
for s in (-1, 1):
    xw0, xw1 = sorted((s * FR_CH_X0, s * (FR_CH_X0 + CHAMBER_WALL)))
    tub = tub + box(xw0, xw1, IY0 - 1, FR_CH_Y1, FLOOR - 1, TUB_H)
    xb0, xb1 = sorted((s * FR_CH_X0, s * (IX + 1)))
    tub = tub + box(xb0, xb1, FR_CH_Y1 - CHAMBER_WALL, FR_CH_Y1, FLOOR - 1, TUB_H)

# brace columns, which also take the lid locating pins
# (+-139, 100) overlaps the side wall by 1 mm. At 138 the column only touched the wall along a line,
# which made the mesh non-manifold.
BOSSES = [(-135, 22), (135, 22), (-139, 100), (139, 100), (-130, 128), (130, 128)]
for (x, y) in BOSSES:
    tub = tub + (cyl_z(x, y, FLOOR - 1, TUB_H, 10) ^ extrude(inner.offset(1, m3.JoinType.Round), 0, TUB_H))
for (x, y) in BOSSES:
    tub = tub - cyl_z(x, y, TUB_H - 4, TUB_H + 1, 4.3)

# Driver mounts. Each driver sits in a recessed well deep enough that its surround clears the fabric
# by fabric_clear, on a mounting ring that thickens the baffle behind it for the screws.
def frame_outline(d, grow=0.0):
    ears = [CS.circle(d["ear_r"] + grow, 48).translate([d["ear_c"] * math.cos(math.radians(a)),
                                                        d["ear_c"] * math.sin(math.radians(a))])
            for a in (45, 135, 225, 315)]
    return CS.batch_hull([CS.circle(d["body_r"] + grow, SEG)] + ears)

def prism_y(cs, x, z, y0, y1):
    """extrude an X-Z profile (drawn in X-Y) along +Y from y0 to y1, centered at (x, z)"""
    return cs.extrude(y1 - y0).rotate([-90, 0, 0]).translate([x, y0, z])

INTERIOR = box(-IX, IX, IY0 - 1, IY1 + 1, FLOOR - 1, TUB_H)
SEATS = {}

def mount_driver(tub, name, x, rear=False):
    d = DRIVERS[name]
    sgn = 1 if rear else -1                                   # direction the driver faces, along Y
    fabric_in = BD - FABRIC if rear else FABRIC               # inside face of the fabric
    surface = BD - RECESS if rear else RECESS                 # recessed tub surface under the fabric
    seat = fabric_in - sgn * (d["fabric_clear"] + d["proud"] + GASKET_T)   # baffle face under the gasket
    back = seat - sgn * MOUNT_MEAT                            # back of the mounting ring
    SEATS[name + ("" if x >= 0 else "_l")] = seat
    # the ring runs from the baffle to the back of the mounting face, so the well gets solid walls
    baffle = BD - WALL_REAR + 1 if rear else IY0 - 1
    lo, hi = sorted((baffle, back))
    ring = prism_y(frame_outline(d, 4.0), x, DRV_Z, lo, hi) ^ INTERIOR
    tub = tub + ring
    # well: from the recessed surface down to the mounting face. Keep the skin above the fabric line.
    w0, w1 = sorted((surface - sgn * 0.3, seat))
    tub = tub - prism_y(frame_outline(d, d["well_clr"]), x, DRV_Z, w0, w1)
    e0, e1 = sorted((surface + sgn * 1.0, surface - sgn * 0.3))
    tub = tub - (prism_y(frame_outline(d, d["well_clr"]), x, DRV_Z, e0, e1) ^ box(-BW, BW, -10, BD + 10, -10, REC_Z1 - 0.01))
    # cutout through the ring, plus the solder-tab relief on the top side
    c0, c1 = sorted((seat + sgn * 1.0, back - sgn * 5.0))
    tub = tub - cyl_y(x, DRV_Z, c0, c1, d["cut"])
    if d["tab_notch"]:
        hw, reach, depth = d["tab_notch"]
        n0, n1 = sorted((seat - sgn * depth, back - sgn * 5.0))
        tub = tub - box(x - hw, x + hw, n0, n1, DRV_Z + d["cut"] / 2 - 2.0, DRV_Z + reach)
    # blind pilot holes on the bolt circle
    for k in range(4):
        a = math.radians(45 + 90 * k)
        px, pz = x + d["bc"] / 2 * math.cos(a), DRV_Z + d["bc"] / 2 * math.sin(a)
        p0, p1 = sorted((seat + sgn * 0.5, seat - sgn * PILOT_DEPTH))
        tub = tub - cyl_y(px, pz, p0, p1, PILOT_D)
    return tub

tub = mount_driver(tub, "nd65", -FR_X)
tub = mount_driver(tub, "nd65", FR_X)
tub = mount_driver(tub, "nd105", 0)
tub = mount_driver(tub, "nd105pr", 0, rear=True)

# wire pass-through holes into each full range chamber (seal with hot glue)
PASS_THROUGHS = [cyl_x(FR_CH_Y1 - 12, TUB_H - 14, FR_CH_X0 - 6, FR_CH_X0 + 10, 4),
                 cyl_x(FR_CH_Y1 - 12, TUB_H - 14, -FR_CH_X0 - 10, -FR_CH_X0 + 6, 4)]
for c in PASS_THROUGHS:
    tub = tub - c

# magnet pockets (front / rear: (x, z); sides: (y, z))
MAG_FRONT = [(-58, 9), (58, 9), (-58, 106), (58, 106)]
MAG_REAR = [(-62, 9), (62, 9), (-62, 106), (62, 106)]
MAG_SIDE = [(65, 9), (65, 106)]
YF, YR, XS = RECESS, BD - RECESS, BW/2 - RECESS
def mag_cuts(depth_tub, depth_frame, for_frame):
    cuts = []
    a, b = (-depth_frame, 0.01) if for_frame else (-1, depth_tub)   # offsets measured inward from the inset surface
    for (x, z) in MAG_FRONT:
        cuts.append(cyl_y(x, z, YF + (-0.01 if for_frame else -1), YF + (0.01 if for_frame else depth_tub), MAG_D) if not for_frame
                    else cyl_y(x, z, YF - depth_frame, YF + 0.01, MAG_D))
    for (x, z) in MAG_REAR:
        cuts.append(cyl_y(x, z, YR - depth_tub, YR + 1, MAG_D) if not for_frame else cyl_y(x, z, YR - 0.01, YR + depth_frame, MAG_D))
    for (y, z) in MAG_SIDE:
        if not for_frame:
            cuts += [cyl_x(y, z, XS - depth_tub, XS + 1, MAG_D), cyl_x(y, z, -XS - 1, -XS + depth_tub, MAG_D)]
        else:
            cuts += [cyl_x(y, z, XS - 0.01, XS + depth_frame, MAG_D), cyl_x(y, z, -XS - depth_frame, -XS + 0.01, MAG_D)]
    return cuts
for c in mag_cuts(MAG_TUB, MAG_FRAME, False):
    tub = tub - c

# feet recesses (10 mm silicone bumpers, ~3 mm tall, lift the fabric edge off the counter)
for (x, y) in [(-120, 24), (120, 24), (-120, 126), (120, 126)]:
    tub = tub - cyl_z(x, y, -1, 1.0, 10.5)

# ======================= LID (glued on; spine is printed with it) =======================
LID_Z0 = TUB_H
TOPZ = LID_Z0 + LID_T
CH = 1.2   # top edge chamfer
lid = M.batch_hull([extrude(outline, LID_Z0, TOPZ - CH), extrude(outline.offset(-CH, m3.JoinType.Round), TOPZ - CH, TOPZ)])
for (x, y) in BOSSES:                      # 4 mm dowel holes (dowels align lid to tub for gluing)
    lid = lid - cyl_z(x, y, LID_Z0 - 1, LID_Z0 + 2.0, 4.3)
WIRE_HOLE = (0, 74)
lid = lid - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], LID_Z0 - 1, TOPZ + 1, 12)

# ======================= GRILLE RING =======================
frame_outer = inset.offset(RECESS - FABRIC, m3.JoinType.Round)
GZ0, GZ1 = 0.5, REC_Z1 - 0.5
gf = extrude(frame_outer, GZ0, GZ1) - extrude(inset.offset(RING_GAP, m3.JoinType.Round), -1, 200)
WZ0, WZ1 = 18.0, GZ1 - 14.0
FW = 150 - R_FRONT - 2      # flat part of front face
win = box(-FW, -60.5, -20, 40, WZ0, WZ1) + box(-55.5, 55.5, -20, 40, WZ0, WZ1) + box(60.5, FW, -20, 40, WZ0, WZ1)
win = win + box(-200, -120, 32, BD - 20, WZ0, WZ1) + box(120, 200, 32, BD - 20, WZ0, WZ1)
RW = 150 - R_REAR - 4
win = win + box(-RW, -66, BD - 40, BD + 20, WZ0, WZ1) + box(-58, 58, BD - 40, BD + 20, WZ0, WZ1) + box(66, RW, BD - 40, BD + 20, WZ0, WZ1)
gf = gf - win
for c in mag_cuts(MAG_TUB, MAG_FRAME, True):
    gf = gf - c
fabric = extrude(outline, GZ0, GZ1) - extrude(inset, -1, 200)

# ======================= BEZEL (built in local frame) =======================
# local: x = X, y = a (depth, 0 at front face, + backward), z = h (up the face, 0 at bottom edge)
PW, PH = TAB_W + 2 * TAB_CLR, TAB_H + 2 * TAB_CLR
EW, EH = PW + 2 * FRAME_SIDE, PH + 2 * FRAME + CHIN
assert USB_CLEAR <= FRAME_SIDE - TRAY_WALL - 0.4, "USB_CLEAR needs a wider FRAME_SIDE"
ER = TAB_R + FRAME
T_FRONT = LIP + POCKET_D
T = T_FRONT + TRAY_D
HC = EH / 2
TAB_CZ = FRAME + CHIN + PH / 2               # tablet center height in the bezel

def rr_xz(w, h, r, a0, a1, cx=0.0, cz=HC):
    """rounded rect in the X-Z plane, extruded along local depth a0..a1"""
    cs = rrect(-w/2, w/2, -h/2, h/2, r, r)
    return cs.extrude(a1 - a0).rotate([90, 0, 0]).translate([cx, a1, cz])  # rotate: z->-y, so shift

def lcyl_a(x, z, a0, a1, d):
    return M.cylinder(a1 - a0, d/2, d/2, SEG).rotate([-90, 0, 0]).translate([x, a0, z])

def lbox(x0, x1, a0, a1, z0, z1):
    return box(x0, x1, a0, a1, z0, z1)

# --- bezel front
BCH = 1.2  # edge chamfer
bf = M.batch_hull([rr_xz(EW - 2*BCH, EH - 2*BCH, ER - BCH, 0, BCH), rr_xz(EW, EH, ER, BCH, T_FRONT)])
bf = bf - rr_xz(WIN_W, WIN_H, WIN_R, -1, LIP + 0.01, cz=TAB_CZ)                        # window
bf = bf - rr_xz(PW, PH, TAB_R + TAB_CLR, LIP, T_FRONT + 1, cz=TAB_CZ)                   # pocket
if CAMERA_HOLE:
    bf = bf - lcyl_a(0, TAB_CZ + PH / 2 - 5.5, -1, LIP + 1, 5.0)
# mic slots through the top of the frame into the pocket
for x in (-60, -20, 20, 60):
    bf = bf - lbox(x - 6, x + 6, LIP + 1.5, LIP + 4.5, TAB_CZ + PH / 2 - 1, EH + 1)
# USB-C notch at the port end. A right-angle adapter turns the plug back into the tray.
ux0, ux1 = sorted((USB_SIDE * PW/2 - USB_SIDE * 1, USB_SIDE * (PW/2 + USB_CLEAR)))
bf = bf - lbox(ux0, ux1, LIP + 0.2, T_FRONT + 1, TAB_CZ - USB_NOTCH_H / 2, TAB_CZ + USB_NOTCH_H / 2)
# mmWave radar pocket in the chin, open to the tray; the radar looks out through the 2.4 mm lip
RADAR_Z = (FRAME + CHIN) / 2
bf = bf - lbox(-RADAR_W / 2, RADAR_W / 2, LIP, T_FRONT + 1, RADAR_Z - RADAR_H / 2, RADAR_Z + RADAR_H / 2)
# insert holes for tray screws
SCREWS = [(-(EW/2 - 4.5), 32), (EW/2 - 4.5, 32), (-(EW/2 - 4.5), EH - 32), (EW/2 - 4.5, EH - 32),
          (-70, 4.5), (70, 4.5), (-70, EH - 4.5), (70, EH - 4.5)]
for (x, z) in SCREWS:
    bf = bf - lcyl_a(x, z, T_FRONT - INSERT_DEPTH, T_FRONT + 1, M3_INSERT)
# radar label on the back of the chin, beside its pocket (read from the tray side)
if LABELS:
    bf = bf + bezel_label("LD2410C", RADAR_W / 2 + 18.0, RADAR_Z, T_FRONT, +1)

# --- bezel tray
tr = M.batch_hull([rr_xz(EW, EH, ER, T_FRONT, T - BCH), rr_xz(EW - 2*BCH, EH - 2*BCH, ER - BCH, T - BCH, T)]) - rr_xz(EW - 2*TRAY_WALL, EH - 2*TRAY_WALL, ER - TRAY_WALL, T_FRONT - 1, T - TRAY_WALL)
# screw bosses through the tray depth
CBORE = 5.0 + (TRAY_D - 26.0)   # counterbore grows with the tray, so M3x25 keeps ~4 mm insert engagement
for (x, z) in SCREWS:
    tr = tr + (lcyl_a(x, z, T_FRONT, T - 0.01, 8.0) ^ rr_xz(EW, EH, ER, T_FRONT - 1, T + 1))
for (x, z) in SCREWS:
    tr = tr - lcyl_a(x, z, T_FRONT - 1, T + 1, M3_CLR) - lcyl_a(x, z, T - CBORE, T + 1, 6.2)
# tablet back-stop posts (put 1.5 mm foam on the tips)
for x in (-115, 0, 115):
    for z in (40, EH - 40):
        tr = tr + lcyl_a(x, z, T_FRONT, T - 0.01, 8.0)
# KABD-430 standoffs, 2.6 mm pilots for M3 thread-forming screws
JX, JZ = -70.0, HC
for dx in (-AMP_HOLES[0] / 2, AMP_HOLES[0] / 2):
    for dz in (-AMP_HOLES[1] / 2, AMP_HOLES[1] / 2):
        tr = tr + lcyl_a(JX + dx, JZ + dz, T - TRAY_WALL - AMP_STANDOFF, T - 0.01, 7.0)
        tr = tr - lcyl_a(JX + dx, JZ + dz, T - TRAY_WALL - AMP_STANDOFF - 1, T - 1.0, 2.6)
# USB notch continuation
tr = tr - lbox(ux0, ux1, T_FRONT - 1, T_FRONT + 3, TAB_CZ - USB_NOTCH_H / 2, TAB_CZ + USB_NOTCH_H / 2)
# cradles for the small boards, standing off the inside of the back wall
BACK_IN = T - TRAY_WALL
for (_, cx, cz, w, h, label, side) in CRADLES:
    iw, ih = w + 2 * CRADLE_CLR, h + 2 * CRADLE_CLR
    ring = lbox(cx - iw/2 - CRADLE_WALL, cx + iw/2 + CRADLE_WALL, BACK_IN - CRADLE_H, BACK_IN + 0.01,
                cz - ih/2 - CRADLE_WALL, cz + ih/2 + CRADLE_WALL) \
         - lbox(cx - iw/2, cx + iw/2, BACK_IN - CRADLE_H - 1, BACK_IN + 1, cz - ih/2, cz + ih/2)
    gap = min(8.0, ih / 2)                   # wire exits on both short sides
    ring = ring - lbox(cx - iw/2 - CRADLE_WALL - 1, cx + iw/2 + CRADLE_WALL + 1, BACK_IN - CRADLE_H - 1, BACK_IN - 0.6,
                       cz - gap/2, cz + gap/2)
    tr = tr + ring
    if LABELS:
        off = ih / 2 + CRADLE_WALL + LABEL_GAP + LABEL_SIZE * 0.4
        tr = tr + bezel_label(label, cx, cz + (off if side == "above" else -off), BACK_IN, -1)
if LABELS:
    # amp: above the board; right-angle USB-C adapter: beside the notch, reading upward
    tr = tr + bezel_label("KABD-430 AMP", JX, JZ + 34.3 + LABEL_GAP + 3.5 + LABEL_SIZE * 0.4, BACK_IN, -1)
    tr = tr + bezel_label("USB-C 90°", USB_SIDE * (PW / 2 - 4.0), TAB_CZ, BACK_IN, -1, angle=90 * USB_SIDE)
# vents in the back wall
for i in range(9):
    x = -112 + i * 28
    if abs(x) < 40:
        continue
    tr = tr - lbox(x - 2, x + 2, T - TRAY_WALL - 1, T + 1, 12, 34)
for i in range(16):
    x = -112 + i * 15
    tr = tr - lbox(x - 2, x + 2, T - TRAY_WALL - 1, T + 1, EH - 34, EH - 12)
# spine bolts (heads inside tray, inserts in spine)
SPINE_PTS = [(-18, 25), (18, 25), (-18, 85), (18, 85)]
for (x, z) in SPINE_PTS:
    tr = tr - lcyl_a(x, z, T - TRAY_WALL - 1, T + 1, M3_CLR)
CH_H = 60.0                                     # cable channel enters tray here
tr = tr - lcyl_a(0, CH_H, T - TRAY_WALL - 1, T + 1, 13)

# --- place bezel in world
st, ct = math.sin(math.radians(TILT)), math.cos(math.radians(TILT))
Z0 = LID_Z0 + LID_T + BEZ_GAP + T * st
def place(part):
    return part.rotate([-TILT, 0, 0]).translate([0, BEZ_Y0, Z0])
def to_world(x, a, h):
    return np.array([x, BEZ_Y0 + a * ct + h * st, Z0 - a * st + h * ct])
bezel_front_w, bezel_tray_w = place(bf), place(tr)

# ======================= SPINE =======================
bp0 = to_world(0, T, 0)              # bottom of tray back face
HS = 115.0
bps = to_world(0, T, HS)
Yb0 = bp0[1]
REAR_Y = Yb0 + 50
REAR_FACE_H = max(8.0, DC_JACK_Z + DC_PLATE_H / 2 + 3.0)   # flat rear face tall enough for the jack plate
prof = CS([[(Yb0 - 6, TOPZ), (REAR_Y - 0.6, TOPZ), (REAR_Y - 0.6, TOPZ + REAR_FACE_H), (bps[1], bps[2]), (bp0[1], bp0[2]), (Yb0 - 6, bp0[2])]])
SW = 60.0
spine = prof.extrude(SW).rotate([90, 0, 90]).translate([-SW/2, 0, 0])   # profile (Y,Z) extruded along X
spine = spine.translate([0, 0, -0.5])     # sink 0.5 mm into the lid so they fuse
# inserts for tray bolts, drilled along the bezel normal
for (x, h) in SPINE_PTS:
    p = to_world(x, T, h)
    c = M.cylinder(INSERT_DEPTH + 1, M3_INSERT/2, M3_INSERT/2, SEG).rotate([-90, 0, 0]).rotate([-TILT, 0, 0])
    spine = spine - c.translate((to_world(x, T - 1, h)).tolist())
# cable channel: hull of two spheres, lid hole -> tray
p_low = np.array([0, WIRE_HOLE[1], TOPZ - 2])
p_high = to_world(0, T - 6, CH_H)
chan = M.batch_hull([M.sphere(6, 48).translate(p_low.tolist()), M.sphere(6, 48).translate(p_high.tolist())])
spine = spine - chan
# 24 V jack: flush pocket for the plate, cavity for the jack body and nut, inserts for the plate screws
def plate_cs(w, h, r):
    return rrect(-w/2, w/2, -h/2, h/2, r, r)
def along_y(cs, y0, y1, z):
    """extrude an X-Z profile (drawn as X-Y) along +Y from y0 to y1, centered at height z"""
    return cs.extrude(y1 - y0).rotate([-90, 0, 0]).translate([0, y0, z])
REAR_FACE = REAR_Y - 0.6
DC_Z = TOPZ + DC_JACK_Z
POCKET_FLOOR = REAR_FACE - DC_PLATE_T
spine = spine - along_y(plate_cs(DC_PLATE_W + 2 * DC_PLATE_CLR, DC_PLATE_H + 2 * DC_PLATE_CLR, DC_PLATE_R + DC_PLATE_CLR),
                        POCKET_FLOOR, REAR_FACE + 1, DC_Z)
spine = spine - cyl_y(0, DC_Z, WIRE_HOLE[1] - 8, POCKET_FLOOR + 0.01, DC_CAVITY_D)   # runs into the cable channel
for sx in (-DC_SCREW_X, DC_SCREW_X):
    spine = spine - cyl_y(sx, DC_Z, POCKET_FLOOR - INSERT_DEPTH, POCKET_FLOOR + 0.01, M3_INSERT)

# jack plate, built face down: z = 0 is the outside face
dc_plate = plate_cs(DC_PLATE_W, DC_PLATE_H, DC_PLATE_R).extrude(DC_PLATE_T)
dc_plate = dc_plate - cyl_z(0, 0, -1, DC_PLATE_T + 1, DC_JACK_HOLE)
for sx in (-DC_SCREW_X, DC_SCREW_X):
    dc_plate = dc_plate - cyl_z(sx, 0, -1, DC_PLATE_T + 1, M3_CLR)
    dc_plate = dc_plate - M.cylinder(1.7, 3.4, M3_CLR / 2, SEG).translate([sx, 0, -0.01])   # 90 deg countersink
dc_plate_w = dc_plate.rotate([90, 0, 0]).translate([0, REAR_FACE, DC_Z])
# don't let the spine poke into the tray
spine = spine - place(rr_xz(EW + 2, EH + 2, ER, -1, T))
lid_spine = lid + spine
lid_spine = lid_spine - chan - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], LID_Z0 - 1, TOPZ + 1, 12)

# ======================= EXPORT =======================
def export(man, name):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=False)
    bodies = [b for b in tm.split(only_watertight=False) if abs(b.volume) > 1.0]
    if len(bodies) > 1 or not tm.is_watertight:
        tm = trimesh.util.concatenate(bodies) if len(bodies) > 1 else bodies[0]
    tm.export(os.path.join(OUT, name + ".stl"))
    bb = tm.bounds
    print(f"{name:14s} vol {tm.volume/1000:8.1f} cm3  bbox {np.round(bb[1]-bb[0],1)}  watertight={tm.is_watertight}")
    return tm

parts_world = {
    "base_tub": tub, "lid_spine": lid_spine, "grille_ring": gf,
    "bezel_front": bezel_front_w, "bezel_tray": bezel_tray_w, "dc_plate": dc_plate_w,
}
meshes = {k: export(v, k) for k, v in parts_world.items()}
export(fabric, "_render_fabric")
# print-ready orientations
export(bf.rotate([90, 0, 0]), "print_bezel_front")          # face down
export(tr.rotate([-90, 0, 0]), "print_bezel_tray")             # back wall down
export(gf.rotate([180, 0, 0]), "print_grille_ring")          # top edge down
export(lid_spine.translate([0, 0, -LID_Z0]), "print_lid_spine")
export(tub, "print_base_tub")
export(dc_plate, "print_dc_plate")                             # outside face down

# acoustic volumes: air inside the closed tub (lid on), by chamber. Driver bodies are not subtracted.
air = extrude(inner, FLOOR, TUB_H) - tub - union(PASS_THROUGHS)   # pass-throughs hot-glued shut
chambers = sorted((c.volume() / 1e6 for c in air.decompose()), reverse=True)
print("chamber air volumes (L, driver bodies not subtracted):", [round(v, 3) for v in chambers[:3]])
print("mounting faces (Y):", {k: round(v, 1) for k, v in SEATS.items()})
print("bezel thickness", T, "bezel outer", EW, EH, "Z0", Z0, "top Z", to_world(0, 0, EH)[2], "top-back", to_world(0, T, EH))
print("lowest bezel corner Z", to_world(0, T, 0)[2], "Yb0", Yb0)
