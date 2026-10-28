// Panel JS ni soxta DOM'da ishga tushirib tekshiradi (haqiqiy brauzer emas).
// Ishga tushirish:
//   py -3.11 tests/ui/make_data.py
//   node tests/ui/panel_smoke.js
const fs = require("fs"), vm = require("vm");
const CODE = fs.readFileSync(require("path").join(__dirname, "..", "..", "app", "static", "js", "panel.js"), "utf8");
const DATA = JSON.parse(fs.readFileSync(require("path").join(__dirname, "data.json"), "utf8"));

class FNode { constructor(){ this.parentNode = null; this.childNodes = []; } get firstChild(){ return this.childNodes[0] || null; } }
class FText extends FNode { constructor(t){ super(); this.data = String(t); } get textContent(){ return this.data; } }
class FEl extends FNode {
  constructor(tag){ super(); this.tagName = tag.toUpperCase(); this.attributes = {}; this.className = ""; this.listeners = {}; this._value = ""; this.checked = false; this.disabled = false; this.hidden = false; this.style = {};
    const self = this; this.classList = { add: c => { const s = new Set(self.className.split(/\s+/).filter(Boolean)); s.add(c); self.className = [...s].join(" "); }, remove: c => { self.className = self.className.split(/\s+/).filter(x => x && x !== c).join(" "); }, toggle: c => { self.className.split(/\s+/).includes(c) ? self.classList.remove(c) : self.classList.add(c); }, contains: c => self.className.split(/\s+/).includes(c) }; }
  get value(){ return this._value; }
  set value(v){ if (this.tagName === "SELECT") { const opts = this.childNodes.filter(c => c.tagName === "OPTION"); this._value = opts.some(o => o._value === String(v)) ? String(v) : (opts.length ? "" : String(v)); } else this._value = String(v); }
  appendChild(c){ if (c.parentNode) c.parentNode.removeChild(c); c.parentNode = this; this.childNodes.push(c); return c; }
  removeChild(c){ this.childNodes = this.childNodes.filter(x => x !== c); c.parentNode = null; }
  replaceChildren(...n){ this.childNodes.forEach(c => c.parentNode = null); this.childNodes = []; n.forEach(x => this.appendChild(x)); }
  setAttribute(k, v){ this.attributes[k] = String(v); if (k === "class") this.className = String(v); if (k === "hidden") this.hidden = true; if (k === "value") this._value = String(v); }
  getAttribute(k){ return this.attributes[k]; }
  addEventListener(t, f){ (this.listeners[t] = this.listeners[t] || []).push(f); }
  async fire(t){ const r = []; for (const f of (this.listeners[t] || [])) r.push(f({ target: this })); await Promise.all(r); await tick(); }
  get textContent(){ return this.childNodes.map(c => c.textContent).join(""); }
  set textContent(t){ this.childNodes.forEach(c => c.parentNode = null); this.childNodes = []; if (t !== "" && t !== null && t !== undefined) this.appendChild(new FText(t)); }
}
const tick = () => new Promise(r => setImmediate(r));
function walk(n, fn){ fn(n); n.childNodes.forEach(c => walk(c, fn)); }
function all(root, pred){ const out = []; walk(root, n => { if (n instanceof FEl && pred(n)) out.push(n); }); return out; }
const byText = (root, tag, text) => all(root, n => n.tagName === tag.toUpperCase() && n.textContent === text)[0];
const byPh = (root, ph) => all(root, n => n.attributes.placeholder === ph)[0];
const FIELD = (root, label) => { const f = all(root, n => n.className.split(" ").includes("field") && n.childNodes[0] && n.childNodes[0].textContent === label)[0]; return f && f.childNodes[1]; };

