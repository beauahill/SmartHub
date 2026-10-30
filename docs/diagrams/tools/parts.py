"""Builds the meshes and the manifest for the assembly diagrams.

    python docs/diagrams/tools/parts.py <outdir>

Runs enclosure/enclosure.py for the printed parts, adds simple stand-in models for the drivers,
boards and hardware, and writes <outdir>/*.stl plus <outdir>/manifest.json. render.html draws the
sheets from that folder.
"""
import json, math, os, runpy, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "diag")
os.makedirs(OUT, exist_ok=True)
sys.argv = [os.path.join(ROOT, "enclosure", "enclosure.py"), os.path.join(OUT, "_enclosure")]
g = runpy.run_path(sys.argv[0], run_name="__main__")
M, m3, np, trimesh = g["M"], g["m3"], g["np"], g["trimesh"]
lbox, place, box, cyl_y, cyl_x, cyl_z = g["lbox"], g["place"], g["box"], g["cyl_y"], g["cyl_x"], g["cyl_z"]
prism_y, frame_outline, lcyl_a, rr_xz = g["prism_y"], g["frame_outline"], g["lcyl_a"], g["rr_xz"]
D, SEATS, GASKET_T = g["DRIVERS"], g["SEATS"], g["GASKET_T"]
st, ct = g["st"], g["ct"]

def save(man, name):
    mesh = man.to_mesh()
    trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts).export(os.path.join(OUT, name + ".stl"))
    return name

def frustum_y(x, z, y0, y1, r0, r1):
    if y1 < y0:
        y0, y1, r0, r1 = y1, y0, r1, r0
    return M.cylinder(y1 - y0, r0, r1, 64).rotate([-90, 0, 0]).translate([x, y0, z])

def driver(key, name, x, z, rear, depth, magnet=True):
    """Stand-in driver: frame, surround and cone, basket, magnet. Seated on its gasket."""
    d = D[key]
    s = 1 if rear else -1                      # facing direction along Y
    fb = SEATS[name] + s * GASKET_T            # back of the flange
    f0, f1 = sorted((fb, fb + s * d["flange_t"]))
    m = prism_y(frame_outline(d), x, z, f0, f1)
    cone_r = d["cut"] / 2 + 1
    m += frustum_y(x, z, fb + s * d["flange_t"], fb + s * d["proud"], d["body_r"] - 2, cone_r - 6)
    m += frustum_y(x, z, fb, fb - s * depth * (0.62 if magnet else 1.0), d["cut"] / 2 - 1, d["cut"] / 2 * 0.5)
    if magnet:
        m += frustum_y(x, z, fb - s * depth * 0.62, fb - s * depth, d["cut"] / 2 * 0.55, d["cut"] / 2 * 0.55)
    return m

parts = {}
# ---- printed parts, assembled positions
for n in ("base_tub", "lid_spine", "grille_shell", "bezel_shell", "bezel_chin", "power_plate"):
    parts[n] = save(g["parts_world"][n], n)
