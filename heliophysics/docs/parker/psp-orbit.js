const tracker = document.querySelector(".psp-orbit");
const canvas = tracker.querySelector("canvas");
const context = canvas.getContext("2d");
const legend = tracker.querySelector(".psp-orbit-legend");
const distance = tracker.querySelector("[data-psp-distance]");
const sampleTime = tracker.querySelector("[data-psp-time]");
const ephemerisUrl = new URL("psp-orbit.json", import.meta.url);
const solarRadiusKm = 695700;
const hourMs = 3600000;
const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});
const colors = {
  sun: "#eaa635",
  past: "#60418a",
  future: "#907aab",
  marker: "#502378",
  rings: "#e3ddea",
  text: "#50435d",
};
let orbit;

function drawOrbit(positions, currentIndex) {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;

  const deviceScale = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * deviceScale);
  canvas.height = Math.round(height * deviceScale);
  context.scale(canvas.width / width, canvas.height / height);

  const centerX = width / 2;
  const centerY = height / 2;
  const maxRadius = positions.reduce(
    (largest, [x, y]) => Math.max(largest, Math.hypot(x, y) / solarRadiusKm),
    1,
  );
  const scale = (Math.min(width, height) / 2 - 22) / maxRadius;
  const points = positions.map(([x, y]) => [
    centerX + x * scale / solarRadiusKm,
    centerY - y * scale / solarRadiusKm,
  ]);

  context.font = "13px Georgia, serif";
  context.fillStyle = colors.text;
  context.strokeStyle = colors.rings;
  const ringStep = maxRadius >= 100 ? 50 : maxRadius >= 40 ? 20 : 10;
  for (let radius = ringStep; radius <= maxRadius; radius += ringStep) {
    context.beginPath();
    context.arc(centerX, centerY, radius * scale, 0, 2 * Math.PI);
    context.stroke();
    context.fillText(radius.toString(), centerX + 4, centerY - radius * scale - 4);
  }

  function trace(start, end, color, dash) {
    context.strokeStyle = color;
    context.lineWidth = 2.5;
    context.setLineDash(dash);
    context.beginPath();
    context.moveTo(...points[start]);
    for (let i = start + 1; i <= end; i += 1) context.lineTo(...points[i]);
    context.stroke();
  }

  const split = Math.max(0, currentIndex);
  trace(split, points.length - 1, colors.future, [6, 5]);
  trace(0, split, colors.past, []);

  context.beginPath();
  context.arc(centerX, centerY, Math.max(4, scale), 0, 2 * Math.PI);
  context.fillStyle = colors.sun;
  context.fill();

  if (currentIndex >= 0) {
    context.beginPath();
    context.arc(...points[currentIndex], 6, 0, 2 * Math.PI);
    context.fillStyle = colors.marker;
    context.fill();
    context.strokeStyle = "#fff";
    context.lineWidth = 2;
    context.stroke();
  }
}

function render() {
  if (!orbit) return;
  const { start, xyz } = orbit;
  const last = xyz.length - 1;
  const requestedIndex = Math.floor((Date.now() - start) / hourMs);
  const index = Math.min(requestedIndex, last);
  if (index < 0) {
    distance.textContent = "Estimated position unavailable";
    sampleTime.textContent = `Ephemeris begins ${dateFormat.format(start)} UTC`;
  } else {
    const radius = Math.hypot(...xyz[index]) / solarRadiusKm;
    const label = requestedIndex > last ? "Last covered hour" : "Position at";
    const timestamp = `${label} ${dateFormat.format(start + index * hourMs)} UTC`;
    const estimate = `Estimated distance from Sun · ${radius.toFixed(1)} R☉`;
    if (distance.textContent !== estimate) distance.textContent = estimate;
    if (sampleTime.textContent !== timestamp) sampleTime.textContent = timestamp;
  }
  canvas.hidden = false;
  legend.hidden = false;
  if (context) drawOrbit(xyz, index);
}

async function refresh() {
  try {
    const response = await fetch(ephemerisUrl, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const { start_utc, step_seconds, xyz_km } = await response.json();
    const start = Date.parse(start_utc);
    if (
      !Number.isFinite(start) || start % hourMs !== 0 || step_seconds !== 3600 ||
      !Array.isArray(xyz_km) || !xyz_km.length ||
      !xyz_km.every((xyz) => Array.isArray(xyz) && xyz.length === 3 && xyz.every(Number.isFinite))
    ) {
      throw new Error("Invalid PSP ephemeris");
    }
    orbit = { start, xyz: xyz_km };
    render();
  } catch {
    if (!orbit) sampleTime.textContent = "The ephemeris is temporarily unavailable.";
  }
}

refresh();
window.setInterval(render, 60_000);
window.setInterval(refresh, 15 * 60_000);
new ResizeObserver(render).observe(canvas);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    render();
    refresh();
  }
});
