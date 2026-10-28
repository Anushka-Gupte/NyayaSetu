/**
 * NyayaSetu Dashboard Master Controller
 */

let currentUser = null;
let currentHearingSession = null;
let searchTimeout = null;
let managedStaffAccounts = [];

function formatCourtDateTime(value, includeDate = true) {
  const timestamp = typeof value === 'string' && !/(Z|[+-]\d{2}:\d{2})$/i.test(value) ? value + 'Z' : value;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return value || '';
  const options = includeDate
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' }
    : { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' };
  return new Intl.DateTimeFormat('en-IN', options).format(date) + ' IST';
}

function getCourtLocalDateInputValue() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Kolkata'
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
}


function formatCourtDateOnly(value) {
  if (!value) return 'Date to be confirmed';
  const date = new Date(`${value}T12:00:00+05:30`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-IN', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata'
  }).format(date);
}

function formatCourtClock(value) {
  if (!value) return '';
  const match = String(value).match(/^(\d{1,2}):(\d{2})/);
  if (!match) return value;
  const hour = Number(match[1]);
  const suffix = hour >= 12 ? 'pm' : 'am';
  return `${hour % 12 || 12}:${match[2]} ${suffix} IST`;
}
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

  // Set the local court date before loading date-dependent views.
  const clInput = document.getElementById('causelist-date-input');
  if (clInput) clInput.value = getCourtLocalDateInputValue();

  // Load only the sections each role uses on arrival.
  await loadOverviewMetrics();
  if (currentUser.role === 'LITIGANT') {
    await loadCasesTable();
    await loadCauseList();
    await loadVirtualHearingDropdown();
    await loadNotifications();
  } else {
    await loadLiveBoards();
    await loadCasesTable();
    await loadSchedulingCases();
    await loadCauseList();
    await loadVirtualHearingDropdown();
    await loadNotifications();
    await loadAuditLogs();
  }
  if (currentUser.role === 'COURT_CLERK') {
    await loadRegisteredLitigants();
    await loadRegisteredLawyers();
  }
  // Setup Role-Specific UI views
  applyRoleVisibility();

});

function applyRoleVisibility() {
  if (currentUser.role === 'ADMINISTRATOR') {
    document.getElementById('tab-btn-user-management')?.classList.remove('hidden');
    updateStaffRoleFields();
    loadManagedStaffAccounts();
    loadManagedCourtrooms();
  }

  if (currentUser.role === 'COURT_CLERK') {
    const filingCard = document.getElementById('clerk-case-filing-card');
    if (filingCard) filingCard.classList.remove('hidden');
  }

  // Conclude Proceeding button is only for Judge, Clerk, and Admin
  const vcEndBtn = document.getElementById('vc-end-btn');
  if (vcEndBtn) {
    if (['JUDGE', 'COURT_CLERK', 'ADMINISTRATOR'].includes(currentUser.role)) {
      vcEndBtn.classList.remove('hidden');
    } else {
      vcEndBtn.classList.add('hidden');
    }
  }

  if (currentUser.role === 'LITIGANT') {
    document.body.classList.add('litigant-view');
    document.getElementById('litigant-home')?.classList.remove('hidden');
    document.getElementById('notifications-heading')?.replaceChildren('Case updates & messages');
    const greetingName = document.getElementById('litigant-greeting-name');
    if (greetingName) greetingName.textContent = (currentUser.name || 'there').split(' ')[0];
    document.getElementById('metrics-ribbon')?.classList.add('hidden');
    document.getElementById('audit-trail-card')?.classList.add('hidden');
    ['live-boards', 'scheduler'].forEach(id => {
      document.getElementById(`tab-btn-${id}`)?.classList.add('hidden');
      document.getElementById(`tab-${id}`)?.classList.add('hidden');
    });
    document.getElementById('tab-btn-home')?.classList.remove('hidden');
    document.getElementById('tab-btn-cases')?.querySelector('span')?.replaceChildren('My cases');
    document.getElementById('tab-btn-causelist')?.querySelector('span')?.replaceChildren('Hearing schedule');
    document.getElementById('tab-btn-notifications')?.querySelector('span')?.replaceChildren('Updates');
    document.getElementById('tab-btn-virtual-court')?.querySelector('span')?.replaceChildren('Virtual hearings');
    document.querySelectorAll('.tab-btn').forEach(button => {
      button.classList.remove('active', 'bg-blue-600/20', 'text-blue-300', 'border-blue-500/30');
      button.setAttribute('aria-pressed', 'false');
    });
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.add('hidden'));
  }
}
// Tab Switching
function switchTab(tabId) {
  if (tabId === 'user-management' && currentUser?.role !== 'ADMINISTRATOR') return;
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  const litigantHome = document.getElementById('litigant-home');
  if (litigantHome && currentUser?.role === 'LITIGANT') litigantHome.classList.toggle('hidden', tabId !== 'home');
  document.querySelectorAll('.tab-btn').forEach(el => {
    el.setAttribute('aria-pressed', 'false');
    el.classList.remove('bg-blue-600/20', 'text-blue-300', 'border-blue-500/30');
    el.classList.add('text-slate-400', 'border-transparent');
  });

  const activePane = document.getElementById(`tab-${tabId}`);
  if (activePane) activePane.classList.remove('hidden');
  if (tabId === 'home') {
    const homeButton = document.getElementById('tab-btn-home');
    homeButton?.classList.add('active');
    homeButton?.setAttribute('aria-pressed', 'true');
    homeButton?.classList.remove('text-slate-400', 'border-transparent');
    return;
  }

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.add('active', 'bg-blue-600/20', 'text-blue-300', 'border-blue-500/30');
    activeBtn.setAttribute('aria-pressed', 'true');
    activeBtn.classList.remove('text-slate-400', 'border-transparent');
  }
}

