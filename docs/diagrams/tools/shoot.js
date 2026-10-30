// node shoot.js <base url> <data dir> <out prefix> <rev> <date> <commit> <total> <page:sheet>...
// page:sheet is render:sheet1 for an exploded view or wiring:wiring for the wiring diagram.
const { chromium } = require('playwright');
(async () => {
  const [,, base, data, out, rev, date, commit, total, ...pages] = process.argv;
  const b = await chromium.launch({args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  const p = await b.newPage({viewport: {width: 2200, height: 1500}, deviceScaleFactor: 1.5});
  p.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
  p.on('pageerror', e => console.log('pageerror:', e.message));
  for (const spec of pages) {
    const [page, sheet] = spec.split(':');
    await p.goto(`${base}/${page}.html?data=${data}&sheet=${sheet}&rev=${rev}&date=${date}&commit=${commit}&total=${total}`);
    await p.waitForFunction(() => window.__done === true, null, {timeout: 300000});
    await p.screenshot({path: `${out}${sheet}.png`});
    console.log('wrote', `${out}${sheet}.png`);
  }
  await b.close();
})();
