package com.counterdisplay.launcher

import android.content.ComponentName
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent
import org.json.JSONObject

/**
 * Play, pause and skip for whatever app is playing: Spotify, MassDroid (Music Assistant's Spotify
 * Connect / AirPlay player), YouTube TV.
 *
 * It talks to the apps' media sessions directly, which needs notification-listener access; the
 * [CallWatcher] listener already has it (setup.sh allows it). Android's own "media button" target is
 * the last app that asked for it (often MassDroid even while Spotify plays), so a plain media key
 * would go to the wrong app.
 *
 * YouTube TV's session doesn't follow what it plays: during live TV it says STOPPED and accepts no
 * commands. So when audio plays and no session admits to it, pausing takes the audio focus for a
 * moment instead: every well-behaved player (YouTube TV, Spotify, MassDroid) pauses when another app
 * takes the focus for good. Such an app can't be resumed from here; the sidebar's play button then
 * does nothing rather than start some other app.
 *
 * Safe from any thread.
 */
object Media {
    private const val TAG = "CounterHome"
    private const val FOCUS_HOLD_MS = 1500L
    private const val NO_RESUME_MS = 30 * 60_000L

    private val main = Handler(Looper.getMainLooper())
    /** When pause last had to take the audio focus (an app without a usable session), else 0. */
    @Volatile private var focusPausedAt = 0L

    private val ACTIVE = setOf(
        PlaybackState.STATE_PLAYING, PlaybackState.STATE_BUFFERING, PlaybackState.STATE_CONNECTING,
        PlaybackState.STATE_FAST_FORWARDING, PlaybackState.STATE_REWINDING,
        PlaybackState.STATE_SKIPPING_TO_NEXT, PlaybackState.STATE_SKIPPING_TO_PREVIOUS,
        PlaybackState.STATE_SKIPPING_TO_QUEUE_ITEM,
    )

    /** Media sessions, most recently active first. Empty when listener access is missing. */
    fun sessions(ctx: Context): List<MediaController> = try {
        ctx.getSystemService(MediaSessionManager::class.java)
            .getActiveSessions(ComponentName(ctx, CallWatcher::class.java))
    } catch (e: SecurityException) {
        Log.w(TAG, "media sessions need notification-listener access for CallWatcher")
        emptyList()
    }

    private fun MediaController.active() = playbackState?.state in ACTIVE

    private fun MediaController.canPause() =
        (playbackState?.actions ?: 0L) and (PlaybackState.ACTION_PAUSE or PlaybackState.ACTION_PLAY_PAUSE) != 0L

    /** No state reported at all, but it can pause (YouTube TV). */
    private fun MediaController.silent() =
        playbackState.let { it == null || it.state == PlaybackState.STATE_NONE } && canPause()

    /**
     * The sessions that are playing: those that say so, or, when audio plays and none say so, the
     * ones that report no state at all.
     */
    private fun playing(ctx: Context, s: List<MediaController> = sessions(ctx)): List<MediaController> {
        val sure = s.filter { it.active() }
        if (sure.isNotEmpty()) focusPausedAt = 0L          // a proper session plays again: play may resume it later
        if (sure.isNotEmpty() || !am(ctx).isMusicActive) return sure
        return s.filter { it.silent() }
    }

    private fun am(ctx: Context) = ctx.getSystemService(AudioManager::class.java)

    /** True while any app plays. */
    fun isPlaying(ctx: Context): Boolean = sessions(ctx).any { it.active() } || am(ctx).isMusicActive

    /** The session the buttons act on: the one playing, else the last one used. */
    private fun target(ctx: Context): MediaController? = sessions(ctx).let { s -> playing(ctx, s).firstOrNull() ?: s.firstOrNull() }

    /** Pauses everything that plays. Returns true if something was playing. */
    fun pause(ctx: Context): Boolean {
        val all = sessions(ctx)
        val playing = playing(ctx, all)
        for (c in playing) {
            Log.i(TAG, "pausing ${c.packageName}")
            // Some apps only offer stop; pause keeps the place in the song when it can.
            if (c.canPause()) c.transportControls.pause()
            else c.transportControls.stop()
        }
        // Audio with no session owning up to it (YouTube TV live): take the focus from whoever plays.
        if (all.none { it.active() } && am(ctx).isMusicActive && !Announcer.speaking) {
            takeFocus(ctx)
            return true
        }
        if (playing.isNotEmpty()) focusPausedAt = 0L
        return playing.isNotEmpty()
    }

