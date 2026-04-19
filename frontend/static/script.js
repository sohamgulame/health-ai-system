// Shared utility for API
async function fetchLatestData() {
    try {
        const response = await fetch('/api/latest');
        const data = await response.json();
        
        if (document.getElementById('temp-val')) {
            document.getElementById('temp-val').innerText = data.temperature !== undefined ? data.temperature : '--';
        }
        if (document.getElementById('hr-val')) {
            document.getElementById('hr-val').innerText = data.heart_rate !== undefined ? data.heart_rate : '--';
        }
        if (document.getElementById('spo2-val')) {
            document.getElementById('spo2-val').innerText = data.spo2 !== undefined ? data.spo2 : '--';
        }
        
        // Update connection status
        let isConnected = false;
        if (data.temperature !== undefined && data.temperature !== '--') {
            isConnected = true; 
        }
        
        const sensorStatusEl = document.getElementById('sensor-status-val');
        const connectedDevicesEl = document.getElementById('connected-devices-val');
        
        if (sensorStatusEl && connectedDevicesEl) {
            if (isConnected) {
                sensorStatusEl.innerHTML = '<span class="dot"></span> Transmitting';
                sensorStatusEl.className = 'value success';
                connectedDevicesEl.innerText = '1 ESP32 Active';
            } else {
                sensorStatusEl.innerText = 'Offline / Waiting';
                sensorStatusEl.className = 'value warning';
                connectedDevicesEl.innerText = '0 ESP32 Active';
            }
        }

    } catch (error) {
        console.error("Error fetching latest data:", error);
        
        const sensorStatusEl = document.getElementById('sensor-status-val');
        const connectedDevicesEl = document.getElementById('connected-devices-val');
        
        if (sensorStatusEl && connectedDevicesEl) {
            sensorStatusEl.innerText = 'Database Error';
            sensorStatusEl.className = 'value warning';
            connectedDevicesEl.innerText = '0 ESP32 Active';
        }
    }
}

async function fetchAnalysisData() {
    try {
        const response = await fetch('/api/latest');
        const data = await response.json();
        
        if (document.getElementById('temp-val')) {
            document.getElementById('temp-val').innerText = data.temperature !== undefined ? data.temperature : '--';
            document.getElementById('hr-val').innerText = data.heart_rate !== undefined ? data.heart_rate : '--';
            document.getElementById('spo2-val').innerText = data.spo2 !== undefined ? data.spo2 : '--';
        }
        
        if (document.getElementById('prediction-val')) {
            document.getElementById('prediction-val').innerText = data.prediction || 'No prediction available';
            document.getElementById('diagnosis-val').innerText = data.diagnosis || 'Analysis pending';
            document.getElementById('advice-val').innerText = data.advice || 'No advice available';
            document.getElementById('explanation-val').innerText = data.explanation || 'No explanation available';
            
            // Update health badge color based on prediction
            updateHealthBadge(data.prediction);
        }
    } catch (error) {
        console.error("Error fetching analysis data:", error);
    }
}

function updateHealthBadge(prediction) {
    const badge = document.getElementById('health-badge');
    if (!badge) return;
    
    prediction = prediction.toLowerCase();
    if (prediction.includes('critical')) {
        badge.style.color = '#dc2626';
        badge.title = 'Critical - Seek immediate medical attention';
    } else if (prediction.includes('caution')) {
        badge.style.color = '#f59e0b';
        badge.title = 'Caution - Monitor closely';
    } else if (prediction.includes('monitor')) {
        badge.style.color = '#eab308';
        badge.title = 'Monitor - Keep watch';
    } else {
        badge.style.color = '#10b981';
        badge.title = 'Healthy - All good';
    }
}

// Global pagination state
let currentPage = 1;
let totalPages = 1;
let reportDataCache = [];