// 1. Overview Metrics Ribbon
async function renderLitigantHome(metrics) {
  const nextHearingContainer = document.getElementById('litigant-next-hearing');
  const casesContainer = document.getElementById('litigant-cases-list');
  const cases = Array.isArray(metrics.my_cases) ? metrics.my_cases : [];
  const statusCopy = {
    Registered: { label: 'Filed', explanation: 'Your case has been registered.' },
    Active: { label: 'In court', explanation: 'Your case is active in court.' },
    Pending: { label: 'Waiting for court action', explanation: 'Your case is waiting for a hearing or decision.' },
    Disposed: { label: 'Disposed', explanation: 'The court has disposed of this case.' }
  };

  casesContainer.replaceChildren();
  if (!cases.length) {
    const empty = document.createElement('p');
    empty.className = 'litigant-empty-state';
    empty.textContent = 'No cases are linked to your account yet. If you expected to see a case here, contact the court registry.';
    casesContainer.appendChild(empty);
  } else {
    cases.forEach(caseItem => {
      const card = document.createElement('article');
      card.className = 'litigant-case-card';
      const details = statusCopy[caseItem.status] || { label: 'Status update', explanation: 'Check the case details for the latest update.' };
      const header = document.createElement('div');
      header.className = 'litigant-case-card-header';
      const number = document.createElement('span');
      number.className = 'litigant-case-number';
      number.textContent = caseItem.case_number || 'Case number unavailable';
      const status = document.createElement('span');
      status.className = 'litigant-case-status';
      status.textContent = details.label;
      header.append(number, status);
      const title = document.createElement('h3');
      title.textContent = caseItem.title || 'Case';
      const description = document.createElement('p');
      description.textContent = details.explanation;
      const action = document.createElement('button');
      action.type = 'button';
      action.className = 'litigant-secondary-action';
      action.textContent = 'View case details';
      action.setAttribute('aria-label', `View details for ${caseItem.case_number || 'this case'}`);
      action.addEventListener('click', () => openCaseDossier(caseItem.case_id));
      card.append(header, title, description, action);
      casesContainer.appendChild(card);
    });
  }

  nextHearingContainer.replaceChildren();
  let upcomingHearings = [];
  try {
    const hearings = await api('/hearings?limit=100');
    const today = getCourtLocalDateInputValue();
    upcomingHearings = hearings
      .filter(hearing => hearing.hearing_date >= today && !['Cancelled', 'Completed', 'Postponed'].includes(hearing.hearing_status))
      .sort((a, b) => `${a.hearing_date}T${a.hearing_time}`.localeCompare(`${b.hearing_date}T${b.hearing_time}`));
  } catch (err) {
    const unavailable = document.createElement('p');
    unavailable.className = 'litigant-empty-state';
    unavailable.textContent = 'Hearing information is unavailable right now. Please check the hearing schedule again.';
    nextHearingContainer.appendChild(unavailable);
    return;
  }

  if (!upcomingHearings.length) {
    const empty = document.createElement('p');
    empty.className = 'litigant-empty-state';
    empty.textContent = 'No upcoming hearing date is listed for your cases right now.';
    nextHearingContainer.appendChild(empty);
    return;
  }

  const next = upcomingHearings[0];
  const dateLabel = next.hearing_date === getCourtLocalDateInputValue() ? 'Today' : formatCourtDateOnly(next.hearing_date);
  const caseItem = cases.find(item => item.case_id === next.case_id);
  const date = document.createElement('p');
  date.className = 'next-hearing-date';
  date.textContent = dateLabel;
  const time = document.createElement('p');
  time.className = 'next-hearing-time';
  time.textContent = `${formatCourtClock(next.hearing_time)} · ${next.hearing_type || 'Court hearing'}`;
  const caseNumber = document.createElement('p');
  caseNumber.className = 'next-hearing-case';
  caseNumber.textContent = caseItem?.case_number || next.case_number || 'Case details';
  const venue = document.createElement('p');
  venue.className = 'next-hearing-venue';
  venue.textContent = [next.courtroom_name, next.courtroom_location].filter(Boolean).join(' · ') || 'Courtroom details not available';
  nextHearingContainer.append(date, time, caseNumber, venue);

  if (['Online', 'Hybrid'].includes(next.hearing_type)) {
    const joinBtn = document.createElement('button');
    joinBtn.type = 'button';
    joinBtn.className = 'mt-3 w-full py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shadow-md shadow-indigo-600/30';
    joinBtn.innerHTML = '<i data-lucide="video" class="w-3.5 h-3.5"></i><span>Join Virtual Courtroom</span>';
    joinBtn.addEventListener('click', async () => {
      switchTab('virtual-court');
      const select = document.getElementById('virtual-hearing-select');
      if (select) {
        select.value = next.hearing_id;
        await joinSelectedVirtualHearing();
      }
    });
    nextHearingContainer.append(joinBtn);
    if (window.lucide) lucide.createIcons();
  }
}
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

    if (currentUser.role === 'LITIGANT') {
      ribbon.classList.add('hidden');
      await renderLitigantHome(metrics);
      lucide.createIcons();
      return;
    }
    ribbon.classList.remove('hidden');
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
        { label: 'Bench availability', val: metrics.judge_availability || 'Not set', icon: 'check-circle', color: 'emerald' }
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
        { label: 'Active cases', val: metrics.active_assigned_cases_count || 0, icon: 'activity', color: 'emerald' },
        { label: 'Case documents', val: metrics.assigned_case_documents_count || 0, icon: 'file-text', color: 'teal' }
      );
    } else { // Litigant
      cards.push(
        { label: 'My Registered Cases', val: metrics.my_cases_count || 0, icon: 'folder', color: 'blue' },
        { label: 'Upcoming Hearings', val: metrics.upcoming_hearings_count || 0, icon: 'calendar', color: 'emerald' },
        { label: 'Case documents', val: metrics.my_case_documents_count || 0, icon: 'file-text', color: 'indigo' },
        { label: 'Assigned advocates', val: metrics.assigned_advocates_count || 0, icon: 'user', color: 'teal' }
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
        <td class="py-3 px-4 text-slate-300">${c.litigant_name || 'Not recorded'}</td>
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
    const litigantId = Number(document.getElementById('case-litigant-input').value);
    if (!litigantId) {
      showToast('Select a registered litigant before filing this case.', 'warning');
      return;
    }

    const lawyerId = Number(document.getElementById('case-lawyer-input')?.value);
    const lawyer_assignments = lawyerId ? [{ lawyer_id: lawyerId, representing_party: 'Petitioner' }] : [];

    const res = await api('/cases', {
      method: 'POST',
      body: JSON.stringify({
        title,
        case_type: type,
        priority,
        description: desc,
        litigant_id: litigantId,
        lawyer_assignments: lawyer_assignments
      })
    });

    showToast(`Case registered successfully! Assigned Case ID: <b>${res.case_number}</b>`, 'success');
    document.getElementById('case-title-input').value = '';
    document.getElementById('case-desc-input').value = '';
    const lawyerSelect = document.getElementById('case-lawyer-input');
    if (lawyerSelect) lawyerSelect.value = '';
    await loadCasesTable();
    await loadSchedulingCases();
  } catch (err) {
    showToast(`Registration failed: ${err.message}`, 'error');
  }
}

