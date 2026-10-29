"""
Hub Mini enclosure - parametric model (manifold3d)
A smaller sibling of the Counter Display: an 8.7 in Galaxy Tab A9 in a tilted frameless bezel on a
small single-driver speaker base. Sized to replace a Google Home / Nest Mini on a nightstand, desk
or shelf. Every part fits a 256 mm print bed.
Units: mm.  World axes: X = width, Y = depth (front face at Y=0, back is +Y), Z = up.

Parts exported (world position as <name>.stl, print orientation as print_<name>.stl):
  base_tub       sealed speaker box for one front-firing ND65, open top
  lid_spine      top plate (seals the box) printed in one piece with the tilted spine that joins it
                 to the bezel tray and carries the cable channel
  grille_shell   printed honeycomb grille skin, slides on from below, held by magnets
  bezel_shell    frameless bezel: thin rim around the tablet glass and the tray behind it, one piece.
                 Holds the mono amp, PD module, 5 V buck and ESP32-C3
  bezel_chin     chin bar below the tablet: the mmWave radar and the lip along the bottom of the glass.
                 Fills the slot the tablet slides in through, screwed in from the back of the tray
  power_plate    flush USB-C power plate with a sled for the PD trigger board, screws into the spine
  _render_tablet / _render_screen   placeholders, for renders only
Measure your tablet and driver and edit the PARAMETERS block before printing.

Usage:  python enclosure.py [out_dir]      (see requirements.txt)
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
# Base: one sealed box, about 0.9 L of air for a single ND65.
BW, BD = 170.0, 110.0          # outer width, depth
TUB_H, LID_T = 76.0, 4.0       # tub height, lid thickness (total base height 80)
R_FRONT, R_REAR = 20.0, 10.0   # plan view corner radii
WALL_SIDE, WALL_REAR, FLOOR = 7.0, 8.0, 4.0   # side wall leaves 1.8 mm behind the side magnet pockets
FRONT_INNER_Y = 12.0           # front baffle inner face (outer face at Y=0, recess to Y=3 -> 9 mm baffle)
RECESS = 3.0                   # the grille shell sits in this recess, flush with the top band
REC_Z1 = 74.0                  # recess runs from the counter up to here; a 2 mm band stays above it
# Grille shell: honeycomb of pointy-top hexagon holes (prints cleanly in a vertical wall), ~52% open.
SHELL_HEX = 2.6                # hole size across flats
SHELL_WEB = 1.0                # web between holes
SHELL_Z = (6.0, 70.0)          # perforated band on the front. No magnets on the front, so it runs tall
SHELL_FIELD_R = 8.0            # corner radius of each perforated field
SHELL_SIDES = False            # also perforate the side faces (decorative; the box is sealed)
SHELL_TOP_GAP = 0.3            # reveal line between the shell and the tub's top band
TOP_LAND = 0.6                 # flat strip on the shell's outer top edge, under the band chamfer
BAND_CHAMFER = RECESS          # 45 deg chamfer under the top band (the band overhangs the recess by RECESS)
FOOT_CHAMFER = 0.6             # 45 deg chamfer on the tub's bottom outer edge (elephant foot, eases the shell on)

# Driver, from Dayton's spec sheet and the ND65 3D model (same numbers as the Counter Display).
# Its frame is a round body with four mounting ears on the diagonals:
#   body_r     radius of the round part of the frame
#   ear_c, ear_r   ear tip modeled as a circle of radius ear_r centered ear_c from the axis
#   flange_t   frame flange thickness
#   proud      how far the surround stands in front of the mounting face, at rest
#   cut        baffle cutout
#   tab_notch  (half width, reach from the axis, depth behind the mounting face where it starts):
#              relief on the top side for the solder tabs
#   bc         screw bolt circle (4 x 4.2 mm holes at 45 deg)
#   cover_clear    gap from the surround (at rest) to the inner face of the grille shell, for excursion
#   well_clr   clearance around the frame in its recess
DRIVERS = {
    # ND65-4: 64 mm frame, 52 mm cutout, 48 mm deep (43 behind the mounting face), Xmax 3.5 mm.
    # The solder tabs reach 27 mm from the axis within +-15.7 mm, from 2.4 mm behind the flange (1.4 mm
    # behind the seat, with the gasket under the flange).
    "nd65": dict(body_r=32.45, ear_c=34.5, ear_r=3.4, flange_t=1.0, proud=4.1, cut=52.6, tab_notch=(16.5, 28.0, 1.2),
                 bc=66.0, cover_clear=4.0, well_clr=0.5),
}
DRIVER = "nd65"
DRV_X = 0.0                            # driver centered on the front
# Driver center height. Below the middle of the box, so its well stays under the band chamfer, which
# starts at REC_Z1 - BAND_CHAMFER = 71: the driver has to pass under it on the way in.
DRV_Z = 37.0
MOUNT_MEAT = 7.0                       # baffle material behind the mounting face, for the screws
GASKET_T = 1.0                         # foam gasket under the flange (compressed); the seat sits this much deeper
PILOT_D = 2.5                          # blind pilots for M3 thread-forming or #4 screws
PILOT_DEPTH = 6.0

# Tablet: Galaxy Tab A9 8.7 in (SM-X110 / X115): 211.0 x 124.7 x 8.0. Corner radius is an estimate;
# measure yours. It has a 3.5 mm headphone jack, so audio leaves through the jack and the USB-C port
# only charges.
TAB_W, TAB_H, TAB_T, TAB_R = 211.0, 124.7, 8.0, 8.0
TAB_CLR = 0.4
# Frameless front: the tablet's own black glass border shows; a thin printed lip overlaps its edge.
LIP_OVERLAP = 1.5                            # how far the lip covers the tablet glass, per side
FRAME = 10.0                                 # rim width above the tablet (and part of the chin)
FRAME_SIDE = 10.0                            # rim width left and right; wide enough for the 3.5 mm plug
USB_CLEAR = 4.0                              # room past the USB-C edge for a flat FPC 90 deg adapter
JACK_CLEAR = 7.0                             # room past the jack edge for a slim 90 deg 3.5 mm plug
USB_SIDE = +1                                # +1 = USB-C at the right end seen from the front, -1 = left
JACK_SIDE = -USB_SIDE                        # the Tab A9 has the jack on the opposite short edge
USB_Z, JACK_Z = 0.0, 0.0                     # port center offset from the tablet's center, along the edge (+ = up)
USB_NOTCH_H, JACK_NOTCH_H = 22.0, 18.0       # height of the clearance channel around each port
CHIN = 11.0                                  # extra bottom border for the mmWave sensor (chin = FRAME + CHIN = 21)
RADAR_W, RADAR_H = 23.0, 17.0                # pocket for HLK-LD2410C (22 x 16 mm board)
LIP = 1.2                                    # lip in front of the glass
RADAR_LIP = 1.6                              # plastic in front of the radar
POCKET_D = TAB_T + 0.8                       # room for 0.5 mm felt pads on the back-stop posts
TRAY_WALL = 2.4
# Tray: no big amp any more, so it only has to clear the small boards stuck to its back wall.
PARTS_H = 13.0                               # tallest board in the tray, from the back wall (PD module)
TRAY_CLEAR = 1.0                             # gap between that board and the tablet back
TRAY_D = math.ceil(TRAY_WALL + PARTS_H + TRAY_CLEAR)
# Cradles on the inside of the tray back wall: (name, x, z, width, height, label, label side) of the
# board itself, in bezel coordinates (z from the bezel bottom edge). Low walls locate each part; VHB
# tape holds it. Set each size to the board you buy.
CRADLE_WALL, CRADLE_H, CRADLE_CLR = 1.6, 3.0, 0.4
CRADLES = [
    ("pd_module",  58.0, 102.0, 40.0, 25.0, "PD MODULE", "below"),   # 20 V -> USB-C PD output to the tablet
    ("amp",       -58.0, 106.0, 21.0, 18.0, "AMP",       "below"),   # Adafruit PAM8302 mono class D
    ("buck_5v",   -58.0,  64.0, 22.0, 17.0, "5V BUCK",   "below"),   # MP1584EN: ESP32, radar and amp
    ("esp32_c3",   58.0,  60.0, 22.5, 18.0, "ESP32-C3",  "below"),   # ESP32-C3 SuperMini
]
# Raised labels inside the bezel, one per component. They face up in both print orientations.
LABELS = True
LABEL_SIZE = 5.5                             # font size in mm; capitals come out about 4 mm tall
LABEL_RAISE = 0.6                            # height above the surface
LABEL_GAP = 1.5                              # space between a cradle wall and its label
LABEL_FONT = "DejaVu Sans"                   # bundled with matplotlib, so every machine gets the same STL
TILT = 20.0                                  # screen tilt back, degrees; it usually sits below eye level
# Bezel styling. Rounded edges are drawn as a quarter circle that turns into a 45 deg chamfer on the
# edge that sits on the print bed, so they print without sagging.
BEZEL_R = TAB_R + TAB_CLR + FRAME_SIDE       # corner radius in plan: an even rim around the tablet corners
BEZEL_FRONT_FILLET = 3.0                     # round-over on the front edge
BEZEL_BACK_FILLET = 6.0                      # round-over on the tray's back edge
WINDOW_CHAMFER = 0.5                         # 45 deg chamfer on the lip's inner edge
MIC_SLOTS_X = (-60.0, -20.0, 20.0, 60.0)     # slots through the top rim, for the tablet microphones
POSTS_X = (-92.0, 0.0, 92.0)                 # tablet back-stop posts, at POST_Z1 and EH - POST_Z1
POST_Z1 = 40.0
# Chin bar: 4 screws from the back of the tray, through bosses, into inserts in the bar's back face.
CHIN_SCREW_X = (-90.0, -40.0, 40.0, 90.0)   # clear of the radar pocket in the middle
CHIN_SCREW_LEN = 16.0                        # M3 x 16 (same as the spine bolts); ~5 mm goes into the insert
JACK_CABLE_NOTCH = (6.0, 7.0)                # cable notch in the chin bar below the jack channel:
                                             # (reach inward past the tablet edge, depth below the bar top)
# Bezel to spine: M3 bolts from the back of the spine into inserts in the tray's back wall.
SPINE_PTS = [(-16, 50), (16, 50), (-16, 80), (16, 80)]    # (x, height up the tray back), exit above the power plate
SPINE_GRIP = 12.0                            # spine material under the bolt heads -> M3 x 16 bolts
SPINE_W = 56.0                               # spine width
SPINE_HS = 110.0                             # spine reaches this far up the tray back
SPINE_REAR = 52.0                            # spine rear face, behind the bezel's lowest back corner
BEZ_Y0 = 8.0                                 # bezel bottom-front edge Y
BEZ_GAP = 4.0                                # air gap between lid and lowest bezel corner
CH_H = 60.0                                  # cable channel enters the tray here (height up the tray back)
WIRE_HOLE = (0.0, 55.0, 6.0)                 # speaker wire hole through the lid (x, y, d). Hot-glue it shut

# Hardware
M3_CLR, M3_INSERT, INSERT_DEPTH = 3.4, 4.0, 6.0
# Power input: USB-C PD, identical to the Counter Display. An Adafruit HUSB238 PD trigger (product 5991,
# set to 20 V on its DIP switch) screws to a sled on the back of a small printed plate. The plate sits
# flush in a pocket on the spine's rear face, held by two M3 countersunk screws in heat-set inserts.
# Board geometry is from Adafruit's PCB files: 20.32 x 27.81 mm, 2.5 mm holes, mid-mount USB-C socket
# overhanging the top edge by 1.14 mm.
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
# Magnet pairs: a 6x2 mm disc in the tub and a 6x1 mm disc in the grille shell at each position.
# Rear and sides only, so the front grille can run the full height of the driver.
MAG_D = 6.4                                  # pocket diameter for 6 mm discs
MAG_T_TUB, MAG_T_FRAME = 2.0, 1.0            # magnet thicknesses
MAG_GLUE = 0.2                               # tub magnet sits this far below the surface
RING_GAP = 0.35                              # clearance between the grille shell and the tub recess
MAG_TUB = MAG_T_TUB + MAG_GLUE               # pocket depth into the tub
MAG_FRAME = MAG_T_FRAME + RING_GAP           # pocket cut, measured from the tub surface; flush in the shell
MAG_REAR = [(-45, 12), (45, 12), (-45, 62), (45, 62)]      # (x, z)
MAG_SIDE = [(BD / 2, 12), (BD / 2, 62)]                     # (y, z), both sides
DOWELS = [(-68, 22), (68, 22), (-68, 96), (68, 96)]         # brace columns with lid dowel holes
FEET = [(-62, 18), (62, 18), (-62, BD - 18), (62, BD - 18)]
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
    cs = cs.offset(0.02, m3.JoinType.Miter)    # merges glyph contours that touch at a point
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
# The tub is recessed RECESS mm all the way around from the floor up to REC_Z1; the grille shell slides
# on from below and is held by magnets. The whole inside is one sealed chamber.
outline = rrect(-BW/2, BW/2, 0, BD, R_FRONT, R_REAR)
inset = rrect(-BW/2 + RECESS, BW/2 - RECESS, RECESS, BD - RECESS, R_FRONT - RECESS, R_REAR - RECESS)
inner = rrect(-BW/2 + WALL_SIDE, BW/2 - WALL_SIDE, FRONT_INNER_Y, BD - WALL_REAR,
              R_FRONT - WALL_SIDE, max(R_REAR - WALL_REAR, 2))
IX = BW/2 - WALL_SIDE
IY0, IY1 = FRONT_INNER_Y, BD - WALL_REAR

# Prints floor down. The band overhangs the recess, so its underside is a 45 deg chamfer instead of a
# flat ledge; the shell's top is beveled to match. The bottom outer edge is chamfered too.
CH_Z = REC_Z1 - BAND_CHAMFER
tub = (M.batch_hull([extrude(inset.offset(-FOOT_CHAMFER, m3.JoinType.Round), 0, 0.01), extrude(inset, FOOT_CHAMFER, CH_Z)])
       + M.batch_hull([extrude(inset, CH_Z - 0.01, CH_Z), extrude(outline, REC_Z1, TUB_H)]))
tub = tub - extrude(inner, FLOOR, TUB_H + 1)

# brace columns, which also take the lid dowels
for (x, y) in DOWELS:
    tub = tub + (cyl_z(x, y, FLOOR - 1, TUB_H, 10) ^ extrude(inner.offset(1, m3.JoinType.Round), 0, TUB_H))
for (x, y) in DOWELS:
    tub = tub - cyl_z(x, y, TUB_H - 4, TUB_H + 1, 4.3)

# Driver mount. The driver sits in a recessed well deep enough that its surround clears the grille
# shell by cover_clear, on a mounting ring that thickens the baffle behind it for the screws.
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
    """Frame outline with a 45 deg V below it, so the underside of the mounting ring prints unsupported."""
    h = max(d["body_r"], d["ear_c"] + d["ear_r"]) + grow     # extent along the 45 deg diagonals
    return CS.batch_hull([frame_outline(d, grow), CS.circle(0.01, 4).translate([0, h * math.sqrt(2)])])

def teardrop_up(r):
    """Circle of radius r with 45 deg sides above it, capped flat at its own top (a bridge)."""
    tip = CS.batch_hull([CS.circle(r, SEG), CS.circle(0.01, 4).translate([0, -r * math.sqrt(2)])])
    return tip ^ CS.square([4 * r, 2 * r]).translate([-2 * r, -r])

INTERIOR = box(-IX, IX, IY0 - 1, IY1 + 1, FLOOR - 1, TUB_H)

def mount_driver(tub, name, x):
    d = DRIVERS[name]
    cover_in = RECESS - RING_GAP                               # inside face of the grille shell
    surface = RECESS                                           # recessed tub surface under the shell
    seat = cover_in + d["cover_clear"] + d["proud"] + GASKET_T # baffle face under the gasket
    back = seat + MOUNT_MEAT                                   # back of the mounting ring
    ring = prism_y(teardrop_down(d, 4.0), x, DRV_Z, IY0 - 1, back) ^ INTERIOR
    tub = tub + ring
    # well: from the recessed surface down to the mounting face, plus the skin in front of it
    tub = tub - prism_y(frame_outline(d, d["well_clr"]), x, DRV_Z, surface + 0.3, seat)
    tub = tub - (prism_y(frame_outline(d, d["well_clr"]), x, DRV_Z, surface - 1.0, surface + 0.3)
                 ^ box(-BW, BW, -10, BD + 10, -10, CH_Z - 0.01))
    # cutout through the ring (45 deg sides and a flat top, so it bridges), plus the solder-tab relief
    # on the top side. The notch floor sits below where its sides meet the cutout, so no sliver is left.
    tub = tub - prism_y(teardrop_up(d["cut"] / 2), x, DRV_Z, seat - 1.0, back + 5.0)
    if d["tab_notch"]:
        hw, reach, depth = d["tab_notch"]
        tub = tub - box(x - hw, x + hw, seat + depth, back + 5.0,
                        DRV_Z + math.sqrt((d["cut"] / 2) ** 2 - hw ** 2) - 0.5, DRV_Z + reach)
    # blind pilot holes on the bolt circle
    for k in range(4):
        a = math.radians(45 + 90 * k)
        px, pz = x + d["bc"] / 2 * math.cos(a), DRV_Z + d["bc"] / 2 * math.sin(a)
        tub = tub - cyl_y(px, pz, seat - 0.5, seat + PILOT_DEPTH, PILOT_D)
    return tub, seat

tub, SEAT = mount_driver(tub, DRIVER, DRV_X)
WELL_TOP = DRV_Z + DRIVERS[DRIVER]["body_r"] + DRIVERS[DRIVER]["well_clr"]
assert WELL_TOP < CH_Z - 0.5 and DRV_Z - (WELL_TOP - DRV_Z) > FOOT_CHAMFER + 1.0, \
    "driver well does not fit under the band chamfer; lower DRV_Z or raise TUB_H"

# magnet pockets: rear (x, z) and both sides (y, z)
YR, XS = BD - RECESS, BW/2 - RECESS
def mag_cuts(for_shell):
    cuts = []
    for (x, z) in MAG_REAR:
        cuts.append(cyl_y(x, z, YR - 0.01, YR + MAG_FRAME, MAG_D) if for_shell
                    else cyl_y(x, z, YR - MAG_TUB, YR + 1, MAG_D))
    for (y, z) in MAG_SIDE:
        for s in (-1, 1):
            if for_shell:
                x0, x1 = sorted((s * (XS - 0.01), s * (XS + MAG_FRAME)))
            else:
                x0, x1 = sorted((s * (XS - MAG_TUB), s * (XS + 1)))
            cuts.append(cyl_x(y, z, x0, x1, MAG_D))
    return cuts
for c in mag_cuts(False):
    tub = tub - c

# feet recesses (10 mm silicone bumpers, ~3 mm tall, lift the shell's edge off the counter)
for (x, y) in FEET:
    tub = tub - cyl_z(x, y, -1, 1.0, 10.5)

# ======================= LID (glued on; spine is printed with it) =======================
LID_Z0 = TUB_H
TOPZ = LID_Z0 + LID_T
CH = 1.2   # top edge chamfer
lid = M.batch_hull([extrude(outline, LID_Z0, TOPZ - CH), extrude(outline.offset(-CH, m3.JoinType.Round), TOPZ - CH, TOPZ)])
for (x, y) in DOWELS:                      # 4 mm dowel holes (dowels align lid to tub for gluing)
    lid = lid - cyl_z(x, y, LID_Z0 - 1, LID_Z0 + 2.0, 4.3)
wire_hole = cyl_z(WIRE_HOLE[0], WIRE_HOLE[1], LID_Z0 - 1, TOPZ + 1, WIRE_HOLE[2])
lid = lid - wire_hole

# ======================= GRILLE SHELL =======================
# Flush with the tub's top band on the outside; magnet pockets open to the inside.
SZ0, SZ1 = 0.5, REC_Z1 - SHELL_TOP_GAP
shell = extrude(outline, SZ0, SZ1) - extrude(inset.offset(RING_GAP, m3.JoinType.Round), -1, 200)
for c in mag_cuts(True):
    shell = shell - c

def top_bevel(gap, outer):
    """Everything the shell must stay out of under the band: the band chamfer lowered by gap, and
    above a flat land of TOP_LAND in from the part's outer face (outer = its offset from outline)."""
    def zc(o):
        return REC_Z1 - gap + o
    cham = M.batch_hull([extrude(outline.offset(-6, m3.JoinType.Round), zc(-6) - 0.01, zc(-6)),
                         extrude(outline.offset(3, m3.JoinType.Round), zc(3), zc(3) + 0.01)])
    return cham + extrude(outline.offset(3, m3.JoinType.Round), zc(outer - TOP_LAND), 300)

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
            probe = CS.circle(r_hex, 6).translate([u, z])
            if (probe - field).area() < 1e-6:   # keep holes whose whole hexagon sits inside the field
                holes.append(place_hole(u, z, r_hex))
    return holes

