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

    // ── Sítios próximos ──────────────────────────────────────────────────────
    const bemMaterialIdInput = document.getElementById('bem-material-id-input');
    const sitiosData = (typeof SITIOS_PROXIMOS_DATA !== 'undefined') ? SITIOS_PROXIMOS_DATA : [];

    function _buildSitioIndex() {
        const idx = {};
        sitiosData.forEach((s) => { if (s.id) idx[String(s.id)] = s; });
        return idx;
    }
    const sitioIndex = _buildSitioIndex();

    function _updateComparisonRows(sitio) {
        // sitio = null → restaura estado original (opção "coleta")
        const subtitleEl = document.getElementById('official-panel-subtitle');
        const titleEl    = document.getElementById('official-panel-title');

        if (!sitio) {
            // Restaura cabeçalho
            if (subtitleEl) subtitleEl.textContent = 'Registro oficial atual';
            if (titleEl)    titleEl.textContent    = 'Registro mestre';

            document.querySelectorAll('.comparison-row[data-field-name]').forEach((row) => {
                const valueEl = row.querySelector('.js-official-value');
                const tagEl   = row.querySelector('.js-official-tag');
                const noteEl  = row.querySelector('.js-official-note');
                const inBox   = row.querySelector('.js-incoming-box');
                const inTag   = row.querySelector('.js-incoming-tag');

                if (valueEl) {
                    const orig = valueEl.dataset.originalValue;
                    valueEl.textContent = orig || 'Não informado';
                }
                if (tagEl) {
                    tagEl.textContent = tagEl.dataset.originalTag || '';
                    tagEl.classList.remove('conflict-text');
                    if (tagEl.dataset.originalTagClass) tagEl.classList.add(tagEl.dataset.originalTagClass);
                }
                if (noteEl) noteEl.style.display = '';

                // Restaura classes do lado da coleta a partir das classes CSS originais
                // guardadas nos data-attributes (lidas uma vez na inicialização)
                if (inBox && inBox.dataset.origClass !== undefined) {
                    inBox.className = inBox.dataset.origClass;
                }
                if (inTag && inTag.dataset.origText !== undefined) {
                    inTag.textContent = inTag.dataset.origText;
                    inTag.className   = inTag.dataset.origClass || 'field-tag';
                }
            });
            return;
        }

        // Atualiza cabeçalho com o sítio selecionado
        if (subtitleEl) subtitleEl.textContent = 'Sítio cadastrado selecionado';
        if (titleEl)    titleEl.textContent    = sitio.nome_bem || 'Sítio sem nome';

        document.querySelectorAll('.comparison-row[data-field-name]').forEach((row) => {
            const field      = row.dataset.fieldName;
            const incoming   = row.dataset.incomingValue || '';
            const siteRaw    = sitio[field];
            const siteVal    = (siteRaw !== null && siteRaw !== undefined && String(siteRaw).trim() !== '')
                               ? String(siteRaw) : '';

            const valueEl = row.querySelector('.js-official-value');
            const tagEl   = row.querySelector('.js-official-tag');
            const noteEl  = row.querySelector('.js-official-note');
            const inBox   = row.querySelector('.js-incoming-box');
            const inTag   = row.querySelector('.js-incoming-tag');

            if (noteEl) noteEl.style.display = 'none';

            if (!siteVal) {
                if (valueEl) valueEl.textContent = 'Não informado';
                if (tagEl) { tagEl.textContent = 'SEM REGISTRO'; tagEl.className = 'field-tag conflict-text js-official-tag'; }
                if (inBox) { inBox.classList.remove('conflict'); inBox.classList.add('new-data'); }
                if (inTag) { inTag.textContent = 'NOVO CAMPO'; inTag.className = 'field-tag js-incoming-tag'; }
            } else if (siteVal === incoming) {
                if (valueEl) valueEl.textContent = siteVal;
                if (tagEl) { tagEl.textContent = 'REGISTRO ATUAL'; tagEl.className = 'field-tag js-official-tag'; }
                if (inBox) { inBox.classList.remove('conflict', 'new-data'); }
                if (inTag) { inTag.textContent = 'MESMO VALOR'; inTag.className = 'field-tag js-incoming-tag'; }
            } else {
                if (valueEl) valueEl.textContent = siteVal;
                if (tagEl) { tagEl.textContent = 'VALOR OFICIAL'; tagEl.className = 'field-tag js-official-tag'; }
                if (inBox) { inBox.classList.remove('new-data'); inBox.classList.add('conflict'); }
                if (inTag) { inTag.textContent = 'CONFLITO'; inTag.className = 'field-tag conflict-text js-incoming-tag'; }
            }
        });
    }

    // Guarda classes/texto originais do lado coleta antes de qualquer modificação
    document.querySelectorAll('.comparison-row[data-field-name]').forEach((row) => {
        const inBox = row.querySelector('.js-incoming-box');
        const inTag = row.querySelector('.js-incoming-tag');
        if (inBox) inBox.dataset.origClass = inBox.className;
        if (inTag) { inTag.dataset.origText = inTag.textContent.trim(); inTag.dataset.origClass = inTag.className; }
    });

    window.selecionarSitioProximo = function (btn) {
        const id   = btn.dataset.sitioId;
        const nome = btn.dataset.sitioNome;

        // Estilo dos botões
        document.querySelectorAll('.sitio-proximo-item').forEach((el) => {
            el.style.background  = '';
            el.style.borderColor = '';
            el.style.borderWidth = '';
            el.style.outline     = '';
        });
        btn.style.background  = '#fffbeb';
        btn.style.borderColor = '#f59e0b';
        btn.style.borderWidth = '2px';

        if (bemMaterialIdInput) bemMaterialIdInput.value = id || '';

        const sitio = id ? sitioIndex[String(id)] : null;
        _updateComparisonRows(sitio);
    };

    // Pré-seleciona o item da coleta ao carregar
    const itemColeta = document.getElementById('sitio-item-coleta');
    if (itemColeta) {
        // Não chama selecionarSitioProximo pra não sobrescrever estado original;
        // só aplica o estilo visual de selecionado
        itemColeta.style.background  = '#fffbeb';
        itemColeta.style.borderColor = '#f59e0b';
        itemColeta.style.borderWidth = '2px';
        if (bemMaterialIdInput) bemMaterialIdInput.value = '';
    }

    // Mantém compatibilidade com código antigo
    window.desselecionarSitio = function () {
        if (itemColeta) selecionarSitioProximo(itemColeta);
    };
})();