async function loadRegisteredLitigants() {
  const select = document.getElementById('case-litigant-input');
  if (!select) return;
  select.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'Select a registered litigant';
  select.appendChild(placeholder);
  try {
    const litigants = await api('/users?role=LITIGANT&limit=100');
    litigants.forEach(litigant => {
      const option = document.createElement('option');
      option.value = String(litigant.user_id);
      option.textContent = `${litigant.name} · ${litigant.username}`;
      select.appendChild(option);
    });
    select.disabled = litigants.length === 0;
    if (!litigants.length) placeholder.textContent = 'No litigant accounts registered';
  } catch (error) {
    select.disabled = true;
    placeholder.textContent = 'Could not load litigant accounts';
    showToast(error.message || 'Could not load registered litigants.', 'error');
  }
}

async function loadRegisteredLawyers() {
  const select = document.getElementById('case-lawyer-input');
  if (!select) return;
  select.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'None (Party in Person / Self-Represented)';
  select.appendChild(placeholder);
  try {
    const lawyers = await api('/users?role=LAWYER&limit=100');
    lawyers.forEach(lawyer => {
      const option = document.createElement('option');
      option.value = String(lawyer.user_id);
      option.textContent = `${lawyer.name} (${lawyer.bar_registration_no || lawyer.username})`;
      select.appendChild(option);
    });
  } catch (error) {
    console.warn('Could not load lawyers for case filing', error);
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

    const caseProgressByStatus = {
      Registered: { step: 0, label: 'Filed', message: 'Your case has been registered by the court.' },
      Active: { step: 1, label: 'In court', message: 'Your case is active and moving through court proceedings.' },
      Pending: { step: 1, label: 'In court', message: 'Your case is waiting for a hearing or court decision.' },
      Disposed: { step: 2, label: 'Disposed', message: 'The court has disposed of this case.' }
    };
    const caseProgress = caseProgressByStatus[dossier.case_status] || {
      step: 0, label: 'Filed', message: 'Current case status: ' + dossier.case_status + '.'
    };
    const caseProgressSteps = ['Filed', 'In court', 'Disposed'].map((label, index) => {
      const stateClass = index < caseProgress.step ? 'is-complete' : index === caseProgress.step ? 'is-current' : '';
      const marker = index < caseProgress.step ? '✓' : String(index + 1);
      const current = index === caseProgress.step ? 'aria-current="step"' : '';
      return `<li class="case-progress-step ${stateClass}" ${current}><span class="case-progress-marker">${marker}</span><span>${label}</span></li>`;
    }).join('');
    modalContent.innerHTML = `
      <section class="case-progress-card" aria-labelledby="case-progress-title">
        <div class="case-progress-heading">
          <div>
            <p class="case-progress-kicker"><span lang="hi">न्याय की राह</span> · NYAYA KI RAAH</p>
            <h4 id="case-progress-title">Your case progress</h4>
          </div>
          <span class="case-progress-status">${caseProgress.label}</span>
        </div>
        <p class="case-progress-message">${caseProgress.message}</p>
        <ol class="case-progress-steps" aria-label="Three broad case stages">${caseProgressSteps}</ol>
      </section>
      <!-- Case Info Bar -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-900/80 border border-white/5 text-xs font-mono">
        <div><span class="text-slate-500 block">FILING DATE</span>${dossier.filing_date}</div>
        <div><span class="text-slate-500 block">PRIORITY</span><span class="text-amber-400 font-bold">${dossier.priority}</span></div>
        <div><span class="text-slate-500 block">LITIGANT / PETITIONER</span>${dossier.litigant_name || 'Not recorded'}</div>
        <div><span class="text-slate-500 block">COUNSELS</span>${dossier.lawyers.length > 0 ? dossier.lawyers.map(l => `<span class="inline-block px-1.5 py-0.5 rounded bg-blue-950/60 border border-blue-500/30 text-blue-300 font-bold mr-1 mb-1">${l.name} [${l.representing_party || 'Counsel'}]</span>`).join('') : 'None assigned'}</div>
      </div>

      ${['COURT_CLERK', 'ADMINISTRATOR'].includes(currentUser.role) ? `
      <!-- Counsel Representation for Opponent / Respondent or Additional Counsel -->
      <div class="p-4 rounded-xl bg-slate-900/60 border border-white/5 text-xs space-y-3">
        <div class="flex items-center justify-between">
          <h5 class="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-1.5">
            <i data-lucide="scale" class="w-4 h-4 text-amber-400"></i>
            <span>Assign Counsel (Petitioner / Respondent Opponent)</span>
          </h5>
          <span class="text-[10px] font-mono text-slate-400">Record appearance upon summons</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          <select id="modal-assign-lawyer-select" class="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-2 text-xs text-white outline-none">
            <option value="">Loading advocates...</option>
          </select>
          <select id="modal-assign-party-select" class="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-2 text-xs text-white outline-none">
            <option value="Respondent" selected>Respondent Counsel (Opponent)</option>
            <option value="Petitioner">Petitioner Counsel</option>
            <option value="Intervenor">Intervenor Counsel</option>
          </select>
          <button onclick="handleAssignLawyerModal(${caseId})" class="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shadow-md shadow-indigo-500/20">
            <i data-lucide="user-plus" class="w-3.5 h-3.5"></i>
            <span>Record Appearance</span>
          </button>
        </div>
      </div>
      ` : ''}

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
              <button data-case-id="${caseId}" data-doc-id="${d.document_id}" data-doc-name="${encodeURIComponent(d.document_name)}" onclick="downloadCaseDocument(this)" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono transition cursor-pointer">
                Download
              </button>
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
                <span>${formatCourtDateTime(h.date_time)}</span>
              </div>
              <p class="mt-1 text-slate-300 text-[11px]">${h.description}</p>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    lucide.createIcons();
    if (['COURT_CLERK', 'ADMINISTRATOR'].includes(currentUser.role)) {
      await loadModalLawyersDropdown();
    }
  } catch (err) {
    modalContent.innerHTML = `<div class="p-4 text-xs text-rose-400">Error: ${err.message}</div>`;
  }
}

async function loadModalLawyersDropdown() {
  const select = document.getElementById('modal-assign-lawyer-select');
  if (!select) return;
  try {
    const lawyers = await api('/users?role=LAWYER&limit=100');
    select.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Select Advocate to Assign...';
    select.appendChild(placeholder);
    lawyers.forEach(l => {
      const opt = document.createElement('option');
      opt.value = String(l.user_id);
      opt.textContent = `${l.name} (${l.bar_registration_no || l.username})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.warn('Failed to load advocates in modal', err);
  }
}

