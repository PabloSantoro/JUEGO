const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname)));

// ── Estado global ──────────────────────────────────────────────────────────
let pendingMessages = [];   // { id, sender, text, time, read }
let qrDataUrl = null;       // QR en base64 para mostrar en la web
let connected = false;
let sock = null;

// ── WhatsApp connection ────────────────────────────────────────────────────
async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth_info');
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: true,
    browser: ['Lector Mensajes', 'Chrome', '1.0.0'],
    getMessage: async () => ({ conversation: '' }),
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrDataUrl = await QRCode.toDataURL(qr);
      connected = false;
      console.log('📱 QR generado - abrí /qr en el navegador');
    }

    if (connection === 'close') {
      connected = false;
      qrDataUrl = null;
      const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;
      if (reason === DisconnectReason.loggedOut) {
        console.log('⚠ Sesión cerrada. Borrá la carpeta auth_info y reiniciá.');
      } else {
        console.log('🔄 Reconectando…');
        setTimeout(connectToWhatsApp, 3000);
      }
    }

    if (connection === 'open') {
      connected = true;
      qrDataUrl = null;
      console.log('✅ WhatsApp conectado!');
    }
  });

  sock.ev.on('messages.upsert', ({ messages: msgs, type }) => {
    if (type !== 'notify') return;
    for (const msg of msgs) {
      if (msg.key.fromMe) continue;                          // ignorar propios
      if (!msg.message) continue;

      const text =
        msg.message.conversation ||
        msg.message.extendedTextMessage?.text ||
        msg.message.imageMessage?.caption ||
        '[Mensaje sin texto]';

      const jid = msg.key.remoteJid || '';
      const isGroup = jid.endsWith('@g.us');
      let sender = msg.pushName || jid.split('@')[0];
      if (isGroup && msg.key.participant) {
        sender = msg.pushName || msg.key.participant.split('@')[0];
      }

      const now = new Date();
      const timeStr = now.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });

      pendingMessages.push({
        id: msg.key.id,
        sender,
        text,
        time: timeStr,
        read: false,
      });

      console.log(`💬 Nuevo mensaje de ${sender}: ${text.slice(0, 50)}`);
    }
  });
}

// ── API endpoints ──────────────────────────────────────────────────────────

// Estado de conexión + QR
app.get('/api/status', (req, res) => {
  res.json({ connected, hasQr: !!qrDataUrl });
});

// QR como imagen HTML
app.get('/qr', (req, res) => {
  if (connected) {
    return res.send('<h2 style="font-family:sans-serif;color:green;text-align:center;margin-top:40px">✅ WhatsApp conectado!</h2>');
  }
  if (!qrDataUrl) {
    return res.send('<h2 style="font-family:sans-serif;text-align:center;margin-top:40px">⏳ Generando QR… recargá en unos segundos.</h2>');
  }
  res.send(`<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Escanear QR WhatsApp</title>
<style>
  body{background:#111;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;font-family:sans-serif;color:#fff}
  img{border-radius:16px;max-width:280px;width:90vw}
  p{color:#aaa;margin-top:16px;font-size:.9rem;text-align:center}
  .refresh{color:#25d366;font-size:.8rem;margin-top:8px}
</style>
<script>setTimeout(()=>location.reload(),15000)</script>
</head>
<body>
  <h2>📱 Escaneá con WhatsApp</h2>
  <img src="${qrDataUrl}" alt="QR WhatsApp"/>
  <p>Abrí WhatsApp → Dispositivos vinculados → Vincular dispositivo</p>
  <p class="refresh">(Se recarga automáticamente)</p>
</body></html>`);
});

// Mensajes pendientes
app.get('/api/messages', (req, res) => {
  res.json({ connected, messages: pendingMessages });
});

// Marcar como leído
app.post('/api/messages/read', (req, res) => {
  const { id } = req.body;
  const msg = pendingMessages.find(m => m.id === id);
  if (msg) msg.read = true;
  res.json({ ok: true });
});

// Marcar todos como leídos
app.post('/api/messages/read-all', (req, res) => {
  pendingMessages.forEach(m => m.read = true);
  res.json({ ok: true });
});

// ── Arrancar ───────────────────────────────────────────────────────────────
const PORT = 3001;
app.listen(PORT, () => {
  console.log(`🚀 Servidor en http://localhost:${PORT}`);
  console.log(`📱 QR code en http://localhost:${PORT}/qr`);
});

connectToWhatsApp().catch(console.error);
