// node make_pdf.js <folder with sheet1..3.png and wiring.png> <out.pdf>
const { chromium } = require('playwright');
(async () => {
  const [,, dir, out] = process.argv;
  const b = await chromium.launch();
  const p = await b.newPage();
  const fs = require('fs');
  const imgs = ['sheet1', 'sheet2', 'sheet3', 'wiring'].map(n => `<div class="pg"><img src="data:image/png;base64,${fs.readFileSync(`${dir}/${n}.png`).toString('base64')}"></div>`).join('');
  await p.setContent(`<style>@page{size:2200px 1500px;margin:0}body{margin:0}.pg{width:2200px;height:1500px;page-break-after:always}img{width:2200px;height:1500px;display:block}</style>${imgs}`, {waitUntil: 'load'});
  await p.pdf({path: out, width: '2200px', height: '1500px', printBackground: true});
  await b.close();
})();
