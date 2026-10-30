# Diagram tools

These scripts regenerate the sheets in `docs/diagrams/` from `enclosure/enclosure.py`, so the
diagrams follow the model when it changes. They need Python with `enclosure/requirements.txt`,
Node with Playwright, and three.js.

```bash
cd docs/diagrams/tools
npm install three@0.160.0 playwright      # once
python parts.py /tmp/diag                 # printed parts, stand-in drivers, boards and hardware, manifest.json
ln -s /tmp/diag diag                      # render.html reads ./diag
python -m http.server 8766 &              # serve this folder
node shoot.js http://127.0.0.1:8766 diag out/ A 2026-10-30 "$(git rev-parse --short HEAD)" 4 \
  render:sheet1 render:sheet2 render:sheet3 wiring:wiring
node make_pdf.js "$PWD/out" ../assembly_diagrams.pdf
```

The sheets are written as `out/sheet1.png` … `out/wiring.png`. Copy them over the numbered PNGs in
`docs/diagrams/`.

- `parts.py` sets what goes on each exploded sheet: items, explode offsets, callout anchors and notes.
- `render.html` draws an exploded sheet with an orthographic camera. Edges come from breaks in depth
  and surface normals. Balloons go in columns on each side of the drawing.
- `wiring.html` is the wiring diagram, laid out by hand.
- `sheet.js` holds the shared border, parts key and title block.

The drivers, boards and fasteners are simple stand-ins sized from the BOM, not the makers' models.
