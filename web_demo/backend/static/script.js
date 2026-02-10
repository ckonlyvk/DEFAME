const chatContainer = document.getElementById('chatContainer');
const claimInput = document.getElementById('claimInput');
const sendButton = document.getElementById('sendButton');
const emptyState = document.getElementById('emptyState');

let currentToolCalls = [];
let processingElement = null;
let currentAssistantContent = null; // Track the current assistant message content
let messageCounter = 0; // Counter for unique message IDs
let abortController = null; // Track abort controller for canceling requests

function clearChat() {
    // Cancel any ongoing request
    if (abortController) {
        abortController.abort();
        abortController = null;
    }

    // Remove all messages except the empty state
    const messages = chatContainer.querySelectorAll('.message, .processing');
    messages.forEach(msg => msg.remove());

    // Show empty state again with example questions
    if (emptyState) {
        emptyState.style.display = 'flex';
    }

    // Reset state variables
    currentToolCalls = [];
    processingElement = null;
    currentAssistantContent = null;
    messageCounter = 0;

    // Clear and enable input
    claimInput.value = '';
    claimInput.disabled = false;
    sendButton.disabled = false;
    claimInput.focus();
}

function fillExample(text) {
    claimInput.value = text;
    claimInput.focus();
}

function submitClaim() {
    const claim = claimInput.value.trim();
    if (!claim) {
        claimInput.focus();
        return;
    }

    // Get selected mode
    const mode = document.querySelector('input[name="inputMode"]:checked').value;

    // Hide empty state
    if (emptyState) {
        emptyState.style.display = 'none';
    }

    // Disable input
    claimInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addUserMessage(claim);

    // Clear input
    claimInput.value = '';

    // Add assistant response container
    addAssistantMessage();

    // Start fact checking with mode
    checkClaim(claim, mode);
}

