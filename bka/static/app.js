document.addEventListener('DOMContentLoaded', () => {
    console.log("BookAnalizer: Initializing JS...");

    // ========== SETTINGS MANAGEMENT ==========
    const settingsModal = document.getElementById('settings-modal');
    const settingsBtn = document.getElementById('settings-btn');
    const closeSettingsBtn = document.getElementById('close-settings');
    const cancelSettingsBtn = document.getElementById('cancel-settings');
    const saveSettingsBtn = document.getElementById('save-settings');
    const refreshModelsBtn = document.getElementById('refresh-models-btn');

    // Settings Elements
    const settingProvider = document.getElementById('setting-provider');
    const settingApiKey = document.getElementById('setting-api-key');
    const groupApiKey = document.getElementById('group-api-key');
    const groupUrl = document.getElementById('group-url');
    const settingUrl = document.getElementById('setting-url');
    const settingModel = document.getElementById('setting-model');
    const settingModelInput = document.getElementById('setting-model-input');
    const toggleModelInputBtn = document.getElementById('toggle-model-input-btn');
    const settingCtx = document.getElementById('setting-ctx');
    const settingTimeout = document.getElementById('setting-timeout');

    // Default settings
    const DEFAULTS = {
        provider: 'ollama',
        url: 'http://127.0.0.1:11434',
        model: 'gpt-oss:latest',
        ctx: 32768,
        timeout: 180,
        api_key: ''
    };

    function loadSettings() {
        return {
            provider: localStorage.getItem('ba_provider') || DEFAULTS.provider,
            url: localStorage.getItem('ba_ollama_url') || DEFAULTS.url,
            model: localStorage.getItem('ba_ollama_model') || DEFAULTS.model,
            ctx: parseInt(localStorage.getItem('ba_ollama_ctx') || DEFAULTS.ctx),
            timeout: parseInt(localStorage.getItem('ba_ollama_timeout') || DEFAULTS.timeout),
            api_key: localStorage.getItem('ba_api_key') || DEFAULTS.api_key
        };
    }

    function toggleProviderFields() {
        const provider = settingProvider.value;
        if (provider === 'ollama') {
            groupUrl.classList.remove('hidden');
            groupApiKey.classList.add('hidden');
        } else if (provider === 'openai') {
            groupUrl.classList.remove('hidden'); // Custom OpenAI compatibles need URL
            groupApiKey.classList.remove('hidden');
        } else {
            groupUrl.classList.add('hidden');
            groupApiKey.classList.remove('hidden');
        }
    }

    function toggleModelInput() {
        if (settingModel.classList.contains('hidden')) {
            settingModel.classList.remove('hidden');
            settingModelInput.classList.add('hidden');
        } else {
            settingModel.classList.add('hidden');
            settingModelInput.classList.remove('hidden');
            settingModelInput.value = settingModel.value;
        }
    }

    function populateSettingsForm() {
        const settings = loadSettings();
        settingProvider.value = settings.provider;
        settingUrl.value = settings.url;
        settingCtx.value = settings.ctx;
        settingTimeout.value = settings.timeout;
        settingApiKey.value = settings.api_key;

        toggleProviderFields();

        if (settings.provider === 'ollama') {
            fetchModels().then(() => {
                settingModel.value = settings.model;
            });
        } else {
            // For online providers, default to manual input usually
            settingModelInput.value = settings.model;
            settingModel.classList.add('hidden');
            settingModelInput.classList.remove('hidden');
        }
    }

    async function fetchModels() {
        const settings = loadSettings();
        if (settings.provider !== 'ollama') return; // Only fetch for Ollama

        try {
            const resp = await fetch(`${settings.url}/api/tags`);
            const data = await resp.json();
            settingModel.innerHTML = '';
            let modelFound = false;

            if (data.models && data.models.length > 0) {
                data.models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.name;
                    opt.textContent = m.name;
                    if (m.name === settings.model) modelFound = true;
                    settingModel.appendChild(opt);
                });
            } else {
                settingModel.innerHTML = '<option value="gpt-oss:latest">gpt-oss:latest</option>';
            }

            // Restore saved selection
            if (modelFound) {
                settingModel.value = settings.model;
            } else if (settings.model) {
                // Append saved model if missing from list (maybe offline or custom)
                const opt = document.createElement('option');
                opt.value = settings.model;
                opt.textContent = `${settings.model} (Saved)`;
                settingModel.appendChild(opt);
                settingModel.value = settings.model;
            }

        } catch (err) {
            console.error("Failed to fetch models:", err);
            settingModel.innerHTML = `<option value="${settings.model || 'gpt-oss:latest'}">${settings.model || 'gpt-oss:latest'} (offline)</option>`;
        }
    }

    // ...

    function goHome() {
        // Hide all main views
        selectionView.classList.remove('hidden');
        uploadZone.classList.add('hidden');
        segmentationView.classList.add('hidden');
        resultsArea.classList.add('hidden');
        if (projectListContainer) projectListContainer.classList.add('hidden'); // Fix: hide project list specifically

        // Show selection cards again
        const cards = selectionView.querySelector('.selection-cards');
        if (cards) cards.classList.remove('hidden');

        // Reset upload zone
        if (dropArea) dropArea.innerHTML = `<p>Trascina qui il tuo file (PDF o TXT) o clicca per selezionare</p><input type="file" id="file-input" accept=".txt,.pdf" hidden>`;
    }

    async function saveSettings() {
        const provider = settingProvider.value;
        const url = settingUrl.value.trim() || DEFAULTS.url;
        // Check which model input is active or specific logic
        let model = settingModel.value;
        if (!settingModelInput.classList.contains('hidden')) {
            model = settingModelInput.value.trim();
        }

        const ctx = parseInt(settingCtx.value) || DEFAULTS.ctx;
        const timeout = parseInt(settingTimeout.value) || DEFAULTS.timeout;
        const apiKey = settingApiKey.value.trim();

        // Save to localStorage
        localStorage.setItem('ba_provider', provider);
        localStorage.setItem('ba_ollama_url', url);
        localStorage.setItem('ba_ollama_model', model);
        localStorage.setItem('ba_ollama_ctx', ctx.toString());
        localStorage.setItem('ba_ollama_timeout', timeout.toString());
        localStorage.setItem('ba_api_key', apiKey);

        // Send to backend
        try {
            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, url, model, ctx, timeout, api_key: apiKey })
            });
            console.log("Settings saved:", { provider, model });
        } catch (err) {
            console.error("Failed to save settings to backend:", err);
        }

        closeSettingsModal();
    }

    function openSettingsModal() {
        console.log("Opening Settings Modal...");
        try {
            populateSettingsForm();
        } catch (e) {
            console.error("Error populating settings form:", e);
        }
        if (settingsModal) {
            settingsModal.classList.remove('hidden');
        } else {
            console.error("Settings modal element not found!");
        }
    }

    function closeSettingsModal() {
        if (settingsModal) settingsModal.classList.add('hidden');
    }

    // Settings Event Listeners
    if (settingsBtn) {
        settingsBtn.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent any default behavior
            openSettingsModal();
        });
    } else {
        console.error("Settings button not found in DOM!");
    }

    if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettingsModal);
    if (cancelSettingsBtn) cancelSettingsBtn.addEventListener('click', closeSettingsModal);
    if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', saveSettings);
    if (refreshModelsBtn) refreshModelsBtn.addEventListener('click', fetchModels);
    if (settingProvider) settingProvider.addEventListener('change', toggleProviderFields);
    if (settingProvider) settingProvider.addEventListener('change', toggleProviderFields);
    if (toggleModelInputBtn) toggleModelInputBtn.addEventListener('click', toggleModelInput);

    const testConnectionBtn = document.getElementById('test-connection-btn');
    if (testConnectionBtn) {
        testConnectionBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const statusEl = document.getElementById('connection-status');
            statusEl.textContent = "Test in corso...";
            statusEl.style.color = "var(--text-muted)";

            // Sync current values to backend first
            const provider = settingProvider.value;
            const url = settingUrl.value;
            const apiKey = settingApiKey.value;

            try {
                // Update config
                await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider, url, api_key: apiKey })
                });

                // Fetch models
                const resp = await fetch('/api/models');
                const data = await resp.json();

                if (data.models && Array.isArray(data.models)) {
                    statusEl.textContent = `✅ OK! ${data.models.length} modelli trovati.`;
                    statusEl.style.color = "#10b981";

                    // Populate dropdown
                    settingModel.innerHTML = '';
                    data.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m;
                        settingModel.appendChild(opt);
                    });
                } else {
                    throw new Error(data.error || "Nessun modello trovato");
                }
            } catch (e) {
                statusEl.textContent = "❌ Errore: " + e.message;
                statusEl.style.color = "#ef4444";
            }
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !settingsModal.classList.contains('hidden')) {
            closeSettingsModal();
        }
    });

    // Close on outside click
    if (settingsModal) {
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) closeSettingsModal();
        });
    }

    // ========== END SETTINGS ==========


    // --- Elements ---
    const selectionView = document.getElementById('selection-view');
    const uploadZone = document.getElementById('upload-zone');
    const segmentationView = document.getElementById('segmentation-view'); // NEW
    const resultsArea = document.getElementById('results-area');
    const projectListContainer = document.getElementById('project-list-container');
    const projectsGrid = document.getElementById('projects-grid');

    const newProjectCard = document.getElementById('new-project-card');
    const resumeProjectCard = document.getElementById('resume-project-card');
    const backToSelection = document.getElementById('back-to-selection');
    const backFromUpload = document.getElementById('back-from-upload');
    const homeBtn = document.getElementById('home-btn');
    const backToSegmentationBtn = document.getElementById('back-to-selection-btn') || document.getElementById('back-to-segmentation-btn');

    // --- Navigation Functions ---
    function goHome() {
        // Hide all main views
        selectionView.classList.remove('hidden');
        uploadZone.classList.add('hidden');
        segmentationView.classList.add('hidden');
        resultsArea.classList.add('hidden');

        // Reset upload zone
        if (dropArea) dropArea.innerHTML = `<p>Trascina qui il tuo file (PDF o TXT) o clicca per selezionare</p><input type="file" id="file-input" accept=".txt,.pdf" hidden>`;

        // Reset current state if needed? For now keep data in memory but show start.
    }

    function backToSegmentation() {
        if (currentChunks && currentChunks.length > 0) {
            // Ensure rendered
            const list = document.getElementById('chunks-list');
            if (list.children.length === 0) renderSegmentationView(currentChunks);
        }
        resultsArea.classList.add('hidden');
        segmentationView.classList.remove('hidden');
    }

    if (homeBtn) homeBtn.addEventListener('click', goHome);
    if (backToSegmentationBtn) backToSegmentationBtn.addEventListener('click', backToSegmentation);

    // Rescan Button
    const rescanBtn = document.getElementById('rescan-btn');
    if (rescanBtn) rescanBtn.addEventListener('click', rescanChapters);

    async function rescanChapters() {
        if (!currentManuscriptText) {
            alert("Nessun testo in memoria. Carica nuovamente il file o assicurati di aver salvato il testo.");
            return;
        }
        if (!confirm("Attenzione: questo sovrascriverà l'attuale lista dei capitoli. Continuare?")) return;

        const list = document.getElementById('chunks-list');
        list.innerHTML = '<p>Rielaborazione in corso...</p>';

        try {
            const segResp = await fetch('/api/segment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: currentManuscriptText })
            });

            if (segResp.ok) {
                const segData = await segResp.json();
                renderSegmentationView(segData.chunks);
                triggerAutoSave(); // Save new chunks
            } else {
                alert("Errore fase di segmentazione backend.");
            }
        } catch (e) {
            console.error("Rescan error:", e);
            alert("Errore di connessione durante il rescan.");
        }
    }

    console.log("Elements found:", { selectionView, uploadZone, newProjectCard, resumeProjectCard });

    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const characterGrid = document.getElementById('character-grid');
    const worldGrid = document.getElementById('world-grid');
    const refineBtn = document.getElementById('refine-btn');
    const sectionTitle = document.getElementById('section-title');
    const projectTitleEl = document.getElementById('project-title');

    // --- State ---
    let currentResults = [];
    let currentWorldResults = [];
    let currentSynopses = [];
    let currentManuscriptText = "";
    let currentFileName = "Untitled";
    let autoSaveTimeout = null;
    let deletedEntities = new Set(); // Blacklist

    // --- Blacklist Helper Functions ---
    function addToBlacklist(name) {
        if (!name) return;
        deletedEntities.add(name.toLowerCase().trim());
    }

    function removeFromBlacklist(name) {
        if (!name) return;
        deletedEntities.delete(name.toLowerCase().trim());
    }

    function isBlacklisted(name) {
        if (!name) return false;
        return deletedEntities.has(name.toLowerCase().trim());
    }

    // --- Ignored List UI ---
    const ignoredListBtn = document.getElementById('ignored-list-btn');
    const ignoredModal = document.getElementById('ignored-modal');
    const closeIgnoredBtn = document.getElementById('close-ignored');
    const ignoredListContainer = document.getElementById('ignored-list');

    if (ignoredListBtn) {
        ignoredListBtn.addEventListener('click', () => {
            renderIgnoredList();
            ignoredModal.classList.remove('hidden');
        });
    }

    if (closeIgnoredBtn) {
        closeIgnoredBtn.addEventListener('click', () => {
            ignoredModal.classList.add('hidden');
        });
    }

    // Force hide on startup
    if (ignoredModal) ignoredModal.classList.add('hidden');

    function renderIgnoredList() {
        ignoredListContainer.innerHTML = '';
        if (deletedEntities.size === 0) {
            ignoredListContainer.innerHTML = '<p style="text-align:center; color: var(--text-muted);">Nessuna entità ignorata.</p>';
            return;
        }

        deletedEntities.forEach(name => {
            const item = document.createElement('div');
            item.style.display = 'flex';
            item.style.justifyContent = 'space-between';
            item.style.alignItems = 'center';
            item.style.padding = '5px';
            item.style.borderBottom = '1px solid var(--glass-border)';

            item.innerHTML = `
                <span>${name}</span>
                <button class="restore-btn" style="background: none; border: none; cursor: pointer; color: #10b981;" title="Ripristina">♻️</button>
            `;

            item.querySelector('.restore-btn').addEventListener('click', () => {
                removeFromBlacklist(name);
                renderIgnoredList();
                triggerAutoSave();
            });

            ignoredListContainer.appendChild(item);
        });
    }

    // --- Navigation ---
    if (newProjectCard) {
        newProjectCard.addEventListener('click', () => {
            console.log("New Project Clicked");
            selectionView.classList.add('hidden');
            uploadZone.classList.remove('hidden');
        });
    }

    if (resumeProjectCard) {
        resumeProjectCard.addEventListener('click', () => {
            console.log("Resume Project Clicked");
            const cards = selectionView.querySelector('.selection-cards');
            if (cards) cards.classList.add('hidden');
            if (projectListContainer) projectListContainer.classList.remove('hidden');
            loadProjectsList();
        });
    }

    if (backToSelection) {
        backToSelection.addEventListener('click', () => {
            if (projectListContainer) projectListContainer.classList.add('hidden');
            const cards = selectionView.querySelector('.selection-cards');
            if (cards) cards.classList.remove('hidden');
        });
    }

    if (backFromUpload) {
        backFromUpload.addEventListener('click', () => {
            uploadZone.classList.add('hidden');
            selectionView.classList.remove('hidden');
        });
    }

    // --- Project Management ---
    async function loadProjectsList() {
        projectsGrid.innerHTML = '<p>Caricamento...</p>';
        try {
            const response = await fetch('/api/projects');
            const projects = await response.json();

            projectsGrid.innerHTML = '';
            if (projects.length === 0) {
                projectsGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center;">Nessun progetto trovato.</p>';
                return;
            }

            projects.forEach(p => {
                const date = new Date(p.updated * 1000).toLocaleString('it-IT');
                const name = p.name.replace('.json', '').replace(/_/g, ' ');
                const item = document.createElement('div');
                item.className = 'project-item';
                item.innerHTML = `
                    <div class="name">${name}</div>
                    <div class="date">${date}</div>
                    <button class="delete-project-btn" data-filename="${p.name}" style="margin-top: 10px; background: rgba(255,0,0,0.1); border: none; color: #ffaaaa; border-radius: 4px; padding: 2px 5px; cursor: pointer;">Elimina</button>
                `;
                item.addEventListener('click', (e) => {
                    if (e.target.classList.contains('delete-project-btn')) {
                        deleteProject(e.target.dataset.filename);
                    } else {
                        loadProject(p.name);
                    }
                });
                projectsGrid.appendChild(item);
            });
        } catch (err) {
            console.error(err);
            projectsGrid.innerHTML = '<p>Errore nel caricamento dei progetti.</p>';
        }
    }

    async function loadProject(filename) {
        try {
            const response = await fetch(`/api/projects/${filename}`);
            const data = await response.json();

            currentFileName = data.title || filename.replace('.json', '');
            currentResults = data.characters || [];
            currentWorldResults = data.world || [];
            currentChunks = data.chunks || [];
            // We assume text isn't saved in JSON to keep it light? 
            // Phase 13 Requirement says "Save chunks", implies we might reload them.
            // If text is lost, rescan won't work perfectly unless we reload file.
            // But chunks usually contain their own text. 
            // Let's assume user accepts they might need to re-upload for full text manipulations if not saved.
            // However, chunks have 'text' property.

            if (projectTitleEl) projectTitleEl.textContent = currentFileName;

            renderResults(currentResults);
            currentWorldResults = data.world || [];
            currentChunks = data.chunks || [];

            // Load Blacklist
            if (data.deleted && Array.isArray(data.deleted)) {
                deletedEntities = new Set(data.deleted);
            } else {
                deletedEntities = new Set();
            }

            if (projectTitleEl) projectTitleEl.textContent = currentFileName;

            renderResults(currentResults);
            renderWorld(currentWorldResults);
            renderSynopsis(data.synopses || []);

            // Reconstruct text from chunks for global synopsis support if not present
            if (currentChunks.length > 0 && !currentManuscriptText) {
                currentManuscriptText = currentChunks.map(c => c.text).join('\n\n');
            }

            // Render chunks in background so back navigation works
            if (currentChunks.length > 0) renderSegmentationView(currentChunks);

            selectionView.classList.add('hidden');
            resultsArea.classList.remove('hidden');
        } catch (err) {
            console.error(err);
            alert("Errore nel caricamento del progetto.");
        }
    }

    async function deleteProject(filename) {
        if (!confirm("Sei sicuro di voler eliminare questo progetto?")) return;
        try {
            await fetch(`/api/projects/${filename}`, { method: 'DELETE' });
            loadProjectsList();
        } catch (err) {
            console.error(err);
        }
    }

    function triggerAutoSave() {
        if (autoSaveTimeout) clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(saveToServer, 2000);
    }

    async function saveToServer() {
        // Collect current state from UI to ensure we save latest edits
        const exportChars = [];
        document.querySelectorAll('.character-card:not(.world-card)').forEach(card => {
            const name = card.querySelector('.editable-name').innerText.trim();
            const role = card.querySelector('.editable-role').innerText.trim();
            if (name) exportChars.push({ name, role });
        });

        const exportWorld = [];
        document.querySelectorAll('.world-card').forEach(card => {
            const name = card.querySelector('.editable-name').innerText.trim();
            const category = card.querySelector('.delete-btn').getAttribute('data-cat');
            const rawType = card.querySelector('.editable-role').innerText.trim();
            const contextSnippet = card.querySelector('.context-snippet');
            const context = contextSnippet ? contextSnippet.innerText : "";
            if (name) exportWorld.push({ name, category, raw_type: rawType, context });
        });

        const title = projectTitleEl.textContent.trim();

        // Collect synopsis data
        const exportSynopses = [];
        document.querySelectorAll('.synopsis-card').forEach((card, idx) => {
            const content = card.querySelector('.post-content');
            const titleEl = card.querySelector('.post-title');
            const numEl = card.querySelector('.post-number');
            exportSynopses.push({
                post_number: idx + 1,
                title: titleEl ? titleEl.textContent : `POST ${idx + 1}`,
                summary: content ? content.innerText.trim() : ''
            });
        });

        const payload = {
            title: title,
            characters: exportChars,
            world: exportWorld,
            synopses: exportSynopses.length > 0 ? exportSynopses : currentSynopses,
            synopses: exportSynopses.length > 0 ? exportSynopses : currentSynopses,
            synopses: exportSynopses.length > 0 ? exportSynopses : currentSynopses,
            chunks: currentChunks, // Persist chunks
            deleted: Array.from(deletedEntities), // Persist blacklist
            version: "3.2"
        };

        try {
            await fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            console.log("Project auto-saved.");
        } catch (err) {
            console.error("Save failed", err);
        }
    }

    // --- Drag & Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(name => {
        dropArea.addEventListener(name, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
    });

    ['dragenter', 'dragover'].forEach(name => {
        dropArea.addEventListener(name, () => dropArea.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(name => {
        dropArea.addEventListener(name, () => dropArea.classList.remove('dragover'), false);
    });

    dropArea.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files), false);
    dropArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

    function handleFiles(files) {
        if (files.length > 0) uploadFile(files[0]);
    }

    async function uploadFile(file) {
        currentFileName = file.name.replace(/\.[^/.]+$/, "");
        if (projectTitleEl) projectTitleEl.textContent = currentFileName.replace(/[_-]/g, " ");

        const formData = new FormData();
        const reader = new FileReader();

        reader.onload = async (e) => {
            const text = e.target.result;
            currentManuscriptText = text; // Save raw text

            dropArea.innerHTML = `<p>Segmentazione testo in corso...</p>`;

            try {
                const response = await fetch('/api/segment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text })
                });

                if (response.ok) {
                    const data = await response.json();
                    renderSegmentationView(data.chunks);

                    uploadZone.classList.add('hidden');
                    segmentationView.classList.remove('hidden');
                } else {
                    dropArea.innerHTML = `<p>Errore durante la segmentazione.</p>`;
                }
            } catch (error) {
                console.error(error);
                dropArea.innerHTML = `<p>Errore di connessione.</p>`;
            }
        };

        // Read as text to send raw content to segmentation endpoint
        // (Assuming we handle PDF extraction in frontend or separate endpoint. 
        //  Wait, original used /analyze with file upload. 
        //  Let's stick to /analyze pattern but called /api/segment endpoint? 
        //  Actually, regex works on TEXT. So we need text first.
        //  The backend extract_text logic was inside /analyze. 
        //  Let's compromise: reuse the existing /analyze endpoint logic but only to extract text?
        //  No, let's just accept text files for now OR move extraction logic. 
        //  SIMPLIFICATION: If PDF, we might fail here. 
        //  Let's update /api/segment to accept text. 
        //  If file is PDF, we rely on the user converting it? 
        //  User said "Carica PDF/TXT". 
        //  Robust solution: Create a new endpoint /api/upload_to_segment that accepts FILE, extracts text, then segments.
        //  But for now, reusing text reading in JS is fine for TXT. For PDF it's broken.
        //  Let's fix that later or implementing /api/segment to support raw text and we handle PDF->Text in backend?
        //  Let's keep it simple: assume TXT for Granular Analysis optimization for now, 
        //  or better, use the Multi-Step: Upload -> Text -> Segment.
        //  I'll assume TXT for this sprint or use a quick pdf.js if needed.
        //  Actually, the USER PROMPT said "Carica PDF o TXT". I must support PDF.
        //  I will modify the uploadFile to send the file to a helper endpoint /api/extract_text first?
        //  Or I can just send the text content if I read it? No, PDF is binary.
        //  Ok, I'll assume I can send the file to /analyze (which does extraction) but modify /analyze to RETURN text instead of processing spacy.
        //  Wait, /analyze ALREADY returns "text": text in line 117 of main.py!
        //  So I can call /analyze (the old one), ignore spacy results (or use them as cache), and then proceed to segmentation.
        //  PERFECT.

        // REVISED PLAN: Call /analyze (legacy), get text, then call /api/segment.

        const fd = new FormData();
        fd.append('file', file);

        try {
            dropArea.innerHTML = `<p>Lettura file...</p>`;
            const resp = await fetch('/analyze', { method: 'POST', body: fd });
            const data = await resp.json();

            if (data.text) {
                currentManuscriptText = data.text;
                // Now Segment
                dropArea.innerHTML = `<p>Segmentazione...</p>`;
                const segResp = await fetch('/api/segment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: currentManuscriptText })
                });
                const segData = await segResp.json();

                renderSegmentationView(segData.chunks);
                uploadZone.classList.add('hidden');
                segmentationView.classList.remove('hidden');
            }
        } catch (e) {
            console.error(e);
            dropArea.innerHTML = `<p>Errore upload.</p>`;
        }
    }

    // --- Segmentation & Granular Analysis ---
    let currentChunks = [];

    function renderSegmentationView(chunks) {
        currentChunks = chunks; // Store for analysis
        const list = document.getElementById('chunks-list');
        list.innerHTML = '';

        // Add "Clear Results" button to segmentation view for convenience? No, mostly in Results view.
        // Let's ensure Results View has a clear button.
        let clearBtn = document.getElementById('clear-results-btn');
        if (!clearBtn) {
            // Create it dynamically if missing or add to HTML? 
            // Better to add to HTML, but let's inject it for now to be safe.
        }

        chunks.forEach(chunk => {
            const row = document.createElement('div');
            row.className = 'chunk-row';
            row.style.padding = '10px';
            row.style.borderBottom = '1px solid var(--glass-border)';
            row.style.display = 'flex';
            row.style.gap = '10px';
            row.style.alignItems = 'center';

            row.innerHTML = `
                <input type="checkbox" class="chunk-checkbox" data-id="${chunk.id}" checked>
                <div style="flex-grow: 1;">
                    <strong>POST ${chunk.id}</strong>: ${chunk.title || 'Untitled'}
                    <div style="font-size: 0.8rem; color: var(--text-muted);">${chunk.text.substring(0, 60)}...</div>
                </div>
                <span class="status-badge" id="status-${chunk.id}" style="font-size: 0.8rem;">Ready</span>
             `;
            list.appendChild(row);
        });

        // Select All / Deselect All
        document.getElementById('select-all-chunks').onclick = () => {
            document.querySelectorAll('.chunk-checkbox').forEach(cb => cb.checked = true);
        };
        document.getElementById('deselect-all-chunks').onclick = () => {
            document.querySelectorAll('.chunk-checkbox').forEach(cb => cb.checked = false);
        };

        document.getElementById('start-granular-analysis-btn').onclick = startGranularAnalysis;
    }

    async function startGranularAnalysis() {
        // Filter selected chunks
        const selectedIds = Array.from(document.querySelectorAll('.chunk-checkbox:checked')).map(cb => parseInt(cb.dataset.id));
        const chunksToProcess = currentChunks.filter(c => selectedIds.includes(c.id));

        if (chunksToProcess.length === 0) {
            alert("Seleziona almeno un capitolo.");
            return;
        }

        // Determine mode based on radio buttons
        const selectedModeEl = document.querySelector('input[name="analysis-mode"]:checked');
        const mode = selectedModeEl ? selectedModeEl.value : 'characters';

        // Switch to result view immediately
        segmentationView.classList.add('hidden');
        resultsArea.classList.remove('hidden');

        // --- ROBUSTNESS: BACKUP ---
        try {
            console.log("Creating backup before analysis...");
            await fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: projectTitleEl.textContent.trim() + "_backup",
                    characters: currentResults,
                    world: currentWorldResults,
                    synopses: currentSynopses,
                    chunks: currentChunks,
                    version: "3.1-backup"
                })
            });
        } catch (e) { console.error("Backup failed", e); }

        // DO NOT RESET RESULTS - APPEND MODE
        // if (mode === 'world') { currentWorldResults = []; renderWorld([]); }
        // else { currentResults = []; renderResults([]); }
        console.log(`Starting analysis in APPEND mode for ${mode}. Current counts: Chars=${currentResults.length}, World=${currentWorldResults.length}`);

        // Setup progress UI in result area
        const progressContainer = document.getElementById('progress-container');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');

        progressContainer.classList.remove('hidden');

        let processedCount = 0;

        for (const chunk of chunksToProcess) {
            progressText.textContent = `Analisi [${mode.toUpperCase()}] POST ${chunk.id} (${processedCount + 1}/${chunksToProcess.length}) - APPENDING...`;
            progressFill.style.width = `${((processedCount) / chunksToProcess.length) * 100}%`;

            try {
                const resp = await fetch('/api/analyze_chunk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: chunk.text, mode: mode })
                });
                const data = await resp.json();

                // Add to global results
                if (data.results) {
                    // Normalize results to array
                    const resultsArray = Array.isArray(data.results) ? data.results : [data.results];
                    // FILTER BLACKLISTED
                    const filteredResults = resultsArray.filter(c => !isBlacklisted(c.name || ''));

                    if (filteredResults.length < data.results.length) {
                        console.log(`Filtered ${data.results.length - filteredResults.length} blacklisted items.`);
                    }

                    if (mode === 'world') {
                        currentWorldResults.push(...filteredResults);
                        renderWorld(currentWorldResults);
                    } else if (mode === 'synopsis') {
                        // Results for synopsis are usually a single object or {title, summary}
                        // If analyze_chunk returns a list for consistency
                        if (Array.isArray(filteredResults)) {
                            filteredResults.forEach(syn => {
                                currentSynopses.push({
                                    post_number: chunk.id,
                                    title: syn.title || `POST ${chunk.id}`,
                                    summary: syn.summary || ''
                                });
                            });
                        } else {
                            currentSynopses.push({
                                post_number: chunk.id,
                                title: filteredResults.title || `POST ${chunk.id}`,
                                summary: filteredResults.summary || ''
                            });
                        }
                        renderSynopsis(currentSynopses);
                    } else {
                        currentResults.push(...filteredResults);
                        renderResults(currentResults);
                    }
                }

            } catch (e) {
                console.error(`Error chunk ${chunk.id}:`, e);
            }

            processedCount++;
            // Small delay to be rate-limit friendly
            await new Promise(r => setTimeout(r, 1000));
        }

        progressText.textContent = "Analisi Completata! Puoi consolidare i risultati ora.";
        progressFill.style.width = "100%";

        // Auto-switch to correct tab
        const targetTab = mode === 'synopsis' ? 'synopsis' : mode;
        const tabBtn = document.querySelector(`.tab-btn[data-tab="${targetTab}"]`);
        if (tabBtn) tabBtn.click();

        setTimeout(() => progressContainer.classList.add('hidden'), 3000);

        saveToServer();
    }

    // --- Merge Logic ---
    const mergeBtn = document.getElementById('merge-results-btn');
    if (mergeBtn) {
        mergeBtn.addEventListener('click', async () => {
            // Determine mode based on active tab
            const activeTabEl = document.querySelector('.tab-btn.active');
            const activeTab = activeTabEl ? activeTabEl.getAttribute('data-tab') : 'characters';
            const mode = activeTab === 'world' ? 'world' : 'characters';

            const targetList = mode === 'world' ? currentWorldResults : currentResults;

            if (targetList.length === 0) return;

            mergeBtn.disabled = true;
            mergeBtn.textContent = "🌪️ Consolidamento...";

            try {
                const resp = await fetch('/api/merge', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ results: targetList, mode: mode })
                });
                const data = await resp.json();
                if (data.results) {
                    if (mode === 'world') {
                        currentWorldResults = data.results.filter(c => !isBlacklisted(c.name));
                        renderWorld(currentWorldResults);
                    } else {
                        currentResults = data.results.filter(c => !isBlacklisted(c.name));
                        renderResults(currentResults);
                    }
                    alert(`Risultati [${mode}] uniti con successo!`);
                }
            } catch (e) {
                console.error(e);
                alert("Errore durante il merge.");
            } finally {
                mergeBtn.disabled = false;
                mergeBtn.textContent = "🌪️ Unisci Risultati";
                saveToServer();
            }
        });
    }

    // --- Render ---
    function renderResults(characters) {
        characterGrid.innerHTML = '';
        if (!characters.length) {
            characterGrid.innerHTML = '<p style="text-align:center; color: var(--text-muted);">No characters found.</p>';
        }
        characters.forEach((char, index) => {
            const card = document.createElement('div');
            card.className = 'character-card';
            card.innerHTML = `
                <button class="delete-btn" data-index="${index}" title="Remove character">✕</button>
                <h3 contenteditable="true" class="editable-name">${char.name}</h3>
                <p contenteditable="true" class="editable-role">${char.role}</p>
            `;
            characterGrid.appendChild(card);
        });

        document.querySelectorAll('#character-grid .delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const card = e.target.parentElement;
                const name = card.querySelector('.editable-name').innerText.trim();
                addToBlacklist(name);

                card.remove();
                triggerAutoSave();
            });
        });

        document.querySelectorAll('#character-grid [contenteditable]').forEach(el => {
            el.addEventListener('input', triggerAutoSave);
        });
    }

    function renderWorld(elements) {
        worldGrid.innerHTML = '';
        if (!elements || elements.length === 0) {
            worldGrid.innerHTML = '<p style="grid-column: 1/-1; text-align:center; color: var(--text-muted);">No world elements found yet. Try refining.</p>';
            return;
        }

        const categories = { "Place": [], "System/Group": [], "Object/Myth": [], "Unknown": [] };
        elements.forEach(el => {
            const cat = el.category || "Unknown";
            if (!categories[cat]) categories[cat] = [];
            categories[cat].push(el);
        });

        for (const [category, items] of Object.entries(categories)) {
            if (items.length === 0) continue;
            const header = document.createElement('h3');
            header.style.gridColumn = "1 / -1";
            header.style.marginTop = "20px";
            header.style.borderBottom = "1px solid var(--glass-border)";
            header.textContent = category;
            worldGrid.appendChild(header);

            items.forEach((item, index) => {
                const card = document.createElement('div');
                card.className = 'character-card world-card';
                card.innerHTML = `
                    <button class="delete-btn world-delete-btn" data-cat="${category}" data-index="${index}">✕</button>
                    <h4 contenteditable="true" class="editable-name">${item.name}</h4>
                    <p contenteditable="true" class="editable-role">${item.raw_type || item.category}</p>
                    <p class="context-snippet" style="font-size: 0.8em; margin-top:5px; font-style:italic;">${item.context ? item.context.substring(0, 100) + '...' : ''}</p>
                `;
                worldGrid.appendChild(card);
            });
        }

        document.querySelectorAll('.world-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const card = e.target.parentElement;
                const name = card.querySelector('.editable-name').innerText.trim();
                addToBlacklist(name);

                card.remove();
                triggerAutoSave();
            });
        });

        document.querySelectorAll('#world-grid [contenteditable]').forEach(el => {
            el.addEventListener('input', triggerAutoSave);
        });
    }

    function renderSynopsis(synopses) {
        const synopsisList = document.getElementById('synopsis-list');
        synopsisList.innerHTML = '';

        if (!synopses || synopses.length === 0) {
            synopsisList.innerHTML = '<p style="text-align:center; color: var(--text-muted);">Nessun riassunto generato.</p>';
            return;
        }

        synopses.forEach((syn, index) => {
            const card = document.createElement('div');
            card.className = 'synopsis-card';
            card.innerHTML = `
                <div class="post-header">
                    <span class="post-number">POST ${syn.post_number || index + 1}</span>
                    <span class="post-title">${syn.title || ''}</span>
                </div>
                <div class="post-content" contenteditable="true">${syn.summary || ''}</div>
                <div class="post-actions">
                    <button class="btn-small regenerate-post" data-index="${index}">🔄 Rigenera</button>
                    <button class="btn-small delete-post" data-index="${index}">🗑️ Elimina</button>
                </div>
            `;
            synopsisList.appendChild(card);
        });

        // Delete handlers
        document.querySelectorAll('.delete-post').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.getAttribute('data-index'));
                currentSynopses.splice(idx, 1);
                renderSynopsis(currentSynopses);
                triggerAutoSave();
            });
        });
    }

    // --- Refine with Progress ---
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    refineBtn.addEventListener('click', async () => {
        const activeTabEl = document.querySelector('.tab-btn.active');
        const activeTab = activeTabEl ? activeTabEl.getAttribute('data-tab') : 'characters';
        const grid = activeTab === 'characters' ? characterGrid : worldGrid;

        // Use streaming for characters, regular for world
        const useStreaming = activeTab === 'characters';
        const endpoint = useStreaming ? '/refine_stream' : (activeTab === 'characters' ? '/refine' : '/refine_world');
        const payload = activeTab === 'characters'
            ? { characters: currentResults, mode: 'characters' }
            : { world: currentWorldResults };

        refineBtn.disabled = true;
        const originalText = refineBtn.textContent;
        refineBtn.textContent = "Refining...";
        grid.style.opacity = '0.5';

        // Show progress bar for streaming
        if (useStreaming && progressContainer) {
            progressContainer.classList.remove('hidden');
            progressFill.style.width = '10%';
            progressText.textContent = 'Inizializzazione...';
        }

        try {
            if (useStreaming) {
                // Streaming request
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line

                    for (const line of lines) {
                        if (line.trim()) {
                            try {
                                const update = JSON.parse(line);

                                if (update.type === 'progress') {
                                    // Update progress bar
                                    progressFill.style.width = `${update.progress}%`;
                                    progressText.textContent = update.message || `Batch ${update.batch}/${update.total}...`;
                                } else if (update.type === 'complete') {
                                    currentResults = update.characters;
                                    renderResults(currentResults);
                                    progressFill.style.width = '100%';
                                    progressText.textContent = 'Completato!';
                                }
                            } catch (e) {
                                console.log('Parse error:', e);
                            }
                        }
                    }
                }
                saveToServer();
            } else {
                // Regular request for world
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                currentWorldResults = data.world;
                renderWorld(currentWorldResults);
                saveToServer();
            }
        } catch (e) {
            console.error(e);
            alert("Refinement failed.");
            if (progressText) progressText.textContent = 'Errore!';
        } finally {
            refineBtn.disabled = false;
            refineBtn.textContent = originalText;
            grid.style.opacity = '1';

            // Hide progress after delay
            setTimeout(() => {
                if (progressContainer) progressContainer.classList.add('hidden');
                if (progressFill) progressFill.style.width = '0%';
            }, 1500);
        }
    });


    // --- Tabs ---
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');

            // Show appropriate content
            if (target === 'characters') {
                document.getElementById('character-grid').classList.add('active');
                if (sectionTitle) sectionTitle.textContent = "Personaggi Trovati";
            } else if (target === 'world') {
                document.getElementById('world-grid').classList.add('active');
                if (sectionTitle) sectionTitle.textContent = "World Building Elements";
            } else if (target === 'synopsis') {
                document.getElementById('synopsis-container').classList.add('active');
                if (sectionTitle) sectionTitle.textContent = "Sinossi POST";
            }
        });
    });

    // --- Export JSON ---
    document.getElementById('export-btn').addEventListener('click', () => {
        const data = {
            title: projectTitleEl.textContent.trim(),
            characters: currentResults,
            world: currentWorldResults,
            synopses: currentSynopses,
            version: "3.0"
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `BookAnalizer_${data.title.replace(/\s+/g, '_')}.json`;
        a.click();
    });

    // --- Export TOON (for BIBBIA integration) ---
    document.getElementById('export-toon-btn').addEventListener('click', async () => {
        const btn = document.getElementById('export-toon-btn');
        btn.disabled = true;
        btn.textContent = '⏳ Exporting...';

        try {
            const response = await fetch('/api/export/toon', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: projectTitleEl.textContent.trim(),
                    characters: currentResults,
                    world: currentWorldResults
                })
            });

            const data = await response.json();

            if (data.toon) {
                const blob = new Blob([data.toon], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `BIBBIA_${projectTitleEl.textContent.trim().replace(/\s+/g, '_')}.toon`;
                a.click();
                console.log(`Exported ${data.characters_count} characters, ${data.world_count} world elements`);
            }
        } catch (err) {
            console.error("Export TOON failed:", err);
            alert("Errore durante l'export TOON");
        } finally {
            btn.disabled = false;
            btn.textContent = '📜 Export TOON';
        }
    });

    // --- Send to BIBBIA ---
    const sendBibbiaBtn = document.getElementById('send-bibbia-btn');
    if (sendBibbiaBtn) {
        sendBibbiaBtn.addEventListener('click', async () => {
            sendBibbiaBtn.disabled = true;
            const originalText = sendBibbiaBtn.textContent;
            sendBibbiaBtn.textContent = '⏳ Invio...';

            try {
                const response = await fetch('/api/bibbia/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: projectTitleEl.textContent.trim(),
                        // Scrape current UI state to ensure edits are captured
                        characters: (function () {
                            const chars = [];
                            document.querySelectorAll('.character-card:not(.world-card)').forEach(card => {
                                const name = card.querySelector('.editable-name').innerText.trim();
                                const role = card.querySelector('.editable-role').innerText.trim();
                                if (name) chars.push({ name, role });
                            });
                            return chars;
                        })(),
                        world: (function () {
                            const world = [];
                            document.querySelectorAll('.world-card').forEach(card => {
                                const name = card.querySelector('.editable-name').innerText.trim();
                                const category = card.querySelector('.delete-btn').getAttribute('data-cat');
                                const rawType = card.querySelector('.editable-role').innerText.trim();
                                const contextSnippet = card.querySelector('.context-snippet');
                                const context = contextSnippet ? contextSnippet.innerText : "";
                                if (name) world.push({ name, category, raw_type: rawType, context });
                            });
                            return world;
                        })(),
                        synopses: (function () {
                            const syns = [];
                            document.querySelectorAll('.synopsis-card').forEach((card, idx) => {
                                const content = card.querySelector('.post-content');
                                const titleEl = card.querySelector('.post-title');
                                const numEl = card.querySelector('.post-number');
                                syns.push({
                                    post_number: idx + 1,
                                    title: titleEl ? titleEl.textContent : `POST ${idx + 1}`,
                                    summary: content ? content.innerText.trim() : ''
                                });
                            });
                            return syns;
                        })(),
                        sandbox_url: 'http://127.0.0.1:5000'
                    })
                });

                const data = await response.json();

                if (data.success) {
                    alert(`✅ Inviato a BIBBIA!\n\nPersonaggi: ${data.characters_sent}\nWorld: ${data.world_sent}\nSynopses: ${data.synopses_sent}\nToken stimati: ${data.tokens}`);
                } else {
                    alert(`❌ Errore: ${data.error}`);
                }
            } catch (err) {
                console.error("Send to BIBBIA failed:", err);
                alert("Errore durante l'invio a BIBBIA. Assicurati che Sandbox-UI sia in esecuzione.");
            } finally {
                sendBibbiaBtn.disabled = false;
                sendBibbiaBtn.textContent = originalText;
            }
        });
    }


    // --- Import (Manual JSON) ---
    const importBtn = document.getElementById('start-import-btn');
    const importInput = document.createElement('input');
    importInput.type = 'file';
    importInput.accept = '.json';
    importInput.onchange = (e) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            const data = JSON.parse(event.target.result);
            currentResults = data.characters || [];
            currentWorldResults = data.world || [];
            currentSynopses = data.synopses || [];
            if (projectTitleEl) projectTitleEl.textContent = data.title || "Imported";
            renderResults(currentResults);
            renderWorld(currentWorldResults);
            renderSynopsis(currentSynopses);
            uploadZone.classList.add('hidden');
            resultsArea.classList.remove('hidden');
            saveToServer();
        };
        reader.readAsText(e.target.files[0]);
    };

    if (importBtn) importBtn.onclick = () => importInput.click();

    // --- Clear Results ---
    const clearResultsBtn = document.getElementById('clear-results-btn');
    if (clearResultsBtn) {
        clearResultsBtn.addEventListener('click', async () => {
            if (!confirm("ATTENZIONE: Stai per cancellare TUTTI i risultati (Personaggi e World).\n\nConsiglio: Se vuoi solo rimuovere alcuni elementi, usa la croce rossa sulle singole card.\n\nProcedere con la CANCELLAZIONE TOTALE?")) return;

            // Backup before clear for safety
            try {
                await fetch('/api/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: projectTitleEl.textContent.trim() + "_pre_clear_backup",
                        characters: currentResults,
                        world: currentWorldResults,
                        synopses: currentSynopses,
                        chunks: currentChunks,
                        version: "3.1-pre-clear"
                    })
                });
            } catch (e) { console.error("Backup failed", e); }

            currentResults = [];
            currentWorldResults = [];
            renderResults([]);
            renderWorld([]);
            triggerAutoSave();
        });
    }

    // --- Generate Synopsis ---
    const generateSynopsisBtn = document.getElementById('generate-synopsis-btn');
    const synopsisStatus = document.getElementById('synopsis-status');

    if (generateSynopsisBtn) {
        generateSynopsisBtn.addEventListener('click', async () => {
            if (!currentManuscriptText) {
                alert("Nessun testo caricato. Carica prima un manoscritto.");
                return;
            }

            generateSynopsisBtn.disabled = true;
            generateSynopsisBtn.textContent = '⏳ Generazione...';
            if (synopsisStatus) synopsisStatus.textContent = 'Analisi in corso...';

            try {
                const response = await fetch('/api/synopsis', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: currentManuscriptText,
                        num_posts: 5
                    })
                });

                const data = await response.json();

                if (data.synopses) {
                    currentSynopses = data.synopses;
                    renderSynopsis(currentSynopses);
                    if (synopsisStatus) synopsisStatus.textContent = `${currentSynopses.length} POST generati`;
                    triggerAutoSave();
                }
            } catch (err) {
                console.error("Synopsis generation failed:", err);
                if (synopsisStatus) synopsisStatus.textContent = 'Errore generazione';
                alert("Errore durante la generazione delle sinossi");
            } finally {
                generateSynopsisBtn.disabled = false;
                generateSynopsisBtn.textContent = '✨ Genera Sinossi POST';
            }
        });
    }
});