    fun play(ctx: Context) {
        val c = target(ctx) ?: return key(ctx, KeyEvent.KEYCODE_MEDIA_PLAY)
        Log.i(TAG, "playing ${c.packageName}")
        c.transportControls.play()
    }

    /** Takes the media audio focus for a moment, so the app holding it pauses, then lets it go. */
    private fun takeFocus(ctx: Context) {
        val am = am(ctx)
        val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build())
            .setOnAudioFocusChangeListener({ }, main)
            .build()
        val got = am.requestAudioFocus(req)
        Log.i(TAG, "pausing by audio focus (no session playing), granted=$got")
        focusPausedAt = SystemClock.elapsedRealtime()
        main.postDelayed({ am.abandonAudioFocusRequest(req) }, FOCUS_HOLD_MS)
    }

    /**
     * The sidebar's middle button. After pausing an app that has no usable session, it doesn't
     * resume the last session, which would start a different app. POST /media/play still does.
     */
    fun playPause(ctx: Context) {
        if (isPlaying(ctx)) { pause(ctx); return }
        if (focusPausedAt != 0L && SystemClock.elapsedRealtime() - focusPausedAt < NO_RESUME_MS) {
            Log.i(TAG, "play: the paused app has no media session; resume it in the app")
            return
        }
        play(ctx)
    }

    fun next(ctx: Context) {
        target(ctx)?.transportControls?.skipToNext() ?: key(ctx, KeyEvent.KEYCODE_MEDIA_NEXT)
    }

    fun previous(ctx: Context) {
        target(ctx)?.transportControls?.skipToPrevious() ?: key(ctx, KeyEvent.KEYCODE_MEDIA_PREVIOUS)
    }

    fun stop(ctx: Context) {
        val all = sessions(ctx)
        playing(ctx, all).forEach { it.transportControls.stop() }
        if (all.none { it.active() } && am(ctx).isMusicActive && !Announcer.speaking) takeFocus(ctx)
    }

    /**
     * Going back to the dashboard (Home tile, POST /home, coming back from an app): stop the music,
     * as the setting asks. Never during a video call.
     */
    fun pauseForHome(ctx: Context, cfg: Config, why: String) {
        if (!cfg.pauseMediaOnHome || Calls.inCall(ctx)) return
        try {
            if (pause(ctx)) Log.i(TAG, "media paused: $why")
        } catch (e: Exception) {
            Log.w(TAG, "media pause failed", e)
        }
    }

    /** For GET /media and /status: what plays and in which app. */
    fun statusJson(ctx: Context): JSONObject {
        val o = JSONObject().put("playing", false)
        val all = try { sessions(ctx) } catch (e: Exception) { emptyList() }
        val now = playing(ctx, all)
        val music = am(ctx).isMusicActive
        // Audio with no session owning up to it: most likely the one session that isn't paused (YouTube TV says STOPPED).
        val guess = if (now.isEmpty() && music) all.firstOrNull {
            it.playbackState?.state !in setOf(PlaybackState.STATE_PAUSED, PlaybackState.STATE_ERROR)
        } else null
        val c = now.firstOrNull() ?: guess ?: all.firstOrNull() ?: return o.put("playing", music)
        val m = c.metadata
        val on = c in now || c === guess
        return o.put("playing", on)
            .put("app", c.packageName)
            .put("state", if (on && !c.active()) "playing" else stateName(c.playbackState?.state))
            .put("title", m?.getString(MediaMetadata.METADATA_KEY_TITLE) ?: "")
            .put("artist", m?.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: "")
    }

    private fun stateName(s: Int?) = when (s) {
        PlaybackState.STATE_PLAYING -> "playing"
        PlaybackState.STATE_PAUSED -> "paused"
        PlaybackState.STATE_STOPPED -> "stopped"
        PlaybackState.STATE_BUFFERING, PlaybackState.STATE_CONNECTING -> "buffering"
        PlaybackState.STATE_ERROR -> "error"
        null, PlaybackState.STATE_NONE -> "none"
        else -> "other"
    }

    private fun key(ctx: Context, code: Int) {
        val t = SystemClock.uptimeMillis()
        am(ctx).dispatchMediaKeyEvent(KeyEvent(t, t, KeyEvent.ACTION_DOWN, code, 0))
        am(ctx).dispatchMediaKeyEvent(KeyEvent(t, t, KeyEvent.ACTION_UP, code, 0))
    }
}
