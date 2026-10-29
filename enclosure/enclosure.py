"""
Counter Display enclosure - parametric model (manifold3d)
Units: mm.  World axes: X = width, Y = depth (front face at Y=0, back is +Y), Z = up.

Parts exported (world position as <name>.stl, print orientation as print_<name>.stl):
  base_tub       speaker box with full range sub chambers, open top
  lid_spine      top plate (seals all three chambers) printed in one piece with the tilted
                 spine that joins it to the bezel tray and carries the cable channel
  grille_ring    ring frame that the linen wraps around, slides on from below, magnets to the tub
  grille_shell   fabric-free alternative to grille_ring + linen: printed honeycomb grille, same fit
  bezel_shell    frameless bezel: thin rim around the tablet glass and the tray behind it, one piece.
                 Holds the KABD-430 amp, PD module, 5 V buck, ESP32-C3 and audio adapter
  bezel_chin     chin below the tablet with the mmWave radar; closes the bottom of the shell
  power_plate    flush USB-C power plate with a sled for the PD trigger board, screws into the spine
  _render_fabric linen skin, for renders only
  _render_tablet tablet placeholder, for renders only
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
# Fabric-free alternative: a printed grille shell replaces the grille ring and linen. Same tub, same
# magnets. Honeycomb of pointy-top hexagon holes (prints cleanly in a vertical wall), ~52% open.
SHELL_HEX = 2.6                # hole size across flats
SHELL_WEB = 1.0                # web between holes
SHELL_Z = (15.0, 100.0)        # perforated band, clear of the magnets at z = 9 and 106
SHELL_FIELD_R = 8.0            # corner radius of each perforated field
SHELL_SIDES = False            # also perforate the side faces
SHELL_TOP_GAP = 0.3            # reveal line between the shell and the tub's top band
TOP_LAND = 0.6                 # flat strip on the outer top edge of the ring / shell, under the band chamfer
BAND_CHAMFER = RECESS          # 45 deg chamfer under the top band (the band overhangs the recess by RECESS)
FOOT_CHAMFER = 0.6             # 45 deg chamfer on the tub's bottom outer edge (elephant foot, eases the ring on)
LEAD_IN = 0.5                  # 45 deg chamfer on the inner bottom edge of the ring / shell: slide-on lead-in, and
                               # room for elephant's foot, which would otherwise eat the 0.35 mm clearance
SHELL_FOOT = 0.3               # 45 deg chamfer on the shell's outer bottom edge (hides elephant's foot)
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
#   cover_clear    gap from the surround (at rest) to the inside of the covering, for cone excursion.
#                  Measured to the inner face of the grille ring / grille shell (RECESS - RING_GAP from
#                  the outside), which is closer than the linen, so it holds for both base versions.
#   well_clr   clearance around the frame in its recess
DRIVERS = {
    # ND65-4: 64 mm frame, 52 mm cutout, 48 mm deep (43 behind the mounting face), Xmax 3.5 mm.
    # Outline, proud height and solder tabs measured from Dayton's STEP/STL. The tabs reach 27 mm from
    # the axis within +-15.7 mm, from 2.4 mm behind the flange (1.4 mm behind the seat, with the gasket
    # under the flange). Mount the ND65s with the tabs up.
    "nd65":   dict(body_r=32.45, ear_c=34.5, ear_r=3.4, flange_t=1.0, proud=4.1, cut=52.6, tab_notch=(16.5, 28.0, 1.2),
                   bc=66.0, cover_clear=4.0, well_clr=0.5),
    # ND105-4: 105 mm frame, ears to 120 mm, 93 mm cutout, 67 mm deep (57 behind the mounting face),
    # Xmax 4 mm. Ear shape inferred from the drawing, so the recess has extra clearance.
    "nd105":  dict(body_r=52.5, ear_c=55.0, ear_r=5.0, flange_t=1.7, proud=10.0, cut=93.4, tab_notch=None,
                   bc=108.5, cover_clear=5.0, well_clr=1.0),
    # ND105-PR: same frame as the ND105-4, 40.5 mm deep (30.5 behind the mounting face), Xmax 11 mm.
    "nd105pr": dict(body_r=52.5, ear_c=55.0, ear_r=5.0, flange_t=1.7, proud=10.0, cut=93.4, tab_notch=None,
                   bc=108.5, cover_clear=9.0, well_clr=1.0),
}
FR_X = 96.0                            # full range centers at +/-X
DRV_Z = (FLOOR + TUB_H) / 2.0          # full range center height
# Woofer and passive radiator sit lower, so their wells (ND105 frame + clearance, radius 53.5) stay
# below the band chamfer, which starts at REC_Z1 - BAND_CHAMFER.
WOOF_Z = 56.25
MOUNT_MEAT = 7.0                       # baffle material behind each mounting face, for the screws
GASKET_T = 1.0                         # foam gasket under each flange (compressed); seats sit this much deeper
PILOT_D = 2.5                          # blind pilots for M3 thread-forming or #4 screws
PILOT_DEPTH = 6.0                      # leaves 1 mm before the chamber

# Tablet (Galaxy Tab A9+ : 257.1 x 168.7 x 6.9)
TAB_W, TAB_H, TAB_T, TAB_R = 257.1, 168.7, 6.9, 10.0
TAB_CLR = 0.4
# Frameless front: the tablet's own black glass border shows; a thin printed lip overlaps its edge.
LIP_OVERLAP = 1.5                            # how far the lip covers the tablet glass, per side
FRAME = 6.8                                  # rim width above the tablet (and part of the chin)
FRAME_SIDE = 6.8                             # rim width left and right of the tablet
USB_CLEAR = 4.0                              # room past the tablet's USB-C edge for a flat FPC 90 deg adapter
CHIN = 14.2                                  # extra bottom border for the mmWave sensor (chin = FRAME + CHIN = 21)
RADAR_W, RADAR_H = 23.0, 17.0                # pocket for HLK-LD2410C (22 x 16 mm board)
LIP = 1.2                                    # lip in front of the glass
RADAR_LIP = 1.6                              # plastic in front of the radar
USB_NOTCH_H = 22.0                           # height of the USB-C clearance around the port
POCKET_D = TAB_T + 0.8                       # room for 0.5 mm felt pads on the back-stop posts
TRAY_WALL = 2.4
# Amplifier: Dayton Audio KABD-430. Board 91.4 x 68.6 mm, M3 holes on 83.8 x 61.0 mm.
# Height: the user guide says 20 mm, retail listings say 0.9 in (23 mm). Measure yours and set AMP_H.
AMP_HOLES = (83.8, 61.0)                     # hole spacing, x by z
AMP_H = 20.0                                 # tallest part above the PCB bottom (Dayton spec sheet: 20 mm)
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
    ("pd_module",      85.0,  75.0, 40.0, 25.0, "PD MODULE",     "below"),   # 20 V -> USB-C PD output
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
USB_SIDE = +1                                # +1 = tablet USB-C at right end, -1 = left
TILT = 15.0                                  # screen tilt back, degrees
# Bezel styling. Rounded edges are drawn as a quarter circle that turns into a 45 deg chamfer on the
# edge that sits on the print bed, so they print without sagging.
BEZEL_R = TAB_R + TAB_CLR + FRAME_SIDE       # corner radius in plan: an even rim around the tablet corners
BEZEL_FRONT_FILLET = 3.0                     # round-over on the front edge
BEZEL_BACK_FILLET = 6.0                      # round-over on the tray's back edge
WINDOW_CHAMFER = 0.5                         # 45 deg chamfer on the lip's inner edge
# Chin bar: 4 screws from the back of the tray, through bosses, into inserts in the bar's back face.
CHIN_SCREW_X = (-100.0, -40.0, 40.0, 100.0)  # clear of the radar pocket in the middle
CHIN_SCREW_LEN = 20.0                         # M3 x 20; ~5 mm goes into the insert
# Bezel to spine: M3 bolts from the back of the spine into inserts in the tray's back wall.
SPINE_PTS = [(-18, 45), (18, 45), (-18, 80), (18, 80)]    # (x, height up the tray back)
SPINE_GRIP = 12.0                            # spine material under the bolt heads -> M3 x 16 bolts
SPINE_CLR = 0.2                              # gap between the spine and the tray back, so the curved bottom edge can't hold the faces apart
SPINE_TOP = 5.0                              # flat at the top of the spine, instead of a knife edge
BEZ_Y0 = 14.0                                # bezel bottom-front edge Y
BEZ_GAP = 4.0                                # air gap between lid and lowest bezel corner

# Hardware
M3_CLR, M3_INSERT, INSERT_DEPTH = 3.4, 4.0, 6.0
# Power input: USB-C PD. An Adafruit HUSB238 PD trigger (product 5991, set to 20 V on its DIP switch)
# screws to a sled on the back of a small printed plate. The plate sits flush in a pocket on the spine's
# rear face, held by two M3 countersunk screws in heat-set inserts. Board geometry is from Adafruit's
# PCB files: 20.32 x 27.81 mm, 2.5 mm holes, mid-mount USB-C socket overhanging the top edge by 1.14 mm.
# The opening clears the plug's overmold, so the plug seats fully. It takes a 13 x 7 mm overmold with
# the socket up to 0.9 mm off center (the socket's exact height on the PCB isn't in the board files).
PWR_Z = 16.0                                 # socket center above the lid top
PWR_PLATE_W, PWR_PLATE_H, PWR_PLATE_T, PWR_PLATE_R = 44.0, 26.0, 3.0, 3.0
PWR_PLATE_CLR = 0.2                          # pocket clearance per side
PWR_SCREW_X = 17.0                           # plate screws at +-X
PWR_OPENING = (14.4, 8.8, 2.4)               # rounded rectangle (w, h, corner r) the plug overmold passes through
PWR_OPENING_CHAMFER = 0.6
TRIG_W, TRIG_L, TRIG_T = 20.32, 27.81, 1.6   # PD trigger PCB
TRIG_USB_OVERHANG = 1.14                     # socket mouth beyond the PCB edge
TRIG_USB_OFFSET = 0.0                        # socket center above the PCB mid-plane
TRIG_HOLES = [(2.413, 25.273), (17.653, 25.273), (2.54, 2.54), (17.78, 2.54)]   # board coords, USB edge at y = 27.81
TRIG_PAD, TRIG_PAD_H = 5.0, 2.2              # standoff pads under the mounting holes
TRIG_PILOT = 2.1                             # for M2.5 thread-forming screws
TRIG_SLED_T = 2.5
TRIG_TALL = 9.5                              # tallest part above the PCB (the screw terminal)
# Magnet pairs: a 6x2 mm disc in the tub and a 6x1 mm disc in the grille ring at each position.
MAG_D = 6.4                                  # pocket diameter for 6 mm discs
MAG_T_TUB, MAG_T_FRAME = 2.0, 1.0            # magnet thicknesses
MAG_GLUE = 0.2                               # tub magnet sits this far below the surface
RING_GAP = 0.35                              # clearance between the grille ring and the tub recess
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

# Prints floor down. The band overhangs the recess, so its underside is a 45 deg chamfer instead of a
# flat ledge; the ring and shell tops are beveled to match. The bottom outer edge is chamfered too.
CH_Z = REC_Z1 - BAND_CHAMFER
tub = (M.batch_hull([extrude(inset.offset(-FOOT_CHAMFER, m3.JoinType.Round), 0, 0.01), extrude(inset, FOOT_CHAMFER, CH_Z)])
       + M.batch_hull([extrude(inset, CH_Z - 0.01, CH_Z), extrude(outline, REC_Z1, TUB_H)]))
tub = tub - extrude(inner, FLOOR, TUB_H + 1)

# full range sub chambers (one per side)
for s in (-1, 1):
    xw0, xw1 = sorted((s * FR_CH_X0, s * (FR_CH_X0 + CHAMBER_WALL)))
    tub = tub + box(xw0, xw1, IY0 - 1, FR_CH_Y1, FLOOR - 1, TUB_H)
    xb0, xb1 = sorted((s * FR_CH_X0, s * (IX + 1)))
    tub = tub + box(xb0, xb1, FR_CH_Y1 - CHAMBER_WALL, FR_CH_Y1, FLOOR - 1, TUB_H)

# brace columns, which also take the lid locating pins. Each one is webbed out to the side wall, so
# none stands free and the front ones leave no thin slot against the curved corner wall.
# (+-139, 100) overlaps the side wall by 1 mm. At 138 the column only touched the wall along a line,
# which made the mesh non-manifold.
BOSSES = [(-135, 22), (135, 22), (-139, 100), (139, 100), (-130, 128), (130, 128)]
for (x, y) in BOSSES:
    col = M.batch_hull([cyl_z(x, y, FLOOR - 1, TUB_H, 10), cyl_z(math.copysign(IX + 1, x), y, FLOOR - 1, TUB_H, 10)])
    tub = tub + (col ^ extrude(inner.offset(1, m3.JoinType.Round), 0, TUB_H))
for (x, y) in BOSSES:
    tub = tub - cyl_z(x, y, TUB_H - 4, TUB_H + 1, 4.3)

# Driver mounts. Each driver sits in a recessed well deep enough that its surround clears the fabric
# by cover_clear, on a mounting ring that thickens the baffle behind it for the screws.
def frame_outline(d, grow=0.0):
    ears = [CS.circle(d["ear_r"] + grow, 48).translate([d["ear_c"] * math.cos(math.radians(a)),
                                                        d["ear_c"] * math.sin(math.radians(a))])
            for a in (45, 135, 225, 315)]
    return CS.batch_hull([CS.circle(d["body_r"] + grow, SEG)] + ears)

def prism_y(cs, x, z, y0, y1):
    """extrude an X-Z profile (drawn in X-Y) along +Y from y0 to y1, centered at (x, z).
    Profile +y ends up as -Z."""
    return cs.extrude(y1 - y0).rotate([-90, 0, 0]).translate([x, y0, z])

def teardrop_down(d, grow):
    """Frame outline with a 45 deg V below it, so the underside of a mounting ring prints unsupported."""
    h = max(d["body_r"], d["ear_c"] + d["ear_r"]) + grow     # extent along the 45 deg diagonals
    return CS.batch_hull([frame_outline(d, grow), CS.circle(0.01, 4).translate([0, h * math.sqrt(2)])])

def teardrop_up(r):
    """Circle of radius r with 45 deg sides above it, capped flat at its own top (a bridge)."""
    tip = CS.batch_hull([CS.circle(r, SEG), CS.circle(0.01, 4).translate([0, -r * math.sqrt(2)])])
    return tip ^ CS.square([4 * r, 2 * r]).translate([-2 * r, -r])

INTERIOR = box(-IX, IX, IY0 - 1, IY1 + 1, FLOOR - 1, TUB_H)
SEATS = {}

def mount_driver(tub, name, x, z, rear=False):
    d = DRIVERS[name]
    sgn = 1 if rear else -1                                   # direction the driver faces, along Y
    cover_in = BD - (RECESS - RING_GAP) if rear else RECESS - RING_GAP   # inside face of ring / shell
    surface = BD - RECESS if rear else RECESS                 # recessed tub surface under the fabric
    seat = cover_in - sgn * (d["cover_clear"] + d["proud"] + GASKET_T)    # baffle face under the gasket
    back = seat - sgn * MOUNT_MEAT                            # back of the mounting ring
    SEATS[name + ("" if x >= 0 else "_l")] = seat
    # the ring runs from the baffle to the back of the mounting face, so the well gets solid walls
    baffle = BD - WALL_REAR + 1 if rear else IY0 - 1
    lo, hi = sorted((baffle, back))
    ring = prism_y(teardrop_down(d, 4.0), x, z, lo, hi) ^ INTERIOR
    tub = tub + ring
    # well: from the recessed surface down to the mounting face. Keep the skin above the fabric line.
    w0, w1 = sorted((surface - sgn * 0.3, seat))
    tub = tub - prism_y(frame_outline(d, d["well_clr"]), x, z, w0, w1)
    e0, e1 = sorted((surface + sgn * 1.0, surface - sgn * 0.3))
    tub = tub - (prism_y(frame_outline(d, d["well_clr"]), x, z, e0, e1) ^ box(-BW, BW, -10, BD + 10, -10, CH_Z - 0.01))
    # cutout through the ring (45 deg sides and a flat top, so it bridges), plus the solder-tab relief
    # on the top side. The notch floor sits below where its sides meet the cutout, so no sliver is left.
    c0, c1 = sorted((seat + sgn * 1.0, back - sgn * 5.0))
    tub = tub - prism_y(teardrop_up(d["cut"] / 2), x, z, c0, c1)
    if d["tab_notch"]:
        hw, reach, depth = d["tab_notch"]
        n0, n1 = sorted((seat - sgn * depth, back - sgn * 5.0))
        tub = tub - box(x - hw, x + hw, n0, n1, z + math.sqrt((d["cut"] / 2) ** 2 - hw ** 2) - 0.5, z + reach)
    # blind pilot holes on the bolt circle
    for k in range(4):
        a = math.radians(45 + 90 * k)
        px, pz = x + d["bc"] / 2 * math.cos(a), z + d["bc"] / 2 * math.sin(a)
        p0, p1 = sorted((seat + sgn * 0.5, seat - sgn * PILOT_DEPTH))
        tub = tub - cyl_y(px, pz, p0, p1, PILOT_D)
    return tub

tub = mount_driver(tub, "nd65", -FR_X, DRV_Z)
tub = mount_driver(tub, "nd65", FR_X, DRV_Z)
tub = mount_driver(tub, "nd105", 0, WOOF_Z)
tub = mount_driver(tub, "nd105pr", 0, WOOF_Z, rear=True)

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
LID_FOOT = 0.4                             # bottom outer edge chamfer: hides elephant's foot at the joint with the tub
lid = M.batch_hull([extrude(outline.offset(-LID_FOOT, m3.JoinType.Round), LID_Z0, LID_Z0 + 0.01),
                    extrude(outline, LID_Z0 + LID_FOOT, TOPZ - CH), extrude(outline.offset(-CH, m3.JoinType.Round), TOPZ - CH, TOPZ)])
# 4 mm dowel holes (dowels align lid to tub for gluing). 4 mm deep in the tub + 2.8 mm here = 6.8 mm for 6 mm
# dowels, so a short hole can't hold the lid off the tub.
LID_DOWEL_DEPTH = 2.8
for (x, y) in BOSSES:
    lid = lid - cyl_z(x, y, LID_Z0 - 1, LID_Z0 + LID_DOWEL_DEPTH, 4.3)
# Speaker wire hole into the woofer chamber, at the bottom of the spine's cable channel. Sized for three
# 20 AWG zip-cord pairs (about 2 x 4 mm each) and hot-glued shut around them: any gap here acts as a port.
WIRE_HOLE = (0, 74)
WIRE_HOLE_D = 8.0
lid = lid - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], LID_Z0 - 1, TOPZ + 1, WIRE_HOLE_D)

# Power cable clip on the lid behind the spine: the USB-C cable drops from the plug onto the lid and runs
# back through it to the rear edge. Two posts with small 45 deg hooks; pushing the cable in flexes them
# about 0.3 mm each (1.2 mm PLA posts stay well under yield). Measure your cable and set CABLE_D.
CABLE_D = 4.5                              # USB-C cable outer diameter
CLIP_Y, CLIP_L = 132.0, 10.0               # start (Y) and length of the clip, clear of the plug's strain relief
CLIP_POST, CLIP_HOOK = 1.2, 0.4            # post thickness, hook reach
def clip_post(side):
    g = (CABLE_D + 0.2) / 2                # inner face of the post
    za = TOPZ + CABLE_D + 0.2              # hook starts just above the cable
    pts = [(g, TOPZ - 0.5), (g + CLIP_POST, TOPZ - 0.5), (g + CLIP_POST, za + 2 * CLIP_HOOK),
           (g, za + 2 * CLIP_HOOK), (g - CLIP_HOOK, za + CLIP_HOOK), (g, za)]
    pts = [(side * x, -z) for x, z in pts] # prism_y maps profile +y to -Z
    if side > 0:                           # one flip (z) leaves the winding clockwise; mirroring x too undoes it
        pts.reverse()
    return prism_y(CS([pts]), 0, 0, CLIP_Y, CLIP_Y + CLIP_L)
cable_clip = clip_post(1) + clip_post(-1)
lid = lid + cable_clip

# ======================= GRILLE RING =======================
frame_outer = inset.offset(RECESS - FABRIC, m3.JoinType.Round)
GZ0, GZ1 = 0.5, REC_Z1 - 0.5
def bore(z0):
    """Inside of the ring / shell, with the LEAD_IN chamfer at its bottom edge z0."""
    i = inset.offset(RING_GAP, m3.JoinType.Round)
    return extrude(i, -1, 200) + M.batch_hull([extrude(inset.offset(RING_GAP + LEAD_IN + 1, m3.JoinType.Round), z0 - 1.01, z0 - 1),
                                               extrude(i, z0 + LEAD_IN, z0 + LEAD_IN + 0.01)])
gf = extrude(frame_outer, GZ0, GZ1) - bore(GZ0)
WZ0, WZ1 = 18.0, GZ1 - 14.0
FW = 150 - R_FRONT - 2      # flat part of front face
win = box(-FW, -60.5, -20, 40, WZ0, WZ1) + box(-55.5, 55.5, -20, 40, WZ0, WZ1) + box(60.5, FW, -20, 40, WZ0, WZ1)
win = win + box(-200, -120, 32, BD - 20, WZ0, WZ1) + box(120, 200, 32, BD - 20, WZ0, WZ1)
RW = 150 - R_REAR - 4
win = win + box(-RW, -66, BD - 40, BD + 20, WZ0, WZ1) + box(-58, 58, BD - 40, BD + 20, WZ0, WZ1) + box(66, RW, BD - 40, BD + 20, WZ0, WZ1)
gf = gf - win
for c in mag_cuts(MAG_TUB, MAG_FRAME, True):
    gf = gf - c

def top_bevel(gap, outer):
    """Everything the ring / shell must stay out of under the band: the band chamfer lowered by gap,
    and above a flat land of TOP_LAND in from the part's outer face (outer = its offset from outline)."""
    def zc(o):
        return REC_Z1 - gap + o
    cham = M.batch_hull([extrude(outline.offset(-6, m3.JoinType.Round), zc(-6) - 0.01, zc(-6)),
                         extrude(outline.offset(3, m3.JoinType.Round), zc(3), zc(3) + 0.01)])
    return cham + extrude(outline.offset(3, m3.JoinType.Round), zc(outer - TOP_LAND), 300)