def hex_hole_y(x, z, r, y0, y1):
    # 6-sided cylinder along Y with a vertex pointing up (rotated 30 deg about its own axis)
    return M.cylinder(y1 - y0, r, r, 6).rotate([0, 0, 30]).rotate([-90, 0, 0]).translate([x, y0, z])

def hex_hole_x(y, z, r, x0, x1):
    return M.cylinder(x1 - x0, r, r, 6).rotate([0, 0, 30]).rotate([0, 90, 0]).translate([x0, y, z])

FRONT_FLAT = BW / 2 - R_FRONT - 4.0
holes = hex_field(-FRONT_FLAT, FRONT_FLAT, *SHELL_Z, lambda u, z, r: hex_hole_y(u, z, r, -1, RECESS + 1))
if SHELL_SIDES:
    side_z = (SHELL_Z[0] + 12, MAG_SIDE[1][1] - 6)   # between the side magnets
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (BW / 2 + 1), sx * (BW / 2 - RECESS - 1)))
        holes += hex_field(R_FRONT + 4.0, BD - R_REAR - 4.0, *side_z,
                           lambda u, z, r, x0=x0, x1=x1: hex_hole_x(u, z, r, x0, x1))
shell = shell - union(holes)

# ======================= BEZEL (built in local frame) =======================
# local: x = X, y = a (depth, 0 at front face, + backward), z = h (up the face, 0 at bottom edge)
PW, PH = TAB_W + 2 * TAB_CLR, TAB_H + 2 * TAB_CLR
EW, EH = PW + 2 * FRAME_SIDE, PH + 2 * FRAME + CHIN
for clear in (USB_CLEAR, JACK_CLEAR):
    assert clear <= FRAME_SIDE - TRAY_WALL - 0.4 + 1e-6, "plug clearance needs a wider FRAME_SIDE"