function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
                <div class="message-icon">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                    </svg>
                </div>
                <div class="message-content">
                    <div class="message-text">${escapeHtml(text)}</div>
                </div>
            `;
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

function addAssistantMessage() {
    // Reset state for new message
    messageCounter++;
    processingElement = null;
    stepsContainer = null;
    messageCounter++;
    processingElement = null;
    stepsContainer = null;
    stepMap = new Map();
    groupMap = new Map();

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';
    messageDiv.id = `assistantMessage-${messageCounter}`;
    messageDiv.innerHTML = `
                <div class="message-icon">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                    </svg>
                </div>
                <div class="message-content" id="assistantContent-${messageCounter}">
                </div>
            `;
    chatContainer.appendChild(messageDiv);

    // Store reference to the current assistant content
    currentAssistantContent = messageDiv.querySelector('.message-content');

    scrollToBottom();
}

function parseAnsiCodes(text) {
    // First escape HTML
    let result = escapeHtml(text);

    // Remove all ANSI escape sequences (starting with ESC or \033 or \x1b)
    // This handles complex sequences like cursor movement, RGB colors, etc.
    result = result.replace(/\x1b\[[0-9;]*m/g, '');
    result = result.replace(/\033\[[0-9;]*m/g, '');

    // Map simple ANSI codes to CSS classes
    const ansiMap = {
        '[93m': '<span class="ansi-yellow">',
        '[92m': '<span class="ansi-green">',
        '[91m': '<span class="ansi-red">',
        '[94m': '<span class="ansi-blue">',
        '[95m': '<span class="ansi-magenta">',
        '[96m': '<span class="ansi-cyan">',
        '[39m': '</span>',
        '[0m': '</span>'
    };

    for (const [code, replacement] of Object.entries(ansiMap)) {
        result = result.split(code).join(replacement);
    }

    // Remove any remaining ANSI-like patterns including RGB colors
    // Pattern like [38;2;R;G;Bm or [48;2;R;G;Bm
    result = result.replace(/\[38;2;\d+;\d+;\d+m/g, '');
    result = result.replace(/\[48;2;\d+;\d+;\d+m/g, '');
    // Generic pattern for any remaining [number;...m sequences
    result = result.replace(/\[\d+(;\d+)*m/g, '');

    return result;
}

function categorizeMessage(message) {
    const lowerMsg = message.toLowerCase();

    // Error patterns
    if (lowerMsg.includes('error') || lowerMsg.includes('exception') ||
        lowerMsg.includes('failed') || lowerMsg.includes('traceback') ||
        lowerMsg.includes('[91m') || /ssl.*error/i.test(message)) {
        return 'error';
    }

    // Success patterns
    if (lowerMsg.includes('complete') || lowerMsg.includes('success') ||
        lowerMsg.includes('verified') || lowerMsg.includes('[92m') ||
        /is (supported|refuted)/i.test(message)) {
        return 'success';
    }

    // Warning patterns
    if (lowerMsg.includes('warning') || lowerMsg.includes('retry') ||
        lowerMsg.includes('[93m') || lowerMsg.includes('timeout')) {
        return 'warning';
    }

    return 'info';
}

function generateSummary(message, type) {
    // Try to extract meaningful summary
    const lines = message.split('\n').filter(l => l.trim());

    if (type === 'error') {
        // Extract error type
        const errorMatch = message.match(/(Error|Exception):\s*(.+)/i);
        if (errorMatch) {
            return 'Lỗi: ' + errorMatch[2].substring(0, 80);
        }
        if (message.includes('SSL')) {
            return 'Lỗi kết nối SSL';
        }
        return 'Đã xảy ra lỗi trong quá trình xử lý';
    }

    if (type === 'success') {
        if (message.includes('refuted')) {
            return 'Đã bác bỏ tuyên bố';
        }
        if (message.includes('supported')) {
            return 'Đã xác nhận tuyên bố';
        }
        return 'Thực hiện thành công';
    }

    if (type === 'warning') {
        return 'Cảnh báo: ' + (lines[0] || 'Có vấn đề cần lưu ý').substring(0, 80);
    }

    // For info, try to extract action
    const claimMatch = message.match(/Claim:\s*"([^"]+)"/i);
    if (claimMatch) {
        return 'Đang kiểm chứng: ' + claimMatch[1].substring(0, 60) + '...';
    }

    if (message.includes('Verifying claim')) {
        return 'Đang kiểm chứng tuyên bố';
    }

    if (message.includes('Asking question')) {
        return 'Đặt câu hỏi kiểm chứng';
    }

    // Default to first meaningful line
    const firstLine = lines.find(l => l.length > 10) || lines[0] || message;
    return firstLine.substring(0, 80) + (firstLine.length > 80 ? '...' : '');
}

function getToolIcon(type) {
    const icons = {
        'info': 'ℹ️',
        'success': '✓',
        'error': '✕',
        'warning': '⚠'
    };
    return icons[type] || 'ℹ️';
}

function getToolTitle(type) {
    const titles = {
        'info': 'Thông tin',
        'success': 'Thành công',
        'error': 'Lỗi',
        'warning': 'Cảnh báo'
    };
    return titles[type] || 'Công cụ';
}

function addToolCall(message) {
    if (!currentAssistantContent) return;

    const type = categorizeMessage(message);
    const summary = generateSummary(message, type);
    const icon = getToolIcon(type);
    const title = getToolTitle(type);
    const formattedContent = parseAnsiCodes(message);

    const toolDiv = document.createElement('div');
    toolDiv.className = `tool-call tool-${type} collapsed`;
    const toolId = 'tool-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    toolDiv.id = toolId;
    toolDiv.innerHTML = `
                <div class="tool-header" onclick="toggleTool('${toolId}')">
                    <div class="tool-icon">${icon}</div>
                    <div class="tool-label">
                        <div class="tool-title">${title}</div>
                        <div class="tool-summary">${summary}</div>
                    </div>
                    <svg class="tool-arrow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"></path>
                    </svg>
                </div>
                <div class="tool-content"><pre>${formattedContent}</pre></div>
            `;
    currentAssistantContent.appendChild(toolDiv);
    scrollToBottom();
}

function addProcessing() {
    if (!currentAssistantContent) return;

    processingElement = document.createElement('div');
    processingElement.className = 'processing';
    processingElement.id = 'processingIndicator';
    processingElement.innerHTML = `
                <div class="spinner"></div>
                <span>Đang xử lý...</span>
            `;
    currentAssistantContent.appendChild(processingElement);
    scrollToBottom();
}

function removeProcessing() {
    if (processingElement) {
        processingElement.remove();
        processingElement = null;
    }
}


// Step-based progress UI functions
let stepsContainer = null;
let stepMap = new Map(); // Maps event id to step element
let groupMap = new Map(); // Maps group id to group element

function initStepsContainer() {
    if (!currentAssistantContent || stepsContainer) return;

    stepsContainer = document.createElement('div');
    stepsContainer.className = 'steps-container';
    stepsContainer.id = 'stepsContainer';
    currentAssistantContent.appendChild(stepsContainer);
}

function createClaimGroup(data) {
    const groupId = data.id;
    const groupDiv = document.createElement('div');
    groupDiv.className = 'claim-group status-inprogress expanded'; // Default expanded
    groupDiv.id = `group-${groupId}`;

    // Extract simple title if it's too long
    // const displayTitle = data.title.length > 60 ? data.title.substring(0, 60) + '...' : data.title;

    groupDiv.innerHTML = `
                <div class="claim-group-header" onclick="toggleGroup('${groupId}')">
                    <div class="claim-group-icon">
                        <div class="spinner-icon" style="width:16px;height:16px;border-width:2px;border-color:rgba(0,0,0,0.1);border-top-color:currentColor"></div>
                    </div>
                    <div class="claim-group-title">${escapeHtml(data.title)}</div>
                    <svg class="claim-group-arrow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"></path>
                    </svg>
                </div>
                <div class="claim-group-content" id="group-content-${groupId}">
                </div>
             `;

    stepsContainer.appendChild(groupDiv);
    groupMap.set(groupId, groupDiv);
    return groupDiv;
}

function toggleGroup(groupId) {
    const groupDiv = groupMap.get(groupId);
    if (groupDiv) {
        groupDiv.classList.toggle('expanded');
    }
}

function addStep(stepData) {
    initStepsContainer();

    // Handle EXTRACT_CLAIMS specifically
    if (stepData.stage === 'EXTRACT_CLAIMS') {
        // We can render this as a special banner or just a regular step
        // Let's render as a distinct status banner at the top
        const extractDiv = document.createElement('div');
        extractDiv.className = 'extraction-status';
        extractDiv.id = `step-${stepData.id}`;
        extractDiv.innerHTML = `
                    <div class="extraction-icon">
                        <div class="spinner" style="width:20px;height:20px;border-color:rgba(245, 124, 0, 0.2);border-top-color:var(--warning-text)"></div>
                    </div>
                    <div class="extraction-info">
                        <div class="extraction-title">${escapeHtml(stepData.title)}</div>
                        <div class="extraction-detail">${escapeHtml(stepData.detail)}</div>
                    </div>
                 `;
        // Insert at top or append? Append is fine as it's the first thing usually
        stepsContainer.appendChild(extractDiv);
        stepMap.set(stepData.id, extractDiv);
        return;
    }

    // Check if this is a group container (no parent, but potentially big ID from backend)
    // In our backend implementation, claim groups are emitted with manually constructed stages (tuple)
    // We can identify them if they don't have a parent BUT are intended to contain others.
    // Or simpler: if the backend sends `detail` that is just the claim text, and it comes from that loop.
    // The backend sends `stage_id >= 100` for groups in our ad-hoc implementation.
    if (stepData.stage_id >= 100) {
        createClaimGroup(stepData);
        return;
    }

    const eventId = stepData.id || stepData.step_id || Date.now().toString();
    const parentId = stepData.parent_id;

    // If parent_id exists, try to find the group content
    let targetContainer = stepsContainer;
    if (parentId) {
        const groupDiv = groupMap.get(parentId);
        if (groupDiv) {
            targetContainer = groupDiv.querySelector('.claim-group-content');
        } else {
            // Parent not found yet? It might be a race condition or implicit group.
            // Fallback to main container or create a dummy group?
            // Fallback for now.
            console.warn(`Parent group ${parentId} not found for step ${eventId}`);
        }
    }

    const status = stepData.status === 'inprogress' ? 'running' : stepData.status;

    const stepDiv = document.createElement('div');
    stepDiv.className = `step-item ${status}`;
    stepDiv.id = `step-${eventId}`;

    const iconContent = status === 'running' ?
        '<div class="spinner-icon"></div>' :
        '✓';

    stepDiv.innerHTML = `
                <div class="step-icon">${iconContent}</div>
                <div class="step-content">
                    <div class="step-title">${escapeHtml(stepData.title)}</div>
                    ${stepData.detail ? `<div class="step-detail">${escapeHtml(stepData.detail)}</div>` : ''}
                </div>
            `;

    targetContainer.appendChild(stepDiv);
    stepMap.set(eventId, stepDiv);
    scrollToBottom();
}

function updateStep(stepData) {
    const eventId = stepData.id || stepData.step_id;

    // Check if it's a group update
    if (groupMap.has(eventId)) {
        const groupDiv = groupMap.get(eventId);

        // Update status class
        if (stepData.status) {
            groupDiv.classList.remove('status-inprogress', 'status-complete', 'status-error');

            // We only set basic status here; detailed verdict logic is below
            // groupDiv.classList.add(`status-${stepData.status}`); 

            const iconDiv = groupDiv.querySelector('.claim-group-icon');
            if (stepData.status === 'inprogress') {
                groupDiv.classList.add('status-inprogress');
                iconDiv.innerHTML = '<div class="spinner-icon" style="width:16px;height:16px;border-width:2px;border-color:rgba(245, 124, 0, 0.2);border-top-color:var(--warning-text)"></div>';
            }
        }

        // Update title/detail if provided (maybe verdict)
        if (stepData.detail) {
            // Check for verdict in the detail text
            // Verdicts: "True", "False", "Unknown" (mapped from Vietnamese labels)
            let verdictClass = '';
            let verdictIcon = '';
            let verdictLabel = '';

            if (stepData.detail.includes('ĐƯỢC XÁC NHẬN') || stepData.detail.includes('True') || stepData.detail.includes('Tuyên bố True')) {
                verdictClass = 'verdict-supported';
                verdictIcon = '✓';
                verdictLabel = 'True';
            } else if (stepData.detail.includes('BỊ BÁC BỎ') || stepData.detail.includes('False') || stepData.detail.includes('Tuyên bố False')) {
                verdictClass = 'verdict-refuted';
                verdictIcon = '✕';
                verdictLabel = 'False';
            } else if (stepData.detail.includes('CHƯA ĐỦ BẰNG CHỨNG') || stepData.detail.includes('Unknown') || stepData.detail.includes('Tuyên bố Unknown')) {
                verdictClass = 'verdict-nei';
                verdictIcon = '?';
                verdictLabel = 'Unknown';
            }

            if (verdictClass) {
                groupDiv.classList.remove('status-inprogress');
                groupDiv.classList.add(verdictClass);

                const iconDiv = groupDiv.querySelector('.claim-group-icon');
                iconDiv.innerHTML = verdictIcon;

                // Update title with verdict label
                const titleDiv = groupDiv.querySelector('.claim-group-title');
                const originalTitle = titleDiv.textContent.split(' - ')[0].trim();
                titleDiv.innerHTML = `${originalTitle} - <b>${verdictLabel}</b>`;
            }
        }
        return;
    }

    const stepDiv = stepMap.get(eventId);
    if (!stepDiv) {
        console.warn('Step not found for update:', eventId);
        return;
    }

    // Handle Extraction Update specially
    if (stepDiv.classList.contains('extraction-status')) {
        if (stepData.status === 'complete') {
            const icon = stepDiv.querySelector('.extraction-icon');
            icon.innerHTML = '<span style="color:var(--success-text)">✓</span>';
            if (stepData.detail) stepDiv.querySelector('.extraction-detail').textContent = stepData.detail;
        } else if (stepData.status === 'error') {
            const icon = stepDiv.querySelector('.extraction-icon');
            icon.innerHTML = '<span style="color:var(--danger-text)">✕</span>';
            if (stepData.detail) stepDiv.querySelector('.extraction-detail').textContent = stepData.detail;
        } else {
            if (stepData.detail) stepDiv.querySelector('.extraction-detail').textContent = stepData.detail;
        }
        return;
    }

    // Standard Step Update
    if (stepData.status) {
        const status = stepData.status === 'inprogress' ? 'running' : stepData.status;

        // Remove existing status classes
        stepDiv.classList.remove('running', 'complete', 'error');
        stepDiv.classList.add(status);

        const iconDiv = stepDiv.querySelector('.step-icon');
        if (status === 'complete') {
            iconDiv.innerHTML = '✓';
            iconDiv.className = 'step-icon'; // Reset any spinner classes
        } else if (status === 'error') {
            iconDiv.innerHTML = '✕';
            iconDiv.className = 'step-icon';

            // Propagate error to parent group if exists
            const parentGroup = stepDiv.closest('.claim-group');
            if (parentGroup) {
                // Only mark as error if it hasn't already been marked with a final verdict
                if (!parentGroup.classList.contains('verdict-supported') &&
                    !parentGroup.classList.contains('verdict-refuted') &&
                    !parentGroup.classList.contains('verdict-nei')) {

                    // Maybe just show a generic error state for the group if not final
                    parentGroup.classList.add('status-error');
                    parentGroup.querySelector('.claim-group-icon').innerHTML = '✕';
                }
            }
        } else if (status === 'running') {
            iconDiv.innerHTML = '';
            iconDiv.classList.add('spinner-icon');
        }
    }

    if (stepData.detail) {
        const stepContent = stepDiv.querySelector('.step-content');
        let detailDiv = stepContent.querySelector('.step-detail');

        if (!detailDiv) {
            detailDiv = document.createElement('div');
            detailDiv.className = 'step-detail';
            stepContent.appendChild(detailDiv);
        }
        detailDiv.textContent = stepData.detail;
    }

    if (stepData.result) {
        const stepContent = stepDiv.querySelector('.step-content');
        let resultDiv = stepContent.querySelector('.step-result');
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.className = 'step-result';
            stepContent.appendChild(resultDiv);
        }
        resultDiv.textContent = stepData.result;
    }

    scrollToBottom();
}



function showResult(result) {
    removeProcessing();

    if (!currentAssistantContent) return;

    const resultDiv = document.createElement('div');
    resultDiv.className = 'result-section';

    // Verdict - Map internal labels to display labels
    const verdict = result.verdict || 'NEI';
    const verdictDisplayMap = {
        'SUPPORTED': 'True',
        'REFUTED': 'False',
        'NEI': 'Unknown',
        'supported': 'True',
        'refuted': 'False',
        'not enough information': 'Unknown'
    };
    const verdictDisplay = verdictDisplayMap[verdict] || verdict;
    // Use uppercase version for CSS class matching
    const verdictClass = verdict.toUpperCase() === 'SUPPORTED' || verdict.toLowerCase().includes('supported') ? 'SUPPORTED'
        : verdict.toUpperCase() === 'REFUTED' || verdict.toLowerCase().includes('refuted') ? 'REFUTED'
            : 'NEI';
    let verdictHTML = `<div class="verdict-badge verdict-${verdictClass}">${verdictDisplay}</div>`;

    // Justification
    let justification = result.justification || 'No justification provided.';
    justification = justification
        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
        .replace(/【(.*?)】/g, (match, url) => {
            // Handle multiple URLs if split by semicolon or space
            if (url.includes('http')) {
                // It's a URL
                return ` <a href="${url.trim()}" class="citation-badge" target="_blank">Nguồn</a> `;
            } else {
                // It might be just text or empty
                return ` <span class="citation-text">[${url}]</span> `;
            }
        })
        .replace(/\n/g, '<br>');

    // Wrap in paragraphs if it contains double newlines (converted to <br><br>)
    // Actually simpler: split by <br><br> and wrap each in <p>
    const paragraphs = justification.split('<br><br>').map(p => `<p>${p}</p>`).join('');
    // If no double breaks were found, it might be just <br>, leave as is but wrapped in one p
    justification = paragraphs || `<p>${justification}</p>`;

    let justificationHTML = `
                <div class="section-title">Giải trình</div>
                <div class="justification-text">${justification}</div>
            `;

    // Evidence
    let evidenceHTML = '';
    const evidences = result.evidences || [];
    if (evidences.length > 0) {
        evidenceHTML = '<div class="section-title">Bằng chứng & Tham khảo</div><ul class="evidence-grid">';
        evidences.forEach(evObj => {
            const content = typeof evObj === 'string' ? evObj : evObj.text;
            const url = typeof evObj === 'object' ? evObj.url : null;
            const title = typeof evObj === 'object' ? evObj.title : null;

            const cleanContent = content.replace(/\*\*/g, '').replace(/### Evidence from `[^`]+`\n/g, '');

            let cardHTML = '<li class="evidence-card">';
            if (title) {
                cardHTML += `<div class="evidence-title">${escapeHtml(title)}</div>`;
            }
            cardHTML += `<div class="evidence-text">${escapeHtml(cleanContent)}</div>`;
            if (url) {
                cardHTML += `
                            <a href="${escapeHtml(url)}" target="_blank" class="evidence-link">
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                                </svg>
                                <span>${escapeHtml(url)}</span>
                            </a>
                        `;
            }
            cardHTML += '</li>';
            evidenceHTML += cardHTML;
        });
        evidenceHTML += '</ul>';
    }

    resultDiv.innerHTML = verdictHTML + justificationHTML + evidenceHTML;
    currentAssistantContent.appendChild(resultDiv);

    // Re-enable input
    claimInput.disabled = false;
    sendButton.disabled = false;
    claimInput.focus();

    scrollToBottom();
}

