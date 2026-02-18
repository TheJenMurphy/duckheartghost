/**
 * RABBIT HOLE NAVIGATION
 * Cross-links between Ingredients, Regulators, and Research pages
 *
 * Usage: Include after HowWeKnowData.js on ingredient/regulator/research pages
 */

const RabbitHoleNav = {

  // Map dirty_list keys to regulator slugs
  DIRTY_LIST_TO_REGULATOR: {
    'eu_annex_ii': 'echa-reach',
    'eu_annex_iii': 'echa-reach',
    'ifra_standards': 'ifra',
    'prop_65': 'fda',
    'safe_cosmetics_red': 'campaign-for-safe-cosmetics',
    'sephora_clean': null,  // Retailer, not regulator
    'target_clean': null,   // Retailer, not regulator
    'wholefoods_premium': null, // Retailer, not regulator
    'beautycounter_never': null, // Brand list, not regulator
    'cir_unsafe': 'cir',
    'ewg_high': 'ewg',
    'health_canada': 'health-canada',
    'sccs_concern': 'sccs',
    'made_safe_banned': 'made-safe',
  },

  // Regulator display names
  REGULATOR_NAMES: {
    'campaign-for-safe-cosmetics': 'Campaign for Safe Cosmetics',
    'ifra': 'IFRA',
    'echa-reach': 'EU ECHA/REACH',
    'nmpa-china': 'NMPA China',
    'think-dirty': 'Think Dirty',
    'natrue': 'NATRUE',
    'cosmos-ecocert': 'COSMOS/ECOCERT',
    'made-safe': 'MADE SAFE',
    'iheartclean': 'iHeartClean',
    'leaping-bunny': 'Leaping Bunny',
    'health-canada': 'Health Canada',
    'sccs': 'SCCS',
    'fda': 'FDA',
    'eu-cosing': 'EU CosIng',
    'cir': 'CIR',
    'ewg': 'EWG',
  },

  // Slugify helper
  slugify: function(text) {
    return text.toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  },

  // Get ingredient data from HowWeKnowData
  getIngredientData: function(slug) {
    if (window.HowWeKnowData && window.HowWeKnowData[slug]) {
      return window.HowWeKnowData[slug];
    }
    return null;
  },

  // Find ingredients flagged by a regulator
  getIngredientsByRegulator: function(regulatorSlug) {
    if (!window.HowWeKnowData) return [];

    const results = [];
    const self = this;

    // Find which dirty_list keys map to this regulator
    const matchingLists = [];
    Object.keys(this.DIRTY_LIST_TO_REGULATOR).forEach(function(listKey) {
      if (self.DIRTY_LIST_TO_REGULATOR[listKey] === regulatorSlug) {
        matchingLists.push(listKey);
      }
    });

    if (matchingLists.length === 0) return [];

    // Search all ingredients
    Object.keys(window.HowWeKnowData).forEach(function(slug) {
      const data = window.HowWeKnowData[slug];
      if (data.dirty_lists && data.dirty_lists.length > 0) {
        data.dirty_lists.forEach(function(dl) {
          if (matchingLists.indexOf(dl.list) !== -1) {
            results.push({
              slug: slug,
              name: data.name,
              status: dl.status,
              reason: dl.reason
            });
          }
        });
      }
    });

    return results;
  },

  // Get regulators for an ingredient
  getRegulatorsForIngredient: function(ingredientSlug) {
    const data = this.getIngredientData(ingredientSlug);
    if (!data || !data.dirty_lists) return [];

    const regulators = [];
    const seen = {};
    const self = this;

    data.dirty_lists.forEach(function(dl) {
      const regSlug = self.DIRTY_LIST_TO_REGULATOR[dl.list];
      if (regSlug && !seen[regSlug]) {
        seen[regSlug] = true;
        regulators.push({
          slug: regSlug,
          name: self.REGULATOR_NAMES[regSlug] || regSlug,
          status: dl.status,
          list: dl.list
        });
      }
    });

    return regulators;
  },

  // Render regulator links on ingredient page
  renderRegulatorLinks: function(container, ingredientSlug) {
    const regulators = this.getRegulatorsForIngredient(ingredientSlug);

    if (regulators.length === 0) {
      container.innerHTML = '<div class="rh-empty">No regulatory flags</div>';
      return;
    }

    let html = '<div class="rh-section">';
    html += '<div class="rh-header">Flagged By Regulators</div>';
    html += '<div class="rh-links">';

    regulators.forEach(function(reg) {
      const statusClass = reg.status || 'flagged';
      html += '<a href="/regulators/' + reg.slug + '" class="rh-link rh-' + statusClass + '">';
      html += '<span class="rh-badge">' + statusClass + '</span>';
      html += '<span class="rh-name">' + reg.name + '</span>';
      html += '<span class="rh-arrow">→</span>';
      html += '</a>';
    });

    html += '</div></div>';
    container.innerHTML = html;
  },

  // Render ingredient links on regulator page
  renderIngredientLinks: function(container, regulatorSlug, limit) {
    limit = limit || 20;
    const ingredients = this.getIngredientsByRegulator(regulatorSlug);

    if (ingredients.length === 0) {
      container.innerHTML = '<div class="rh-empty">No ingredients flagged</div>';
      return;
    }

    let html = '<div class="rh-section">';
    html += '<div class="rh-header">Ingredients on This List (' + ingredients.length + ')</div>';
    html += '<div class="rh-links">';

    const shown = ingredients.slice(0, limit);
    shown.forEach(function(ing) {
      const statusClass = ing.status || 'flagged';
      html += '<a href="/ingredients/' + ing.slug + '" class="rh-link rh-' + statusClass + '">';
      html += '<span class="rh-badge">' + statusClass + '</span>';
      html += '<span class="rh-name">' + ing.name + '</span>';
      html += '<span class="rh-arrow">→</span>';
      html += '</a>';
    });

    if (ingredients.length > limit) {
      html += '<div class="rh-more">+ ' + (ingredients.length - limit) + ' more ingredients</div>';
    }

    html += '</div></div>';
    container.innerHTML = html;
  },

  // Render research sources for ingredient
  renderResearchLinks: function(container, ingredientSlug) {
    const data = this.getIngredientData(ingredientSlug);

    if (!data) {
      container.innerHTML = '<div class="rh-empty">No research data</div>';
      return;
    }

    let html = '<div class="rh-section">';
    html += '<div class="rh-header">Research Sources</div>';
    html += '<div class="rh-research">';

    // PubMed
    if (data.pubmed_total_results > 0) {
      html += '<div class="rh-research-item">';
      html += '<div class="rh-research-source">PubMed</div>';
      html += '<div class="rh-research-count">' + data.pubmed_total_results + ' studies</div>';
      if (data.paper_1_title) {
        html += '<div class="rh-research-title">"' + data.paper_1_title + '"</div>';
      }
      html += '<a href="https://pubmed.ncbi.nlm.nih.gov/?term=' + encodeURIComponent(data.name) + '" target="_blank" class="rh-research-link">Search PubMed →</a>';
      html += '</div>';
    }

    // CIR
    if (data.cir_safety) {
      html += '<div class="rh-research-item">';
      html += '<div class="rh-research-source">CIR Safety Review</div>';
      html += '<div class="rh-research-verdict">' + data.cir_safety + '</div>';
      if (data.cir_url) {
        html += '<a href="' + data.cir_url + '" target="_blank" class="rh-research-link">View CIR Report →</a>';
      }
      html += '</div>';
    }

    // EWG
    if (data.ewg_score !== null && data.ewg_score !== undefined) {
      const scoreClass = data.ewg_score <= 2 ? 'low' : data.ewg_score <= 6 ? 'moderate' : 'high';
      html += '<div class="rh-research-item">';
      html += '<div class="rh-research-source">EWG Skin Deep</div>';
      html += '<div class="rh-ewg-score rh-ewg-' + scoreClass + '">' + data.ewg_score + '</div>';
      html += '<div class="rh-research-concern">' + (data.ewg_concern_level || '') + '</div>';
      if (data.ewg_url) {
        html += '<a href="' + data.ewg_url + '" target="_blank" class="rh-research-link">View on EWG →</a>';
      }
      html += '</div>';
    }

    html += '</div></div>';
    container.innerHTML = html;
  },

  // Auto-init based on page type
  init: function() {
    const self = this;

    // Inject styles
    this.injectStyles();

    // Detect page type and init appropriate navigation
    const path = window.location.pathname;

    if (path.indexOf('/ingredients/') !== -1) {
      // Ingredient page
      const slug = path.split('/ingredients/')[1].replace(/\/$/, '');
      const regContainer = document.querySelector('.rh-regulators');
      const resContainer = document.querySelector('.rh-research-sources');

      if (regContainer) self.renderRegulatorLinks(regContainer, slug);
      if (resContainer) self.renderResearchLinks(resContainer, slug);

    } else if (path.indexOf('/regulators/') !== -1) {
      // Regulator page
      const slug = path.split('/regulators/')[1].replace(/\/$/, '');
      const container = document.querySelector('.rh-ingredients');

      if (container) self.renderIngredientLinks(container, slug, 30);
    }
  },

  // Inject CSS styles
  injectStyles: function() {
    if (document.querySelector('#rh-styles')) return;

    const css = `
      .rh-section { margin: 20px 0; }
      .rh-header {
        font-size: 12px;
        font-weight: 600;
        color: rgba(255,255,255,0.6);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
      }
      .rh-links { display: flex; flex-direction: column; gap: 8px; }
      .rh-link {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        text-decoration: none;
        transition: all 0.2s ease;
        border: 1px solid rgba(255,255,255,0.1);
      }
      .rh-link:hover {
        background: rgba(255,255,255,0.1);
        border-color: rgba(168,85,247,0.5);
      }
      .rh-badge {
        font-size: 10px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 10px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }
      .rh-prohibited .rh-badge { background: rgba(239,68,68,0.15); color: #F87171; }
      .rh-restricted .rh-badge { background: rgba(249,115,22,0.15); color: #FB923C; }
      .rh-excluded .rh-badge { background: rgba(234,179,8,0.15); color: #FACC15; }
      .rh-flagged .rh-badge { background: rgba(168,85,247,0.15); color: #C084FC; }
      .rh-name { flex: 1; color: #e0e0e0; font-size: 14px; }
      .rh-arrow { color: #666; font-size: 14px; }
      .rh-empty { color: rgba(255,255,255,0.4); font-size: 13px; font-style: italic; }
      .rh-more { color: rgba(168,85,247,0.8); font-size: 12px; margin-top: 8px; }

      .rh-research { display: flex; flex-direction: column; gap: 16px; }
      .rh-research-item {
        padding: 14px;
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.08);
      }
      .rh-research-source {
        font-size: 11px;
        font-weight: 600;
        color: rgba(255,255,255,0.5);
        text-transform: uppercase;
        margin-bottom: 6px;
      }
      .rh-research-count { color: #A855F7; font-weight: 600; font-size: 18px; }
      .rh-research-title {
        color: rgba(255,255,255,0.7);
        font-size: 13px;
        margin-top: 6px;
        line-height: 1.4;
      }
      .rh-research-verdict {
        display: inline-block;
        padding: 6px 12px;
        background: rgba(59,130,246,0.15);
        color: #60A5FA;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
      }
      .rh-research-link {
        display: inline-block;
        margin-top: 10px;
        color: #A855F7;
        font-size: 12px;
        font-weight: 600;
        text-decoration: none;
      }
      .rh-research-link:hover { text-decoration: underline; }

      .rh-ewg-score {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        font-weight: bold;
        font-size: 18px;
        color: white;
      }
      .rh-ewg-low { background: #10B981; box-shadow: 0 0 15px rgba(16,185,129,0.4); }
      .rh-ewg-moderate { background: #F59E0B; box-shadow: 0 0 15px rgba(245,158,11,0.4); }
      .rh-ewg-high { background: #EF4444; box-shadow: 0 0 15px rgba(239,68,68,0.4); }
      .rh-research-concern { color: rgba(255,255,255,0.6); font-size: 12px; margin-top: 4px; }
    `;

    const style = document.createElement('style');
    style.id = 'rh-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }
};

// Auto-init when DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() { RabbitHoleNav.init(); });
} else {
  RabbitHoleNav.init();
}