parts["tablet"] = save(g["tablet"], "tablet")
# ---- drivers
FR_X, DRV_Z, WOOF_Z = g["FR_X"], g["DRV_Z"], g["WOOF_Z"]
parts["nd65_l"] = save(driver("nd65", "nd65_l", -FR_X, DRV_Z, False, 43.0), "nd65_l")
parts["nd65_r"] = save(driver("nd65", "nd65", FR_X, DRV_Z, False, 43.0), "nd65_r")
parts["nd105"] = save(driver("nd105", "nd105", 0, WOOF_Z, False, 57.0), "nd105")
parts["nd105pr"] = save(driver("nd105pr", "nd105pr", 0, WOOF_Z, True, 30.5, magnet=False), "nd105pr")
# ---- dowels and tub magnets
TUB_H = g["TUB_H"]
parts["dowels"] = save(g["union"]([cyl_z(x, y, TUB_H - 4, TUB_H + 2, 4.0) for (x, y) in g["BOSSES"]]), "dowels")
YF, YR, XS = g["YF"], g["YR"], g["XS"]
mags_rear = [cyl_y(x, z, YR - 2.2, YR - 0.2, 6.0) for (x, z) in g["MAG_REAR"]]
mags_side = [c for (y, z) in g["MAG_SIDE"] for c in (cyl_x(y, z, XS - 2.2, XS - 0.2, 6.0), cyl_x(y, z, -XS + 0.2, -XS + 2.2, 6.0))]
parts["mags_rear"] = save(g["union"](mags_rear), "mags_rear")
parts["mags_side_r"] = save(g["union"]([c for c in mags_side[0::2]]), "mags_side_r")
parts["mags_side_l"] = save(g["union"]([c for c in mags_side[1::2]]), "mags_side_l")
# ---- PD trigger on the power plate (plate coordinates, then the plate's placement)
pcb_bot, edge_z, board_xz = g["pcb_bot"], g["edge_z"], g["board_xz"]
TW, TL, TT = g["TRIG_W"], g["TRIG_L"], g["TRIG_T"]
trig = box(-TW / 2, TW / 2, pcb_bot, pcb_bot + TT, edge_z, edge_z + TL)
trig += box(-4.5, 4.5, -1.6, 1.6, edge_z - g["TRIG_USB_OVERHANG"], edge_z + 6.5)          # USB-C socket
tx0, tz0 = board_xz(5.0, 8.0); tx1, tz1 = board_xz(15.5, 0.5)
trig += box(min(tx0, tx1), max(tx0, tx1), pcb_bot + TT, pcb_bot + TT + g["TRIG_TALL"], min(tz0, tz1), max(tz0, tz1))   # terminal
trig += box(-9.5, -3.5, pcb_bot + TT, pcb_bot + TT + 4.0, edge_z + 12, edge_z + 20)        # DIP switch
place_plate = lambda m: m.rotate([90, 0, 0]).translate([0, g["REAR_FACE"], g["PWR_ZW"]])
parts["pd_trigger"] = save(place_plate(trig), "pd_trigger")
RF = g["REAR_FACE"]
plate_screws = [frustum_y(sx, g["PWR_ZW"], RF - 1.7, RF, 1.5, 3.0) + cyl_y(sx, g["PWR_ZW"], RF - 8, RF - 1.7, 3.0)
                for sx in (-g["PWR_SCREW_X"], g["PWR_SCREW_X"])]
parts["plate_screws"] = save(g["union"](plate_screws), "plate_screws")
# ---- bezel contents, built in the bezel frame (x, a = depth from the front, h = height)
T, T_FRONT, BACK_IN, LIP = g["T"], g["T_FRONT"], g["BACK_IN"], g["LIP"]
JX, JZ, AS, AH = g["JX"], g["JZ"], g["AMP_STANDOFF"], g["AMP_H"]
pcb_a = BACK_IN - AS
amp = lbox(JX - 45.7, JX + 45.7, pcb_a - 1.6, pcb_a, JZ - 34.3, JZ + 34.3)
amp += lbox(JX - 40, JX - 8, pcb_a - AH, pcb_a - 1.6, JZ - 30, JZ - 6)        # tallest parts: inductors and caps
amp += lbox(JX - 4, JX + 26, pcb_a - 9, pcb_a - 1.6, JZ - 18, JZ + 12)        # DSP and BT module
amp += lbox(JX - 42, JX + 42, pcb_a - 10, pcb_a - 1.6, JZ + 22, JZ + 32)      # terminal strip
bez_local = {"amp": amp}
thick = {"pd_module": 10.0, "audio_adapter": 12.0, "buck_5v": 5.0, "esp32_c3": 4.0}
for (name, cx, cz, w, h, label, side) in g["CRADLES"]:
    bez_local[name] = lbox(cx - w / 2, cx + w / 2, BACK_IN - thick[name], BACK_IN, cz - h / 2, cz + h / 2)
