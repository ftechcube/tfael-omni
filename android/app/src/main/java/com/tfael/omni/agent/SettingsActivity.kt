package com.tfael.omni.agent

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat

/** Menu Pengaturan: semua isian agen (server, unit, kunci, jeda, auto-start). */
class SettingsActivity : Activity() {

    private val BG = 0xFF201E19.toInt()
    private val LINE = 0xFF3E3A31.toInt()
    private val INK = 0xFFF1ECE0.toInt()
    private val INK_DIM = 0xFFA9A192.toInt()
    private val GO = 0xFF6FB06A.toInt()
    private val DARKINK = 0xFF1A1813.toInt()
    private val cond = Typeface.create("sans-serif-condensed", Typeface.BOLD)
    private val sans = Typeface.create("sans-serif", Typeface.NORMAL)
    private val mono = Typeface.MONOSPACE

    private lateinit var prefs: android.content.SharedPreferences
    private lateinit var serverField: EditText
    private lateinit var unitField: EditText
    private lateinit var roleField: EditText
    private lateinit var keyField: EditText
    private lateinit var intervalField: EditText
    private lateinit var autoRow: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("omni_agent", Context.MODE_PRIVATE)
        if (android.os.Build.VERSION.SDK_INT >= 21) { window.statusBarColor = BG; window.navigationBarColor = BG }
        setContentView(buildUi())
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun rounded(fill: Int, radius: Int, stroke: Int = 0, strokeW: Int = 0) =
        GradientDrawable().apply { setColor(fill); cornerRadius = dp(radius).toFloat(); if (strokeW > 0) setStroke(dp(strokeW), stroke) }

    private fun buildUi(): ScrollView {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setBackgroundColor(BG)
            setPadding(dp(20), dp(22), dp(20), dp(28))
        }
        root.addView(TextView(this).apply {
            text = "Pengaturan"; setTextColor(INK); textSize = 22f; typeface = cond
        })
        root.addView(TextView(this).apply {
            text = "Agen unit lapangan"; setTextColor(INK_DIM); textSize = 13f; typeface = sans
            setPadding(0, 0, 0, dp(6))
        })

        serverField = field(MainActivity.KEY_SERVER, "http://192.168.1.10:8080", mono = true)
        serverField.inputType = InputType.TYPE_TEXT_VARIATION_URI
        root.addView(block("Alamat server", serverField))
        unitField = field(MainActivity.KEY_UNIT, "ALPHA-01", mono = true)
        root.addView(block("Nama unit", unitField))
        roleField = field(MainActivity.KEY_ROLE, "Tim Tindak Cepat")
        root.addView(block("Peran", roleField))
        keyField = field(MainActivity.KEY_AGENTKEY, "", mono = true)
        root.addView(block("Kunci agen (boleh kosong)", keyField))
        intervalField = field(MainActivity.KEY_INTERVAL, "5", mono = true)
        intervalField.inputType = InputType.TYPE_CLASS_NUMBER
        root.addView(block("Jeda kirim (detik)", intervalField))

        // Toggle auto-start
        autoRow = TextView(this).apply {
            textSize = 14f; typeface = sans; setPadding(dp(14), dp(14), dp(14), dp(14))
            isClickable = true
            setOnClickListener {
                val now = !prefs.getBoolean(MainActivity.KEY_AUTO, true)
                prefs.edit().putBoolean(MainActivity.KEY_AUTO, now).apply(); paintAutoRow(now)
            }
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                .apply { topMargin = dp(22) }
        }
        paintAutoRow(prefs.getBoolean(MainActivity.KEY_AUTO, true))
        root.addView(autoRow)