const ADMIN_USER = { id: 1, username: "admin1", full_name: "Admin Sinov", role: "admin", school_id: null, direction: null, is_active: true };
const USERS = {
  admin: ADMIN_USER,
  director: { id: 2, username: "dir1", full_name: "Direktor", role: "director", school_id: null, direction: null, is_active: true },
  kelajak_leader: { id: 3, username: "lider1", full_name: "Lider", role: "kelajak_leader", school_id: null, direction: null, is_active: true },
  coordinator: { id: 4, username: "c_sport", full_name: "Sport Koordinator", role: "coordinator", school_id: 1, direction: "sport", is_active: true },
  school_advisor: { id: 5, username: "adv1", full_name: "Maslahatchi", role: "school_advisor", school_id: 1, direction: null, is_active: true },
  district_coordinator: { id: 6, username: "old1", full_name: "Eski Tuman", role: "district_coordinator", school_id: null, direction: null, is_active: true },
  school_coordinator: { id: 7, username: "old2", full_name: "Eski Maktab", role: "school_coordinator", school_id: 1, direction: null, is_active: true },
};
const SECTIONS = {
  admin: ["overview","reports","projects","tasks","ai","users","directions","audit"],
  director: ["overview","reports","projects","tasks","ai","users"], kelajak_leader: ["overview","reports","projects","tasks","ai","users"],
  coordinator: ["overview","reports","projects","tasks","ai"], school_advisor: ["overview","reports","projects","tasks","ai"],
  district_coordinator: ["overview","reports","projects","tasks","ai","users"], school_coordinator: ["overview","reports","projects","tasks","ai"],
};
const XSS = '<img src=x onerror=alert(1)>';
const REPORTS = [{ id: 11, school_id: 1, created_by: 4, title: XSS, period: "Oktyabr", summary: "Matn <script>alert(1)</script> bor", status: "submitted", evidence_url: "", direction: "sport", created_at: "2026-10-20T10:00:00Z" }];
const PROJECTS = [{ id: 21, school_id: 1, created_by: 4, title: "Loyiha", description: "", category: "AI", status: "in_progress", evidence_url: "", direction: "sport", created_at: "2026-10-20T10:00:00Z" }];
const TASKS = [
  { id: 31, school_id: 1, created_by: 4, title: "Sport topshirig'i", description: "", deadline: "2026-10-01T10:00:00Z", status: "pending", direction: "sport", created_at: "2026-09-20T10:00:00Z" },
  { id: 32, school_id: 1, created_by: 3, title: "Umumiy topshiriq", description: "", deadline: null, status: "pending", direction: null, created_at: "2026-09-20T10:00:00Z" },
];

