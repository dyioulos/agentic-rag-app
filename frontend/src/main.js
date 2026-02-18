const apiBase = window.location.origin.replace(':8080', ':8000');
let activeRunId = null;

async function getJson(path, opts = {}) {
  const res = await fetch(`${apiBase}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json();
}

async function loadModels() {
  const data = await getJson('/models');
  document.getElementById('models').textContent = `Models: ${data.models.join(', ') || 'none detected'}`;
}

async function loadProjects() {
  const data = await getJson('/projects');
  const sel = document.getElementById('project');
  sel.innerHTML = '';
  data.projects.forEach((p) => {
    const option = document.createElement('option');
    option.value = p;
    option.textContent = p;
    sel.appendChild(option);
  });
}

async function loadRuns() {
  const data = await getJson('/runs');
  const ul = document.getElementById('runs');
  ul.innerHTML = '';
  data.runs.forEach((run) => {
    const li = document.createElement('li');
    li.innerHTML = `<button data-id="${run.id}">#${run.id} ${run.status}</button> <small>${run.project_path}</small>`;
    li.querySelector('button').onclick = () => {
      activeRunId = run.id;
      loadRun(run.id);
    };
    ul.appendChild(li);
  });
}

async function loadRun(id) {
  const data = await getJson(`/runs/${id}`);
  const logs = data.logs
    .map((l) => `[${l.created_at}] ${l.kind.toUpperCase()}: ${l.message}`)
    .join('\n');
  document.getElementById('logs').textContent = logs;

  const diffs = document.getElementById('diffs');
  diffs.innerHTML = '';
  data.changes.forEach((ch) => {
    const div = document.createElement('div');
    div.className = 'diff';
    div.innerHTML = `
      <strong>${ch.file_path}</strong>
      <pre>${ch.diff}</pre>
      <button data-id="${ch.id}">${ch.accepted ? 'Accepted' : 'Accept'}</button>
    `;
    div.querySelector('button').onclick = async () => {
      await getJson(`/changes/${ch.id}/accept`, {
        method: 'POST',
        body: JSON.stringify({ accepted: true }),
      });
      loadRun(id);
    };
    diffs.appendChild(div);
  });
}

async function createRun() {
  const payload = {
    project_path: document.getElementById('project').value,
    prompt: document.getElementById('prompt').value,
    fast_model: document.getElementById('fastModel').value || null,
    deep_model: document.getElementById('deepModel').value || null,
  };
  const result = await getJson('/runs', { method: 'POST', body: JSON.stringify(payload) });
  activeRunId = result.id;
  await loadRuns();
}

document.getElementById('runBtn').onclick = createRun;

setInterval(async () => {
  await loadRuns();
  if (activeRunId) {
    await loadRun(activeRunId);
  }
}, 3000);

loadModels();
loadProjects();
loadRuns();
