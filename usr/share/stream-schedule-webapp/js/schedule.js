
function showToast(message, type = "info", duration = 3000) {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `${message}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("visible");
    }, 10);

    setTimeout(() => {
        toast.classList.remove("visible");
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function showMessages(el, url) {
    if (!el) return;
    fetch(url)
        .then(res => res.json())
        .then(stats => {
            let output = '';
            ['error', 'warning', 'info'].forEach(
                type => {
                    var msg = stats[type + "s"];
                    if (msg == null || msg.length == 0) return;
                    output += `<div class="${type}">${msg}</div>`;
                });
            el.innerHTML = output;
        });
}

function loadWidget(el, url) {
    if (!el) return;
    fetch(url)
        .then(res => res.text())
        .then(html => {
            el.innerHTML = html;
        });
}

function loadWidgets() {
    loadWidget(document.getElementById("plot"), "/stream-schedule/plot");
    loadWidget(document.getElementById("liquidsoap-status"), "/stream-schedule/liquidsoap-status");
    loadWidget(document.getElementById("schedule"), "/stream-schedule/schedule");
    loadWidget(document.getElementById("schedule-ongoing"), "/stream-schedule/schedule-ongoing");
    loadWidget(document.getElementById("schedule-upcoming"), "/stream-schedule/schedule-upcoming");
    loadWidget(document.getElementById("date-status"), "/stream-schedule/date-status");
    showMessages(document.getElementById("messages"), "/stream-schedule/stream-status");
    audio_levels(document.getElementById("audio-levels"), "/stream-schedule/level");
}

const dbToWidth = (db) => {
    let c = Math.max(0, 100 + parseFloat(db) * 2);
    return c + "%"
};

const rmsColor = db => {
    db = parseFloat(db);
    if (isNaN(db)) return "red";
    db = -db;
    if (db > 18 && db < 22) return "green";
    if (db > 16 && db < 25) return "yellow";
    return "red";
};

const peakColor = db => {
    db = -parseFloat(db);
    if (isNaN(db)) return "red";
    db = -db;
    if (db <= 1.5) return "red";
    if (db > 1.5 && db <= 2.5) return "yellow";
    if (db > 2.5 && db <= 10) return "green";
    if (db > 10) return "yellow";
    return "red";
}

function audio_levels(el, url) {
    if (!el) return;
    // Only initialize bars once
    if (!el.dataset.initialized) {
        el.innerHTML = '<h3>Audio Levels</h3>';
        el.dataset.initialized = 'true';

        function makeBar(label, id) {
            const div = document.createElement("div");
            div.className = "barbox";
            div.innerHTML = `
              <div class="bar">
                <div class="rms" id="${id}-rms">${label} <span></span></div>
                <div class="peak" id="${id}-peak"><span></span></div>
                <div class="text"></div>
              </div>`;
            el.appendChild(div);
        }

        makeBar("Input Left", "in-left");
        makeBar("Input Right", "in-right");
        makeBar("Output Left", "out-left");
        makeBar("Output Right", "out-right");
    }
    fetch(url)
        .then(resp => resp.json())
        .then(data => {
            function updateBar(id, peak, rms) {
                const peakVal = parseFloat(peak).toFixed(2);
                const rmsVal = parseFloat(rms).toFixed(2);

                const rmsEl = document.getElementById(`${id}-rms`);
                const peakEl = document.getElementById(`${id}-peak`);

                rmsEl.className = `rms ${rmsColor(rms)}`;
                rmsEl.style.width = dbToWidth(rms);
                rmsEl.querySelector("span").textContent = `RMS: ${rmsVal} dB`;

                peakEl.className = `peak ${peakColor(peak)}`;
                peakEl.style.width = dbToWidth(peak);
                peakEl.querySelector("span").textContent = `Peak: ${peakVal} dB`;
            }

            updateBar("in-left", data.in.peakLeft, data.in.rmsLeft);
            updateBar("in-right", data.in.peakRight, data.in.rmsRight);
            updateBar("out-left", data.out.peakLeft, data.out.rmsLeft);
            updateBar("out-right", data.out.peakRight, data.out.rmsRight);
        });
}


document.addEventListener("DOMContentLoaded", () => {
    setInterval(loadWidgets, 10000);
    loadWidgets();

    function handleButtonClick(buttonId, endpoint, successMessagePrefix) {
        const button = document.querySelector(buttonId);
        if (!button) return;

        button.addEventListener("click", (e) => {
            e.preventDefault();
            fetch(endpoint)
                .then((res) => res.text())
                .then((text) => {
                    showToast(`${successMessagePrefix}: ${text.trim()}`, "success");
                })
                .catch((err) => {
                    showToast(`${successMessagePrefix} failed: ${err.message}`, "error");
                });
        });
    }

    handleButtonClick("#sync-button", "/stream-schedule/sync", "Sync");
    handleButtonClick("#restart-button", "/stream-schedule/restart", "Restart");

});
