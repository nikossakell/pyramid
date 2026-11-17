/**
 * Screenshots κάθε οθόνης σε 360 / 768 / 1024 / 1440 px (Στάδιο 4 του responsive) με Playwright Chromium,
 * πάνω σε demo backend (scripts/demo_backend.sh) και `npm run dev`. Έξοδος: frontend/screenshots/ (στο .gitignore).
 * Σε κάθε πλάτος ελέγχει: καμία οριζόντια κύλιση, HelpButton ορατό, Tab φτάνει σε όλα τα κουμπιά, Esc κλείνει dialogs.
 *
 *   PYRAMID_KEY=<κλειδί παιδιού> node scripts/screenshots.mjs [--only S04,S05] [--widths 360,1440]
 *
 * Το playwright μπορεί να είναι στην cache του npx: PLAYWRIGHT_PATH=~/.npm/_npx/<hash>/node_modules/playwright.
 */
import { mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright')

const BASE = process.env.PYRAMID_URL || 'http://localhost:5173'
const KEY = process.env.PYRAMID_KEY
const OUT = path.resolve('screenshots')
const args = process.argv.slice(2)
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def }
const WIDTHS = opt('--widths', '360,768,1024,1440').split(',').map(Number)
const ONLY = opt('--only', '').split(',').filter(Boolean)
if (!KEY) { console.error('PYRAMID_KEY λείπει (κλειδί demo παιδιού από το scripts/demo_backend.sh)'); process.exit(2) }
mkdirSync(OUT, { recursive: true })

async function shoot(p) {
  await p.locator('button[aria-label="Λήψη φωτογραφίας"]:enabled').click()
  await p.waitForURL(/\/log\/confirm/)
  await p.waitForTimeout(300)
}

/** Σκηνές: όνομα, διαδρομή, προαιρετική ενέργεια πριν το screenshot (ανοίγει dialog κ.λπ.). */
const SCENES = [
  { id: 'S02-login', path: '/login', anon: true },
  { id: 'S02-login-nokey', path: '/login', anon: true, act: async (p) => p.getByRole('button', { name: 'Δεν έχω κλειδί' }).click() },
  { id: 'M01-help', path: '/login', anon: true, act: async (p) => p.getByRole('button', { name: /Βοήθεια/ }).click() },
  { id: 'S04-today', path: '/today' },
  { id: 'S05-newlog', path: '/today', act: async (p) => p.locator('nav a[href="/log"]:visible').first().click() },
  { id: 'M04-camera-permission', path: '/today', act: async (p) => {
    await p.evaluate(() => localStorage.removeItem('pyramid.camera_intro_seen'))
    await p.locator('nav a[href="/log"]:visible').first().click()
    await p.getByRole('button', { name: /Φωτογραφία/ }).click()
  } },
  { id: 'S06-camera', path: '/log/camera', act: async (p) => p.locator('button[aria-label="Λήψη φωτογραφίας"]:enabled').waitFor() },
  // Το πρόχειρο ζει μόνο στη μνήμη (ποτέ σε storage): κάθε σκηνή του S08 και μετά ξεκινά από λήψη στο S06.
  { id: 'S08-confirm', path: '/log/camera', act: shoot },
  { id: 'M02-portion', path: '/log/camera', act: async (p) => { await shoot(p); await p.getByRole('button', { name: 'Πόσο μεγάλο ήταν;' }).first().click() }, skipExpanded: true },
  { id: 'S11-saved', path: '/log/camera', act: async (p) => {
    await shoot(p)
    for (const alt of await p.locator('.alts button.chip--outline').all()) { if (await alt.isVisible()) { await alt.click(); break } }
    for (const group of await p.getByRole('radiogroup', { name: /Μερίδα για/ }).all()) await group.getByRole('radio').first().click()
    await p.getByRole('button', { name: 'Σωστό, αποθήκευσε' }).click()
    await p.waitForURL(/\/log\/saved/)
    await p.waitForTimeout(300)
  } },
  { id: 'S09-text', path: '/log/text' },
  { id: 'S10-search', path: '/log/search' },
  { id: 'S12-history', path: '/history' },
  { id: 'S12-history-detail', path: '/history', act: async (p) => {
    const card = p.locator('.mealcard:visible, .meal:visible').first()
    await card.click()
    await p.waitForTimeout(300)
  } },
  { id: 'S10-search-group', path: '/log/search', act: async (p) => p.locator('.cat:visible').first().click() },
  { id: 'S01-splash', path: '/', anon: true },
  { id: 'S19-study-end', path: '/study-ended', anon: true },
  { id: 'S20-error', path: '/error', anon: true },
  { id: 'S21-not-yet', path: '/not-yet', anon: true },
  { id: 'S17-profile', path: '/profile' },
  { id: 'S18-privacy', path: '/privacy' },
  { id: 'S13-chat', path: '/chat' },
  { id: 'S14-cards', path: '/cards' },
]

