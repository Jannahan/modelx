// ============================================================
// ModelX 2.0 — Team Model Y
// AgroShield Interactive Engine & Simulation Logic
// ============================================================

const APP_STATE = {
  currentCorridor: "dambulla_peliyagoda",
  traderProfile: {
    interestRateDaily: 0.003, // 0.3% per trip
    transportCostPerKg: 6.0,  // Rs. 6/kg
    quotaKg: 100              // 100 kg
  },
  corridors: {
    dambulla_peliyagoda: {
      name: "Dambulla → Peliyagoda Manning Market",
      crops: 7,
      distanceKm: 148,
      transitHours: "4.5 hrs",
      weather: { temp: 30, cond: "Partly Cloudy", wind: "14 km/h", humidity: "62%" }
    },
    dambulla_pettah: {
      name: "Dambulla → Pettah Terminal",
      crops: 5,
      distanceKm: 154,
      transitHours: "5.0 hrs",
      weather: { temp: 31, cond: "Sunny", wind: "12 km/h", humidity: "60%" }
    },
    keppetipola_colombo: {
      name: "Keppetipola → Colombo Wholesale",
      crops: 4,
      distanceKm: 210,
      transitHours: "6.2 hrs",
      weather: { temp: 22, cond: "Heavy Mist", wind: "18 km/h", humidity: "85%" }
    }
  },
  signals: {
    leeks: {
      crop: "Leeks",
      route: "Dambulla → Peliyagoda",
      status: "GREEN",
      badgeText: "OK to Trade",
      badgeClass: "badge-complete",
      wholesalePrice: 135.0,
      expectedSelling: 180.0,
      rangeLo: 165.0,
      rangeHi: 195.0,
      reason: "Even a bad day (5th percentile Rs. 165) covers debt interest + transport cost.",
      img: "https://images.unsplash.com/photo-1597362925123-77861d3fbac7?auto=format&fit=crop&w=500&q=80"
    },
    carrot: {
      crop: "Carrot",
      route: "Dambulla → Pettah",
      status: "AMBER",
      badgeText: "Caution: Buy Less",
      badgeClass: "badge-progress",
      wholesalePrice: 240.0,
      expectedSelling: 275.0,
      rangeLo: 235.0,
      rangeHi: 300.0,
      reason: "Expected price covers cost, but downside loss is plausible. Recommend cash or half quota.",
      img: "https://images.unsplash.com/photo-1598170845058-32b9d6a5da37?auto=format&fit=crop&w=500&q=80"
    },
    beans: {
      crop: "Beans",
      route: "Dambulla → Peliyagoda",
      status: "RED",
      badgeText: "Do Not Borrow",
      badgeClass: "badge-waiting",
      wholesalePrice: 400.0,
      expectedSelling: 420.0,
      rangeLo: null,
      rangeHi: null,
      reason: "Dambulla and Peliyagoda prices are out of step this week. Link breakdown flagged.",
      img: "https://images.unsplash.com/photo-1592417817098-8f3d6910985c?auto=format&fit=crop&w=500&q=80"
    }
  }
};

// Calculate Break-Even: B_t = P_t^w (1 + r) + C
function computeBreakEven(wholesalePrice, r, C) {
  return wholesalePrice * (1 + r) + C;
}

// Update DOM elements on init or changes
function renderDashboard() {
  const r = APP_STATE.traderProfile.interestRateDaily;
  const C = APP_STATE.traderProfile.transportCostPerKg;
  const quota = APP_STATE.traderProfile.quotaKg;

  // Render bottom 3 decision cards
  const container = document.getElementById("bottom-cards-container");
  if (!container) return;

  container.innerHTML = "";

  Object.values(APP_STATE.signals).forEach(sig => {
    const breakEven = computeBreakEven(sig.wholesalePrice, r, C);
    const isRed = sig.status === "RED";
    const rangeText = isRed ? "[HIDDEN TO PREVENT ANCHORING]" : `Rs. ${sig.rangeLo} – ${sig.rangeHi}/kg`;
    const rangeColor = isRed ? "#dc2626" : "#059669";

    const card = document.createElement("div");
    card.className = "action-card";
    card.innerHTML = `
      <div class="card-img-wrap">
        <img src="${sig.img}" class="card-img" alt="${sig.crop}">
        <div class="card-status-badge ${sig.badgeClass}">
          <span>●</span> ${sig.badgeText}
        </div>
      </div>
      <div class="card-body">
        <div class="card-crop-name">
          <span>${sig.crop}</span>
          <span style="font-size:0.8rem; font-weight:700; color:${rangeColor};">${sig.status}</span>
        </div>
        <div class="card-route-sub">${sig.route}</div>
        <div class="card-reason-text">${sig.reason}</div>
        <div class="card-price-row">
          <span>Break-Even: <b>Rs. ${breakEven.toFixed(2)}/kg</b></span>
          <span style="color:${rangeColor};">Range: <b>${rangeText}</b></span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

// Modal Management
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = "flex";
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = "none";
  }
}

// Close modal when clicking backdrop
window.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal-backdrop")) {
    e.target.style.display = "none";
  }
});

// Real-time Trade Calculator in Modal
function updateCalculator() {
  const w = parseFloat(document.getElementById("calc-wholesale").value) || 240;
  const sell = parseFloat(document.getElementById("calc-sell").value) || 270;
  const rPct = parseFloat(document.getElementById("calc-rate").value) || 0.3;
  const c = parseFloat(document.getElementById("calc-cost").value) || 6.0;
  const quota = parseFloat(document.getElementById("calc-quota").value) || 100;

  const r = rPct / 100.0;
  const breakEven = computeBreakEven(w, r, c);
  const totalOutlay = w * (1 + r) * quota + (c * quota);
  const totalRevenue = sell * quota;
  const netProfit = totalRevenue - totalOutlay;

  document.getElementById("calc-breakeven-res").innerText = `Rs. ${breakEven.toFixed(2)}/kg`;
  document.getElementById("calc-outlay-res").innerText = `Rs. ${totalOutlay.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  
  const profitElem = document.getElementById("calc-profit-res");
  profitElem.innerText = `Rs. ${netProfit.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  
  if (netProfit >= 0) {
    profitElem.style.color = "#10b981";
    document.getElementById("calc-verdict").innerHTML = `<span style="color:#059669; font-weight:700;">✅ Profitable Trade</span> · Selling price covers loan interest and transport.`;
  } else {
    profitElem.style.color = "#ef4444";
    document.getElementById("calc-verdict").innerHTML = `<span style="color:#dc2626; font-weight:700;">⚠️ Net Default / Loss</span> · Trader loses Rs. ${Math.abs(netProfit).toFixed(2)}! Model Y RED signal flags this to avoid debt!`;
  }
}

// Corridor change listener
document.addEventListener("DOMContentLoaded", () => {
  renderDashboard();

  const corridorSelect = document.getElementById("corridor-dropdown");
  if (corridorSelect) {
    corridorSelect.addEventListener("change", (e) => {
      APP_STATE.currentCorridor = e.target.value;
      const cData = APP_STATE.corridors[e.target.value];
      if (cData) {
        document.getElementById("stat-routes").innerText = cData.name.includes("Pettah") ? "Dambulla → Pettah" : "Dambulla → Peliyagoda";
        document.getElementById("weather-loc").innerText = cData.name.split("→")[0].trim();
        document.getElementById("weather-temp").innerText = `${cData.weather.temp}°`;
      }
    });
  }
});
