package com.counterdisplay.launcher

import android.app.ActivityOptions
import android.app.Notification
import android.app.PendingIntent
import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log

private const val TAG = "CounterHome"

/**
 * Video calls on the hub (Google Meet, or any calling app on a dock tile).
 *
 * While a call is up the hub keeps out of its way: the wake-word listener lets go of the microphone,
 * and Home Assistant can't turn the panel off or put up the sleep screen.
 */
object Calls {
    const val MEET = "com.google.android.apps.tachyon"

    /** True while any app holds a voice or video call (Meet switches the audio to communication mode). */
    fun inCall(ctx: Context): Boolean {
        val mode = ctx.getSystemService(AudioManager::class.java).mode
        return mode == AudioManager.MODE_IN_COMMUNICATION || mode == AudioManager.MODE_IN_CALL
    }
}

/**
 * Makes incoming calls ring on screen.
 *
 * Under the kiosk lock the status bar and heads-up notifications are off, so a calling app's
 * incoming-call banner never shows. This listener sees the call notification instead and opens its
 * full-screen intent (the app's own ringing screen) itself. It only acts on call notifications from
 * apps that have a dock tile, and leaves everything else alone.
 *
 * Android only lets it run once allowed: setup.sh does that with
 * `cmd notification allow_listener com.counterdisplay.launcher/.CallWatcher`.
 */
class CallWatcher : NotificationListenerService() {
    /** Notifications already opened, so an updated (still ringing) notification doesn't reopen it. */
    private val opened = mutableSetOf<String>()

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val n = sbn.notification ?: return
        if (n.category != Notification.CATEGORY_CALL) return
        val fsi = n.fullScreenIntent ?: return
        if (State.kioskPaused) return                     // normal notifications work while paused
        if (Calls.inCall(this)) return                    // an ongoing call, not a new one ringing
        if (!opened.add(sbn.key)) return
        val cfg = Config(this)
        if (cfg.tiles.none { it.pkg == sbn.packageName }) return

        Log.i(TAG, "incoming call from ${sbn.packageName}: opening its ringing screen")
        Kiosk.screenOn(this)
        Bus.post(Command.Ambient(false))
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                val opts = ActivityOptions.makeBasic().setPendingIntentBackgroundActivityStartMode(
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED).toBundle()
                fsi.send(this, 0, null, null, null, null, opts)
            } else {
                fsi.send()
            }
        } catch (e: PendingIntent.CanceledException) {
            Log.w(TAG, "incoming call screen already gone")
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        opened.remove(sbn.key)
    }
}
