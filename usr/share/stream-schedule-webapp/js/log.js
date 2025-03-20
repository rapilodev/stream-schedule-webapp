function setDatePicker() {
    const params = new URLSearchParams(window.location.search);
    const dateParam = params.get("date");
    const dateInput = document.querySelector(".datepicker");

    if (!dateInput) return;

    if (dateParam) {
        dateInput.value = dateParam;
    } else {
        const today = new Date().toISOString().split("T")[0];
        dateInput.value = today;
    }

    dateInput.addEventListener("change", () => {
        document.getElementById("form").submit();
    });

    // Auto-submit on load if no date param
    if (!dateParam) {
        document.getElementById("form").submit();
    }
}

function markUp() {
    var okays = new Array(
        'Source logging in at mountpoint',
        'Connection setup was successful',
        'accepted',
        'server started',
        'LOG START',
        'Switch to src_',
        'Method "OGG" ',
        'Method "MP3" ',
        'Decoding...'
    );
    var infos = new Array(
        'RELOAD	schedule',
        'INIT',
        'PLAY',
    );
    var errors = new Array(
        'Shutdown started',
        'Shutting down',
        'Source failed',
        'Underrun',
        'ERROR',
        'Alsa error: Device or resource busy!',
        'source_shutdown',
        'LOG END',
        'Switch to net_outage',
        '[net_outage',
        'Feeding stopped: source stopped',
        'Feeding stopped: Utils.Timeout',
        'Feeding stopped: Ogg.End_of_stream',
        'invalid or missing password',
        'liquidsoap is not available!',
        'We must catchup',
        'Connection failed: could not connect to host',
        'EROR',
        'not found'
    );

    document.querySelectorAll('pre').forEach(pre => {
        let str = pre.innerHTML;
        for (const word of errors) {
            str = str.split(word).join(`<span class="error">${word}</span>`);
        }
        for (const word of infos) {
            str = str.split(word).join(`<span class="info">${word}</span>`);
        }
        for (const word of okays) {
            str = str.split(word).join(`<span class="okay">${word}</span>`);
        }

        pre.innerHTML = str;
    });
}

document.addEventListener('DOMContentLoaded', function() {
    setDatePicker();
    markUp();
});