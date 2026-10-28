/* MAKTAB AI CONTROL — rol bo'yicha panel.
 * Barcha dinamik matnlar textContent orqali qo'yiladi (innerHTML ishlatilmaydi).
 */
(function () {
  "use strict";

  var TOKEN_KEY = "maktab_token";
  var LEGACY_TOKEN_KEY = "tuman_admin_token";

  var MANAGER_ROLES = ["admin", "director", "kelajak_leader", "district_coordinator"];
  var SCHOOL_ROLES = ["coordinator", "school_advisor", "school_coordinator"];

  var ROLE_CONFIG = {
    admin: {
      label: "Administrator",
      subtitle: "Tizim, foydalanuvchilar, yo'nalishlar va xavfsizlik",
      sections: ["overview", "reports", "projects", "tasks", "ai", "users", "directions", "audit", "telegram"],
      quick: [["#users", "Foydalanuvchi qo'shish"], ["#directions", "Yo'nalishlar"], ["#audit", "Audit jurnali"]]
    },
    director: {
      label: "Maktab direktori",
      subtitle: "Maktab faoliyatining umumiy ko'rinishi va nazorati",
      sections: ["overview", "reports", "projects", "tasks", "ai", "users", "telegram"],
      quick: [["#reports", "Hisobotlarni tekshirish"], ["#tasks", "Topshiriq berish"], ["#ai", "AI hisobot"]]
    },
    kelajak_leader: {
      label: "Kelajak lideri",
      subtitle: "Yetti yo'nalishni muvofiqlashtirish va kechikishlarni nazorat qilish",
      sections: ["overview", "reports", "projects", "tasks", "ai", "users", "telegram"],
      quick: [["#tasks", "Topshiriq berish"], ["#reports", "Hisobotlarni tekshirish"], ["#ai", "Haftalik hisobot"]]
    },
    coordinator: {
      label: "Koordinator",
      subtitle: "O'z yo'nalishingiz bo'yicha topshiriq, loyiha va hisobotlar",
      sections: ["overview", "reports", "projects", "tasks", "ai", "telegram"],
      quick: [["#reports", "Hisobot yuborish"], ["#projects", "Loyiha qo'shish"], ["#tasks", "Topshiriqlarim"]]
    },
    school_advisor: {
      label: "Maktab maslahatchisi",
      subtitle: "Tashabbuslar, tadbirlar va o'zingiz yuborgan hisobotlar",
      sections: ["overview", "reports", "projects", "tasks", "ai", "telegram"],
      quick: [["#reports", "Hisobot yuborish"], ["#projects", "Tashabbus qo'shish"], ["#tasks", "Topshiriqlarim"]]
    },
    district_coordinator: {
      label: "Tuman koordinatori (eski rol)",
      subtitle: "Barcha maktablar bo'yicha ko'rinish",
      sections: ["overview", "reports", "projects", "tasks", "ai", "users", "telegram"],
      quick: [["#reports", "Hisobotlarni tekshirish"], ["#tasks", "Topshiriq berish"], ["#ai", "AI hisobot"]]
    },
    school_coordinator: {
      label: "Maktab koordinatori (eski rol)",
      subtitle: "O'z maktabingiz bo'yicha ko'rinish",
      sections: ["overview", "reports", "projects", "tasks", "ai", "telegram"],
      quick: [["#reports", "Hisobot yuborish"], ["#projects", "Loyiha qo'shish"], ["#tasks", "Topshiriqlar"]]
    }
  };

  var SECTION_TITLES = {
    overview: ["Umumiy ko'rinish", "So'nggi holat va AI xulosalari"],
    reports: ["Hisobotlar", "Yuborish, ko'rish va tekshirish"],
    projects: ["Loyihalar va tashabbuslar", "Holatni kuzatish"],
    tasks: ["Topshiriqlar", "Muddatlar va bajarilish holati"],
    ai: ["AI markazi", "Statistik tahlil, tavsiyalar va hisobotlar"],
    users: ["Foydalanuvchilar", "Rollar, maktab va yo'nalishlar"],
    directions: ["Yo'nalishlar", "Kengash yo'nalishlarini sozlash"],
    audit: ["Audit jurnali", "Muhim amallar tarixi"],
    telegram: ["Telegram bog\'lash", "Telegram akkauntingizni tizimga ulash"]
  };

  var NAV_ICONS = {
    overview: "◈", reports: "▤", projects: "◇", tasks: "✓", ai: "✦", users: "☻", directions: "⌘", audit: "⛨",
    telegram: "✉"
  };

  var STATUS = {
    report: {
      submitted: ["Yuborilgan", "info"],
      reviewed: ["Qabul qilingan", "good"],
      needs_revision: ["Qayta ko'rish kerak", "warn"]
    },
    project: {
      planned: ["Rejalashtirilgan", "info"],
      in_progress: ["Jarayonda", "warn"],
      completed: ["Yakunlangan", "good"],
      paused: ["To'xtatilgan", "bad"]
    },
    task: {
      pending: ["Kutilmoqda", "info"],
      in_progress: ["Jarayonda", "warn"],
      completed: ["Bajarilgan", "good"],
      cancelled: ["Bekor qilingan", "bad"]
    }
  };

  var state = { me: null, directions: [], dirMap: {}, current: "overview" };

  /* ================= yordamchi funksiyalar ================= */

  function isManager() { return MANAGER_ROLES.indexOf(state.me.role) !== -1; }
  function isSchoolRole() { return SCHOOL_ROLES.indexOf(state.me.role) !== -1; }

  function h(tag, props) {
    var el = document.createElement(tag);
    var afterValue;
    var hasValue = false;

    if (props) {
      Object.keys(props).forEach(function (k) {
        var v = props[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") el.className = v;
        else if (k === "text") el.textContent = v;
        else if (k === "value") { hasValue = true; afterValue = v; }
        else if (k === "checked") el.checked = !!v;
        else if (k === "disabled") el.disabled = !!v;
        else if (k.slice(0, 2) === "on" && typeof v === "function") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? "" : String(v));
      });
    }

    for (var i = 2; i < arguments.length; i++) appendChild(el, arguments[i]);

    // select uchun qiymat variantlar qo'shilgandan keyin o'rnatiladi
    if (hasValue) el.value = afterValue;
    return el;
  }

  function appendChild(parent, child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) { child.forEach(function (c) { appendChild(parent, c); }); return; }
    if (typeof child === "object") parent.appendChild(child);
    else parent.appendChild(document.createTextNode(String(child)));
  }

  function byId(id) { return document.getElementById(id); }

  function formatDate(value) {
    if (!value) return "—";
    var d = new Date(value);
    if (isNaN(d.getTime())) return "—";
    var pad = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function dirName(code) {
    if (!code) return "Umumiy";
    return state.dirMap[code] || code;
  }

  function badge(kind, value) {
    var pair = (STATUS[kind] || {})[value] || [String(value), ""];
    return h("span", { class: "badge " + pair[1], text: pair[0] });
  }

  function notify(message, type) {
    var box = byId("notice");
    box.replaceChildren();
    if (!message) return;
    box.appendChild(h("div", { class: "notice " + (type || "info"), text: message }));
    if (type === "ok") {
      setTimeout(function () { if (box.firstChild && box.firstChild.textContent === message) box.replaceChildren(); }, 5000);
    }
  }

  function errorMessage(data, status) {
    if (data && typeof data.detail === "string") return data.detail;
    if (data && Array.isArray(data.detail)) {
      return data.detail.map(function (d) {
        var where = d.loc && d.loc.length > 1 ? d.loc.slice(1).join(".") + ": " : "";
        return where + d.msg;
      }).join("; ");
    }
    return "Xatolik yuz berdi (HTTP " + status + ").";
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    window.location.replace("/login");
  }

  async function api(path, options) {
    options = options || {};
    var token = localStorage.getItem(TOKEN_KEY);
    if (!token) { logout(); throw new Error("Kirish talab qilinadi."); }

    var headers = { "Authorization": "Bearer " + token };
    var body;
    if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.json);
    }

    var res = await fetch(path, { method: options.method || "GET", headers: headers, body: body });

    if (res.status === 401) { logout(); throw new Error("Sessiya tugadi. Qayta kiring."); }

    var data = null;
    try { data = await res.json(); } catch (e) { data = null; }

    if (!res.ok) throw new Error(errorMessage(data, res.status));
    return data;
  }

  function card(title) {
    var children = Array.prototype.slice.call(arguments, 1);
    var head = title ? h("h2", { text: title }) : null;
    return h.apply(null, ["div", { class: "card" }, head].concat(children));
  }

  function field(label, control, full) {
    return h("div", { class: "field" + (full ? " full" : "") }, h("label", { text: label }), control);
  }

  function selectEl(options, value, extra) {
    var props = Object.assign({ class: "select" }, extra || {});
    var opts = options.map(function (o) { return h("option", { value: o[0], text: o[1] }); });
    var el = h.apply(null, ["select", props].concat(opts));
    if (value !== undefined && value !== null) el.value = value;
    return el;
  }

  function table(columns, rows, renderRow, emptyText) {
    if (!rows.length) return h("div", { class: "empty", text: emptyText || "Ma'lumot topilmadi." });
    var head = h("tr", null, columns.map(function (c) { return h("th", { text: c }); }));
    var body = h("tbody", null, rows.map(function (r) {
      return h("tr", null, renderRow(r).map(function (cell) {
        return h("td", null, cell);
      }));
    }));
    return h("div", { class: "table-wrap" }, h("table", null, h("thead", null, head), body));
  }

  function openModal(title, bodyEl, buttons) {
    var overlay = h("div", { class: "overlay" });
    function close() { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }
    var foot = h("div", { class: "foot" }, buttons(close));
    var modal = h("div", { class: "modal" }, h("h2", { text: title }), bodyEl, foot);
    overlay.appendChild(modal);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
    document.body.appendChild(overlay);
    return close;
  }

  async function withBusy(button, fn) {
    var old = button.textContent;
    button.disabled = true;
    try { return await fn(); }
    finally { button.disabled = false; button.textContent = old; }
  }

  function loading() {
    byId("view").replaceChildren(h("div", { class: "empty", text: "Yuklanmoqda..." }));
  }
  /* ================= Telegram akkauntini bog'lash ================= */

  async function viewTelegramLink() {
    var resultBox = h("div", {
      class: "notice info",
      text: "Telegram akkauntingizni bog'lash uchun quyidagi tugmani bosing."
    });

    var generateButton = h("button", {
      class: "btn btn-primary",
      text: "Telegram ulash kodini olish"
    });

    var codeBox = h("div");

    generateButton.addEventListener("click", function () {
      withBusy(generateButton, async function () {
        try {
          var result = await api("/auth/telegram-link-code", {
            method: "POST"
          });

          codeBox.replaceChildren(
            h("div", { class: "card" },
              h("h3", { text: "Telegram ulash kodi" }),
              h("p", {
                class: "value",
                text: result.code
              }),
              h("p", {
                class: "muted",
                text: "Kod 10 daqiqa amal qiladi."
              }),
              h("p", {
                text: result.instruction ||
                  ("Telegram botga /link " + result.code + " yuboring.")
              }),
              h("button", {
                class: "btn",
                text: "Ko'rsatmani nusxalash"
              })
            )
          );

          var copyButton = codeBox.querySelector("button");
          copyButton.addEventListener("click", async function () {
            try {
              await navigator.clipboard.writeText(
                "/link " + result.code
              );
              notify("Ko'rsatma nusxalandi.", "ok");
            } catch (e) {
              notify("Nusxalash amalga oshmadi. Kodni qo'lda ko'chiring.", "err");
            }
          });

          resultBox.textContent =
            "Kod yaratildi. Endi uni Telegram botga yuboring.";
          notify("Telegram ulash kodi yaratildi.", "ok");
        } catch (e) {
          notify(e.message || "Telegram kodini yaratib bo'lmadi.", "err");
        }
      });
    });

    byId("view").replaceChildren(
      h("div", { class: "stack" },
        card(
          "Telegram akkauntini bog'lash",
          h("p", {
            text: "1. Kod yarating. 2. Telegram botingizni oching. 3. Botga ko'rsatilgan /link buyrug'ini yuboring."
          }),
          generateButton,
          resultBox,
          codeBox
        )
      )
    );
  }
  /* ================= umumiy ko'rinish ================= */

  function statCard(label, value, tone) {
    return h("div", { class: "card stat " + (tone || "") },
      h("div", { class: "label", text: label }),
      h("div", { class: "value", text: String(value === null || value === undefined ? "—" : value) }));
  }

  function directionCard(b) {
    var rate = b.completion_rate;
    var rateText = rate === null || rate === undefined ? "ma'lumot yo'q" : rate + "%" + (b.completion_rate_reliable ? "" : " (namuna kichik)");
    return h("div", { class: "card dir-card" },
      h("div", { class: "name", text: b.name }),
      h("div", { class: "kv" }, h("span", { text: "Topshiriqlar bajarilishi" }), h("b", { text: rateText })),
      h("div", { class: "bar" }, h("span", { style: "width:" + (rate || 0) + "%" })),
      h("div", { class: "kv" }, h("span", { text: "Hisobotlar (davrda / jami)" }), h("b", { text: b.reports_recent + " / " + b.reports_total })),
      h("div", { class: "kv" }, h("span", { text: "Loyihalar" }), h("b", { text: b.projects_total })),
      h("div", { class: "kv" }, h("span", { text: "Topshiriqlar (bajarilgan / jami)" }), h("b", { text: b.tasks_completed + " / " + b.tasks_total })),
      h("div", { class: "kv" + (b.tasks_overdue ? " alert" : "") }, h("span", { text: "Muddati o'tgan" }), h("b", { text: b.tasks_overdue })));
  }

  async function viewOverview() {
    var cfg = ROLE_CONFIG[state.me.role];
    var results = await Promise.all([api("/dashboard/summary"), api("/ai/overview?window_days=30")]);
    var s = results[0];
    var ov = results[1];

    var stats = [
      statCard("Hisobotlar", s.reports_count),
      statCard("Loyihalar", s.projects_count, "neon"),
      statCard("Ochiq topshiriqlar", s.tasks_pending_count),
      statCard("Bajarilgan topshiriqlar", s.tasks_completed_count, "good")
    ];
    if (isManager()) {
      stats.push(statCard("Foydalanuvchilar", s.users_count));
    }

    var quick = h("div", { class: "row" }, cfg.quick.map(function (q, i) {
      return h("a", { class: "btn" + (i === 0 ? " btn-primary" : ""), href: q[0], text: q[1] });
    }));

    var hero = h("div", { class: "hero" },
      h("h2", { text: "Salom, " + state.me.full_name }),
      h("p", { text: cfg.subtitle + "." + (state.me.direction ? " Yo'nalishingiz: " + dirName(state.me.direction) + "." : "") }),
      quick);

    var dirs = ov.directions.length
      ? h("div", { class: "grid grid-dirs" }, ov.directions.map(directionCard))
      : h("div", { class: "empty", text: "Ko'rsatish uchun yo'nalish ma'lumoti yo'q." });

    var findings = card("AI xulosalari",
      h("ul", { class: "clean" }, ov.findings.map(function (t) { return h("li", { text: t }); })),
      h("p", { class: "muted small", text: ov.note }));

    var overdue = card("Muddati o'tgan topshiriqlar",
      table(["Topshiriq", "Yo'nalish", "Kechikish"], ov.overdue_tasks.slice(0, 5), function (t) {
        return [t.title, t.direction_name, t.days_overdue + " kun"];
      }, "Muddati o'tgan topshiriq yo'q."));

    byId("view").replaceChildren(h("div", { class: "stack" },
      hero,
      h("div", { class: "grid grid-stats" }, stats),
      h("h2", { text: "Yo'nalishlar kesimi" }),
      dirs,
      h("div", { class: "grid", style: "grid-template-columns:repeat(auto-fit,minmax(300px,1fr))" }, findings, overdue)));
  }

  /* ================= hisobotlar ================= */

  function reviewDialog(report, status, reload) {
    var note = h("textarea", { class: "textarea", placeholder: "Izoh (ixtiyoriy)", maxlength: "3000" });
    var title = status === "reviewed" ? "Hisobotni qabul qilish" : "Qayta ko'rishga qaytarish";
    openModal(title, field("Izoh", note), function (close) {
      var ok = h("button", { class: "btn btn-primary", text: "Tasdiqlash" });
      ok.addEventListener("click", function () {
        withBusy(ok, async function () {
          try {
            await api("/reports/" + report.id + "/review", { method: "PATCH", json: { status: status, review_note: note.value } });
            close();
            notify("Hisobot holati yangilandi.", "ok");
            reload();
          } catch (e) { notify(e.message, "err"); }
        });
      });
      var cancel = h("button", { class: "btn", text: "Bekor qilish" });
      cancel.addEventListener("click", close);
      return [cancel, ok];
    });
  }

  async function viewReports() {
    var rows = await api("/reports");
    var reload = function () { route(); };

    var list = card("Hisobotlar ro'yxati",
      table(["Sarlavha", "Davr", "Yo'nalish", "Holat", "Sana", ""], rows, function (r) {
        var actions = [];
        if (isManager()) {
          var accept = h("button", { class: "btn btn-sm", text: "Qabul" });
          accept.addEventListener("click", function () { reviewDialog(r, "reviewed", reload); });
          var back = h("button", { class: "btn btn-sm btn-danger", text: "Qayta" });
          back.addEventListener("click", function () { reviewDialog(r, "needs_revision", reload); });
          actions = [accept, back];
        }
        var detail = h("button", { class: "btn btn-sm", text: "Ko'rish" });
        detail.addEventListener("click", function () {
          var body = h("div", null,
            h("p", { class: "muted small", text: r.period + " • " + formatDate(r.created_at) }),
            h("pre", { class: "report", text: r.summary }),
            r.evidence_url ? h("p", { class: "small", text: "Dalil: " + r.evidence_url }) : null);
          openModal(r.title, body, function (close) {
            var b = h("button", { class: "btn", text: "Yopish" });
            b.addEventListener("click", close);
            return [b];
          });
        });
        return [r.title, r.period, dirName(r.direction), badge("report", r.status), formatDate(r.created_at),
          h("div", { class: "actions" }, [detail].concat(actions))];
      }, "Hisobot hali yo'q."));

    var blocks = [];

    if (isSchoolRole()) {
      var title = h("input", { class: "input", maxlength: "200", placeholder: "Hisobot sarlavhasi" });
      var period = h("input", { class: "input", maxlength: "100", placeholder: "Masalan: 2026-oktyabr, 2-hafta" });
      var summary = h("textarea", { class: "textarea", maxlength: "10000", placeholder: "Bajarilgan ishlar, ishtirokchilar, natijalar..." });
      var evidence = h("input", { class: "input", maxlength: "1000", placeholder: "https://... (foto yoki hujjat havolasi)" });
      var send = h("button", { class: "btn btn-primary", text: "Hisobotni yuborish" });
      send.addEventListener("click", function () {
        withBusy(send, async function () {
          try {
            await api("/reports", { method: "POST", json: { title: title.value, period: period.value, summary: summary.value, evidence_url: evidence.value } });
            notify("Hisobot yuborildi.", "ok");
            reload();
          } catch (e) { notify(e.message, "err"); }
        });
      });
      blocks.push(card("Yangi hisobot",
        h("div", { class: "form-grid" }, field("Sarlavha", title), field("Davr", period), field("Matn", summary, true), field("Dalil havolasi", evidence, true)),
        send));
    }

    byId("view").replaceChildren(h("div", { class: "stack" }, blocks.concat([list])));
  }

  /* ================= loyihalar ================= */

  async function viewProjects() {
    var rows = await api("/projects");
    var reload = function () { route(); };

    var list = card("Loyihalar ro'yxati",
      table(["Nomi", "Turkum", "Yo'nalish", "Holat", "Sana"], rows, function (p) {
        return [p.title, p.category, dirName(p.direction), badge("project", p.status), formatDate(p.created_at)];
      }, "Loyiha hali yo'q."));

    var blocks = [];

    if (isSchoolRole()) {
      var title = h("input", { class: "input", maxlength: "200", placeholder: "Loyiha nomi" });
      var category = h("input", { class: "input", maxlength: "100", value: "AI" });
      var desc = h("textarea", { class: "textarea", maxlength: "10000", placeholder: "Qisqacha tavsif" });
      var status = selectEl([["planned", "Rejalashtirilgan"], ["in_progress", "Jarayonda"], ["completed", "Yakunlangan"], ["paused", "To'xtatilgan"]], "planned");
      var evidence = h("input", { class: "input", maxlength: "1000", placeholder: "https://..." });
      var add = h("button", { class: "btn btn-primary", text: "Loyihani qo'shish" });
      add.addEventListener("click", function () {
        withBusy(add, async function () {
          try {
            await api("/projects", { method: "POST", json: { title: title.value, category: category.value, description: desc.value, status: status.value, evidence_url: evidence.value } });
            notify("Loyiha qo'shildi.", "ok");
            reload();
          } catch (e) { notify(e.message, "err"); }
        });
      });
      blocks.push(card("Yangi loyiha",
        h("div", { class: "form-grid" }, field("Nomi", title), field("Turkum", category), field("Holat", status), field("Dalil havolasi", evidence), field("Tavsif", desc, true)),
        add));
    }

    byId("view").replaceChildren(h("div", { class: "stack" }, blocks.concat([list])));
  }

  /* ================= topshiriqlar ================= */

  function canChangeTaskStatus(task) {
    if (isManager()) return true;
    if (state.me.role === "coordinator") return !!task.direction; // umumiy topshiriqni faqat rahbariyat o'zgartiradi
    return isSchoolRole();
  }

  async function viewTasks() {
    var rows = await api("/tasks");
    var reload = function () { route(); };
    var statusOptions = [["pending", "Kutilmoqda"], ["in_progress", "Jarayonda"], ["completed", "Bajarilgan"], ["cancelled", "Bekor qilingan"]];

    var list = card("Topshiriqlar ro'yxati",
      table(["Topshiriq", "Yo'nalish", "Muddat", "Holat", ""], rows, function (t) {
        var control = h("span", { class: "muted small", text: "—" });
        if (canChangeTaskStatus(t)) {
          var sel = selectEl(statusOptions, t.status, { "aria-label": "Holat" });
          sel.addEventListener("change", async function () {
            try {
              await api("/tasks/" + t.id, { method: "PATCH", json: { status: sel.value } });
              notify("Topshiriq holati yangilandi.", "ok");
              reload();
            } catch (e) { notify(e.message, "err"); sel.value = t.status; }
          });
          control = sel;
        }
        return [t.title, dirName(t.direction), formatDate(t.deadline), badge("task", t.status), control];
      }, "Topshiriq hali yo'q."));

    var blocks = [];

    var title = h("input", { class: "input", maxlength: "200", placeholder: "Topshiriq nomi" });
    var desc = h("textarea", { class: "textarea", maxlength: "10000", placeholder: "Tavsif" });
    var deadline = h("input", { class: "input", type: "datetime-local" });

    var dirSel = null;
    var fields = [field("Nomi", title), field("Muddat", deadline)];

    if (isManager()) {
      dirSel = selectEl([["", "Umumiy (barcha yo'nalishlar)"]].concat(state.directions.map(function (d) { return [d.code, d.name]; })), "");
      fields.push(field("Yo'nalish", dirSel));
    }
    fields.push(field("Tavsif", desc, true));

    var add = h("button", { class: "btn btn-primary", text: "Topshiriq yaratish" });
    add.addEventListener("click", function () {
      withBusy(add, async function () {
        try {
          var payload = { title: title.value, description: desc.value };
          if (deadline.value) payload.deadline = new Date(deadline.value).toISOString();
          if (isManager() && dirSel.value) payload.direction = dirSel.value;
          await api("/tasks", { method: "POST", json: payload });
          notify("Topshiriq yaratildi.", "ok");
          reload();
        } catch (e) { notify(e.message, "err"); }
      });
    });
    blocks.push(card("Yangi topshiriq", h("div", { class: "form-grid" }, fields), add));

    byId("view").replaceChildren(h("div", { class: "stack" }, blocks.concat([list])));
  }

  /* ================= AI markazi ================= */

  function overviewBlock(ov) {
    var dirs = ov.directions.length
      ? h("div", { class: "grid grid-dirs" }, ov.directions.map(directionCard))
      : h("div", { class: "empty", text: "Ko'rsatish uchun yo'nalish ma'lumoti yo'q." });

    return h("div", { class: "stack" },
      h("div", { class: "notice info", text: ov.note }),
      dirs,
      card("Aniqlangan holatlar", h("ul", { class: "clean" }, ov.findings.map(function (t) { return h("li", { text: t }); }))),
      card("Tavsiyalar", h("ul", { class: "clean" }, ov.recommendations.map(function (t) { return h("li", { text: t }); }))),
      card("Muddati o'tgan topshiriqlar",
        table(["Topshiriq", "Yo'nalish", "Muddat", "Kechikish"], ov.overdue_tasks, function (t) {
          return [t.title, t.direction_name, formatDate(t.deadline), t.days_overdue + " kun"];
        }, "Muddati o'tgan topshiriq yo'q.")),
      h("p", { class: "muted small", text: ov.limitations.join(" ") }));
  }

  async function viewAI() {
    var windowSel = selectEl([["7", "So'nggi 7 kun"], ["30", "So'nggi 30 kun"], ["90", "So'nggi 90 kun"]], "30");
    var overviewBox = h("div", null, h("div", { class: "empty", text: "Yuklanmoqda..." }));
    var reportBox = h("div");
    var textBox = h("div");

    async function loadOverview() {
      overviewBox.replaceChildren(h("div", { class: "empty", text: "Yuklanmoqda..." }));
      try {
        var ov = await api("/ai/overview?window_days=" + encodeURIComponent(windowSel.value));
        overviewBox.replaceChildren(overviewBlock(ov));
      } catch (e) { overviewBox.replaceChildren(h("div", { class: "notice err", text: e.message })); }
    }
    windowSel.addEventListener("change", loadOverview);

    function reportButton(label, period) {
      var b = h("button", { class: "btn", text: label });
      b.addEventListener("click", function () {
        withBusy(b, async function () {
          try {
            var r = await api("/ai/report?period=" + period);
            var copy = h("button", { class: "btn btn-sm", text: "Nusxa olish" });
            copy.addEventListener("click", function () {
              if (navigator.clipboard) navigator.clipboard.writeText(r.text).then(function () { notify("Matn nusxalandi.", "ok"); });
            });
            reportBox.replaceChildren(h("div", { class: "stack" }, h("div", { class: "row row-between" }, h("h3", { text: r.title }), copy), h("pre", { class: "report", text: r.text })));
          } catch (e) { notify(e.message, "err"); }
        });
      });
      return b;
    }

    var textArea = h("textarea", { class: "textarea", maxlength: "15000", placeholder: "Hisobot yoki loyiha matnini kiriting (kamida 10 belgi)..." });
    var analyze = h("button", { class: "btn btn-primary", text: "Matnni tahlil qilish" });
    analyze.addEventListener("click", function () {
      withBusy(analyze, async function () {
        try {
          var r = await api("/ai/analyze", { method: "POST", json: { text: textArea.value, context: "report" } });
          function list(title, items) {
            return h("div", null, h("h3", { text: title }), h("ul", { class: "clean" }, items.map(function (t) { return h("li", { text: t }); })));
          }
          textBox.replaceChildren(h("div", { class: "stack" },
            h("p", { text: r.summary }),
            list("Kuchli tomonlar", r.strengths),
            list("Xavf va kamchiliklar", r.risks),
            list("Tavsiyalar", r.recommendations),
            h("p", { class: "muted small", text: r.limitations.join(" ") })));
        } catch (e) { notify(e.message, "err"); }
      });
    });

    loadOverview();

    byId("view").replaceChildren(h("div", { class: "stack" },
      card("Yo'nalishlar tahlili", h("div", { class: "row" }, field("Davr", windowSel)), overviewBox),
      card("Haftalik va oylik hisobot", h("div", { class: "row" }, reportButton("Haftalik hisobot", "week"), reportButton("Oylik hisobot", "month")), reportBox),
      card("Matn tahlili", field("Matn", textArea, true), analyze, textBox)));
  }

  /* ================= foydalanuvchilar ================= */

  var ROLE_OPTIONS = [
    ["director", "Maktab direktori"],
    ["kelajak_leader", "Kelajak lideri"],
    ["coordinator", "Koordinator"],
    ["school_advisor", "Maktab maslahatchisi"]
  ];

  function roleLabel(role) {
    return (ROLE_CONFIG[role] && ROLE_CONFIG[role].label) || role;
  }

  function userFormFields(initial) {
    initial = initial || {};
    var role = selectEl(initial.extraRoleOptions ? initial.extraRoleOptions.concat(ROLE_OPTIONS) : ROLE_OPTIONS, initial.role || "coordinator");
    var dir = selectEl(state.directions.map(function (d) { return [d.code, d.name]; }), initial.direction || (state.directions.length ? state.directions[0].code : ""));
    var dirField = field("Yo'nalish", dir);

    function sync() {
      dirField.hidden = role.value !== "coordinator";
    }
    role.addEventListener("change", sync);
    sync();

    return { role: role, dir: dir, dirField: dirField };
  }

  function collectAssignment(f) {
    var out = { role: f.role.value };
    out.direction = f.role.value === "coordinator" ? f.dir.value : null;
    return out;
  }

  function editUserDialog(u, reload) {
    var isAdminTarget = u.role === "admin";
    var legacy = ROLE_OPTIONS.some(function (o) { return o[0] === u.role; }) ? null : [[u.role, roleLabel(u.role)]];
    var name = h("input", { class: "input", maxlength: "200", value: u.full_name });
    var f = userFormFields({ role: u.role, direction: u.direction, extraRoleOptions: legacy });
    var active = h("input", { type: "checkbox", checked: u.is_active });
    var isSelf = u.id === state.me.id;
    if (isSelf) active.disabled = true;

    var body = h("div", null,
      field("To'liq ism", name),
      isAdminTarget ? h("p", { class: "muted small", text: "Administrator rolini bu yerda o'zgartirib bo'lmaydi." }) : [field("Rol", f.role), f.dirField],
      h("label", { class: "check" }, active, h("span", { text: isSelf ? "Faol (o'zingizni o'chira olmaysiz)" : "Faol" })));

    openModal("Foydalanuvchini tahrirlash: " + u.username, body, function (close) {
      var save = h("button", { class: "btn btn-primary", text: "Saqlash" });
      save.addEventListener("click", function () {
        withBusy(save, async function () {
          try {
            var payload = { full_name: name.value };
            if (!isSelf) payload.is_active = active.checked;
            if (!isAdminTarget) Object.assign(payload, collectAssignment(f));
            await api("/admin/users/" + u.id, { method: "PATCH", json: payload });
            close();
            notify("Foydalanuvchi yangilandi.", "ok");
            reload();
          } catch (e) { notify(e.message, "err"); }
        });
      });
      var cancel = h("button", { class: "btn", text: "Bekor qilish" });
      cancel.addEventListener("click", close);
      return [cancel, save];
    });
  }

  async function viewUsers() {
    var rows = await api("/users");
    var reload = function () { route(); };
    var admin = state.me.role === "admin";

    var list = card("Foydalanuvchilar ro'yxati",
      table(["Login", "Ism", "Rol", "Yo'nalish", "Holat", ""], rows, function (u) {
        var actions = [];
        if (admin) {
          var edit = h("button", { class: "btn btn-sm", text: "Tahrirlash" });
          edit.addEventListener("click", function () { editUserDialog(u, reload); });
          actions.push(edit);
        }
        return [u.username, u.full_name, roleLabel(u.role), u.direction ? dirName(u.direction) : "—",
          h("span", { class: "badge " + (u.is_active ? "good" : "bad"), text: u.is_active ? "Faol" : "Faol emas" }),
          h("div", { class: "actions" }, actions)];
      }, "Foydalanuvchi topilmadi."));

    var blocks = [];

    if (admin) {
      var username = h("input", { class: "input", maxlength: "80", placeholder: "kamida 3 belgi", autocomplete: "off" });
      var fullName = h("input", { class: "input", maxlength: "200", placeholder: "Ism familiya" });
      var password = h("input", { class: "input", type: "password", maxlength: "128", placeholder: "kamida 12 belgi", autocomplete: "new-password" });
      var f = userFormFields();
      var create = h("button", { class: "btn btn-primary", text: "Foydalanuvchi yaratish" });
      create.addEventListener("click", function () {
        withBusy(create, async function () {
          try {
            var payload = Object.assign({ username: username.value, full_name: fullName.value, password: password.value }, collectAssignment(f));
            await api("/admin/users", { method: "POST", json: payload });
            notify("Foydalanuvchi yaratildi.", "ok");
            reload();
          } catch (e) { notify(e.message, "err"); }
        });
      });
      blocks.push(card("Yangi foydalanuvchi",
        h("div", { class: "form-grid" }, field("Login", username), field("To'liq ism", fullName), field("Parol", password), field("Rol", f.role), f.dirField),
        create));
    }

    byId("view").replaceChildren(h("div", { class: "stack" }, blocks.concat([list])));
  }

  /* ================= yo'nalishlar (admin) ================= */

  async function viewDirections() {
    var rows = await api("/directions?include_inactive=true");

    var items = rows.map(function (d) {
      var name = h("input", { class: "input", maxlength: "150", value: d.name });
      var order = h("input", { class: "input", type: "number", min: "0", max: "1000", value: d.sort_order });
      var active = h("input", { type: "checkbox", checked: d.is_active });
      var save = h("button", { class: "btn btn-sm btn-primary", text: "Saqlash" });
      save.addEventListener("click", function () {
        withBusy(save, async function () {
          try {
            await api("/admin/directions/" + d.id, { method: "PATCH", json: { name: name.value, sort_order: Number(order.value), is_active: active.checked } });
            await loadDirectionsCache();
            notify("Yo'nalish saqlandi.", "ok");
          } catch (e) { notify(e.message, "err"); }
        });
      });
      return h("div", { class: "card" },
        h("div", { class: "row row-between" }, h("span", { class: "badge info", text: d.code }), h("label", { class: "check" }, active, h("span", { text: "Faol" }))),
        h("div", { class: "form-grid", style: "margin-top:12px" }, field("Nomi", name), field("Tartib raqami", order)),
        save);
    });

    byId("view").replaceChildren(h("div", { class: "stack" },
      h("div", { class: "notice info", text: "Kodlar o'zgarmaydi, faqat nomi, tartibi va faolligi sozlanadi. Faol koordinatori bor yo'nalishni o'chirib bo'lmaydi." }),
      h("div", { class: "grid grid-dirs" }, items)));
  }

  /* ================= audit (admin) ================= */

  async function viewAudit() {
    var rows = await api("/admin/audit-logs?limit=100");
    byId("view").replaceChildren(card("So'nggi 100 ta amal",
      table(["Vaqt", "Foydalanuvchi ID", "Amal", "Obyekt", "Tafsilot"], rows, function (r) {
        return [formatDate(r.created_at), r.user_id === null ? "—" : r.user_id, r.action, r.entity_type + (r.entity_id ? " #" + r.entity_id : ""), r.details || ""];
      }, "Audit yozuvi yo'q.")));
  }

  /* ================= marshrutlash va ishga tushirish ================= */

  var VIEWS = {
    overview: viewOverview, reports: viewReports, projects: viewProjects, tasks: viewTasks,
    ai: viewAI, users: viewUsers, directions: viewDirections, audit: viewAudit,
    telegram: viewTelegramLink
  };

  async function route() {
    var cfg = ROLE_CONFIG[state.me.role] || ROLE_CONFIG.coordinator;
    var name = (window.location.hash || "#overview").slice(1);
    if (cfg.sections.indexOf(name) === -1) name = "overview";
    state.current = name;

    byId("pageTitle").textContent = SECTION_TITLES[name][0];
    byId("pageSub").textContent = SECTION_TITLES[name][1];
    renderNav(cfg);
    byId("sidebar").classList.remove("open");
    notify("");
    loading();

    try { await VIEWS[name](); }
    catch (e) {
      byId("view").replaceChildren();
      notify(e.message || "Ma'lumotni yuklab bo'lmadi.", "err");
    }
  }

  function renderNav(cfg) {
    var nav = byId("nav");
    nav.replaceChildren();
    cfg.sections.forEach(function (key) {
      nav.appendChild(h("a", { href: "#" + key, class: key === state.current ? "active" : "" },
        h("span", { text: NAV_ICONS[key] }), h("span", { text: SECTION_TITLES[key][0] })));
    });
    if (state.me.role === "admin") {
      nav.appendChild(h("a", { href: "/admin" }, h("span", { text: "⇱" }), h("span", { text: "Eski admin sahifasi" })));
    }
  }

  async function loadDirectionsCache() {
    state.directions = await api("/directions");
    state.dirMap = {};
    // faol bo'lmagan yo'nalish nomlari ham ko'rinishi uchun admin to'liq ro'yxatni oladi
    var all = state.me.role === "admin" ? await api("/directions?include_inactive=true") : state.directions;
    all.forEach(function (d) { state.dirMap[d.code] = d.name; });
  }

  async function init() {
    if (!localStorage.getItem(TOKEN_KEY)) { window.location.replace("/login"); return; }

    try {
      state.me = await api("/auth/me");
      var cfg = ROLE_CONFIG[state.me.role];
      if (!cfg) { logout(); return; }

      document.body.setAttribute("data-role", state.me.role);
      await loadDirectionsCache();

      byId("roleBadge").textContent = cfg.label;
      byId("userName").textContent = state.me.full_name;
      byId("userRole").textContent = cfg.label;

      byId("logoutBtn").addEventListener("click", logout);
      byId("menuBtn").addEventListener("click", function () { byId("sidebar").classList.toggle("open"); });
      window.addEventListener("hashchange", route);

      byId("boot").hidden = true;
      byId("app").hidden = false;
      await route();
    } catch (e) {
      byId("boot").textContent = e.message || "Yuklab bo'lmadi.";
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