async function handleAssignLawyerModal(caseId) {
  const lawyerId = Number(document.getElementById('modal-assign-lawyer-select')?.value);
  const party = document.getElementById('modal-assign-party-select')?.value || 'Respondent';
  if (!lawyerId) {
    showToast('Please select an advocate to assign.', 'warning');
    return;
  }
  try {
    await api(`/cases/${caseId}/lawyers`, {
      method: 'POST',
      body: JSON.stringify({
        lawyer_id: lawyerId,
        representing_party: party
      })
    });
    showToast(`Advocate assigned successfully as ${party} Counsel!`, 'success');
    await openCaseDossier(caseId);
    await loadCasesTable();
  } catch (err) {
    showToast(`Failed to assign advocate: ${err.message}`, 'error');
  }
}

function closeCaseModal() {
  document.getElementById('case-detail-modal').classList.add('hidden');
}

async function downloadCaseDocument(btn) {
  const caseId = btn.getAttribute('data-case-id');
  const docId = btn.getAttribute('data-doc-id');
  const docName = decodeURIComponent(btn.getAttribute('data-doc-name') || 'document');
  try {
    showToast(`Downloading ${docName}...`, 'info');
    const response = await api(`/cases/${caseId}/documents/${docId}/download`);
    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = docName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(downloadUrl), 30000);
    showToast(`Downloaded ${docName}`, 'success');
  } catch (err) {
    showToast(`Download failed: ${err.message}`, 'error');
  }
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
      showToast('Preparing Cause List PDF...', 'info');
      const response = await api(`/cause-lists/${causeLists[0].cause_list_id}/pdf`);
      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `CauseList_${dateVal}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.open(downloadUrl, '_blank');
      setTimeout(() => URL.revokeObjectURL(downloadUrl), 30000);
      showToast(`Daily Cause List for ${dateVal} downloaded!`, 'success');
    } else {
      showToast('No cause list exists for this date. Compile it first.', 'warning');
    }
  } catch (err) {
    showToast(`PDF download failed: ${err.message}`, 'error');
  }
}

async function exportIcalSync() {
  try {
    const response = await api('/cause-lists/calendar/export.ics');
    const downloadUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = 'nyayasetu_court_calendar.ics';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    showToast('Calendar file downloaded. Import it into your calendar app.', 'success');
  } catch (error) {
    showToast(`Calendar export failed: ${error.message}`, 'error');
  }
}

// 6. Virtual Courtroom & Live Transcription
async function loadVirtualHearingDropdown() {
  try {
    const hearings = await api('/hearings?limit=50');
    const select = document.getElementById('virtual-hearing-select');
    if (!select) return;

    select.innerHTML = '<option value="">Select a Virtual Hearing...</option>';
    const virtualHearings = hearings.filter(h => 
      ['Online', 'Hybrid'].includes(h.hearing_type) && 
      !['Cancelled', 'Completed', 'Disposed'].includes(h.hearing_status)
    );

    if (virtualHearings.length === 0) {
      select.innerHTML = '<option value="">No active virtual hearings scheduled</option>';
      return;
    }

    virtualHearings.forEach(h => {
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

    const meetingUrl = new URL(joinRes.meeting_url);
    if (meetingUrl.protocol !== 'https:') {
      throw new Error('The video conference provider must use HTTPS.');
    }

    document.getElementById('vc-room-title').innerText = `${joinRes.room_name} (${joinRes.role})`;
    document.getElementById('vc-viewport-header').innerText = `Conference ready`;
    document.getElementById('vc-viewport-sub').innerText = `Joined as ${joinRes.participant_name}. Allow microphone and camera access in the conference.`;

    const linkBox = document.getElementById('vc-live-link-box');
    linkBox.classList.remove('hidden');
    linkBox.replaceChildren();
    const linkLabel = document.createElement('span');
    linkLabel.textContent = 'Open conference in a new tab: ';
    const meetingLink = document.createElement('a');
    meetingLink.href = meetingUrl.href;
    meetingLink.target = '_blank';
    meetingLink.rel = 'noopener noreferrer';
    meetingLink.className = 'underline text-blue-300';
    meetingLink.textContent = 'Join video conference';
    linkBox.append(linkLabel, meetingLink);

    const meetingFrame = document.getElementById('vc-meeting-frame');
    if (joinRes.meeting_provider === 'google_meet') {
      // Meet is a hosted conference, so join from Google Meet in its own tab.
      meetingFrame.src = 'about:blank';
      meetingFrame.classList.add('hidden');
      document.getElementById('vc-viewport-header').innerText = 'Google Meet is ready';
      document.getElementById('vc-viewport-sub').innerText = 'Use the conference link above to join in Google Meet. Attendance in NyayaSetu records when you open and leave this session.';
    } else {
      meetingFrame.src = meetingUrl.href;
      meetingFrame.classList.remove('hidden');
    }
    document.getElementById('vc-leave-btn').classList.remove('hidden');

    showToast('Conference opened. Allow camera and microphone access to participate.', 'success');
    await refreshTranscriptFeed(session.online_hearing_id);
    await refreshAttendeesCounter(session.online_hearing_id);
  } catch (err) {
    const msg = err.message || 'Unable to join virtual courtroom';
    if (msg.includes('not open yet') || msg.includes('scheduled for')) {
      showToast(msg, 'warning');
      document.getElementById('vc-viewport-header').innerText = 'Courtroom Not In Session';
      document.getElementById('vc-viewport-sub').innerText = msg;
    } else {
      showToast(`Access Denied: ${msg}`, 'error');
    }
  }
}

async function leaveVirtualHearing() {
  if (!currentHearingSession) return;

  const frame = document.getElementById('vc-meeting-frame');
  frame.src = 'about:blank';
  frame.classList.add('hidden');
  document.getElementById('vc-leave-btn').classList.add('hidden');
  try {
    await api(`/virtual-court/sessions/${currentHearingSession.online_hearing_id}/leave`, { method: 'POST' });
    showToast('You left the conference.', 'success');
  } catch (err) {
    showToast(`Conference closed, but attendance could not be updated: ${err.message}`, 'warning');
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
    const transcript = document.createElement('pre');
    transcript.className = 'whitespace-pre-wrap font-mono text-[11px] text-slate-300';
    transcript.textContent = t.transcript_text;
    feed.replaceChildren(transcript);
  } catch {
    feed.innerHTML = `<p class="text-slate-500 italic text-[11px]">Proceeding in session. Transcript will compile upon hearing conclusion.</p>`;
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
    await leaveVirtualHearing();
    showToast('Proceeding concluded. A session record was saved; speech transcription is not configured.', 'info');
    await refreshTranscriptFeed(currentHearingSession.online_hearing_id);
    await loadLiveBoards();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

async function downloadTranscriptPdf() {
  if (!currentHearingSession) {
    showToast('Join a hearing session first.', 'warning');
    return;
  }
  try {
    showToast('Preparing transcript PDF...', 'info');
    const response = await api(`/virtual-court/sessions/${currentHearingSession.online_hearing_id}/transcript/pdf`);
    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `Hearing_Transcript_${currentHearingSession.online_hearing_id}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.open(downloadUrl, '_blank');
    setTimeout(() => URL.revokeObjectURL(downloadUrl), 30000);
    showToast('Transcript PDF downloaded successfully!', 'success');
  } catch (err) {
    showToast(`Transcript download failed: ${err.message}`, 'error');
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
          <span class="text-[10px] font-mono text-slate-500">${formatCourtDateTime(n.date_time)}</span>
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
  if (!container) return;
  if (currentUser.role !== 'ADMINISTRATOR') {
    container.textContent = 'Audit trail access is restricted to administrators.';
    return;
  }

  try {
    const logs = await api('/audit-logs?limit=30');
    container.replaceChildren();
    if (!logs.length) {
      const empty = document.createElement('p');
      empty.className = 'text-sm text-slate-600';
      empty.textContent = 'No administrative activity has been recorded yet.';
      container.appendChild(empty);
      return;
    }
    logs.forEach(l => {
      const el = document.createElement('div');
      el.className = 'flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3';
      const content = document.createElement('div');
      const action = document.createElement('p');
      action.className = 'font-semibold text-slate-900';
      action.textContent = `${l.action} · ${l.entity_type}`;
      const details = document.createElement('p');
      details.className = 'mt-1 text-sm leading-relaxed text-slate-600';
      details.textContent = l.details || 'No additional details recorded.';
      const timestamp = document.createElement('time');
      timestamp.className = 'shrink-0 text-xs text-slate-600';
      timestamp.dateTime = l.date_time;
      timestamp.textContent = formatCourtDateTime(l.date_time, false);
      content.append(action, details);
      el.append(content, timestamp);
      container.appendChild(el);
    });
  } catch (err) {
    console.warn('Error loading audit logs', err);
    container.textContent = 'Audit activity could not be loaded. Refresh to try again.';
  }
}