async function fetchReportData(page = 1) {
    try {
        const response = await fetch(`/api/report?page=${page}&limit=10`);
        const result = await response.json();
        const data = result.data;
        const pagination = result.pagination || {};
        
        currentPage = pagination.page || 1;
        totalPages = pagination.total_pages || 1;
        
        if (data && data.length > 0) {
            // Calculate summary stats from current page (or you could fetch from all data)
            const avgTemp = (data.reduce((sum, item) => sum + (parseFloat(item.temperature) || 0), 0) / data.length).toFixed(1);
            const avgHR = Math.round(data.reduce((sum, item) => sum + (parseInt(item.heart_rate) || 0), 0) / data.length);
            const avgSpO2 = Math.round(data.reduce((sum, item) => sum + (parseInt(item.spo2) || 0), 0) / data.length);
            
            document.getElementById('total-readings').innerText = pagination.total || 0;
            document.getElementById('avg-temp').innerText = avgTemp + '°C';
            document.getElementById('avg-hr').innerText = avgHR + ' bpm';
            document.getElementById('avg-spo2').innerText = avgSpO2 + '%';
            
            // Render table with compact view
            const tbody = document.getElementById('report-body');
            tbody.innerHTML = data.map((item, index) => {
                const time = item.timestamp ? item.timestamp.split(' ')[1] : 'N/A';
                const predText = item.prediction ? item.prediction.substring(0, 30) : 'N/A';
                
                return `
                    <tr onclick="showReadingDetail('${index}')">
                        <td>${pagination.total - ((currentPage - 1) * 10) - index}</td>
                        <td>${time}</td>
                        <td><strong>${item.temperature}°C</strong></td>
                        <td><strong>${item.heart_rate} bpm</strong></td>
                        <td><strong>${item.spo2}%</strong></td>
                        <td class="col-prediction" title="${item.prediction}">${predText}...</td>
                    </tr>
                `;
            }).join('');
            
            // Store data globally for modal
            window.reportDataCache = data;
            
            // Update pagination controls
            updatePaginationControls();
        } else {
            document.getElementById('report-body').innerHTML = `<tr><td colspan="6" style="text-align: center;">No data yet</td></tr>`;
        }
    } catch (error) {
        console.error("Error fetching report data:", error);
    }
}

function updatePaginationControls() {
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const pageInfo = document.getElementById('page-info');
    
    pageInfo.innerText = `Page ${currentPage} of ${totalPages}`;
    
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages;
}

function goToNextPage() {
    if (currentPage < totalPages) {
        fetchReportData(currentPage + 1);
    }
}

function goToPreviousPage() {
    if (currentPage > 1) {
        fetchReportData(currentPage - 1);
    }
}

function showReadingDetail(index) {
    const data = window.reportDataCache[index];
    if (!data) return;
    
    const modal = document.getElementById('detail-modal');
    const modalBody = document.getElementById('modal-body');
    
    modalBody.innerHTML = `
        <div class="detail-section">
            <p><strong>Time:</strong> ${data.timestamp}</p>
            <p><strong>Temperature:</strong> ${data.temperature}°C</p>
            <p><strong>Heart Rate:</strong> ${data.heart_rate} bpm</p>
            <p><strong>SpO2:</strong> ${data.spo2}%</p>
        </div>
        <div class="detail-section">
            <p><strong>Prediction:</strong></p>
            <p>${data.prediction || 'N/A'}</p>
        </div>
        <div class="detail-section">
            <p><strong>Advice:</strong></p>
            <p>${data.advice || 'N/A'}</p>
        </div>
        <div class="result-actions" style="margin-top: 24px; display: flex; justify-content: flex-end;">
            <button class="btn-premium btn-premium-primary" onclick="downloadPDF(${index})">
                <span class="btn-icon">📥</span> Download PDF
            </button>
        </div>
    `;
    
    modal.style.display = 'flex';
}

