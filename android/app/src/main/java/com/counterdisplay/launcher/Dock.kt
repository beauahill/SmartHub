package com.counterdisplay.launcher

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/**
 * The look of the dock. It is drawn as one more column of the dashboard: the same wallpaper
 * colours behind it and the same dark glass tiles, each with a glyph in a circle and a short
 * label. Nothing here is a solid block of colour; a tile's colour only tints its glyph.
 */
object Dock {
    /** Thickness of the dock: its width on the left or right, its height along the bottom. */
    const val SIZE_DP = 108
    /** Tiles are sized as if this many shared the dock, so a short list doesn't stretch. */
    const val SLOTS_SIDE = 6
    const val SLOTS_BOTTOM = 10
    const val GAP_DP = 10

    /**
     * The dashboard wallpaper's colours along each edge, so the dock continues the picture next
     * to it. homeassistant/dashboards/wallpaper/make_wallpaper.py prints the right-hand column;
     * change these with it. Right and left run top to bottom, bottom runs left to right.
     */
    private val EDGE_RIGHT = colors("#42348F", "#4B358C", "#6D3880", "#6F3980", "#AF5F5B", "#C36B51")
    private val EDGE_LEFT = colors("#09507C", "#084A76", "#093463", "#083361", "#081E42", "#081838")
    private val EDGE_BOTTOM = colors("#081838", "#101E45", "#332A63", "#342A63", "#9E5A58", "#C26A50")

    private const val GLASS = 0x70161822          // the dashboard's tile: rgba(22, 24, 34, 0.44)
    private const val GLASS_EDGE = 0x24FFFFFF     // hairline highlight around a tile
    private const val CIRCLE = 0x1FFFFFFF         // the disc behind a glyph, white at 12%
    private const val PRESSED = 0x38FFFFFF
    private const val TEXT = 0xF5FFFFFF.toInt()
    private const val GLYPH = 0xDBFFFFFF.toInt()  // an untinted glyph, white at 86%

    private val ICONS = mapOf(
        "music" to R.drawable.dock_music,
        "tv" to R.drawable.dock_tv,
        "play" to R.drawable.dock_play,
        "radio" to R.drawable.dock_radio,
        "volume" to R.drawable.dock_volume,
        "mic" to R.drawable.dock_mic,
        "home" to R.drawable.dock_home,
        "reload" to R.drawable.dock_reload,
        "video" to R.drawable.dock_video,
        "globe" to R.drawable.dock_globe,
        "apps" to R.drawable.dock_apps,
    )

    /** What sits behind the tiles, for a dock on [side] ("right", "left" or "bottom"). */
    fun background(side: String): Drawable = when (side) {
        "bottom" -> GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, EDGE_BOTTOM)
        "left" -> GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, EDGE_LEFT)
        else -> GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, EDGE_RIGHT)
    }

    /** One tile: a glass rounded rectangle with the glyph in a circle above the label. */
    fun tile(ctx: Context, tile: Tile, onClick: () -> Unit): View {
        val density = ctx.resources.displayMetrics.density
        fun dp(v: Float) = (v * density).toInt()
        val radius = 20f * density

        val glyph = ImageView(ctx).apply {
            setImageResource(iconFor(tile))
            imageTintList = ColorStateList.valueOf(tint(tile.color))
            setPadding(dp(9f), dp(9f), dp(9f), dp(9f))
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(CIRCLE) }
        }
        val label = TextView(ctx).apply {
            text = tile.label
            setTextColor(TEXT)
            textSize = 12.5f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            gravity = Gravity.CENTER
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
            includeFontPadding = false
        }
        return LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(4f), 0, dp(4f), 0)
            val glass = GradientDrawable().apply {
                cornerRadius = radius
                setColor(GLASS)
                setStroke(dp(0.5f).coerceAtLeast(1), GLASS_EDGE)
            }
            val mask = GradientDrawable().apply { cornerRadius = radius; setColor(Color.WHITE) }
            background = RippleDrawable(ColorStateList.valueOf(PRESSED), glass, mask)
            addView(glyph, LinearLayout.LayoutParams(dp(40f), dp(40f)))
            addView(label, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(7f) })
            contentDescription = tile.label
            setOnClickListener { onClick() }
        }
    }

    /** The glyph for a tile: its "icon" if it names one, otherwise a guess from what it opens. */
    fun iconFor(tile: Tile): Int = ICONS[tile.icon?.lowercase() ?: guess(tile)] ?: R.drawable.dock_apps

    private fun guess(tile: Tile): String {
        when (tile.action) {
            "assist" -> return "mic"
            "reload" -> return "reload"
            "home" -> return "home"
            "volume", "volume_up", "volume_down" -> return "volume"
        }
        val s = "${tile.label} ${tile.pkg ?: ""}".lowercase()
        fun has(vararg words: String) = words.any { it in s }
        return when {
            has("radio", "audacy", "tunein", "iheart") -> "radio"
            has("spotify", "music", "pandora", "tidal") -> "music"
            has("unplugged", "live tv") -> "tv"
            has("iptv", "ott", "netflix", "plex", "kodi", "youtube", "tv") -> "play"
            has("camera", "meet", "zoom", "video") -> "video"
            has("chrome", "browser", "web") -> "globe"
            else -> "apps"
        }
    }

    /**
     * A tile's colour as a glyph tint: same hue, lifted to full brightness and softened, so any
     * colour reads on dark glass and the set sits together. Greys and bad values become white.
     */
    fun tint(color: String): Int {
        val c = try { Color.parseColor(color) } catch (e: Exception) { return GLYPH }
        val hsv = FloatArray(3)
        Color.colorToHSV(c, hsv)
        if (hsv[1] < 0.28f) return GLYPH
        hsv[1] = hsv[1].coerceAtMost(0.62f)
        hsv[2] = 1f
        return Color.HSVToColor(hsv)
    }

    private fun colors(vararg hex: String) = IntArray(hex.size) { Color.parseColor(hex[it]) }
}
