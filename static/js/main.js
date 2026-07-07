document.addEventListener('DOMContentLoaded', () => {

    let selectedTemp = 0.8;
    let selectedCount = 5;
    let activeRequest = null;

    const modeBtns = document.querySelectorAll('.mode-btn');
    const countBtns = document.querySelectorAll('.count-btn');
    const prefixInput = document.getElementById('prefix');

    const generateBtn = document.getElementById('generate-btn');
    const compareBtn = document.getElementById('compare-btn');

    const resultsSection = document.getElementById('results-section');
    const resultsGrid = document.getElementById('results-grid');
    const resultsHeader = document.getElementById('results-header');

    const REQUEST_TIMEOUT_MS = 30000;

    modeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedTemp = parseFloat(btn.dataset.temp);
        });
    });

    countBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            countBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedCount = parseInt(btn.dataset.count);
        });
    });

    function setButtonsLoading(isLoading) {
        [generateBtn, compareBtn].forEach(btn => {
            const textSpan = btn.querySelector('.btn-text');
            const spinner = btn.querySelector('.spinner');
            btn.disabled = isLoading;
            if (isLoading) {
                textSpan.classList.add('loading-hide');
                spinner.classList.remove('hidden');
            } else {
                textSpan.classList.remove('loading-hide');
                spinner.classList.add('hidden');
            }
        });
    }

    async function fetchWithTimeout(url, options) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        activeRequest = controller;

        try {
            const res = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            if (!res.ok) {
                throw new Error(`Server returned ${res.status}`);
            }
            return await res.json();
        } catch (err) {
            clearTimeout(timeoutId);
            if (err.name === 'AbortError') {
                throw new Error('Request timed out. The server may be busy — try again.');
            }
            throw err;
        } finally {
            activeRequest = null;
        }
    }

    function createTitleCard(titleObj, temperature, modeName = null) {
        const div = document.createElement('div');
        div.className = 'card';

        let headerHtml = '';
        if (modeName) {
            headerHtml = `<div class="card-mode-badge">${modeName}</div>`;
        }

        const confidence = titleObj.confidence;

        div.innerHTML = `
            ${headerHtml}
            <div class="card-title">${titleObj.title}</div>
            <div class="confidence-control">
                <div class="confidence-header">
                    <span>Confidence</span>
                    <span>${confidence}%</span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: 0%"></div>
                </div>
            </div>
            <div style="font-size: 0.75rem; color: rgba(255,255,255,0.35); text-align: right; margin-top: -5px;">
                Temp: ${typeof titleObj.temperature !== 'undefined' ? titleObj.temperature : temperature}
            </div>
        `;

        requestAnimationFrame(() => {
            const fill = div.querySelector('.progress-bar-fill');
            if (fill) fill.style.width = `${confidence}%`;
        });

        return div;
    }

    function showResults(header, items, isCompare = false) {
        resultsGrid.innerHTML = '';
        resultsGrid.classList.toggle('compare-layout', isCompare);
        resultsHeader.innerText = header;

        if (!items || items.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = 'No titles passed the filters. Try a different prefix or creativity mode.';
            resultsGrid.appendChild(empty);
        } else {
            items.forEach(t => {
                const card = isCompare
                    ? createTitleCard(t, t.temperature, t.mode)
                    : createTitleCard(t, t.temperature || selectedTemp);
                resultsGrid.appendChild(card);
            });
        }

        resultsSection.classList.remove('hidden');
    }

    generateBtn.addEventListener('click', async () => {
        if (activeRequest) return;
        setButtonsLoading(true);

        try {
            const data = await fetchWithTimeout('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prefix: prefixInput.value,
                    temperature: selectedTemp,
                    num_titles: selectedCount
                })
            });

            if (!data.success) throw new Error('Generation failed');
            showResults('Generated Titles', data.titles);
        } catch (error) {
            console.error('Error generating titles:', error);
            alert(error.message || 'Something went wrong. Please try again.');
        } finally {
            setButtonsLoading(false);
        }
    });

    compareBtn.addEventListener('click', async () => {
        if (activeRequest) return;
        setButtonsLoading(true);

        try {
            const data = await fetchWithTimeout('/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prefix: prefixInput.value })
            });

            if (!data.success) throw new Error('Compare failed');
            showResults('Comparing Temperatures', data.compare_results, true);
        } catch (error) {
            console.error('Error comparing titles:', error);
            alert(error.message || 'Something went wrong. Please try again.');
        } finally {
            setButtonsLoading(false);
        }
    });
});
