const REPORT_URL = 'results/fund_ops_daily_report.json';
const page = document.body.dataset.page;
const esc = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = value => Number(value ?? 0).toLocaleString(undefined,{maximumFractionDigits:2});
const nav = () => {
  const links = [['dashboard','Dashboard','fund_ops_dashboard.html'],['accounts','Accounts','fund_ops_accounts.html'],['ledger','Ledger','fund_ops_ledger.html'],['reconciliation','Reconciliation','fund_ops_reconciliation.html'],['portfolio','Portfolio Close','fund_ops_portfolio.html'],['risk','Risk & Paper','fund_ops_risk.html']];
  document.querySelector('#nav').innerHTML = links.map(([id,label,href]) => `<a class="${page===id?'active':''}" href="${href}">${label}</a>`).join('');
};
const row = cells => `<tr>${cells.map(cell=>`<td>${cell}</td>`).join('')}</tr>`;
async function report(){const response=await fetch(REPORT_URL);if(!response.ok)throw Error('no daily-close report');return response.json()}
function setState(r){const status=r.status==='clean'?'ok':'warn';document.querySelector('#state').innerHTML=`<span class="${status}">${esc(r.status).toUpperCase()}</span> · ${esc(r.report_date)} · data as of ${esc(r.data_as_of)}`}
function empty(body, columns, message){body.innerHTML=`<tr><td colspan="${columns}" class="empty">${esc(message)}</td></tr>`}
nav();