ER = BEZEL_R
T_FRONT = LIP + POCKET_D
T = T_FRONT + TRAY_D
HC = EH / 2
CHIN_TOP = FRAME + CHIN                      # pocket bottom; the shell / chin split
TAB_CZ = CHIN_TOP + PH / 2                   # tablet center height in the bezel

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

lbox = box

# --- bezel body: front rim, tablet pocket and tray in one piece, later split at the top of the chin
WIN_W, WIN_H = PW - 2 * LIP_OVERLAP, PH - 2 * LIP_OVERLAP
WIN_R = TAB_R + TAB_CLR - LIP_OVERLAP
# Prints back down: the front edge is on top, so it gets a full round-over; the back edge is on the bed.
body_outer = rounded_slab(EW, EH, ER, 0, T, f0=BEZEL_FRONT_FILLET, f1=BEZEL_BACK_FILLET, bed="a1")
# The rim is wider than the tray wall, so where they meet the tray's inside tapers at 45 deg instead
# of leaving a flat 7.6 mm ledge, which would overhang when printing back down.
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
for x in MIC_SLOTS_X:
    tr = tr - lbox(x - 6, x + 6, LIP + 2.6, LIP + 5.6, TAB_CZ + PH / 2 - 1, EH + 1)   # behind the front round-over