gf = gf - top_bevel(REC_Z1 - GZ1, -FABRIC)
fabric = extrude(outline, GZ0, GZ1) - extrude(inset, -1, 200) - top_bevel(REC_Z1 - GZ1, 0)

# ======================= GRILLE SHELL (fabric-free alternative) =======================
# Flush with the tub's top band on the outside, same inner clearance and magnet pockets as the ring.
SZ0, SZ1 = GZ0, REC_Z1 - SHELL_TOP_GAP
shell = M.batch_hull([extrude(outline.offset(-SHELL_FOOT, m3.JoinType.Round), SZ0, SZ0 + 0.01),
                      extrude(outline, SZ0 + SHELL_FOOT, SZ1)]) - bore(SZ0)
for c in mag_cuts(MAG_TUB, MAG_FRAME, True):
    shell = shell - c
shell = shell - top_bevel(SHELL_TOP_GAP, 0)

def hex_field(u0, u1, z0, z1, place_hole):
    """Honeycomb hole centers inside a rounded rectangle (u = along the face, z = height)."""
    pitch = SHELL_HEX + SHELL_WEB
    row = pitch * math.sqrt(3) / 2
    field = rrect(u0, u1, z0, z1, SHELL_FIELD_R, SHELL_FIELD_R)
    r_hex = SHELL_HEX / math.sqrt(3)           # circumradius of the hexagon
    holes = []
    nrows = int((z1 - z0) / row) + 1
    zc0 = (z0 + z1) / 2 - (nrows - 1) * row / 2
    for i in range(nrows):
        z = zc0 + i * row
        off = pitch / 2 if i % 2 else 0.0
        ncols = int((u1 - u0) / pitch) + 2
        uc0 = (u0 + u1) / 2 - (ncols - 1) * pitch / 2 + off
        for j in range(ncols):
            u = uc0 + j * pitch
            # keep holes whose whole hexagon sits inside the field
            probe = CS.circle(r_hex, 6).translate([u, z])
            if (probe - field).area() < 1e-6:
                holes.append(place_hole(u, z, r_hex))
    return holes