function makeEnv(role, opts = {}) {
  const calls = [], redirects = [], ls = new Map();
  if (!opts.noToken) ls.set("maktab_token", "tok");
  const ids = {}; ["boot","app","nav","view","pageTitle","pageSub","roleBadge","userName","userRole","logoutBtn","menuBtn","sidebar","notice"].forEach(i => ids[i] = new FEl("div"));
  ids.app.hidden = true;
  const docL = {};
  const body = new FEl("body");
  const document = { createElement: t => new FEl(t), createTextNode: t => new FText(t), getElementById: i => ids[i], body, addEventListener: (t, f) => (docL[t] = docL[t] || []).push(f) };
  const winL = {};
  const window = { location: { hash: "", replace: u => redirects.push(u) }, addEventListener: (t, f) => (winL[t] = winL[t] || []).push(f) };
  const json = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
  const fetch = async (path, o = {}) => {
    const method = o.method || "GET"; const bodyJson = o.body ? JSON.parse(o.body) : undefined;
    calls.push({ path, method, body: bodyJson });
    if (opts.unauthorized) return json({ detail: "x" }, 401);
    const p = path.split("?")[0];
    if (p === "/auth/me") return json(USERS[role]);
    if (p === "/directions") return json(DATA.dirs);
    if (p === "/schools") return json([{ id: 1, name: "Sinov maktabi", district: "", address: "", is_active: true, created_at: "" }]);
    if (p === "/dashboard/summary") return json({ schools_count: 1, active_schools_count: 1, users_count: 7, reports_count: 2, projects_count: 1, tasks_pending_count: 2, tasks_completed_count: 3 });
    if (p === "/ai/overview") return json(DATA.overview);
    if (p === "/ai/report") return json(DATA.week);
    if (p === "/ai/analyze") return json({ summary: "S", strengths: ["a"], risks: ["b"], recommendations: ["c"], limitations: ["d"] });
    if (p === "/reports" && method === "GET") return json(REPORTS);
    if (p === "/projects" && method === "GET") return json(PROJECTS);
    if (p === "/tasks" && method === "GET") return json(TASKS);
    if (p === "/users" && method === "GET") return json(Object.values(USERS));
    if (p === "/admin/audit-logs") return json([{ id: 1, user_id: 1, action: "login", entity_type: "user", entity_id: 1, details: XSS, created_at: "2026-10-20T10:00:00Z" }]);
    if (opts.failWrite && method !== "GET") return json({ detail: "Server xatosi: sinov" }, 422);
    return json({ ok: true }, method === "POST" ? 201 : 200);
  };
  const sandbox = { document, window, localStorage: { getItem: k => ls.has(k) ? ls.get(k) : null, setItem: (k, v) => ls.set(k, v), removeItem: k => ls.delete(k) }, fetch, navigator: {}, setTimeout: (f) => 0, console, Promise, Object, Array, JSON, Date, Number, String, isNaN, encodeURIComponent };
  vm.runInNewContext(CODE, sandbox);
  const start = async () => { for (const f of docL.DOMContentLoaded || []) await f(); await tick(); };
  const go = async hash => { window.location.hash = hash; for (const f of winL.hashchange || []) await f(); await tick(); };
  return { ids, calls, redirects, ls, start, go, body };
}

let pass = 0, fail = 0;
const ok = (c, msg) => { if (c) { pass++; console.log("  PASSED", msg); } else { fail++; console.log("  FAILED", msg); } };

