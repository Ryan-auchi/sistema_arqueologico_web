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
	bindExcluirContaModal();
});
