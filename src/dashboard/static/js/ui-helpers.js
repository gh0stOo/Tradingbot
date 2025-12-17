/**
 * Central UI Helpers for Webpanel
 * Provides loading spinners, error/success banners, and standardized API calls
 */

// ============ BANNER SYSTEM ============

function showBanner(type, title, message, detail = '') {
  // Remove existing banner
  const existing = document.getElementById('main-banner');
  if (existing) existing.remove();

  const colors = {
    success: { bg: 'bg-green-900', border: 'border-green-500', text: 'text-green-100', icon: '✓' },
    error: { bg: 'bg-red-900', border: 'border-red-500', text: 'text-red-100', icon: '✕' },
    warning: { bg: 'bg-yellow-900', border: 'border-yellow-500', text: 'text-yellow-100', icon: '⚠' },
    info: { bg: 'bg-blue-900', border: 'border-blue-500', text: 'text-blue-100', icon: 'ⓘ' }
  };

  const color = colors[type] || colors.info;

  const banner = document.createElement('div');
  banner.id = 'main-banner';
  banner.className = `${color.bg} ${color.border} border-l-4 p-4 mb-6 rounded`;
  banner.innerHTML = `
    <div class="flex items-start">
      <div class="flex-shrink-0 font-bold ${color.text}">${color.icon}</div>
      <div class="ml-3 flex-1">
        <p class="font-bold ${color.text}">${title}</p>
        <p class="${color.text}">${message}</p>
        ${detail ? `<p class="text-sm opacity-75 ${color.text} mt-1">Detail: ${detail}</p>` : ''}
      </div>
      <button onclick="this.parentElement.parentElement.remove()" class="ml-3 text-xl opacity-50 hover:opacity-100">×</button>
    </div>
  `;

  // Insert at top of content
  const content = document.querySelector('main') || document.querySelector('.container') || document.body;
  content.insertBefore(banner, content.firstChild);

  // Auto-hide success/info after 5 seconds
  if (type === 'success' || type === 'info') {
    setTimeout(() => {
      if (banner.parentElement) banner.remove();
    }, 5000);
  }
}

function showSuccess(title, message = '') {
  showBanner('success', title, message);
}

function showError(title, message = '', detail = '') {
  showBanner('error', title, message, detail);
}

function showWarning(title, message = '') {
  showBanner('warning', title, message);
}

function showInfo(title, message = '') {
  showBanner('info', title, message);
}

// ============ LOADING SPINNER ============

function showSpinner() {
  let spinner = document.getElementById('global-spinner');
  if (!spinner) {
    spinner = document.createElement('div');
    spinner.id = 'global-spinner';
    spinner.innerHTML = `
      <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="text-center">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
          <p class="text-cyan-400">Loading...</p>
        </div>
      </div>
    `;
    document.body.appendChild(spinner);
  }
  spinner.style.display = 'flex';
}

function hideSpinner() {
  const spinner = document.getElementById('global-spinner');
  if (spinner) spinner.style.display = 'none';
}

// ============ API CALL HELPER ============

async function apiCall(method, endpoint, body = null) {
  showSpinner();

  try {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };

    if (body) options.body = JSON.stringify(body);

    const response = await fetch(endpoint, options);
    
    // Check if response is ok before trying to parse JSON
    if (!response.ok) {
      let errorData = null;
      try {
        errorData = await response.json();
      } catch (e) {
        // If JSON parsing fails, use status text
        showError('API Error', `HTTP ${response.status}: ${response.statusText}`);
        return null;
      }
      
      const errorType = errorData?.error_type || 'API_ERROR';
      const message = errorData?.message || errorData?.error || `HTTP ${response.status}: ${response.statusText}`;
      const detail = errorData?.detail || '';

      showError(`${errorType}`, message, detail);
      return null;
    }

    // Parse JSON response
    let json;
    try {
      json = await response.json();
    } catch (e) {
      showError('Parse Error', 'Invalid JSON response from server');
      return null;
    }

    // Check for error response in JSON
    if (json && json.success === false) {
      const errorType = json.error_type || 'API_ERROR';
      const message = json.message || json.error || 'Unknown error';
      const detail = json.detail || '';

      showError(`${errorType}`, message, detail);
      return null;
    }

    // Success
    if (json && json.message) {
      showSuccess('Success', json.message);
    }

    return json;
  } catch (err) {
    // Network errors, CORS errors, etc.
    console.error('API call error:', err);
    const errorMessage = err.message || 'Failed to fetch';
    showError('Network Error', errorMessage, 'Bitte prüfen Sie die Verbindung zum Server');
    return null;
  } finally {
    hideSpinner();
  }
}

// ============ STALE DETECTION ============

function updateStaleStatus(lastHeartbeat) {
  const staleElement = document.getElementById('heartbeat-stale-warning');
  if (!staleElement) return;

  if (!lastHeartbeat) {
    staleElement.innerHTML = '<span class="text-red-400">⚠ No heartbeat data</span>';
    return;
  }

  const hb = new Date(lastHeartbeat);
  const now = new Date();
  const secondsAgo = Math.floor((now - hb) / 1000);

  if (secondsAgo > 10) {
    staleElement.innerHTML = `<span class="text-red-400 font-bold">⚠ STALE (${secondsAgo}s)</span>`;
  } else {
    staleElement.innerHTML = `<span class="text-green-400">✓ Fresh (${secondsAgo}s ago)</span>`;
  }
}

// ============ DISABLE/ENABLE BUTTONS ============

function disableButton(buttonId) {
  const btn = document.getElementById(buttonId);
  if (btn) {
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
  }
}

function enableButton(buttonId) {
  const btn = document.getElementById(buttonId);
  if (btn) {
    btn.disabled = false;
    btn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
}

// ============ EXPORT ============
// All functions are globally available via window object
