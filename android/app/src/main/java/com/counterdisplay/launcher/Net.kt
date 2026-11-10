package com.counterdisplay.launcher

import android.net.Uri
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.Socket
import java.net.URL
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLSession
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory
import java.security.cert.X509Certificate

/**
 * Plain HTTP(S) and TLS sockets to Home Assistant, with the same certificate rule as [Tls] for the
 * WebView: when the dashboard is loaded over HTTPS by LAN IP and "certificate name" is set, a
 * certificate is accepted for that IP if it is otherwise valid and names that host. Everything
 * else goes through normal verification.
 */
object Net {

    /** Opens a connection; for HTTPS to the dashboard host the name rule above applies. */
    fun open(cfg: Config, url: String, bearer: String? = null, timeoutMs: Int = 15_000): HttpURLConnection {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = timeoutMs
        c.readTimeout = timeoutMs
        if (c is HttpsURLConnection) c.hostnameVerifier = verifier(cfg)
        bearer?.let { c.setRequestProperty("Authorization", "Bearer $it") }
        return c
    }

    /** GETs [url] fully, up to [maxBytes]. Throws on a non-2xx status. */
    fun fetch(cfg: Config, url: String, bearer: String? = null, maxBytes: Int = 20 shl 20): ByteArray {
        val c = open(cfg, url, bearer)
        try {
            if (c.responseCode / 100 != 2) throw java.io.IOException("HTTP ${c.responseCode} for $url")
            val out = ByteArrayOutputStream()
            val buf = ByteArray(16 * 1024)
            c.inputStream.use { s ->
                while (true) {
                    val n = s.read(buf); if (n < 0) break
                    out.write(buf, 0, n)
                    if (out.size() > maxBytes) throw java.io.IOException("too large: $url")
                }
            }
            return out.toByteArray()
        } finally { c.disconnect() }
    }

    /** A connected socket to host:port; TLS with the hostname rule when [tls]. */
    fun socket(cfg: Config, host: String, port: Int, tls: Boolean, timeoutMs: Int = 10_000): Socket {
        if (!tls) return Socket().apply { connect(java.net.InetSocketAddress(host, port), timeoutMs) }
        val s = SSLSocketFactory.getDefault().createSocket() as SSLSocket
        s.connect(java.net.InetSocketAddress(host, port), timeoutMs)
        s.startHandshake()
        if (!verifier(cfg).verify(host, s.session)) {
            s.close()
            throw javax.net.ssl.SSLPeerUnverifiedException("certificate does not match $host")
        }
        return s
    }

    private fun verifier(cfg: Config) = HostnameVerifier { host, session ->
        HttpsURLConnection.getDefaultHostnameVerifier().verify(host, session) || nameRule(cfg, host, session)
    }

    /** The [Tls] rule: the page host is the dashboard host and the certificate names [Config.haCertName]. */
    private fun nameRule(cfg: Config, host: String, session: SSLSession): Boolean {
        val want = cfg.haCertName
        if (want.isEmpty()) return false
        val haHost = Uri.parse(cfg.haUrl).host?.lowercase() ?: return false
        if (host.lowercase() != haHost) return false
        val cert = try { session.peerCertificates.firstOrNull() as? X509Certificate } catch (_: Exception) { null } ?: return false
        val names = mutableListOf<String>()
        try {
            cert.subjectAlternativeNames?.filter { it.size >= 2 && it[0] == 2 }
                ?.mapNotNull { (it[1] as? String)?.lowercase() }?.let { names += it }
        } catch (_: Exception) { }
        Regex("CN=([^,]+)").find(cert.subjectX500Principal.name)?.groupValues?.get(1)?.let { names += it.lowercase() }
        return names.any { it == want }
    }
}
