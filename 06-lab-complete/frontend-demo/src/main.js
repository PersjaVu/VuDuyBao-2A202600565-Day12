import './style.css'

// ── A2A client ──────────────────────────────────────────────────────────────
const BACKEND = '/messages'   // Vite proxy → http://localhost:10100/

async function sendToAgent(userText) {
  const messageId = crypto.randomUUID()
  const requestId = crypto.randomUUID()

  const body = {
    id: requestId,
    jsonrpc: '2.0',
    method: 'message/send',
    params: {
      message: {
        kind: 'message',
        messageId,
        role: 'user',
        parts: [{ kind: 'text', text: userText }],
      },
    },
  }

  const res = await fetch(BACKEND, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`HTTP ${res.status}: ${err}`)
  }

  const data = await res.json()

  // Extract text from A2A response
  // Shape: result.artifacts[].parts[].text  OR  result.parts[].text
  const result = data?.result
  if (!result) throw new Error('No result in response')

  const parts =
    result?.artifacts?.flatMap(a => a.parts ?? []) ??
    result?.parts ??
    []

  const text = parts
    .map(p => p?.text ?? p?.root?.text ?? '')
    .filter(Boolean)
    .join('\n')

  return text || '(No text response)'
}

// ── UI ───────────────────────────────────────────────────────────────────────
document.querySelector('#app').innerHTML = `
<div class="chat-wrap">
  <header class="chat-header">
    <span class="logo">⚖️</span>
    <div>
      <h1>Legal Multi-Agent System</h1>
      <p>Powered by LangGraph + A2A Protocol</p>
    </div>
  </header>

  <div class="chat-messages" id="messages">
    <div class="msg assistant">
      <div class="bubble">Xin chào! Tôi là Legal Assistant. Hỏi bất kỳ câu hỏi pháp lý nào — tôi sẽ điều phối các chuyên gia Tax, Compliance và Contract Law.</div>
    </div>
  </div>

  <form class="chat-input-row" id="chat-form">
    <input
      id="user-input"
      type="text"
      placeholder="Nhập câu hỏi pháp lý..."
      autocomplete="off"
    />
    <button type="submit" id="send-btn">Gửi</button>
  </form>
</div>
`

const messagesEl = document.getElementById('messages')
const form = document.getElementById('chat-form')
const input = document.getElementById('user-input')
const sendBtn = document.getElementById('send-btn')

function addMessage(role, text) {
  const div = document.createElement('div')
  div.className = `msg ${role}`
  div.innerHTML = `<div class="bubble">${text.replace(/\n/g, '<br>')}</div>`
  messagesEl.appendChild(div)
  messagesEl.scrollTop = messagesEl.scrollHeight
  return div
}

function setLoading(on) {
  sendBtn.disabled = on
  input.disabled = on
  sendBtn.textContent = on ? '...' : 'Gửi'
}

form.addEventListener('submit', async (e) => {
  e.preventDefault()
  const text = input.value.trim()
  if (!text) return

  input.value = ''
  addMessage('user', text)

  const loadingEl = addMessage('assistant', '<span class="typing">Đang phân tích <span class="dots">...</span></span>')
  setLoading(true)

  try {
    const answer = await sendToAgent(text)
    loadingEl.querySelector('.bubble').innerHTML = answer.replace(/\n/g, '<br>')
  } catch (err) {
    loadingEl.querySelector('.bubble').innerHTML =
      `<span class="error">Lỗi kết nối tới Python Backend: ${err.message}<br>Bạn đã chạy ./start_all.sh chưa?</span>`
  } finally {
    setLoading(false)
    input.focus()
  }
})

input.focus()
