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
import android.webkit.CookieManager
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
}

class MainActivity : Activity() {

    private lateinit var cfg: Config
    private lateinit var web: WebView
    private lateinit var dock: LinearLayout
    private lateinit var content: LinearLayout
    private lateinit var ambient: FrameLayout
    private lateinit var offline: TextView
    private val handler = Handler(Looper.getMainLooper())
    private var loadedUrl: String? = null
    private val retry = Runnable { web.reload() }

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
        ControlService.start(this)
    }

    override fun onResume() {
        super.onResume()
        State.foreground = true
        Bus.listener = ::onCommand
        hideSystemBars()
        Kiosk.applyPolicies(this, cfg) // picks up apps installed since the last launch
        if (!State.kioskPaused) Kiosk.enterLock(this, cfg)
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

        dock = LinearLayout(this).apply {
            setBackgroundColor(Color.parseColor("#0C0E11"))
            setPadding(dp(10), dp(10), dp(10), dp(10))
        }

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

        ambient = buildAmbient()
        root.addView(ambient, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))

        setContentView(root)
        layoutDock()
    }

    /** Rebuilds the dock from config. Called at start and whenever config changes. */
    private fun layoutDock() {
        content.removeAllViews()
        dock.removeAllViews()
        val bottom = cfg.dockSide == "bottom"
        content.orientation = if (bottom) LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
        dock.orientation = if (bottom) LinearLayout.HORIZONTAL else LinearLayout.VERTICAL

        // The clock doubles as the hidden settings handle: hold it for 3 seconds.
        val clock = TextClock(this).apply {
            format12Hour = "h:mm"
            format24Hour = "H:mm"
            setTextColor(Color.parseColor("#E8E8E8"))
            textSize = 26f
            typeface = Typeface.create("sans-serif-light", Typeface.NORMAL)
            gravity = Gravity.CENTER
            setOnTouchListener(SecretHold { askPin() })
        }
        dock.addView(clock, if (bottom) LinearLayout.LayoutParams(dp(130), MATCH_PARENT)
                            else LinearLayout.LayoutParams(MATCH_PARENT, dp(64)))

        for (tile in cfg.tiles) {
            val b = TextView(this).apply {
                text = tile.label
                setTextColor(Color.WHITE)
                textSize = 18f
                typeface = Typeface.DEFAULT_BOLD
                gravity = Gravity.CENTER
                background = GradientDrawable().apply {
                    cornerRadius = dp(18).toFloat()
                    setColor(safeColor(tile.color))
                }
                setOnClickListener { runTile(tile) }
            }
            val lp = if (bottom) LinearLayout.LayoutParams(0, MATCH_PARENT, 1f)
                     else LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f)
            lp.setMargins(dp(4), dp(4), dp(4), dp(4))
            dock.addView(b, lp)
        }

        val webLp = if (bottom) LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f)
                    else LinearLayout.LayoutParams(0, MATCH_PARENT, 1f)
        val dockLp = if (bottom) LinearLayout.LayoutParams(MATCH_PARENT, dp(110))
                     else LinearLayout.LayoutParams(dp(150), MATCH_PARENT)
        (web.parent as? LinearLayout)?.removeView(web)
        if (cfg.dockSide == "left") {
            content.addView(dock, dockLp); content.addView(web, webLp)
        } else {
            content.addView(web, webLp); content.addView(dock, dockLp)
        }
    }

    private fun buildAmbient(): FrameLayout {
        val frame = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
            visibility = View.GONE
            setOnClickListener { setAmbient(false) }
        }
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
        }
        col.addView(TextClock(this).apply {
            format12Hour = "h:mm"; format24Hour = "H:mm"
            setTextColor(Color.parseColor("#6E747A"))
            textSize = 120f
            typeface = Typeface.create("sans-serif-thin", Typeface.NORMAL)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        col.addView(TextClock(this).apply {
            format12Hour = "EEEE, MMM d"; format24Hour = "EEEE, d MMM"
            setTextColor(Color.parseColor("#4A4F55"))
            textSize = 28f
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        frame.addView(col, FrameLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT, Gravity.CENTER))
        return frame
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

    private fun setAmbient(on: Boolean) {
        State.ambient = on
        ambient.visibility = if (on) View.VISIBLE else View.GONE
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
            Command.ConfigChanged -> {
                Kiosk.applyPolicies(this, cfg)
                layoutDock()
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
