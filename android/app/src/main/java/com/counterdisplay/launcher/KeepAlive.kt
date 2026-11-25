package com.counterdisplay.launcher

import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.ServiceConnection
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import org.json.JSONObject

/**
 * Keeps background players such as MassDroid (Music Assistant's Spotify Connect / AirPlay speaker)
 * out of Android's cached-app freezer.
 *
 * While MassDroid is paused its playback service isn't a foreground service, so with the dashboard
 * in front Android caches its process and freezes it about ten seconds later. A frozen MassDroid
 * never hears Music Assistant start a cast, so "Counter Display | Music Assistant" plays nothing. The
 * battery whitelist and RUN_ANY_IN_BACKGROUND don't exempt it from the freezer.
 *
 * Holding a binding to the app's exported media browser service does: a bound process takes on
 * this app's priority (Counter Home always runs a foreground service), so it's never cached. Only
 * the binding is held; nothing connects to the media session, so the app behaves as before.
 *
 * Call [sync] from the main thread; [ControlService] does it when it starts and when settings change.
 */
object KeepAlive {
    private const val TAG = "CounterHome"
    private const val ACTION = "android.media.browse.MediaBrowserService"

    private val main = Handler(Looper.getMainLooper())
    private val bound = mutableMapOf<String, ServiceConnection>()
    private var app: Context? = null
    private var wanted: List<String> = emptyList()

    /** Re-binds when a kept app is installed, updated or re-enabled. */
    private val packages = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val pkg = intent.data?.schemeSpecificPart ?: return
            if (pkg in wanted) main.post { rebind(pkg) }
        }
    }

    fun sync(ctx: Context, apps: List<String>) {
        val c = ctx.applicationContext
        if (app == null) {
            app = c
            c.registerReceiver(packages, IntentFilter().apply {
                addAction(Intent.ACTION_PACKAGE_ADDED)
                addAction(Intent.ACTION_PACKAGE_REPLACED)
                addAction(Intent.ACTION_PACKAGE_CHANGED)
                addDataScheme("package")
            })
        }
        wanted = apps.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
        (bound.keys - wanted.toSet()).forEach { unbind(it) }
        wanted.forEach { if (it !in bound) bind(it) }
    }

    fun release() {
        bound.keys.toList().forEach { unbind(it) }
        main.removeCallbacksAndMessages(null)
        app?.let { try { it.unregisterReceiver(packages) } catch (_: Exception) { } }
        app = null
        wanted = emptyList()
    }

    /** For /status: each kept app and whether its binding is live. */
    fun statusJson(): JSONObject = JSONObject().apply { wanted.forEach { put(it, it in bound) } }

    private fun bind(pkg: String) {
        val c = app ?: return
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, service: IBinder) {
                Log.i(TAG, "keeping $pkg alive (bound to ${name.shortClassName})")
            }
            // The app's process died; Android restarts the service and reconnects on its own.
            override fun onServiceDisconnected(name: ComponentName) {
                Log.w(TAG, "$pkg went away; Android will restart it")
            }
            // Updated, disabled or force-stopped: this binding is finished, make a new one.
            override fun onBindingDied(name: ComponentName) {
                Log.w(TAG, "binding to $pkg died; binding again")
                main.post { rebind(pkg) }
            }
            override fun onNullBinding(name: ComponentName) {
                Log.w(TAG, "$pkg returned no binder; it stays bound but may still be frozen")
            }
        }
        val intent = Intent(ACTION).setPackage(pkg)
        val ok = try {
            c.bindService(intent, conn, Context.BIND_AUTO_CREATE)
        } catch (e: SecurityException) {
            Log.w(TAG, "can't bind to $pkg", e); false
        }
        if (ok) {
            bound[pkg] = conn
        } else {
            // Not installed, or no media browser service in it. The package receiver binds on install.
            try { c.unbindService(conn) } catch (_: Exception) { }
            Log.w(TAG, "can't keep $pkg alive: not installed, or no $ACTION in it")
        }
    }

    private fun unbind(pkg: String) {
        val conn = bound.remove(pkg) ?: return
        try { app?.unbindService(conn) } catch (_: Exception) { }
    }

    private fun rebind(pkg: String) {
        unbind(pkg)
        if (pkg in wanted) bind(pkg)
    }
}
