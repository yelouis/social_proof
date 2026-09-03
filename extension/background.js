/**
 * Social Proof Browser Extension - Background Service Worker.
 *
 * Implements design_local_api_and_clients.md §2 and §5:
 * 1. Holds Bearer token in extension storage, unreadable by page scripts.
 * 2. Proxies HTTP requests to the loopback API at 127.0.0.1:8787.
 * 3. Coordinates Depth 2 sidepanel opening.
 */

const API_BASE = 'http://127.0.0.1:8787';

async function getApiToken() {
  const data = await chrome.storage.local.get(['apiToken']);
  return data.apiToken || '';
}

chrome.runtime.onInstalled.addListener(() => {
  console.log('Social Proof extension initialized.');
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'RESOLVE_SELECTION') {
    handleResolve(message.payload).then(sendResponse);
    return true; // async sendResponse
  }

  if (message.type === 'OPEN_EXPANDED_VIEW') {
    chrome.storage.local.set({ activePayload: message.payload }, () => {
      if (sender.tab && sender.tab.id && chrome.sidePanel) {
        chrome.sidePanel.open({ tabId: sender.tab.id });
      }
    });
    sendResponse({ ok: true });
    return false;
  }
});

async function handleResolve(payload) {
  try {
    const token = await getApiToken();
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };

    const res = await fetch(`${API_BASE}/resolve`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      return { ok: false, error: `API error ${res.status}` };
    }

    const resolveData = await res.json();
    if (!resolveData.subjects || resolveData.subjects.length === 0) {
      return {
        ok: true,
        data: { state: 'nothing' }
      };
    }

    const subject = resolveData.subjects[0];
    const proposition = resolveData.proposition;
    const topic = (resolveData.topics && resolveData.topics.length > 0)
      ? resolveData.topics[0].query_string
      : 'global';

    // Fetch assessment for the resolved subject
    const assessRes = await fetch(`${API_BASE}/subjects/${subject.subject_id}/assessment?topic=${encodeURIComponent(topic)}`, {
      headers
    });
    const assessment = assessRes.ok ? await assessRes.json() : null;

    // Fetch timeline for contrast quote
    const timelineRes = await fetch(`${API_BASE}/subjects/${subject.subject_id}/timeline?topic=${encodeURIComponent(topic)}`, {
      headers
    });
    const timeline = timelineRes.ok ? await timelineRes.json() : null;
    const contrastQuote = (timeline && timeline.claims && timeline.claims.length > 0)
      ? timeline.claims[0]
      : null;

    return {
      ok: true,
      data: {
        state: proposition ? 'matched' : 'topic_only',
        subject,
        proposition,
        topic,
        contrastQuote,
        assessment,
        tensionCount: assessment && assessment.axis_evidence ? Object.keys(assessment.axis_evidence).length : 0
      }
    };
  } catch (err) {
    console.error('Failed to resolve with local API:', err);
    return { ok: false, error: err.message };
  }
}
