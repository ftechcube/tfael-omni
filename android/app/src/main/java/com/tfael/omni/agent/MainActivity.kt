package com.tfael.omni.agent

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.BitmapDrawable
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.provider.Settings as AndroidSettings
import android.telephony.SmsManager
import android.util.Base64
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat
import org.json.JSONObject
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.cachemanager.CacheManager
import org.osmdroid.util.BoundingBox
import org.osmdroid.events.MapEventsReceiver
import org.osmdroid.events.MapListener
import org.osmdroid.events.ScrollEvent
import org.osmdroid.events.ZoomEvent
import org.osmdroid.views.CustomZoomButtonsController
import org.osmdroid.tileprovider.tilesource.OnlineTileSourceBase
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.util.MapTileIndex
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.MapEventsOverlay
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polygon
import org.osmdroid.views.overlay.Polyline
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Layar utama = peta taktis native (osmdroid) bergaya ATAK:
 * citra satelit, crosshair + readout koordinat/MGRS, taruh marker (tekan lama),
 * ukur jarak & bearing, gambar lingkaran, dan "team view" (seluruh armada
 * TFAEL-OMNI dari server). Pelaporan GPS berjalan otomatis di latar belakang.
 */
class MainActivity : Activity() {

    private val BG = 0xFF161512.toInt()
    private val CARD = 0xE6201D16.toInt()
    private val INK = 0xFFF1ECE0.toInt()
    private val INK_DIM = 0xFFBDB6A6.toInt()
    private val GO = 0xFF6FB06A.toInt()
    private val WAIT = 0xFFE8A93C.toInt()
    private val STOP = 0xFFD66450.toInt()
    private val TEAM = 0xFF6F9FAC.toInt()
    private val DARKINK = 0xFF14110B.toInt()

    private val cond = Typeface.create("sans-serif-condensed", Typeface.BOLD)
    private val sans = Typeface.create("sans-serif", Typeface.NORMAL)
    private val mono = Typeface.MONOSPACE

    private lateinit var prefs: android.content.SharedPreferences
    private lateinit var map: MapView
    private var agentMarker: Marker? = null
    private var follow = true
    private var satellite = true

    private val userMarkers = ArrayList<Marker>()
    private val shapes = ArrayList<Polygon>()
    private val markerAnnoId = HashMap<Marker, String>()
    private var annoColor = 0xFFF2A93B.toInt()
    private var photoAnchor: GeoPoint? = null
    private var measureLine: Polyline? = null
    private val teamMarkers = HashMap<String, Marker>()
    private val annoMarkers = HashMap<String, Marker>()
    private val annoShapes = HashMap<String, Polygon>()
    private var teamOn = false
    // Rute GPX (panduan jalur ala Coros)
    private var routeLine: Polyline? = null
    private var routeLineBase: Polyline? = null
    private val routeWpMarkers = ArrayList<Marker>()
    private var routePts: List<GeoPoint> = emptyList()
    private var routeName = ""
    private var routeLocal = false   // true = dari GPX lokal (jangan ditimpa rute server)
    private var navHud: TextView? = null
    private val handler = Handler(Looper.getMainLooper())

