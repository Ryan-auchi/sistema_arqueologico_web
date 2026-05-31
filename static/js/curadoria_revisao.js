(function () {
    'use strict';

    const selectedFields = new Set();

    const selectedFieldsInput = document.getElementById('selected-fields-input');
    const importMediaInput = document.getElementById('import-media-input');
    const publishedInput = document.getElementById('published-input');
    const publishedCheckbox = document.getElementById('published-checkbox');
    const publishedStatusChip = document.getElementById('published-status-chip');

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

    syncFields();
})();