(async () => {
  console.log("== har bir rol: barcha bo'limlar ==");
  for (const role of Object.keys(USERS)) {
    const e = makeEnv(role); await e.start();
    ok(!e.ids.app.hidden && e.ids.boot.hidden, `${role}: panel ochildi`);
    ok(e.body.attributes["data-role"] === role, `${role}: data-role o'rnatildi`);
    const navLinks = all(e.ids.nav, n => n.tagName === "A").filter(a => a.attributes.href.startsWith("#"));
    ok(navLinks.length === SECTIONS[role].length, `${role}: menyu ${navLinks.length} ta bo'lim`);
    for (const s of SECTIONS[role]) {
      await e.go("#" + s);
      const text = e.ids.view.textContent;
      ok(text.length > 20 && e.ids.notice.textContent === "", `${role}: #${s} chizildi, xatosiz`);
    }
    if (role === "admin") ok(all(e.ids.nav, n => n.tagName === "A" && n.attributes.href === "/admin").length === 1, "admin: eski sahifa havolasi bor");
    // ruxsatsiz bo'limga o'tish "overview" ga qaytarilishi kerak
    if (!SECTIONS[role].includes("audit")) { await e.go("#audit"); ok(e.ids.pageTitle.textContent === "Umumiy ko'rinish", `${role}: #audit ruxsatsiz, umumiy ko'rinishga qaytdi`); }
  }

  console.log("== xavfsizlik ==");
  const CODE_NO_COMMENTS = CODE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(/.test(CODE_NO_COMMENTS), "panel.js da xavfli DOM API ishlatilmagan (izohlarsiz kod)");
  { const e = makeEnv("coordinator"); await e.start(); await e.go("#reports");
    ok(e.ids.view.textContent.includes(XSS), "XSS matni oddiy matn sifatida ko'rsatildi");
    ok(all(e.ids.view, n => n.tagName === "IMG" || n.tagName === "SCRIPT").length === 0, "XSS uchun IMG/SCRIPT elementi yaratilmadi"); }
  { const e = makeEnv("admin"); await e.start(); await e.go("#audit"); ok(all(e.ids.view, n => n.tagName === "IMG").length === 0, "audit tafsiloti ham matn sifatida"); }
  { const e = makeEnv("admin", { noToken: true }); await e.start(); ok(e.redirects.includes("/login"), "token yo'q: /login ga yo'naltirildi"); }
  { const e = makeEnv("admin", { unauthorized: true }); await e.start(); ok(e.redirects.includes("/login") && !e.ls.has("maktab_token"), "401: token o'chirildi va /login ga yo'naltirildi"); }

  console.log("== amallar ==");
  { // koordinator hisobot yuboradi
    const e = makeEnv("coordinator"); await e.start(); await e.go("#reports");
    ok(!!byText(e.ids.view, "button", "Hisobotni yuborish"), "koordinator: hisobot formasi bor");
    ok(!byText(e.ids.view, "button", "Qabul"), "koordinator: tekshirish tugmasi yo'q");
    byPh(e.ids.view, "Hisobot sarlavhasi")._value = "Sport hisoboti";
    byPh(e.ids.view, "Masalan: 2026-oktyabr, 2-hafta")._value = "Oktyabr";
    all(e.ids.view, n => n.tagName === "TEXTAREA")[0]._value = "Bajarilgan ishlar haqida batafsil matn.";
    await byText(e.ids.view, "button", "Hisobotni yuborish").fire("click");
    const c = e.calls.find(x => x.method === "POST" && x.path === "/reports");
    ok(c && c.body.title === "Sport hisoboti" && c.body.period === "Oktyabr" && c.body.summary.startsWith("Bajarilgan"), "hisobot to'g'ri JSON bilan yuborildi");
  }
  { // maslahatchi va rahbariyat: forma ko'rinishi
    const e = makeEnv("school_advisor"); await e.start(); await e.go("#projects"); ok(!!byText(e.ids.view, "button", "Loyihani qo'shish"), "maslahatchi: loyiha formasi bor");
    const m = makeEnv("kelajak_leader"); await m.start(); await m.go("#projects"); ok(!byText(m.ids.view, "button", "Loyihani qo'shish"), "lider: loyiha formasi yo'q (faqat ko'radi)");
  }
  { // lider topshiriq beradi
    const e = makeEnv("kelajak_leader"); await e.start(); await e.go("#tasks");
    byPh(e.ids.view, "Topshiriq nomi")._value = "Media uchun topshiriq";
    const dirSel = FIELD(e.ids.view, "Yo'nalish"); dirSel.value = "media";
    const dl = all(e.ids.view, n => n.attributes.type === "datetime-local")[0]; dl._value = "2026-11-01T10:00";
    await byText(e.ids.view, "button", "Topshiriq yaratish").fire("click");
    const c = e.calls.find(x => x.method === "POST" && x.path === "/tasks");
    ok(c && !("school_id" in c.body) && c.body.direction === "media" && /^2026-11-01T/.test(c.body.deadline), "lider topshirig'i maktab ID'siz, yo'nalish va muddat bilan ketdi");
    ok(!FIELD(e.ids.view, "Maktab"), "topshiriq formasida maktab maydoni yo'q");
    dirSel.value = ""; await byText(e.ids.view, "button", "Topshiriq yaratish").fire("click");
    const c2 = e.calls.filter(x => x.method === "POST" && x.path === "/tasks")[1];
    ok(c2 && !("direction" in c2.body), "yo'nalish tanlanmasa umumiy topshiriq (direction yuborilmaydi)");
  }
  { // koordinator topshiriq holati
    const e = makeEnv("coordinator"); await e.start(); await e.go("#tasks");
    const rows = all(e.ids.view, n => n.tagName === "TR").slice(1);
    const sportRow = rows.find(r => r.textContent.includes("Sport topshirig'i")), umbrella = rows.find(r => r.textContent.includes("Umumiy topshiriq"));
    ok(all(sportRow, n => n.tagName === "SELECT").length === 1, "koordinator: o'z yo'nalishi topshirig'ida holat tanlagichi bor");
    ok(all(umbrella, n => n.tagName === "SELECT").length === 0, "koordinator: umumiy topshiriqda holat tanlagichi yo'q");
    const sel = all(sportRow, n => n.tagName === "SELECT")[0]; sel.value = "completed"; await sel.fire("change");
    ok(!!e.calls.find(x => x.method === "PATCH" && x.path === "/tasks/31" && x.body.status === "completed"), "holat o'zgarishi PATCH sifatida ketdi");
    const m = makeEnv("kelajak_leader"); await m.start(); await m.go("#tasks");
    ok(all(m.ids.view, n => n.tagName === "TR").slice(1).every(r => all(r, n => n.tagName === "SELECT").length === 1), "lider: barcha topshiriqlarda holat tanlagichi bor");
  }
  { // hisobotni tekshirish
    const e = makeEnv("kelajak_leader"); await e.start(); await e.go("#reports");
    await byText(e.ids.view, "button", "Qabul").fire("click");
    const okBtn = byText(e.body, "button", "Tasdiqlash"); ok(!!okBtn, "tekshirish oynasi ochildi");
    await okBtn.fire("click");
    const c = e.calls.find(x => x.method === "PATCH" && x.path === "/reports/11/review");
    ok(c && c.body.status === "reviewed" && c.body.review_note === "", "hisobot tekshiruvi to'g'ri JSON bilan ketdi");
  }
  { // admin foydalanuvchi yaratadi
    const e = makeEnv("admin"); await e.start(); await e.go("#users");
    byPh(e.ids.view, "kamida 3 belgi")._value = "yangi1"; byPh(e.ids.view, "Ism familiya")._value = "Yangi Koordinator"; byPh(e.ids.view, "kamida 12 belgi")._value = "Sinov-parol-12345";
    const role = FIELD(e.ids.view, "Rol"), dirF = all(e.ids.view, n => n.className.includes("field") && n.childNodes[0] && n.childNodes[0].textContent === "Yo'nalish")[0];
    ok(role.value === "coordinator" && !dirF.hidden && !FIELD(e.ids.view, "Maktab"), "koordinator tanlanganda faqat yo'nalish maydoni ko'rinadi (maktab yo'q)");
    dirF.childNodes[1].value = "ecology";
    await byText(e.ids.view, "button", "Foydalanuvchi yaratish").fire("click");
    let c = e.calls.find(x => x.method === "POST" && x.path === "/admin/users");
    ok(c && c.body.role === "coordinator" && !("school_id" in c.body) && c.body.direction === "ecology" && c.body.username === "yangi1", "koordinator maktab ID'siz, yo'nalish bilan yaratildi");
    // yaratilgach ko'rinish qayta chiziladi (forma tozalanadi): elementlarni qayta olamiz
    const q = (label) => all(e.ids.view, n => n.className.includes("field") && n.childNodes[0] && n.childNodes[0].textContent === label)[0];
    ok(byPh(e.ids.view, "kamida 3 belgi")._value === "", "yaratilgach forma tozalandi");
    const role2 = q("Rol").childNodes[1], dirF2 = q("Yo'nalish");
    byPh(e.ids.view, "kamida 3 belgi")._value = "lider2"; byPh(e.ids.view, "Ism familiya")._value = "Yangi Lider"; byPh(e.ids.view, "kamida 12 belgi")._value = "Sinov-parol-12345";
    role2.value = "kelajak_leader"; await role2.fire("change");
    ok(dirF2.hidden, "lider tanlanganda yo'nalish maydoni yashirildi");
    await byText(e.ids.view, "button", "Foydalanuvchi yaratish").fire("click");
    c = e.calls.filter(x => x.method === "POST" && x.path === "/admin/users")[1];
    ok(c && c.body.role === "kelajak_leader" && !("school_id" in c.body) && c.body.direction === null, "lider uchun school_id yuborilmadi, direction null");
    const role3 = all(e.ids.view, n => n.tagName === "SELECT").find(n => n.childNodes.some(o => o._value === "school_advisor"));
    role3.value = "school_advisor"; await role3.fire("change");
    const dirF3 = q("Yo'nalish");
    ok(dirF3.hidden && !q("Maktab"), "maslahatchi: yo'nalish ham, maktab ham so'ralmaydi");
  }
  { // admin foydalanuvchini tahrirlaydi (o'zini va adminni cheklash)
    const e = makeEnv("admin"); await e.start(); await e.go("#users");
    const rows = all(e.ids.view, n => n.tagName === "TR").slice(1);
    const adminRow = rows.find(r => r.textContent.includes("admin1")), coordRow = rows.find(r => r.textContent.includes("c_sport"));
    await byText(adminRow, "button", "Tahrirlash").fire("click");
    ok(!!all(e.body, n => n.textContent === "Administrator rolini bu yerda o'zgartirib bo'lmaydi.").length, "admin tahriri: rol o'zgartirib bo'lmasligi ko'rsatildi");
    const chk = all(e.body, n => n.attributes.type === "checkbox")[0]; ok(chk.disabled, "admin o'zini faolsizlantira olmaydi (checkbox o'chirilgan)");
    await byText(e.body, "button", "Saqlash").fire("click");
    let c = e.calls.find(x => x.method === "PATCH" && x.path === "/admin/users/1");
    ok(c && !("role" in c.body) && !("is_active" in c.body) && c.body.full_name === "Admin Sinov", "admin PATCH: role va is_active yuborilmadi");
    const overlay = e.body.childNodes[0]; if (overlay) e.body.removeChild(overlay);
    await byText(coordRow, "button", "Tahrirlash").fire("click");
    await byText(e.body, "button", "Saqlash").fire("click");
    c = e.calls.find(x => x.method === "PATCH" && x.path === "/admin/users/4");
    ok(c && c.body.role === "coordinator" && !("school_id" in c.body) && c.body.direction === "sport" && c.body.is_active === true, "koordinator PATCH: rol, yo'nalish va faollik to'g'ri (maktab ID'siz)");
  }
  { // AI markazi
    const e = makeEnv("kelajak_leader"); await e.start(); await e.go("#ai");
    ok(e.ids.view.textContent.includes("API kalit talab qilinmaydi"), "AI: mahalliy rejim izohi ko'rsatildi");
    await byText(e.ids.view, "button", "Haftalik hisobot").fire("click");
    ok(all(e.ids.view, n => n.tagName === "PRE").some(p => p.textContent.includes("Haftalik hisobot")), "AI: haftalik hisobot matni chiqdi");
    ok(!!e.calls.find(x => x.path === "/ai/report?period=week"), "AI: to'g'ri endpoint chaqirildi");
    all(e.ids.view, n => n.tagName === "TEXTAREA")[0]._value = "Bu hisobot matni juda uzun emas lekin yetarli.";
    await byText(e.ids.view, "button", "Matnni tahlil qilish").fire("click");
    ok(e.ids.view.textContent.includes("Kuchli tomonlar"), "AI: matn tahlili natijasi chiqdi");
  }
  { // server xatosi bildirishnomada ko'rinadi
    const e = makeEnv("coordinator", { failWrite: true }); await e.start(); await e.go("#reports");
    await byText(e.ids.view, "button", "Hisobotni yuborish").fire("click");
    ok(e.ids.notice.textContent.includes("Server xatosi: sinov") && e.ids.notice.textContent !== "", "server xatosi foydalanuvchiga ko'rsatildi");
  }
  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch(err => { console.error("HARNESS XATO:", err); process.exit(2); });