async function checkClaim(claim, mode) {
    addProcessing();

    try {
        // Create new abort controller for this request
        abortController = new AbortController();

        const response = await fetch('/api/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claim, mode }),
            signal: abortController.signal
        });

        if (!response.ok) throw new Error('Network response was not ok');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    const [meta, ...dataParts] = line.split('\n');
                    const eventType = meta.replace('event: ', '').trim();
                    const dataStr = dataParts.map(p => p.replace('data: ', '')).join('\n').trim();

                    if (!dataStr) continue;
                    const data = JSON.parse(dataStr);

                    // Debug logging
                    console.log('📨 Event received:', eventType, data);

                    if (eventType === 'log') {
                        addToolCall(data.message);
                    } else if (eventType === 'step') {
                        console.log('✨ Adding step:', data);
                        addStep(data);
                    } else if (eventType === 'step_update') {
                        console.log('🔄 Updating step:', data);
                        updateStep(data);
                    } else if (eventType === 'result') {
                        showResult(data);
                    } else if (eventType === 'error') {
                        removeProcessing();
                        addToolCall('ERROR: ' + data.error);
                        claimInput.disabled = false;
                        sendButton.disabled = false;
                    }
                }
            }
        }
    } catch (err) {
        console.error(err);
        removeProcessing();
        addToolCall('Error connecting to server: ' + err.message);
        claimInput.disabled = false;
        sendButton.disabled = false;
    }
}

function toggleTool(toolId) {
    const toolElement = document.getElementById(toolId);
    if (toolElement) {
        toolElement.classList.toggle('collapsed');
    }
}

function scrollToBottom() {
    setTimeout(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }, 100);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// Allow Enter to submit
claimInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !claimInput.disabled) {
        submitClaim();
    }
});

// Update placeholder based on selected mode
document.querySelectorAll('input[name="inputMode"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const mode = e.target.value;
        if (mode === 'claim') {
            claimInput.placeholder = 'Nhập câu tuyên bố cần kiểm chứng...';
        } else {
            claimInput.placeholder = 'Nhập đoạn tin tức cần phân tích...';
        }
    });
});

// Focus input on load
claimInput.focus();
