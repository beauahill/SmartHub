// Shared drawing frame: border, title block, parts key. Sheets are 2200 x 1500 CSS px.
export const W = 2200, H = 1500;
export const DRAW = {x: 30, y: 30, w: 1600, h: 1440};
export function frame({title, subtitle, sheet, total, dwg, rev, date, commit}) {
  document.body.innerHTML = '';
  const s = document.createElement('div'); s.id = 'sheet'; document.body.appendChild(s);
  s.innerHTML = `
  <div class="border"></div>
  <div id="draw" style="left:${DRAW.x}px;top:${DRAW.y}px;width:${DRAW.w}px;height:${DRAW.h}px"></div>
  <div id="panel">
    <div class="ptitle">${title}<span>${subtitle}</span></div>
    <div id="key"></div>
    <div id="notes"></div>
    <div id="tblock">
      <div class="tb-proj">SMARTHUB · COUNTER DISPLAY</div>
      <div class="tb-row"><div><b>DRAWING</b>${title}</div></div>
      <div class="tb-grid">
        <div><b>DWG NO.</b>${dwg}</div><div><b>SHEET</b>${sheet} OF ${total}</div>
        <div><b>REV</b>${rev}</div><div><b>DATE</b>${date}</div>
        <div><b>SCALE</b>NTS</div><div><b>SOURCE</b>enclosure.py ${commit || ''}</div>
      </div>
    </div>
  </div>`;
  return {draw: s.querySelector('#draw'), key: s.querySelector('#key'), notes: s.querySelector('#notes')};
}
export function partsKey(el, items) {
  el.innerHTML = `<table><tr><th>ITEM</th><th>DESCRIPTION</th><th>QTY</th><th>BOM</th></tr>` +
    items.map(i => `<tr><td class="n"><span class="ball">${i.n}</span></td><td>${i.name}</td><td class="c">${i.qty}</td><td class="c">${i.ref}</td></tr>`).join('') +
    `</table>`;
}
export function notesKey(el, notes, heading = 'NOTES') {
  if (!notes.length) return;
  el.innerHTML = `<div class="nh">${heading}</div>` +
    notes.map(n => `<div class="note"><span class="nkey">${n.k}</span><span>${n.text}</span></div>`).join('');
}
export const CSS = `
  html,body{margin:0;background:#fff}
  #sheet{position:relative;width:${W}px;height:${H}px;background:#fff;font-family:'DejaVu Sans',Arial,sans-serif;color:#111;overflow:hidden}
  .border{position:absolute;left:12px;top:12px;right:12px;bottom:12px;border:3px solid #111}
  #draw{position:absolute;overflow:hidden}
  #panel{position:absolute;left:1650px;top:30px;width:520px;height:1440px;border-left:2px solid #111;padding-left:18px;box-sizing:border-box}
  .ptitle{font-size:30px;font-weight:700;letter-spacing:1px;margin:4px 0 14px}
  .ptitle span{display:block;font-size:17px;font-weight:400;letter-spacing:0;color:#444;margin-top:4px}
  table{border-collapse:collapse;width:100%;font-size:15.5px}
  th{background:#111;color:#fff;text-align:left;padding:6px 6px;font-size:13px;letter-spacing:1px}
  td{border-bottom:1px solid #bbb;padding:5px 6px;vertical-align:middle}
  td.c{text-align:center;white-space:nowrap}
  td.n{width:40px}
  .ball{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:2px solid #111;border-radius:50%;font-weight:700;font-size:14px;box-sizing:border-box}
  #notes{margin-top:22px;font-size:15px}
  .nh{font-weight:700;letter-spacing:1px;font-size:14px;border-bottom:2px solid #111;padding-bottom:4px;margin-bottom:8px}
  .note{display:flex;gap:10px;margin:8px 0;line-height:1.3}
  .nkey{flex:none;display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border:2px solid #111;font-weight:700;font-size:14px;box-sizing:border-box;transform:none}
  #tblock{position:absolute;left:18px;right:0;bottom:0;border:2px solid #111;font-size:13px}
  #tblock b{display:block;font-size:10.5px;letter-spacing:1px;color:#555;font-weight:700;margin-bottom:2px}
  .tb-proj{background:#111;color:#fff;font-weight:700;letter-spacing:2px;padding:8px 10px;font-size:16px}
  .tb-row{padding:7px 10px;border-bottom:1px solid #111;font-size:17px;font-weight:700}
  .tb-grid{display:grid;grid-template-columns:1fr 1fr}
  .tb-grid div{padding:6px 10px;border-top:1px solid #111;font-size:14px}
  .tb-grid div:nth-child(odd){border-right:1px solid #111}
  .tb-grid div:nth-child(-n+2){border-top:none}
`;