function updateStaffRoleFields() {
  const role = document.getElementById('staff-role')?.value;
  const clerkFields = document.getElementById('clerk-account-fields');
  const judgeFields = document.getElementById('judge-account-fields');
  const advocateFields = document.getElementById('advocate-account-fields');
  if (!clerkFields || !judgeFields || !advocateFields) return;

  clerkFields.classList.toggle('hidden', role !== 'COURT_CLERK');
  judgeFields.classList.toggle('hidden', role !== 'JUDGE');
  advocateFields.classList.toggle('hidden', role !== 'LAWYER');
  document.getElementById('staff-employee-id').required = role === 'COURT_CLERK';
  document.getElementById('staff-employee-id').disabled = role !== 'COURT_CLERK';
  document.getElementById('staff-bar-registration').required = role === 'LAWYER';
  document.getElementById('staff-bar-registration').disabled = role !== 'LAWYER';
  document.getElementById('staff-specialization').disabled = role !== 'JUDGE';
}

function setStaffAccountFeedback(message, kind = 'success') {
  const feedback = document.getElementById('staff-account-feedback');
  feedback.textContent = message;
  feedback.classList.remove('hidden', 'staff-feedback-success', 'staff-feedback-error');
  feedback.classList.add(kind === 'error' ? 'staff-feedback-error' : 'staff-feedback-success');
}

