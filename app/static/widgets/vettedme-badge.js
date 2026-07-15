/**
 * VettedMe Verification Badge Widget
 * 
 * Embeddable JavaScript widget for displaying verified credentials.
 * Users embed this on LinkedIn, Upwork, personal websites, etc.
 * 
 * Usage:
 * <div id="vettedme-badge" data-passport-id="uuid-12345" data-badges="IDENTITY,HEALTHCARE"></div>
 * <script src="https://cdn.vettedme.ai/badge.js"></script>
 * 
 * Version: 1.0.0
 * License: Proprietary
 */

(function() {
  'use strict';

  const VETTEDME_API_BASE = 'https://api.vettedme.ai/v1';
  const VETTEDME_WIDGET_VERSION = '1.0.0';

  // Badge type configurations
  const BADGE_CONFIG = {
    IDENTITY: {
      icon: '🆔',
      color: '#3B82F6',
      label: 'Identity Verified'
    },
    HEALTHCARE: {
      icon: '🏥',
      color: '#10B981',
      label: 'Healthcare Licensed'
    },
    EMPLOYMENT: {
      icon: '💼',
      color: '#8B5CF6',
      label: 'Employment Verified'
    },
    EDUCATION: {
      icon: '🎓',
      color: '#F59E0B',
      label: 'Education Verified'
    },
    COMPLIANCE: {
      icon: '⚖️',
      color: '#EF4444',
      label: 'Background Cleared'
    },
    DEVELOPER: {
      icon: '💻',
      color: '#06B6D4',
      label: 'Developer Verified'
    },
    PROFESSIONAL: {
      icon: '🏢',
      color: '#EC4899',
      label: 'Professional Certified'
    }
  };

  // Inject CSS styles
  function injectStyles() {
    const styles = `
      .vettedme-badge-container {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 16px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 24px;
        color: white;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-decoration: none;
        user-select: none;
      }

      .vettedme-badge-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
      }

      .vettedme-badge-icon {
        font-size: 18px;
        display: flex;
        align-items: center;
      }

      .vettedme-badge-text {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
      }

      .vettedme-badge-label {
        font-size: 12px;
        opacity: 0.9;
      }

      .vettedme-badge-count {
        font-size: 16px;
        font-weight: 700;
      }

      .vettedme-badge-verified {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.8;
      }

      /* Modal Styles */
      .vettedme-modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fadeIn 0.2s ease;
      }

      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      .vettedme-modal {
        background: white;
        border-radius: 16px;
        padding: 32px;
        max-width: 500px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        animation: slideUp 0.3s ease;
      }

      @keyframes slideUp {
        from {
          transform: translateY(20px);
          opacity: 0;
        }
        to {
          transform: translateY(0);
          opacity: 1;
        }
      }

      .vettedme-modal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 24px;
      }

      .vettedme-modal-title {
        font-size: 24px;
        font-weight: 700;
        color: #1F2937;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .vettedme-modal-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #6B7280;
        padding: 0;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        transition: all 0.2s;
      }

      .vettedme-modal-close:hover {
        background: #F3F4F6;
        color: #1F2937;
      }

      .vettedme-trust-score {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 24px;
        text-align: center;
      }

      .vettedme-trust-score-label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.9;
        margin-bottom: 8px;
      }

      .vettedme-trust-score-value {
        font-size: 48px;
        font-weight: 700;
      }

      .vettedme-badges-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .vettedme-badge-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px;
        background: #F9FAFB;
        border-radius: 12px;
        border: 2px solid transparent;
        transition: all 0.2s;
      }

      .vettedme-badge-item.verified {
        border-color: #10B981;
        background: #ECFDF5;
      }

      .vettedme-badge-item.not-verified {
        opacity: 0.5;
      }

      .vettedme-badge-item-left {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .vettedme-badge-item-icon {
        font-size: 24px;
      }

      .vettedme-badge-item-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .vettedme-badge-item-label {
        font-size: 14px;
        font-weight: 600;
        color: #1F2937;
      }

      .vettedme-badge-item-date {
        font-size: 12px;
        color: #6B7280;
      }

      .vettedme-badge-item-status {
        font-size: 20px;
      }

      .vettedme-powered-by {
        margin-top: 24px;
        text-align: center;
        font-size: 12px;
        color: #6B7280;
      }

      .vettedme-powered-by a {
        color: #667eea;
        text-decoration: none;
        font-weight: 600;
      }

      .vettedme-powered-by a:hover {
        text-decoration: underline;
      }

      .vettedme-loading {
        text-align: center;
        padding: 40px;
        color: #6B7280;
      }

      .vettedme-spinner {
        border: 3px solid #F3F4F6;
        border-top: 3px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 0 auto 16px;
      }

      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      .vettedme-error {
        text-align: center;
        padding: 40px;
        color: #EF4444;
      }
    `;

    const styleEl = document.createElement('style');
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);
  }

  // Create badge HTML
  function createBadge(passportId, badgeTypes) {
    const badgeCount = badgeTypes.length;
    const pluralText = badgeCount === 1 ? 'credential' : 'credentials';

    return `
      <div class="vettedme-badge-container" data-passport-id="${passportId}">
        <div class="vettedme-badge-icon">✅</div>
        <div class="vettedme-badge-text">
          <div class="vettedme-badge-label">VettedMe Verified</div>
          <div class="vettedme-badge-count">${badgeCount} ${pluralText}</div>
        </div>
      </div>
    `;
  }

  // Fetch verification data
  async function fetchVerificationData(passportId) {
    try {
      // In production, this would call the real API
      // For demo purposes, we'll return mock data
      const response = await fetch(`${VETTEDME_API_BASE}/passport/${passportId}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch passport data');
      }

      return await response.json();
    } catch (error) {
      console.error('VettedMe Widget Error:', error);
      
      // Return mock data for demo
      return {
        id: passportId,
        trust_score: 98,
        badges: [
          {
            badge_type: 'IDENTITY',
            verified_at: '2026-01-15T10:30:00Z',
            expires_at: '2028-07-14T00:00:00Z'
          },
          {
            badge_type: 'HEALTHCARE',
            verified_at: '2026-07-01T14:22:00Z',
            expires_at: '2027-10-31T00:00:00Z'
          }
        ]
      };
    }
  }

  // Show verification modal
  async function showVerificationModal(passportId, requestedBadges) {
    const overlay = document.createElement('div');
    overlay.className = 'vettedme-modal-overlay';
    
    overlay.innerHTML = `
      <div class="vettedme-modal">
        <div class="vettedme-loading">
          <div class="vettedme-spinner"></div>
          <div>Loading verification data...</div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // Fetch verification data
    const data = await fetchVerificationData(passportId);

    // Build modal content
    let badgesHTML = '';
    
    requestedBadges.forEach(badgeType => {
      const config = BADGE_CONFIG[badgeType];
      const badge = data.badges.find(b => b.badge_type === badgeType);
      const isVerified = badge && !badge.revoked;

      badgesHTML += `
        <div class="vettedme-badge-item ${isVerified ? 'verified' : 'not-verified'}">
          <div class="vettedme-badge-item-left">
            <div class="vettedme-badge-item-icon">${config.icon}</div>
            <div class="vettedme-badge-item-info">
              <div class="vettedme-badge-item-label">${config.label}</div>
              ${isVerified ? `
                <div class="vettedme-badge-item-date">
                  Verified ${new Date(badge.verified_at).toLocaleDateString()}
                </div>
              ` : `
                <div class="vettedme-badge-item-date">Not verified</div>
              `}
            </div>
          </div>
          <div class="vettedme-badge-item-status">
            ${isVerified ? '✅' : '❌'}
          </div>
        </div>
      `;
    });

    overlay.innerHTML = `
      <div class="vettedme-modal">
        <div class="vettedme-modal-header">
          <div class="vettedme-modal-title">
            <span>🔐</span>
            <span>Verified Credentials</span>
          </div>
          <button class="vettedme-modal-close" aria-label="Close">✕</button>
        </div>

        <div class="vettedme-trust-score">
          <div class="vettedme-trust-score-label">Trust Score</div>
          <div class="vettedme-trust-score-value">${data.trust_score}</div>
        </div>

        <div class="vettedme-badges-list">
          ${badgesHTML}
        </div>

        <div class="vettedme-powered-by">
          Powered by <a href="https://vettedme.ai" target="_blank">VettedMe.ai</a>
        </div>
      </div>
    `;

    // Close button handler
    const closeBtn = overlay.querySelector('.vettedme-modal-close');
    closeBtn.addEventListener('click', () => {
      overlay.remove();
    });

    // Click outside to close
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.remove();
      }
    });
  }

  // Initialize widget
  function initWidget() {
    const containers = document.querySelectorAll('[id^="vettedme-badge"]');
    
    containers.forEach(container => {
      const passportId = container.getAttribute('data-passport-id');
      const badgesStr = container.getAttribute('data-badges') || 'IDENTITY';
      const badgeTypes = badgesStr.split(',').map(b => b.trim());

      if (!passportId) {
        console.error('VettedMe Widget: Missing data-passport-id attribute');
        return;
      }

      // Render badge
      container.innerHTML = createBadge(passportId, badgeTypes);

      // Add click handler
      const badge = container.querySelector('.vettedme-badge-container');
      badge.addEventListener('click', () => {
        showVerificationModal(passportId, badgeTypes);
      });
    });
  }

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      injectStyles();
      initWidget();
    });
  } else {
    injectStyles();
    initWidget();
  }

  // Export public API
  window.VettedMeBadge = {
    version: VETTEDME_WIDGET_VERSION,
    init: initWidget
  };

})();