def hex_hole_y(x, z, r, y0, y1):
    # 6-sided cylinder along Y with a vertex pointing up (rotated 30 deg about its own axis)
    return M.cylinder(y1 - y0, r, r, 6).rotate([0, 0, 30]).rotate([-90, 0, 0]).translate([x, y0, z])

def hex_hole_x(y, z, r, x0, x1):
    return M.cylinder(x1 - x0, r, r, 6).rotate([0, 0, 30]).rotate([0, 90, 0]).translate([x0, y, z])

FRONT_FLAT = BW / 2 - R_FRONT - 4.0
REAR_FLAT = BW / 2 - R_REAR - 4.0
SIDE_FLAT = (R_FRONT + 4.0, BD - R_REAR - 4.0)
holes = hex_field(-FRONT_FLAT, FRONT_FLAT, *SHELL_Z, lambda u, z, r: hex_hole_y(u, z, r, -1, RECESS + 1))
holes += hex_field(-REAR_FLAT, REAR_FLAT, *SHELL_Z, lambda u, z, r: hex_hole_y(u, z, r, BD - RECESS - 1, BD + 1))
if SHELL_SIDES:
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (BW / 2 + 1), sx * (BW / 2 - RECESS - 1)))
        holes += hex_field(*SIDE_FLAT, *SHELL_Z, lambda u, z, r, x0=x0, x1=x1: hex_hole_x(u, z, r, x0, x1))
