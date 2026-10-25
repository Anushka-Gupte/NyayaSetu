/**
 * NyayaSetu Dashboard Master Controller
 */

let currentUser = null;
let currentHearingSession = null;
let searchTimeout = null;

document.addEventListener('DOMContentLoaded', async () => {
  currentUser = Auth.getUser();
  if (!currentUser) {
    window.location.href = '/auth';
    return;
  }

  // Populate header profile
  document.getElementById('header-user-name').innerText = currentUser.name;
  const roleBadge = document.getElementById('header-user-role-badge');
  roleBadge.innerText = currentUser.role;

  // Initialize Lucide icons
  lucide.createIcons();

  // Load Dashboard Data
  await loadOverviewMetrics();
  await loadLiveBoards();
  await loadCasesTable();
  await loadSchedulingCases();
  await loadCauseList();
  await loadVirtualHearingDropdown();
  await loadNotifications();
  await loadAuditLogs();

  // Setup Role-Specific UI views
  applyRoleVisibility();

  // Set today's date on cause list input
  const todayStr = new Date().toISOString().split('T')[0];
  const clInput = document.getElementById('causelist-date-input');
  if (clInput) clInput.value = todayStr;
});

function applyRoleVisibility() {
  if (currentUser.role === 'COURT_CLERK' || currentUser.role === 'ADMINISTRATOR') {
    const filingCard = document.getElementById('clerk-case-filing-card');
    if (filingCard) filingCard.classList.remove('hidden');
  }
}

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(el => {
    el.classList.remove('bg-blue-600/20', 'text-blue-300', 'border-blue-500/30');
    el.classList.add('text-slate-400', 'border-transparent');
  });

  const activePane = document.getElementById(`tab-${tabId}`);
  if (activePane) activePane.classList.remove('hidden');

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.add('bg-blue-600/20', 'text-blue-300', 'border-blue-500/30');
    activeBtn.classList.remove('text-slate-400', 'border-transparent');
  }
}

// 1. Overview Metrics Ribbon
async function loadOverviewMetrics() {
  try {
    const data = await api('/dashboard/overview');
    const ribbon = document.getElementById('metrics-ribbon');
    ribbon.innerHTML = '';

    const metrics = data.metrics || {};
    const unread = data.unread_notifications || 0;

    // Update notif badge
    const badge = document.getElementById('nav-notif-badge');
    if (unread > 0) {
      badge.innerText = unread;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }

    const cards = [];

    if (currentUser.role === 'ADMINISTRATOR') {
      cards.push(
        { label: 'Total Registered Users', val: metrics.total_users || 0, icon: 'users', color: 'blue' },
        { label: 'Total Court Cases', val: metrics.total_cases || 0, icon: 'folder', color: 'indigo' },
        { label: 'Active Proceedings', val: metrics.active_cases || 0, icon: 'activity', color: 'emerald' },
        { label: 'Total Courtrooms', val: metrics.total_courtrooms || 0, icon: 'building', color: 'amber' }
      );
    } else if (currentUser.role === 'JUDGE') {
      cards.push(
        { label: 'Assigned Bench Cases', val: metrics.assigned_cases_count || 0, icon: 'briefcase', color: 'blue' },
        { label: "Today's Hearings", val: metrics.today_hearings_count || 0, icon: 'calendar', color: 'indigo' },
        { label: 'Pending Judgments', val: metrics.pending_judgments || 0, icon: 'clock', color: 'amber' },
        { label: 'Court Status', val: 'Active Bench', icon: 'check-circle', color: 'emerald' }
      );
    } else if (currentUser.role === 'COURT_CLERK') {
      cards.push(
        { label: 'Cases Filed Today', val: metrics.cases_registered_today || 0, icon: 'file-plus', color: 'blue' },
        { label: 'Total Case Repository', val: metrics.total_cases || 0, icon: 'folder', color: 'indigo' },
        { label: "Hearings Today", val: metrics.hearings_today || 0, icon: 'calendar', color: 'emerald' },
        { label: 'Pending Cause Lists', val: metrics.pending_cause_lists || 0, icon: 'file-text', color: 'amber' }
      );
    } else if (currentUser.role === 'LAWYER') {
      cards.push(
        { label: 'Assigned Cases', val: metrics.total_assigned_cases || 0, icon: 'briefcase', color: 'blue' },
        { label: 'Upcoming Hearings', val: metrics.upcoming_hearings_count || 0, icon: 'clock', color: 'indigo' },
        { label: 'Filings Admitted', val: 'Verified', icon: 'shield-check', color: 'emerald' },
        { label: 'Client Representation', val: 'Active', icon: 'user-check', color: 'teal' }
      );
    } else { // Litigant
      cards.push(
        { label: 'My Registered Cases', val: metrics.my_cases_count || 0, icon: 'folder', color: 'blue' },
        { label: 'Next Hearing Date', val: 'Listed Online', icon: 'calendar', color: 'emerald' },
        { label: 'Orders & Notices', val: 'Available', icon: 'file-text', color: 'indigo' },
        { label: 'Representation', val: 'Counsel Assigned', icon: 'user', color: 'teal' }
      );
    }

    cards.forEach(c => {
      const cardEl = document.createElement('div');
      cardEl.className = 'p-5 rounded-2xl glass-card glass-card-hover flex items-center justify-between border border-white/5';
      cardEl.innerHTML = `
        <div>
          <div class="text-[11px] font-mono text-slate-400 uppercase tracking-wider">${c.label}</div>
          <div class="text-2xl font-extrabold text-white mt-1">${c.val}</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-${c.color}-500/10 border border-${c.color}-500/20 flex items-center justify-center text-${c.color}-400">
          <i data-lucide="${c.icon}" class="w-5 h-5"></i>
        </div>
      `;
      ribbon.appendChild(cardEl);
    });

    lucide.createIcons();
  } catch (err) {
    console.warn('Overview metric load error', err);
  }
}

