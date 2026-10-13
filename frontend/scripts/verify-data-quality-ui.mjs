import { spawn, spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..', '..')
const python = resolve(root, 'backend', '.venv', 'Scripts', 'python.exe')
const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const outputDir = resolve(root, 'docs', 'acceptance', 'evidence', 'phase_s5_2_b2_part1')
const debugPort = 9223
const profile = mkdtempSync(resolve(tmpdir(), 'dq-ui-cdp-'))
const browserUserId = Number(process.env.DQ_BROWSER_USER_ID)
if (!Number.isInteger(browserUserId) || browserUserId < 1) {
  throw new Error('DQ_BROWSER_USER_ID must identify the isolated administrator')
}

const tokenProcess = spawnSync(
  python,
  [
    '-c',
    `from auth.jwt import create_access_token; from config.settings import get_settings; s=get_settings(); print(create_access_token(user_id=${browserUserId}, username='dq-integration-admin', role='ADMINISTRATOR', secret_key=s.secret_key.get_secret_value(), expires_minutes=10))`,
  ],
  { cwd: resolve(root, 'backend'), encoding: 'utf8' },
)
if (tokenProcess.status !== 0) {
  const reason = tokenProcess.error?.message ?? tokenProcess.stderr?.trim() ?? 'unknown subprocess error'
  throw new Error(`Could not create isolated-browser JWT: ${reason}`)
}
const token = tokenProcess.stdout.trim()

const chrome = spawn(
  chromePath,
  [
    '--headless=new',
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profile}`,
    '--disable-gpu',
    '--no-first-run',
    '--window-size=1920,1080',
    'about:blank',
  ],
  { stdio: 'ignore' },
)

try {
  const target = await waitForTarget()
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolveOpen, rejectOpen) => {
    socket.addEventListener('open', resolveOpen, { once: true })
    socket.addEventListener('error', rejectOpen, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (!message.id) return
    const entry = pending.get(message.id)
    if (!entry) return
    pending.delete(message.id)
    if (message.error) entry.reject(new Error(JSON.stringify(message.error)))
    else entry.resolve(message.result)
  })
  const send = (method, params = {}) => new Promise((resolveSend, rejectSend) => {
    const id = nextId++
    pending.set(id, { resolve: resolveSend, reject: rejectSend })
    socket.send(JSON.stringify({ id, method, params }))
  })

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false,
  })
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/login' })
  await waitForExpression(send, "document.readyState === 'complete'")
  await send('Runtime.evaluate', {
    expression: `localStorage.setItem('access_token', ${JSON.stringify(token)})`,
  })
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/data-quality' })
  await waitForExpression(
    send,
    "document.body.innerText.includes('97.00') && document.body.innerText.includes('DQ_T_SNAPSHOT_FRESHNESS') && !document.querySelector('.el-loading-mask')",
    20_000,
  )
  const textResult = await send('Runtime.evaluate', {
    expression: 'document.body.innerText',
    returnByValue: true,
  })
  const bodyText = textResult.result.value
  for (const expected of [
    'Quality Score V2.0',
    '97.00',
    'DQ_C_PLAY_COUNT_COVERAGE',
    'DQ_A_CUMULATIVE_NONNEGATIVE',
    'DQ_K_REVISION_CHAIN_VALID',
    'DQ_T_SNAPSHOT_FRESHNESS',
    '历史范围使用当前主数据状态',
  ]) {
    if (!bodyText.includes(expected)) throw new Error(`Missing UI evidence: ${expected}`)
  }

  mkdirSync(outputDir, { recursive: true })
  await screenshot(send, resolve(outputDir, 'data-quality-v2-1920x1080.png'))
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1366,
    height: 768,
    deviceScaleFactor: 1,
    mobile: false,
  })
  await send('Page.reload', { ignoreCache: true })
  await waitForExpression(
    send,
    "document.readyState === 'complete' && document.body.innerText.includes('97.00') && document.body.innerText.includes('DQ_T_SNAPSHOT_FRESHNESS') && !document.querySelector('.el-loading-mask')",
    20_000,
  )
  await delay(300)
  const overflow = await send('Runtime.evaluate', {
    expression: 'document.documentElement.scrollWidth > document.documentElement.clientWidth',
    returnByValue: true,
  })
  if (overflow.result.value) throw new Error('Horizontal page overflow at 1366x768')
  await screenshot(send, resolve(outputDir, 'data-quality-v2-1366x768.png'))

  await send('Runtime.evaluate', {
    expression: `(() => {
      const wrapper = document.querySelector('.toolbar .el-select__wrapper')
      if (!wrapper) throw new Error('Quality algorithm selector was not found')
      wrapper.click()
    })()`,
  })
  await waitForExpression(
    send,
    "[...document.querySelectorAll('.el-select-dropdown__item')].some((item) => item.textContent.includes('Quality Score V1.0'))",
  )
  await send('Runtime.evaluate', {
    expression: `(() => {
      const option = [...document.querySelectorAll('.el-select-dropdown__item')]
        .find((item) => item.textContent.includes('Quality Score V1.0'))
      if (!option) throw new Error('Quality Score V1.0 option was not found')
      option.click()
    })()`,
  })
  await waitForExpression(
    send,
    "document.querySelector('.score-meta')?.innerText.includes('Quality Score V1.0') && document.body.innerText.includes('100.00') && !document.querySelector('.el-loading-mask')",
    20_000,
  )
  socket.close()
  console.log('Data Quality browser verification passed at 1920x1080 and 1366x768, including V1/V2 switching')
} finally {
  chrome.kill()
  await Promise.race([
    new Promise((resolveExit) => chrome.once('exit', resolveExit)),
    delay(2_000),
  ])
  try {
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 })
  } catch {
    // Chrome can retain a transient lock on Windows; the OS temp directory owns cleanup.
  }
}

async function waitForTarget() {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    try {
      const targets = await fetch(`http://127.0.0.1:${debugPort}/json`).then((response) => response.json())
      const page = targets.find((item) => item.type === 'page')
      if (page) return page
    } catch {}
    await delay(100)
  }
  throw new Error('Chrome DevTools target did not become available')
}

async function waitForExpression(send, expression, timeout = 10_000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const result = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
    })
    if (result.result.value) return
    await delay(100)
  }
  throw new Error(`Timed out waiting for: ${expression}`)
}

async function screenshot(send, path) {
  const result = await send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
  })
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(result.data, 'base64'))
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds))
}
