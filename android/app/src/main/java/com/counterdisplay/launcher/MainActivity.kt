package com.counterdisplay.launcher

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.net.http.SslError
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextClock
import android.widget.TextView
import android.widget.Toast

/** Shared state the HTTP service reports back to Home Assistant. */
object State {
    @Volatile var ambient = false
    @Volatile var foreground = false
    @Volatile var kioskPaused = false
    /** The line under the clock on the sleep screen, last sent by Home Assistant. */
    @Volatile var ambientInfo = ""
}

class MainActivity : Activity() {

    private lateinit var cfg: Config
    private lateinit var web: WebView
    private lateinit var dock: LinearLayout
    private lateinit var content: LinearLayout
    private lateinit var ambient: AmbientView
    private lateinit var offline: TextView
    private lateinit var caption: TextView
    private var camIndicator: TextView? = null
    private var micIndicator: TextView? = null
    private val handler = Handler(Looper.getMainLooper())
    private var loadedUrl: String? = null
    private val retry = Runnable { web.reload() }
    private val hideCaption = Runnable { caption.visibility = View.GONE }

    // ---------------------------------------------------------------- lifecycle

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = Config(this)
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        handleProvision(intent)
        Kiosk.applyPolicies(this, cfg)
        buildUi()
        loadDashboard()
        Bus.listener = ::onCommand
        CameraStreamer.onStateChanged = { on -> Bus.post(Command.CameraState(on)) }
        ControlService.start(this)
    }

    override fun onResume() {
        super.onResume()
        State.foreground = true
        Bus.listener = ::onCommand
        hideSystemBars()
        Kiosk.applyPolicies(this, cfg) // picks up apps installed since the last launch
        if (!State.kioskPaused) Kiosk.enterLock(this, cfg)
        // We're on screen, so the service may claim camera and microphone access now and keep them in the background.
        ControlService.refreshForeground(this)
        showCameraState(CameraStreamer.running)
        showMicState(VoiceSatellite.running)
        // Settings may have changed while we were away.
        if (cfg.haUrl != loadedUrl) loadDashboard()
    }

    override fun onPause() {
        super.onPause()
        State.foreground = false
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    @Deprecated("Back stays inside the dashboard; a home app has nowhere to go back to.")
    override fun onBackPressed() {
        when {
            ambient.visibility == View.VISIBLE -> setAmbient(false)
            web.canGoBack() -> web.goBack()
            else -> Unit
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleProvision(intent)
        // Pressing home while already home: scroll the dashboard back to its first view.
        if (State.foreground && intent?.hasCategory(Intent.CATEGORY_HOME) == true) loadDashboard()
    }

    // ---------------------------------------------------------------- UI

    @SuppressLint("SetJavaScriptEnabled")
    private fun buildUi() {
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }

        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#101317"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.loadWithOverviewMode = true
            settings.useWideViewPort = true
            settings.builtInZoomControls = false
            isVerticalScrollBarEnabled = false
            webViewClient = DashboardClient()
        }
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(web, true)
        }

        dock = LinearLayout(this)   // styled and filled by layoutDock()

        content = LinearLayout(this)
        root.addView(content, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))

        offline = TextView(this).apply {
            text = "Can't reach Home Assistant. Retrying..."
            setTextColor(Color.parseColor("#9AA4AE"))
            textSize = 20f
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#101317"))
            visibility = View.GONE
            setOnClickListener { web.reload() }
        }
        root.addView(offline, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))

        ambient = AmbientView(this, cfg).apply { setOnClickListener { setAmbient(false) } }
        root.addView(ambient, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))

        // Voice caption: what was heard and what Assist answered, over everything else for a few seconds.
        caption = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 22f
            gravity = Gravity.CENTER
            setPadding(dp(28), dp(16), dp(28), dp(16))
            maxLines = 3
            background = GradientDrawable().apply {
                cornerRadius = dp(28).toFloat()
                setColor(Color.parseColor("#E0141A22"))
                setStroke(dp(1), Color.parseColor("#3316A3C9"))
            }
            visibility = View.GONE
            setOnClickListener { visibility = View.GONE }
        }
        root.addView(caption, FrameLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL).apply {
            bottomMargin = dp(36); leftMargin = dp(60); rightMargin = dp(60)
        })

        setContentView(root)
        layoutDock()
    }

    /**
     * Rebuilds the dock from config. Called at start and whenever config changes.
     *
     * The dock lines up with the dashboard beside it as a fourth column: the clock sits in the
     * dashboard's title row, the privacy lamps where the section headings are, and the tiles start
     * and end level with the dashboard's tiles (20 + 72 + 20 + 30 + 10 dp down, 45 dp off the bottom).
     */
    private fun layoutDock() {
        content.removeAllViews()
        dock.removeAllViews()
        val side = cfg.dockSide
        val bottom = side == "bottom"
        content.orientation = if (bottom) LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
        dock.orientation = if (bottom) LinearLayout.HORIZONTAL else LinearLayout.VERTICAL
        dock.background = Dock.background(side)
        when (side) {
            "bottom" -> dock.setPadding(dp(28), dp(4), dp(28), dp(20))
            "left" -> dock.setPadding(dp(24), dp(20), 0, dp(45))
            else -> dock.setPadding(0, dp(20), dp(24), dp(45))
        }

        // The clock doubles as the hidden settings handle: hold it for 3 seconds.
        val clock = TextClock(this).apply {
            format12Hour = "h:mm"
            format24Hour = "H:mm"
            setTextColor(Color.WHITE)
            textSize = 28f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            includeFontPadding = false
            gravity = Gravity.CENTER
            setOnTouchListener(SecretHold { askPin() })
        }

        // Privacy lamps: shown whenever the camera or the microphone is in use.
        camIndicator = indicator("\u25CF CAM", "#FF453A", CameraStreamer.running)
        micIndicator = indicator("\u25CF MIC", "#30D158", VoiceSatellite.running)
        val lamps = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            addView(camIndicator, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
            addView(micIndicator, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        }

        if (bottom) {
            val head = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                addView(clock, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
                addView(lamps, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(4) })
            }
            dock.addView(head, LinearLayout.LayoutParams(dp(120), MATCH_PARENT))
        } else {
            dock.addView(clock, LinearLayout.LayoutParams(MATCH_PARENT, dp(72)))
            dock.addView(lamps, LinearLayout.LayoutParams(MATCH_PARENT, dp(30)).apply { topMargin = dp(20) })
        }

        val tiles = cfg.tiles
        for (tile in tiles) {
            val lp = if (bottom) LinearLayout.LayoutParams(0, MATCH_PARENT, 1f).apply { leftMargin = dp(Dock.GAP_DP) }
                     else LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f).apply { topMargin = dp(Dock.GAP_DP) }
            dock.addView(Dock.tile(this, tile) { runTile(tile) }, lp)
        }
        // A short list leaves the rest of the dock empty instead of stretching its tiles.
        val spare = (if (bottom) Dock.SLOTS_BOTTOM else Dock.SLOTS_SIDE) - tiles.size
        if (spare > 0) {
            dock.addView(View(this), if (bottom) LinearLayout.LayoutParams(0, MATCH_PARENT, spare.toFloat())
                                     else LinearLayout.LayoutParams(MATCH_PARENT, 0, spare.toFloat()))
        }

        val webLp = if (bottom) LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f)
                    else LinearLayout.LayoutParams(0, MATCH_PARENT, 1f)
        val dockLp = if (bottom) LinearLayout.LayoutParams(MATCH_PARENT, dp(Dock.SIZE_DP))
                     else LinearLayout.LayoutParams(dp(Dock.SIZE_DP), MATCH_PARENT)
        (web.parent as? LinearLayout)?.removeView(web)
        if (side == "left") {
            content.addView(dock, dockLp); content.addView(web, webLp)
        } else {
            content.addView(web, webLp); content.addView(dock, dockLp)
        }
    }

    private fun indicator(label: String, color: String, on: Boolean) = TextView(this).apply {
        text = label
        setTextColor(Color.parseColor(color))
        textSize = 11f
        typeface = Typeface.DEFAULT_BOLD
        letterSpacing = 0.06f
        includeFontPadding = false
        gravity = Gravity.CENTER
        setPadding(dp(4), 0, dp(4), 0)
        visibility = if (on) View.VISIBLE else View.GONE
    }

    private fun hideSystemBars() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN)
        }
    }

    // ---------------------------------------------------------------- actions

    private fun loadDashboard() {
        loadedUrl = cfg.haUrl
        web.loadUrl(cfg.haUrl)
    }

    private fun runTile(tile: Tile) {
        when (tile.action) {
            "assist" -> openAssist()
            "reload" -> web.reload()
            "home" -> loadDashboard()
            "volume" -> Volume.showPanel(this)
            "volume_up" -> { Volume.step(this, cfg, true); Volume.showPanel(this) }
            "volume_down" -> { Volume.step(this, cfg, false); Volume.showPanel(this) }
            null -> tile.pkg?.let { openPackage(it, tile.label) }
            else -> toast("Unknown action ${tile.action}")
        }
    }

    /** [app] is a tile label (case-insensitive) or a package name. */
    private fun launch(app: String) {
        val tile = cfg.tiles.firstOrNull { it.label.equals(app, true) || it.pkg == app }
        if (tile != null) runTile(tile) else openPackage(app, app)
    }

    private fun openPackage(pkg: String, label: String) {
        val pm = packageManager
        val intent = pm.getLaunchIntentForPackage(pkg) ?: pm.getLeanbackLaunchIntentForPackage(pkg)
        if (intent == null) {
            toast("$label isn't installed")
            return
        }
        setAmbient(false)
        startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun openAssist() {
        try {
            startActivity(Intent(Intent.ACTION_ASSIST).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: Exception) {
            openPackage(Config.HA_COMPANION, "Home Assistant")
        }
    }

    private fun bringToFront() {
        startActivity(Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT))
    }

    private fun showCameraState(on: Boolean) {
        camIndicator?.visibility = if (on) View.VISIBLE else View.GONE
    }

    private fun showMicState(on: Boolean) {
        micIndicator?.visibility = if (on) View.VISIBLE else View.GONE
    }

    private fun setAmbient(on: Boolean) {
        State.ambient = on
        ambient.setActive(on)
    }

    /** Shows a line over everything for a few seconds (voice progress). */
    private fun showCaption(text: String, forMs: Long = 6000) {
        caption.text = text
        caption.visibility = View.VISIBLE
        handler.removeCallbacks(hideCaption)
        handler.postDelayed(hideCaption, forMs)
    }

    private fun onVoice(ev: VoiceSatellite.Event) {
        when (ev) {
            VoiceSatellite.Event.Started -> showMicState(true)
            VoiceSatellite.Event.Stopped -> { showMicState(false); caption.visibility = View.GONE }
            VoiceSatellite.Event.WakeWord -> { Kiosk.screenOn(this); showCaption("Listening…", 15_000) }
            is VoiceSatellite.Event.Heard -> showCaption("“${ev.text}”", 15_000)
            is VoiceSatellite.Event.Reply -> showCaption(ev.text.ifBlank { "Done" })
            is VoiceSatellite.Event.Error -> if (caption.visibility == View.VISIBLE) showCaption("Voice: ${ev.message}")
        }
    }

    private fun onCommand(cmd: Command) {
        when (cmd) {
            Command.Home -> { setAmbient(false); bringToFront(); loadDashboard() }
            Command.Reload -> web.reload()
            Command.WakeUp -> { bringToFront(); hideSystemBars() }
            is Command.Ambient -> { if (cmd.on) bringToFront(); setAmbient(cmd.on) }
            is Command.Launch -> launch(cmd.app)
            is Command.Navigate -> { setAmbient(false); bringToFront(); web.loadUrl(cmd.url) }
            Command.Assist -> openAssist()
            is Command.CameraState -> showCameraState(cmd.on)
            is Command.AmbientInfo -> ambient.setInfo(cmd.line)
            is Command.Voice -> onVoice(cmd.event)
            Command.ConfigChanged -> {
                Kiosk.applyPolicies(this, cfg)
                layoutDock()
                ambient.refresh()
                if (cfg.haUrl != loadedUrl) loadDashboard()
            }
        }
    }

    /**
     * setup.sh pushes the API token (and optionally the dashboard URL) once over adb:
     *   am start -n com.counterdisplay.launcher/.MainActivity --es provision_token X --es provision_url Y
     * After the first token is set this is ignored, so another app can't take over the API.
     */
    private fun handleProvision(i: Intent?) {
        val t = i?.getStringExtra("provision_token") ?: return
        if (cfg.provisioned) { toast("Already provisioned; change the token in settings"); return }
        if (t.length < 16) { toast("Token too short"); return }
        cfg.token = t
        i.getStringExtra("provision_url")?.takeIf { it.startsWith("http") }?.let { cfg.haUrl = it }
        i.getStringExtra("provision_cert_name")?.let { cfg.haCertName = it }
        cfg.provisioned = true
        ControlService.restartServer(this)
        toast("Provisioned")
    }

    private fun askPin() {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            hint = "PIN"
        }
        AlertDialog.Builder(this)
            .setTitle("Counter Home settings")
            .setView(input)
            .setPositiveButton("Open") { _, _ ->
                if (input.text.toString() == cfg.pin) {
                    startActivity(Intent(this, SettingsActivity::class.java))
                } else toast("Wrong PIN")
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    // ---------------------------------------------------------------- helpers

    private inner class DashboardClient : WebViewClient() {
        override fun onPageFinished(view: WebView?, url: String?) {
            offline.visibility = View.GONE
        }

        override fun onReceivedSslError(view: WebView?, h: SslErrorHandler, error: SslError) {
            if (Tls.acceptNameMismatch(cfg, error)) {
                h.proceed()
            } else {
                h.cancel()
                offline.visibility = View.VISIBLE
                handler.removeCallbacks(retry)
                handler.postDelayed(retry, 10_000)
            }
        }

        override fun onReceivedError(view: WebView?, req: WebResourceRequest?, err: WebResourceError?) {
            if (req?.isForMainFrame == true) {
                offline.visibility = View.VISIBLE
                handler.removeCallbacks(retry)
                handler.postDelayed(retry, 10_000)
            }
        }
    }

    /** Fires [action] after a 3 second hold with no lift. */
    private inner class SecretHold(private val action: () -> Unit) : View.OnTouchListener {
        private val fire = Runnable { action() }
        @SuppressLint("ClickableViewAccessibility")
        override fun onTouch(v: View, e: MotionEvent): Boolean {
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> handler.postDelayed(fire, 3000)
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> handler.removeCallbacks(fire)
            }
            return true
        }
    }

    private fun safeColor(s: String) = try { Color.parseColor(s) } catch (e: Exception) { Color.DKGRAY }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
