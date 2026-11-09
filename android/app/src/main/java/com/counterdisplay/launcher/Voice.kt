package com.counterdisplay.launcher

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.media.ToneGenerator
import android.net.Uri
import android.os.SystemClock
import android.util.Base64
import android.util.Log
import org.json.JSONObject
import java.io.DataInputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.Socket
import java.security.SecureRandom
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Hands-free voice: the tablet as an Assist satellite.
 *
 * While running, the microphone is streamed over Home Assistant's websocket into an Assist pipeline
 * that starts at the wake-word stage. Home Assistant does everything else: it listens for "OK Nabu"
 * (the openWakeWord add-on), turns the speech into text, runs the request and answers with
 * speech, which this plays through the tablet speaker. One pipeline run handles one request, so the
 * loop simply starts another run when one ends.
 *
 * Audio only leaves the tablet while [running]; the dock shows a MIC dot the whole time.
 */
object VoiceSatellite {
    private const val TAG = "CounterHome"
    private const val SAMPLE_RATE = 16_000
    private const val CHUNK_SAMPLES = 1024                       // 64 ms per frame
    private const val WAKE_TIMEOUT_S = 3600                      // one pipeline run listens this long

    sealed class Event {
        object Started : Event()
        object Stopped : Event()
        object WakeWord : Event()                                // heard the wake word, now listening
        data class Heard(val text: String) : Event()             // what speech-to-text understood
        data class Reply(val text: String) : Event()             // what Assist answered
        data class Error(val message: String) : Event()
    }

    @Volatile var running = false; private set
    @Volatile var phase = "off"; private set                     // off, connecting, idle, listening, thinking, speaking
    @Volatile var lastError: String? = null; private set
    @Volatile var lastHeard: String? = null; private set
    @Volatile var lastReply: String? = null; private set
    @Volatile var onEvent: ((Event) -> Unit)? = null

    private var thread: Thread? = null
    private val stop = AtomicBoolean(false)
    @Volatile private var socket: Socket? = null

    fun hasPermission(ctx: Context) =
        ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    /** Starts the listening loop. Returns an error message, or null when it started (or was already running). */
    @Synchronized
    fun start(ctx: Context, cfg: Config): String? {
        if (running) return null
        if (!cfg.voiceEnabled) return "voice is turned off in Counter Home settings"
        if (cfg.haToken.isEmpty()) return "no Home Assistant token in Counter Home settings"
        if (!hasPermission(ctx)) return "microphone permission not granted"
        stop.set(false)
        running = true
        lastError = null
        val app = ctx.applicationContext
        thread = Thread({ loop(app, cfg) }, "counter-voice").apply { start() }
        onEvent?.invoke(Event.Started)
        return null
    }

    @Synchronized
    fun stop() {
        if (!running) return
        stop.set(true)
        try { socket?.close() } catch (_: Exception) { }
        thread?.interrupt()
        thread = null
        running = false
        phase = "off"
        onEvent?.invoke(Event.Stopped)
    }

    fun statusJson(): JSONObject = JSONObject()
        .put("running", running)
        .put("phase", phase)
        .put("level", if (running) level else 0)
        .put("lastHeard", lastHeard ?: "")
        .put("lastReply", lastReply ?: "")
        .put("error", lastError ?: "")

    // ---------------------------------------------------------------- the loop

    private fun loop(ctx: Context, cfg: Config) {
        var backoffMs = 2_000L
        while (!stop.get()) {
            try {
                phase = "connecting"
                runOnce(ctx, cfg)
                backoffMs = 2_000L
            } catch (e: InterruptedException) {
                break
            } catch (e: Exception) {
                if (stop.get()) break
                lastError = e.message ?: e.javaClass.simpleName
                Log.w(TAG, "voice: $lastError")
                onEvent?.invoke(Event.Error(lastError!!))
                phase = "connecting"
                try { Thread.sleep(backoffMs) } catch (_: InterruptedException) { break }
                backoffMs = (backoffMs * 2).coerceAtMost(60_000L)
            }
        }
        running = false
        phase = "off"
    }