shell = shell - union(holes)

# ======================= BEZEL (built in local frame) =======================
# local: x = X, y = a (depth, 0 at front face, + backward), z = h (up the face, 0 at bottom edge)
PW, PH = TAB_W + 2 * TAB_CLR, TAB_H + 2 * TAB_CLR
EW, EH = PW + 2 * FRAME_SIDE, PH + 2 * FRAME + CHIN
assert USB_CLEAR <= FRAME_SIDE - TRAY_WALL - 0.4 + 1e-6, "USB_CLEAR needs a wider FRAME_SIDE"
ER = BEZEL_R
T_FRONT = LIP + POCKET_D
T = T_FRONT + TRAY_D
HC = EH / 2
TAB_CZ = FRAME + CHIN + PH / 2               # tablet center height in the bezel

def rr_xz(w, h, r, a0, a1, cx=0.0, cz=HC):
    """rounded rect in the X-Z plane, extruded along local depth a0..a1"""
    cs = rrect(-w/2, w/2, -h/2, h/2, r, r)
    return cs.extrude(a1 - a0).rotate([90, 0, 0]).translate([cx, a1, cz])  # rotate: z->-y, so shift

def rounded_slab(w, h, r, a0, a1, f0=0.0, f1=0.0, bed=None, n=12, cz=HC):
    """Rounded-rect slab from depth a0 to a1 with a round-over of radius f0 on the a0 edge and f1 on
    the a1 edge. bed = "a0" or "a1" marks the edge on the print bed: its curve stops at 45 deg and
    finishes as a 45 deg chamfer. The outline is convex, so the hull of thin slices is exact."""
    slices = []
    def sl(inset, a):
        slices.append(rr_xz(w - 2 * inset, h - 2 * inset, max(r - inset, 0.5), a - 0.005, a + 0.005, cz=cz))
    for f, a_face, sgn, side in ((f0, a0, +1, "a0"), (f1, a1, -1, "a1")):
        if f <= 0:
            sl(0.0, a_face + sgn * 0.005)
            continue
        phis = [math.pi / 2 * k / n for k in range(n + 1)]   # 0 = where it meets the side wall, 90 = face
        if bed == side:
            phis = [p for p in phis if p <= math.pi / 4]     # keep the wall half; the face half overhangs
            sl(2 * f * (1 - math.cos(math.pi / 4)), a_face + sgn * 0.005)      # 45 deg chamfer to the face
        for p in phis:
            sl(f * (1 - math.cos(p)), a_face + sgn * f * (1 - math.sin(p)))
    return M.batch_hull(slices)

