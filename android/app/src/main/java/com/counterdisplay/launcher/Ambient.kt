package com.counterdisplay.launcher

import android.animation.ObjectAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.Shader
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextClock
import android.widget.TextView
import java.io.File
import java.security.MessageDigest
import java.util.Calendar
import java.util.concurrent.Executors
import kotlin.math.hypot
import kotlin.random.Random

/**
 * The sleep screen: a wallpaper that changes every few minutes behind the time, the date and a line
 * Home Assistant sends (outdoor temperature and conditions, see POST /ambient/info). Tap to dismiss.
 *
 * Wallpapers come from three places, mixed at random:
 *  - pictures pushed to the tablet (PUT /wallpapers/<name>, or adb push to [wallpaperDir])
 *  - image URLs in the settings ([Config.wallpaperUrls]), cached on first use
 *  - built-in gradients, whose palette follows the time of day, so there is always something to show
 */
class AmbientView(ctx: Context, private val cfg: Config) : FrameLayout(ctx) {

    private val back = ImageView(ctx).apply { scaleType = ImageView.ScaleType.CENTER_CROP }
    private val front = ImageView(ctx).apply { scaleType = ImageView.ScaleType.CENTER_CROP; alpha = 0f }
    private val info = TextView(ctx)
    private val handler = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private var active = false
    private var lastKey: String? = null
    private val rotate = object : Runnable {
        override fun run() {
            if (!active) return
            next()
            handler.postDelayed(this, cfg.ambientIntervalMin * 60_000L)
        }
    }

    init {
        setBackgroundColor(Color.BLACK)
        visibility = View.GONE
        addView(back, LayoutParams(MATCH_PARENT, MATCH_PARENT))
        addView(front, LayoutParams(MATCH_PARENT, MATCH_PARENT))

        // Dark scrim along the bottom so white text reads on any picture.
        val scrim = View(ctx).apply {
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(Color.TRANSPARENT, 0x66000000, 0xB3000000.toInt()))
        }
        addView(scrim, LayoutParams(MATCH_PARENT, dp(360), Gravity.BOTTOM))