    private lateinit var stateDot: View
    private lateinit var stateWord: TextView
    private lateinit var telemView: TextView
    private lateinit var hud: TextView
    private lateinit var satBtn: TextView
    private lateinit var teamBtn: TextView
    private var recenter: TextView? = null

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            intent?.getStringExtra(ReporterService.EXTRA_STATUS)?.let { applyStatus(it) }
        }
    }

    private val smsPosReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != SmsReceiver.ACTION_SMS_POS) return
            val unit = intent.getStringExtra("unit") ?: "UNIT"
            val lat = intent.getStringExtra("lat")?.toDoubleOrNull() ?: return
            val lon = intent.getStringExtra("lon")?.toDoubleOrNull() ?: return
            val bat = intent.getStringExtra("bat") ?: "?"
            val fixTs = intent.getStringExtra("fix_ts")?.toLongOrNull() ?: 0L
            val nonce = intent.getStringExtra("nonce") ?: ""

            // Ikat balasan ke PING yang kita kirim: tolak balasan yang tak cocok
            // (mencegah posisi lama diputar ulang sebagai yang terkini).
            val expectNonce = prefs.getString("last_ping_nonce", "") ?: ""
            if (nonce.isNotEmpty() && expectNonce.isNotEmpty() && nonce != expectNonce) {
                setState(STOP, "Balasan SMS ditolak", "$unit: nonce tak cocok (kemungkinan replay)")
                return
            }
            // Balasan sah tiba → batalkan timeout "tidak ada balasan".
            pendingPingNonce = null
            handler.removeCallbacks(pingTimeout)

            val ageTxt = if (fixTs > 0) {
                val sec = (System.currentTimeMillis() - fixTs) / 1000
                when {
                    sec < 0 -> "baru"
                    sec < 90 -> "${sec}s lalu"
                    sec < 5400 -> "${sec / 60}m lalu"
                    else -> "${sec / 3600}j lalu"
                }
            } else "?"
            val mgrs = try { Mgrs.toMgrs(lat, lon) } catch (_: Exception) { "" }

            val gp = GeoPoint(lat, lon)
            val m = Marker(map).apply {
                setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER); icon = dotIcon(0xFFFFD166.toInt(), 20)
                title = "$unit (via SMS)"
                subDescription = "bat $bat% · fix $ageTxt" + if (mgrs.isNotEmpty()) "\nMGRS $mgrs" else ""
                position = gp
            }
            map.overlays.add(m); userMarkers.add(m); map.invalidate()
            map.controller.animateTo(gp)
            val coord = if (mgrs.isNotEmpty()) "MGRS $mgrs" else String.format("%.5f, %.5f", lat, lon)
            setState(TEAM, "Posisi via SMS ($ageTxt)", "$unit: $coord")
        }
    }

    // Status pengiriman SMS (terkirim / gagal) agar operator tahu hasil PING.
    private val smsSentReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != ACTION_SMS_SENT) return
            val to = intent.getStringExtra("to") ?: ""
            when (resultCode) {
                Activity.RESULT_OK -> setState(WAIT, "PING terkirim", "ke $to — menunggu balasan posisi")
                SmsManager.RESULT_ERROR_NO_SERVICE -> setState(STOP, "PING gagal", "tidak ada layanan seluler")
                SmsManager.RESULT_ERROR_RADIO_OFF -> setState(STOP, "PING gagal", "radio seluler mati")
                else -> setState(STOP, "PING gagal", "SMS tidak terkirim ke $to")
            }
        }
    }

    private val teamTick = object : Runnable {
        override fun run() {
            if (teamOn) { fetchTeam(); handler.postDelayed(this, 5000) }
        }
    }

    // Batas waktu balasan PING: bila 60 dtk tak ada POS, beri tahu kemungkinan sebabnya.
    private var pendingPingNonce: String? = null
    private val pingTimeout = Runnable {
        if (pendingPingNonce != null) {
            setState(STOP, "Tidak ada balasan SMS", "pulsa agent habis / di luar jangkauan / HP mati?")
            pendingPingNonce = null
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("omni_agent", Context.MODE_PRIVATE)
        val cfg = Configuration.getInstance()
        cfg.userAgentValue = packageName
        cfg.osmdroidBasePath = File(cacheDir, "osmdroid")
        cfg.osmdroidTileCache = File(cfg.osmdroidBasePath, "tiles")
        if (Build.VERSION.SDK_INT >= 21) { window.statusBarColor = BG; window.navigationBarColor = BG }
        setContentView(buildUi())
        maybeAutoStart()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun rounded(fill: Int, radius: Int, stroke: Int = 0, strokeW: Int = 0) =
        GradientDrawable().apply { setColor(fill); cornerRadius = dp(radius).toFloat(); if (strokeW > 0) setStroke(dp(strokeW), stroke) }

    private val esriImagery = object : OnlineTileSourceBase(
        "EsriWorldImagery", 0, 19, 256, "",
        arrayOf("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/")
    ) {
        override fun getTileURLString(pMapTileIndex: Long): String =
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/" +
                MapTileIndex.getZoom(pMapTileIndex) + "/" +
                MapTileIndex.getY(pMapTileIndex) + "/" +
                MapTileIndex.getX(pMapTileIndex)
    }

    private fun buildUi(): FrameLayout {
        val frame = FrameLayout(this).apply { setBackgroundColor(BG) }

        map = MapView(this).apply {
            setTileSource(esriImagery)
            setMultiTouchControls(true)
            // Matikan tombol zoom bawaan yang muncul-hilang & sering salah pencet;
            // diganti tombol +/− yang jelas di toolbar. Cubit (pinch) tetap jalan.
            zoomController.setVisibility(CustomZoomButtonsController.Visibility.NEVER)
            controller.setZoom(16.5)
            controller.setCenter(GeoPoint(-6.2088, 106.8456))
        }
        map.setOnTouchListener { _, _ -> if (follow) { follow = false; recenter?.visibility = View.VISIBLE }; false }
        // Tekan lama untuk menaruh marker di titik mana pun.
        val events = MapEventsOverlay(object : MapEventsReceiver {
            override fun singleTapConfirmedHelper(p: GeoPoint?): Boolean = false
            override fun longPressHelper(p: GeoPoint?): Boolean { if (p != null) dropMarker(p); return true }
        })
        map.overlays.add(0, events)
        map.addMapListener(object : MapListener {
            override fun onScroll(e: ScrollEvent?): Boolean { updateHud(); return false }
            override fun onZoom(e: ZoomEvent?): Boolean { updateHud(); return false }
        })
        frame.addView(map, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))

        // Crosshair tengah
        frame.addView(View(this).apply { setBackgroundColor(0x88FFFFFF.toInt()) },
            FrameLayout.LayoutParams(dp(1), dp(46), Gravity.CENTER))
        frame.addView(View(this).apply { setBackgroundColor(0x88FFFFFF.toInt()) },
            FrameLayout.LayoutParams(dp(46), dp(1), Gravity.CENTER))

        // Kartu status (atas)
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; background = rounded(CARD, 14)
            setPadding(dp(14), dp(10), dp(14), dp(11))
        }
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        stateDot = View(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(INK_DIM) }
            layoutParams = LinearLayout.LayoutParams(dp(11), dp(11)).apply { rightMargin = dp(8) }
        }
        val wb = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f) }
        stateWord = TextView(this).apply { text = "Siaga"; setTextColor(INK); textSize = 16f; typeface = cond }
        telemView = TextView(this).apply { text = "menyalakan pelaporan"; setTextColor(INK_DIM); textSize = 11.5f; typeface = mono }
        wb.addView(stateWord); wb.addView(telemView)
        val gear = toolBtn("⚙") { startActivity(Intent(this, SettingsActivity::class.java)) }
        row.addView(stateDot); row.addView(wb); row.addView(gear)
        card.addView(row)
        frame.addView(card, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            .apply { setMargins(dp(12), dp(12), dp(12), 0) })

        // Toolbar kanan
        val bar = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        satBtn = toolBtn("SAT") { toggleSatellite() }
        teamBtn = toolBtn("Tim") { toggleTeam() }
        val sosBtn = toolBtn("SOS") { confirmSos() }.apply {
            (background as? GradientDrawable)?.setColor(0xCC8A2018.toInt())
            setTextColor(0xFFFF7A68.toInt())
        }
        bar.addView(sosBtn)
        // Ping = SMS C2, butuh SIM. Redupkan tombolnya bila tak ada SIM.
        bar.addView(toolBtn("Ping") { sendPingDialog() }.apply { if (!hasSim()) alpha = 0.4f })
        bar.addView(satBtn)
        bar.addView(toolBtn("Ukur") { measureToCrosshair() })
        bar.addView(toolBtn("○") { circleAtCrosshair() })
        // ⊕ = tandai titik TEPAT di crosshair (sama dengan koordinat di pojok kiri-bawah).
        bar.addView(toolBtn("⊕") { dropMarker(GeoPoint(map.mapCenter.latitude, map.mapCenter.longitude)) })
        bar.addView(teamBtn)
        bar.addView(toolBtn("GPX") { openGpxPicker() })
        bar.addView(toolBtn("Foto") { launchPhotoMarker() })
        bar.addView(toolBtn("Unduh") { downloadOfflineArea() })
        bar.addView(toolBtn("✕") { clearDrawings() })
        // Zoom eksplisit (pengganti tombol bawaan yang membingungkan).
        bar.addView(toolBtn("+") { map.controller.zoomIn() })
        bar.addView(toolBtn("−") { map.controller.zoomOut() })
        // Bungkus toolbar agar bisa discroll — tombol tak terpotong di layar kecil.
        val barScroll = ScrollView(this).apply { isVerticalScrollBarEnabled = false; clipToPadding = false; addView(bar) }
        frame.addView(barScroll, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.END or Gravity.CENTER_VERTICAL)
            .apply { rightMargin = dp(10); topMargin = dp(84); bottomMargin = dp(84) })

        // HUD koordinat (kiri bawah) gaya ATAK
        hud = TextView(this).apply {
            setTextColor(GO); textSize = 12f; typeface = mono
            background = rounded(0xCC0E0D0A.toInt(), 8); setPadding(dp(10), dp(8), dp(10), dp(8))
            text = "—"
        }
        frame.addView(hud, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.START or Gravity.BOTTOM)
            .apply { setMargins(dp(12), 0, 0, dp(16)) })

        // HUD navigasi rute (atas-tengah) — jarak ke jalur, sisa jarak, peringatan keluar jalur.
        navHud = TextView(this).apply {
            setTextColor(0xFF00E5A8.toInt()); textSize = 12f; typeface = mono
            background = rounded(0xCC0E0D0A.toInt(), 8); setPadding(dp(12), dp(7), dp(12), dp(7))
            visibility = View.GONE; gravity = Gravity.CENTER
        }
        frame.addView(navHud, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER_HORIZONTAL or Gravity.TOP)
            .apply { setMargins(dp(12), dp(84), dp(12), 0) })

        // Pusatkan ulang
        recenter = toolBtn("◎") { follow = true; recenter?.visibility = View.GONE; agentMarker?.position?.let { map.controller.animateTo(it) } }
        frame.addView(recenter!!, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.END or Gravity.BOTTOM)
            .apply { setMargins(0, 0, dp(12), dp(16)) })

        paintSatBtn(); paintTeamBtn()
        return frame
    }

    private fun toolBtn(label: String, onClick: () -> Unit): TextView = TextView(this).apply {
        text = label; setTextColor(INK); textSize = 14f; typeface = cond; gravity = Gravity.CENTER
        background = rounded(0xCC201D16.toInt(), 12, 0x33FFFFFF, 1)
        setPadding(dp(12), dp(10), dp(12), dp(10)); isClickable = true
        setOnClickListener { onClick() }
        layoutParams = LinearLayout.LayoutParams(dp(54), ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) }
    }

    // ── Peta ──
    private fun toggleSatellite() {
        satellite = !satellite
        map.setTileSource(if (satellite) esriImagery else TileSourceFactory.MAPNIK)
        paintSatBtn()
    }
    private fun paintSatBtn() {
        satBtn.text = if (satellite) "SAT" else "Peta"
        (satBtn.background as? GradientDrawable)?.setColor(if (satellite) 0xCC2A4030.toInt() else 0xCC201D16.toInt())
    }

    private fun dotIcon(color: Int, sizeDp: Int = 22): BitmapDrawable {
        val s = dp(sizeDp); val bmp = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888)
        val cv = Canvas(bmp); val p = Paint(Paint.ANTI_ALIAS_FLAG)
        p.color = Color.WHITE; cv.drawCircle(s / 2f, s / 2f, s / 2f, p)
        p.color = color; cv.drawCircle(s / 2f, s / 2f, s / 2f - dp(3), p)
        return BitmapDrawable(resources, bmp)
    }

    private fun moveAgent(lat: Double, lon: Double) {
        val gp = GeoPoint(lat, lon)
        if (agentMarker == null) {
            val m = Marker(map).apply { setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER); title = prefs.getString("unit", "Saya") }
            agentMarker = m
            map.overlays.add(m)
        }
        agentMarker!!.icon = dotIcon(GO)
        agentMarker!!.position = gp
        map.invalidate()
        if (follow) map.controller.animateTo(gp)
        updateNav()  // perbarui panduan rute dari posisi terbaru
    }

    // Tekan lama -> dialog: beri nama, pilih warna, radius (0 = marker, >0 = lingkaran).
    private fun dropMarker(p: GeoPoint) {
        annoColor = 0xFFF2A93B.toInt()
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(12), dp(18), 0) }
        val nameField = EditText(this).apply { hint = "Nama (mis. Target, Bahaya, Titik kumpul)" }
        box.addView(nameField)
        box.addView(TextView(this).apply { text = "Warna"; setPadding(0, dp(12), 0, dp(4)) })
        val swatchRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val palette = listOf(0xFFF2A93B.toInt(), 0xFFD66450.toInt(), 0xFF6FB06A.toInt(), 0xFF00E5FF.toInt(), 0xFFFFFFFF.toInt())
        val swatches = ArrayList<View>()
        palette.forEach { c ->
            val sw = View(this).apply {
                background = GradientDrawable().apply { setColor(c); cornerRadius = dp(6).toFloat() }
                layoutParams = LinearLayout.LayoutParams(dp(36), dp(36)).apply { rightMargin = dp(10) }
                isClickable = true
                setOnClickListener {
                    annoColor = c
                    swatches.forEach { s -> (s.background as GradientDrawable).setStroke(0, 0) }
                    (background as GradientDrawable).setStroke(dp(3), 0xFF000000.toInt())
                }
            }
            swatches.add(sw); swatchRow.addView(sw)
        }
        box.addView(swatchRow)
        box.addView(TextView(this).apply { text = "Radius lingkaran (meter) — kosong = marker"; setPadding(0, dp(14), 0, dp(4)) })
        val radiusField = EditText(this).apply { hint = "0"; inputType = InputType.TYPE_CLASS_NUMBER }
        box.addView(radiusField)

        AlertDialog.Builder(this)
            .setTitle("Tandai titik")
            .setView(box)
            .setPositiveButton("Simpan") { _, _ ->
                val name = nameField.text.toString().trim()
                val radius = radiusField.text.toString().trim().toDoubleOrNull() ?: 0.0
                val hex = String.format("#%06X", 0xFFFFFF and annoColor)
                if (radius > 0) {
                    val poly = Polygon(map).apply {
                        points = Polygon.pointsAsCircle(p, radius)
                        fillPaint.color = (0x33000000 or (0xFFFFFF and annoColor))
                        outlinePaint.color = annoColor; outlinePaint.strokeWidth = dp(2).toFloat()
                    }
                    map.overlays.add(poly); shapes.add(poly); map.invalidate()
                    postAnnotation("circle", p.latitude, p.longitude, radius, name, hex)
                } else {
                    val m = Marker(map).apply {
                        // Titik-tumpu di TENGAH agar titik tepat di koordinat, bukan tergeser ke atas.
                        setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER); icon = dotIcon(annoColor, 18)
                        title = name.ifEmpty { String.format("%.5f, %.5f", p.latitude, p.longitude) }
                        subDescription = Mgrs.toMgrs(p.latitude, p.longitude); position = p
                    }
                    map.overlays.add(m); userMarkers.add(m); map.invalidate()
                    m.setOnMarkerClickListener { mk, _ -> promptDeleteMarker(mk); true }
                    postAnnotation("marker", p.latitude, p.longitude, 0.0, name, hex) { annoId -> markerAnnoId[m] = annoId }
                }
            }
            .setNegativeButton("Batal", null)
            .show()
    }

    private fun promptDeleteMarker(m: Marker) {
        val annoId = markerAnnoId[m]
        AlertDialog.Builder(this)
            .setTitle("Hapus marker?")
            .setMessage(m.title ?: "")
            .setPositiveButton("Hapus") { _, _ ->
                map.overlays.remove(m); userMarkers.remove(m); markerAnnoId.remove(m); map.invalidate()
                if (annoId != null) postDeleteAnnotation(annoId)
            }
            .setNegativeButton("Batal", null)
            .show()
    }

    private fun postDeleteAnnotation(annoId: String) {
        val server = (prefs.getString("server", "") ?: "").trimEnd('/'); if (server.isEmpty()) return
        val key = prefs.getString("agent_key", "") ?: ""
        val unit = prefs.getString("unit", "agen") ?: "agen"
        Thread {
            try {
                val json = JSONObject().apply { put("anno_id", annoId); put("created_by", unit); if (key.isNotEmpty()) put("agent_key", key) }
                val conn = URL("$server/api/v2/annotations/delete").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"; conn.doOutput = true; conn.connectTimeout = 6000; conn.readTimeout = 6000
                conn.setRequestProperty("Content-Type", "application/json")
                if (key.isNotEmpty()) conn.setRequestProperty("X-Agent-Key", key)
                conn.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
                conn.responseCode; conn.disconnect()
            } catch (_: Exception) {}
        }.start()
    }

    private fun circleAtCrosshair() {
        val c = map.mapCenter
        val poly = Polygon(map).apply {
            points = Polygon.pointsAsCircle(GeoPoint(c.latitude, c.longitude), 250.0)
            fillPaint.color = 0x33E8A93C.toInt()
            outlinePaint.color = WAIT
            outlinePaint.strokeWidth = dp(2).toFloat()
        }
        map.overlays.add(poly); shapes.add(poly); map.invalidate()
        postAnnotation("circle", c.latitude, c.longitude, 250.0, "")  // bagikan ke admin & agen lain
    }

    private fun measureToCrosshair() {
        val from = agentMarker?.position
        if (from == null) { hud.text = "Ukur: menunggu posisi GPS Anda"; return }
        val c = map.mapCenter
        val to = GeoPoint(c.latitude, c.longitude)
        measureLine?.let { map.overlays.remove(it) }
        val pl = Polyline(map).apply {
            setPoints(listOf(from, to)); outlinePaint.color = 0xFF00E5FF.toInt(); outlinePaint.strokeWidth = dp(2).toFloat()
        }
        measureLine = pl
        map.overlays.add(pl); map.invalidate()
        val dist = from.distanceToAsDouble(to)
        val brg = ((from.bearingTo(to) % 360) + 360) % 360
        val ds = if (dist >= 1000) String.format("%.2f km", dist / 1000) else String.format("%.0f m", dist)
        hud.text = "Ukur  $ds   bearing ${Math.round(brg)}°"
    }

    private fun clearDrawings() {
        userMarkers.forEach { map.overlays.remove(it) }; userMarkers.clear()
        shapes.forEach { map.overlays.remove(it) }; shapes.clear()
        measureLine?.let { map.overlays.remove(it) }; measureLine = null
        map.invalidate(); updateHud()
        postClear()  // hapus juga anotasi milik Anda dari server (hilang di admin & agen lain)
    }

    // Unduh ubin area yang terlihat ke cache agar peta tetap jalan tanpa internet.
    private fun downloadOfflineArea() {
        val bb: BoundingBox = map.boundingBox
        val zMin = map.zoomLevelDouble.toInt()
        val zMax = minOf(zMin + 2, 18)
        AlertDialog.Builder(this)
            .setTitle("Unduh peta offline")
            .setMessage("Simpan area yang terlihat (zoom $zMin–$zMax) agar bisa dipakai tanpa internet?")
            .setPositiveButton("Unduh") { _, _ ->
                try {
                    CacheManager(map).downloadAreaAsync(this, bb, zMin, zMax, object : CacheManager.CacheManagerCallback {
                        override fun onTaskComplete() {
                            setState(if (isRunning()) GO else 0, if (isRunning()) "Mengirim" else "Siaga", "peta offline tersimpan")
                        }
                        override fun onTaskFailed(errors: Int) { setState(STOP, "Unduh peta gagal", "$errors ubin gagal") }
                        override fun updateProgress(progress: Int, currentZoomLevel: Int, zoomMin: Int, zoomMax: Int) {
                            setState(WAIT, "Mengunduh peta", "$progress% (zoom $currentZoomLevel)")
                        }
                        override fun downloadStarted() {}
                        override fun setPossibleTilesInArea(total: Int) {}
                    })
                } catch (e: Exception) { setState(STOP, "Unduh gagal", e.message ?: "galat") }
            }
            .setNegativeButton("Batal", null)
            .show()
    }

    private fun postClear() {
        val server = (prefs.getString("server", "") ?: "").trimEnd('/')
        if (server.isEmpty()) return
        val key = prefs.getString("agent_key", "") ?: ""
        val unit = prefs.getString("unit", "agen") ?: "agen"
        Thread {
            try {
                val json = JSONObject().apply { put("created_by", unit); if (key.isNotEmpty()) put("agent_key", key) }
                val conn = URL("$server/api/v2/annotations/clear").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"; conn.connectTimeout = 6000; conn.readTimeout = 6000; conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                if (key.isNotEmpty()) conn.setRequestProperty("X-Agent-Key", key)
                conn.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
                conn.responseCode; conn.disconnect()
            } catch (_: Exception) {}
        }.start()
    }

    private fun updateHud() {
        val c = map.mapCenter
        val ll = String.format("%.5f, %.5f", c.latitude, c.longitude)
        hud.text = "$ll\n${Mgrs.toMgrs(c.latitude, c.longitude)}"
        updateNav()
    }

    // ── Rute GPX: gambar jalur + start/finish + waypoint, lalu hitung panduan navigasi ──
    private fun drawRoute(pts: List<GeoPoint>, waypoints: List<Pair<GeoPoint, String>>, name: String) {
        routeLineBase?.let { map.overlays.remove(it) }
        routeLine?.let { map.overlays.remove(it) }
        routeWpMarkers.forEach { map.overlays.remove(it) }; routeWpMarkers.clear()
        routePts = pts; routeName = name
        routeLineBase = null; routeLine = null
        if (pts.size >= 2) {
            val base = Polyline(map).apply { setPoints(pts); outlinePaint.color = 0xB30B1F14.toInt(); outlinePaint.strokeWidth = dp(7).toFloat() }
            val top = Polyline(map).apply { setPoints(pts); outlinePaint.color = 0xFF00E5A8.toInt(); outlinePaint.strokeWidth = dp(3).toFloat() }
            routeLineBase = base; routeLine = top
            map.overlays.add(base); map.overlays.add(top)
            listOf(pts.first() to 0xFF16A34A.toInt() to "Start", pts.last() to 0xFFDC2626.toInt() to "Finish").forEach { (gc, t) ->
                val m = Marker(map).apply { setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER); icon = dotIcon(gc.second, 16); title = t; position = gc.first }
                map.overlays.add(m); routeWpMarkers.add(m)
            }
            waypoints.forEach { (gp, nm) ->
                val m = Marker(map).apply { setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER); icon = dotIcon(0xFF00E5A8.toInt(), 14); title = nm.ifEmpty { "WP" }; position = gp }
                map.overlays.add(m); routeWpMarkers.add(m)
            }
        }
        map.invalidate(); updateNav()
    }

    private fun metersBetween(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val r = 6371000.0; val toR = Math.PI / 180
        val dLat = (lat2 - lat1) * toR; val dLon = (lon2 - lon1) * toR
        val a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(lat1 * toR) * Math.cos(lat2 * toR) * Math.sin(dLon / 2) * Math.sin(dLon / 2)
        return 2 * r * Math.asin(Math.sqrt(a))
    }

    /** @return jarak melintang ke rute (m) + sisa jarak ke finish (km). */
    private fun routeNav(lat: Double, lon: Double, pts: List<GeoPoint>): Pair<Double, Double> {
        val r = 6371000.0; val toR = Math.PI / 180; val refLat = lat * toR
        fun x(pl: Double, po: Double) = doubleArrayOf((po - lon) * toR * r * Math.cos(refLat), (pl - lat) * toR * r)
        var bestD = Double.MAX_VALUE; var bestSeg = 0; var bestT = 0.0
        for (i in 0 until pts.size - 1) {
            val a = x(pts[i].latitude, pts[i].longitude); val b = x(pts[i + 1].latitude, pts[i + 1].longitude)
            val abx = b[0] - a[0]; val aby = b[1] - a[1]
            val ab2 = (abx * abx + aby * aby).coerceAtLeast(1e-9)
            val t = (-(a[0] * abx + a[1] * aby) / ab2).coerceIn(0.0, 1.0)
            val d = Math.hypot(a[0] + t * abx, a[1] + t * aby)
            if (d < bestD) { bestD = d; bestSeg = i; bestT = t }
        }
        var rem = metersBetween(pts[bestSeg].latitude, pts[bestSeg].longitude, pts[bestSeg + 1].latitude, pts[bestSeg + 1].longitude) * (1 - bestT)
        for (i in bestSeg + 1 until pts.size - 1) rem += metersBetween(pts[i].latitude, pts[i].longitude, pts[i + 1].latitude, pts[i + 1].longitude)
        return Pair(bestD, rem / 1000.0)
    }

    private fun updateNav() {
        val nh = navHud ?: return
        val pos = agentMarker?.position
        if (routePts.size < 2 || pos == null) { nh.visibility = View.GONE; return }
        val (crossM, remKm) = routeNav(pos.latitude, pos.longitude, routePts)
        val off = crossM > 30
        nh.visibility = View.VISIBLE
        nh.text = (if (off) "⚠ KELUAR JALUR" else "DI JALUR") +
                " · ${crossM.toInt()} m dari rute · sisa ${String.format("%.2f", remKm)} km · $routeName"
        nh.setTextColor(if (off) 0xFFF59E0B.toInt() else 0xFF00E5A8.toInt())
    }

    // ── Impor GPX lokal (offline, tanpa server) ──
    private fun openGpxPicker() {
        try {
            val i = Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type = "*/*" }
            startActivityForResult(i, REQ_GPX)
        } catch (e: Exception) { setState(STOP, "Tak bisa buka berkas", e.message ?: "galat") }
    }

    private fun loadGpxFromUri(uri: Uri) {
        try {
            val xml = contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } ?: return
            val (pts, wpts, name) = parseGpx(xml)
            if (pts.size < 2) { setState(STOP, "GPX kosong", "tak ada jalur (butuh >=2 titik)"); return }
            routeLocal = true
            drawRoute(pts, wpts, name)
            map.controller.animateTo(pts.first())
            setState(TEAM, "Rute dimuat", "$name · ${pts.size} titik")
        } catch (e: Exception) { setState(STOP, "GPX gagal", e.message ?: "galat") }
    }

    private fun gpxAttr(tag: String, attr: String): Double? =
        Regex("$attr\\s*=\\s*\"([-0-9.]+)\"").find(tag)?.groupValues?.get(1)?.toDoubleOrNull()

    private fun parseGpx(xml: String): Triple<List<GeoPoint>, List<Pair<GeoPoint, String>>, String> {
        val trk = ArrayList<GeoPoint>(); val rte = ArrayList<GeoPoint>(); val wpts = ArrayList<Pair<GeoPoint, String>>()
        Regex("<(trkpt|rtept|wpt)\\b[^>]*>", RegexOption.IGNORE_CASE).findAll(xml).forEach { m ->
            val la = gpxAttr(m.value, "lat"); val lo = gpxAttr(m.value, "lon")
            if (la != null && lo != null && la in -90.0..90.0 && lo in -180.0..180.0) {
                when (m.groupValues[1].lowercase()) {
                    "trkpt" -> trk.add(GeoPoint(la, lo))
                    "rtept" -> rte.add(GeoPoint(la, lo))
                    "wpt" -> {
                        val nm = Regex("<name>(.*?)</name>", RegexOption.IGNORE_CASE)
                            .find(xml.substring(m.range.last).take(400))?.groupValues?.get(1)?.trim() ?: ""
                        wpts.add(GeoPoint(la, lo) to nm)
                    }
                }
            }
        }
        val name = Regex("<name>(.*?)</name>", RegexOption.IGNORE_CASE).find(xml)?.groupValues?.get(1)?.trim() ?: "GPX"
        return Triple(if (trk.isNotEmpty()) trk else rte, wpts, name)
    }

    // ── Team view: armada dari server ──
    private fun toggleTeam() {
        teamOn = !teamOn; paintTeamBtn()
        if (teamOn) { handler.post(teamTick) } else {
            handler.removeCallbacks(teamTick)
            teamMarkers.values.forEach { map.overlays.remove(it) }; teamMarkers.clear()
            annoMarkers.values.forEach { map.overlays.remove(it) }; annoMarkers.clear()
            annoShapes.values.forEach { map.overlays.remove(it) }; annoShapes.clear()
            if (!routeLocal) drawRoute(emptyList(), emptyList(), "")  // rute server ikut mati; GPX lokal tetap
            map.invalidate()
        }
    }
    private fun paintTeamBtn() {
        (teamBtn.background as? GradientDrawable)?.setColor(if (teamOn) 0xCC24404A.toInt() else 0xCC201D16.toInt())
    }

    private fun fetchTeam() {
        val server = (prefs.getString("server", "") ?: "").trimEnd('/')
        val self = prefs.getString("unit", "") ?: ""
        if (server.isEmpty()) return
        Thread {
            try {
                val conn = URL("$server/api/v2/overview").openConnection() as HttpURLConnection
                conn.connectTimeout = 6000; conn.readTimeout = 6000
                val body = conn.inputStream.bufferedReader().readText(); conn.disconnect()
                val obj = JSONObject(body)
                val units = obj.optJSONArray("units")
                val annos = obj.optJSONArray("annotations")
                val parsedUnits = ArrayList<Triple<String, Double, Double>>()
                if (units != null) for (i in 0 until units.length()) {
                    val u = units.optJSONObject(i) ?: continue
                    val id = u.optString("unit_id"); if (id == self) continue
                    parsedUnits.add(Triple(id, u.optDouble("lat"), u.optDouble("lon")))
                }
                val parsedAnnos = ArrayList<JSONObject>()
                if (annos != null) for (i in 0 until annos.length()) {
                    val a = annos.optJSONObject(i) ?: continue
                    if (a.optString("created_by") == self) continue  // punya sendiri sudah tampil lokal
                    parsedAnnos.add(a)
                }
                // Rute aktif dari server (komandan).
                var srvPts: List<GeoPoint>? = null
                var srvWps: List<Pair<GeoPoint, String>> = emptyList()
                var srvName = ""
                val ar = obj.optJSONObject("active_route")
                if (ar != null) {
                    val pj = ar.optJSONArray("points")
                    if (pj != null && pj.length() >= 2) {
                        val lst = ArrayList<GeoPoint>(pj.length())
                        for (i in 0 until pj.length()) {
                            val p = pj.optJSONArray(i) ?: continue
                            lst.add(GeoPoint(p.optDouble(0), p.optDouble(1)))
                        }
                        srvPts = lst
                        srvName = ar.optString("name", "Rute")
                        val wj = ar.optJSONArray("waypoints")
                        if (wj != null) {
                            val wl = ArrayList<Pair<GeoPoint, String>>()
                            for (i in 0 until wj.length()) {
                                val w = wj.optJSONObject(i) ?: continue
                                wl.add(GeoPoint(w.optDouble("lat"), w.optDouble("lon")) to w.optString("name"))
                            }
                            srvWps = wl
                        }
                    }
                }
                handler.post {
                    parsedUnits.forEach { (id, lat, lon) ->
                        val gp = GeoPoint(lat, lon)
                        val m = teamMarkers[id]
                        if (m == null) {
                            val nm = Marker(map).apply { setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER); icon = dotIcon(TEAM, 18); title = id; position = gp }
                            map.overlays.add(nm); teamMarkers[id] = nm
                        } else m.position = gp
                    }
                    val seen = HashSet<String>()
                    parsedAnnos.forEach { a ->
                        val id = a.optString("anno_id"); seen.add(id)
                        val lat = a.optDouble("lat"); val lon = a.optDouble("lon")
                        val by = a.optString("created_by")
                        val col = try {
                            val cs = a.optString("color"); if (cs.startsWith("#")) android.graphics.Color.parseColor(cs) else TEAM
                        } catch (_: Exception) { TEAM }
                        if (a.optString("kind") == "circle" && a.optDouble("radius_m") > 0) {
                            if (!annoShapes.containsKey(id)) {
                                val poly = Polygon(map).apply {
                                    points = Polygon.pointsAsCircle(GeoPoint(lat, lon), a.optDouble("radius_m"))
                                    fillPaint.color = (0x33000000 or (0xFFFFFF and col)); outlinePaint.color = col; outlinePaint.strokeWidth = dp(2).toFloat()
                                    title = "oleh $by"
                                }
                                map.overlays.add(poly); annoShapes[id] = poly
                            }
                        } else if (!annoMarkers.containsKey(id)) {
                            val nm = Marker(map).apply {
                                setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM); icon = dotIcon(col, 16)
                                title = a.optString("label").ifEmpty { "Marker" }; subDescription = "oleh $by"; position = GeoPoint(lat, lon)
                            }
                            map.overlays.add(nm); annoMarkers[id] = nm
                        }
                    }
                    annoMarkers.keys.toList().forEach { if (it !in seen) annoMarkers.remove(it)?.let { ov -> map.overlays.remove(ov) } }
                    annoShapes.keys.toList().forEach { if (it !in seen) annoShapes.remove(it)?.let { ov -> map.overlays.remove(ov) } }
                    // Rute server digambar bila kita tak sedang pakai GPX lokal.
                    if (!routeLocal) {
                        if (srvPts != null) drawRoute(srvPts!!, srvWps, srvName)
                        else if (routePts.isNotEmpty()) drawRoute(emptyList(), emptyList(), "")
                    }
                    map.invalidate()
                }
            } catch (_: Exception) {}
        }.start()
    }

    private fun postAnnotation(kind: String, lat: Double, lon: Double, radiusM: Double, label: String,
                               color: String = "", photo: String = "", onId: ((String) -> Unit)? = null) {
        val server = (prefs.getString("server", "") ?: "").trimEnd('/')
        if (server.isEmpty()) return
        val key = prefs.getString("agent_key", "") ?: ""
        val unit = prefs.getString("unit", "agen") ?: "agen"
        Thread {
            try {
                val json = JSONObject().apply {
                    put("kind", kind); put("lat", lat); put("lon", lon)
                    put("radius_m", radiusM); put("label", label); put("color", color); put("created_by", unit)
                    if (photo.isNotEmpty()) put("photo", photo)
                    if (key.isNotEmpty()) put("agent_key", key)
                }
                val conn = URL("$server/api/v2/annotations/add").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"; conn.connectTimeout = 6000; conn.readTimeout = 6000; conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                if (key.isNotEmpty()) conn.setRequestProperty("X-Agent-Key", key)
                conn.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
                val resp = conn.inputStream.bufferedReader().readText(); conn.disconnect()
                val annoId = JSONObject(resp).optString("anno_id")
                if (annoId.isNotEmpty() && onId != null) handler.post { onId(annoId) }
            } catch (_: Exception) {}
        }.start()
    }

    private fun confirmSos() {
        AlertDialog.Builder(this)
            .setTitle("Kirim SOS?")
            .setMessage("Sinyal darurat beserta posisi Anda dikirim ke pusat komando.")
            .setPositiveButton("Kirim SOS") { _, _ -> postSos() }
            .setNegativeButton("Batal", null)
            .show()
    }

    private fun postSos() {
        val server = (prefs.getString("server", "") ?: "").trimEnd('/')
        if (server.isEmpty()) { setState(STOP, "SOS gagal", "server belum diatur"); return }
        val key = prefs.getString("agent_key", "") ?: ""
        val unit = prefs.getString("unit", "ALPHA-01") ?: "ALPHA-01"
        val role = prefs.getString("role", "Unit") ?: "Unit"
        val pos = agentMarker?.position ?: GeoPoint(map.mapCenter.latitude, map.mapCenter.longitude)
        Thread {
            try {
                val json = JSONObject().apply {
                    put("unit_id", unit); put("name", role); put("role", role)
                    put("lat", pos.latitude); put("lon", pos.longitude)
                    put("is_sos", true); put("battery_pct", 50)
                    if (key.isNotEmpty()) put("agent_key", key)
                }
                val conn = URL("$server/api/v2/telemetry/live-device").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"; conn.doOutput = true; conn.connectTimeout = 6000; conn.readTimeout = 6000
                conn.setRequestProperty("Content-Type", "application/json")
                if (key.isNotEmpty()) conn.setRequestProperty("X-Agent-Key", key)
                conn.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode; conn.disconnect()
                handler.post {
                    if (code in 200..299) setState(STOP, "SOS TERKIRIM", "sinyal darurat sampai ke komando")
                    else setState(STOP, "SOS gagal", "server menolak (HTTP $code)")
                }
            } catch (_: Exception) { handler.post { setState(STOP, "SOS gagal", "server tak terjangkau") } }
        }.start()
    }

    // ── Pelaporan ──
    private fun maybeAutoStart() {
        val server = (prefs.getString("server", "") ?: "").trim()
        if (server.isEmpty()) { setState(0, "Belum diatur", "buka ⚙ dan isi alamat server"); return }
        if (prefs.getBoolean("auto", true) || isRunning()) { if (hasPerms()) startReporting() else requestPerms() }
        else setState(if (isRunning()) GO else 0, if (isRunning()) "Mengirim" else "Jeda", "lapor dijeda")
    }
    private fun isRunning(): Boolean = prefs.getBoolean("running", false)
    private fun startReporting() {
        ContextCompat.startForegroundService(this, Intent(this, ReporterService::class.java))
        prefs.edit().putBoolean("running", true).apply()
        setState(WAIT, "Mencari lokasi", "memulai pelaporan"); promptBattery()
    }
    private fun stopReporting() {
        stopService(Intent(this, ReporterService::class.java)); prefs.edit().putBoolean("running", false).apply()
        setState(0, "Jeda", "pelaporan dihentikan")
    }

    private fun setState(color: Int, word: String, sub: String) {
        val c = if (color == 0) INK_DIM else color
        (stateDot.background as? GradientDrawable)?.setColor(c)
        stateWord.text = word; telemView.text = sub
    }

    private fun applyStatus(msg: String) {
        when {
            msg.startsWith("OK") -> {
                val parts = msg.split(" · ")
                val coord = parts.getOrNull(1).orEmpty()
                val bat = Regex("bat (\\d+)%").find(msg)?.groupValues?.get(1)?.let { "bat $it%" } ?: ""
                val sig = Regex("(-?\\d+) dBm").find(msg)?.groupValues?.get(1)?.let { "$it dBm" } ?: ""
                setState(GO, "Mengirim", listOf(bat, sig).filter { it.isNotEmpty() }.joinToString("  "))
                val ll = coord.split(",")
                val lat = ll.getOrNull(0)?.trim()?.toDoubleOrNull()
                val lon = ll.getOrNull(1)?.trim()?.toDoubleOrNull()
                if (lat != null && lon != null) moveAgent(lat, lon)
            }
            msg.startsWith("SMS:") -> setState(if (msg.contains("DITOLAK") || msg.contains("gagal")) STOP else TEAM, "C2 SMS", msg.removePrefix("SMS:").trim())
            msg.contains("Menunggu") || msg.contains("Memulai") -> setState(WAIT, "Mencari lokasi", msg.replace("...", "").trim())
            msg.startsWith("Galat") || msg.contains("menolak") || msg.contains("kosong") -> setState(STOP, "Galat", msg.removePrefix("Galat:").trim())
        }
    }

    // Tombol Foto: ambil foto lewat kamera, buat marker berfoto di crosshair, kirim ke server.
    private fun launchPhotoMarker() {
        val c = map.mapCenter
        photoAnchor = GeoPoint(c.latitude, c.longitude)
        try {
            val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            if (intent.resolveActivity(packageManager) != null) startActivityForResult(intent, REQ_PHOTO)
            else setState(STOP, "Kamera tak tersedia", "")
        } catch (e: Exception) { setState(STOP, "Kamera gagal", e.message ?: "galat") }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_GPX && resultCode == Activity.RESULT_OK) {
            data?.data?.let { loadGpxFromUri(it) }
            return
        }
        if (requestCode != REQ_PHOTO || resultCode != Activity.RESULT_OK) return
        val bmp = data?.extras?.get("data") as? Bitmap
            ?: run { setState(STOP, "Foto gagal", "tidak ada gambar"); return }
        val anchor = photoAnchor ?: GeoPoint(map.mapCenter.latitude, map.mapCenter.longitude)
        val scaled = if (bmp.width > 480) Bitmap.createScaledBitmap(bmp, 480, bmp.height * 480 / bmp.width, true) else bmp
        val baos = java.io.ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 60, baos)
        val b64 = "data:image/jpeg;base64," + Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)
        val m = Marker(map).apply {
            setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM); icon = dotIcon(0xFF00E5FF.toInt(), 18)
            title = "Foto"; subDescription = Mgrs.toMgrs(anchor.latitude, anchor.longitude); position = anchor
        }
        map.overlays.add(m); userMarkers.add(m); map.invalidate()
        m.setOnMarkerClickListener { mk, _ -> promptDeleteMarker(mk); true }
        postAnnotation("marker", anchor.latitude, anchor.longitude, 0.0, "Foto", "#00E5FF", b64) { annoId -> markerAnnoId[m] = annoId }
        setState(if (isRunning()) GO else 0, if (isRunning()) "Mengirim" else "Siaga", "foto marker dibuat & dikirim")
    }

    private fun hasPerms(): Boolean {
        val ok = { p: String -> ContextCompat.checkSelfPermission(this, p) == PackageManager.PERMISSION_GRANTED }
        return ok(Manifest.permission.ACCESS_FINE_LOCATION) && ok(Manifest.permission.READ_PHONE_STATE)
    }
    private fun requestPerms() {
        val needed = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.READ_PHONE_STATE)
        if (Build.VERSION.SDK_INT >= 33) needed.add(Manifest.permission.POST_NOTIFICATIONS)
        requestPermissions(needed.toTypedArray(), REQ_PERMS)
    }
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_PERMS) {
            if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
                if (Build.VERSION.SDK_INT >= 29 &&
                    ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) != PackageManager.PERMISSION_GRANTED
                ) { try { requestPermissions(arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION), REQ_BG) } catch (_: Exception) {} }
                startReporting()
            } else setState(STOP, "Galat", "izin lokasi atau telepon ditolak")
        }
    }

    private fun promptBattery() {
        if (Build.VERSION.SDK_INT < 23 || prefs.getBoolean("batt_asked", false)) return
        prefs.edit().putBoolean("batt_asked", true).apply()
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as android.os.PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName))
                startActivity(Intent(AndroidSettings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
        } catch (_: Exception) {}
    }

    override fun onResume() {
        super.onResume(); map.onResume()
        ContextCompat.registerReceiver(this, statusReceiver, IntentFilter(ReporterService.ACTION_STATUS), ContextCompat.RECEIVER_NOT_EXPORTED)
        ContextCompat.registerReceiver(this, smsPosReceiver, IntentFilter(SmsReceiver.ACTION_SMS_POS), ContextCompat.RECEIVER_NOT_EXPORTED)
        ContextCompat.registerReceiver(this, smsSentReceiver, IntentFilter(ACTION_SMS_SENT), ContextCompat.RECEIVER_NOT_EXPORTED)
        if (!isRunning()) maybeAutoStart()
        if (teamOn) handler.post(teamTick)
    }
    override fun onPause() {
        super.onPause(); map.onPause(); handler.removeCallbacks(teamTick); handler.removeCallbacks(pingTimeout)
        try { unregisterReceiver(statusReceiver) } catch (_: Exception) {}
        try { unregisterReceiver(smsPosReceiver) } catch (_: Exception) {}
        try { unregisterReceiver(smsSentReceiver) } catch (_: Exception) {}
    }

    // ── C2 via SMS (gratis, antar-HP ber-SIM) ──
    private fun hasSim(): Boolean = try {
        val tm = getSystemService(TELEPHONY_SERVICE) as android.telephony.TelephonyManager
        tm.simState == android.telephony.TelephonyManager.SIM_STATE_READY
    } catch (_: Exception) { false }

    private fun sendPingDialog() {
        if (!hasSim()) {
            setState(STOP, "Tidak ada kartu SIM", "SMS C2 (Ping) butuh SIM aktif. Pakai jalur WiFi/radio untuk lapor posisi.")
            return
        }
        if (!ensureSmsPerms()) return
        val field = EditText(this).apply { hint = "Nomor HP unit tujuan (mis. 0812...)"; inputType = InputType.TYPE_CLASS_PHONE }
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(8), dp(18), 0); addView(field) }
        AlertDialog.Builder(this)
            .setTitle("Minta posisi via SMS (terenkripsi)")
            .setView(box)
            .setPositiveButton("Kirim PING") { _, _ ->
                val num = field.text.toString().trim()
                if (num.isNotEmpty()) sendPing(num)
            }
            .setNegativeButton("Batal", null)
            .show()
    }

    private fun sendPing(number: String) {
        val key = prefs.getString("agent_key", "") ?: ""
        val nonce = System.currentTimeMillis().toString()
        val mac = Crypto.hmac(key, "PING $nonce").substring(0, 16)
        // Simpan nonce agar balasan POS bisa diikat ke PING ini (anti-replay sisi pengirim).
        prefs.edit().putString("last_ping_nonce", nonce).putString("last_ping_to", number).apply()
        try {
            // PendingIntent status-kirim: operator tahu terkirim/gagal, bukan sekadar "menunggu".
            val sentIntent = Intent(ACTION_SMS_SENT).setPackage(packageName).putExtra("to", number)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            val pi = PendingIntent.getBroadcast(this, nonce.hashCode(), sentIntent, flags)
            smsManager().sendTextMessage(number, null, "OMNI1 PING $nonce $mac", pi, null)
            setState(WAIT, "PING dikirim…", "ke $number")
            // Pasang batas waktu 60 dtk: kalau tak ada balasan, beri tahu kemungkinan sebab.
            pendingPingNonce = nonce
            handler.removeCallbacks(pingTimeout)
            handler.postDelayed(pingTimeout, 60000)
        } catch (e: Exception) { setState(STOP, "PING gagal", e.message ?: "galat") }
    }

    private fun smsManager(): SmsManager =
        if (Build.VERSION.SDK_INT >= 31) getSystemService(SmsManager::class.java)!! else SmsManager.getDefault()

    private fun ensureSmsPerms(): Boolean {
        val need = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.SEND_SMS)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECEIVE_SMS) != PackageManager.PERMISSION_GRANTED) need.add(Manifest.permission.RECEIVE_SMS)
        if (need.isEmpty()) return true
        requestPermissions(need.toTypedArray(), REQ_SMS)
        setState(WAIT, "Izin SMS", "beri izin SMS, lalu tekan Ping lagi")
        return false
    }

    companion object {
        const val KEY_SERVER = "server"; const val KEY_UNIT = "unit"; const val KEY_ROLE = "role"
        const val KEY_AGENTKEY = "agent_key"; const val KEY_INTERVAL = "interval"
        const val KEY_RUNNING = "running"; const val KEY_AUTO = "auto"; const val KEY_GATEWAY = "gateway_mode"
        private const val REQ_PERMS = 101; private const val REQ_BG = 102; private const val REQ_PHOTO = 103; private const val REQ_SMS = 104; private const val REQ_GPX = 105
        const val ACTION_SMS_SENT = "com.tfael.omni.agent.SMS_SENT"
    }
}