def lcyl_a(x, z, a0, a1, d):
    return M.cylinder(a1 - a0, d/2, d/2, SEG).rotate([-90, 0, 0]).translate([x, a0, z])

def lbox(x0, x1, a0, a1, z0, z1):
    return box(x0, x1, a0, a1, z0, z1)

# --- bezel body: front rim, tablet pocket and tray in one piece, later split at the top of the chin
CHIN_TOP = FRAME + CHIN                      # pocket bottom; the shell / chin split
WIN_W, WIN_H = PW - 2 * LIP_OVERLAP, PH - 2 * LIP_OVERLAP
WIN_R = TAB_R + TAB_CLR - LIP_OVERLAP
assert FRAME_SIDE >= USB_CLEAR + TRAY_WALL + 0.4 - 1e-6, "FRAME_SIDE too thin for USB_CLEAR"
# Prints back down: the front edge is on top, so it gets a full round-over; the back edge is on the bed.
body_outer = rounded_slab(EW, EH, ER, 0, T, f0=BEZEL_FRONT_FILLET, f1=BEZEL_BACK_FILLET, bed="a1")
tray_outer = body_outer
# The rim is wider than the tray wall, so where they meet the tray's inside tapers at 45 deg instead
# of leaving a flat 4.4 mm ledge, which would overhang when printing back down.
RIM_STEP = FRAME_SIDE - TRAY_WALL
tray_inner = M.batch_hull([
    rounded_slab(EW - 2*TRAY_WALL, EH - 2*TRAY_WALL, ER - TRAY_WALL, T_FRONT + RIM_STEP, T - TRAY_WALL,
                 f1=BEZEL_BACK_FILLET - TRAY_WALL),
    rr_xz(PW - 0.1, (TAB_CZ + PH / 2) - TRAY_WALL - 0.05, TAB_R + TAB_CLR - 0.05, T_FRONT - 0.01, T_FRONT,
          cz=(TAB_CZ + PH / 2 + TRAY_WALL) / 2 - 0.025)])   # 0.05 inside the pocket outline: no coincident arcs