async function createStaffAccount(event) {
  event.preventDefault();
  if (currentUser?.role !== 'ADMINISTRATOR') return;
  const form = document.getElementById('staff-account-form');
  const submit = document.getElementById('staff-account-submit');
  const role = document.getElementById('staff-role').value;
  const payload = {
    name: document.getElementById('staff-name').value.trim(),
    email: document.getElementById('staff-email').value.trim(),
    mobile_no: document.getElementById('staff-mobile').value.trim(),
    username: document.getElementById('staff-username').value.trim(),
    password: document.getElementById('staff-password').value,
    role
  };

  if (role === 'COURT_CLERK') payload.employee_id = document.getElementById('staff-employee-id').value.trim();
  if (role === 'JUDGE') payload.specialization = document.getElementById('staff-specialization').value.trim() || 'General';
  if (role === 'LAWYER') payload.bar_registration_no = document.getElementById('staff-bar-registration').value.trim();

  submit.disabled = true;
  submit.textContent = 'Creating account…';
  try {
    const created = await api('/users', { method: 'POST', body: JSON.stringify(payload) });
    setStaffAccountFeedback(`${role.replace('_', ' ')} account created for ${created.name}. Sign-in username: ${created.username}.`, 'success');
    form.reset();
    updateStaffRoleFields();
    await loadManagedStaffAccounts();
  } catch (error) {
    setStaffAccountFeedback(error.message || 'Account could not be created. Check the details and try again.', 'error');
  } finally {
    submit.disabled = false;
    submit.textContent = 'Create account';
  }
}

