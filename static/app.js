(() => {
  const calendarGrid = document.getElementById("calendarGrid");
  const monthLabel = document.getElementById("monthLabel");
  const prevBtn = document.getElementById("prevMonth");
  const nextBtn = document.getElementById("nextMonth");

  const loginBtn = document.getElementById("loginBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const loginOverlay = document.getElementById("loginOverlay");
  const doLogin = document.getElementById("doLogin");
  const cancelLogin = document.getElementById("cancelLogin");
  const loginUser = document.getElementById("loginUser");
  const loginPass = document.getElementById("loginPass");

  const detailOverlay = document.getElementById("detailOverlay");
  const detailDate = document.getElementById("detailDate");
  const detailStatus = document.getElementById("detailStatus");
  const detailReason = document.getElementById("detailReason");
  const closeDetail = document.getElementById("closeDetail");
  const saveDetail = document.getElementById("saveDetail");
  const clearDetail = document.getElementById("clearDetail");

  const infoOverlay = document.getElementById("infoOverlay");
  const infoDate = document.getElementById("infoDate");
  const infoStatus = document.getElementById("infoStatus");
  const infoReason = document.getElementById("infoReason");
  const closeInfo = document.getElementById("closeInfo");

  let current = new Date();
  let currentYear = current.getFullYear();
  let currentMonth = current.getMonth() + 1;
  let monthData = {};
  let loggedIn = false;

  function formatMonthLabel(y, m) {
    const d = new Date(y, m - 1, 1);
    return d.toLocaleString(undefined, { month: "long", year: "numeric" });
  }
  function isoDate(y, m, d) { const mm = String(m).padStart(2, "0"); const dd = String(d).padStart(2, "0"); return `${y}-${mm}-${dd}`; }

  async function fetchCalendar(y = currentYear, m = currentMonth) {
    const res = await fetch(`/api/calendar?year=${y}&month=${m}`);
    const j = await res.json();
    if (j.ok) {
      monthData = {};
      j.days.forEach(day => {
        monthData[day.date] = { status: day.status, reason: day.reason };
      });
      renderCalendar(y, m, j.days.length);
    } else {
      alert("Failed to fetch calendar");
    }
    await checkSession();
  }

  function clearGrid() { calendarGrid.innerHTML = ""; }

  function renderCalendar(year, month, daysInMonth) {
    monthLabel.textContent = formatMonthLabel(year, month);
    clearGrid();

    const first = new Date(year, month - 1, 1);
    const startOffset = first.getDay();

    for (let i = 0; i < startOffset; i++) {
      const blank = document.createElement("div");
      blank.className = "tile";
      blank.style.opacity = "0.06";
      calendarGrid.appendChild(blank);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const iso = isoDate(year, month, d);
      const item = document.createElement("div");
      const weekday = new Date(year, month - 1, d).getDay();
      item.className = "tile";
      item.dataset.date = iso;

      const dayNum = document.createElement("div");
      dayNum.className = "day-num";
      dayNum.textContent = d;
      if (weekday === 0) dayNum.style.color = "#ffb3b3";

      item.appendChild(dayNum);

      const meta = monthData[iso] || { status: "none", reason: "" };
      if (meta.status && meta.status !== "none") {
        item.classList.add(meta.status);
        if (meta.reason) {
          const pill = document.createElement("div");
          pill.className = "reason-pill";
          pill.textContent = meta.reason;
          item.appendChild(pill);
        }
      }

      item.addEventListener("click", (e) => {
        e.stopPropagation();
        openDetailOrInfo(iso, meta);
      });

      calendarGrid.appendChild(item);
    }
  }

  async function checkSession() {
    try {
      const res = await fetch("/api/session");
      const j = await res.json();
      loggedIn = !!j.logged_in;
      if (loggedIn) {
        loginBtn.classList.add("hidden");
        logoutBtn.classList.remove("hidden");
      } else {
        loginBtn.classList.remove("hidden");
        logoutBtn.classList.add("hidden");
      }
    } catch (err) { console.warn(err); }
  }

  loginBtn.addEventListener("click", () => { loginOverlay.classList.remove("hidden"); });
  cancelLogin.addEventListener("click", () => { loginOverlay.classList.add("hidden"); });

  doLogin.addEventListener("click", async () => {
    const username = loginUser.value.trim();
    const password = loginPass.value;
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ username, password })
      });
      if (res.status === 200) {
        loginOverlay.classList.add("hidden");
        await fetchCalendar();
      } else {
        const j = await res.json();
        alert("Login failed: " + (j.message || "invalid credentials"));
      }
    } catch (err) {
      alert("Login error");
    }
  });

  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
    await fetchCalendar();
  });

  // view vs edit
  function openDetailOrInfo(dateIso, meta) {
    if (loggedIn) {
      openDetail(dateIso, meta);
    } else {
      openInfo(dateIso, meta);
    }
  }

  function openInfo(dateIso, meta) {
    infoOverlay.classList.remove("hidden");
    infoDate.textContent = dateIso;
    infoStatus.textContent = (meta.status && meta.status !== "none") ? capitalize(meta.status) : "No status";
    infoReason.textContent = meta.reason ? meta.reason : "—";
  }
  closeInfo.addEventListener("click", () => infoOverlay.classList.add("hidden"));

  function openDetail(dateIso, meta) {
    detailOverlay.classList.remove("hidden");
    detailDate.textContent = dateIso;
    detailStatus.value = meta.status || "none";
    detailReason.value = meta.reason || "";
  }

  closeDetail.addEventListener("click", () => detailOverlay.classList.add("hidden"));

  saveDetail.addEventListener("click", async () => {
    const date = detailDate.textContent;
    const status = detailStatus.value;
    const reason = detailReason.value.trim();
    try {
      const res = await fetch("/api/attendance", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, status, reason })
      });
      if (res.status === 200) {
        await fetchCalendar(currentYear, currentMonth);
        detailOverlay.classList.add("hidden");
      } else if (res.status === 401) {
        alert("You must login to edit.");
        detailOverlay.classList.add("hidden");
        loginOverlay.classList.remove("hidden");
      } else {
        const j = await res.json();
        alert("Save failed: " + (j.message || res.status));
      }
    } catch (err) {
      alert("Save error");
    }
  });

  clearDetail.addEventListener("click", async () => {
    detailStatus.value = "none";
    detailReason.value = "";
  });

  prevBtn.addEventListener("click", () => {
    currentMonth -= 1;
    if (currentMonth < 1) { currentMonth = 12; currentYear -= 1; }
    fetchCalendar(currentYear, currentMonth);
  });
  nextBtn.addEventListener("click", () => {
    currentMonth += 1;
    if (currentMonth > 12) { currentMonth = 1; currentYear += 1; }
    fetchCalendar(currentYear, currentMonth);
  });

  document.addEventListener("click", (e) => {
    if (!loginOverlay.classList.contains("hidden") && e.target === loginOverlay) loginOverlay.classList.add("hidden");
    if (!detailOverlay.classList.contains("hidden") && e.target === detailOverlay) detailOverlay.classList.add("hidden");
    if (!infoOverlay.classList.contains("hidden") && e.target === infoOverlay) infoOverlay.classList.add("hidden");
  });

  function capitalize(s){
    if(!s) return s;
    return s.replace(/_/g," ").replace(/\b\w/g, c => c.toUpperCase());
  }

  fetchCalendar();
})();