c = WINDOW_CHAMFER
window = M.batch_hull([rr_xz(WIN_W + 2*c, WIN_H + 2*c, WIN_R + c, -1, 0.0, cz=TAB_CZ),
                       rr_xz(WIN_W, WIN_H, WIN_R, c, LIP + 0.01, cz=TAB_CZ)])
pocket = rr_xz(PW, PH, TAB_R + TAB_CLR, LIP, T_FRONT + 0.01, cz=TAB_CZ)
# Square below the tablet's center, so its corners slide past on the way in; the lip hides the gaps.
# Cut from the shell only, after the split, so the chin's top stays flat at CHIN_TOP.
pocket_ext = lbox(-PW / 2 - 0.01, PW / 2 + 0.01, LIP, T_FRONT + 0.01, CHIN_TOP - 1, TAB_CZ)
tr = body_outer - window - pocket - tray_inner
# mic slots through the top rim into the pocket
for x in (-60, -20, 20, 60):
    tr = tr - lbox(x - 6, x + 6, LIP + 2.6, LIP + 5.6, TAB_CZ + PH / 2 - 1, EH + 1)   # behind the front round-over
# USB-C: room for a flat FPC 90 deg plug beside the port. It runs down to the bottom of the pocket,
# because the tablet slides in from below with the plug already in.
ux0, ux1 = sorted((USB_SIDE * PW/2 - USB_SIDE * 1, USB_SIDE * (PW/2 + USB_CLEAR)))
usb_channel = lbox(ux0, ux1, LIP + 1.0, T_FRONT + 1, CHIN_TOP - 1, TAB_CZ + USB_NOTCH_H / 2)   # cut after the split
# mmWave radar pocket in the chin, open to the tray; the radar looks out through RADAR_LIP of plastic
RADAR_Z = CHIN_TOP / 2
tr = tr - lbox(-RADAR_W / 2, RADAR_W / 2, RADAR_LIP, T_FRONT + 1, RADAR_Z - RADAR_H / 2, RADAR_Z + RADAR_H / 2)
if LABELS:   # on the back of the chin, beside the radar pocket (read from the tray side)
    tr = tr + bezel_label("LD2410C", 0.0, RADAR_Z + 2.0, T - TRAY_WALL, -1)     # on the back wall, behind the radar
BACK_IN = T - TRAY_WALL
# tablet back-stop posts (0.5 mm felt on the tips, so the tablet slides in)
for x in (-115, 0, 115):
    for z in (40, EH - 40):
        tr = tr + lcyl_a(x, z, T_FRONT, T - 0.01, 8.0)
# KABD-430 standoffs, 2.6 mm pilots for M3 thread-forming screws (the board's holes are 3.6 mm)
JX, JZ = -70.0, HC
for dx in (-AMP_HOLES[0] / 2, AMP_HOLES[0] / 2):
    for dz in (-AMP_HOLES[1] / 2, AMP_HOLES[1] / 2):
        tr = tr + lcyl_a(JX + dx, JZ + dz, T - TRAY_WALL - AMP_STANDOFF, T - 0.01, 7.0)
        tr = tr - lcyl_a(JX + dx, JZ + dz, T - TRAY_WALL - AMP_STANDOFF - 1, T - 1.0, 2.6)
# cradles for the small boards, standing off the inside of the back wall
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
    tr = tr + bezel_label("KABD-430 AMP", JX, JZ + 34.3 + LABEL_GAP + 3.5 + LABEL_SIZE * 0.4, BACK_IN, -1)
    tr = tr + bezel_label("USB-C FPC", USB_SIDE * (PW / 2 - 4.0), TAB_CZ, BACK_IN, -1, angle=90 * USB_SIDE)
# bosses for the spine bolts: inserts pressed in from the back face, bolts come from the spine's rear
for (x, z) in SPINE_PTS:
    tr = tr + lcyl_a(x, z, BACK_IN - 7.0, T - 0.01, 8.0)
    tr = tr - lcyl_a(x, z, T - INSERT_DEPTH, T + 1, M3_INSERT)
# chin screw bosses: vertical columns against the back wall, split with the body below
# chin bar screw bosses: through the tray depth, head counterbores from the back face
CHIN_SCREW_Z = CHIN_TOP / 2 + 0.5       # off the line where the inner floor round-over meets the back wall
for x in CHIN_SCREW_X:
    tr = tr + (lcyl_a(x, CHIN_SCREW_Z, T_FRONT + 0.5, T - 0.01, 9.0) ^ body_outer)
# vents in the back wall, kept clear of the chin bosses
for i in range(9):
    x = -112 + i * 28
    if abs(x) < 40:
        continue
    tr = tr - lbox(x - 2, x + 2, T - TRAY_WALL - 1, T + 1, CHIN_TOP + 3, CHIN_TOP + 13)
for i in range(16):
    x = -112 + i * 15
    tr = tr - lbox(x - 2, x + 2, T - TRAY_WALL - 1, T + 1, EH - 37, EH - 15)
