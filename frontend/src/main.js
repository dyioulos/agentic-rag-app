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
  const modelStatus = document.getElementById('modelStatus');
  modelStatus.textContent =
    availableModels.length > 0
      ? `${availableModels.length} models detected and available in the dropdowns.`
      : 'No models detected; worker auto-selection will be used.';
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

function updateSelectedFilesLabel() {
  const fileInput = document.getElementById('uploadFile');
  const selectedFiles = document.getElementById('selectedFiles');
  const names = Array.from(fileInput.files || []).map((file) => file.name);

  selectedFiles.textContent = names.length
    ? `Selected (${names.length}): ${names.join(', ')}`
    : 'No files selected yet.';
}

async function uploadCode() {
  const uploadStatus = document.getElementById('uploadStatus');
  const projectName = document.getElementById('uploadProjectName').value;
  const fileInput = document.getElementById('uploadFile');
  const files = Array.from(fileInput.files || []);

  if (!files.length) {
    uploadStatus.textContent = 'Please choose one or more files to upload.';
    return;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  if (projectName) {
    formData.append('project_name', projectName);
  }

  uploadStatus.textContent = `Uploading ${files.length} file(s)...`;
  try {
    const result = await getJson('/uploads/code', { method: 'POST', body: formData });
    uploadStatus.textContent = `Uploaded ${result.count} file(s) (${result.total_size} bytes total).`;
    fileInput.value = '';
    updateSelectedFilesLabel();
    await loadProjects(result.project_path);
  } catch (error) {
    uploadStatus.textContent = `Upload failed: ${error.message}`;
  }
}

document.getElementById('runBtn').onclick = createRun;
document.getElementById('uploadBtn').onclick = uploadCode;
document.getElementById('uploadFile').addEventListener('change', updateSelectedFilesLabel);

setInterval(async () => {
  await loadRuns();
  if (activeRunId) {
    await loadRun(activeRunId);
  }
}, 3000);

loadModels();
loadProjects();
loadRuns();