# Plug channels beside the tablet: a flat FPC 90 deg USB-C adapter on one end, a slim 90 deg 3.5 mm
# plug on the other. They run down to the bottom of the pocket, because the tablet slides in from
# below with both plugs already in.
# The flat FPC ribbon folds straight back behind the tablet, so its channel ceiling sits 1 mm behind
# the lip for more material over it. The 3.5 mm plug's body is thicker, so its channel keeps 0.2 mm;
# its cable runs down the channel and back into the tray through a notch in the chin bar.
def side_channel(side, clear, zc, notch_h, front):
    x0, x1 = sorted((side * PW/2 - side * 1, side * (PW/2 + clear)))
    return lbox(x0, x1, LIP + front, T_FRONT + 1, CHIN_TOP - 1, TAB_CZ + zc + notch_h / 2)
plug_channels = side_channel(USB_SIDE, USB_CLEAR, USB_Z, USB_NOTCH_H, 1.0) + \
                side_channel(JACK_SIDE, JACK_CLEAR, JACK_Z, JACK_NOTCH_H, 0.2)                   # cut after the split
# mmWave radar pocket in the chin, open to the tray; the radar looks out through RADAR_LIP of plastic
RADAR_Z = CHIN_TOP / 2
tr = tr - lbox(-RADAR_W / 2, RADAR_W / 2, RADAR_LIP, T_FRONT + 1, RADAR_Z - RADAR_H / 2, RADAR_Z + RADAR_H / 2)
if LABELS:   # on the back of the chin, beside the radar pocket (read from the tray side)
    tr = tr + bezel_label("LD2410C", 0.0, RADAR_Z + 2.0, T - TRAY_WALL, -1)     # on the back wall, behind the radar