RZ, RL = g["RADAR_Z"], g["RADAR_LIP"]
bez_local["radar"] = lbox(-11, 11, RL + 0.2, RL + 1.8, RZ - 8, RZ + 8) + lbox(-4, 4, RL + 1.8, RL + 3.0, RZ - 4, RZ + 4)
PW, TAB_CZ, USB_SIDE = g["PW"], g["TAB_CZ"], g["USB_SIDE"]
ux = USB_SIDE * (PW / 2 + 1.75)
bez_local["fpc"] = lbox(ux - 1.75, ux + 1.75, LIP + 2.6, LIP + 6.4, TAB_CZ - 6, TAB_CZ + 6) + \
                   lbox(ux - 1.75, ux + 1.75, LIP + 7.0, LIP + 7.3, TAB_CZ - 60, TAB_CZ - 6)
bez_local["felt"] = g["union"]([lcyl_a(x, z, T_FRONT - 0.5, T_FRONT, 8.0) for x in (-115, 0, 115) for z in (40, g["EH"] - 40)])
bez_local["tablet_l"] = rr_xz(g["TAB_W"], g["TAB_H"], g["TAB_R"], LIP + 0.05, LIP + g["TAB_T"], cz=TAB_CZ)
bez_local["shell_l"] = g["tr"]
bez_local["chin_l"] = g["chin"]
head_a, CSZ = g["head_a"], g["CHIN_SCREW_Z"]
bez_local["chin_screws"] = g["union"]([lcyl_a(x, CSZ, head_a, head_a + 3, 5.5) + lcyl_a(x, CSZ, head_a - 20, head_a, 3.0)
                                       for x in g["CHIN_SCREW_X"]])
grip = g["SPINE_GRIP"]
bez_local["spine_bolts"] = g["union"]([lcyl_a(x, h, T + grip, T + grip + 3, 5.5) + lcyl_a(x, h, T + grip - 16, T + grip, 3.0)
                                       for (x, h) in g["SPINE_PTS"]])
for n, m in bez_local.items():
    parts[n] = save(m, n)                    # bezel frame, for the bezel sheet
    parts[n + "_w"] = save(place(m), n + "_w")   # placed in the world
# ---- explode directions
nrm = [0.0, ct, -st]                          # bezel normal, pointing back (world)
def mul(v, k): return [round(c * k, 3) for c in v]
def add(*vs): return [round(sum(c), 3) for c in zip(*vs)]
lift = [0, 0, 95]
bez = add([0, -150, 140])

def wpt(x, a, h):
    return [round(float(c), 2) for c in g["to_world"](x, a, h)]