// 2. Live Courtroom Digital Display Boards
async function loadLiveBoards() {
  try {
    const boards = await api('/tracking/courtrooms/display-board');
    const container = document.getElementById('courtroom-boards-grid');
    container.innerHTML = '';

    boards.forEach(b => {
      const statusBadges = {
        IN_SESSION: '<span class="px-2.5 py-1 rounded text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping"></span>IN SESSION</span>',
        AVAILABLE: '<span class="px-2.5 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">AVAILABLE</span>',
        RECESS: '<span class="px-2.5 py-1 rounded text-xs font-bold bg-slate-800 text-slate-400 border border-white/10">RECESS</span>'
      };

      const card = document.createElement('div');
      card.className = 'p-6 rounded-2xl glass-card border border-white/10 flex flex-col justify-between space-y-4';
      
      let currentContent = '<p class="text-xs text-slate-500 italic">No proceeding currently in session.</p>';
      if (b.current_matter) {
        currentContent = `
          <div class="p-4 rounded-xl bg-slate-950/80 border border-rose-500/20">
            <div class="text-[10px] font-mono text-rose-400 font-bold uppercase tracking-wider">NOW HEARING:</div>
            <div class="text-base font-bold text-white mt-0.5">${b.current_matter.case_number}</div>
            <div class="text-xs text-slate-300 line-clamp-1">${b.current_matter.case_title}</div>
            <div class="mt-2 pt-2 border-t border-white/5 text-[11px] text-slate-400 flex justify-between font-mono">
              <span>Bench: ${b.current_matter.judge_name}</span>
              <span class="text-emerald-400">${b.current_matter.hearing_time}</span>
            </div>
          </div>
        `;
      }

      let judgeActionBtn = '';
      if ((currentUser.role === 'JUDGE' || currentUser.role === 'COURT_CLERK') && b.next_matter) {
        judgeActionBtn = `
          <button onclick="commenceHearingOnBoard(${b.next_matter.hearing_id})" class="w-full mt-3 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition flex items-center justify-center gap-1.5">
            <i data-lucide="play" class="w-3.5 h-3.5"></i>
            <span>Commence Next Proceeding (${b.next_matter.case_number})</span>
          </button>
        `;
      }

      card.innerHTML = `
        <div>
          <div class="flex items-center justify-between pb-3 border-b border-white/5">
            <div>
              <h4 class="font-bold text-white text-base">${b.courtroom_name}</h4>
              <p class="text-xs text-slate-400">${b.location}</p>
            </div>
            ${statusBadges[b.bench_status] || statusBadges.AVAILABLE}
          </div>
          <div class="mt-4">
            ${currentContent}
          </div>
        </div>

        <div>
          ${b.next_matter ? `
            <div class="text-[11px] text-slate-400 font-mono mt-2">
              Next in Queue: <span class="text-slate-200">${b.next_matter.case_number}</span> (${b.next_matter.hearing_time})
            </div>
          ` : ''}
          ${judgeActionBtn}
        </div>
      `;

      container.appendChild(card);
    });

    lucide.createIcons();
  } catch (err) {
    console.warn('Error loading live boards', err);
  }
}

