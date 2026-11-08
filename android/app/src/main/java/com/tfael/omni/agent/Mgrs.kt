package com.tfael.omni.agent

import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.math.tan

/**
 * Konversi lintang/bujur (WGS84) ke grid MGRS, untuk readout koordinat gaya ATAK.
 * Bersifat indikatif untuk peragaan; lintang/bujur desimal tetap sumber yang pasti.
 */
object Mgrs {
    private const val A = 6378137.0
    private const val F = 1.0 / 298.257223563
    private const val K0 = 0.9996
    private val E2 = F * (2 - F)
    private val E4 = E2 * E2
    private val E6 = E4 * E2
    private val EP2 = E2 / (1 - E2)

    fun toMgrs(lat: Double, lon: Double, digits: Int = 5): String {
        if (lat < -80 || lat > 84) return "di luar jangkauan MGRS"
        val zone = (floor((lon + 180) / 6).toInt()) + 1
        val lonOrigin = (zone - 1) * 6 - 180 + 3
        val latRad = Math.toRadians(lat)
        val lonRad = Math.toRadians(lon)
        val lonOriginRad = Math.toRadians(lonOrigin.toDouble())

        val N = A / sqrt(1 - E2 * sin(latRad).pow(2))
        val T = tan(latRad).pow(2)
        val C = EP2 * cos(latRad).pow(2)
        val Aa = cos(latRad) * (lonRad - lonOriginRad)
        val M = A * ((1 - E2 / 4 - 3 * E4 / 64 - 5 * E6 / 256) * latRad
                - (3 * E2 / 8 + 3 * E4 / 32 + 45 * E6 / 1024) * sin(2 * latRad)
                + (15 * E4 / 256 + 45 * E6 / 1024) * sin(4 * latRad)
                - (35 * E6 / 3072) * sin(6 * latRad))

        val easting = K0 * N * (Aa + (1 - T + C) * Aa.pow(3) / 6
                + (5 - 18 * T + T * T + 72 * C - 58 * EP2) * Aa.pow(5) / 120) + 500000.0
        var northing = K0 * (M + N * tan(latRad) * (Aa.pow(2) / 2
                + (5 - T + 9 * C + 4 * C * C) * Aa.pow(4) / 24
                + (61 - 58 * T + T * T + 600 * C - 330 * EP2) * Aa.pow(6) / 720))
        if (lat < 0) northing += 10000000.0

        val band = latBand(lat)
        val col = colLetter(zone, easting)
        val row = rowLetter(zone, northing)
        val e = (easting % 100000).toInt()
        val n = ((northing % 100000) + 100000).toInt() % 100000
        val d = digits.coerceIn(1, 5)
        val div = 10.0.pow(5 - d).toInt()
        val es = (e / div).toString().padStart(d, '0')
        val ns = (n / div).toString().padStart(d, '0')
        return "$zone$band $col$row $es $ns"
    }

    private fun latBand(lat: Double): Char {
        val bands = "CDEFGHJKLMNPQRSTUVWX"
        var idx = floor((lat + 80) / 8).toInt()
        if (idx < 0) idx = 0
        if (idx > 19) idx = 19
        return bands[idx]
    }

    private fun colLetter(zone: Int, easting: Double): Char {
        val set = (zone - 1) % 3
        val letters = when (set) {
            0 -> "ABCDEFGH"
            1 -> "JKLMNPQR"
            else -> "STUVWXYZ"
        }
        val col = floor(easting / 100000).toInt()
        val i = (col - 1).coerceIn(0, letters.length - 1)
        return letters[i]
    }

    private fun rowLetter(zone: Int, northing: Double): Char {
        val letters = if (zone % 2 == 0) "FGHJKLMNPQRSTUVABCDE" else "ABCDEFGHJKLMNPQRSTUV"
        val row = (floor(northing / 100000).toInt() % 20 + 20) % 20
        return letters[row]
    }
}
