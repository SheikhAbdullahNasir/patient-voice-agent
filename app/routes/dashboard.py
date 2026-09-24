"""Read-only dashboard: one HTML page that loads patients from GET /patients."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Patient Registrations</title>
<style>
  body{font-family:system-ui,"Segoe UI",Arial,sans-serif;margin:0;background:#f5f7fa;color:#1f2933}
  header{background:#0b6fa4;color:#fff;padding:16px 24px}
  header h1{margin:0;font-size:20px}
  header p{margin:4px 0 0;font-size:13px;opacity:.85}
  main{padding:20px 24px}
  .bar{display:flex;gap:12px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
  input{padding:8px 10px;border:1px solid #cbd2d9;border-radius:6px;min-width:240px}
  .count{font-size:13px;color:#52606d}
  .wrap{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
  table{border-collapse:collapse;width:100%;font-size:14px}
  th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #e4e7eb;white-space:nowrap}
  th{background:#f0f4f8;font-weight:600}
  .empty{padding:24px;color:#52606d}
</style>
</head>
<body>
<header>
  <h1>Patient Registrations</h1>
  <p>Live view of records saved by the voice agent. Refreshes every 10 seconds.</p>
</header>
<main>
  <div class="bar">
    <input id="q" type="search" placeholder="Filter by name or phone...">
    <span class="count" id="count"></span>
  </div>
  <div class="wrap">
    <table><thead><tr id="head"></tr></thead><tbody id="body"></tbody></table>
    <div id="empty" class="empty" hidden>No patients found.</div>
  </div>
</main>
<script>
const fmtPhone = p => p ? "(" + p.slice(0,3) + ") " + p.slice(3,6) + "-" + p.slice(6) : "";
const fmtDob = s => { const [y, m, d] = s.split("-"); return m + "/" + d + "/" + y; };
const fmtTime = s => new Date(s).toISOString().slice(0,16).replace("T", " ");

const COLS = [
  ["Name", p => p.first_name + " " + p.last_name],
  ["Date of birth", p => fmtDob(p.date_of_birth)],
  ["Sex", p => p.sex],
  ["Phone", p => fmtPhone(p.phone_number)],
  ["Email", p => p.email || ""],
  ["Address", p => [p.address_line_1, p.address_line_2, p.city + ", " + p.state + " " + p.zip_code].filter(Boolean).join(", ")],
  ["Insurance", p => [p.insurance_provider, p.insurance_member_id].filter(Boolean).join(" / ")],
  ["Language", p => p.preferred_language],
  ["Emergency contact", p => [p.emergency_contact_name, fmtPhone(p.emergency_contact_phone)].filter(Boolean).join(" ")],
  ["Registered (UTC)", p => fmtTime(p.created_at)],
];

const head = document.getElementById("head");
COLS.forEach(([label]) => { const th = document.createElement("th"); th.textContent = label; head.appendChild(th); });

let patients = [];
let failed = false;

function render() {
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = patients.filter(p => !q || (p.first_name + " " + p.last_name + " " + p.phone_number).toLowerCase().includes(q));
  const body = document.getElementById("body");
  body.replaceChildren(...rows.map(p => {
    const tr = document.createElement("tr");
    COLS.forEach(([, f]) => { const td = document.createElement("td"); td.textContent = f(p); tr.appendChild(td); });
    return tr;
  }));
  document.getElementById("empty").hidden = rows.length > 0;
  document.getElementById("count").textContent = failed ? "Could not load patients" : rows.length + " of " + patients.length + " patients";
}

async function load() {
  try {
    const res = await fetch("/patients");
    patients = (await res.json()).data || [];
    failed = false;
  } catch (e) { failed = true; }
  render();
}

document.getElementById("q").addEventListener("input", render);
load();
setInterval(load, 10000);
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return PAGE