BACK_IN = T - TRAY_WALL
# tablet back-stop posts (0.5 mm felt on the tips, so the tablet slides in)
for x in POSTS_X:
    for z in (POST_Z1, EH - POST_Z1):
        tr = tr + lcyl_a(x, z, T_FRONT, T - 0.01, 8.0)
# cradles for the boards, standing off the inside of the back wall
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
    tr = tr + bezel_label("USB-C FPC", USB_SIDE * (PW / 2 - 4.0), TAB_CZ, BACK_IN, -1, angle=90 * USB_SIDE)
    tr = tr + bezel_label("3.5 MM", JACK_SIDE * (PW / 2 - 4.0), TAB_CZ, BACK_IN, -1, angle=90 * JACK_SIDE)
# bosses for the spine bolts: inserts pressed in from the back face, bolts come from the spine's rear
for (x, z) in SPINE_PTS:
    tr = tr + lcyl_a(x, z, BACK_IN - 7.0, T - 0.01, 8.0)
    tr = tr - lcyl_a(x, z, T - INSERT_DEPTH, T + 1, M3_INSERT)
# chin screw bosses: vertical columns against the back wall, split with the body below
# chin bar screw bosses: through the tray depth, head counterbores from the back face. They stop 0.5 mm
# short of the bar, which seats against the front edges of the tray walls instead.
CHIN_SCREW_Z = CHIN_TOP / 2 + 0.5
for x in CHIN_SCREW_X:
    tr = tr + (lcyl_a(x, CHIN_SCREW_Z, T_FRONT + 0.5, T - 0.01, 9.0) ^ body_outer)
