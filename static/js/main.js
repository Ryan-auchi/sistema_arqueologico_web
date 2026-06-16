function getBadgeClass(value) {
	return `is-${String(value || '').toLowerCase()}`;
}

function buildSiteCard(site) {
	const badgeClass = getBadgeClass(site.conservation);
	return `
		<article class="site-card">
			<span class="badge ${badgeClass}">${site.badge || site.conservation}</span>
			<h3>${site.name}</h3>
			<div class="site-meta">
				<span class="pill">${site.state}</span>
				<span class="pill">${site.municipality}</span>
				<span class="pill">${site.period}</span>
			</div>
			<p>${site.summary}</p>
			<a class="subtle-link" href="/pesquisa/sitio/${site.slug}/">Abrir ficha técnica</a>
		</article>
	`;
}

function renderMarkers(container, sites) {
	if (!container) {
		return;
	}

	container.innerHTML = sites
		.map((site) => `
			<div class="map-marker" style="left:${site.map_x}%; top:${site.map_y}%" title="${site.name}">
				<span>${site.name}</span>
			</div>
		`)
		.join('');
}

async function refreshResearchMap(root) {
	const resultsGrid = root.querySelector('[data-results-grid]');
	const markerLayer = root.querySelector('[data-marker-layer]');
	const countLabel = root.querySelector('[data-result-count]');
	const emptyState = root.querySelector('[data-empty-state]');
	const form = root.querySelector('[data-filter-form]');

	if (!form || !resultsGrid) {
		return;
	}

	const params = new URLSearchParams(new FormData(form));
	const apiUrl = form.dataset.apiUrl || form.action;
	const response = await fetch(`${apiUrl}?${params.toString()}`);
	const payload = await response.json();

	countLabel.textContent = payload.count;
	resultsGrid.innerHTML = payload.results.map(buildSiteCard).join('');
	renderMarkers(markerLayer, payload.results);
	emptyState.hidden = payload.results.length > 0;
}

function bindMapPage() {
	const root = document.querySelector('[data-map-page]');
	if (!root) {
		return;
	}

	const form = root.querySelector('[data-filter-form]');
	const controls = form ? Array.from(form.querySelectorAll('input, select')) : [];

	const update = () => {
		refreshResearchMap(root).catch(() => {
			const emptyState = root.querySelector('[data-empty-state]');
			if (emptyState) {
				emptyState.hidden = false;
				emptyState.textContent = 'Não foi possível carregar os resultados.';
			}
		});
	};

	controls.forEach((control) => {
		control.addEventListener('change', update);
	});

	update();
}

function bindAuthMenu() {
	const menu = document.querySelector('[data-auth-menu]');
	if (!menu) {
		return;
	}

	const toggle = menu.querySelector('[data-auth-toggle]');
	const popover = menu.querySelector('[data-auth-popover]');

	if (!toggle || !popover) {
		return;
	}

	const closePopover = () => {
		popover.hidden = true;
		toggle.setAttribute('aria-expanded', 'false');
	};

	const openPopover = () => {
		popover.hidden = false;
		toggle.setAttribute('aria-expanded', 'true');
	};

	toggle.addEventListener('click', () => {
		if (popover.hidden) {
			openPopover();
			return;
		}
		closePopover();
	});

	document.addEventListener('click', (event) => {
		if (!menu.contains(event.target) && !event.target.closest('.auth-modal')) {
			closePopover();
		}
	});

	document.addEventListener('keydown', (event) => {
		if (event.key === 'Escape') {
			closePopover();
		}
	});
}

function bindAuthModals() {
	const authPopover = document.querySelector('[data-auth-popover]');
	const authToggle = document.querySelector('[data-auth-toggle]');

	function closeAuthPopover() {
		if (authPopover) {
			authPopover.hidden = true;
		}
		if (authToggle) {
			authToggle.setAttribute('aria-expanded', 'false');
		}
	}

	document.querySelectorAll('[data-modal-open]').forEach((btn) => {
		btn.addEventListener('click', () => {
			const dialog = document.getElementById(btn.dataset.modalOpen);
			if (dialog) {
				closeAuthPopover();
				dialog.showModal();
			}
		});
	});

	document.querySelectorAll('[data-modal-close]').forEach((btn) => {
		btn.addEventListener('click', () => {
			const dialog = document.getElementById(btn.dataset.modalClose);
			if (dialog) {
				dialog.close();
			}
		});
	});

	document.querySelectorAll('.auth-modal').forEach((dialog) => {
		dialog.addEventListener('click', (event) => {
			if (event.target === dialog) {
				dialog.close();
			}
		});
	});
}

function bindFlashMessages() {
	function dismiss(el) {
		el.classList.add('flash-hiding');
		el.addEventListener('transitionend', () => el.remove(), { once: true });
	}

	document.querySelectorAll('.flash-message').forEach((msg) => {
		msg.querySelector('.flash-close')?.addEventListener('click', () => dismiss(msg));
		setTimeout(() => { if (msg.isConnected) dismiss(msg); }, 4000);
	});
}

function bindExcluirContaModal() {
	const dialog = document.getElementById('modal-excluir-conta');
	if (!dialog) { return; }

	const input = document.getElementById('excluir-confirm');
	const btn = document.getElementById('btn-excluir-conta');

	input.addEventListener('input', function () {
		btn.disabled = this.value !== 'EXCLUIR';
	});

	const openBtn = document.querySelector('[data-modal-open="modal-excluir-conta"]');
	if (openBtn) {
		openBtn.addEventListener('click', function () {
			input.value = '';
			btn.disabled = true;
		});
	}
}

document.addEventListener('DOMContentLoaded', () => {
	bindFlashMessages();
	bindAuthMenu();
	bindAuthModals();
	bindMapPage();
	bindExcluirContaModal();
});