    /** One websocket session: authenticate, then pipeline runs back to back until stopped. */
    private fun runOnce(ctx: Context, cfg: Config) {
        val ws = Ws.connect(cfg, cfg.haBase().replaceFirst("http", "ws") + "/api/websocket")
        socket = ws.socket
        try {
            // auth
            val hello = JSONObject(ws.readText())
            if (hello.optString("type") != "auth_required") throw IOException("unexpected hello ${hello.optString("type")}")
            ws.sendText(JSONObject().put("type", "auth").put("access_token", cfg.haToken).toString())
            val auth = JSONObject(ws.readText())
            if (auth.optString("type") != "auth_ok") throw IOException("Home Assistant rejected the token")

            var id = 1
            while (!stop.get()) {
                runPipeline(ctx, cfg, ws, id++)
            }
        } finally {
            socket = null
            ws.close()
        }
    }

    private fun runPipeline(ctx: Context, cfg: Config, ws: Ws, id: Int) {
        // Without "timeout" Home Assistant gives up on the wake word after 3 seconds; an hour of
        // listening per run keeps the stream open, and the loop simply starts the next run.
        val req = JSONObject()
            .put("id", id).put("type", "assist_pipeline/run")
            .put("start_stage", "wake_word").put("end_stage", "tts")
            .put("input", JSONObject().put("sample_rate", SAMPLE_RATE).put("timeout", WAKE_TIMEOUT_S))
        if (cfg.voicePipeline.isNotEmpty()) req.put("pipeline", cfg.voicePipeline)
        ws.sendText(req.toString())

        var handlerId = -1
        var recorder: AudioRecord? = null
        var audioThread: Thread? = null
        val streaming = AtomicBoolean(false)
        var ttsUrl: String? = null
        var detected = false
        val startedAt = SystemClock.uptimeMillis()
        try {
            while (!stop.get()) {
                val msg = JSONObject(ws.readText())
                if (msg.optInt("id", -1) != id) continue
                when (msg.optString("type")) {
                    "result" -> if (!msg.optBoolean("success")) {
                        throw IOException("pipeline refused: " + msg.optJSONObject("error")?.optString("message"))
                    }
                    "event" -> {
                        val ev = msg.getJSONObject("event")
                        val data = ev.optJSONObject("data") ?: JSONObject()
                        when (ev.optString("type")) {
                            "run-start" -> {
                                handlerId = data.optJSONObject("runner_data")?.optInt("stt_binary_handler_id", -1) ?: -1
                                if (handlerId < 0) throw IOException("pipeline gave no audio handler")
                                phase = "idle"
                                recorder = openRecorder()
                                streaming.set(true)
                                val rec = recorder!!; val hid = handlerId
                                audioThread = Thread({ pump(rec, ws, hid, streaming) }, "counter-mic").apply { start() }
                            }
                            "wake_word-end" -> {
                                // An empty output means the wake-word stream ended without a detection
                                // (the add-on restarted, say); the run ends and the loop starts another.
                                val out = data.optJSONObject("wake_word_output")
                                if (out != null && out.has("wake_word_id")) {
                                    detected = true
                                    phase = "listening"
                                    Log.i(TAG, "voice: wake word ${out.optString("wake_word_id")}")
                                    chime(ctx)
                                    onEvent?.invoke(Event.WakeWord)
                                }
                            }
                            "stt-end" -> {
                                streaming.set(false)                 // Home Assistant has what it needs
                                phase = "thinking"
                                val text = data.optJSONObject("stt_output")?.optString("text") ?: ""
                                lastHeard = text
                                Log.i(TAG, "voice: heard \"$text\"")
                                onEvent?.invoke(Event.Heard(text))
                            }
                            "intent-end" -> {
                                val speech = data.optJSONObject("intent_output")?.optJSONObject("response")
                                    ?.optJSONObject("speech")?.optJSONObject("plain")?.optString("speech") ?: ""
                                lastReply = speech
                                Log.i(TAG, "voice: reply \"$speech\"")
                                onEvent?.invoke(Event.Reply(speech))
                            }
                            "tts-end" -> ttsUrl = data.optJSONObject("tts_output")?.optString("url")
                            "error" -> {
                                val code = data.optString("code")
                                // The wake-word stage times out after a few minutes of silence by design.
                                if (code == "wake-word-timeout") return
                                throw IOException("$code: ${data.optString("message")}")
                            }
                            "run-end" -> {
                                streaming.set(false)
                                if (detected) ttsUrl?.takeIf { it.isNotEmpty() }?.let { speak(ctx, cfg, it) }
                                // A run that dies within seconds means the wake-word service is down;
                                // don't hammer Home Assistant with new runs.
                                else if (SystemClock.uptimeMillis() - startedAt < 5_000) Thread.sleep(3_000)
                                return
                            }
                        }
                    }
                }
            }
        } finally {
            streaming.set(false)
            audioThread?.join(1500)
            try { recorder?.stop() } catch (_: Exception) { }
            recorder?.release()
            if (!stop.get()) phase = "idle"
        }
    }

