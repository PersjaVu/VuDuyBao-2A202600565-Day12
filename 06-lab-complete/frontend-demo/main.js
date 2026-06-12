// main.js - Logic for A2A Multi-Agent Simulation

const nodesInfo = [
  { id: 'node-customer', x: 50, y: 15 },
  { id: 'node-law', x: 50, y: 45 },
  { id: 'node-tax', x: 20, y: 80 },
  { id: 'node-compliance', x: 50, y: 80 },
  { id: 'node-privacy', x: 80, y: 80 }
];

const connections = [
  { from: 'node-customer', to: 'node-law', id: 'path-cust-law' },
  { from: 'node-law', to: 'node-tax', id: 'path-law-tax' },
  { from: 'node-law', to: 'node-compliance', id: 'path-law-comp' },
  { from: 'node-law', to: 'node-privacy', id: 'path-law-priv' }
];

// Elements
const svg = document.getElementById('connectionLines');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatHistory = document.getElementById('chatHistory');

// Position Nodes & Draw Lines
function initGraph() {
  const container = document.getElementById('graphContainer');
  const w = container.clientWidth;
  const h = container.clientHeight;

  // Set Positions
  nodesInfo.forEach(n => {
    const el = document.getElementById(n.id);
    el.style.left = `${n.x}%`;
    el.style.top = `${n.y}%`;
  });

  // Draw Lines
  connections.forEach(c => {
    const fromEl = document.getElementById(c.from);
    const toEl = document.getElementById(c.to);
    
    // Calculate coordinates (center of nodes)
    const x1 = (parseFloat(fromEl.style.left) / 100) * w;
    const y1 = (parseFloat(fromEl.style.top) / 100) * h;
    const x2 = (parseFloat(toEl.style.left) / 100) * w;
    const y2 = (parseFloat(toEl.style.top) / 100) * h;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('id', c.id);
    path.setAttribute('class', 'conn-line');
    
    // Curved line
    const cp1x = x1;
    const cp1y = y1 + (y2 - y1) / 2;
    const cp2x = x2;
    const cp2y = y1 + (y2 - y1) / 2;
    
    path.setAttribute('d', `M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`);
    svg.appendChild(path);
  });
}

// Window resize handler
window.addEventListener('resize', () => {
  svg.innerHTML = '';
  initGraph();
});

// Sleep helper
const sleep = ms => new Promise(r => setTimeout(r, ms));

// UI Helpers
function appendMessage(text, type, sender = '') {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${type}`;
  if (sender) {
    msgDiv.innerHTML = `<strong>${sender}</strong>${text}`;
  } else {
    msgDiv.innerText = text;
  }
  chatHistory.appendChild(msgDiv);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function setNodeState(nodeId, state) {
  const el = document.getElementById(nodeId);
  el.className = `agent-node ${nodeId.split('-')[1]}`; // reset classes
  if (state) el.classList.add(state);
}

function setLineState(lineId, isActive) {
  const line = document.getElementById(lineId);
  if (isActive) line.classList.add('active');
  else line.classList.remove('active');
}

// --- SIMULATION LOGIC ---
async function runSimulation(query) {
  sendBtn.disabled = true;
  chatInput.disabled = true;

  // 1. Customer Agent nhận Request
  setNodeState('node-customer', 'processing');
  await sleep(500);
  setNodeState('node-customer', 'active');
  setLineState('path-cust-law', true);
  
  // 2. Tới Law Agent
  setNodeState('node-law', 'processing');
  appendMessage("Đang gửi Request xuống Customer Agent (Python Backend ở Port 10100)...", "system-msg");
  
  // Gửi request thực tế
  const uuid = crypto.randomUUID();
  const payload = {
    id: uuid,
    jsonrpc: "2.0",
    method: "message/send",
    params: {
      message: {
        kind: "message",
        messageId: crypto.randomUUID(),
        parts: [{ kind: "text", text: query }],
        role: "user"
      }
    }
  };

  // Blink các agent phụ ngẫu nhiên để thể hiện graph đang chạy ẩn
  let fetching = true;
  const blinkTask = (async () => {
    while(fetching) {
      const nodes = ['node-tax', 'node-compliance', 'node-privacy'];
      for(let n of nodes) setNodeState(n, Math.random() > 0.5 ? 'processing' : '');
      const lines = ['path-law-tax', 'path-law-comp', 'path-law-priv'];
      for(let l of lines) setLineState(l, Math.random() > 0.5);
      await sleep(600);
    }
  })();

  try {
    const tStart = performance.now();
    const res = await fetch('/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if(!res.ok) throw new Error("API lỗi " + res.status);
    const data = await res.json();
    const tEnd = performance.now();
    
    fetching = false;
    
    // Tắt hết đèn chờ
    ['path-law-tax', 'path-law-comp', 'path-law-priv'].forEach(l => setLineState(l, false));
    ['node-tax', 'node-compliance', 'node-privacy'].forEach(n => setNodeState(n, 'done'));
    setLineState('path-cust-law', false);
    setNodeState('node-law', 'done');
    setNodeState('node-customer', 'done');

    // Bóc xuất text từ A2A JSON Response
    let finalResponse = "";
    if (data.result && data.result.parts) {
      finalResponse = data.result.parts.map(p => p.text || (p.root && p.root.text) || "").join("");
    } else if (data.result && data.result.artifacts) {
       for(let a of data.result.artifacts) {
          for(let p of a.parts) finalResponse += p.text || (p.root && p.root.text) || "";
       }
    } else {
       finalResponse = "Raw: " + JSON.stringify(data).substring(0, 150);
    }
    
    appendMessage(finalResponse.replace(/\n/g, '<br>') + `<br><br><i>⏱ Latency: ${((tEnd - tStart)/1000).toFixed(2)}s</i>`, "agent-msg", "Customer Agent (AI Thật)");
    
  } catch (err) {
    fetching = false;
    appendMessage("Lỗi kết nối tới Python Backend: " + err.message + ". Bạn đã chạy ./start_all.sh chưa?", "system-msg");
  }

  sendBtn.disabled = false;
  chatInput.disabled = false;
  chatInput.value = '';
  chatInput.focus();

  // Reset UI
  setTimeout(() => {
    ['node-customer', 'node-law', 'node-tax', 'node-compliance', 'node-privacy'].forEach(id => setNodeState(id, ''));
  }, 5000);
}

// Events
sendBtn.addEventListener('click', () => {
  const text = chatInput.value.trim();
  if (!text) return;
  appendMessage(text, 'user-msg');
  runSimulation(text);
});

chatInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendBtn.click();
});

// Init
window.onload = () => {
  setTimeout(initGraph, 100);
};
