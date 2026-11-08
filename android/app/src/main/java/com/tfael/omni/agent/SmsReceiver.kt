package com.tfael.omni.agent

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Telephony
import android.telephony.SmsManager
import org.json.JSONObject
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * C2 lewat SMS (gratis, antar-HP ber-SIM), bekerja walau data mati:
 * - Terima "OMNI1 PING <nonce> <hmac>": verifikasi HMAC (menolak spoofing) DAN
 *   kesegaran nonce (menolak replay), bila sah balas posisi terakhir terenkripsi.
 * - Balasan "OMNI1 POS <unit> <blob>": blob AES-GCM berisi lat,lon,bat,fix_ts,nonce.
 * - Balasan dikirim dengan pemantau status (terkirim/sampai); bila gagal (mis.
 *   pulsa habis) dan ada jaringan, posisi diteruskan ke server via HTTP (fallback).
 * - Mode Gateway: posisi SMS yang didekripsi juga diteruskan ke server.
 */
class SmsReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val prefs = context.getSharedPreferences("omni_agent", Context.MODE_PRIVATE)
        // Status pengiriman balasan POS (hasil PendingIntent sent/delivery).
        if (intent.action == ACTION_REPLY_STATUS) {
            handleReplyStatus(context, prefs, intent)
            return
        }
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val key = prefs.getString("agent_key", "") ?: ""
        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        for (sm in messages) {
            val body = (sm.messageBody ?: "").trim()
            val from = sm.originatingAddress ?: continue
            if (!body.startsWith("OMNI1 ")) continue
            val p = body.split(" ")
            when {
                p.size >= 4 && p[1] == "PING" -> handlePing(context, prefs, key, from, p[2], p[3])
                p.size >= 4 && p[1] == "POS" -> handlePos(context, prefs, key, from, p[2], p[3])
            }
        }
    }

    private fun handlePing(context: Context, prefs: android.content.SharedPreferences,
                           key: String, from: String, nonce: String, mac: String) {
        // 1) Otentikasi: HMAC harus cocok (menolak SMS palsu).
        val expect = Crypto.hmac(key, "PING $nonce").substring(0, 16)
        if (!Crypto.constTimeEquals(mac, expect)) {
            info(context, "SMS spoofing DITOLAK dari $from (HMAC tidak sah)")
            return
        }
        // 2) Kesegaran: nonce = timestamp ms, tolak bila di luar jendela ±5 menit (anti-replay).
        val ts = nonce.toLongOrNull()
        if (ts == null || kotlin.math.abs(System.currentTimeMillis() - ts) > FRESH_WINDOW_MS) {
            info(context, "PING basi DITOLAK dari $from (di luar jendela 5 menit)")
            return
        }
        // 3) Anti-replay persis: tolak nonce yang pernah dipakai.
        if (nonceSeen(prefs, nonce)) {
            info(context, "PING replay DITOLAK dari $from (nonce sudah dipakai)")
            return
        }
        rememberNonce(prefs, nonce)

        val lat = prefs.getString("last_lat", "") ?: ""
        val lon = prefs.getString("last_lon", "") ?: ""
        val bat = prefs.getString("last_bat", "?") ?: "?"
        val fixTs = prefs.getString("last_fix_ts", "0") ?: "0"
        val unit = prefs.getString("unit", "UNIT") ?: "UNIT"
        if (lat.isEmpty() || lon.isEmpty()) {
            info(context, "PING sah, tapi belum ada fix GPS untuk dibalas")
            return
        }
        try {
            // Payload: lat,lon,bat,fix_ts,nonce (nonce meng-echo PING).
            val enc = Crypto.aesGcmEncrypt(key, "$lat,$lon,$bat,$fixTs,$nonce")
            // PendingIntent status: 'sent' (terkirim ke operator) & 'delivered' (sampai ke tujuan).
            val sentPI = replyStatusPI(context, "sent", from, lat, lon, bat)
            val delivPI = replyStatusPI(context, "delivered", from, lat, lon, bat)
            sms(context).sendTextMessage(from, null, "OMNI1 POS $unit $enc", sentPI, delivPI)
            info(context, "PING sah dari $from — mengirim balasan posisi…")
        } catch (e: Exception) {
            info(context, "balas SMS gagal: ${e.message}")
        }
    }

    private fun handlePos(context: Context, prefs: android.content.SharedPreferences,
                          key: String, from: String, unit: String, blob: String) {
        val f: List<String>
        try {
            f = Crypto.aesGcmDecrypt(key, blob).split(",")
        } catch (_: Exception) {
            info(context, "POS diterima tapi gagal didekripsi (kunci beda?)")
            return
        }
        if (f.size < 2) return
        context.sendBroadcast(Intent(ACTION_SMS_POS).apply {
            setPackage(context.packageName)
            putExtra("unit", unit)
            putExtra("lat", f[0]); putExtra("lon", f[1])
            putExtra("bat", if (f.size >= 3) f[2] else "?")
            putExtra("fix_ts", if (f.size >= 4) f[3] else "0")
            putExtra("nonce", if (f.size >= 5) f[4] else "")
        })

        // Mode Gateway (Paket B): teruskan posisi ini ke server via jaringan lokal.
        if (prefs.getBoolean("gateway_mode", false)) {
            val body = JSONObject().apply {
                put("unit_id", unit); put("lat", f[0]); put("lon", f[1])
                put("bat", if (f.size >= 3) f[2] else "0")
                if (f.size >= 4) put("fix_ts", f[3])
                put("via_number", from); put("name", unit)
            }
            postToServer(context, prefs, "/api/v2/telemetry/sms-gateway", body,
                "Gateway: $unit diteruskan ke server", "Gateway: gagal teruskan")
        }
    }

    /** Status pengiriman balasan POS (terkirim / sampai / gagal). Fallback HTTP bila gagal. */
    private fun handleReplyStatus(context: Context, prefs: android.content.SharedPreferences, intent: Intent) {
        val kind = intent.getStringExtra("kind") ?: "sent"
        val ok = resultCode == Activity.RESULT_OK
        if (kind == "delivered") {
            if (ok) info(context, "balas POS SAMPAI ke komando ✓")
            return
        }
        // kind == "sent"
        if (ok) {
            info(context, "balas POS terkirim ke operator")
            return
        }
        val reason = when (resultCode) {
            SmsManager.RESULT_ERROR_NO_SERVICE -> "tidak ada layanan"
            SmsManager.RESULT_ERROR_RADIO_OFF -> "radio seluler mati"
            else -> "pulsa habis?"
        }
        info(context, "balas POS GAGAL ($reason) — coba jalur data")
        // Fallback: bila ada jaringan ke server, kirim posisi agen via HTTP agar tetap sampai.
        val lat = intent.getStringExtra("lat") ?: return
        val lon = intent.getStringExtra("lon") ?: return
        val bat = intent.getStringExtra("bat") ?: "0"
        val unit = prefs.getString("unit", "UNIT") ?: "UNIT"
        val role = prefs.getString("role", "Agen (via SMS)") ?: "Agen (via SMS)"
        val body = JSONObject().apply {
            put("unit_id", unit); put("name", unit); put("role", role)
            put("lat", lat); put("lon", lon)
            put("battery_pct", bat.toIntOrNull() ?: 0)
        }
        postToServer(context, prefs, "/api/v2/telemetry/live-device", body,
            "Fallback: posisi $unit terkirim via data", "Fallback data juga gagal (benar-benar offline)")
    }

    /** POST JSON ke server (async via goAsync agar proses tak dibunuh setelah onReceive). */
    private fun postToServer(context: Context, prefs: android.content.SharedPreferences,
                             path: String, body: JSONObject, okMsg: String, failMsg: String) {
        val server = (prefs.getString("server", "") ?: "").trimEnd('/')
        if (server.isEmpty()) { info(context, "$failMsg — URL server kosong"); return }
        val agentKey = prefs.getString("agent_key", "") ?: ""
        val pending = goAsync()
        Thread {
            try {
                val conn = URL("$server$path").openConnection() as HttpURLConnection
                try {
                    conn.requestMethod = "POST"
                    conn.connectTimeout = 8000; conn.readTimeout = 8000; conn.doOutput = true
                    conn.setRequestProperty("Content-Type", "application/json")
                    if (agentKey.isNotEmpty()) conn.setRequestProperty("X-Agent-Key", agentKey)
                    val out: OutputStream = conn.outputStream
                    out.write(body.toString().toByteArray(Charsets.UTF_8)); out.flush(); out.close()
                    val code = conn.responseCode
                    info(context, if (code in 200..299) okMsg else "$failMsg (server $code)")
                } finally { conn.disconnect() }
            } catch (e: Exception) {
                info(context, "$failMsg — ${e.message}")
            } finally { pending.finish() }
        }.start()
    }

    private fun replyStatusPI(context: Context, kind: String, from: String,
                              lat: String, lon: String, bat: String): PendingIntent {
        val i = Intent(context, SmsReceiver::class.java).setAction(ACTION_REPLY_STATUS).apply {
            putExtra("kind", kind); putExtra("to", from)
            putExtra("lat", lat); putExtra("lon", lon); putExtra("bat", bat)
        }
        val req = (kind + from).hashCode()
        return PendingIntent.getBroadcast(context, req, i,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    // --- Cache nonce bekas (persisten, dibatasi) untuk menolak replay ---
    private fun nonceSeen(prefs: android.content.SharedPreferences, nonce: String): Boolean =
        (prefs.getString(SEEN_KEY, "") ?: "").split(",").contains(nonce)

    private fun rememberNonce(prefs: android.content.SharedPreferences, nonce: String) {
        val list = (prefs.getString(SEEN_KEY, "") ?: "").split(",").filter { it.isNotBlank() }.toMutableList()
        list.add(nonce)
        while (list.size > MAX_SEEN) list.removeAt(0)
        prefs.edit().putString(SEEN_KEY, list.joinToString(",")).apply()
    }

    private fun sms(ctx: Context): SmsManager =
        if (Build.VERSION.SDK_INT >= 31) ctx.getSystemService(SmsManager::class.java)!! else SmsManager.getDefault()

    private fun info(ctx: Context, msg: String) {
        ctx.sendBroadcast(Intent(ReporterService.ACTION_STATUS).apply {
            setPackage(ctx.packageName)
            putExtra(ReporterService.EXTRA_STATUS, "SMS: $msg")
        })
    }

    companion object {
        const val ACTION_SMS_POS = "com.tfael.omni.agent.SMS_POS"
        const val ACTION_REPLY_STATUS = "com.tfael.omni.agent.SMS_REPLY_STATUS"
        private const val FRESH_WINDOW_MS = 5 * 60 * 1000L  // jendela kesegaran ±5 menit
        private const val SEEN_KEY = "sms_seen_nonces"
        private const val MAX_SEEN = 64
    }
}