async function loadManagedStaffAccounts() {
  if (currentUser?.role !== 'ADMINISTRATOR') return;
  const list = document.getElementById('managed-staff-list');
  if (!list) return;
  list.replaceChildren();
  const loading = document.createElement('p');
  loading.className = 'text-sm text-slate-600';
  loading.textContent = 'Loading accounts…';
  list.appendChild(loading);
  try {
    managedStaffAccounts = (await api('/users?limit=200'))
      .filter(user => ['COURT_CLERK', 'JUDGE', 'LAWYER'].includes(user.role));
    filterManagedStaffAccounts();
  } catch (error) {
    list.replaceChildren();
    const message = document.createElement('p');
    message.className = 'staff-feedback-error rounded-xl border px-4 py-3 text-sm';
    message.textContent = error.message || 'Could not load accounts.';
    list.appendChild(message);
  }
}

function filterManagedStaffAccounts() {
  const list = document.getElementById('managed-staff-list');
  if (!list || currentUser?.role !== 'ADMINISTRATOR') return;
  const search = (document.getElementById('staff-account-search')?.value || '').trim().toLocaleLowerCase();
  const roleFilter = document.getElementById('staff-account-role-filter')?.value || '';
  const matches = managedStaffAccounts.filter(user => {
    const searchable = `${user.name} ${user.username} ${user.email}`.toLocaleLowerCase();
    return (!search || searchable.includes(search)) && (!roleFilter || user.role === roleFilter);
  });
  list.replaceChildren();
  if (!managedStaffAccounts.length) {
    const empty = document.createElement('p');
    empty.className = 'text-sm leading-relaxed text-slate-600';
    empty.textContent = 'No clerk, judge, or advocate accounts have been registered yet. Create the first account using the form.';
    list.appendChild(empty);
    return;
  }
  if (!matches.length) {
    const empty = document.createElement('p');
    empty.className = 'text-sm leading-relaxed text-slate-600';
    empty.textContent = 'No staff accounts match these filters. Clear the search or choose another account type.';
    list.appendChild(empty);
    return;
  }

  matches.forEach(user => {
    const card = document.createElement('article');
    card.className = 'staff-account-card';
    const heading = document.createElement('div');
    heading.className = 'staff-account-card-heading';
    const name = document.createElement('h4');
    name.textContent = user.name;
    const role = document.createElement('span');
    role.className = 'staff-account-role';
    role.textContent = ({ COURT_CLERK: 'Court clerk', JUDGE: 'Judge', LAWYER: 'Advocate' })[user.role] || user.role;
    heading.append(name, role);
    const details = document.createElement('p');
    details.textContent = `${user.username} · ${user.email}`;
    const footer = document.createElement('div');
    footer.className = 'mt-3 flex flex-wrap items-center justify-between gap-2';
    const status = document.createElement('p');
    status.className = `staff-account-status ${user.is_active ? 'is-active' : 'is-inactive'}`;
    status.textContent = user.is_active ? 'Active account · can sign in' : 'Inactive account · sign-in disabled';
    const statusButton = document.createElement('button');
    statusButton.type = 'button';
    statusButton.className = 'min-h-11 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-amber-700';
    statusButton.textContent = user.is_active ? 'Deactivate access' : 'Reactivate access';
    statusButton.setAttribute('aria-label', `${user.is_active ? 'Deactivate' : 'Reactivate'} sign-in access for ${user.name}`);
    statusButton.addEventListener('click', () => updateManagedUserStatus(user, !user.is_active, statusButton));
    footer.append(status, statusButton);
    card.append(heading, details, footer);
    list.appendChild(card);
  });
}