# vents in the back wall: a low row clear of the chin bosses, a high row above the cradles
for x in (-105, -92, -58, -45, 45, 58, 92, 105):
    tr = tr - lbox(x - 2, x + 2, T - TRAY_WALL - 1, T + 1, CHIN_TOP + 3, CHIN_TOP + 13)
for i in range(13):
    x = -96 + i * 16
    tr = tr - lbox(x - 2, x + 2, T - TRAY_WALL - 1, T + 1, EH - 30, EH - 14)
tr = tr - lcyl_a(0, CH_H, T - TRAY_WALL - 1, T + 1, 13)          # cable channel into the tray
# Split: the chin is the solid bar in front of the tray below the tablet, plus the strip of lip along
# the bottom of the glass (so that strip sits on solid plastic instead of spanning 209 mm on its own).
# The lower tray stays with the shell. The tablet slides up through the bar's slot before the bar goes in.
chin_region = lbox(-EW, EW, -10, T_FRONT, -10, CHIN_TOP) + \
              lbox(-PW / 2, PW / 2, -10, LIP, CHIN_TOP - 1, CHIN_TOP + LIP_OVERLAP + TAB_CLR + 0.5)
chin = tr ^ chin_region
tr = tr - chin_region - pocket_ext - plug_channels
head_a = T_FRONT + (CHIN_SCREW_LEN - 5.0)    # where the screw head seats
assert T - head_a >= 3.2, "chin screw head would stand proud of the tray back; use a shorter screw"
for x in CHIN_SCREW_X:
    chin = chin - lcyl_a(x, CHIN_SCREW_Z, T_FRONT - INSERT_DEPTH, T_FRONT + 1, M3_INSERT)    # insert in the bar's back
    tr = tr - lcyl_a(x, CHIN_SCREW_Z, T_FRONT - 1, T + 1, M3_CLR) - lcyl_a(x, CHIN_SCREW_Z, head_a, T + 1, 6.2)