        // Toggle Mode Gateway: HP ini jadi jembatan — tiap posisi SMS yang didekripsi
        // diteruskan ke server lewat jaringan lokal (muncul di peta komando).
        val gatewayRow = TextView(this).apply {
            textSize = 14f; typeface = sans; setPadding(dp(14), dp(14), dp(14), dp(14))
            isClickable = true
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                .apply { topMargin = dp(12) }
        }
        fun paintGw(on: Boolean) {
            gatewayRow.text = if (on) "✓  Mode Gateway — teruskan SMS ke server" else "Mode Gateway — nonaktif"
            gatewayRow.setTextColor(if (on) GO else INK_DIM)
            gatewayRow.background = rounded(if (on) 0x224FA86A else 0x18FFFFFF, 10)
        }
        paintGw(prefs.getBoolean(MainActivity.KEY_GATEWAY, false))
        gatewayRow.setOnClickListener {
            val now = !prefs.getBoolean(MainActivity.KEY_GATEWAY, false)
            prefs.edit().putBoolean(MainActivity.KEY_GATEWAY, now).apply(); paintGw(now)
        }
        root.addView(gatewayRow)
        root.addView(TextView(this).apply {
            text = "Nyalakan hanya di HP pos komando yang tersambung ke server (WiFi/USB lokal). Agen lapangan cukup kirim SMS — tanpa internet."
            setTextColor(INK_DIM); textSize = 11f; typeface = sans; setPadding(dp(4), dp(6), 0, 0)
        })

        val save = TextView(this).apply {
            text = "Simpan"; gravity = Gravity.CENTER; typeface = cond; textSize = 16f
            setTextColor(DARKINK); background = rounded(GO, 28); setPadding(0, dp(16), 0, dp(16))
            isClickable = true
            setOnClickListener { saveAndExit() }
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                .apply { topMargin = dp(24) }
        }
        root.addView(save)
        root.addView(TextView(this).apply {
            text = "Pelaporan berjalan otomatis saat aplikasi dibuka dan setelah ponsel dinyalakan ulang."
            setTextColor(INK_DIM); textSize = 12f; typeface = sans; setPadding(0, dp(14), 0, 0)
        })
        return ScrollView(this).apply { setBackgroundColor(BG); addView(root) }
    }

    private fun paintAutoRow(on: Boolean) {
        autoRow.text = if (on) "✓  Mulai otomatis — aktif" else "Mulai otomatis — nonaktif"
        autoRow.setTextColor(if (on) GO else INK_DIM)
        autoRow.background = rounded(if (on) 0x224FA86A else 0x18FFFFFF, 10)
    }

    private fun block(label: String, input: EditText): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; setPadding(0, dp(12), 0, 0)
        addView(TextView(this@SettingsActivity).apply { text = label; setTextColor(INK_DIM); textSize = 12f; typeface = sans })
        addView(input)
        addView(View(this@SettingsActivity).apply {
            setBackgroundColor(LINE)
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(1)).apply { topMargin = dp(2) }
        })
    }

    private fun field(key: String, def: String, mono: Boolean = false): EditText = EditText(this).apply {
        setText(prefs.getString(key, def)); setTextColor(INK); setHintTextColor(INK_DIM); textSize = 16f
        typeface = if (mono) this@SettingsActivity.mono else sans
        background = null; setPadding(0, dp(7), 0, dp(6))
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    }

    private fun saveAndExit() {
        prefs.edit()
            .putString(MainActivity.KEY_SERVER, serverField.text.toString().trim())
            .putString(MainActivity.KEY_UNIT, unitField.text.toString().trim())
            .putString(MainActivity.KEY_ROLE, roleField.text.toString().trim())
            .putString(MainActivity.KEY_AGENTKEY, keyField.text.toString().trim())
            .putString(MainActivity.KEY_INTERVAL, intervalField.text.toString().trim().ifEmpty { "5" })
            .apply()
        // Jika sedang melapor, mulai ulang service agar konfigurasi baru dipakai.
        if (prefs.getBoolean(MainActivity.KEY_RUNNING, false)) {
            stopService(Intent(this, ReporterService::class.java))
            ContextCompat.startForegroundService(this, Intent(this, ReporterService::class.java))
        }
        finish()
    }
}
