package com.tfael.omni.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

/**
 * Menyalakan ulang pelaporan setelah ponsel di-restart, bila auto-start aktif
 * (atau pelaporan sedang berjalan sebelum reboot) dan server sudah diatur.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        if (action != Intent.ACTION_BOOT_COMPLETED && action != "android.intent.action.QUICKBOOT_POWERON") return
        val prefs = context.getSharedPreferences("omni_agent", Context.MODE_PRIVATE)
        val auto = prefs.getBoolean(MainActivity.KEY_AUTO, true)
        val running = prefs.getBoolean(MainActivity.KEY_RUNNING, false)
        val server = (prefs.getString(MainActivity.KEY_SERVER, "") ?: "").trim()
        if ((auto || running) && server.isNotEmpty()) {
            try {
                ContextCompat.startForegroundService(context, Intent(context, ReporterService::class.java))
            } catch (_: Exception) { /* sebagian ROM membatasi start service dari boot; auto-resume saat app dibuka menutupi ini */ }
        }
    }
}