# Audio cable: from the bottom of the jack channel, through this notch in the top of the bar, out of
# the bar's back face beside the tablet's rounded corner and into the lower tray.
reach, drop = JACK_CABLE_NOTCH
nx0, nx1 = sorted((JACK_SIDE * (PW / 2 - reach), JACK_SIDE * (PW / 2 + JACK_CLEAR)))
cable_notch = lbox(nx0, nx1, LIP + 1.0, T_FRONT + 1, CHIN_TOP - drop, CHIN_TOP + 1)
assert reach < TAB_R + TAB_CLR, "the cable notch would reach under the flat bottom edge of the tablet"
chin = chin - cable_notch

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
bps = to_world(0, T, SPINE_HS)
Yb0 = bp0[1]
REAR_Y = Yb0 + SPINE_REAR
assert REAR_Y < BD - 2, "spine runs off the back of the base"
REAR_FACE_H = max(8.0, PWR_Z + PWR_PLATE_H / 2 + 3.0)    # flat rear face tall enough for the power plate
prof = CS([[(Yb0 - 6, TOPZ), (REAR_Y - 0.6, TOPZ), (REAR_Y - 0.6, TOPZ + REAR_FACE_H), (bps[1], bps[2]), (bp0[1], bp0[2]), (Yb0 - 6, bp0[2])]])
spine = prof.extrude(SPINE_W).rotate([90, 0, 90]).translate([-SPINE_W/2, 0, 0])   # profile (Y,Z) extruded along X
spine = spine.translate([0, 0, -0.5])     # sink 0.5 mm into the lid so they fuse
# bolt holes for the bezel, drilled along the bezel normal from the spine's rear, with head counterbores
for (x, h) in SPINE_PTS:
    spine = spine - place(lcyl_a(x, h, T - 0.5, T + 120, M3_CLR)) - place(lcyl_a(x, h, T + SPINE_GRIP, T + 160, 6.4))