sheets = [
  dict(id="sheet1", title="GENERAL ASSEMBLY", subtitle="Exploded view, front", cam=[-0.48, -0.78, 0.40],
       items=[
         dict(n=1, name="Bezel shell", qty=1, ref="P4", parts=[("bezel_shell", bez, "print")]),
         dict(n=2, name="Chin bar", qty=1, ref="P5", parts=[("bezel_chin", add(bez, [0, -40, -60]), "print")]),
         dict(n=3, name="Tablet, Galaxy Tab A9+", qty=1, ref="E1", parts=[("tablet", add(bez, [0, -120, 30]), "glass")]),
         dict(n=4, name="Lid and spine", qty=1, ref="P2", parts=[("lid_spine", [0, 0, 75], "print")]),
         dict(n=5, name="Dowel pin, 4 x 6 mm", qty=6, ref="H5", parts=[("dowels", [0, 0, 38], "metal")], anchor=[-135, 22, TUB_H + 39]),
         dict(n=6, name="Base tub", qty=1, ref="P1", parts=[("base_tub", [0, 0, 0], "print")]),
         dict(n=7, name="Full-range driver, ND65-4", qty=2, ref="S1",
              parts=[("nd65_l", [0, -125, 0], "driver"), ("nd65_r", [0, -125, 0], "driver")]),
         dict(n=8, name="Woofer, ND105-4", qty=1, ref="S2", parts=[("nd105", [0, -125, 0], "driver")]),
         dict(n=9, name="Grille shell (or grille ring + linen)", qty=1, ref="P3a", parts=[("grille_shell", [0, 0, -175], "print2")]),
         dict(n=10, name="Driver screw, M3 x 6 thread-forming", qty=16, ref="S4", parts=[], anchor=[-FR_X - 23, -125 + 5, DRV_Z + 23]),
         dict(n=11, name="Gasket tape, 1 mm (under each flange)", qty=1, ref="S5", parts=[], anchor=[0, -125 + 18, WOOF_Z + 50]),
       ],
       notes=[
         dict(k="A", text="Bezel bolts to the spine from the rear (sheet 2).", anchor=[-30, 75, 165 + 75]),
         dict(k="B", text="Epoxy the lid to the tub: outer rim and both full-range chamber walls. Airtight.", anchor=[-148, 70, 116 + 75.5]),
         dict(k="C", text="Tablet slides up into the shell from below, then the chin bar closes the slot.", anchor=add(wpt(0, 0, 5), bez, [0, -40, -60])),
         dict(k="D", text="ND65 solder tabs up, into the notch above the cutout.", anchor=[FR_X, -125 + 8, DRV_Z + 30]),
       ]),
  dict(id="sheet2", title="BASE AND SPINE", subtitle="Exploded view, rear", cam=[0.50, 0.76, 0.42],
       items=[
         dict(n=1, name="Lid and spine", qty=1, ref="P2", parts=[("lid_spine", lift, "print")]),
         dict(n=2, name="Bezel assembly (sheet 3)", qty=1, ref="", parts=[("shell_l_w", lift, "print2"), ("chin_l_w", lift, "print2")]),
         dict(n=3, name="Bezel bolt, M3 x 16 socket head", qty=4, ref="H3", parts=[("spine_bolts_w", add(lift, mul(nrm, 70)), "metal")]),
         dict(n=4, name="Chin bar screw, M3 x 20 socket head", qty=4, ref="H2", parts=[("chin_screws_w", add(lift, mul(nrm, 45)), "metal")]),
         dict(n=5, name="Power plate", qty=1, ref="P6", parts=[("power_plate", add(lift, [0, 75, 45]), "print")]),
         dict(n=6, name="PD trigger, Adafruit HUSB238 (DIP = 20 V)", qty=1, ref="E9", parts=[("pd_trigger", add(lift, [0, 75, 45]), "pcb")],
              anchor=add(lift, [0, 75, 45], [8, g["REAR_FACE"] - 20, g["PWR_ZW"] + 6])),
         dict(n=7, name="Plate screw, M3 x 8 countersunk", qty=2, ref="H3a", parts=[("plate_screws", add(lift, [0, 120, 45]), "metal")]),
         dict(n=8, name="Dowel pin, 4 x 6 mm", qty=6, ref="H5", parts=[("dowels", [0, 0, 45], "metal")], anchor=[130, 128, TUB_H + 46]),
         dict(n=9, name="Base tub", qty=1, ref="P1", parts=[("base_tub", [0, 0, 0], "print")]),
         dict(n=10, name="Passive radiator, ND105-PR", qty=1, ref="S3", parts=[("nd105pr", [0, 120, 0], "driver")]),
         dict(n=11, name="Magnet, 6 x 2 mm (tub pockets)", qty=12, ref="H6",
              parts=[("mags_rear", [0, 30, 0], "magnet"), ("mags_side_r", [30, 0, 0], "magnet"), ("mags_side_l", [-30, 0, 0], "magnet")]),
       ],
       notes=[
         dict(k="A", text="Ø8 speaker wire hole in the lid, under the spine. Fill it with hot glue from inside before the lid goes on.",
              anchor=[0, 74, 120 + 95]),
         dict(k="B", text="Cable clip: press the charger cable in here.", anchor=[0, 137, 124 + 95]),
         dict(k="C", text="Speaker and 20 V leads run up the spine channel into the tray.", anchor=add(lift, wpt(0, T, 60))),
         dict(k="D", text="Set the DIP switch to 20 V only before fitting the plate.", anchor=add(lift, [0, 75, 45], [-8, g["REAR_FACE"] - 15, g["PWR_ZW"]])),
       ]),
  dict(id="sheet3", title="BEZEL ASSEMBLY", subtitle="Exploded view, front (bezel frame, upright)", cam=[-0.45, -0.80, 0.40],
       items=[
         dict(n=1, name="Bezel shell", qty=1, ref="P4", parts=[("shell_l", [0, 0, 0], "print")]),
         dict(n=2, name="Amplifier, Dayton KABD-430", qty=1, ref="E2", parts=[("amp", [0, -75, 0], "pcb")]),
         dict(n=3, name="Amp screw, M3 x 6 thread-forming", qty=4, ref="H4", parts=[], anchor=[JX - 41.9, BACK_IN - AS - 75 - 2, JZ + 30.5]),
         dict(n=4, name="USB-C PD module (20 V in)", qty=1, ref="E6", parts=[("pd_module", [0, -75, 0], "pcb")]),
         dict(n=5, name="UGREEN 2-in-1 USB-C audio + PD adapter", qty=1, ref="A2", parts=[("audio_adapter", [0, -75, 0], "pcb2")]),
         dict(n=6, name="5 V buck, MP1584EN", qty=1, ref="E5", parts=[("buck_5v", [0, -75, 0], "pcb")]),
         dict(n=7, name="ESP32-C3 SuperMini", qty=1, ref="E3", parts=[("esp32_c3", [0, -75, 0], "pcb")]),
         dict(n=8, name="Felt pad, 8 mm, 0.5 mm thick", qty=6, ref="H9", parts=[("felt", [0, -45, 0], "felt")]),
         dict(n=9, name="Flat FPC USB-C 90° adapter", qty=1, ref="A1", parts=[("fpc", [30, -120, -265], "pcb2")]),
         dict(n=10, name="Tablet, Galaxy Tab A9+", qty=1, ref="E1", parts=[("tablet_l", [0, -120, -265], "glass")]),
         dict(n=11, name="Chin bar", qty=1, ref="P5", parts=[("chin_l", [0, -40, -75], "print")]),
         dict(n=12, name="Radar, HLK-LD2410C", qty=1, ref="E4", parts=[("radar", [0, -75, -75], "pcb")]),
       ],
       notes=[
         dict(k="A", text="Heat-set inserts: 4 in the chin bar's back face, 4 in the spine-bolt bosses (from the back).", anchor=[100, -40 + T_FRONT, -75 + CSZ]),
         dict(k="B", text="Small boards sit in their labeled cradles on VHB tape.", anchor=[85, BACK_IN - 75 - 12, 120]),
         dict(k="C", text="Plug the FPC adapter into the tablet first. It rides in the channel on the right as the tablet slides up into the shell.", anchor=[ux + 30, LIP + 4 - 120, TAB_CZ - 265]),
         dict(k="D", text="Radar looks out through 1.6 mm of the chin. No metal-filled filament.", anchor=[0, RL - 75, -75 + RZ]),
       ]),
]
for s in sheets:
    for it in s["items"]:
        it["parts"] = [dict(file=f, offset=o, style=st_) for (f, o, st_) in it["parts"]]
json.dump(dict(sheets=sheets), open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
print("wrote", len(os.listdir(OUT)), "files to", OUT)
