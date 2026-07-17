document.addEventListener("DOMContentLoaded", () => {
    let sessionId = null;
    let pollInterval = null;
    const mdConverter = new showdown.Converter({ tables: true });

    // DOM elements
    const promptInput = document.getElementById("promptInput");
    const startBtn = document.getElementById("startBtn");
    const sessionInfo = document.getElementById("sessionInfo");
    const dispSessionId = document.getElementById("dispSessionId");
    const dispStatus = document.getElementById("dispStatus");
    const dispAgent = document.getElementById("dispAgent");
    const logsContainer = document.getElementById("logsContainer");
    const interruptPanel = document.getElementById("interruptPanel");
    const feedbackInput = document.getElementById("feedbackInput");
    const feedbackBtn = document.getElementById("feedbackBtn");
    const approveBtn = document.getElementById("approveBtn");
    const interruptMessage = document.getElementById("interruptMessage");

    const prdTab = document.getElementById("prdTab");
    const techTab = document.getElementById("techTab");
    const qaTab = document.getElementById("qaTab");

    // Tab switcher logic
    const tabButtons = document.querySelectorAll(".tab-btn");
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            tabButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const targetTab = btn.getAttribute("data-tab");
            document.querySelectorAll(".tab-content").forEach(content => {
                content.style.display = "none";
            });
            document.getElementById(targetTab).style.display = "block";
        });
    });

    // Start Session Click Handler
    startBtn.addEventListener("click", async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) {
            alert("Please type a product description first.");
            return;
        }

        try {
            startBtn.disabled = true;
            startBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Initializing...';
            
            const response = await fetch("/api/orchestrate/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Failed to start orchestrator session.");
            }

            const data = await response.json();
            sessionId = data.session_id;

            // Update UI
            dispSessionId.textContent = sessionId.substring(0, 8) + "...";
            sessionInfo.style.display = "flex";
            logsContainer.innerHTML = '<div class="empty-state">Spawning orchestrator flow...</div>';
            
            // Start Polling
            startPolling();
        } catch (error) {
            alert("Error: " + error.message);
            resetStartBtn();
        }
    });

    // Approve / Proceed Handler
    approveBtn.addEventListener("click", () => submitFeedback(true));

    // Request Revision Handler
    feedbackBtn.addEventListener("click", () => submitFeedback(false));

    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        
        // Immediate poll first
        pollStatus();
        
        // Set interval
        pollInterval = setInterval(pollStatus, 1500);
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    async function pollStatus() {
        if (!sessionId) return;

        try {
            const response = await fetch(`/api/orchestrate/status/${sessionId}?t=${Date.now()}`);
            if (!response.ok) {
                throw new Error("Unable to fetch session status.");
            }

            const data = await response.json();
            updateUI(data);

            // Stop polling if completed or rejected
            if (data.status === "completed" || data.status === "rejected") {
                stopPolling();
                resetStartBtn();
            }
        } catch (error) {
            console.error("Polling error:", error);
        }
    }

    function updateUI(data) {
        // Status & Agent Text
        dispStatus.className = `value badge ${data.status}`;
        dispStatus.textContent = data.status;
        dispAgent.textContent = data.current_agent;

        // If processing in background, display spinner and disable Start Orchestrator
        if (data.is_processing) {
            dispStatus.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${data.status}`;
            startBtn.disabled = true;
            startBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
        } else {
            resetStartBtn();
        }

        // Render Artifact Docs
        renderDocument(prdTab, data.prd, "PRD not yet generated.");
        renderDocument(techTab, data.tech_design, "Technical design specs not yet generated.");
        renderDocument(qaTab, data.test_plan, "QA test plan not yet generated.");

        // Logs
        renderLogs(data.history);

        // Manage Workflow Nodes Maps
        updateWorkflowNodes(data.status);

        // Handle Human Intercept interrupt inputs
        if (data.feedback_requested) {
            interruptPanel.style.display = "block";
            if (data.status === "pm_review") {
                interruptMessage.innerHTML = `<i class="fa-solid fa-file-invoice"></i> Awaiting Human PM review approval for the **Product Requirement Document (PRD)**.`;
            } else if (data.status === "tech_review") {
                interruptMessage.innerHTML = `<i class="fa-solid fa-laptop-code"></i> Awaiting Architect approval for the **Technical Design Specs**.`;
            }
        } else {
            interruptPanel.style.display = "none";
        }
    }

    function renderDocument(container, mdContent, emptyText) {
        if (mdContent) {
            container.innerHTML = `<div class="markdown-body">${mdConverter.makeHtml(mdContent)}</div>`;
        } else {
            container.innerHTML = `<div class="empty-doc">${emptyText}</div>`;
        }
    }

    function renderLogs(history) {
        if (!history || history.length === 0) {
            logsContainer.innerHTML = '<div class="empty-state">No agent entries recorded yet...</div>';
            return;
        }

        logsContainer.innerHTML = "";
        history.forEach(log => {
            const bubble = document.createElement("div");
            
            // Set class for coloring
            let senderClass = "system-log";
            const sender = log.sender.toLowerCase();
            if (sender.includes("product manager")) senderClass = "pm-log";
            else if (sender.includes("tech lead")) senderClass = "tech-log";
            else if (sender.includes("qa")) senderClass = "qa-log";
            else if (sender.includes("guardrail")) senderClass = "guardrail-log";
            else if (sender.includes("human")) senderClass = "user-log";

            bubble.className = `log-bubble ${senderClass}`;
            bubble.innerHTML = `
                <div class="meta">
                    <span class="sender">${log.sender}</span>
                    <span class="time">${log.timestamp}</span>
                </div>
                <div class="message">${log.message}</div>
            `;
            logsContainer.appendChild(bubble);
        });
        
        // Auto scroll to bottom
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    function updateWorkflowNodes(status) {
        const nodes = {
            input: document.getElementById("node-input"),
            pm: document.getElementById("node-pm"),
            tech: document.getElementById("node-tech"),
            qa: document.getElementById("node-qa"),
            complete: document.getElementById("node-complete")
        };

        // Reset all nodes
        Object.values(nodes).forEach(n => n.className = "node-item");

        if (status === "starting") {
            nodes.input.classList.add("active");
        } else if (status === "pm_review") {
            nodes.input.classList.add("done");
            nodes.pm.classList.add("active");
        } else if (status === "tech_review") {
            nodes.input.classList.add("done");
            nodes.pm.classList.add("done");
            nodes.tech.classList.add("active");
        } else if (status === "qa_drafting") {
            nodes.input.classList.add("done");
            nodes.pm.classList.add("done");
            nodes.tech.classList.add("done");
            nodes.qa.classList.add("active");
        } else if (status === "completed") {
            nodes.input.classList.add("done");
            nodes.pm.classList.add("done");
            nodes.tech.classList.add("done");
            nodes.qa.classList.add("done");
            nodes.complete.classList.add("done");
        } else if (status === "rejected") {
            nodes.input.classList.add("error");
            nodes.pm.classList.add("error");
            nodes.tech.classList.add("error");
            nodes.qa.classList.add("error");
        }
    }

    async function submitFeedback(approve) {
        const feedbackText = feedbackInput.value.trim();
        if (!approve && !feedbackText) {
            alert("Please type feedback details when requesting revisions.");
            return;
        }

        try {
            feedbackBtn.disabled = true;
            approveBtn.disabled = true;
            
            const response = await fetch(`/api/orchestrate/feedback/${sessionId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    feedback: approve ? null : feedbackText,
                    approve: approve
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Failed to submit feedback.");
            }

            feedbackInput.value = "";
            interruptPanel.style.display = "none";
            
            // Resume polling
            startPolling();
        } catch (error) {
            alert("Error submitting feedback: " + error.message);
        } finally {
            feedbackBtn.disabled = false;
            approveBtn.disabled = false;
        }
    }

    function resetStartBtn() {
        startBtn.disabled = false;
        startBtn.innerHTML = '<i class="fa-solid fa-circle-play"></i> Start Orchestrator';
    }
});