function downloadPDF(index = 0) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    // Check if we have data to export
    if (!window.reportDataCache || !window.reportDataCache[index]) {
        alert("No data available to download.");
        return;
    }

    const data = window.reportDataCache[index]; 
    
    // --- Header Section ---
    doc.setFillColor(59, 130, 246); // Accent blue
    doc.rect(0, 0, 210, 40, 'F');
    
    doc.setTextColor(255, 255, 255);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(24);
    doc.text("HEALTH ANALYSIS REPORT", 105, 25, { align: 'center' });
    
    // --- Patient / Report Info ---
    doc.setTextColor(30, 41, 59);
    doc.setFontSize(10);
    doc.text("Generated: " + new Date().toLocaleString(), 15, 55);
    doc.text("Report ID: HG-" + Math.random().toString(36).substr(2, 9).toUpperCase(), 15, 60);
    
    // Horizontal Line
    doc.setDrawColor(226, 232, 240);
    doc.line(15, 65, 195, 65);
    
    // --- Vitals Section ---
    doc.setFontSize(14);
    doc.text("Clinical Measurements", 15, 75);
    
    // Vital Cards (Simulated)
    doc.setDrawColor(59, 130, 246);
    doc.rect(15, 80, 55, 30);
    doc.rect(77, 80, 55, 30);
    doc.rect(140, 80, 55, 30);
    
    doc.setFontSize(9);
    doc.setTextColor(100, 116, 139);
    doc.text("TEMPERATURE", 20, 88);
    doc.text("HEART RATE", 82, 88);
    doc.text("OXYGEN (SpO2)", 145, 88);
    
    doc.setFontSize(16);
    doc.setTextColor(30, 41, 59);
    doc.text(data.temperature + "°C", 20, 100);
    doc.text(data.heart_rate + " bpm", 82, 100);
    doc.text(data.spo2 + "%", 145, 100);
    
    // --- Analysis Results ---
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("AI Health Assessment", 15, 125);
    
    // Status
    doc.setFontSize(10);
    doc.setTextColor(71, 85, 105);
    doc.text("CURRENT STATUS:", 15, 135);
    doc.setTextColor(30, 41, 59);
    doc.setFont("helvetica", "bold");
    doc.text(data.prediction || "Monitor", 55, 135);
    
    // Diagnosis
    doc.setFontSize(10);
    doc.setTextColor(71, 85, 105);
    doc.text("DIAGNOSIS:", 15, 145);
    doc.setTextColor(30, 41, 59);
    doc.setFont("helvetica", "normal");
    const diagnosisText = data.diagnosis || "No diagnosis available.";
    const splitDiag = doc.splitTextToSize(diagnosisText, 140);
    doc.text(splitDiag, 55, 145);
    
    let yOffset = 145 + (splitDiag.length * 5) + 5;
    
    // Explanation
    doc.setFontSize(10);
    doc.setTextColor(71, 85, 105);
    doc.text("EXPLANATION:", 15, yOffset);
    doc.setTextColor(30, 41, 59);
    const explanationText = data.explanation || "No explanation provided.";
    const splitExpl = doc.splitTextToSize(explanationText, 140);
    doc.text(splitExpl, 55, yOffset);
    
    yOffset += (splitExpl.length * 5) + 10;
    
    // Advice
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(59, 130, 246);
    doc.text("Clinical Recommendations & Advice:", 15, yOffset);
    
    doc.setFont("helvetica", "normal");
    doc.setTextColor(30, 41, 59);
    const adviceText = data.advice || "Consult a doctor for guidance.";
    const splitAdvice = doc.splitTextToSize(adviceText, 180);
    doc.text(splitAdvice, 15, yOffset + 8);
    
    // --- Footer ---
    doc.setDrawColor(226, 232, 240);
    doc.line(15, 270, 195, 270);
    
    doc.setFontSize(8);
    doc.setTextColor(148, 163, 184);
    doc.text("This is an AI-generated assessment for monitoring purposes. Always consult a medical professional for clinical diagnosis.", 105, 275, { align: 'center' });
    
    doc.save(`health-report-${data.timestamp.replace(/[: ]/g, '-')}.pdf`);
}
