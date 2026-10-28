package com.counterdisplay.launcher

import android.content.Context
import android.media.AudioManager
import android.util.Log

/**
 * Media volume cap. The tablet feeds the amp a line-level signal through the USB-C to 3.5 mm
 * adapter, so the tablet's media volume sets the amp's output. Capping it keeps the 15 W
 * full-range drivers from being overdriven when someone turns the volume all the way up.
 */
object Volume {
    /** Sent by the system on every volume change. Not in the public SDK, but stable since Android 4. */
    const val ACTION_CHANGED = "android.media.VOLUME_CHANGED_ACTION"
    const val EXTRA_STREAM = "android.media.EXTRA_VOLUME_STREAM_TYPE"

    private const val TAG = "CounterHome"
    private const val STREAM = AudioManager.STREAM_MUSIC

    private fun am(ctx: Context) = ctx.getSystemService(AudioManager::class.java)

    /** Highest allowed volume index for the current output, from the cap in percent. */
    private fun capIndex(ctx: Context, cfg: Config): Int {
        val max = am(ctx).getStreamMaxVolume(STREAM)
        return ((max * cfg.maxVolume + 50) / 100).coerceIn(1, max)
    }

    /** Pulls the media volume back down to the cap. Returns true if it had to. */
    fun enforce(ctx: Context, cfg: Config): Boolean {
        return try {
            val cap = capIndex(ctx, cfg)
            if (am(ctx).getStreamVolume(STREAM) > cap) {
                am(ctx).setStreamVolume(STREAM, cap, 0)
                true
            } else false
        } catch (e: Exception) {
            Log.w(TAG, "volume cap", e); false
        }
    }

    /** Current media volume as a percentage of the stream maximum. */
    fun percent(ctx: Context): Int {
        val max = am(ctx).getStreamMaxVolume(STREAM)
        return if (max > 0) am(ctx).getStreamVolume(STREAM) * 100 / max else 0
    }
}
