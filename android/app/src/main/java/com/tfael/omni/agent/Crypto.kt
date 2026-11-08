package com.tfael.omni.agent

import android.util.Base64
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Kriptografi untuk C2 via SMS (gratis, antar-HP ber-SIM):
 * - HMAC-SHA256 untuk otentikasi perintah (menolak spoofing).
 * - AES-256-GCM untuk mengenkripsi balasan posisi.
 * Kunci pra-berbagi = "Kunci agen" di Pengaturan (fallback kunci demo).
 */
object Crypto {
    private const val DEMO_KEY = "OMNI-C2-DEMO-KEY"

    private fun keyBytes(key: String): ByteArray =
        (if (key.isBlank()) DEMO_KEY else key).toByteArray(Charsets.UTF_8)

    private fun aesKey(key: String): SecretKeySpec {
        val digest = MessageDigest.getInstance("SHA-256").digest(keyBytes(key))
        return SecretKeySpec(digest, "AES")
    }

    fun hmac(key: String, msg: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(keyBytes(key), "HmacSHA256"))
        return mac.doFinal(msg.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }

    /** Perbandingan waktu-konstan (anti timing attack). */
    fun constTimeEquals(a: String, b: String): Boolean {
        if (a.length != b.length) return false
        var r = 0
        for (i in a.indices) r = r or (a[i].code xor b[i].code)
        return r == 0
    }

    fun aesGcmEncrypt(key: String, plain: String): String {
        val iv = ByteArray(12)
        SecureRandom().nextBytes(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, aesKey(key), GCMParameterSpec(128, iv))
        val ct = cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(iv + ct, Base64.NO_WRAP or Base64.URL_SAFE)
    }

    fun aesGcmDecrypt(key: String, b64: String): String {
        val all = Base64.decode(b64, Base64.NO_WRAP or Base64.URL_SAFE)
        val iv = all.copyOfRange(0, 12)
        val ct = all.copyOfRange(12, all.size)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, aesKey(key), GCMParameterSpec(128, iv))
        return String(cipher.doFinal(ct), Charsets.UTF_8)
    }
}
