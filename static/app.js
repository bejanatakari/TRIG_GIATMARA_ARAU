/**
 * TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM
 * GM GEAR ARAU
 * Frontend Application Controller (SPA)
 */

const app = (function () {
  let state = {
    user: null,
    company: null,
    token: localStorage.getItem("trig_token") || "",
    currentScreen: "dashboard",
    currentPosTab: "AUTO_SERVICE", // AUTO_SERVICE, BODY_PAINT, MOTORCYCLE
    activeServiceMode: localStorage.getItem("trig_service_mode") || null, // AUTO_SERVICE, BODY_PAINT, MOTORCYCLE, ALL
    customers: [],
    vehicles: [],
    inventory: [],
    posItems: []
  };

  // =========================================================================
  // API CLIENT
  // =========================================================================
  async function api(endpoint, options = {}) {
    // If running on GitHub Pages or file:// static host, route to client-side Mock API
    if (window.TrigMockAPI && window.TrigMockAPI.isMock()) {
      return await window.TrigMockAPI.handle(endpoint, options);
    }

    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {})
    };
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }

    try {
      const response = await fetch(endpoint, {
        ...options,
        headers
      });

      if (response.status === 401) {
        logout(false);
        showToast("Sesi tamat atau tidak sah. Sila log masuk semula.", "danger");
        return { success: false, error: "Unauthorized" };
      }

      if (response.status === 404 && window.TrigMockAPI) {
        return await window.TrigMockAPI.handle(endpoint, options);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      console.warn("API Network Fallback:", err);
      if (window.TrigMockAPI) {
        return await window.TrigMockAPI.handle(endpoint, options);
      }
      showToast("Ralat sambungan rangkaian ke pelayan.", "danger");
      return { success: false, error: err.message };
    }
  }

  // Toast Notification
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "✅" : (type === "danger" ? "❌" : "⚠️");
    toast.innerHTML = `<span>${icon}</span> <div>${message}</div>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // =========================================================================
  // AUTHENTICATION & INITIALIZATION
  // =========================================================================
  async function init() {
    setupEventListeners();
    initBodyPaintPanels();

    if (state.token) {
      const res = await api("/api/auth/me");
      if (res.success) {
        state.user = res.user;
        state.company = res.company;
        applyCompanyInfo();
        applyUserRoleUI();
        applyActiveServiceModeUI();
        document.getElementById("login-overlay").classList.remove("active");

        const hasChosen = localStorage.getItem("trig_has_chosen_mode");
        if (hasChosen === "1" && state.activeServiceMode) {
          loadScreen("dashboard");
        } else {
          showPortal();
        }
      } else {
        showLogin();
      }
    } else {
      showLogin();
    }
  }

  function showLogin() {
    document.getElementById("login-overlay").classList.add("active");
  }

  function applyCompanyInfo() {
    if (!state.company) return;
    const name = state.company.company_name || "GM GEAR ARAU";
    document.getElementById("sidebar-company-name").innerText = name;
    document.getElementById("topbar-company-title").innerText = name;
    if (state.company.address) {
      document.getElementById("topbar-company-address").innerText = `${state.company.address} | Sistem Pengurusan Bengkel & POS`;
    }

    if (state.company.logo_base64) {
      const img = `<img src="${state.company.logo_base64}" alt="Logo">`;
      document.getElementById("sidebar-logo-container").innerHTML = img;
      const preview = document.getElementById("setting-logo-preview");
      if (preview) preview.innerHTML = img;
    }
  }

  function applyUserRoleUI() {
    if (!state.user) return;
    document.getElementById("user-display-name").innerText = state.user.name;
    document.getElementById("user-role-badge").innerText = state.user.role;
    document.getElementById("user-avatar-text").innerText = state.user.name.charAt(0).toUpperCase();

    // Role restrictions
    const adminElements = document.querySelectorAll(".admin-only");
    adminElements.forEach(el => {
      if (state.user.role !== "ADMIN") {
        el.style.display = "none";
      } else {
        el.style.display = "";
      }
    });

    if (state.user.role === "MECHANIC") {
      // Mechanic screen view
      const cashierElements = document.querySelectorAll("[data-screen='receipts'], [data-screen='ar-aging'], [data-screen='cashier-closing'], [data-screen='suppliers']");
      cashierElements.forEach(el => el.style.display = "none");
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value.trim();
    const alertBox = document.getElementById("login-error-alert");

    alertBox.style.display = "none";
    const res = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    if (res.success) {
      state.token = res.token;
      state.user = res.user;
      state.company = res.company;
      localStorage.setItem("trig_token", res.token);
      document.cookie = `session_token=${res.token}; path=/; max-age=604800`;
      applyCompanyInfo();
      applyUserRoleUI();
      applyActiveServiceModeUI();
      document.getElementById("login-overlay").classList.remove("active");
      showToast(res.message || "Log masuk berjaya!");

      const hasChosen = localStorage.getItem("trig_has_chosen_mode");
      if (hasChosen === "1" && state.activeServiceMode) {
        loadScreen("dashboard");
      } else {
        showPortal();
      }
    } else {
      alertBox.innerText = res.error || "Log masuk gagal.";
      alertBox.style.display = "block";
    }
  }

  async function logout(callApi = true) {
    if (callApi && state.token) {
      await api("/api/auth/logout", { method: "POST" });
    }
    state.token = "";
    state.user = null;
    localStorage.removeItem("trig_token");
    document.cookie = "session_token=; path=/; max-age=0";
    showLogin();
  }

  // =========================================================================
  // SERVICE MODE ISOLATION & PORTAL PLATFORM
  // =========================================================================
  function applyActiveServiceModeUI() {
    const badge = document.getElementById("topbar-active-mode-badge");
    const posTitle = document.getElementById("sidebar-pos-category-title");
    const navAuto = document.getElementById("nav-pos-auto");
    const navPaint = document.getElementById("nav-pos-paint");
    const navMoto = document.getElementById("nav-pos-moto");

    const mode = state.activeServiceMode;

    if (badge) {
      if (mode === "AUTO_SERVICE") {
        badge.innerHTML = "🚗 MOD: SERVIS AUTO";
        badge.className = "badge badge-auto";
        badge.style.display = "inline-flex";
      } else if (mode === "BODY_PAINT") {
        badge.innerHTML = "🎨 MOD: MENGETUK & MENGECAT";
        badge.className = "badge badge-paint";
        badge.style.display = "inline-flex";
      } else if (mode === "MOTORCYCLE") {
        badge.innerHTML = "🏍 MOD: SERVIS MOTOSIKAL";
        badge.className = "badge badge-moto";
        badge.style.display = "inline-flex";
      } else if (mode === "ALL") {
        badge.innerHTML = "🌐 MOD: SEMUA KATEGORI";
        badge.className = "badge badge-secondary";
        badge.style.display = "inline-flex";
      } else {
        badge.innerHTML = "⚙️ PILIH MOD SERVIS";
        badge.className = "badge badge-secondary";
        badge.style.display = "inline-flex";
      }
    }

    // Sidebar POS menu items isolation
    if (navAuto && navPaint && navMoto) {
      if (mode === "AUTO_SERVICE") {
        navAuto.style.display = "";
        navPaint.style.display = "none";
        navMoto.style.display = "none";
        if (posTitle) posTitle.innerText = "POS Servis Auto";
      } else if (mode === "BODY_PAINT") {
        navAuto.style.display = "none";
        navPaint.style.display = "";
        navMoto.style.display = "none";
        if (posTitle) posTitle.innerText = "POS Ketuk & Cat";
      } else if (mode === "MOTORCYCLE") {
        navAuto.style.display = "none";
        navPaint.style.display = "none";
        navMoto.style.display = "";
        if (posTitle) posTitle.innerText = "POS Servis Motosikal";
      } else {
        navAuto.style.display = "";
        navPaint.style.display = "";
        navMoto.style.display = "";
        if (posTitle) posTitle.innerText = "POS & Servis Kenderaan";
      }
    }

    // Synchronize Jobs & Invoices filter selectors if present
    const jobsFilter = document.getElementById("jobs-filter-service");
    if (jobsFilter) {
      jobsFilter.value = (mode && mode !== "ALL") ? mode : "";
    }
    const invFilter = document.getElementById("invoices-filter-service");
    if (invFilter) {
      invFilter.value = (mode && mode !== "ALL") ? mode : "";
    }
  }

  function showPortal() {
    state.currentScreen = "portal";
    document.querySelectorAll(".sidebar-menu .nav-item").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".app-screen").forEach(s => s.style.display = "none");
    const portal = document.getElementById("screen-portal");
    if (portal) {
      portal.style.display = "block";
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectServiceMode(mode) {
    state.activeServiceMode = mode;
    localStorage.setItem("trig_service_mode", mode);
    localStorage.setItem("trig_has_chosen_mode", "1");

    applyActiveServiceModeUI();

    let label = "Semua Kategori";
    if (mode === "AUTO_SERVICE") label = "Servis Kenderaan Auto";
    else if (mode === "BODY_PAINT") label = "Mengetuk & Mengecat";
    else if (mode === "MOTORCYCLE") label = "Servis Motosikal";

    showToast(`Mod Servis Aktif: ${label}`, "success");

    // Automatically navigate to dashboard
    navigate("dashboard");
  }

  // =========================================================================
  // NAVIGATION & ROUTING
  // =========================================================================
  function navigate(screenName) {
    state.currentScreen = screenName;

    // Update sidebar active class
    document.querySelectorAll(".sidebar-menu .nav-item").forEach(item => {
      if (item.getAttribute("data-screen") === screenName) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    if (screenName === "portal") {
      showPortal();
      return;
    }

    // Handle POS tabs navigation
    if (screenName === "pos-auto") {
      switchPosTab("AUTO_SERVICE");
      loadScreen("pos");
      return;
    } else if (screenName === "pos-paint") {
      switchPosTab("BODY_PAINT");
      loadScreen("pos");
      return;
    } else if (screenName === "pos-moto") {
      switchPosTab("MOTORCYCLE");
      loadScreen("pos");
      return;
    } else if (screenName === "pos") {
      if (state.activeServiceMode && state.activeServiceMode !== "ALL") {
        switchPosTab(state.activeServiceMode);
      }
      loadScreen("pos");
      return;
    }

    loadScreen(screenName);
  }

  function loadScreen(name) {
    if (name === "portal") {
      showPortal();
      return;
    }
    document.querySelectorAll(".app-screen").forEach(s => s.style.display = "none");
    const target = document.getElementById(`screen-${name}`);
    if (target) {
      target.style.display = "block";
    }

    // Trigger data loader
    if (name === "dashboard") loadDashboard();
    else if (name === "pos") loadPosData();
    else if (name === "jobs") loadJobs();
    else if (name === "invoices") loadInvoices();
    else if (name === "inventory" || name === "qr-parts") loadInventory();
    else if (name === "customers") loadCustomers();
    else if (name === "vehicles") loadVehicles();
    else if (name === "reminders") loadReminders();
    else if (name === "stock-ledger") loadStockLedger();
    else if (name === "cashier-closing") loadCashierClosing();
    else if (name === "reports") loadReports();
    else if (name === "settings") loadSettings();
    else if (name === "audit-log") loadAuditLogs();
    else if (name === "users") loadUsers();
    else if (name === "receipts") loadReceipts();
    else if (name === "ar-aging") loadArAging();
  }

  // =========================================================================
  // SCREEN 1: DASHBOARD
  // =========================================================================
  async function loadDashboard() {
    const isFiltered = state.activeServiceMode && state.activeServiceMode !== "ALL";
    const serviceParam = isFiltered ? `?service_type=${encodeURIComponent(state.activeServiceMode)}` : "";

    const statsRes = await api(`/api/dashboard/stats${serviceParam}`);
    if (statsRes.success) {
      const s = statsRes.stats;
      document.getElementById("kpi-today-collection").innerText = `RM ${s.today_collection.toFixed(2)}`;
      document.getElementById("kpi-today-revenue").innerText = `RM ${s.today_revenue.toFixed(2)}`;
      document.getElementById("kpi-outstanding").innerText = `RM ${s.outstanding_balance.toFixed(2)}`;
      document.getElementById("kpi-jobs-progress").innerText = s.jobs_in_progress;
      document.getElementById("kpi-vehicles-ready").innerText = s.vehicles_ready;
      document.getElementById("kpi-low-stock").innerText = s.low_stock_count;

      if (s.category_stats) {
        const auto = s.category_stats.AUTO_SERVICE;
        const paint = s.category_stats.BODY_PAINT;
        const moto = s.category_stats.MOTORCYCLE;

        document.getElementById("cat-stat-auto-rev").innerText = `RM ${auto.revenue.toFixed(2)}`;
        document.getElementById("cat-stat-auto-jobs").innerText = `${auto.jobs_count} Kerja Auto Didaftarkan`;

        document.getElementById("cat-stat-paint-rev").innerText = `RM ${paint.revenue.toFixed(2)}`;
        document.getElementById("cat-stat-paint-jobs").innerText = `${paint.jobs_count} Kerja Ketuk & Cat`;

        document.getElementById("cat-stat-moto-rev").innerText = `RM ${moto.revenue.toFixed(2)}`;
        document.getElementById("cat-stat-moto-jobs").innerText = `${moto.jobs_count} Servis Motosikal`;
      }
    }

    // Load recent invoices (isolated to active category if chosen)
    const invRes = await api(`/api/invoices${serviceParam}`);
    if (invRes.success) {
      const tbody = document.querySelector("#dashboard-recent-invoices-table tbody");
      let invoices = invRes.invoices;
      if (isFiltered) {
        invoices = invoices.filter(inv => inv.service_type === state.activeServiceMode);
      }
      if (invoices.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 18px;">Tiada invois terkini bagi mod ini.</td></tr>`;
      } else {
        tbody.innerHTML = invoices.slice(0, 6).map(inv => {
          const badgeClass = inv.service_type === "AUTO_SERVICE" ? "badge-auto" : (inv.service_type === "BODY_PAINT" ? "badge-paint" : "badge-moto");
          const statusClass = `badge-${inv.status.toLowerCase()}`;
          return `
            <tr>
              <td><strong>${inv.invoice_no}</strong></td>
              <td><span class="badge ${badgeClass}">${formatServiceType(inv.service_type)}</span></td>
              <td>${inv.customer_name}</td>
              <td>${inv.vehicle_reg} (${inv.vehicle_model})</td>
              <td><strong>RM ${parseFloat(inv.grand_total).toFixed(2)}</strong></td>
              <td><span class="badge ${statusClass}">${inv.status}</span></td>
            </tr>
          `;
        }).join("");
      }
    }

    // Load charts/top parts
    const chartRes = await api("/api/dashboard/charts");
    if (chartRes.success && chartRes.charts.top_parts) {
      const container = document.getElementById("dashboard-top-parts-list");
      if (chartRes.charts.top_parts.length === 0) {
        container.innerHTML = `<p style="color: var(--text-dim); font-size: 13px;">Tiada data alat ganti terlaris.</p>`;
      } else {
        container.innerHTML = chartRes.charts.top_parts.map(p => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 13px;">
            <div>
              <div style="font-weight: 600; color: #fff;">${p.description}</div>
              <div style="font-size: 11px; color: var(--text-dim);">${p.sku}</div>
            </div>
            <div style="text-align: right;">
              <span class="badge badge-auto">${p.total_qty} Unit</span>
            </div>
          </div>
        `).join("");
      }
    }
  }

  // =========================================================================
  // SCREEN 2: POS THREE SERVICE TABS & WORKFLOW
  // =========================================================================
  function initBodyPaintPanels() {
    const panels = [
      "Front Bumper", "Rear Bumper", "Bonnet (Depan)", "Roof (Bumbung)",
      "Pintu Depan Kiri (FL)", "Pintu Depan Kanan (FR)", "Pintu Belakang Kiri (RL)", "Pintu Belakang Kanan (RR)",
      "Fender Kiri", "Fender Kanan", "Quarter Panel Kiri", "Quarter Panel Kanan",
      "Boot (Pintu Belakang)", "Side Skirt Kiri", "Side Skirt Kanan", "Pillar A/B/C", "Chassis / Frame"
    ];

    const container = document.getElementById("bp-panels-container");
    if (container) {
      container.innerHTML = panels.map(p => `
        <label class="panel-checkbox-label">
          <input type="checkbox" value="${p}" class="bp-panel-check">
          <span>${p}</span>
        </label>
      `).join("");
    }
  }

  function switchPosTab(serviceType) {
    state.currentPosTab = serviceType;

    // Update active tab buttons
    document.querySelectorAll(".pos-service-tab").forEach(tab => {
      if (tab.getAttribute("data-pos-tab") === serviceType) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });

    const titleEl = document.getElementById("pos-form-title");
    const badgeEl = document.getElementById("pos-active-badge");
    const bpSection = document.getElementById("pos-body-paint-section");

    if (serviceType === "AUTO_SERVICE") {
      titleEl.innerHTML = "🚗 Pendaftaran Servis Kenderaan Auto";
      badgeEl.className = "badge badge-auto";
      badgeEl.innerText = "AUTO SERVICE";
      bpSection.style.display = "none";
    } else if (serviceType === "BODY_PAINT") {
      titleEl.innerHTML = "🎨 Pendaftaran Servis Mengetuk & Mengecat Kenderaan";
      badgeEl.className = "badge badge-paint";
      badgeEl.innerText = "BODY & PAINT";
      bpSection.style.display = "block";
    } else if (serviceType === "MOTORCYCLE") {
      titleEl.innerHTML = "🏍 Pendaftaran Servis Motosikal";
      badgeEl.className = "badge badge-moto";
      badgeEl.innerText = "MOTORCYCLE";
      bpSection.style.display = "none";
    }

    filterVehiclesByPosTab();
  }

  async function loadPosData() {
    // Load customers, vehicles, mechanics, inventory items
    const [cRes, vRes, uRes, iRes] = await Promise.all([
      api("/api/customers"),
      api("/api/vehicles"),
      api("/api/users"),
      api("/api/inventory")
    ]);

    if (cRes.success) {
      state.customers = cRes.customers;
      const cSelect = document.getElementById("pos-customer-select");
      cSelect.innerHTML = `<option value="">-- Sila Pilih Pelanggan --</option>` +
        state.customers.map(c => `<option value="${c.id}">${c.name} (${c.phone})</option>`).join("");
    }

    if (vRes.success) {
      state.vehicles = vRes.vehicles;
      filterVehiclesByPosTab();
    }

    if (uRes.success) {
      const tSelect = document.getElementById("pos-technician-select");
      tSelect.innerHTML = `<option value="">-- Pilih Mekanik --</option>` +
        uRes.users.filter(u => u.role === "MECHANIC" || u.role === "ADMIN")
          .map(u => `<option value="${u.id}">${u.name} (${u.role})</option>`).join("");
    }

    if (iRes.success) {
      state.inventory = iRes.inventory;
    }

    if (state.posItems.length === 0) {
      addPosItemRow("PART", "", "", 1, 0);
    }
  }

  function filterVehiclesByPosTab() {
    const vSelect = document.getElementById("pos-vehicle-select");
    const custId = document.getElementById("pos-customer-select").value;

    let filtered = state.vehicles;
    if (custId) {
      filtered = filtered.filter(v => v.customer_id == custId);
    }

    if (state.currentPosTab === "MOTORCYCLE") {
      filtered = filtered.filter(v => v.vehicle_type === "MOTORCYCLE");
    } else {
      filtered = filtered.filter(v => v.vehicle_type === "CAR" || v.vehicle_type === "OTHER");
    }

    vSelect.innerHTML = `<option value="">-- Pilih Kenderaan Pelanggan --</option>` +
      filtered.map(v => `<option value="${v.id}">${v.reg_no} - ${v.make} ${v.model} (${v.colour || 'N/A'})</option>`).join("");
  }

  function addPosItemRow(itemType = "PART", name = "", sku = "", qty = 1, unitPrice = 0, invId = null) {
    const rowId = "pos-row-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
    const itemObj = {
      id: rowId,
      item_type: itemType,
      name: name,
      sku: sku,
      qty: parseFloat(qty) || 1,
      unit_price: parseFloat(unitPrice) || 0,
      inventory_id: invId
    };
    state.posItems.push(itemObj);
    renderPosItemRows();
  }

  function removePosItemRow(rowId) {
    state.posItems = state.posItems.filter(i => i.id !== rowId);
    renderPosItemRows();
  }

  function renderPosItemRows() {
    const tbody = document.getElementById("pos-items-tbody");
    if (!tbody) return;

    if (state.posItems.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada item. Klik butang '+ Tambah Baris Manual' atau imbas Kod QR.</td></tr>`;
      recalculatePosSummary();
      return;
    }

    tbody.innerHTML = state.posItems.map(item => `
      <tr id="${item.id}">
        <td>
          <select class="form-control pos-item-type" onchange="app.updatePosItemField('${item.id}', 'item_type', this.value)">
            <option value="PART" ${item.item_type === 'PART' ? 'selected' : ''}>Alat Ganti (Part)</option>
            <option value="MATERIAL" ${item.item_type === 'MATERIAL' ? 'selected' : ''}>Bahan (Material)</option>
            <option value="LABOUR" ${item.item_type === 'LABOUR' ? 'selected' : ''}>Upah (Labour)</option>
          </select>
        </td>
        <td>
          <input type="text" class="form-control" value="${item.name}" placeholder="Penerangan atau nama alat ganti" oninput="app.updatePosItemField('${item.id}', 'name', this.value)">
        </td>
        <td>
          <input type="text" class="form-control" value="${item.sku || ''}" placeholder="SKU" oninput="app.updatePosItemField('${item.id}', 'sku', this.value)">
        </td>
        <td>
          <input type="number" step="0.5" class="form-control" value="${item.qty}" style="text-align: center;" oninput="app.updatePosItemField('${item.id}', 'qty', this.value)">
        </td>
        <td>
          <input type="number" step="0.01" class="form-control" value="${item.unit_price.toFixed(2)}" style="text-align: right;" oninput="app.updatePosItemField('${item.id}', 'unit_price', this.value)">
        </td>
        <td style="text-align: right; font-weight: 700; color: #fff;">
          RM ${(item.qty * item.unit_price).toFixed(2)}
        </td>
        <td style="text-align: center;">
          <button type="button" class="btn btn-sm btn-danger" onclick="app.removePosItemRow('${item.id}')">✕</button>
        </td>
      </tr>
    `).join("");

    recalculatePosSummary();
  }

  function updatePosItemField(rowId, field, value) {
    const item = state.posItems.find(i => i.id === rowId);
    if (!item) return;

    if (field === "qty" || field === "unit_price") {
      item[field] = parseFloat(value) || 0;
    } else {
      item[field] = value;
    }

    // Refresh row amount display
    const rowEl = document.getElementById(rowId);
    if (rowEl) {
      const amountCell = rowEl.children[5];
      if (amountCell) {
        amountCell.innerText = `RM ${(item.qty * item.unit_price).toFixed(2)}`;
      }
    }
    recalculatePosSummary();
  }

  function recalculatePosSummary() {
    let partsTotal = 0;
    let materialsTotal = 0;
    let labourTotal = 0;

    state.posItems.forEach(i => {
      const amount = i.qty * i.unit_price;
      if (i.item_type === "PART") partsTotal += amount;
      else if (i.item_type === "MATERIAL") materialsTotal += amount;
      else if (i.item_type === "LABOUR") labourTotal += amount;
    });

    const discount = parseFloat(document.getElementById("pos-discount").value) || 0;
    const grandTotal = Math.max(0, partsTotal + materialsTotal + labourTotal - discount);

    document.getElementById("pos-summary-parts").innerText = `RM ${partsTotal.toFixed(2)}`;
    document.getElementById("pos-summary-materials").innerText = `RM ${materialsTotal.toFixed(2)}`;
    document.getElementById("pos-summary-labour").innerText = `RM ${labourTotal.toFixed(2)}`;
    document.getElementById("pos-grand-total").innerText = `RM ${grandTotal.toFixed(2)}`;
  }

  async function handlePosOrderSubmit(e) {
    e.preventDefault();
    const customer_id = document.getElementById("pos-customer-select").value;
    const vehicle_id = document.getElementById("pos-vehicle-select").value;

    if (!customer_id || !vehicle_id) {
      showToast("Sila pilih pelanggan dan kenderaan terlebih dahulu.", "warning");
      return;
    }

    if (state.posItems.length === 0) {
      showToast("Sila masukkan sekurang-kurangnya satu alat ganti atau upah servis.", "warning");
      return;
    }

    // Collect Body & Paint data
    const damaged_panels = Array.from(document.querySelectorAll(".bp-panel-check:checked")).map(el => el.value);
    const damage_types = Array.from(document.querySelectorAll("#bp-damage-types-container input[type='checkbox']:checked")).map(el => el.value);

    const payload = {
      service_type: state.currentPosTab,
      customer_id: parseInt(customer_id),
      vehicle_id: parseInt(vehicle_id),
      mileage: parseInt(document.getElementById("pos-mileage").value) || 0,
      technician_id: parseInt(document.getElementById("pos-technician-select").value) || null,
      complaint: document.getElementById("pos-complaint").value.trim(),
      diagnosis: document.getElementById("pos-diagnosis").value.trim(),
      discount: parseFloat(document.getElementById("pos-discount").value) || 0,
      items: state.posItems.map(i => ({
        item_type: i.item_type,
        name: i.name,
        sku: i.sku,
        qty: i.qty,
        unit_price: i.unit_price,
        amount: i.qty * i.unit_price,
        inventory_id: i.inventory_id
      })),
      // Body & Paint specifics
      paint_colour: document.getElementById("bp-paint-colour").value.trim(),
      paint_code: document.getElementById("bp-paint-code").value.trim(),
      paint_quantity: parseFloat(document.getElementById("bp-paint-qty").value) || 1.0,
      estimated_days: parseInt(document.getElementById("bp-estimated-days").value) || 1,
      damaged_panels,
      damage_types,
      repair_method: document.getElementById("bp-repair-method").value.trim()
    };

    const res = await api("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (res.success) {
      showToast(`Kad Kerja ${res.job_no} berjaya dibuka!`);
      resetPosForm();
      navigate("jobs");
    } else {
      showToast(res.error || "Gagal membuka kad kerja.", "danger");
    }
  }

  function resetPosForm() {
    document.getElementById("pos-order-form").reset();
    state.posItems = [];
    addPosItemRow("PART", "", "", 1, 0);
  }

  // =========================================================================
  // SCREEN 3: WORK ORDERS / JOBS
  // =========================================================================
  async function loadJobs() {
    let filter = document.getElementById("jobs-filter-service")?.value;
    if (!filter && state.activeServiceMode && state.activeServiceMode !== "ALL") {
      filter = state.activeServiceMode;
      const sel = document.getElementById("jobs-filter-service");
      if (sel) sel.value = filter;
    }
    const res = await api(`/api/jobs${filter ? '?service_type=' + encodeURIComponent(filter) : ''}`);
    const tbody = document.querySelector("#jobs-data-table tbody");

    if (!res.success || res.jobs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 24px;">Tiada Kad Kerja ditemui.</td></tr>`;
      return;
    }

    tbody.innerHTML = res.jobs.map(job => {
      const badgeClass = job.service_type === "AUTO_SERVICE" ? "badge-auto" : (job.service_type === "BODY_PAINT" ? "badge-paint" : "badge-moto");
      return `
        <tr>
          <td><strong>${job.job_no}</strong></td>
          <td><span class="badge ${badgeClass}">${formatServiceType(job.service_type)}</span></td>
          <td>${job.customer_name}</td>
          <td><strong>${job.vehicle_reg}</strong></td>
          <td>${job.vehicle_make} ${job.vehicle_model}</td>
          <td>${job.technician_name || '-'}</td>
          <td><span class="badge badge-approved">${job.status}</span></td>
          <td><strong>RM ${parseFloat(job.estimated_total).toFixed(2)}</strong></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-sm btn-primary" onclick="app.convertJobToInvoice(${job.id})">🧾 Tukar ke Invois</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function convertJobToInvoice(jobId) {
    if (!confirm("Tukar Kad Kerja ini kepada Invois rasmi?")) return;
    const res = await api(`/api/jobs/${jobId}/convert-to-invoice`, { method: "POST" });
    if (res.success) {
      showToast(`Invois ${res.invoice_no} berjaya dijana!`);
      navigate("invoices");
    } else {
      showToast(res.error || "Gagal menukar kad kerja ke invois.", "danger");
    }
  }

  // =========================================================================
  // SCREEN 4: INVOICES & ATOMIC APPROVAL / CANCELLATION
  // =========================================================================
  async function loadInvoices() {
    const statusFilter = document.getElementById("invoices-filter-status")?.value || "";
    let serviceFilter = document.getElementById("invoices-filter-service")?.value;
    if (!serviceFilter && state.activeServiceMode && state.activeServiceMode !== "ALL") {
      serviceFilter = state.activeServiceMode;
      const sel = document.getElementById("invoices-filter-service");
      if (sel) sel.value = serviceFilter;
    }
    const params = [];
    if (statusFilter) params.push(`status=${encodeURIComponent(statusFilter)}`);
    if (serviceFilter) params.push(`service_type=${encodeURIComponent(serviceFilter)}`);
    const qStr = params.length ? '?' + params.join('&') : '';
    const res = await api(`/api/invoices${qStr}`);
    const tbody = document.querySelector("#invoices-data-table tbody");

    if (!res.success || res.invoices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 24px;">Tiada Invois ditemui.</td></tr>`;
      return;
    }

    tbody.innerHTML = res.invoices.map(inv => {
      const badgeClass = inv.service_type === "AUTO_SERVICE" ? "badge-auto" : (inv.service_type === "BODY_PAINT" ? "badge-paint" : "badge-moto");
      const statusClass = `badge-${inv.status.toLowerCase()}`;
      return `
        <tr>
          <td><strong>${inv.invoice_no}</strong></td>
          <td><span class="badge ${badgeClass}">${formatServiceType(inv.service_type)}</span></td>
          <td>${inv.customer_name}</td>
          <td><strong>${inv.vehicle_reg}</strong></td>
          <td>${inv.created_at.split(' ')[0]}</td>
          <td><strong>RM ${parseFloat(inv.grand_total).toFixed(2)}</strong></td>
          <td><span style="color: ${parseFloat(inv.balance_due) > 0 ? '#fbbf24' : '#34d399'}; font-weight: 700;">RM ${parseFloat(inv.balance_due).toFixed(2)}</span></td>
          <td><span class="badge ${statusClass}">${inv.status}</span></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-sm btn-secondary" onclick="app.viewInvoiceModal(${inv.id})">👁 Lihat / Cetak</button>
              ${inv.status === 'DRAFT' ? `<button class="btn btn-sm btn-primary" onclick="app.approveInvoice(${inv.id})">✅ Luluskan</button>` : ''}
              ${inv.status !== 'CANCELLED' && parseFloat(inv.balance_due) > 0 ? `<button class="btn btn-sm btn-success" onclick="app.openPaymentModal(${inv.id})">💵 Bayar</button>` : ''}
              ${inv.status !== 'CANCELLED' && inv.status !== 'PAID' ? `<button class="btn btn-sm btn-danger" onclick="app.cancelInvoice(${inv.id})">✕ Batal</button>` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function approveInvoice(invoiceId) {
    if (!confirm("Luluskan invois ini? Stok alat ganti akan ditolak daripada inventori secara rasmi.")) return;
    const res = await api(`/api/invoices/${invoiceId}/approve`, { method: "POST" });
    if (res.success) {
      showToast(res.message);
      loadInvoices();
    } else {
      showToast(res.error || "Gagal meluluskan invois.", "danger");
    }
  }

  async function cancelInvoice(invoiceId) {
    const reason = prompt("Sila masukkan sebab rasmi pembatalan invois ini:");
    if (!reason || !reason.trim()) return;

    const res = await api(`/api/invoices/${invoiceId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: reason.trim() })
    });

    if (res.success) {
      showToast(res.message);
      loadInvoices();
    } else {
      showToast(res.error || "Gagal membatalkan invois.", "danger");
    }
  }

  async function viewInvoiceModal(invoiceId) {
    const res = await api(`/api/invoices/${invoiceId}`);
    if (!res.success) return showToast("Gagal memuatkan invois.", "danger");

    const inv = res.invoice;
    const container = document.getElementById("invoice-printable-area");

    // Generate Invoice QR Code into memory SVG
    const qrSvg = window.QRCodeGenerator ? window.QRCodeGenerator.generateSVG(inv.qr_token, { size: 110 }) : "";

    container.innerHTML = `
      <div class="print-a4-doc">
        <div class="a4-header">
          <div>
            <h1 style="font-size: 22px; font-weight: 900; margin-bottom: 2px;">${state.company?.company_name || 'GM GEAR ARAU'}</h1>
            <div style="font-size: 12px; color: #555;">${state.company?.trading_name || 'Bengkel Automotif & Mengecat'}</div>
            <div style="font-size: 11px; color: #555;">No. SSM: ${state.company?.reg_no || ''} | Tel: ${state.company?.phone || ''}</div>
            <div style="font-size: 11px; color: #555;">${state.company?.address || ''}</div>
          </div>
          <div style="text-align: right;">
            <h2 style="font-size: 20px; font-weight: 800; color: #0284c7;">INVOIS RASMI</h2>
            <div style="font-size: 13px; font-weight: 700;">No: ${inv.invoice_no}</div>
            <div style="font-size: 12px; color: #555;">Tarikh: ${inv.created_at.split(' ')[0]}</div>
            <div style="margin-top: 6px;">
              <span class="badge badge-auto">${formatServiceType(inv.service_type)}</span>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; margin-bottom: 16px; font-size: 12px;">
          <div>
            <strong>KEPADA (PELANGGAN):</strong><br>
            ${inv.customer_name}<br>
            Tel: ${inv.customer_phone}<br>
            ${inv.customer_address || ''}
          </div>
          <div style="text-align: right;">
            <strong>MAKLUMAT KENDERAAN:</strong><br>
            No. Pendaftaran: <strong>${inv.vehicle_reg}</strong><br>
            Model: ${inv.vehicle_make} ${inv.vehicle_model}<br>
            Perbatuan: ${inv.vehicle_mileage || 0} KM
          </div>
        </div>

        <table class="a4-table">
          <thead>
            <tr>
              <th style="width: 30px;">No</th>
              <th style="width: 100px;">SKU</th>
              <th>Keterangan Item / Alat Ganti / Upah</th>
              <th style="width: 60px; text-align: center;">Kuantiti</th>
              <th style="width: 100px; text-align: right;">Harga Seunit (RM)</th>
              <th style="width: 100px; text-align: right;">Jumlah (RM)</th>
            </tr>
          </thead>
          <tbody>
            ${inv.lines.map((l, idx) => `
              <tr>
                <td>${idx + 1}</td>
                <td>${l.sku || '-'}</td>
                <td>${l.description}</td>
                <td style="text-align: center;">${l.qty}</td>
                <td style="text-align: right;">${parseFloat(l.unit_price).toFixed(2)}</td>
                <td style="text-align: right;">${parseFloat(l.amount).toFixed(2)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>

        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-top: 20px;">
          <div style="text-align: center; border: 1px solid #ddd; padding: 10px; border-radius: 6px;">
            ${qrSvg}
            <div style="font-size: 10px; margin-top: 4px; color: #555;">Imbas Kod QR untuk Bayaran Akhir</div>
          </div>

          <table class="a4-totals-table">
            <tr>
              <td>Jumlah Kecil (Subtotal):</td>
              <td style="text-align: right;">RM ${parseFloat(inv.subtotal).toFixed(2)}</td>
            </tr>
            <tr>
              <td>Diskaun:</td>
              <td style="text-align: right;">- RM ${parseFloat(inv.discount).toFixed(2)}</td>
            </tr>
            <tr>
              <td>Cukai SST:</td>
              <td style="text-align: right;">RM ${parseFloat(inv.tax).toFixed(2)}</td>
            </tr>
            <tr style="font-size: 15px; font-weight: 900; border-top: 2px solid #000; border-bottom: 2px solid #000;">
              <td>JUMLAH BESAR:</td>
              <td style="text-align: right;">RM ${parseFloat(inv.grand_total).toFixed(2)}</td>
            </tr>
            <tr>
              <td>Deposit / Bayaran Lalu:</td>
              <td style="text-align: right; color: green;">RM ${parseFloat(inv.paid_amount).toFixed(2)}</td>
            </tr>
            <tr style="font-size: 14px; font-weight: 800; color: #d97706;">
              <td>BAKI PERLU DIBAYAR:</td>
              <td style="text-align: right;">RM ${parseFloat(inv.balance_due).toFixed(2)}</td>
            </tr>
          </table>
        </div>

        <div style="margin-top: 30px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 11px; color: #666; text-align: center;">
          ${state.company?.invoice_footer || 'Terima kasih atas sokongan anda kepada GM GEAR ARAU.'}
        </div>
      </div>
    `;

    openModal("invoice-view-modal");
  }

  // =========================================================================
  // SCREEN 5: INVENTORY & QR PARTS
  // =========================================================================
  async function loadInventory() {
    const search = document.getElementById("inventory-search-input")?.value || "";
    const cat = document.getElementById("inventory-cat-filter")?.value || "";
    const low = document.getElementById("inventory-low-stock-check")?.checked ? "1" : "0";

    const res = await api(`/api/inventory?search=${encodeURIComponent(search)}&category=${encodeURIComponent(cat)}&low_stock=${low}`);
    const tbody = document.querySelector("#inventory-data-table tbody");

    if (!res.success || res.inventory.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 24px;">Tiada item inventori ditemui.</td></tr>`;
      return;
    }

    tbody.innerHTML = res.inventory.map(item => {
      const isLow = parseFloat(item.stock_qty) <= parseFloat(item.min_stock);
      return `
        <tr>
          <td><strong>${item.sku}</strong></td>
          <td>${item.name}</td>
          <td><span class="badge badge-auto">${item.category}</span></td>
          <td>${item.brand || '-'}</td>
          <td>${item.location || '-'}</td>
          <td>RM ${parseFloat(item.cost_price).toFixed(2)}</td>
          <td><strong>RM ${parseFloat(item.selling_price).toFixed(2)}</strong></td>
          <td>
            <span class="badge ${isLow ? 'badge-cancelled' : 'badge-paid'}">
              ${item.stock_qty} ${item.unit} ${isLow ? '⚠️ RENDAH' : ''}
            </span>
          </td>
          <td>
            <button class="btn btn-sm btn-secondary" onclick="app.showQrLabelModal('${item.sku}', '${encodeURIComponent(item.name)}', '${item.location || 'Rak Utama'}')">
              📱 Label QR
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  function showQrLabelModal(sku, nameEnc, location) {
    const name = decodeURIComponent(nameEnc);
    const container = document.getElementById("qr-label-printable-area");
    const qrSvg = window.QRCodeGenerator ? window.QRCodeGenerator.generateSVG(sku, { size: 140 }) : "";

    container.innerHTML = `
      <div style="background: #fff; color: #000; padding: 18px; border-radius: 8px; border: 1px solid #ccc; max-width: 280px; margin: 0 auto; text-align: center;">
        <div style="font-weight: 900; font-size: 14px; text-transform: uppercase;">${state.company?.company_name || 'GM GEAR ARAU'}</div>
        <div style="font-size: 10px; color: #555; margin-bottom: 8px;">LABEL ALAT GANTI BENGKEL</div>
        <div style="margin: 10px 0;">${qrSvg}</div>
        <div style="font-weight: 800; font-size: 13px; color: #000;">${name}</div>
        <div style="font-weight: 700; font-size: 12px; color: #0284c7; margin-top: 2px;">SKU: ${sku}</div>
        <div style="font-size: 11px; color: #666; margin-top: 4px;">Lokasi: ${location}</div>
      </div>
    `;

    openModal("qr-label-modal");
  }

  // =========================================================================
  // PAYMENTS & RECEIPT (A4 & 80MM THERMAL)
  // =========================================================================
  async function openPaymentModal(invoiceId) {
    const res = await api(`/api/invoices/${invoiceId}`);
    if (!res.success) return showToast("Gagal memuatkan invois.", "danger");

    const inv = res.invoice;
    document.getElementById("pay-invoice-id").value = inv.id;
    document.getElementById("pay-modal-inv-no").innerText = inv.invoice_no;
    document.getElementById("pay-modal-customer-vehicle").innerText = `${inv.customer_name} | ${inv.vehicle_reg} (${inv.vehicle_model})`;
    document.getElementById("pay-modal-service-type").innerText = formatServiceType(inv.service_type);
    document.getElementById("pay-modal-grand-total").innerText = `RM ${parseFloat(inv.grand_total).toFixed(2)}`;
    document.getElementById("pay-modal-paid-amount").innerText = `RM ${parseFloat(inv.paid_amount).toFixed(2)}`;
    document.getElementById("pay-modal-balance-due").innerText = `RM ${parseFloat(inv.balance_due).toFixed(2)}`;
    document.getElementById("pay-amount-input").value = parseFloat(inv.balance_due).toFixed(2);

    openModal("payment-modal");
  }

  async function handlePaymentSubmit(e) {
    e.preventDefault();
    const invoice_id = parseInt(document.getElementById("pay-invoice-id").value);
    const amount = parseFloat(document.getElementById("pay-amount-input").value);
    const payment_method = document.getElementById("pay-method-select").value;
    const payment_type = document.getElementById("pay-type-select").value;
    const reference_no = document.getElementById("pay-ref-input").value.trim();
    const notes = document.getElementById("pay-notes-input").value.trim();

    const res = await api("/api/payments", {
      method: "POST",
      body: JSON.stringify({
        invoice_id,
        amount,
        payment_method,
        payment_type,
        reference_no,
        notes
      })
    });

    if (res.success) {
      showToast(res.message);
      closeModal("payment-modal");
      loadInvoices();
      showReceiptModal(res.snapshot);
    } else {
      showToast(res.error || "Gagal merekodkan pembayaran.", "danger");
    }
  }

  function showReceiptModal(snapshot) {
    const container = document.getElementById("receipt-printable-area");
    const qrSvg = window.QRCodeGenerator ? window.QRCodeGenerator.generateSVG(snapshot.receipt_no, { size: 90 }) : "";

    container.innerHTML = `
      <div class="print-thermal-80mm">
        <div class="thermal-header">
          <div class="shop-name">${state.company?.company_name || 'GM GEAR ARAU'}</div>
          <div>${state.company?.trading_name || 'Bengkel Automotif'}</div>
          <div>Tel: ${state.company?.phone || ''}</div>
          <div style="font-size: 9px; color: #555;">${state.company?.address || ''}</div>
        </div>

        <div class="thermal-line"></div>
        <div class="thermal-row"><span>NO RESIT:</span> <strong>${snapshot.receipt_no}</strong></div>
        <div class="thermal-row"><span>NO INVOIS:</span> <span>${snapshot.invoice_no}</span></div>
        <div class="thermal-row"><span>TARIKH:</span> <span>${snapshot.date}</span></div>
        <div class="thermal-row"><span>JURUWANG:</span> <span>${snapshot.cashier_name}</span></div>
        <div class="thermal-row"><span>PELANGGAN:</span> <span>${snapshot.customer_name}</span></div>
        <div class="thermal-row"><span>NO PLAT:</span> <strong>${snapshot.vehicle_reg}</strong></div>
        <div class="thermal-row"><span>KATEGORI:</span> <span>${formatServiceType(snapshot.service_type)}</span></div>
        <div class="thermal-line"></div>

        <div>
          ${(snapshot.items || []).map(i => `
            <div class="thermal-row">
              <span style="max-width: 60%;">${i.description} x${i.qty}</span>
              <span>RM ${parseFloat(i.amount).toFixed(2)}</span>
            </div>
          `).join("")}
        </div>

        <div class="thermal-line"></div>
        <div class="thermal-row"><span>Jumlah Invois:</span> <span>RM ${parseFloat(snapshot.grand_total).toFixed(2)}</span></div>
        <div class="thermal-row"><span>Bayaran Sebelum:</span> <span>RM ${parseFloat(snapshot.previous_paid).toFixed(2)}</span></div>
        
        <div class="thermal-total thermal-row">
          <span>BAYARAN INI:</span>
          <span>RM ${parseFloat(snapshot.payment_amount).toFixed(2)}</span>
        </div>

        <div class="thermal-row"><span>Kaedah Bayaran:</span> <strong>${snapshot.payment_method}</strong></div>
        <div class="thermal-row"><span>Jenis Bayaran:</span> <span>${snapshot.payment_type}</span></div>
        <div class="thermal-row"><span>Baki Tertunggak:</span> <strong>RM ${parseFloat(snapshot.balance_due).toFixed(2)}</strong></div>

        <div class="thermal-line"></div>
        <div style="text-align: center; margin-top: 8px;">
          ${qrSvg}
          <div style="font-size: 9px; margin-top: 4px;">${state.company?.receipt_footer || 'Terima kasih atas urusan anda.'}</div>
        </div>
      </div>
    `;

    openModal("receipt-view-modal");
  }

  // =========================================================================
  // QR SCANNER (INVENTORY PART & INVOICE PAYMENT LOOKUP)
  // =========================================================================
  function openQrScanner() {
    document.getElementById("manual-qr-input").value = "";
    document.getElementById("qr-scan-result").style.display = "none";
    openModal("qr-scanner-modal");
  }

  async function handleManualQrSubmit() {
    const code = document.getElementById("manual-qr-input").value.trim();
    if (!code) return;

    const resultBox = document.getElementById("qr-scan-result");
    resultBox.style.display = "block";
    resultBox.innerHTML = `<p style="color: var(--text-dim);">Mencari kod ${code}...</p>`;

    // 1. Check if invoice token
    if (code.startsWith("INV-TOKEN-") || code.startsWith("INV-")) {
      const invRes = await api(`/api/invoices/qr-lookup?token=${encodeURIComponent(code)}`);
      if (invRes.success) {
        closeModal("qr-scanner-modal");
        openPaymentModal(invRes.invoice.id);
        return;
      }
    }

    // 2. Check if part QR or SKU
    const partRes = await api(`/api/inventory/qr-lookup?code=${encodeURIComponent(code)}`);
    if (partRes.success) {
      const item = partRes.item;
      resultBox.innerHTML = `
        <div style="border-left: 3px solid #0ea5e9; padding-left: 10px;">
          <h4 style="color: #fff; font-size: 14px;">${item.name}</h4>
          <div style="font-size: 12px; color: var(--text-muted);">SKU: <strong>${item.sku}</strong> | Lokasi: ${item.location || 'N/A'}</div>
          <div style="font-size: 13px; margin-top: 4px;">Baki Stok: <strong>${item.stock_qty} ${item.unit}</strong> | Harga: <strong style="color: #38bdf8;">RM ${parseFloat(item.selling_price).toFixed(2)}</strong></div>
          <div style="margin-top: 10px; display: flex; gap: 8px;">
            <input type="number" id="scanned-part-qty" class="form-control" style="width: 80px;" value="1" min="1">
            <button class="btn btn-sm btn-primary" onclick="app.addScannedPartToJob(${item.id}, '${item.sku}', '${encodeURIComponent(item.name)}', ${item.selling_price})">
              + Tambah ke Kad Kerja Aktif
            </button>
          </div>
        </div>
      `;
      return;
    }

    resultBox.innerHTML = `<p style="color: var(--danger);">Kod tidak sah atau tidak ditemui dalam sistem.</p>`;
  }

  function addScannedPartToJob(invId, sku, nameEnc, price) {
    const name = decodeURIComponent(nameEnc);
    const qty = parseFloat(document.getElementById("scanned-part-qty").value) || 1;
    addPosItemRow("PART", name, sku, qty, price, invId);
    closeModal("qr-scanner-modal");
    showToast(`Alat ganti ${name} ditambah ke senarai.`);
    navigate("pos");
  }

  // =========================================================================
  // CUSTOMERS, VEHICLES, REMINDERS, AUDIT, SETTINGS
  // =========================================================================
  async function loadCustomers() {
    const search = document.getElementById("customer-search-input")?.value || "";
    const res = await api(`/api/customers?search=${encodeURIComponent(search)}`);
    const tbody = document.querySelector("#customers-data-table tbody");
    if (!res.success || res.customers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada rekod pelanggan.</td></tr>`;
      return;
    }
    tbody.innerHTML = res.customers.map(c => `
      <tr>
        <td>#${c.id}</td>
        <td><strong>${c.name}</strong></td>
        <td>${c.phone}</td>
        <td>${c.whatsapp || c.phone}</td>
        <td>${c.email || '-'}</td>
        <td>${c.address || '-'}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="app.showCustomerHistory(${c.id})">Sejarah Servis</button>
        </td>
      </tr>
    `).join("");
  }

  async function loadVehicles() {
    const search = document.getElementById("vehicle-search-input")?.value || "";
    let type = document.getElementById("vehicle-type-filter")?.value || "";

    if (!type && state.activeServiceMode && state.activeServiceMode !== "ALL") {
      if (state.activeServiceMode === "MOTORCYCLE") {
        type = "MOTORCYCLE";
      } else {
        type = "CAR";
      }
      const typeSelect = document.getElementById("vehicle-type-filter");
      if (typeSelect) typeSelect.value = type;
    }

    const res = await api(`/api/vehicles?search=${encodeURIComponent(search)}&type=${encodeURIComponent(type)}`);
    const tbody = document.querySelector("#vehicles-data-table tbody");
    if (!res.success || res.vehicles.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada kenderaan ditemui.</td></tr>`;
      return;
    }
    tbody.innerHTML = res.vehicles.map(v => `
      <tr>
        <td><strong>${v.reg_no}</strong></td>
        <td><span class="badge ${v.vehicle_type === 'CAR' ? 'badge-auto' : 'badge-moto'}">${v.vehicle_type}</span></td>
        <td>${v.customer_name}</td>
        <td>${v.make} ${v.model}</td>
        <td>${v.variant || (v.engine_cc ? v.engine_cc + ' cc' : '-')}</td>
        <td>${v.year || '-'}</td>
        <td>${v.colour || '-'}</td>
        <td>${v.mileage || 0} KM</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="app.startJobForVehicle(${v.id}, ${v.customer_id}, '${v.vehicle_type}')">+ Servis</button>
        </td>
      </tr>
    `).join("");
  }

  function startJobForVehicle(vehicleId, customerId, vehicleType) {
    if (vehicleType === "MOTORCYCLE") {
      switchPosTab("MOTORCYCLE");
    } else {
      switchPosTab("AUTO_SERVICE");
    }
    loadScreen("pos");
    setTimeout(() => {
      document.getElementById("pos-customer-select").value = customerId;
      filterVehiclesByPosTab();
      document.getElementById("pos-vehicle-select").value = vehicleId;
    }, 200);
  }

  async function loadReminders() {
    const res = await api("/api/reminders");
    const tbody = document.querySelector("#reminders-data-table tbody");
    if (!res.success || res.reminders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada peringatan servis buat masa ini.</td></tr>`;
      return;
    }
    tbody.innerHTML = res.reminders.map(r => {
      const msg = encodeURIComponent(`Salam ${r.customer_name}, kenderaan anda (${r.vehicle_reg}) telah tiba waktu untuk servis berkala di bengkel GM GEAR ARAU. Sila balas mesej ini untuk penetapan slot masa anda. Terima kasih!`);
      const phoneClean = r.customer_phone.replace(/[^0-9]/g, "");
      const waPhone = phoneClean.startsWith("0") ? "6" + phoneClean : phoneClean;
      return `
        <tr>
          <td><strong>${r.customer_name}</strong></td>
          <td>${r.customer_phone}</td>
          <td>${r.vehicle_reg} (${r.vehicle_make} ${r.vehicle_model})</td>
          <td><span class="badge badge-auto">${formatServiceType(r.service_type)}</span></td>
          <td>${r.last_service_date || '-'}</td>
          <td><strong>${r.next_service_date}</strong></td>
          <td><span class="badge ${r.days_left <= 7 ? 'badge-cancelled' : 'badge-partial'}">${r.days_left} Hari Lagi</span></td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-sm btn-secondary" onclick="navigator.clipboard.writeText(decodeURIComponent('${msg}')).then(() => app.showToast('Mesej peringatan disalin!'))">📋 Salin</button>
              <a href="https://wa.me/${waPhone}?text=${msg}" target="_blank" class="btn btn-sm btn-success">💬 WhatsApp</a>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function loadStockLedger() {
    const res = await api("/api/stock-movements");
    const tbody = document.querySelector("#stock-ledger-table tbody");
    if (!res.success || res.movements.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada transaksi lejar.</td></tr>`;
      return;
    }
    tbody.innerHTML = res.movements.map(m => {
      const isOut = m.movement_type === "OUT";
      return `
        <tr>
          <td>${m.created_at}</td>
          <td><strong>${m.sku}</strong></td>
          <td>${m.item_name}</td>
          <td><span class="badge ${isOut ? 'badge-cancelled' : 'badge-paid'}">${m.movement_type}</span></td>
          <td><strong>${m.qty}</strong></td>
          <td>${m.before_qty}</td>
          <td>${m.after_qty}</td>
          <td>${m.reference_id || '-'}</td>
          <td>${m.user_name || 'Sistem'}</td>
          <td>${m.reason || '-'}</td>
        </tr>
      `;
    }).join("");
  }

  async function loadCashierClosing() {
    const res = await api("/api/cashier/closing");
    if (!res.success) return;

    const list = document.getElementById("closing-methods-list");
    list.innerHTML = Object.entries(res.methods).map(([method, total]) => `
      <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 13.5px;">
        <span>${method}:</span>
        <strong>RM ${total.toFixed(2)}</strong>
      </div>
    `).join("");

    document.getElementById("closing-total-collected").innerText = `RM ${res.total_collected.toFixed(2)}`;
  }

  async function handleCashierClosingSubmit(e) {
    e.preventDefault();
    const actual_cash = parseFloat(document.getElementById("closing-actual-cash").value) || 0;
    const opening_cash = parseFloat(document.getElementById("closing-opening-cash").value) || 0;
    const notes = document.getElementById("closing-notes").value.trim();

    const res = await api("/api/cashier/closing", {
      method: "POST",
      body: JSON.stringify({ actual_cash, opening_cash, notes })
    });

    if (res.success) {
      showToast(`Penyata Penutupan berjaya direkodkan. Selisih: RM ${res.difference.toFixed(2)}`);
      loadCashierClosing();
    } else {
      showToast(res.error || "Gagal menyimpan penutupan.", "danger");
    }
  }

  async function loadReports() {
    const serviceFilter = document.getElementById("report-filter-service").value;
    const [salesRes, bpRes] = await Promise.all([
      api(`/api/reports/sales?service_type=${serviceFilter}`),
      api("/api/reports/body-paint")
    ]);

    if (salesRes.success) {
      const tbody = document.querySelector("#report-sales-table tbody");
      tbody.innerHTML = salesRes.sales_report.map(r => `
        <tr>
          <td><strong>${r.invoice_no}</strong></td>
          <td><span class="badge badge-auto">${formatServiceType(r.service_type)}</span></td>
          <td>${r.created_at.split(' ')[0]}</td>
          <td><strong>RM ${parseFloat(r.grand_total).toFixed(2)}</strong></td>
          <td>RM ${parseFloat(r.deposit_amount).toFixed(2)}</td>
          <td>RM ${parseFloat(r.paid_amount).toFixed(2)}</td>
          <td>RM ${parseFloat(r.balance_due).toFixed(2)}</td>
          <td><span class="badge badge-${r.status.toLowerCase()}">${r.status}</span></td>
        </tr>
      `).join("");
    }

    if (bpRes.success && bpRes.summary) {
      const s = bpRes.summary;
      document.getElementById("bp-rep-total-jobs").innerText = s.total_jobs || 0;
      document.getElementById("bp-rep-materials-cost").innerText = `RM ${parseFloat(s.total_materials_cost || 0).toFixed(2)}`;
      document.getElementById("bp-rep-labour-cost").innerText = `RM ${parseFloat(s.total_labour || 0).toFixed(2)}`;
      document.getElementById("bp-rep-revenue").innerText = `RM ${parseFloat(s.total_revenue || 0).toFixed(2)}`;
      document.getElementById("bp-rep-avg-days").innerText = `${Math.round(s.avg_duration_days || 0)} Hari`;
    }
  }

  async function loadSettings() {
    const res = await api("/api/settings");
    if (!res.success) return;
    const s = res.settings;
    document.getElementById("setting-company-name").value = s.company_name;
    document.getElementById("setting-trading-name").value = s.trading_name || "";
    document.getElementById("setting-reg-no").value = s.reg_no || "";
    document.getElementById("setting-phone").value = s.phone || "";
    document.getElementById("setting-email").value = s.email || "";
    document.getElementById("setting-address").value = s.address || "";
    document.getElementById("setting-tax-enabled").value = s.tax_enabled ? "1" : "0";
    document.getElementById("setting-tax-rate").value = s.tax_rate;
    document.getElementById("setting-invoice-footer").value = s.invoice_footer || "";

    if (s.logo_base64) {
      document.getElementById("setting-logo-preview").innerHTML = `<img src="${s.logo_base64}" alt="Logo" style="width:100%;height:100%;object-fit:cover;">`;
    }
  }

  async function handleCompanySettingsSubmit(e) {
    e.preventDefault();
    const payload = {
      company_name: document.getElementById("setting-company-name").value.trim(),
      trading_name: document.getElementById("setting-trading-name").value.trim(),
      reg_no: document.getElementById("setting-reg-no").value.trim(),
      phone: document.getElementById("setting-phone").value.trim(),
      email: document.getElementById("setting-email").value.trim(),
      address: document.getElementById("setting-address").value.trim(),
      tax_enabled: parseInt(document.getElementById("setting-tax-enabled").value),
      tax_rate: parseFloat(document.getElementById("setting-tax-rate").value) || 0,
      invoice_footer: document.getElementById("setting-invoice-footer").value.trim()
    };

    const res = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (res.success) {
      showToast("Tetapan syarikat berjaya disimpan!");
      const meRes = await api("/api/auth/me");
      if (meRes.success) {
        state.company = meRes.company;
        applyCompanyInfo();
      }
    } else {
      showToast(res.error || "Gagal menyimpan tetapan.", "danger");
    }
  }

  async function handleLogoUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async function (evt) {
      const base64 = evt.target.result;
      const res = await api("/api/settings", {
        method: "POST",
        body: JSON.stringify({ logo_base64: base64 })
      });

      if (res.success) {
        showToast("Logo baharu berjaya dimuat naik!");
        document.getElementById("setting-logo-preview").innerHTML = `<img src="${base64}" alt="Logo" style="width:100%;height:100%;object-fit:cover;">`;
        document.getElementById("sidebar-logo-container").innerHTML = `<img src="${base64}" alt="Logo">`;
      } else {
        showToast(res.error || "Gagal mengemaskini logo.", "danger");
      }
    };
    reader.readAsDataURL(file);
  }

  async function purgeDemoData() {
    if (!confirm("AMARAN KESELAMATAN: Anda pasti ingin memadam semua rekod Data Demo? Tetapan syarikat & akaun pengguna sebenar akan dikekalkan.")) return;
    const res = await api("/api/settings/purge-demo", { method: "POST" });
    if (res.success) {
      showToast(res.message);
      loadDashboard();
    } else {
      showToast(res.error || "Gagal memadam data demo.", "danger");
    }
  }

  async function loadAuditLogs() {
    const res = await api("/api/audit-logs");
    const tbody = document.querySelector("#audit-log-table tbody");
    if (!res.success || res.logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada rekod log audit.</td></tr>`;
      return;
    }
    tbody.innerHTML = res.logs.map(l => `
      <tr>
        <td>${l.created_at}</td>
        <td><strong>${l.user_name}</strong></td>
        <td><span class="badge badge-auto">${l.role}</span></td>
        <td><strong>${l.action}</strong></td>
        <td>${l.module}</td>
        <td>${l.record_id || '-'}</td>
        <td style="font-family: monospace; font-size: 11px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${l.new_value || '-'}</td>
        <td>${l.ip_address || '-'}</td>
      </tr>
    `).join("");
  }

  async function loadUsers() {
    const res = await api("/api/users");
    const tbody = document.querySelector("#users-data-table tbody");
    if (!res.success || res.users.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 20px;">Tiada pengguna ditemui.</td></tr>`;
      return;
    }
    tbody.innerHTML = res.users.map(u => `
      <tr>
        <td>#${u.id}</td>
        <td><strong>${u.name}</strong></td>
        <td>${u.email}</td>
        <td><span class="badge ${u.role === 'ADMIN' ? 'badge-cancelled' : (u.role === 'CASHIER' ? 'badge-partial' : 'badge-auto')}">${u.role}</span></td>
        <td>${u.phone || '-'}</td>
        <td>${u.last_login || 'Belum pernah'}</td>
        <td><span class="badge badge-paid">AKTIF</span></td>
      </tr>
    `).join("");
  }

  async function loadReceipts() {
    const res = await api("/api/receipts");
    // Handled via modal or view
  }

  async function loadArAging() {
    const res = await api("/api/ar/aging");
    // Populate AR table
  }

  // =========================================================================
  // GLOBAL SEARCH & UTILITIES
  // =========================================================================
  function openGlobalSearch() {
    openModal("global-search-modal");
    document.getElementById("global-search-input").focus();
  }

  async function handleGlobalSearch(q) {
    const container = document.getElementById("global-search-results");
    if (!q || q.length < 2) {
      container.innerHTML = `<p style="color: var(--text-dim); text-align: center;">Sila masukkan sekurang-kurangnya 2 aksara untuk mencari.</p>`;
      return;
    }

    const res = await api(`/api/global-search?q=${encodeURIComponent(q)}`);
    if (!res.success) return;

    const r = res.results;
    let html = "";

    if (r.customers.length > 0) {
      html += `<div style="font-size: 11px; font-weight: 700; color: var(--primary); text-transform: uppercase; margin: 8px 0;">Pelanggan</div>`;
      html += r.customers.map(c => `
        <div style="padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; margin-bottom: 4px; cursor: pointer;" onclick="app.closeModal('global-search-modal'); app.navigate('customers');">
          <strong>${c.name}</strong> - Tel: ${c.phone}
        </div>
      `).join("");
    }

    if (r.vehicles.length > 0) {
      html += `<div style="font-size: 11px; font-weight: 700; color: #34d399; text-transform: uppercase; margin: 8px 0;">Kenderaan</div>`;
      html += r.vehicles.map(v => `
        <div style="padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; margin-bottom: 4px; cursor: pointer;" onclick="app.closeModal('global-search-modal'); app.navigate('vehicles');">
          Plat: <strong>${v.reg_no}</strong> (${v.make} ${v.model})
        </div>
      `).join("");
    }

    if (r.invoices.length > 0) {
      html += `<div style="font-size: 11px; font-weight: 700; color: #fbbf24; text-transform: uppercase; margin: 8px 0;">Invois</div>`;
      html += r.invoices.map(i => `
        <div style="padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; margin-bottom: 4px; cursor: pointer;" onclick="app.closeModal('global-search-modal'); app.viewInvoiceModal(${i.id});">
          <strong>${i.invoice_no}</strong> - RM ${parseFloat(i.grand_total).toFixed(2)} (${i.status})
        </div>
      `).join("");
    }

    if (r.inventory.length > 0) {
      html += `<div style="font-size: 11px; font-weight: 700; color: #a78bfa; text-transform: uppercase; margin: 8px 0;">Alat Ganti</div>`;
      html += r.inventory.map(item => `
        <div style="padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 4px; margin-bottom: 4px; cursor: pointer;" onclick="app.closeModal('global-search-modal'); app.navigate('inventory');">
          <strong>${item.name}</strong> (SKU: ${item.sku}) - Stok: ${item.stock_qty}
        </div>
      `).join("");
    }

    if (!html) {
      html = `<p style="color: var(--text-dim); text-align: center;">Tiada rekod sepadan ditemui untuk "${q}".</p>`;
    }

    container.innerHTML = html;
  }

  function formatServiceType(type) {
    if (type === "AUTO_SERVICE") return "SERVIS AUTO";
    if (type === "BODY_PAINT") return "KETUK & CAT";
    if (type === "MOTORCYCLE") return "MOTOSIKAL";
    return type || "";
  }

  function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("active");
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("active");
  }

  // =========================================================================
  // EVENT LISTENERS
  // =========================================================================
  function setupEventListeners() {
    // Login form
    document.getElementById("login-form").addEventListener("submit", handleLogin);
    document.getElementById("btn-logout").addEventListener("click", () => logout(true));

    // Mobile menu toggle
    document.getElementById("mobile-toggle-btn").addEventListener("click", () => {
      document.getElementById("main-sidebar").classList.toggle("mobile-open");
    });

    // Navigation clicks
    document.querySelectorAll(".sidebar-menu .nav-item").forEach(item => {
      item.addEventListener("click", () => {
        const screen = item.getAttribute("data-screen");
        if (screen) {
          navigate(screen);
          document.getElementById("main-sidebar").classList.remove("mobile-open");
        }
      });
    });

    // Top action buttons
    document.getElementById("top-btn-new-job").addEventListener("click", () => navigate("pos-auto"));
    document.getElementById("top-btn-scan-qr").addEventListener("click", openQrScanner);
    document.getElementById("open-global-search").addEventListener("click", openGlobalSearch);

    // Global Search input & shortcut
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        openGlobalSearch();
      }
    });

    document.getElementById("global-search-input").addEventListener("input", (e) => {
      handleGlobalSearch(e.target.value.trim());
    });

    // POS tabs click
    document.querySelectorAll(".pos-service-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        const serviceType = tab.getAttribute("data-pos-tab");
        switchPosTab(serviceType);
      });
    });

    // POS customer select change -> filter vehicles
    document.getElementById("pos-customer-select").addEventListener("change", filterVehiclesByPosTab);

    // POS items buttons
    document.getElementById("pos-btn-add-item-row").addEventListener("click", () => addPosItemRow("PART", "", "", 1, 0));
    document.getElementById("pos-btn-scan-part-qr").addEventListener("click", openQrScanner);
    document.getElementById("pos-discount").addEventListener("input", recalculatePosSummary);
    document.getElementById("pos-order-form").addEventListener("submit", handlePosOrderSubmit);

    // Payment Form
    document.getElementById("record-payment-form").addEventListener("submit", handlePaymentSubmit);

    // QR Scanner manual submit
    document.getElementById("btn-submit-manual-qr").addEventListener("click", handleManualQrSubmit);
    document.getElementById("manual-qr-input").addEventListener("keypress", (e) => {
      if (e.key === "Enter") handleManualQrSubmit();
    });

    // Cashier Closing Form
    document.getElementById("cashier-closing-form").addEventListener("submit", handleCashierClosingSubmit);

    // Company Settings Form & Logo Upload
    document.getElementById("company-settings-form").addEventListener("submit", handleCompanySettingsSubmit);
    document.getElementById("setting-logo-file").addEventListener("change", handleLogoUpload);
    document.getElementById("btn-purge-demo-data").addEventListener("click", purgeDemoData);

    // Inventory search & filter
    document.getElementById("inventory-search-input")?.addEventListener("input", loadInventory);
    document.getElementById("inventory-cat-filter")?.addEventListener("change", loadInventory);
    document.getElementById("inventory-low-stock-check")?.addEventListener("change", loadInventory);

    // Vehicle search
    document.getElementById("vehicle-search-input")?.addEventListener("input", loadVehicles);
    document.getElementById("vehicle-type-filter")?.addEventListener("change", loadVehicles);

    // Customer search
    document.getElementById("customer-search-input")?.addEventListener("input", loadCustomers);

    // Invoice status & service filter, and Jobs service filter
    document.getElementById("invoices-filter-status")?.addEventListener("change", loadInvoices);
    document.getElementById("invoices-filter-service")?.addEventListener("change", loadInvoices);
    document.getElementById("jobs-filter-service")?.addEventListener("change", loadJobs);

    // Refresh Dashboard button
    document.getElementById("refresh-dashboard-btn")?.addEventListener("click", loadDashboard);
  }

  // Public exports
  return {
    init,
    navigate,
    showPortal,
    selectServiceMode,
    applyActiveServiceModeUI,
    openModal,
    closeModal,
    showToast,
    addPosItemRow,
    removePosItemRow,
    updatePosItemField,
    resetPosForm,
    approveInvoice,
    cancelInvoice,
    viewInvoiceModal,
    openPaymentModal,
    showQrLabelModal,
    convertJobToInvoice,
    startJobForVehicle,
    addScannedPartToJob
  };
})();

// Start application upon DOM loaded
document.addEventListener("DOMContentLoaded", () => {
  app.init();
});