async function commenceHearingOnBoard(hearingId) {
  try {
    await api(`/tracking/hearings/${hearingId}/start`, { method: 'PUT' });
    showToast('Proceeding commenced! Display boards updated.', 'success');
    await loadLiveBoards();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

// 3. AI Scheduling Studio
async function loadSchedulingCases() {
  try {
    const cases = await api('/cases?status=Registered');
    const select = document.getElementById('schedule-case-select');
    if (!select) return;

    select.innerHTML = '<option value="">Select a registered case...</option>';
    cases.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.case_id;
      opt.innerText = `${c.case_number} - ${c.title} (${c.case_type}, ${c.priority})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.warn('Error loading cases for scheduler', err);
  }
}

async function requestAiRecommendations() {
  const caseId = document.getElementById('schedule-case-select').value;
  const mode = document.getElementById('schedule-mode-select').value;
  if (!caseId) {
    showToast('Please select a case to generate recommendations', 'warning');
    return;
  }

  const container = document.getElementById('ai-recommendations-container');
  container.innerHTML = `
    <div class="p-8 rounded-2xl glass-card text-center text-slate-400 font-mono text-xs animate-pulse">
      Solving constraint satisfaction optimization model (analyzing judge specialization, caseloads, and courtroom capacity)...
    </div>
  `;

  try {
    const res = await api('/hearings/recommend', {
      method: 'POST',
      body: JSON.stringify({
        case_id: parseInt(caseId),
        hearing_type: mode
      })
    });

    container.innerHTML = '';
    const recs = res.recommendations || [];

    if (recs.length === 0) {
      container.innerHTML = `<div class="p-6 rounded-xl glass-card text-xs text-slate-400">No conflict-free slots found for this case priority window.</div>`;
      return;
    }

    const header = document.createElement('div');
    header.className = 'text-xs font-mono text-slate-400 mb-2';
    header.innerText = `Top ${recs.length} AI Ranked Slots for Case: ${res.case_number} (${res.case_type}, ${res.priority} Priority)`;
    container.appendChild(header);

    recs.forEach((r, idx) => {
      const card = document.createElement('div');
      card.className = 'p-5 rounded-xl glass-card border border-white/10 hover:border-blue-500/40 transition flex flex-col md:flex-row items-start md:items-center justify-between gap-4';
      
      const reasonsList = r.reasons.map(rs => `<li class="flex items-center gap-1.5"><i data-lucide="check-circle-2" class="w-3.5 h-3.5 text-emerald-400 shrink-0"></i>${rs}</li>`).join('');

      card.innerHTML = `
        <div class="space-y-1.5">
          <div class="flex items-center gap-3">
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">RANK #${idx + 1}</span>
            <span class="text-sm font-bold text-white">${r.hearing_date} at ${r.hearing_time}</span>
            <span class="text-xs font-mono text-emerald-400">${Math.round(r.confidence_score * 100)}% Confidence Match</span>
          </div>
          <div class="text-xs text-slate-300 font-medium">
            Bench: <span class="text-white">${r.judge_name}</span> (${r.judge_specialization}) • Venue: <span class="text-white">${r.courtroom_name}</span>
          </div>
          <ul class="text-[11px] text-slate-400 space-y-0.5 pt-1 font-light">
            ${reasonsList}
          </ul>
        </div>
        <button onclick="confirmHearingSchedule(${res.case_id}, ${r.judge_id}, ${r.courtroom_id}, '${r.hearing_date}', '${r.hearing_time}', '${mode}')" class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition flex items-center gap-2 shadow-lg shadow-blue-500/25 shrink-0 btn-glow">
          <i data-lucide="calendar-check" class="w-4 h-4"></i>
          <span>Schedule This Slot</span>
        </button>
      `;

      container.appendChild(card);
    });

    lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-6 rounded-xl glass-card text-xs text-rose-400 border border-rose-500/20">Error: ${err.message}</div>`;
  }
}

async function confirmHearingSchedule(caseId, judgeId, courtroomId, dateStr, timeStr, mode) {
  try {
    await api('/hearings', {
      method: 'POST',
      body: JSON.stringify({
        case_id: caseId,
        judge_id: judgeId,
        courtroom_id: courtroomId,
        hearing_date: dateStr,
        hearing_time: timeStr,
        hearing_type: mode,
        is_ai_recommended: true
      })
    });

    showToast(`Hearing confirmed on ${dateStr} at ${timeStr}!`, 'success');
    document.getElementById('ai-recommendations-container').innerHTML = '';
    await loadSchedulingCases();
    await loadLiveBoards();
    await loadCasesTable();
  } catch (err) {
    showToast(`Scheduling failed: ${err.message}`, 'error');
  }
}

// 4. Cases Table & Evidence Vault
async function loadCasesTable() {
  const query = document.getElementById('case-search-query') ? document.getElementById('case-search-query').value.trim() : '';
  const statusFilter = document.getElementById('case-filter-status') ? document.getElementById('case-filter-status').value : '';

  let url = '/cases?limit=50';
  if (query) url += `&q=${encodeURIComponent(query)}`;
  if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;

  try {
    const cases = await api(url);
    const tbody = document.getElementById('cases-table-body');
    tbody.innerHTML = '';

    if (cases.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-500 font-mono text-xs">No cases found matching query criteria.</td></tr>`;
      return;
    }

    cases.forEach(c => {
      const statusColors = {
        Registered: 'bg-blue-500/10 text-blue-300 border-blue-500/20',
        Active: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
        Pending: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
        Disposed: 'bg-slate-800 text-slate-400 border-white/10'
      };

      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-900/60 transition';
      tr.innerHTML = `
        <td class="py-3 px-4 font-mono font-bold text-white">${c.case_number}</td>
        <td class="py-3 px-4">
          <div class="font-medium text-white">${c.title}</div>
          <div class="text-[11px] text-slate-400 line-clamp-1">${c.description || 'No description provided'}</div>
        </td>
        <td class="py-3 px-4">
          <span class="font-medium text-slate-300">${c.case_type}</span>
          <span class="block text-[10px] font-mono text-slate-500">${c.priority}</span>
        </td>
        <td class="py-3 px-4 text-slate-300">${c.litigant_name || 'N/A'}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded text-[10px] font-mono font-medium border ${statusColors[c.case_status] || statusColors.Registered}">
            ${c.case_status}
          </span>
        </td>
        <td class="py-3 px-4 font-mono text-slate-400">
          <span class="text-blue-400">${c.documents_count} docs</span> • <span class="text-teal-400">${c.evidence_count} ev</span>
        </td>
        <td class="py-3 px-4 text-right">
          <button onclick="openCaseDossier(${c.case_id})" class="px-3 py-1.5 rounded-lg border border-white/10 hover:border-blue-500 bg-slate-900 text-slate-300 hover:text-white transition font-mono text-xs">
            Open Dossier
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('Error loading cases', err);
  }
}

function debounceCaseSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(loadCasesTable, 300);
}

// Case Filing
async function handleCaseRegistration(e) {
  e.preventDefault();
  const title = document.getElementById('case-title-input').value.trim();
  const type = document.getElementById('case-type-input').value;
  const priority = document.getElementById('case-priority-input').value;
  const desc = document.getElementById('case-desc-input').value.trim();

  try {
    // Default litigant ID to 7 (Rajesh Kumar) or active user if litigant
    const litigantId = currentUser.role === 'LITIGANT' ? currentUser.user_id : 7;

    const res = await api('/cases', {
      method: 'POST',
      body: JSON.stringify({
        title,
        case_type: type,
        priority,
        description: desc,
        litigant_id: litigantId
      })
    });

    showToast(`Case registered successfully! Assigned Case ID: <b>${res.case_number}</b>`, 'success');
    document.getElementById('case-title-input').value = '';
    document.getElementById('case-desc-input').value = '';
    await loadCasesTable();
    await loadSchedulingCases();
  } catch (err) {
    showToast(`Registration failed: ${err.message}`, 'error');
  }
}

// Case Dossier Modal
async function openCaseDossier(caseId) {
  const modal = document.getElementById('case-detail-modal');
  const modalContent = document.getElementById('modal-case-content');
  modal.classList.remove('hidden');
  modalContent.innerHTML = `<div class="p-8 text-center font-mono text-xs text-slate-400 animate-pulse">Loading case dossier...</div>`;

  try {
    const dossier = await api(`/cases/${caseId}`);
    document.getElementById('modal-case-number').innerText = `${dossier.case_number} - Dossier`;
    document.getElementById('modal-case-title').innerText = `${dossier.title} • ${dossier.case_type} • Status: ${dossier.case_status}`;

    modalContent.innerHTML = `
      <!-- Case Info Bar -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-900/80 border border-white/5 text-xs font-mono">
        <div><span class="text-slate-500 block">FILING DATE</span>${dossier.filing_date}</div>
        <div><span class="text-slate-500 block">PRIORITY</span><span class="text-amber-400 font-bold">${dossier.priority}</span></div>
        <div><span class="text-slate-500 block">LITIGANT</span>${dossier.litigant_name || 'N/A'}</div>
        <div><span class="text-slate-500 block">COUNSELS</span>${dossier.lawyers.length > 0 ? dossier.lawyers.map(l => l.name).join(', ') : 'None assigned'}</div>
      </div>

      <!-- Document Vault Section -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <h5 class="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-1.5">
            <i data-lucide="file-text" class="w-4 h-4 text-blue-400"></i>
            <span>Attached Documents (SHA-256 Verified)</span>
          </h5>
          <label class="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono cursor-pointer transition flex items-center gap-1">
            <i data-lucide="upload" class="w-3 h-3"></i>
            <span>Upload Document</span>
            <input type="file" onchange="uploadCaseDocument(event, ${caseId})" class="hidden">
          </label>
        </div>

        <div class="space-y-2">
          ${dossier.documents.length === 0 ? '<p class="text-xs text-slate-500 italic">No documents attached.</p>' : ''}
          ${dossier.documents.map(d => `
            <div class="p-3 rounded-xl bg-slate-950/70 border border-white/5 flex items-center justify-between text-xs">
              <div>
                <span class="font-bold text-white">${d.document_name}</span>
                <span class="text-[10px] font-mono text-blue-400 ml-2">v${d.version}</span>
                <span class="text-[10px] font-mono text-slate-500 block">SHA-256: ${d.file_hash.substring(0, 16)}...</span>
              </div>
              <a href="/api/v1/cases/${caseId}/documents/${d.document_id}/download" target="_blank" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono transition">
                Download
              </a>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Chronological History Timeline -->
      <div>
        <h5 class="text-xs font-bold text-white uppercase font-mono tracking-wider mb-3 flex items-center gap-1.5">
          <i data-lucide="git-commit" class="w-4 h-4 text-emerald-400"></i>
          <span>Chronological Case Timeline (${dossier.history.length} Events)</span>
        </h5>
        <div class="space-y-2.5 max-h-[220px] overflow-y-auto pr-2 text-xs">
          ${dossier.history.map(h => `
            <div class="p-2.5 rounded-lg bg-slate-950/50 border-l-2 border-emerald-500 text-slate-300">
              <div class="flex justify-between font-mono text-[10px] text-slate-500">
                <span class="font-bold text-emerald-400">${h.event}</span>
                <span>${h.date_time.replace('T', ' ').substring(0, 16)} UTC</span>
              </div>
              <p class="mt-1 text-slate-300 text-[11px]">${h.description}</p>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    lucide.createIcons();
  } catch (err) {
    modalContent.innerHTML = `<div class="p-4 text-xs text-rose-400">Error: ${err.message}</div>`;
  }
}

function closeCaseModal() {
  document.getElementById('case-detail-modal').classList.add('hidden');
}

async function uploadCaseDocument(e, caseId) {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', 'Petition');

  try {
    await api(`/cases/${caseId}/documents`, {
      method: 'POST',
      body: formData
    });
    showToast(`Uploaded ${file.name} successfully!`, 'success');
    await openCaseDossier(caseId);
    await loadCasesTable();
  } catch (err) {
    showToast(`Upload failed: ${err.message}`, 'error');
  }
}

// 5. Daily Cause List
async function loadCauseList() {
  const dateVal = document.getElementById('causelist-date-input').value;
  const container = document.getElementById('causelist-table-container');

  try {
    const causeLists = await api(`/cause-lists?date_from=${dateVal}&date_to=${dateVal}`);
    if (causeLists.length === 0) {
      container.innerHTML = `
        <div class="p-12 text-center text-slate-400 text-xs font-mono space-y-3">
          <p>No cause list officially generated for ${dateVal}.</p>
          ${currentUser.role === 'COURT_CLERK' || currentUser.role === 'ADMINISTRATOR' ? `
            <button onclick="generateDailyCauseList()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition shadow-lg shadow-blue-500/20">
              Compile & Generate Cause List for ${dateVal}
            </button>
          ` : ''}
        </div>
      `;
      return;
    }

    const cl = causeLists[0];
    const entries = cl.entries || [];

    let rowsHtml = '';
    entries.forEach((e, idx) => {
      rowsHtml += `
        <tr class="hover:bg-slate-900/60 transition">
          <td class="py-2.5 px-4 font-mono">${idx + 1}</td>
          <td class="py-2.5 px-4 font-bold text-blue-400 font-mono">${e.hearing_time}</td>
          <td class="py-2.5 px-4 font-bold text-white font-mono">${e.case_number}</td>
          <td class="py-2.5 px-4 text-slate-300">${e.case_title}</td>
          <td class="py-2.5 px-4 text-slate-300">${e.judge_name}</td>
          <td class="py-2.5 px-4 font-mono text-slate-400">${e.courtroom_name}</td>
          <td class="py-2.5 px-4 text-slate-300 font-mono text-[11px]">${e.hearing_type}</td>
        </tr>
      `;
    });

    container.innerHTML = `
      <div class="p-4 border-b border-white/5 flex items-center justify-between text-xs font-mono">
        <div><b>${cl.court_name}</b> • Total Matters: ${cl.total_cases}</div>
        <div>Status: <span class="${cl.is_published ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}">${cl.is_published ? 'PUBLISHED' : 'DRAFT'}</span></div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-900 text-slate-400 font-mono text-[11px] uppercase">
            <tr>
              <th class="py-3 px-4">#</th>
              <th class="py-3 px-4">Time</th>
              <th class="py-3 px-4">Case ID</th>
              <th class="py-3 px-4">Dispute Title</th>
              <th class="py-3 px-4">Bench</th>
              <th class="py-3 px-4">Courtroom</th>
              <th class="py-3 px-4">Mode</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            ${rowsHtml || '<tr><td colspan="7" class="py-6 text-center text-slate-500 font-mono">No matters scheduled.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    console.warn('Error loading cause list', err);
  }
}

async function generateDailyCauseList() {
  const dateVal = document.getElementById('causelist-date-input').value;
  try {
    await api('/cause-lists/generate', {
      method: 'POST',
      body: JSON.stringify({ date: dateVal })
    });
    showToast(`Daily cause list generated for ${dateVal}!`, 'success');
    await loadCauseList();
  } catch (err) {
    showToast(`Generation failed: ${err.message}`, 'error');
  }
}

async function downloadCauseListPdf() {
  const dateVal = document.getElementById('causelist-date-input').value;
  try {
    const causeLists = await api(`/cause-lists?date_from=${dateVal}&date_to=${dateVal}`);
    if (causeLists.length > 0) {
      window.open(`/api/v1/cause-lists/${causeLists[0].cause_list_id}/pdf`, '_blank');
    } else {
      showToast('No cause list exists for this date. Compile it first.', 'warning');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function exportIcalSync() {
  window.open('/api/v1/cause-lists/calendar/export.ics', '_blank');
  showToast('iCalendar (.ics) exported for Google Calendar / Outlook sync!', 'success');
}

// 6. Virtual Courtroom & Live Transcription
async function loadVirtualHearingDropdown() {
  try {
    const hearings = await api('/hearings?limit=20');
    const select = document.getElementById('virtual-hearing-select');
    if (!select) return;

    select.innerHTML = '<option value="">Select a Virtual Hearing...</option>';
    hearings.forEach(h => {
      const opt = document.createElement('option');
      opt.value = h.hearing_id;
      opt.innerText = `Hearing #${h.hearing_id} (${h.case_number}) - ${h.hearing_date} ${h.hearing_time}`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.warn('Error loading virtual hearings', err);
  }
}

async function joinSelectedVirtualHearing() {
  const hearingId = document.getElementById('virtual-hearing-select').value;
  if (!hearingId) {
    showToast('Please select a virtual hearing first', 'warning');
    return;
  }

  try {
    // 1. Ensure online session exists or create it
    const session = await api('/virtual-court/sessions', {
      method: 'POST',
      body: JSON.stringify({ hearing_id: parseInt(hearingId) })
    });

    currentHearingSession = session;

    // 2. Join the session
    const joinRes = await api(`/virtual-court/sessions/${session.online_hearing_id}/join`, {
      method: 'POST'
    });

    document.getElementById('vc-room-title').innerText = `${joinRes.room_name} (${joinRes.role})`;
    document.getElementById('vc-viewport-header').innerText = `Session Connected`;
    document.getElementById('vc-viewport-sub').innerText = `Joined as ${joinRes.participant_name} • Video Conference Link Active`;
    
    const linkBox = document.getElementById('vc-live-link-box');
    linkBox.classList.remove('hidden');
    linkBox.innerHTML = `Meeting URL: <a href="${joinRes.meeting_url}" target="_blank" class="underline text-blue-300">${joinRes.meeting_url}</a>`;

    showToast(`Connected to virtual courtroom!`, 'success');
    await refreshTranscriptFeed(session.online_hearing_id);
    await refreshAttendeesCounter(session.online_hearing_id);
  } catch (err) {
    showToast(`Access Denied: ${err.message}`, 'error');
  }
}

async function refreshAttendeesCounter(onlineHearingId) {
  try {
    const attendees = await api(`/virtual-court/sessions/${onlineHearingId}/attendees`);
    const counter = document.getElementById('vc-attendees-counter');
    if (counter) counter.innerText = `Attendees Present: ${attendees.length}`;
  } catch {}
}

async function refreshTranscriptFeed(onlineHearingId) {
  const feed = document.getElementById('vc-transcript-feed');
  try {
    const t = await api(`/virtual-court/sessions/${onlineHearingId}/transcript`);
    feed.innerHTML = `<pre class="whitespace-pre-wrap font-mono text-[11px] text-slate-300">${t.transcript_text}</pre>`;
  } catch {
    feed.innerHTML = `<p class="text-slate-500 italic text-[11px]">Proceeding in session. Transcript will compile upon hearing conclusion.</p>`;
  }
}

async function toggleVcRecording() {
  if (!currentHearingSession) {
    showToast('No active hearing session', 'warning');
    return;
  }
  const btn = document.getElementById('vc-rec-btn');
  try {
    const res = await api(`/virtual-court/sessions/${currentHearingSession.online_hearing_id}/recording?enable=true`, {
      method: 'POST'
    });
    showToast('Recording activated! Audio/video stream is being securely archived.', 'info');
    btn.classList.add('bg-rose-600', 'text-white');
  } catch (err) {
    showToast(`Recording control restricted: ${err.message}`, 'error');
  }
}

async function concludeHearingSession() {
  if (!currentHearingSession) {
    showToast('No active hearing session', 'warning');
    return;
  }

  try {
    const res = await api(`/virtual-court/sessions/${currentHearingSession.online_hearing_id}/end`, {
      method: 'POST'
    });
    showToast('Proceeding concluded! AI Transcript automatically compiled.', 'success');
    await refreshTranscriptFeed(currentHearingSession.online_hearing_id);
    await loadLiveBoards();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

function downloadTranscriptPdf() {
  if (currentHearingSession) {
    window.open(`/api/v1/virtual-court/sessions/${currentHearingSession.online_hearing_id}/transcript/pdf`, '_blank');
  } else {
    showToast('Join a hearing session first.', 'warning');
  }
}

// 7. Notifications & Audit Logs
async function loadNotifications() {
  try {
    const notifs = await api('/notifications?limit=25');
    const container = document.getElementById('notifications-list');
    container.innerHTML = '';

    if (notifs.length === 0) {
      container.innerHTML = `<p class="text-slate-500 font-mono text-xs italic">No notifications.</p>`;
      return;
    }

    notifs.forEach(n => {
      const item = document.createElement('div');
      item.className = `p-3 rounded-xl border text-xs transition ${n.is_read ? 'bg-slate-950/40 border-white/5 text-slate-400' : 'bg-blue-950/20 border-blue-500/20 text-slate-200'}`;
      item.innerHTML = `
        <div class="flex items-center justify-between mb-1">
          <span class="font-bold text-white">${n.title}</span>
          <span class="text-[10px] font-mono text-slate-500">${n.date_time.replace('T', ' ').substring(0, 16)}</span>
        </div>
        <p class="text-[11px] text-slate-300 leading-relaxed">${n.message.replace(/\n/g, '<br/>')}</p>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.warn('Error loading notifications', err);
  }
}

async function markAllNotificationsRead() {
  try {
    await api('/notifications/read-all', { method: 'PUT' });
    showToast('All notifications marked as read', 'success');
    await loadNotifications();
    await loadOverviewMetrics();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadAuditLogs() {
  const container = document.getElementById('audit-logs-list');
  if (currentUser.role !== 'ADMINISTRATOR') {
    container.innerHTML = `<p class="text-slate-500 italic text-[11px]">Audit trail access restricted to System Administrators (SRS NFR-5.3.7).</p>`;
    return;
  }

  try {
    const logs = await api('/audit-logs?limit=30');
    container.innerHTML = '';
    logs.forEach(l => {
      const el = document.createElement('div');
      el.className = 'p-2 rounded border border-white/5 bg-slate-950/60 flex items-start justify-between gap-2';
      el.innerHTML = `
        <div>
          <span class="font-bold text-emerald-400">${l.action}</span>
          <span class="text-slate-500 ml-1.5">[${l.entity_type}]</span>
          <div class="text-[11px] text-slate-300 mt-0.5">${l.details || ''}</div>
        </div>
        <span class="text-[10px] text-slate-500 shrink-0">${l.date_time.substring(11, 19)} UTC</span>
      `;
      container.appendChild(el);
    });
  } catch (err) {
    console.warn('Error loading audit logs', err);
  }
}

// Quick Demo Role Switcher
async function switchDemoRole(username) {
  try {
    const res = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username_or_email: username,
        password: 'Password@123'
      })
    });

    Auth.setAuth(res.access_token, {
      user_id: res.user_id,
      name: res.name,
      email: res.email,
      username: res.username,
      role: res.role
    });

    showToast(`Switched active role to: <b>${res.role}</b> (${res.name})`, 'success');
    setTimeout(() => {
      window.location.reload();
    }, 400);
  } catch (err) {
    showToast(`Role switch failed: ${err.message}`, 'error');
  }
}

function handleLogout() {
  Auth.clearAuth();
  window.location.href = '/auth';
}
