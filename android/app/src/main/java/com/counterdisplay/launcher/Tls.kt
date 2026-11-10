package com.counterdisplay.launcher

import android.net.Uri
import android.net.http.SslError

/**
 * Lets the dashboard load Home Assistant over HTTPS by LAN IP when its certificate is issued to a
 * public name (for example a DuckDNS address the LAN can't reach because the router has no NAT
 * loopback).
 *
 * The WebView rejects such a page because the certificate names a host, not the IP. This accepts
 * it only when all of these hold, so it is as strict as normal name checking for that one name:
 *  - the page's host is the host of the configured dashboard URL
 *  - "certificate name" is set and appears in the certificate's DNS names or common name
 *  - the name mismatch is the only error: the chain is trusted, in date and valid
 */
object Tls {
    private val otherErrors = intArrayOf(
        SslError.SSL_NOTYETVALID, SslError.SSL_EXPIRED, SslError.SSL_UNTRUSTED,
        SslError.SSL_DATE_INVALID, SslError.SSL_INVALID,
    )

    fun acceptNameMismatch(cfg: Config, error: SslError): Boolean {
        val want = cfg.haCertName
        if (want.isEmpty()) return false
        if (!error.hasError(SslError.SSL_IDMISMATCH)) return false
        if (otherErrors.any { error.hasError(it) }) return false

        val pageHost = Uri.parse(error.url ?: return false).host?.lowercase() ?: return false
        val haHost = Uri.parse(cfg.haUrl).host?.lowercase() ?: return false
        if (pageHost != haHost) return false

        return certNames(error).any { it == want }
    }

    private fun certNames(error: SslError): List<String> {
        val names = mutableListOf<String>()
        error.certificate?.issuedTo?.cName?.let { names += it.lowercase() }
        try {
            // Type 2 is dNSName in X.509 subjectAltName.
            error.certificate?.x509Certificate?.subjectAlternativeNames
                ?.filter { it.size >= 2 && it[0] == 2 }
                ?.mapNotNull { (it[1] as? String)?.lowercase() }
                ?.let { names += it }
        } catch (_: Exception) { }
        return names
    }
}
