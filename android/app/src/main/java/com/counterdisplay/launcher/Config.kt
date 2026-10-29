package com.counterdisplay.launcher

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.security.SecureRandom

/** One button on the dock. Either opens an app by package, or runs a built-in action. */
data class Tile(
    val label: String,
    val pkg: String? = null,       // e.g. com.spotify.music
    val action: String? = null,    // "assist", "reload", "home"
    val color: String = "#2A3038",
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("label", label)
        pkg?.let { put("package", it) }
        action?.let { put("action", it) }
        put("color", color)
    }

    companion object {
        fun fromJson(o: JSONObject) = Tile(
            label = o.optString("label", "App"),
            pkg = o.optString("package").takeIf { it.isNotBlank() },
            action = o.optString("action").takeIf { it.isNotBlank() },
            color = o.optString("color", "#2A3038"),
        )
    }
}

/** All settings live in one SharedPreferences file and can also be pushed as JSON over the API. */
class Config(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("counter_home", Context.MODE_PRIVATE)

    init {
        if (!prefs.contains(KEY_TOKEN)) prefs.edit().putString(KEY_TOKEN, newToken()).apply()
    }

    var haUrl: String
        get() = prefs.getString(KEY_URL, DEFAULT_URL)!!
        set(v) = prefs.edit().putString(KEY_URL, v.trim()).apply()

    var port: Int
        get() = prefs.getInt(KEY_PORT, 2323)
        set(v) = prefs.edit().putInt(KEY_PORT, v).apply()

    var token: String
        get() = prefs.getString(KEY_TOKEN, "")!!
        set(v) = prefs.edit().putString(KEY_TOKEN, v.trim()).apply()

    var pin: String
        get() = prefs.getString(KEY_PIN, "2580")!!
        set(v) = prefs.edit().putString(KEY_PIN, v.trim()).apply()

    /** True once a token has been pushed by setup.sh; after that the intent route is ignored. */
    var provisioned: Boolean
        get() = prefs.getBoolean(KEY_PROVISIONED, false)
        set(v) = prefs.edit().putBoolean(KEY_PROVISIONED, v).apply()

    /** Pin the launcher with lock task mode when it is the device owner. */
    var kioskLock: Boolean
        get() = prefs.getBoolean(KEY_LOCK, true)
        set(v) = prefs.edit().putBoolean(KEY_LOCK, v).apply()

    /** Media volume cap in percent of the stream maximum (1-100). 100 means no cap. */
    var maxVolume: Int
        get() = prefs.getInt(KEY_MAX_VOLUME, DEFAULT_MAX_VOLUME)
        set(v) = prefs.edit().putInt(KEY_MAX_VOLUME, v.coerceIn(1, 100)).apply()

    /**
     * Master switch for the camera. Only the on-device settings screen (behind the PIN) can change it;
     * the API cannot, so a leaked token alone can't turn a camera on that the owner switched off.
     */
    var cameraAllowed: Boolean
        get() = prefs.getBoolean(KEY_CAM_ALLOWED, false)
        set(v) = prefs.edit().putBoolean(KEY_CAM_ALLOWED, v).apply()

    /** "front" (looks out through the bezel) or "back" (behind the tray, normally covered). */
    var cameraFacing: String
        get() = prefs.getString(KEY_CAM_FACING, "front")!!
        set(v) = prefs.edit().putString(KEY_CAM_FACING, if (v == "back") "back" else "front").apply()

    var cameraWidth: Int
        get() = prefs.getInt(KEY_CAM_WIDTH, 1280)
        set(v) = prefs.edit().putInt(KEY_CAM_WIDTH, v.coerceIn(320, 1920)).apply()

    var cameraFps: Int
        get() = prefs.getInt(KEY_CAM_FPS, 5)
        set(v) = prefs.edit().putInt(KEY_CAM_FPS, v.coerceIn(1, 15)).apply()

    var cameraQuality: Int
        get() = prefs.getInt(KEY_CAM_QUALITY, 70)
        set(v) = prefs.edit().putInt(KEY_CAM_QUALITY, v.coerceIn(30, 95)).apply()

    /** Degrees to rotate the picture, or -1 to follow the screen orientation. */
    var cameraRotation: Int
        get() = prefs.getInt(KEY_CAM_ROTATION, -1)
        set(v) = prefs.edit().putInt(KEY_CAM_ROTATION, if (v in setOf(0, 90, 180, 270)) v else -1).apply()

    /** "right", "left" or "bottom". */
    var dockSide: String
        get() = prefs.getString(KEY_DOCK, "right")!!
        set(v) = prefs.edit().putString(KEY_DOCK, v).apply()

    var tiles: List<Tile>
        get() = parseTiles(prefs.getString(KEY_TILES, null) ?: DEFAULT_TILES)
        set(v) = prefs.edit().putString(KEY_TILES, JSONArray(v.map { it.toJson() }).toString(2)).apply()

    var tilesJson: String
        get() = prefs.getString(KEY_TILES, null) ?: DEFAULT_TILES
        set(v) {
            parseTiles(v) // throws if malformed, so bad JSON never gets saved
            prefs.edit().putString(KEY_TILES, v).apply()
        }

    fun toJson(includeSecrets: Boolean = false): JSONObject = JSONObject().apply {
        put("haUrl", haUrl)
        put("port", port)
        put("kioskLock", kioskLock)
        put("dockSide", dockSide)
        put("maxVolume", maxVolume)
        put("cameraAllowed", cameraAllowed)
        put("cameraFacing", cameraFacing)
        put("cameraWidth", cameraWidth)
        put("cameraFps", cameraFps)
        put("cameraQuality", cameraQuality)
        put("cameraRotation", cameraRotation)
        put("tiles", JSONArray(tilesJson))
        if (includeSecrets) { put("token", token); put("pin", pin) }
    }

    /** Applies any keys present in [o]; unknown keys are ignored. */
    fun apply(o: JSONObject) {
        if (o.has("haUrl")) haUrl = o.getString("haUrl")
        if (o.has("port")) port = o.getInt("port")
        if (o.has("kioskLock")) kioskLock = o.getBoolean("kioskLock")
        if (o.has("dockSide")) dockSide = o.getString("dockSide")
        if (o.has("maxVolume")) maxVolume = o.getInt("maxVolume")
        // cameraAllowed is deliberately not settable here; see its comment.
        if (o.has("cameraFacing")) cameraFacing = o.getString("cameraFacing")
        if (o.has("cameraWidth")) cameraWidth = o.getInt("cameraWidth")
        if (o.has("cameraFps")) cameraFps = o.getInt("cameraFps")
        if (o.has("cameraQuality")) cameraQuality = o.getInt("cameraQuality")
        if (o.has("cameraRotation")) cameraRotation = o.getInt("cameraRotation")
        if (o.has("tiles")) tilesJson = o.getJSONArray("tiles").toString(2)
        if (o.has("pin")) pin = o.getString("pin")
    }

    /** Packages the launcher may open while lock task mode is on. */
    fun allowedPackages(self: String): Array<String> =
        (listOf(self, HA_COMPANION) + tiles.mapNotNull { it.pkg }).distinct().toTypedArray()

    companion object {
        const val HA_COMPANION = "io.homeassistant.companion.android"
        private const val KEY_URL = "ha_url"
        private const val KEY_PORT = "port"
        private const val KEY_TOKEN = "token"
        private const val KEY_PIN = "pin"
        private const val KEY_LOCK = "kiosk_lock"
        private const val KEY_DOCK = "dock_side"
        private const val KEY_TILES = "tiles"
        private const val KEY_PROVISIONED = "provisioned"
        private const val KEY_MAX_VOLUME = "max_volume"
        private const val KEY_CAM_ALLOWED = "camera_allowed"
        private const val KEY_CAM_FACING = "camera_facing"
        private const val KEY_CAM_WIDTH = "camera_width"
        private const val KEY_CAM_FPS = "camera_fps"
        private const val KEY_CAM_QUALITY = "camera_quality"
        private const val KEY_CAM_ROTATION = "camera_rotation"
        /** Roughly 6 to 8 dB below full scale on Android's volume curve. Tune it by ear. */
        const val DEFAULT_MAX_VOLUME = 80
        const val DEFAULT_URL = "http://homeassistant.local:8123/dashboard-counter/0?kiosk"

        val DEFAULT_TILES = """
            [
              {"label": "Music",   "package": "com.spotify.music",                         "color": "#1F8F4E"},
              {"label": "Live TV", "package": "com.google.android.apps.youtube.unplugged", "color": "#C43B33"},
              {"label": "IPTV",    "package": "com.nst.iptvsmarterstvbox",                 "color": "#3A62B8"},
              {"label": "Assist",  "action": "assist",                                     "color": "#16A3C9"}
            ]
        """.trimIndent()

        fun parseTiles(s: String): List<Tile> {
            val a = JSONArray(s)
            return (0 until a.length()).map { Tile.fromJson(a.getJSONObject(it)) }
        }

        private fun newToken(): String {
            val bytes = ByteArray(18)
            SecureRandom().nextBytes(bytes)
            return bytes.joinToString("") { "%02x".format(it) }
        }
    }
}