        val col = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(56), 0, dp(56), dp(44))
        }
        col.addView(TextClock(ctx).apply {
            format12Hour = "h:mm"; format24Hour = "H:mm"
            setTextColor(Color.WHITE)
            textSize = 132f
            typeface = Typeface.create("sans-serif-thin", Typeface.NORMAL)
            includeFontPadding = false
            setShadowLayer(18f, 0f, 4f, 0x80000000.toInt())
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        col.addView(TextClock(ctx).apply {
            format12Hour = "EEEE, MMMM d"; format24Hour = "EEEE, d MMMM"
            setTextColor(0xF0FFFFFF.toInt())
            textSize = 30f
            typeface = Typeface.create("sans-serif-light", Typeface.NORMAL)
            setShadowLayer(12f, 0f, 2f, 0x80000000.toInt())
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(2) })
        col.addView(info.apply {
            setTextColor(0xE0FFFFFF.toInt())
            textSize = 30f
            typeface = Typeface.create("sans-serif", Typeface.NORMAL)
            setShadowLayer(12f, 0f, 2f, 0x80000000.toInt())
            text = State.ambientInfo
            visibility = if (State.ambientInfo.isEmpty()) View.GONE else View.VISIBLE
        }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(10) })
        addView(col, LayoutParams(WRAP_CONTENT, WRAP_CONTENT, Gravity.BOTTOM or Gravity.START))
    }

    /** The line under the date, e.g. "44°F · Sunny". Empty hides it. */
    fun setInfo(line: String) {
        info.text = line
        info.visibility = if (line.isEmpty()) View.GONE else View.VISIBLE
    }

    /** Shows or hides the screen and starts or stops the wallpaper rotation. */
    fun setActive(on: Boolean) {
        if (on == active && (visibility == View.VISIBLE) == on) return
        active = on
        handler.removeCallbacks(rotate)
        if (on) {
            visibility = View.VISIBLE
            next()
            handler.postDelayed(rotate, cfg.ambientIntervalMin * 60_000L)
        } else {
            visibility = View.GONE
        }
    }

    /** Settings changed: restart the timer with the new interval. */
    fun refresh() {
        if (!active) return
        handler.removeCallbacks(rotate)
        handler.postDelayed(rotate, cfg.ambientIntervalMin * 60_000L)
    }

    // ---------------------------------------------------------------- wallpapers

    private fun next() {
        val w = width.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
        val h = height.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
        io.execute {
            val bmp = try { pick(w, h) } catch (e: Exception) {
                Log.w(TAG, "wallpaper failed: ${e.message}"); gradient(w, h, Random.Default)
            }
            handler.post { show(bmp) }
        }
    }

    private fun show(bmp: Bitmap) {
        if (!active) { bmp.recycle(); return }
        front.setImageBitmap(bmp)
        front.alpha = 0f
        ObjectAnimator.ofFloat(front, View.ALPHA, 0f, 1f).apply {
            duration = 1500
            start()
        }
        handler.postDelayed({
            // Move the new picture to the back layer so the next one can fade over it.
            val old = (back.drawable as? android.graphics.drawable.BitmapDrawable)?.bitmap
            back.setImageBitmap(bmp)
            front.setImageDrawable(null)
            front.alpha = 0f
            old?.takeIf { it != bmp }?.recycle()
        }, 1600)
    }

    /** One wallpaper, chosen at random from every source, never the same one twice in a row. */
    private fun pick(w: Int, h: Int): Bitmap {
        val files = wallpaperDir(context).listFiles { f -> f.isFile && f.extension.lowercase() in IMAGE_EXT }
            ?.map { "file:" + it.absolutePath } ?: emptyList()
        val urls = cfg.wallpaperUrls.map { "url:$it" }
        val gradients = List(if (files.isEmpty() && urls.isEmpty()) 6 else 2) { "gradient:$it" }
        val all = files + urls + gradients
        var key = all.random()
        if (all.size > 1 && key == lastKey) key = (all - key).random()
        lastKey = key
        return when {
            key.startsWith("file:") -> decode(File(key.removePrefix("file:")).readBytes(), w, h)
            key.startsWith("url:") -> decode(cached(key.removePrefix("url:")), w, h)
            else -> gradient(w, h, Random(key.hashCode() + Calendar.getInstance().get(Calendar.HOUR_OF_DAY)))
        }
    }

    /** Downloads a URL once and keeps it in the cache directory. */
    private fun cached(url: String): ByteArray {
        val dir = File(context.cacheDir, "wallpapers").apply { mkdirs() }
        val f = File(dir, sha1(url))
        if (f.exists()) return f.readBytes()
        val bytes = Net.fetch(cfg, url, cfg.haToken.takeIf { it.isNotEmpty() && url.startsWith(cfg.haBase()) })
        f.writeBytes(bytes)
        return bytes
    }

    private fun decode(bytes: ByteArray, w: Int, h: Int): Bitmap {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        while (bounds.outWidth / (sample * 2) >= w && bounds.outHeight / (sample * 2) >= h) sample *= 2
        val opts = BitmapFactory.Options().apply { inSampleSize = sample; inPreferredConfig = Bitmap.Config.ARGB_8888 }
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts) ?: throw IllegalArgumentException("not an image")
    }

    /**
     * A soft "mesh" gradient: a dark base with a few blurred colour glows. The palette follows the
     * clock: cool blues at night, teal and gold in the morning, sky blue by day, violet and amber
     * in the evening.
     */
    private fun gradient(w: Int, h: Int, rnd: Random): Bitmap {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val (base, glows) = when (hour) {
            in 5..10 -> (0xFF0E1A26.toInt() to 0xFF07101A.toInt()) to listOf(0xFF1C8C96.toInt(), 0xFFD9A441.toInt(), 0xFF2B5C8A.toInt())
            in 11..16 -> (0xFF0F1B2E.toInt() to 0xFF0A1322.toInt()) to listOf(0xFF2F7FD6.toInt(), 0xFF1FB3C9.toInt(), 0xFFE0A030.toInt())
            in 17..20 -> (0xFF160F24.toInt() to 0xFF0B0914.toInt()) to listOf(0xFF6C3FB0.toInt(), 0xFFC2457A.toInt(), 0xFFE0702E.toInt())
            else -> (0xFF0E121E.toInt() to 0xFF080A12.toInt()) to listOf(0xFF147896.toInt(), 0xFF5A3FA8.toInt(), 0xFF1E3C78.toInt())
        }
        // Render small and let the ImageView scale it: cheap, and the scaling smooths the gradients.
        val sw = 480; val sh = (480L * h / w).toInt().coerceAtLeast(200)
        val bmp = Bitmap.createBitmap(sw, sh, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        p.shader = LinearGradient(0f, 0f, 0f, sh.toFloat(), base.first, base.second, Shader.TileMode.CLAMP)
        c.drawRect(0f, 0f, sw.toFloat(), sh.toFloat(), p)
        for (color in glows) {
            val cx = rnd.nextFloat() * sw; val cy = rnd.nextFloat() * sh
            val r = (0.45f + rnd.nextFloat() * 0.35f) * hypot(sw.toFloat(), sh.toFloat()) / 2
            val a = 0x70 + rnd.nextInt(0x40)
            p.shader = RadialGradient(cx, cy, r, intArrayOf(withAlpha(color, a), withAlpha(color, a / 3), Color.TRANSPARENT),
                floatArrayOf(0f, 0.45f, 1f), Shader.TileMode.CLAMP)
            c.drawCircle(cx, cy, r, p)
        }
        return bmp
    }

    private fun withAlpha(color: Int, a: Int) = (color and 0x00FFFFFF) or (a.coerceIn(0, 255) shl 24)
    private fun sha1(s: String) = MessageDigest.getInstance("SHA-1").digest(s.toByteArray()).joinToString("") { "%02x".format(it) }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    companion object {
        private const val TAG = "CounterHome"
        val IMAGE_EXT = setOf("jpg", "jpeg", "png", "webp")

        /** Pictures live in the app's external files folder, reachable with adb push and the API. */
        fun wallpaperDir(ctx: Context): File =
            File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "wallpapers").apply { mkdirs() }
    }
}
