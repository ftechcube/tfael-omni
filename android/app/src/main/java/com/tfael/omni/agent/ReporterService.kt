package com.tfael.omni.agent

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.telephony.CellInfo
import android.telephony.CellInfoGsm
import android.telephony.CellInfoLte
import android.telephony.CellInfoNr
import android.telephony.CellInfoWcdma
import android.telephony.CellSignalStrengthNr
import android.telephony.TelephonyManager
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Foreground service: membaca GPS, baterai, kekuatan sinyal, dan serving cell,
 * lalu mengirimkannya ke endpoint telemetri TFAEL-OMNI tiap interval.
 */
class ReporterService : Service(), LocationListener {

    @Volatile private var running = false
    private var worker: Thread? = null
    private var lastLocation: Location? = null

    private val locationManager: LocationManager by lazy {
        getSystemService(Context.LOCATION_SERVICE) as LocationManager
    }
    private val telephony: TelephonyManager? by lazy {
        getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIF_ID, buildNotification("Agen aktif", "Menunggu posisi GPS..."))
        requestLocationUpdates()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!running) {
            running = true
            worker = Thread { reportLoop() }.also { it.start() }
        }
        return START_STICKY
    }

    @SuppressLint("MissingPermission")
    private fun requestLocationUpdates() {
        try {
            val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            for (p in providers) {
                if (locationManager.isProviderEnabled(p)) {
                    locationManager.requestLocationUpdates(p, 5000L, 5f, this, Looper.getMainLooper())
                    // Jangan menyemai dari fix tersimpan yang sudah BASI (mode pesawat/indoor
                    // sering menyisakan lokasi lama di tempat sebelumnya).
                    locationManager.getLastKnownLocation(p)?.let {
                        if (fixAgeMs(it) <= STALE_FIX_MS && isBetterLocation(it, lastLocation)) lastLocation = it
                    }
                }
            }
        } catch (_: SecurityException) {
        } catch (_: Exception) {
        }
    }

    override fun onLocationChanged(location: Location) {
        // Hanya pakai fix yang lebih baik agar fix jaringan kasar tidak menimpa GPS presisi.
        if (isBetterLocation(location, lastLocation)) lastLocation = location
    }

    /**
     * Heuristik standar Android: fix baru dianggap lebih baik bila lebih akurat,
     * atau lebih baru tanpa jauh lebih buruk akurasinya. Mencegah fix NETWORK/WiFi
     * yang meleset ratusan meter menggeser penanda dari posisi GPS yang benar.
     */
    private fun isBetterLocation(loc: Location, cur: Location?): Boolean {
        if (cur == null) return true
        val timeDelta = loc.time - cur.time
        val isMuchNewer = timeDelta > 60_000L
        val isMuchOlder = timeDelta < -60_000L
        if (isMuchOlder) return false
        val isNewer = timeDelta > 0
        val accuracyDelta = loc.accuracy - cur.accuracy
        val isMoreAccurate = accuracyDelta < 0
        val isSignificantlyLessAccurate = accuracyDelta > 200
        val sameProvider = loc.provider == cur.provider
        return when {
            isMoreAccurate -> true
            isNewer && accuracyDelta <= 0 -> true
            isNewer && !isSignificantlyLessAccurate && sameProvider -> true
            isMuchNewer && !isSignificantlyLessAccurate -> true
            else -> false
        }
    }

    /** Umur fix dalam ms, pakai jam monotonic (kebal perubahan jam sistem). */
    private fun fixAgeMs(loc: Location): Long =
        (SystemClock.elapsedRealtimeNanos() - loc.elapsedRealtimeNanos) / 1_000_000L

    private fun ageText(ms: Long): String = when {
        ms < 90_000 -> "${ms / 1000}s"
        ms < 5_400_000 -> "${ms / 60_000}m"
        else -> "${ms / 3_600_000}j"
    }

    // Callback lama (API < 29) — tak dipakai tapi wajib ada pada sebagian perangkat.
    @Deprecated("Deprecated in API 29")
    override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}

    private fun reportLoop() {
        val prefs = getSharedPreferences("omni_agent", Context.MODE_PRIVATE)
        while (running) {
            val intervalSec = (prefs.getString(MainActivity.KEY_INTERVAL, "15") ?: "15")
                .toIntOrNull()?.coerceIn(5, 3600) ?: 15
            try {
                val status = reportOnce(prefs)
                broadcast(status)
                updateNotification("Agen aktif", status)
            } catch (e: Exception) {
                broadcast("Galat: ${e.message}")
            }
            var slept = 0
            while (running && slept < intervalSec) {
                try { Thread.sleep(1000) } catch (_: InterruptedException) {}
                slept++
            }
        }
    }

    private fun reportOnce(prefs: android.content.SharedPreferences): String {
        val server = (prefs.getString(MainActivity.KEY_SERVER, "") ?: "").trimEnd('/')
        val unitId = prefs.getString(MainActivity.KEY_UNIT, "ALPHA-01") ?: "ALPHA-01"
        val role = prefs.getString(MainActivity.KEY_ROLE, "Unit") ?: "Unit"
        val agentKey = prefs.getString(MainActivity.KEY_AGENTKEY, "") ?: ""
        if (server.isEmpty()) return "URL server kosong."

        val loc = lastLocation ?: return "Menunggu GPS (belum ada fix)..."
        // Jangan laporkan lokasi BASI sebagai posisi terkini — itu bikin peta salah.
        val age = fixAgeMs(loc)
        if (age > STALE_FIX_MS) {
            return "Fix GPS basi (${ageText(age)} lalu, ±${loc.accuracy.toInt()}m) — tidak dikirim. " +
                   "Matikan mode pesawat / keluar ruangan untuk fix segar."
        }
        val battery = readBatteryPct()
        val cellData = readCells()

        // Simpan posisi terakhir agar C2-SMS bisa membalas walau data mati.
        prefs.edit()
            .putString("last_lat", String.format(Locale.US, "%.6f", loc.latitude))
            .putString("last_lon", String.format(Locale.US, "%.6f", loc.longitude))
            .putString("last_bat", battery.toString())
            // Waktu fix (epoch ms) agar balasan C2-SMS bisa menyertakan umur posisi.
            .putString("last_fix_ts", (if (loc.time > 0) loc.time else System.currentTimeMillis()).toString())
            .apply()

        val body = JSONObject().apply {
            put("unit_id", unitId)
            put("name", role)
            put("role", role)
            put("lat", loc.latitude)
            put("lon", loc.longitude)
            put("alt_m", loc.altitude.toInt())
            put("accuracy_m", loc.accuracy.toInt())
            put("speed_kmh", (loc.speed * 3.6f).toInt())
            put("battery_pct", battery)
            put("is_sos", false)
            put("rssi_dbm", cellData.rssiDbm)
            cellData.mcc?.let { put("mcc", it) }
            cellData.mnc?.let { put("mnc", it) }
            put("cells", cellData.cells)
            if (agentKey.isNotEmpty()) put("agent_key", agentKey)
        }

        val code = postJson("$server/api/v2/telemetry/live-device", body, agentKey)
        val t = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        return if (code in 200..299) {
            "OK $t · ${fmt(loc.latitude)}, ${fmt(loc.longitude)} · ±${loc.accuracy.toInt()}m · fix ${ageText(age)} lalu · bat $battery% · ${cellData.rssiDbm} dBm · ${cellData.cells.length()} sel"
        } else {
            "Server menolak (HTTP $code) $t"
        }
    }

    private fun postJson(urlStr: String, body: JSONObject, agentKey: String): Int {
        val url = URL(urlStr)
        val conn = url.openConnection() as HttpURLConnection
        return try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            if (agentKey.isNotEmpty()) conn.setRequestProperty("X-Agent-Key", agentKey)
            val out: OutputStream = conn.outputStream
            out.write(body.toString().toByteArray(Charsets.UTF_8))
            out.flush(); out.close()
            conn.responseCode
        } finally {
            conn.disconnect()
        }
    }

    private fun readBatteryPct(): Int {
        return try {
            val intent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
            val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
            if (level >= 0 && scale > 0) (level * 100 / scale) else 0
        } catch (_: Exception) { 0 }
    }

    private data class CellData(val cells: JSONArray, val rssiDbm: Int, val mcc: Int?, val mnc: Int?)

    @SuppressLint("MissingPermission")
    private fun readCells(): CellData {
        val arr = JSONArray()
        var bestDbm = 0
        var topMcc: Int? = null
        var topMnc: Int? = null
        try {
            val infos: List<CellInfo> = telephony?.allCellInfo ?: emptyList()
            for (info in infos) {
                val cell = JSONObject()
                var dbm = 0
                try {
                    when (info) {
                        is CellInfoLte -> {
                            val id = info.cellIdentity
                            cell.put("radio", "lte")
                            cell.put("lac", id.tac)
                            cell.put("cid", id.ci)
                            parseMccMnc(mccStr(id.mccString, id.mcc), mncStr(id.mncString, id.mnc), cell)
                            dbm = info.cellSignalStrength.dbm
                        }
                        is CellInfoGsm -> {
                            val id = info.cellIdentity
                            cell.put("radio", "gsm")
                            cell.put("lac", id.lac)
                            cell.put("cid", id.cid)
                            parseMccMnc(mccStr(id.mccString, id.mcc), mncStr(id.mncString, id.mnc), cell)
                            dbm = info.cellSignalStrength.dbm
                        }
                        is CellInfoWcdma -> {
                            val id = info.cellIdentity
                            cell.put("radio", "umts")
                            cell.put("lac", id.lac)
                            cell.put("cid", id.cid)
                            parseMccMnc(mccStr(id.mccString, id.mcc), mncStr(id.mncString, id.mnc), cell)
                            dbm = info.cellSignalStrength.dbm
                        }
                        else -> {
                            if (Build.VERSION.SDK_INT >= 29 && info is CellInfoNr) {
                                val id = info.cellIdentity as android.telephony.CellIdentityNr
                                cell.put("radio", "nr")
                                cell.put("lac", id.tac)
                                cell.put("cid", id.nci)
                                parseMccMnc(id.mccString, id.mncString, cell)
                                val ss = info.cellSignalStrength
                                if (ss is CellSignalStrengthNr) dbm = ss.dbm
                            } else {
                                continue
                            }
                        }
                    }
                } catch (_: Exception) { continue }

                if (dbm != 0 && dbm != Int.MAX_VALUE) cell.put("signal", dbm)
                // Lewati sel tanpa lac/cid valid.
                val lac = cell.optInt("lac", Int.MAX_VALUE)
                val cid = cell.optLong("cid", Long.MAX_VALUE)
                if (lac == Int.MAX_VALUE || cid == Long.MAX_VALUE || cid < 0) continue
                arr.put(cell)

                if (info.isRegistered && dbm != 0 && dbm != Int.MAX_VALUE) {
                    bestDbm = dbm
                    if (cell.has("mcc")) topMcc = cell.getInt("mcc")
                    if (cell.has("mnc")) topMnc = cell.getInt("mnc")
                }
            }
        } catch (_: SecurityException) {
        } catch (_: Exception) {
        }
        return CellData(arr, bestDbm, topMcc, topMnc)
    }

    private fun mccStr(s: String?, legacy: Int): String? =
        if (!s.isNullOrEmpty()) s else if (legacy in 0..999) legacy.toString() else null

    private fun mncStr(s: String?, legacy: Int): String? =
        if (!s.isNullOrEmpty()) s else if (legacy in 0..999) legacy.toString() else null

    private fun parseMccMnc(mcc: String?, mnc: String?, cell: JSONObject) {
        mcc?.toIntOrNull()?.let { cell.put("mcc", it) }
        mnc?.toIntOrNull()?.let { cell.put("mnc", it) }
    }

    private fun fmt(v: Double): String = String.format(Locale.US, "%.4f", v)

    // ---- Notifikasi ----

    private fun buildNotification(title: String, text: String): Notification {
        if (Build.VERSION.SDK_INT >= 26) {
            val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (mgr.getNotificationChannel(CHANNEL_ID) == null) {
                mgr.createNotificationChannel(
                    NotificationChannel(CHANNEL_ID, "Agen OMNI", NotificationManager.IMPORTANCE_LOW)
                )
            }
            return Notification.Builder(this, CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setOngoing(true)
                .build()
        }
        @Suppress("DEPRECATION")
        return Notification.Builder(this)
            .setContentTitle(title)
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(title: String, text: String) {
        try {
            val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            mgr.notify(NOTIF_ID, buildNotification(title, text))
        } catch (_: Exception) {}
    }

    private fun broadcast(status: String) {
        val i = Intent(ACTION_STATUS).apply {
            setPackage(packageName)
            putExtra(EXTRA_STATUS, status)
        }
        sendBroadcast(i)
    }

    override fun onDestroy() {
        running = false
        try { locationManager.removeUpdates(this) } catch (_: Exception) {}
        worker?.interrupt()
        super.onDestroy()
    }

    companion object {
        const val ACTION_STATUS = "com.tfael.omni.agent.STATUS"
        const val EXTRA_STATUS = "status"
        private const val CHANNEL_ID = "omni_agent"
        private const val NOTIF_ID = 42
        // Fix lebih tua dari ini dianggap basi: tidak disemai & tidak dilaporkan.
        private const val STALE_FIX_MS = 120_000L  // 2 menit
    }
}