CH_H = 60.0                                     # cable channel enters tray here
tr = tr - lcyl_a(0, CH_H, T - TRAY_WALL - 1, T + 1, 13)
# split: shell above the top of the chin, chin cap below it
# Split: the chin is the solid bar in front of the tray below the tablet, plus the strip of lip along
# the bottom of the glass (so that strip sits on solid plastic instead of spanning 255 mm on its own).
# The tablet slides up through the bar's slot before the bar goes in.
chin_region = lbox(-EW, EW, -10, T_FRONT, -10, CHIN_TOP) + \
              lbox(-PW / 2, PW / 2, -10, LIP, CHIN_TOP - 1, CHIN_TOP + LIP_OVERLAP + TAB_CLR + 0.5)
chin = tr ^ chin_region
tr = tr - chin_region - pocket_ext - usb_channel
head_a = T_FRONT + (CHIN_SCREW_LEN - 5.0)    # where the screw head seats
for x in CHIN_SCREW_X:
    chin = chin - lcyl_a(x, CHIN_SCREW_Z, T_FRONT - INSERT_DEPTH, T_FRONT + 1, M3_INSERT)    # insert in the bar's back
    tr = tr - lcyl_a(x, CHIN_SCREW_Z, T_FRONT - 1, T + 1, M3_CLR) - lcyl_a(x, CHIN_SCREW_Z, head_a, T + 1, 6.2)

# --- place bezel in world
st, ct = math.sin(math.radians(TILT)), math.cos(math.radians(TILT))
Z0 = LID_Z0 + LID_T + BEZ_GAP + T * st
def place(part):
    return part.rotate([-TILT, 0, 0]).translate([0, BEZ_Y0, Z0])
def to_world(x, a, h):
    return np.array([x, BEZ_Y0 + a * ct + h * st, Z0 - a * st + h * ct])
bezel_shell_w, bezel_chin_w = place(tr), place(chin)

# ======================= SPINE =======================
bp0 = to_world(0, T, 0)              # bottom of tray back face
HS = 115.0
bps = to_world(0, T, HS)
Yb0 = bp0[1]
REAR_Y = Yb0 + 50
REAR_FACE_H = max(8.0, PWR_Z + PWR_PLATE_H / 2 + 3.0)    # flat rear face tall enough for the power plate
bpt = to_world(0, T + SPINE_TOP, HS)       # back of the flat top
prof = CS([[(Yb0 - 6, TOPZ), (REAR_Y - 0.6, TOPZ), (REAR_Y - 0.6, TOPZ + REAR_FACE_H), (bpt[1], bpt[2]), (bps[1], bps[2]),
            (bp0[1], bp0[2]), (Yb0 - 6, bp0[2])]])
SW = 60.0
spine = prof.extrude(SW).rotate([90, 0, 90]).translate([-SW/2, 0, 0])   # profile (Y,Z) extruded along X
spine = spine.translate([0, 0, -0.5])     # sink 0.5 mm into the lid so they fuse
# bolt holes for the bezel, drilled along the bezel normal from the spine's rear, with head counterbores
for (x, h) in SPINE_PTS:
    spine = spine - place(lcyl_a(x, h, T - 0.5, T + 120, M3_CLR)) - place(lcyl_a(x, h, T + SPINE_GRIP, T + 160, 6.4))
# cable channel: hull of two spheres, lid hole -> tray. The low sphere dips only 1 mm into the lid, so the
# lid stays closed around the wire hole.
p_low = np.array([0, WIRE_HOLE[1], TOPZ + 5])
p_high = to_world(0, T - 6, CH_H)
chan = M.batch_hull([M.sphere(6, 48).translate(p_low.tolist()), M.sphere(6, 48).translate(p_high.tolist())])
spine = spine - chan
# USB-C power: flush pocket for the plate, cavity for the PD trigger on its sled, inserts for the plate
def plate_cs(w, h, r):
    return rrect(-w/2, w/2, -h/2, h/2, r, r)
def along_y(cs, y0, y1, z):
    """extrude an X-Z profile (drawn as X-Y) along +Y from y0 to y1, centered at height z"""
    return cs.extrude(y1 - y0).rotate([-90, 0, 0]).translate([0, y0, z])
REAR_FACE = REAR_Y - 0.6
PWR_ZW = TOPZ + PWR_Z
POCKET_FLOOR = REAR_FACE - PWR_PLATE_T

# Power plate, built face down: z = 0 is the outside face, +z goes into the spine, +y is up.
# Trigger board in plate coordinates: socket mouth at the plate's back face, PCB horizontal, parts up.
pcb_bot = -TRIG_T / 2 - TRIG_USB_OFFSET                     # socket center at y = 0
edge_z = PWR_PLATE_T + TRIG_USB_OVERHANG                     # z of the PCB's USB edge
def board_xz(bx, by):
    return bx - TRIG_W / 2, edge_z + (TRIG_L - by)
sled_top = pcb_bot - TRIG_PAD_H
sled_end = edge_z + TRIG_L + 1.0
pp = plate_cs(PWR_PLATE_W, PWR_PLATE_H, PWR_PLATE_R).extrude(PWR_PLATE_T)
ow, oh, orr = PWR_OPENING
c = PWR_OPENING_CHAMFER
opening = M.batch_hull([plate_cs(ow + 2*c, oh + 2*c, orr + c).extrude(0.01).translate([0, 0, -0.01]),
                        plate_cs(ow, oh, orr).extrude(PWR_PLATE_T + 1).translate([0, 0, c])])
pp = pp - opening - plate_cs(ow, oh, orr).extrude(PWR_PLATE_T + 2).translate([0, 0, -1])
for sx in (-PWR_SCREW_X, PWR_SCREW_X):
    pp = pp - cyl_z(sx, 0, -1, PWR_PLATE_T + 1, M3_CLR)
    pp = pp - M.cylinder(1.7, 3.4, M3_CLR / 2, SEG).translate([sx, 0, -0.01])   # 90 deg countersink
