package com.counterdisplay.launcher

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.BroadcastReceiver
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
import java.io.OutputStream
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

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
 *   POST /camera/on?minutes=N       -> camera on, optional auto-off (needs "Allow the camera" in settings)
 *   POST /camera/off
 *   GET  /camera.jpg                -> latest frame (503 while the camera is off)
 *   GET  /camera.mjpeg              -> MJPEG stream; ends when the camera turns off
 *
 * It also holds the media volume at or below the configured cap (see [Volume]).
 *
 * Every request needs the token: header "Authorization: Bearer <token>" or ?token=<token>.
 */
class ControlService : Service() {

    private lateinit var cfg: Config
    private var server: ServerSocket? = null
    private val pool = Executors.newFixedThreadPool(8)      // MJPEG streams hold a thread each
    private val streams = AtomicInteger(0)
    private var cpuLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    private val volumeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.getIntExtra(Volume.EXTRA_STREAM, -1) == android.media.AudioManager.STREAM_MUSIC) {
                Volume.enforce(context, cfg)
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        cfg = Config(this)
        // Camera access from a foreground service has to be claimed while the app is on screen.
        // The launcher starts this service from onCreate, so State.foreground is normally true here.
        goForeground(withCamera = State.foreground)
        holdLocks()
        startServer()
        watchVolume()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_RESTART_SERVER -> startServer()
            ACTION_REFRESH_FOREGROUND -> goForeground(withCamera = true)   // sent from MainActivity.onResume
        }
        return START_STICKY
    }

    override fun onDestroy() {
        try { unregisterReceiver(volumeReceiver) } catch (_: Exception) { }
        CameraStreamer.stop()
        try { server?.close() } catch (_: Exception) { }
        pool.shutdownNow()
        cpuLock?.let { if (it.isHeld) it.release() }
        wifiLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    // ---------------------------------------------------------------- setup

    private fun goForeground(withCamera: Boolean) {
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
        val camera = withCamera && cfg.cameraAllowed && CameraStreamer.hasPermission(this)
        try {
            when {
                Build.VERSION.SDK_INT >= 34 -> startForeground(NOTIF_ID, n,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or
                        (if (camera) ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA else 0))
                Build.VERSION.SDK_INT >= 30 && camera ->
                    startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)
                else -> startForeground(NOTIF_ID, n)
            }
            cameraForeground = camera
        } catch (e: Exception) {
            // Not allowed to claim the camera right now (app in the background): keep the plain type.
            Log.w(TAG, "foreground with camera refused: ${e.message}")
            if (Build.VERSION.SDK_INT >= 34) startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            else startForeground(NOTIF_ID, n)
            cameraForeground = false
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

    private fun watchVolume() {
        val filter = IntentFilter(Volume.ACTION_CHANGED)
        // System broadcasts still arrive with NOT_EXPORTED; other apps can't poke the receiver.
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(volumeReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        else registerReceiver(volumeReceiver, filter)
        Volume.enforce(this, cfg)
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
                val out = s.getOutputStream()
                if (auth != cfg.token) {
                    writeJson(out, 401, err("bad or missing token")); return
                }
                when (path) {
                    "/camera.jpg" -> { serveSnapshot(out); return }
                    "/camera.mjpeg" -> { serveMjpeg(out); return }
                }
                val (code, json) = route(method, path, query, body)
                writeJson(out, code, json)
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
            "/camera/on" -> {
                if (!cfg.cameraAllowed) return 403 to err("camera is turned off in Counter Home settings")
                if (!cameraForeground) goForeground(withCamera = true)
                val minutes = q["minutes"]?.toIntOrNull() ?: 0
                CameraStreamer.start(this, cfg, minutes)?.let { return 409 to err(it) }
                return 200 to JSONObject().put("ok", true).put("camera", CameraStreamer.statusJson())
            }
            "/camera/off" -> CameraStreamer.stop()
            "/config" -> {
                if (method == "GET") return 200 to cfg.toJson()
                return try {
                    val oldPort = cfg.port
                    val oldCam = Triple(cfg.cameraFacing, cfg.cameraWidth, cfg.cameraRotation)
                    cfg.apply(JSONObject(body))
                    Volume.enforce(this, cfg)
                    if (CameraStreamer.running && oldCam != Triple(cfg.cameraFacing, cfg.cameraWidth, cfg.cameraRotation)) {
                        // reopen with the new settings, keeping any auto-off that was running
                        val offAt = CameraStreamer.offAtMs
                        val left = if (offAt > 0)
                            ((offAt - android.os.SystemClock.uptimeMillis() + 59_999L) / 60_000L).toInt().coerceAtLeast(1) else 0
                        CameraStreamer.stop()
                        CameraStreamer.start(this, cfg, left)
                    }
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
            .put("volume", Volume.percent(this))
            .put("maxVolume", cfg.maxVolume)
            .put("cameraAllowed", cfg.cameraAllowed)
            .put("camera", CameraStreamer.statusJson())
            .put("batteryTempC", temp)
            .put("ip", ipAddress(this) ?: "")
    }

    private fun err(msg: String) = JSONObject().put("ok", false).put("error", msg)

    private fun writeJson(out: OutputStream, code: Int, json: JSONObject) =
        writeBytes(out, code, "application/json", json.toString().toByteArray(Charsets.UTF_8))

    private fun writeBytes(out: OutputStream, code: Int, type: String, bytes: ByteArray) {
        out.write(("HTTP/1.1 $code ${if (code == 200) "OK" else "Error"}\r\n" +
            "Content-Type: $type\r\n" +
            "Content-Length: ${bytes.size}\r\n" +
            "Cache-Control: no-store\r\n" +
            "Connection: close\r\n\r\n").toByteArray(Charsets.UTF_8))
        out.write(bytes)
        out.flush()
    }

    /** Latest JPEG. While the camera is off this is an error, never a reason to switch it on. */
    private fun serveSnapshot(out: OutputStream) {
        if (!CameraStreamer.running) { writeJson(out, 503, err("camera is off")); return }
        val f = CameraStreamer.latestFrame() ?: CameraStreamer.awaitFrame(0L, 4000)
        if (f == null) writeJson(out, 503, err(CameraStreamer.error ?: "no frame yet"))
        else writeBytes(out, 200, "image/jpeg", f.jpeg)
    }

    /** multipart/x-mixed-replace stream of JPEG frames until the client leaves or the camera stops. */
    private fun serveMjpeg(out: OutputStream) {
        if (!CameraStreamer.running) { writeJson(out, 503, err("camera is off")); return }
        if (streams.incrementAndGet() > MAX_STREAMS) {
            streams.decrementAndGet(); writeJson(out, 503, err("too many streams")); return
        }
        try {
            out.write(("HTTP/1.1 200 OK\r\n" +
                "Content-Type: multipart/x-mixed-replace; boundary=$BOUNDARY\r\n" +
                "Cache-Control: no-store\r\n" +
                "Connection: close\r\n\r\n").toByteArray(Charsets.UTF_8))
            var last = 0L
            while (true) {
                val f = CameraStreamer.awaitFrame(last, 5000) ?: break
                last = f.atMs
                out.write(("--$BOUNDARY\r\nContent-Type: image/jpeg\r\nContent-Length: ${f.jpeg.size}\r\n\r\n")
                    .toByteArray(Charsets.UTF_8))
                out.write(f.jpeg)
                out.write("\r\n".toByteArray(Charsets.UTF_8))
                out.flush()
            }
        } catch (_: Exception) {
            // client went away
        } finally {
            streams.decrementAndGet()
        }
    }

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
        const val ACTION_REFRESH_FOREGROUND = "refresh_foreground"
        private const val MAX_STREAMS = 3
        private const val BOUNDARY = "counterframe"
        @Volatile private var cameraForeground = false

        /** Re-claims the foreground service types (camera included) while the launcher is on screen. */
        fun refreshForeground(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, ControlService::class.java).setAction(ACTION_REFRESH_FOREGROUND))
        }

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
object BuildConfigShim { const val VERSION = "1.2.0" }