# cable channel: hull of two spheres, lid hole -> tray
p_low = np.array([WIRE_HOLE[0], WIRE_HOLE[1], TOPZ - 2])
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
bezel_keepout = place(rounded_slab(EW, EH, ER, -1, T, f1=BEZEL_BACK_FILLET, bed="a1"))   # hugs the curved tray back
spine = spine - bezel_keepout
lid_spine = lid + spine
lid_spine = lid_spine - chan - wire_hole

# ======================= EXPORT =======================
def export(man, name):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=False)
    bodies = [b for b in tm.split(only_watertight=False) if abs(b.volume) > 1.0]
    if len(bodies) > 1 or not tm.is_watertight:
        tm = trimesh.util.concatenate(bodies) if len(bodies) > 1 else bodies[0]
    tm.export(os.path.join(OUT, name + ".stl"))
    bb = tm.bounds
    print(f"{name:18s} vol {tm.volume/1000:8.1f} cm3  bbox {np.round(bb[1]-bb[0],1)}  watertight={tm.is_watertight}")
    return tm

parts_world = {
    "base_tub": tub, "lid_spine": lid_spine, "grille_shell": shell,
    "bezel_shell": bezel_shell_w, "bezel_chin": bezel_chin_w, "power_plate": pwr_plate_w,
}
meshes = {k: export(v, k) for k, v in parts_world.items()}
# tablet placeholder for renders: glass face at the back of the lip
tablet = place(rr_xz(TAB_W, TAB_H, TAB_R, LIP + 0.05, LIP + TAB_T, cz=TAB_CZ))
export(tablet, "_render_tablet")
# lit screen area for renders: the 8.7 in 1340 x 800 active area, centered on the glass
screen = place(rr_xz(189.7, 113.3, 1.0, LIP + 0.0, LIP + 0.06, cz=TAB_CZ))
export(screen, "_render_screen")
# print-ready orientations
export(tr.rotate([-90, 0, 0]), "print_bezel_shell")            # back wall down, front rim on top
export(chin.rotate([-90, 0, 0]), "print_bezel_chin")           # back wall down
export(shell, "print_grille_shell")                            # bottom edge down, beveled top up
export(lid_spine.translate([0, 0, -LID_Z0]), "print_lid_spine")
export(tub, "print_base_tub")
export(pwr_plate, "print_power_plate")                         # outside face down, sled standing up

# Checks
air = extrude(inner, FLOOR, TUB_H) - tub                       # lid on, wire hole hot-glued shut
chambers = sorted((c.volume() / 1e6 for c in air.decompose()), reverse=True)
print("chamber air volume (L, driver body not subtracted):", [round(v, 3) for v in chambers[:2]])
print("driver mounting face Y", round(SEAT, 1), "magnet back Y", round(SEAT + 43.0, 1), "of", IY1)
# Spine material along each bolt axis, from the tray back to the spine's rear surface, probed with a
# thin rod just beside the counterbore. A bolt gets a proper seat when this exceeds SPINE_GRIP + 3 mm.
for (x, h) in SPINE_PTS:
    rod = place(lcyl_a(x + 4.0, h, T - 0.01, T + 100, 1.0))
    print(f"spine bolt ({x:+.0f}, {h:.0f}): {(lid_spine ^ rod).volume() / (math.pi * 0.25):.1f} mm of spine "
          f"along the axis, head seat at {SPINE_GRIP}")
print("bezel thickness", T, "bezel outer", round(EW, 1), round(EH, 1), "top Z", round(to_world(0, 0, EH)[2], 1),
      "top-back Y", round(to_world(0, T, EH)[1], 1))
print("lowest bezel corner Z", round(to_world(0, T, 0)[2], 1), "Yb0", round(Yb0, 1), "spine rear Y", round(REAR_Y, 1))
