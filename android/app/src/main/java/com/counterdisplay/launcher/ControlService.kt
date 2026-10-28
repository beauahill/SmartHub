package com.counterdisplay.launcher

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.util.concurrent.Executors

/**
 * Foreground service with a tiny HTTP server so Home Assistant can drive the display.
 *
 *   GET  /status                    -> JSON state
 *   POST /screen/on | /screen/off   -> panel power (off needs device owner)
 *   POST /ambient/on | /ambient/off -> dim clock overlay
 *   POST /home | /reload | /assist
 *   POST /launch?app=Music          -> tile label or package name
 *   POST /navigate?url=...          -> load a URL in the dashboard view
 *   POST /brightness?value=0-255|auto
 *   GET  /config, POST /config      -> read or update settings (JSON body)
 *
 * Every request needs the token: header "Authorization: Bearer <token>" or ?token=<token>.
 */
class ControlService : Service() {

    private lateinit var cfg: Config
    private var server: ServerSocket? = null
    private val pool = Executors.newFixedThreadPool(4)
    private var cpuLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        cfg = Config(this)
        goForeground()
        holdLocks()
        startServer()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_RESTART_SERVER) startServer()
        return START_STICKY
    }

    override fun onDestroy() {
        try { server?.close() } catch (_: Exception) { }
        pool.shutdownNow()
        cpuLock?.let { if (it.isHeld) it.release() }
        wifiLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    // ---------------------------------------------------------------- setup

    private fun goForeground() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Counter Home control", NotificationManager.IMPORTANCE_MIN)
        )
        val n = Notification.Builder(this, CHANNEL)
            .setContentTitle("Counter Home")
            .setContentText("Listening for Home Assistant on port ${cfg.port}")
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIF_ID, n)
        }
    }

    @Suppress("DEPRECATION")
    private fun holdLocks() {
        // The tablet is always on the charger, so holding these costs nothing and keeps the API reachable with the panel off.
        cpuLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "CounterHome:api").apply {
                setReferenceCounted(false); acquire()
            }
        wifiLock = applicationContext.getSystemService(WifiManager::class.java)
            .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "CounterHome:wifi").apply {
                setReferenceCounted(false); acquire()
            }
    }

    private fun startServer() {
        try { server?.close() } catch (_: Exception) { }
        val port = cfg.port
        Thread({
            try {
                val ss = ServerSocket()
                ss.reuseAddress = true
                ss.bind(InetSocketAddress(port))
                server = ss
                Log.i(TAG, "API listening on $port")
                while (!ss.isClosed) {
                    val s = ss.accept()
                    pool.execute { handle(s) }
                }
            } catch (e: Exception) {
                Log.w(TAG, "server stopped: ${e.message}")
            }
        }, "counter-api").start()
    }

    // ---------------------------------------------------------------- HTTP

    private fun handle(sock: Socket) {
        sock.use { s ->
            s.soTimeout = 5000
            try {
                val reader = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.UTF_8))
                val requestLine = reader.readLine() ?: return
                val parts = requestLine.split(" ")
                if (parts.size < 2) return
                val method = parts[0].uppercase()
                val (path, query) = splitQuery(parts[1])

                val headers = HashMap<String, String>()
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                    val i = line.indexOf(':')
                    if (i > 0) headers[line.substring(0, i).trim().lowercase()] = line.substring(i + 1).trim()
                }
                val len = headers["content-length"]?.toIntOrNull() ?: 0
                val body = if (len in 1..65536) {
                    val buf = CharArray(len); var read = 0
                    while (read < len) { val r = reader.read(buf, read, len - read); if (r < 0) break; read += r }
                    String(buf, 0, read)
                } else ""

                val auth = headers["authorization"]?.removePrefix("Bearer ")?.trim()
                    ?: headers["x-api-key"] ?: query["token"]
                val (code, json) = if (auth != cfg.token) {
                    401 to JSONObject().put("ok", false).put("error", "bad or missing token")
                } else route(method, path, query, body)

                val bytes = json.toString().toByteArray(Charsets.UTF_8)
                val out = s.getOutputStream()
                out.write(("HTTP/1.1 $code ${if (code == 200) "OK" else "Error"}\r\n" +
                    "Content-Type: application/json\r\n" +
                    "Content-Length: ${bytes.size}\r\n" +
                    "Connection: close\r\n\r\n").toByteArray(Charsets.UTF_8))
                out.write(bytes)
                out.flush()
            } catch (e: Exception) {
                Log.w(TAG, "request failed: ${e.message}")
            }
        }
    }

    private fun route(method: String, path: String, q: Map<String, String>, body: String): Pair<Int, JSONObject> {
        val ok = JSONObject().put("ok", true)
        when (path.trimEnd('/').ifEmpty { "/" }) {
            "/", "/status" -> return 200 to status()
            "/screen/on" -> { Kiosk.screenOn(this); Bus.post(Command.WakeUp); Bus.post(Command.Ambient(false)) }
            "/screen/off" -> if (!Kiosk.screenOff(this)) return 409 to err("screen off needs device owner")
            "/screen/toggle" -> if (Kiosk.isScreenOn(this)) Kiosk.screenOff(this)
                                else { Kiosk.screenOn(this); Bus.post(Command.WakeUp) }
            "/ambient/on" -> { Kiosk.screenOn(this); Bus.post(Command.Ambient(true)) }
            "/ambient/off" -> Bus.post(Command.Ambient(false))
            "/home" -> { Kiosk.screenOn(this); Bus.post(Command.Home) }
            "/reload" -> Bus.post(Command.Reload)
            "/assist" -> { Kiosk.screenOn(this); Bus.post(Command.Assist) }
            "/launch" -> {
                val app = q["app"] ?: return 400 to err("missing app")
                Kiosk.screenOn(this); Bus.post(Command.Launch(app))
            }
            "/navigate" -> {
                val url = q["url"] ?: return 400 to err("missing url")
                Bus.post(Command.Navigate(url))
            }
            "/brightness" -> {
                val v = q["value"] ?: return 400 to err("missing value")
                val done = if (v == "auto") Kiosk.setAutoBrightness(this)
                           else Kiosk.setBrightness(this, v.toIntOrNull() ?: return 400 to err("value 0-255 or auto"))
                if (!done) return 409 to err("brightness needs device owner")
            }
            "/config" -> {
                if (method == "GET") return 200 to cfg.toJson()
                return try {
                    val oldPort = cfg.port
                    cfg.apply(JSONObject(body))
                    Bus.post(Command.ConfigChanged)
                    if (cfg.port != oldPort) startServer()
                    200 to ok
                } catch (e: Exception) { 400 to err("bad config: ${e.message}") }
            }
            else -> return 404 to err("unknown path $path")
        }
        return 200 to ok
    }

    private fun status(): JSONObject {
        val batt = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = batt?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = batt?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val plugged = (batt?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0
        val temp = (batt?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10.0
        return JSONObject()
            .put("ok", true)
            .put("version", BuildConfigShim.VERSION)
            .put("screenOn", Kiosk.isScreenOn(this))
            .put("ambient", State.ambient)
            .put("launcherInFront", State.foreground)
            .put("deviceOwner", Kiosk.isOwner(this))
            .put("kioskPaused", State.kioskPaused)
            .put("battery", if (level >= 0) level * 100 / scale else -1)
            .put("charging", plugged)
            .put("batteryTempC", temp)
            .put("ip", ipAddress(this) ?: "")
    }

    private fun err(msg: String) = JSONObject().put("ok", false).put("error", msg)

    private fun splitQuery(target: String): Pair<String, Map<String, String>> {
        val i = target.indexOf('?')
        if (i < 0) return target to emptyMap()
        val map = HashMap<String, String>()
        for (pair in target.substring(i + 1).split('&')) {
            if (pair.isEmpty()) continue
            val j = pair.indexOf('=')
            val k = if (j < 0) pair else pair.substring(0, j)
            val v = if (j < 0) "" else pair.substring(j + 1)
            map[URLDecoder.decode(k, "UTF-8")] = URLDecoder.decode(v, "UTF-8")
        }
        return target.substring(0, i) to map
    }

    companion object {
        private const val TAG = "CounterHome"
        private const val CHANNEL = "control"
        private const val NOTIF_ID = 7
        const val ACTION_RESTART_SERVER = "restart_server"

        fun start(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, ControlService::class.java))
        }

        fun restartServer(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, ControlService::class.java).setAction(ACTION_RESTART_SERVER))
        }

        fun ipAddress(ctx: Context): String? {
            val cm = ctx.getSystemService(ConnectivityManager::class.java)
            val lp = cm.getLinkProperties(cm.activeNetwork) ?: return null
            return lp.linkAddresses.map { it.address }.firstOrNull { it is Inet4Address }?.hostAddress
        }
    }
}

/** Avoids enabling buildConfig generation just for one string. */
object BuildConfigShim { const val VERSION = "1.0.0" }