# sled under the board, pads under its four mounting holes, reliefs under the socket shell and terminal pins
sled = box(-TRIG_W / 2 - 0.7, TRIG_W / 2 + 0.7, sled_top - TRIG_SLED_T, sled_top, PWR_PLATE_T - 0.01, sled_end)
sled = sled - box(-5.3, 5.3, sled_top - 1.2, sled_top + 1, PWR_PLATE_T - 1, edge_z + 8.0)          # socket shell
tx0, tz0 = board_xz(8.46 - 2.2, 3.81 + 2.5); tx1, tz1 = board_xz(11.86 + 2.2, 3.81 - 2.5)
sled = sled - box(tx0, tx1, sled_top - 1.2, sled_top + 1, tz0, tz1)                              # terminal pins
for bx, by in TRIG_HOLES:
    x, z = board_xz(bx, by)
    sled = sled + box(x - TRIG_PAD/2, x + TRIG_PAD/2, sled_top - 0.01, pcb_bot, z - TRIG_PAD/2, z + TRIG_PAD/2)
    sled = sled - M.cylinder(20, TRIG_PILOT/2, TRIG_PILOT/2, 24).rotate([90, 0, 0]).translate([x, pcb_bot + 1, z])
pwr_plate = pp + sled
pwr_plate_w = pwr_plate.rotate([90, 0, 0]).translate([0, REAR_FACE, PWR_ZW])

# spine pocket, cavity and inserts
spine = spine - along_y(plate_cs(PWR_PLATE_W + 2 * PWR_PLATE_CLR, PWR_PLATE_H + 2 * PWR_PLATE_CLR, PWR_PLATE_R + PWR_PLATE_CLR),
                        POCKET_FLOOR, REAR_FACE + 1, PWR_ZW)
cav_y0 = REAR_FACE - sled_end - 6.0                          # room behind the board for the output wires
cav = box(-TRIG_W / 2 - 2.2, TRIG_W / 2 + 2.2, cav_y0, POCKET_FLOOR + 0.01,
          PWR_ZW + sled_top - TRIG_SLED_T - 1.5, PWR_ZW + pcb_bot + TRIG_T + TRIG_TALL + 1.5)
spine = spine - cav                                          # opens into the cable channel
for sx in (-PWR_SCREW_X, PWR_SCREW_X):
    spine = spine - cyl_y(sx, PWR_ZW, POCKET_FLOOR - INSERT_DEPTH, POCKET_FLOOR + 0.01, M3_INSERT)
# don't let the spine poke into the tray
spine = spine - place(rounded_slab(EW, EH, ER, -1, T + SPINE_CLR, f1=BEZEL_BACK_FILLET, bed="a1"))   # hugs the curved tray back
lid_spine = lid + spine
# the hole runs straight up into the channel's low sphere, so the full 8 mm reaches the channel. Above the lid
# the throat is a straight 12 mm bore, so the trigger cavity floor doesn't leave a thin lip over the sphere.
lid_spine = lid_spine - chan - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], LID_Z0 - 1, p_low[2], WIRE_HOLE_D) \
            - cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], TOPZ, p_low[2] + 7, 12)

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
    "base_tub": tub, "lid_spine": lid_spine, "grille_ring": gf, "grille_shell": shell,
    "bezel_shell": bezel_shell_w, "bezel_chin": bezel_chin_w, "power_plate": pwr_plate_w,
}
meshes = {k: export(v, k) for k, v in parts_world.items()}
export(fabric, "_render_fabric")
# tablet placeholder for renders: glass face at the back of the lip
tablet = place(rr_xz(TAB_W, TAB_H, TAB_R, LIP + 0.05, LIP + TAB_T, cz=TAB_CZ))
export(tablet, "_render_tablet")
# lit screen area for renders: the 11 in 16:10 active area, centered on the glass
screen = place(rr_xz(236.9, 148.1, 1.0, LIP + 0.0, LIP + 0.06, cz=TAB_CZ))
export(screen, "_render_screen")
# print-ready orientations
export(tr.rotate([-90, 0, 0]).translate([0, 0, T]), "print_bezel_shell")            # back wall down, front rim on top
export(chin.rotate([-90, 0, 0]).translate([0, 0, T_FRONT]), "print_bezel_chin")     # back wall down
export(gf.translate([0, 0, -GZ0]), "print_grille_ring")         # bottom edge down, beveled top up
export(shell.translate([0, 0, -SZ0]), "print_grille_shell")     # bottom edge down, beveled top up
export(lid_spine.translate([0, 0, -LID_Z0]), "print_lid_spine")
export(tub, "print_base_tub")
export(pwr_plate, "print_power_plate")                         # outside face down, sled standing up

# acoustic volumes: air inside the closed tub (lid on), by chamber. Driver bodies are not subtracted.
air = extrude(inner, FLOOR, TUB_H) - tub - union(PASS_THROUGHS)   # pass-throughs hot-glued shut
chambers = sorted((c.volume() / 1e6 for c in air.decompose()), reverse=True)
print("chamber air volumes (L, driver bodies not subtracted):", [round(v, 3) for v in chambers[:3]])
# The volumes above assume a closed lid. Anything open through the lid over the chambers leaks; only the
# wire hole should show here, and it gets glued shut. Sampled between the dowel holes and the channel's dip.
lid_open = (extrude(inner, LID_Z0 + LID_DOWEL_DEPTH + 0.05, LID_Z0 + LID_DOWEL_DEPTH + 0.15) - lid_spine).volume() / 0.1
print(f"open area through the lid: {lid_open:.1f} mm2 (the {WIRE_HOLE_D:.0f} mm wire hole is "
      f"{math.pi * WIRE_HOLE_D ** 2 / 4:.1f} mm2; hot-glue it shut)")
print("mounting faces (Y):", {k: round(v, 1) for k, v in SEATS.items()})
print("bezel thickness", T, "bezel outer", EW, EH, "Z0", Z0, "top Z", to_world(0, 0, EH)[2], "top-back", to_world(0, T, EH))
print("lowest bezel corner Z", to_world(0, T, 0)[2], "Yb0", Yb0)
