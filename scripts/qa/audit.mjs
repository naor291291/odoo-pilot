/** Synthetic loopback pilot only. Never accepts an external target or live credentials. */
import {chromium} from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(root, '.local-data/ui-checks/pre-deployment');
await fs.mkdir(output, {recursive: true});
const credentials = JSON.parse(await fs.readFile(path.join(root, '.local-data/credentials.json')));
const base = 'http://127.0.0.1:8069';
const results = [], errors = [];
const browser = await chromium.launch({executablePath: process.env.CHROME_BIN, args: ['--no-sandbox']});
async function authenticate(context, account) {
  const r = await context.request.post(base + '/web/session/authenticate', {data: {
    jsonrpc: '2.0', method: 'call', id: 1,
    params: {db: 'odoo_pilot', login: account.login, password: account.password}
  }});
  if (!(await r.json()).result?.uid) throw Error('Synthetic account authentication failed');
}
async function rpc(context, model, method, args, kwargs = {}) {
  const r = await context.request.post(base + '/web/dataset/call_kw', {data: {
    jsonrpc: '2.0', method: 'call', id: 1, params: {model, method, args, kwargs}
  }});
  const data = await r.json();
  if (data.error) throw Error('RPC failed: ' + model + '.' + method);
  return data.result;
}
async function audit(context, name, route, selector) {
  const page = await context.newPage();
  page.on('pageerror', () => errors.push({screen:name, type:'uncaught JavaScript'}));
  const network = [];
  page.on('response', r => {if (r.url().startsWith(base) && r.status() >= 400)
    network.push({path:new URL(r.url()).pathname, status:r.status()});});
  try {
    for (const width of [375, 390, 768, 1440]) {
      await page.setViewportSize({width, height:1000});
      const start = performance.now();
      await page.goto(base + route);
      await page.locator(selector).first().waitFor({state:'visible',timeout:60000});
      await page.locator('.o_blockUI').waitFor({state:'hidden',timeout:60000});
      await page.evaluate(() => document.fonts.ready);
      const elapsedMs = Math.round(performance.now() - start);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      const direction = await page.locator(selector).first().evaluate(e => getComputedStyle(e).direction);
      const axe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      const screenshot = `${name}-${width}.png`;
      await page.screenshot({path:path.join(output,screenshot),fullPage:true});
      results.push({screen:name,width,elapsedMs,overflow,direction,screenshot,
        violations:axe.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,
          targets:v.nodes.map(n=>n.target)})),
        incomplete:axe.incomplete.map(v=>v.id),network:[...network]});
    }
  } catch(e) {
    const screenshot = `${name}-failure.png`;
    await page.screenshot({path:path.join(output,screenshot),fullPage:true}).catch(()=>{});
    errors.push({screen:name,type:e.name,screenshot});
  }
  finally {await page.close();}
}
try {
  const owner = await browser.newContext({locale:'he-IL'});
  await authenticate(owner,credentials);
  for (const name of ['action_field_dashboard','action_field_service_leads','action_field_clients_open',
      'action_field_tasks','action_field_today','action_field_contractor_rates','action_field_guide',
      'action_field_owner_dashboard']) {
    const rows = await rpc(owner,'ir.model.data','search_read',[[['module','=','field_work_photos'],['name','=',name]]],{fields:['res_id']});
    if (!rows.length) {errors.push({screen:name,type:'Missing action'});continue;}
    await audit(owner,name,`/odoo/action-${rows[0].res_id}`,'.o_action_manager .o_content');
  }
  const contractor = await browser.newContext({locale:'he-IL'});
  await authenticate(contractor,credentials.contractors[0]);
  await audit(contractor,'contractor-list','/my/field-work','.o_field_portal');
  const list = await contractor.request.get(base+'/my/field-work');
  const links = [...(await list.text()).matchAll(/href="(\/my\/field-work\/\d+)"/g)];
  if (links.length) await audit(contractor,'contractor-report',links[0][1],'.o_field_portal');
  else errors.push({screen:'contractor-report',type:'No assigned synthetic job'});
  const guest = await browser.newContext({locale:'he-IL'});
  await audit(guest,'login','/web/login','form.oe_login_form');
} finally {
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify({results,errors,
    note:'Viewport emulation; no physical phone, screen reader or live integration verification.'},null,2));
  await browser.close();
}
const failed = errors.length || results.some(r=>r.overflow || r.violations.some(v=>['critical','serious'].includes(v.impact)));
console.log(JSON.stringify({screens:results.length,errors:errors.length,failed:Boolean(failed)}));
if (failed) process.exitCode=1;
