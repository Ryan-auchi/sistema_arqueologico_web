(function () {
    'use strict';

    const mapElement = document.getElementById('map');
    const form = document.querySelector('[data-map-filter-form]');
    const countElement = document.querySelector('[data-map-count]');

    if (!mapElement || !form) {
        return;
    }

    const map = L.map(mapElement).setView([-14.235, -51.925], 4);
    const polygonDetailZoom = 10;

    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
    }).addTo(map);

    const markerLayer = L.layerGroup().addTo(map);
    const geometryLayer = L.layerGroup().addTo(map);
    const polygonShapes = [];
    const polygonMarkers = [];

    function applyGeometryVisibility() {
        const showPolygons = map.getZoom() >= polygonDetailZoom;

        polygonShapes.forEach((polygon) => {
            if (showPolygons) {
                if (!geometryLayer.hasLayer(polygon)) {
                    geometryLayer.addLayer(polygon);
                }
            } else if (geometryLayer.hasLayer(polygon)) {
                geometryLayer.removeLayer(polygon);
            }
        });

        polygonMarkers.forEach((marker) => {
            if (showPolygons) {
                if (markerLayer.hasLayer(marker)) {
                    markerLayer.removeLayer(marker);
                }
            } else if (!markerLayer.hasLayer(marker)) {
                markerLayer.addLayer(marker);
            }
        });
    }

    function renderMarkers(results) {
        markerLayer.clearLayers();
        geometryLayer.clearLayers();
        polygonShapes.length = 0;
        polygonMarkers.length = 0;

        if (countElement) {
            countElement.textContent = String(results.length);
        }

        if (!results.length) {
            map.setView([-14.235, -51.925], 4);
            return;
        }

        const bounds = [];

        results.forEach((site) => {
            const isPublished = Boolean(site.published);
            const detailUrl = `/pesquisa/sitio/${site.id}/`;
            const popupHtml = `<strong>${site.name}</strong><br>${site.code || ''}<br>Status: ${site.published_label || 'Nao publicado'}<br>${site.municipality || ''} - ${site.state || ''}<br><a href="${detailUrl}">Abrir detalhe</a>`;

            if (site.geometry && (site.geometry.type === 'Polygon' || site.geometry.type === 'MultiPolygon')) {
                const polygon = L.geoJSON(site.geometry, {
                    style: {
                        color: isPublished ? '#14532D' : '#B91C1C',
                        fillColor: isPublished ? '#22C55E' : '#DC2626',
                        fillOpacity: isPublished ? 0.18 : 0.12,
                        weight: 2,
                    },
                });
                polygon.bindPopup(popupHtml);
                polygon.addTo(geometryLayer);
                polygonShapes.push(polygon);

                const center = polygon.getBounds().getCenter();
                const polygonMarker = isPublished
                    ? L.marker([center.lat, center.lng])
                    : L.circleMarker([center.lat, center.lng], {
                        radius: 9,
                        color: '#B91C1C',
                        fillColor: '#DC2626',
                        fillOpacity: 0.85,
                        weight: 2,
                    });
                polygonMarker.bindPopup(popupHtml);
                polygonMarker.addTo(markerLayer);
                polygonMarkers.push(polygonMarker);

                const polygonBounds = polygon.getBounds();
                if (polygonBounds.isValid()) {
                    bounds.push(polygonBounds);
                }

                return;
            }

            if (site.latitude == null || site.longitude == null) {
                return;
            }

            const marker = isPublished
                ? L.marker([site.latitude, site.longitude])
                : L.circleMarker([site.latitude, site.longitude], {
                    radius: 9,
                    color: '#B91C1C',
                    fillColor: '#DC2626',
                    fillOpacity: 0.85,
                    weight: 2,
                });
            marker.bindPopup(popupHtml);
            marker.addTo(markerLayer);
            bounds.push(L.latLng(site.latitude, site.longitude));
        });

        if (bounds.length) {
            map.fitBounds(L.latLngBounds(bounds), { padding: [30, 30] });
        }

        applyGeometryVisibility();
    }

    async function refreshMap() {
        const params = new URLSearchParams(new FormData(form));
        const apiUrl = form.dataset.apiUrl || form.action;
        const response = await fetch(`${apiUrl}?${params.toString()}`);
        const payload = await response.json();
        renderMarkers(payload.results || []);
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        refreshMap();
    });

    form.querySelectorAll('select').forEach((element) => {
        element.addEventListener('change', function () {
            refreshMap();
        });
    });

    map.on('zoomend', applyGeometryVisibility);

    refreshMap();
    setTimeout(function () { map.invalidateSize(); }, 250);
})();
