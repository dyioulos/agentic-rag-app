const apiBase = `${window.location.origin}/api`;
let activeRunId = null;
let availableModels = [];

async function getJson(path, opts = {}) {
  const headers = opts.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
  const res = await fetch(`${apiBase}${path}`, {
    headers,
    ...opts,
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(errBody || `Request failed (${res.status})`);
  }

  return res.json();
}

function refreshModelSelects() {
  const fastSelect = document.getElementById('fastModel');
  const deepSelect = document.getElementById('deepModel');

  [fastSelect, deepSelect].forEach((select) => {
    const currentValue = select.value;
    select.innerHTML = '';

    const autoOption = document.createElement('option');
    autoOption.value = '';
    autoOption.textContent = 'Auto-select in worker';
    select.appendChild(autoOption);

    availableModels.forEach((model) => {
      const option = document.createElement('option');
      option.value = model;
      option.textContent = model;
      select.appendChild(option);
    });

    if (currentValue && availableModels.includes(currentValue)) {
      select.value = currentValue;
    }
  });
}

async function loadModels() {
  const data = await getJson('/models');
  availableModels = data.models || [];
  document.getElementById('models').textContent = `Models: ${availableModels.join(', ') || 'none detected'}`;
  refreshModelSelects();
}

async function loadProjects(selectedProject = null) {
  const data = await getJson('/projects');
  const sel = document.getElementById('project');
  sel.innerHTML = '';

  if (!data.projects.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No projects found in mounted workspace';
    sel.appendChild(option);
    return;
  }

  data.projects.forEach((p) => {
    const option = document.createElement('option');
    option.value = p;
    option.textContent = p;
    sel.appendChild(option);
  });

  if (selectedProject && data.projects.includes(selectedProject)) {
    sel.value = selectedProject;
  }
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

async function uploadCode() {
  const uploadStatus = document.getElementById('uploadStatus');
  const projectName = document.getElementById('uploadProjectName').value;
  const fileInput = document.getElementById('uploadFile');
  const file = fileInput.files[0];

  if (!file) {
    uploadStatus.textContent = 'Please choose a file to upload.';
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  if (projectName) {
    formData.append('project_name', projectName);
  }

  uploadStatus.textContent = 'Uploading...';
  try {
    const result = await getJson('/uploads/code', { method: 'POST', body: formData });
    uploadStatus.textContent = `Uploaded ${result.filename} (${result.size} bytes).`;
    fileInput.value = '';
    await loadProjects(result.project_path);
  } catch (error) {
    uploadStatus.textContent = `Upload failed: ${error.message}`;
  }
}

document.getElementById('runBtn').onclick = createRun;
document.getElementById('uploadBtn').onclick = uploadCode;

setInterval(async () => {
  await loadRuns();
  if (activeRunId) {
    await loadRun(activeRunId);
  }
}, 3000);

loadModels();
loadProjects();
loadRuns();