    // ---------------------------------------------------------------- audio

    private fun openRecorder(): AudioRecord {
        val min = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, (min * 4).coerceAtLeast(CHUNK_SAMPLES * 2 * 4))
        } catch (e: SecurityException) { throw IOException("microphone permission not granted") }
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); throw IOException("microphone unavailable") }
        rec.startRecording()
        return rec
    }

    /** Reads PCM from the microphone and sends it as binary frames: one handler-id byte, then samples. */
    private fun pump(rec: AudioRecord, ws: Ws, handlerId: Int, streaming: AtomicBoolean) {
        val buf = ByteArray(1 + CHUNK_SAMPLES * 2)
        buf[0] = handlerId.toByte()
        try {
            while (streaming.get() && !stop.get()) {
                val n = rec.read(buf, 1, CHUNK_SAMPLES * 2)
                if (n <= 0) { Thread.sleep(20); continue }
                measure(buf, 1, n)
                ws.sendBinary(buf, 1 + n)
            }
        } catch (e: Exception) {
            if (streaming.get() && !stop.get()) Log.w(TAG, "mic stream ended: ${e.message}")
        }
    }

    /** Microphone level for /status: the loudest 64 ms chunk of the last second, 0-100 (RMS, dB scale). */
    @Volatile var level = 0; private set
    private var peak = 0.0
    private var peakAt = 0L

    private fun measure(buf: ByteArray, off: Int, len: Int) {
        var sum = 0.0
        var i = off
        while (i + 1 < off + len) {
            val s = ((buf[i + 1].toInt() shl 8) or (buf[i].toInt() and 0xFF)).toShort().toDouble()
            sum += s * s; i += 2
        }
        val rms = Math.sqrt(sum / (len / 2).coerceAtLeast(1))
        val db = if (rms < 1) -96.0 else 20 * Math.log10(rms / 32768.0)      // -96..0 dBFS
        val now = SystemClock.uptimeMillis()
        if (db > peak || now - peakAt > 1000) { peak = db; peakAt = now }
        level = ((peak + 96) / 96 * 100).toInt().coerceIn(0, 100)
    }

    private fun chime(ctx: Context) {
        try {
            ToneGenerator(AudioManager.STREAM_MUSIC, 70).apply {
                startTone(ToneGenerator.TONE_PROP_BEEP, 120)
                android.os.Handler(ctx.mainLooper).postDelayed({ release() }, 400)
            }
        } catch (_: Exception) { }
    }

    /** Downloads the answer (so the certificate rule applies) and plays it, ducking other audio. */
    private fun speak(ctx: Context, cfg: Config, url: String) {
        phase = "speaking"
        val am = ctx.getSystemService(AudioManager::class.java)
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ASSISTANT)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
        val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(attrs).build()
        var file: File? = null
        try {
            val full = if (url.startsWith("http")) url else cfg.haBase() + url
            val bytes = Net.fetch(cfg, full, maxBytes = 8 shl 20)
            file = File.createTempFile("tts", ".audio", ctx.cacheDir).apply { writeBytes(bytes) }
            am.requestAudioFocus(focus)
            val done = CountDownLatch(1)
            val mp = MediaPlayer().apply {
                setAudioAttributes(attrs)
                setDataSource(file.absolutePath)
                setOnCompletionListener { done.countDown() }
                setOnErrorListener { _, _, _ -> done.countDown(); true }
                prepare()
                start()
            }
            done.await(30, TimeUnit.SECONDS)
            mp.release()
        } catch (e: Exception) {
            Log.w(TAG, "tts playback: ${e.message}")
        } finally {
            am.abandonAudioFocusRequest(focus)
            file?.delete()
            if (!stop.get()) phase = "idle"
        }
    }

    // ---------------------------------------------------------------- websocket

    /** Just enough of RFC 6455 for Home Assistant: text and binary frames, ping/pong, close. */
    class Ws private constructor(val socket: Socket, private val input: DataInputStream, private val output: OutputStream) {
        private val rnd = SecureRandom()

        fun sendText(s: String) = send(0x1, s.toByteArray(Charsets.UTF_8), s.length.let { s.toByteArray(Charsets.UTF_8).size })
        fun sendBinary(b: ByteArray, len: Int) = send(0x2, b, len)

        @Synchronized
        private fun send(opcode: Int, payload: ByteArray, len: Int) {
            val head = java.io.ByteArrayOutputStream()
            head.write(0x80 or opcode)
            when {
                len < 126 -> head.write(0x80 or len)
                len < 65536 -> { head.write(0x80 or 126); head.write(len shr 8); head.write(len and 0xFF) }
                else -> { head.write(0x80 or 127); for (i in 7 downTo 0) head.write(((len.toLong() shr (8 * i)) and 0xFF).toInt()) }
            }
            val mask = ByteArray(4).also { rnd.nextBytes(it) }
            head.write(mask)
            val masked = ByteArray(len)
            for (i in 0 until len) masked[i] = (payload[i].toInt() xor mask[i and 3].toInt()).toByte()
            output.write(head.toByteArray()); output.write(masked); output.flush()
        }

        /** Next text message (pings are answered, binary frames skipped). Throws when the socket closes. */
        fun readText(): String {
            val acc = java.io.ByteArrayOutputStream()
            while (true) {
                val b0 = input.readUnsignedByte(); val b1 = input.readUnsignedByte()
                val fin = b0 and 0x80 != 0; val op = b0 and 0x0F
                var len = (b1 and 0x7F).toLong()
                if (len == 126L) len = input.readUnsignedShort().toLong()
                else if (len == 127L) len = input.readLong()
                if (len > 64L shl 20) throw IOException("frame too large")
                val mask = if (b1 and 0x80 != 0) ByteArray(4).also { input.readFully(it) } else null
                val data = ByteArray(len.toInt()).also { input.readFully(it) }
                mask?.let { for (i in data.indices) data[i] = (data[i].toInt() xor it[i and 3].toInt()).toByte() }
                when (op) {
                    0x8 -> throw IOException("websocket closed by Home Assistant")
                    0x9 -> send(0xA, data, data.size)
                    0xA, 0x2 -> Unit
                    0x1, 0x0 -> { acc.write(data); if (fin) return acc.toString("UTF-8") }
                }
            }
        }

        fun close() { try { send(0x8, ByteArray(0), 0) } catch (_: Exception) { }; try { socket.close() } catch (_: Exception) { } }

        companion object {
            fun connect(cfg: Config, url: String): Ws {
                val u = Uri.parse(url)
                val tls = u.scheme == "wss"
                val host = u.host ?: throw IOException("bad websocket url")
                val port = if (u.port > 0) u.port else if (tls) 443 else 80
                val sock = Net.socket(cfg, host, port, tls)
                sock.soTimeout = 0
                val out = sock.getOutputStream()
                val key = Base64.encodeToString(ByteArray(16).also { SecureRandom().nextBytes(it) }, Base64.NO_WRAP)
                out.write(("GET ${u.encodedPath} HTTP/1.1\r\nHost: $host:$port\r\nUpgrade: websocket\r\n" +
                    "Connection: Upgrade\r\nSec-WebSocket-Key: $key\r\nSec-WebSocket-Version: 13\r\n\r\n").toByteArray())
                out.flush()
                val input = DataInputStream(java.io.BufferedInputStream(sock.getInputStream()))
                val status = readLine(input)
                if (!status.contains(" 101 ")) throw IOException("websocket handshake failed: $status")
                while (readLine(input).isNotEmpty()) { /* headers */ }
                return Ws(sock, input, out)
            }

            private fun readLine(s: InputStream): String {
                val sb = StringBuilder()
                while (true) {
                    val c = s.read()
                    if (c < 0) throw IOException("connection closed during handshake")
                    if (c == '\n'.code) return sb.toString().trimEnd('\r')
                    sb.append(c.toChar())
                    if (sb.length > 8192) throw IOException("header too long")
                }
            }
        }
    }
}
