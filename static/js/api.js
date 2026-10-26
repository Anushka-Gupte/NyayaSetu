/**
 * NyayaSetu Unified Client & WebSocket Gateway
 */

const API_BASE = '/api/v1';

const Auth = {
  getToken: () => localStorage.getItem('nyayasetu_token'),
  getUser: () => {
    try {
      return JSON.parse(localStorage.getItem('nyayasetu_user') || 'null');
    } catch {
      return null;
    }
  },
  setAuth: (token, user) => {
    localStorage.setItem('nyayasetu_token', token);
    localStorage.setItem('nyayasetu_user', JSON.stringify(user));
  },
  clearAuth: () => {
    localStorage.removeItem('nyayasetu_token');
    localStorage.removeItem('nyayasetu_user');
  },
  isAuthenticated: () => !!localStorage.getItem('nyayasetu_token')
};

async function api(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = options.headers || {};
  
  const token = Auth.getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    headers
  });

  if (response.status === 401) {
    Auth.clearAuth();
    if (!window.location.pathname.includes('/auth') && window.location.pathname !== '/') {
      window.location.href = '/auth';
    }
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail;
      const message = Array.isArray(detail)
        ? detail.map(item => typeof item === 'string' ? item : item?.msg || 'Invalid input').join(' ')
        : typeof detail === 'string' ? detail : 'API request failed';
      throw new Error(message);
    }
    return data;
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'API request failed');
  }

  return response;
}

// Global Toast Notification Helper
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'fixed bottom-6 right-6 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const borderColors = {
    info: 'border-blue-500/40 bg-slate-900/90 text-blue-200',
    success: 'border-emerald-500/40 bg-slate-900/90 text-emerald-200',
    warning: 'border-amber-500/40 bg-slate-900/90 text-amber-200',
    error: 'border-rose-500/40 bg-slate-900/90 text-rose-200'
  };

  toast.className = `p-4 rounded-xl border backdrop-blur-md shadow-2xl pointer-events-auto transition-all duration-300 transform translate-y-2 opacity-0 flex items-start gap-3 ${borderColors[type] || borderColors.info}`;
  toast.innerHTML = `
    <div class="flex-1 text-sm font-medium leading-relaxed">${message}</div>
    <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-white text-xs">&times;</button>
  `;

  toastContainer.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// Real-Time WebSocket Listener
class CourtWebSocket {
  constructor() {
    this.ws = null;
    this.reconnectTimer = null;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/tracking/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected to NyayaSetu Live Courtroom Gateway');
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.handleEvent(payload);
        } catch (e) {
          console.error('[WebSocket] Malformed message', e);
        }
      };

      this.ws.onclose = () => {
        console.log('[WebSocket] Connection closed. Reconnecting in 5s...');
        this.reconnectTimer = setTimeout(() => this.connect(), 5000);
      };

      this.ws.onerror = (err) => {
        console.warn('[WebSocket] Error', err);
        this.ws.close();
      };
    } catch (e) {
      console.warn('[WebSocket] Not connected', e);
    }
  }

  handleEvent(payload) {
    if (payload.event === 'NOW_HEARING') {
      const d = payload.data || {};
      showToast(`⚡ <b>NOW HEARING in ${d.courtroom_name}:</b><br/>${d.case_number} before ${d.judge_name}`, 'info');
      if (window.onNowHearingUpdate) {
        window.onNowHearingUpdate(d);
      }
    } else if (payload.event === 'HEARING_STATUS_CHANGED') {
      const d = payload.data || {};
      showToast(`📢 <b>Hearing Status Update:</b> Hearing #${d.hearing_id} is now <i>${d.status}</i>`, 'warning');
      if (window.onHearingStatusUpdate) {
        window.onHearingStatusUpdate(d);
      }
    } else if (payload.event === 'NEW_NOTIFICATION') {
      const d = payload.data || {};
      showToast(`🔔 <b>${d.title}</b><br/>${d.message}`, 'success');
      if (window.onNotificationUpdate) {
        window.onNotificationUpdate(d);
      }
    }
  }
}

const courtWs = new CourtWebSocket();
courtWs.connect();
