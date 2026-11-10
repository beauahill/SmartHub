package com.counterdisplay.launcher

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Typeface
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Swipe in from the right edge, over any app, for a volume slider.
 *
 * A thin invisible strip sits on the right edge of the screen above every app (Spotify, YouTube TV,
 * the dashboard). Drag left out of it and a glass slider slides in; keep the finger down and move up
 * or down to change the volume in the same gesture, or let go and drag the slider itself. It slides
 * away a few seconds after the last touch, or at once when you touch anywhere else. The dock's
 * Volume tile opens the same slider.
 *
 * The slider runs from silent to the speaker cap ([Config.maxVolume]), so the top is the loudest the
 * speakers are allowed, and its percent is of that range.
 *
 * It needs the "display over other apps" permission, which only adb can grant on the kiosk:
 * setup.sh runs `appops set com.counterdisplay.launcher SYSTEM_ALERT_WINDOW allow`. Without it the
 * strip is left out and the Volume tile falls back to Android's own volume panel.
 *
 * Main thread only. [ControlService] owns it, so it lives as long as the service.
 */
object VolumeOverlay {
    private const val TAG = "CounterHome"
    private const val EDGE_DP = 16              // width of the touch strip
    private const val EDGE_FRACTION = 0.7f      // the middle 70 % of the edge; corners stay with the apps
    private const val GESTURE_GUARD_DP = 200    // Android lets a window keep this much edge from the back gesture
    private const val OPEN_DP = 24              // leftward travel before the slider opens
    private const val PANEL_W_DP = 88
    private const val PANEL_H_DP = 330
    private const val MARGIN_DP = 28            // from the right edge, clear of the dock's tiles
    private const val HIDE_MS = 2500L

    private val main = Handler(Looper.getMainLooper())
    private var app: Context? = null
    private var cfg: Config? = null
    private var wm: WindowManager? = null
    private var edge: View? = null
    private var panel: PanelView? = null
    private var panelShown = false

    // Drag state: the slider level follows the finger by how far it moved, not where it is.
    private var dragY = 0f
    private var dragLevel = 0f
    private var dragging = false

    private val hideLater = Runnable { hide() }

    fun allowed(ctx: Context) = Settings.canDrawOverlays(ctx)

    /** Puts the edge strip up or takes it down to match settings and the overlay permission. */
    fun sync(ctx: Context) {
        val c = ctx.applicationContext
        if (app == null) {
            app = c
            cfg = Config(c)
            wm = c.getSystemService(WindowManager::class.java)
        }
        val want = cfg!!.edgeVolume && allowed(c)
        if (want && edge == null) addEdge() else if (!want && edge != null) removeEdge()
    }

    /** Opens the slider (the Volume tile). Returns false when the overlay isn't allowed, so the caller can fall back. */
    fun show(ctx: Context): Boolean {
        sync(ctx)
        if (!allowed(ctx)) return false
        open()
        main.removeCallbacks(hideLater)
        main.postDelayed(hideLater, HIDE_MS)
        return true
    }

    /** The volume changed somewhere else (side keys, Home Assistant): move the slider to match. */
    fun refresh() {
        val p = panel ?: return
        if (panelShown && !dragging) p.level = Volume.level(app!!, cfg!!)
    }

    fun release() {
        main.removeCallbacks(hideLater)
        removeEdge()
        panel?.let { p -> p.animate().cancel(); detach(p) }
        panel = null
        panelShown = false
    }

    // ---------------------------------------------------------------- edge strip

