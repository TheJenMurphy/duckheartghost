/* =============================================
   DHG CARD SCRIPTS
   Card flip + accordion panels
   ============================================= */

(function() {
    'use strict';

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', initDHGCards);

    function initDHGCards() {
        var cards = document.querySelectorAll('.dhg-card');
        cards.forEach(function(card) {
            initCard(card);
        });
    }

    function initCard(card) {
        // Flip buttons
        var flipBtns = card.querySelectorAll('.dhg-flip-btn');
        flipBtns.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                card.classList.toggle('flipped');
            });
        });

        // Front panels (HYPE, DEAL) - accordion on headers
        var frontPanels = card.querySelectorAll('.dhg-front-panels .dhg-panel');
        frontPanels.forEach(function(panel) {
            var header = panel.querySelector('.dhg-panel-header');
            if (header) {
                header.addEventListener('click', function() {
                    // Close others
                    frontPanels.forEach(function(p) {
                        if (p !== panel) p.classList.remove('expanded');
                    });
                    panel.classList.toggle('expanded');
                });
            }
        });

        // Back panels (facts) - accordion on headers
        var factsPanels = card.querySelectorAll('.dhg-facts-panel');
        factsPanels.forEach(function(panel) {
            var header = panel.querySelector('.dhg-facts-panel-header');
            if (header) {
                header.addEventListener('click', function() {
                    // Close others
                    factsPanels.forEach(function(p) {
                        if (p !== panel) p.classList.remove('expanded');
                    });
                    panel.classList.toggle('expanded');
                });
            }
        });

        // Heart button toggle
        var heartBtns = card.querySelectorAll('.dhg-heart-btn');
        heartBtns.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                // Toggle all heart buttons in this card
                heartBtns.forEach(function(hb) {
                    hb.classList.toggle('dhg-heart-active');
                });
                // Could dispatch custom event for wishlist functionality
                card.dispatchEvent(new CustomEvent('dhg:heart', {
                    detail: { active: btn.classList.contains('dhg-heart-active') }
                }));
            });
        });

        // Search button
        var searchBtns = card.querySelectorAll('.dhg-search-btn');
        searchBtns.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                // Could open search modal or navigate to search
                card.dispatchEvent(new CustomEvent('dhg:search'));
            });
        });

        // Tag clicks - navigate to ingredient/attribute pages
        var tags = card.querySelectorAll('.dhg-tag[data-slug]');
        tags.forEach(function(tag) {
            tag.style.cursor = 'pointer';
            tag.addEventListener('click', function(e) {
                e.stopPropagation();
                var slug = tag.getAttribute('data-slug');
                var type = tag.getAttribute('data-type') || 'ingredients';
                if (slug) {
                    window.location.href = '/' + type + '/' + slug;
                }
            });
        });

        // Monitor badge mapping
        var badge = card.querySelector('.dhg-monitor-badge');
        if (badge) {
            var badgeText = badge.getAttribute('data-badge');
            var badgeIcons = {
                'Viral': '🔥',
                'Trending': '📈',
                'New': '✨',
                'Hot': '🔥',
                'Recalled': '⚠️',
                'Discontinued': '🚫',
                'Award Winner': '🏆',
                'Editor Pick': '⭐',
                'Flagged': '🚩',
                'Grain of Salt': '🧂'
            };
            var iconEl = badge.querySelector('.dhg-badge-icon');
            if (iconEl && badgeIcons[badgeText]) {
                iconEl.textContent = badgeIcons[badgeText];
            }
            // Hide if no badge
            if (!badgeText || badgeText === '') {
                badge.style.display = 'none';
            }
        }

        // All panels start expanded by default (showing content)
        // They collapse when clicked, accordion-style
        frontPanels.forEach(function(p) { p.classList.add('expanded'); });
        factsPanels.forEach(function(p) { p.classList.add('expanded'); });
    }

    // Expose for manual init if needed
    window.DHGCards = {
        init: initDHGCards,
        initCard: initCard
    };

})();
