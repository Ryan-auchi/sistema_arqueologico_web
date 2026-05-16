(function () {
    'use strict';

    // ── Publish toggle ────────────────────────────────────────────────────────
    const checkbox = document.getElementById('published-checkbox-detail');
    const hiddenInput = document.getElementById('published-selected-input');
    const chip = document.getElementById('publish-chip');

    if (checkbox && hiddenInput && chip) {
        checkbox.addEventListener('change', function () {
            const isPublished = checkbox.checked;
            hiddenInput.value = isPublished ? '1' : '0';
            chip.classList.toggle('is-published', isPublished);
            chip.classList.toggle('is-unpublished', !isPublished);
            chip.textContent = isPublished ? 'Publicado' : 'Não publicado';
        });
    }

    // ── Mini-map ──────────────────────────────────────────────────────────────
    const mapEl = document.getElementById('map');
    if (!mapEl || typeof L === 'undefined') {
        return;
    }

    // Coordinates and geometry are injected as data-* attributes by the template
    const latStr = mapEl.dataset.lat;
    const lngStr = mapEl.dataset.lng;
    const lat = (latStr === 'null' || latStr === '') ? null : parseFloat(latStr);
    const lng = (lngStr === 'null' || lngStr === '') ? null : parseFloat(lngStr);

    let geometry = null;
    const geometryRaw = mapEl.dataset.geometry || '';
    if (geometryRaw) {
        try {
            geometry = JSON.parse(geometryRaw);
        } catch (e) {
            geometry = null;
        }
    }

    const hasPoint = lat !== null && lng !== null;
    const map = L.map(mapEl, { zoomControl: false }).setView(
        hasPoint ? [lat, lng] : [-14.235, -51.925],
        hasPoint ? 14 : 4
    );
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png').addTo(map);

    if (geometry && (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon')) {
        const polygonLayer = L.geoJSON(geometry, {
            style: { color: '#14532D', fillColor: '#22C55E', fillOpacity: 0.18, weight: 2 },
        }).addTo(map);
        const polygonBounds = polygonLayer.getBounds();
        if (polygonBounds.isValid()) {
            map.fitBounds(polygonBounds, { padding: [20, 20] });
        }
    } else if (hasPoint) {
        L.marker([lat, lng]).addTo(map);
    }
})();