    @SuppressLint("ClickableViewAccessibility")
    private fun addEdge() {
        val ctx = app ?: return
        val height = (ctx.resources.displayMetrics.heightPixels * EDGE_FRACTION).toInt()
        var downX = 0f
        var downY = 0f
        var opened = false
        val v = View(ctx)
        v.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { downX = e.rawX; downY = e.rawY; opened = false }
                MotionEvent.ACTION_MOVE -> {
                    val dx = downX - e.rawX
                    if (!opened && dx > dp(OPEN_DP) && dx > abs(e.rawY - downY)) {
                        opened = true
                        open()
                        startDrag(e.rawY)
                    }
                    if (opened) drag(e.rawY)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> if (opened) endDrag()
            }
            true
        }
        // Under gesture navigation the right edge is also "back"; keep the middle of the strip for us.
        v.addOnLayoutChangeListener { view, _, _, _, _, _, _, _, _ ->
            val guard = minOf(view.height, dp(GESTURE_GUARD_DP))
            val top = (view.height - guard) / 2
            view.systemGestureExclusionRects = listOf(Rect(0, top, view.width, top + guard))
        }
        val lp = overlayParams(dp(EDGE_DP), height, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE).apply {
            gravity = Gravity.END or Gravity.CENTER_VERTICAL
            title = "CounterHome volume edge"
        }
        try {
            wm!!.addView(v, lp)
            edge = v
        } catch (e: Exception) {
            Log.w(TAG, "volume edge not added", e)
        }
    }

    private fun removeEdge() {
        edge?.let { detach(it) }
        edge = null
    }

    // ---------------------------------------------------------------- slider panel

    @SuppressLint("ClickableViewAccessibility")
    private fun open() {
        val ctx = app ?: return
        val p = panel ?: PanelView(ctx).also { panel = it }
        p.level = Volume.level(ctx, cfg!!)
        if (!panelShown) {
            p.animate().cancel()
            if (p.parent == null) {
                p.setOnTouchListener { _, e ->
                    when (e.actionMasked) {
                        MotionEvent.ACTION_OUTSIDE -> hide()
                        MotionEvent.ACTION_DOWN -> startDrag(e.rawY)
                        MotionEvent.ACTION_MOVE -> drag(e.rawY)
                        MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> endDrag()
                    }
                    true
                }
                val lp = overlayParams(dp(PANEL_W_DP), dp(PANEL_H_DP),
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                        WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                        WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH).apply {
                    gravity = Gravity.END or Gravity.CENTER_VERTICAL
                    x = dp(MARGIN_DP)
                    title = "CounterHome volume"
                }
                try { wm!!.addView(p, lp) } catch (e: Exception) { Log.w(TAG, "volume panel not added", e); return }
                p.translationX = dp(PANEL_W_DP + MARGIN_DP).toFloat()
                p.alpha = 0f
            }
            p.animate().translationX(0f).alpha(1f).setDuration(180)
                .setInterpolator(DecelerateInterpolator()).withEndAction(null).start()
            panelShown = true
        }
        main.removeCallbacks(hideLater)
    }

    private fun hide() {
        main.removeCallbacks(hideLater)
        val p = panel ?: return
        if (!panelShown) return
        panelShown = false
        dragging = false
        p.animate().translationX(dp(PANEL_W_DP + MARGIN_DP).toFloat()).alpha(0f).setDuration(160)
            .withEndAction { if (!panelShown) detach(p) }.start()
    }

    private fun startDrag(y: Float) {
        main.removeCallbacks(hideLater)
        dragging = true
        dragY = y
        dragLevel = Volume.level(app!!, cfg!!)
    }

    private fun drag(y: Float) {
        val p = panel ?: return
        if (!dragging) startDrag(y)
        dragLevel = (dragLevel + (dragY - y) / p.trackHeight()).coerceIn(0f, 1f)
        dragY = y
        p.level = dragLevel
        Volume.setLevel(app!!, cfg!!, dragLevel)
    }

    private fun endDrag() {
        dragging = false
        panel?.level = Volume.level(app!!, cfg!!)     // settle on the step the volume actually landed on
        main.removeCallbacks(hideLater)
        main.postDelayed(hideLater, HIDE_MS)
    }

    // ---------------------------------------------------------------- helpers

    private fun overlayParams(w: Int, h: Int, flags: Int) = WindowManager.LayoutParams(
        w, h,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        flags or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
        PixelFormat.TRANSLUCENT
    ).apply {
        layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
    }

    private fun detach(v: View) {
        try { wm?.removeView(v) } catch (_: Exception) { }
    }

    private fun dp(v: Int) = (v * app!!.resources.displayMetrics.density).roundToInt()

    /**
     * The slider: the dock's dark glass, a percent at the top, a white fill rising in a pill-shaped
     * track, and the volume glyph underneath.
     */
    private class PanelView(ctx: Context) : View(ctx) {
        private val d = ctx.resources.displayMetrics.density
        private val glass = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xF0161822.toInt() }   // denser than the dock: it sits on video and tile labels
        private val edgeLine = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeWidth = (0.5f * d).coerceAtLeast(1f); color = 0x30FFFFFF
        }
        private val track = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x24FFFFFF }
        private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xEBFFFFFF.toInt() }
        private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = 0xF5FFFFFF.toInt()
            textSize = 16f * d
            textAlign = Paint.Align.CENTER
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        }
        private val iconOn = ctx.getDrawable(R.drawable.dock_volume)!!.mutate().apply { setTint(0xDBFFFFFF.toInt()) }
        private val iconOff = ctx.getDrawable(R.drawable.dock_volume_off)!!.mutate().apply { setTint(0xDBFFFFFF.toInt()) }
        private val box = RectF()
        private val trackBox = RectF()
        private val clip = Path()

        var level = 0f
            set(v) { val c = v.coerceIn(0f, 1f); if (c != field) { field = c; invalidate() } }

        private val pad get() = 14f * d
        private val trackTop get() = 48f * d
        private val trackBottom get() = height - 60f * d

        fun trackHeight() = (trackBottom - trackTop).coerceAtLeast(1f)

        override fun onDraw(canvas: Canvas) {
            val w = width.toFloat()
            val h = height.toFloat()
            box.set(0f, 0f, w, h)
            val r = 30f * d
            canvas.drawRoundRect(box, r, r, glass)
            box.inset(edgeLine.strokeWidth / 2, edgeLine.strokeWidth / 2)
            canvas.drawRoundRect(box, r, r, edgeLine)

            canvas.drawText("${(level * 100).roundToInt()}%", w / 2, 32f * d, text)

            trackBox.set(pad, trackTop, w - pad, trackBottom)
            val tr = trackBox.width() / 2.6f
            canvas.drawRoundRect(trackBox, tr, tr, track)
            if (level > 0f) {
                clip.reset()
                clip.addRoundRect(trackBox, tr, tr, Path.Direction.CW)
                canvas.save()
                canvas.clipPath(clip)
                canvas.drawRect(trackBox.left, trackBottom - trackHeight() * level, trackBox.right, trackBottom, fill)
                canvas.restore()
            }

            val icon = if (level > 0f) iconOn else iconOff
            val s = (26f * d).toInt()
            val cx = (w / 2).toInt()
            val cy = (h - 30f * d).toInt()
            icon.setBounds(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2)
            icon.draw(canvas)
        }
    }
}
