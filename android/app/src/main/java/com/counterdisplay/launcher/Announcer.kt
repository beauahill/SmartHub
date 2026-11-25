package com.counterdisplay.launcher

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger

/**
 * Spoken announcements from Home Assistant ("The single garage door is opening."), the same lines
 * the Alexa group reads out. Uses the tablet's own text-to-speech, so it works with nothing playing,
 * the screen off, or Spotify / YouTube TV in front: those are ducked while it speaks and come back after.
 *
 * Optionally raises the media volume to a floor for the announcement (never above the cap) and puts
 * it back when the queue is empty.
 */
object Announcer {
    private const val TAG = "CounterHome"
    private const val GOOGLE_TTS = "com.google.android.tts"

    private var tts: TextToSpeech? = null
    private var ready = false
    private val pending = ArrayList<Pair<String, Int?>>()
    private val queued = AtomicInteger(0)

    /** True while an announcement is queued or speaking (its speech counts as music playing). */
    val speaking get() = queued.get() > 0
    private var focus: AudioFocusRequest? = null
    private var restoreVolume: Int? = null
    private lateinit var app: Context
    private lateinit var cfg: Config

    private val attrs = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANT)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
        .build()

    /** Queues [text]. [volumeFloor] is a percent the media volume is raised to while speaking, if lower. */
    @Synchronized
    fun say(ctx: Context, config: Config, text: String, volumeFloor: Int?) {
        app = ctx.applicationContext; cfg = config
        if (tts == null) init()
        if (!ready) { pending += text to volumeFloor; return }
        speak(text, volumeFloor)
    }

    private fun init() {
        val engine = try {
            app.packageManager.getPackageInfo(GOOGLE_TTS, 0); GOOGLE_TTS
        } catch (_: Exception) { null }
        val listener = TextToSpeech.OnInitListener { status -> onInit(status) }
        tts = if (engine != null) TextToSpeech(app, listener, engine) else TextToSpeech(app, listener)
    }

    @Synchronized
    private fun onInit(status: Int) {
        val t = tts ?: return
        if (status != TextToSpeech.SUCCESS) {
            Log.w(TAG, "text-to-speech failed to start ($status)")
            tts = null; pending.clear(); return
        }
        t.language = Locale.US
        t.setAudioAttributes(attrs)
        t.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {}
            override fun onDone(id: String?) = finished()
            @Deprecated("old API") override fun onError(id: String?) = finished()
            override fun onError(id: String?, code: Int) = finished()
        })
        ready = true
        val todo = pending.toList(); pending.clear()
        todo.forEach { (text, vol) -> speak(text, vol) }
    }

    private fun speak(text: String, volumeFloor: Int?) {
        val t = tts ?: return
        if (queued.getAndIncrement() == 0) begin(volumeFloor)
        else if (volumeFloor != null) raise(volumeFloor)
        val id = "say-" + System.nanoTime()
        if (t.speak(text, TextToSpeech.QUEUE_ADD, Bundle(), id) != TextToSpeech.SUCCESS) finished()
    }

    /** First line in the queue: duck whatever is playing and raise the volume if asked. */
    private fun begin(volumeFloor: Int?) {
        val am = app.getSystemService(AudioManager::class.java)
        val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(attrs)
            .build()
        am.requestAudioFocus(req)
        focus = req
        if (volumeFloor != null) raise(volumeFloor)
    }

    private fun raise(volumeFloor: Int) {
        val now = Volume.percent(app)
        if (now < volumeFloor) {
            if (restoreVolume == null) restoreVolume = now
            Volume.set(app, cfg, volumeFloor)
        }
    }

    @Synchronized
    private fun finished() {
        if (queued.decrementAndGet() > 0) return
        queued.set(0)
        restoreVolume?.let { Volume.set(app, cfg, it) }
        restoreVolume = null
        focus?.let { app.getSystemService(AudioManager::class.java).abandonAudioFocusRequest(it) }
        focus = null
    }

    fun release() {
        tts?.shutdown(); tts = null; ready = false
    }
}