async function updateManagedUserStatus(user, isActive, button) {
  if (currentUser?.role !== 'ADMINISTRATOR') return;
  if (!isActive && !window.confirm(`Deactivate sign-in access for ${user.name}? You can reactivate this account later.`)) return;
  button.disabled = true;
  try {
    await api(`/users/${user.user_id}/status`, {
      method: 'PUT',
      body: JSON.stringify({ is_active: isActive })
    });
    managedStaffAccounts = managedStaffAccounts.map(account =>
      account.user_id === user.user_id ? { ...account, is_active: isActive } : account
    );
    setStaffAccountFeedback(`${user.name}'s sign-in access is now ${isActive ? 'active' : 'deactivated'}.`, 'success');
    filterManagedStaffAccounts();
  } catch (error) {
    setStaffAccountFeedback(error.message || 'Account access could not be changed.', 'error');
    button.disabled = false;
  }
}

function setCourtroomFeedback(message, kind = 'success') {
  const feedback = document.getElementById('courtroom-feedback');
  feedback.textContent = message;
  feedback.classList.remove('hidden', 'staff-feedback-success', 'staff-feedback-error');
  feedback.classList.add(kind === 'error' ? 'staff-feedback-error' : 'staff-feedback-success');
}

async function createCourtroom(event) {
  event.preventDefault();
  if (currentUser?.role !== 'ADMINISTRATOR') return;
  const form = document.getElementById('courtroom-form');
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = 'Registering courtroom…';
  const payload = {
    courtroom_name: document.getElementById('courtroom-name').value.trim(),
    location: document.getElementById('courtroom-location').value.trim(),
    capacity: Number(document.getElementById('courtroom-capacity').value)
  };
  try {
    const courtroom = await api('/hearings/courtrooms', { method: 'POST', body: JSON.stringify(payload) });
    setCourtroomFeedback(`${courtroom.courtroom_name} has been registered.`, 'success');
    form.reset();
    await loadManagedCourtrooms();
  } catch (error) {
    setCourtroomFeedback(error.message || 'Could not register the courtroom. Check the details and try again.', 'error');
  } finally {
    submit.disabled = false;
    submit.textContent = 'Register courtroom';
  }
}

async function loadManagedCourtrooms() {
  if (currentUser?.role !== 'ADMINISTRATOR') return;
  const list = document.getElementById('managed-courtroom-list');
  if (!list) return;
  list.replaceChildren();
  const loading = document.createElement('p');
  loading.className = 'text-sm text-slate-600';
  loading.textContent = 'Loading courtrooms…';
  list.appendChild(loading);
  try {
    const courtrooms = await api('/hearings/courtrooms/available');
    list.replaceChildren();
    if (!courtrooms.length) {
      const empty = document.createElement('p');
      empty.className = 'text-sm leading-relaxed text-slate-600';
      empty.textContent = 'No courtrooms have been registered. Add courtrooms above to enable hearing scheduling.';
      list.appendChild(empty);
      return;
    }
    courtrooms.forEach(courtroom => {
      const card = document.createElement('article');
      card.className = 'staff-account-card';
      const name = document.createElement('h4');
      name.textContent = courtroom.courtroom_name;
      const location = document.createElement('p');
      location.textContent = courtroom.location;
      const capacity = document.createElement('p');
      capacity.className = 'staff-account-status';
      capacity.textContent = `Seating capacity: ${courtroom.capacity}`;
      card.append(name, location, capacity);
      list.appendChild(card);
    });
  } catch (error) {
    list.replaceChildren();
    const message = document.createElement('p');
    message.className = 'staff-feedback-error rounded-xl border px-4 py-3 text-sm';
    message.textContent = error.message || 'Could not load courtrooms.';
    list.appendChild(message);
  }
}

function toggleStaffPasswordVisibility() {
  const input = document.getElementById('staff-password');
  const button = input.parentElement.querySelector('.password-visibility-toggle');
  const isVisible = input.type === 'password';
  input.type = isVisible ? 'text' : 'password';
  button.setAttribute('aria-label', isVisible ? 'Hide password' : 'Show password');
  button.setAttribute('aria-pressed', String(isVisible));
  button.innerHTML = `<i data-lucide="${isVisible ? 'eye-off' : 'eye'}" class="h-5 w-5" aria-hidden="true"></i>`;
  lucide.createIcons();
}

function handleLogout() {
  Auth.clearAuth();
  window.location.href = '/auth';
}