async function login(page) {
  await page.goto(`${BASE}/login`)
  await page.getByPlaceholder('Γράψε το κλειδί σου').fill(KEY)
  await page.getByRole('button', { name: 'Μπες' }).click()
  await page.waitForURL(/\/(today|onboarding)/)
  if (page.url().includes('/onboarding')) {              // S03: πέρνα τα 4 βήματα + avatar
    for (let i = 0; i < 4; i++) await page.getByRole('button', { name: 'Επόμενο' }).click()
    await page.getByRole('button', { name: 'Ξεκίνα' }).click()
    await page.waitForURL(/\/today/)
  }
}

async function checks(page, width, id) {
  const problems = []
  const scrollX = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  if (scrollX > 1) problems.push(`οριζόντια κύλιση ${scrollX}px`)
  const help = page.getByRole('button', { name: /Βοήθεια/ }).first()
  if (!(await help.isVisible().catch(() => false))) problems.push('HelpButton μη ορατό')
  else {
    const box = await help.boundingBox()
    if (box && (box.x + box.width > width + 1 || box.y < 0)) problems.push('HelpButton εκτός οθόνης')
  }
  // Tab: κάθε κουμπί/σύνδεσμος που φαίνεται πρέπει να παίρνει εστίαση
  const unreachable = await page.evaluate(() => {
    const els = [...document.querySelectorAll('a[href], button')].filter((el) => el.offsetParent !== null && !el.disabled)
    return els.filter((el) => el.tabIndex < 0).map((el) => el.textContent.trim().slice(0, 30))
  })
  if (unreachable.length) problems.push(`χωρίς Tab: ${unreachable.join(' | ')}`)
  const dialog = page.locator('[role="dialog"], [role="alertdialog"]').first()
  if (await dialog.isVisible().catch(() => false)) {
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
    if (await dialog.isVisible().catch(() => false)) problems.push('Esc δεν κλείνει το dialog')
  }
  return problems.length ? `${id} @${width}: ${problems.join('; ')}` : null
}

// Ψεύτικη κάμερα του Chromium (χρωματιστό δοκιμαστικό βίντεο) ώστε να φαίνεται το S06 και να περνά η ροή S06 → S08 → S11.
const browser = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] })
const report = []
for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: 'light', locale: 'el-GR', permissions: ['camera'] })
  const page = await ctx.newPage()
  let loggedIn = false
  for (const s of SCENES) {
    if (ONLY.length && !ONLY.some((o) => s.id.startsWith(o))) continue
    if (s.skipExpanded && width >= 1024) continue
    try {
      if (!s.anon && !loggedIn) { await login(page); loggedIn = true }
      if (s.anon && loggedIn) { await ctx.clearCookies(); await page.evaluate(() => localStorage.clear()); loggedIn = false }
      await page.goto(`${BASE}${s.path}`)
      await page.waitForLoadState('networkidle')
      if (s.act) { await s.act(page); await page.waitForTimeout(400) }
      await page.screenshot({ path: path.join(OUT, `${s.id}-${width}.png`), fullPage: false })
      const problem = await checks(page, width, s.id)
      if (problem) report.push(problem)
      console.log(`${s.id} @${width}${problem ? '  !! ' + problem.split(': ')[1] : ''}`)
    } catch (e) {
      report.push(`${s.id} @${width}: ΣΦΑΛΜΑ ${String(e.message).split('\n')[0]}`)
      console.log(`${s.id} @${width}  !! ${String(e.message).split('\n')[0]}`)
    }
  }
  await ctx.close()
}
await browser.close()
console.log(report.length ? `\nΠροβλήματα (${report.length}):\n` + report.join('\n') : '\nΚανένα πρόβλημα στους ελέγχους.')
