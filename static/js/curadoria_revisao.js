(function () {
    'use strict';

    const selectedFields = new Set();

    // requiresIphanForm is injected via data-requires-iphan attribute on the form
    const form = document.getElementById('merge-form');
    const requiresIphanForm = form && form.dataset.requiresIphan === 'true';

    const selectedFieldsInput = document.getElementById('selected-fields-input');
    const importMediaInput = document.getElementById('import-media-input');
    const publishedInput = document.getElementById('published-input');
    const publishedCheckbox = document.getElementById('published-checkbox');
    const publishedStatusChip = document.getElementById('published-status-chip');
    const approveButton = document.getElementById('approve-merge-button');
    const iphanOverlay = document.getElementById('iphan-modal-overlay');
    const iphanConfirmButton = document.getElementById('iphan-confirm-button');
    const iphanCancelButton = document.getElementById('iphan-cancel-button');

    function openIphanModal() {
        if (!iphanOverlay) {
            return;
        }
        iphanOverlay.classList.add('is-open');
        iphanOverlay.setAttribute('aria-hidden', 'false');
    }

    function closeIphanModal() {
        if (!iphanOverlay) {
            return;
        }
        iphanOverlay.classList.remove('is-open');
        iphanOverlay.setAttribute('aria-hidden', 'true');
    }

    function syncFields() {
        if (selectedFieldsInput) {
            selectedFieldsInput.value = JSON.stringify(Array.from(selectedFields));
        }
    }

    document.querySelectorAll('[data-accept-field]').forEach((button) => {
        const fieldName = button.getAttribute('data-accept-field');
        const defaultLabel = button.getAttribute('data-default-label') || 'Aceitar este campo';
        const card = button.closest('.field-box');

        button.addEventListener('click', function () {
            if (selectedFields.has(fieldName)) {
                selectedFields.delete(fieldName);
                button.classList.remove('is-undo');
                button.textContent = defaultLabel;
                if (card) {
                    card.classList.remove('is-selected');
                }
            } else {
                selectedFields.add(fieldName);
                button.classList.add('is-undo');
                button.textContent = 'Desfazer';
                if (card) {
                    card.classList.add('is-selected');
                }
            }

            syncFields();
        });
    });

    const mediaButton = document.getElementById('import-media-button');
    if (mediaButton && importMediaInput) {
        const defaultLabel = mediaButton.getAttribute('data-default-label') || 'Importar mídia';
        mediaButton.addEventListener('click', function () {
            const isSelected = importMediaInput.value === '1';
            importMediaInput.value = isSelected ? '0' : '1';
            mediaButton.classList.toggle('is-undo', !isSelected);
            mediaButton.textContent = isSelected ? defaultLabel : 'Desfazer';
        });
    }

    if (publishedCheckbox && publishedInput) {
        publishedCheckbox.addEventListener('change', function () {
            publishedInput.value = publishedCheckbox.checked ? '1' : '0';

            if (publishedStatusChip) {
                publishedStatusChip.classList.toggle('is-published', publishedCheckbox.checked);
                publishedStatusChip.classList.toggle('is-unpublished', !publishedCheckbox.checked);
                publishedStatusChip.textContent = publishedCheckbox.checked ? 'Publicado' : 'Não publicado';
            }
        });
    }

    if (requiresIphanForm && approveButton && form) {
        approveButton.addEventListener('click', function (event) {
            if (form.dataset.iphanConfirmed === '1') {
                return;
            }
            event.preventDefault();
            openIphanModal();
        });
    }

    if (iphanCancelButton) {
        iphanCancelButton.addEventListener('click', function () {
            closeIphanModal();
        });
    }

    if (iphanConfirmButton && form) {
        iphanConfirmButton.addEventListener('click', function () {
            form.dataset.iphanConfirmed = '1';
            closeIphanModal();
            if (approveButton && typeof form.requestSubmit === 'function') {
                form.requestSubmit(approveButton);
            } else {
                form.submit();
            }
        });
    }

    syncFields();
})();
