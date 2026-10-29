package com.counterdisplay.launcher

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.Rect
import android.graphics.YuvImage
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.display.DisplayManager
import android.media.Image
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.Log
import android.util.Size
import android.view.Display
import android.view.Surface
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * The tablet camera as a security camera for Home Assistant.
 *
 * Camera2 delivers YUV frames at the configured rate; each one is compressed to JPEG and kept as the
 * latest frame. ControlService serves it as /camera.jpg and as an MJPEG stream at /camera.mjpeg.
 * The camera runs only while Home Assistant has turned it on (optionally with an auto-off timer), and
 * only if it is allowed in the on-device settings. Requests while it is off get an error instead of
 * switching it on, so a dashboard refreshing the camera picture can never wake it.
 */
object CameraStreamer {
    private const val TAG = "CounterHome"

    data class Frame(val jpeg: ByteArray, val atMs: Long, val width: Int, val height: Int)

    private val lock = ReentrantLock()
    private val newFrame = lock.newCondition()
    @Volatile private var latest: Frame? = null

    private var thread: HandlerThread? = null
    private var handler: Handler? = null
    private var device: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var reader: ImageReader? = null
    private var rotation = 0
    private var frameIntervalMs = 200L
    private var lastFrameMs = 0L
    private var jpegQuality = 70
    private val main = Handler(android.os.Looper.getMainLooper())
    private val autoOff = Runnable { Log.i(TAG, "camera auto-off"); stop() }

    @Volatile var running = false; private set
    @Volatile var facing = "front"; private set
    @Volatile var size: Size? = null; private set
    @Volatile var error: String? = null; private set
    @Volatile var offAtMs = 0L; private set          // uptime when the auto-off fires, 0 = none
    /** Called on every on/off change, so the launcher can show or hide its camera indicator. */
    @Volatile var onStateChanged: ((Boolean) -> Unit)? = null

    fun hasPermission(ctx: Context) =
        ctx.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    /** Turns the camera on (or changes its auto-off). [minutes] > 0 turns it off again after that long. */
    fun start(ctx: Context, cfg: Config, minutes: Int = 0): String? = lock.withLock {
        if (!cfg.cameraAllowed) return "camera is turned off in Counter Home settings"
        if (!hasPermission(ctx)) return "camera permission not granted"
        main.removeCallbacks(autoOff)
        offAtMs = 0L
        if (minutes > 0) {
            offAtMs = SystemClock.uptimeMillis() + minutes * 60_000L
            main.postAtTime(autoOff, offAtMs)
        }
        if (running && facing == cfg.cameraFacing) return null
        if (running) stopLocked()
        val err = open(ctx, cfg)
        if (err == null) onStateChanged?.invoke(true)
        err
    }

    fun stop() {
        val was = lock.withLock {
            main.removeCallbacks(autoOff)
            offAtMs = 0L
            val r = running
            stopLocked()
            r
        }
        if (was) onStateChanged?.invoke(false)
    }

    /** The newest frame, or null while the camera is off or before the first frame arrives. */
    fun latestFrame(maxAgeMs: Long = 3000): Frame? {
        val f = latest ?: return null
        return if (running && SystemClock.uptimeMillis() - f.atMs <= maxAgeMs) f else null
    }

    /** Waits for a frame captured after [sinceMs] (uptime). Returns null if the camera stops. */
    fun awaitFrame(sinceMs: Long, timeoutMs: Long): Frame? = lock.withLock {
        var left = TimeUnit.MILLISECONDS.toNanos(timeoutMs)
        while ((latest?.atMs ?: 0L) <= sinceMs && left > 0 && running) left = newFrame.awaitNanos(left)
        latest?.takeIf { running && it.atMs > sinceMs }
    }

    fun statusJson(): org.json.JSONObject = org.json.JSONObject()
        .put("running", running)
        .put("facing", facing)
        .put("width", size?.width ?: 0)
        .put("height", size?.height ?: 0)
        .put("frameAgeMs", latest?.let { if (running) SystemClock.uptimeMillis() - it.atMs else -1L } ?: -1L)
        .put("offInSeconds", if (offAtMs > 0) (offAtMs - SystemClock.uptimeMillis()).coerceAtLeast(0) / 1000 else 0)
        .put("error", error ?: "")

    // ------------------------------------------------------------------------------------------

    @SuppressLint("MissingPermission")
    private fun open(ctx: Context, cfg: Config): String? {
        val cm = ctx.getSystemService(CameraManager::class.java)
        val want = if (cfg.cameraFacing == "back") CameraCharacteristics.LENS_FACING_BACK
                   else CameraCharacteristics.LENS_FACING_FRONT
        val id = cm.cameraIdList.firstOrNull {
            cm.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == want
        } ?: return "no ${cfg.cameraFacing} camera"
        val ch = cm.getCameraCharacteristics(id)
        val map = ch.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP) ?: return "camera has no stream map"
        val sizes = map.getOutputSizes(ImageFormat.YUV_420_888) ?: return "camera has no YUV output"
        val pick = pickSize(sizes, cfg.cameraWidth)
        val sensor = ch.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0
        rotation = if (cfg.cameraRotation >= 0) cfg.cameraRotation else autoRotation(ctx, sensor, want)
        frameIntervalMs = (1000L / cfg.cameraFps.coerceIn(1, 15))
        lastFrameMs = 0L
        jpegQuality = cfg.cameraQuality.coerceIn(30, 95)
        facing = cfg.cameraFacing
        size = pick
        error = null

        val t = HandlerThread("counter-camera").apply { start() }
        val h = Handler(t.looper)
        thread = t; handler = h
        val r = ImageReader.newInstance(pick.width, pick.height, ImageFormat.YUV_420_888, 2)
        r.setOnImageAvailableListener({ onImage(it) }, h)
        reader = r
        running = true
        try {
            cm.openCamera(id, object : CameraDevice.StateCallback() {
                override fun onOpened(d: CameraDevice) {
                    device = d
                    @Suppress("DEPRECATION")
                    d.createCaptureSession(listOf(r.surface), object : CameraCaptureSession.StateCallback() {
                        override fun onConfigured(s: CameraCaptureSession) {
                            session = s
                            try {
                                val req = d.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
                                    addTarget(r.surface)
                                    set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                                }
                                s.setRepeatingRequest(req.build(), null, h)
                                Log.i(TAG, "camera $id streaming ${pick.width}x${pick.height}, rotation $rotation")
                            } catch (e: Exception) { fail("capture: ${e.message}") }
                        }
                        override fun onConfigureFailed(s: CameraCaptureSession) { fail("session configure failed") }
                    }, h)
                }
                override fun onDisconnected(d: CameraDevice) { fail("camera disconnected (another app took it?)") }
                override fun onError(d: CameraDevice, code: Int) { fail("camera error $code") }
            }, h)
        } catch (e: Exception) {
            stopLocked()
            return "open failed: ${e.message}"
        }
        return null
    }

    private fun fail(msg: String) {
        Log.w(TAG, msg)
        lock.withLock { error = msg; stopLocked(keepError = true) }
        main.removeCallbacks(autoOff)
        onStateChanged?.invoke(false)
    }

    private fun stopLocked(keepError: Boolean = false) {
        try { session?.close() } catch (_: Exception) { }
        try { device?.close() } catch (_: Exception) { }
        try { reader?.close() } catch (_: Exception) { }
        thread?.quitSafely()
        session = null; device = null; reader = null; thread = null; handler = null
        if (!keepError) error = null
        latest = null                         // never serve a frame from an earlier session
        running = false
        newFrame.signalAll()
    }

    private fun onImage(r: ImageReader) {
        val img = try { r.acquireLatestImage() } catch (e: Exception) { null } ?: return
        try {
            val now = SystemClock.uptimeMillis()
            if (now - lastFrameMs < frameIntervalMs) return
            lastFrameMs = now
            val jpeg = encode(img)
            val w = if (rotation % 180 == 0) img.width else img.height
            val hh = if (rotation % 180 == 0) img.height else img.width
            lock.withLock {
                latest = Frame(jpeg, now, w, hh)
                newFrame.signalAll()
            }
        } catch (e: Exception) {
            Log.w(TAG, "frame encode failed: ${e.message}")
        } finally {
            img.close()
        }
    }

    private fun encode(img: Image): ByteArray {
        val nv21 = toNv21(img)
        val out = ByteArrayOutputStream(img.width * img.height / 4)
        YuvImage(nv21, ImageFormat.NV21, img.width, img.height, null)
            .compressToJpeg(Rect(0, 0, img.width, img.height), jpegQuality, out)
        if (rotation == 0) return out.toByteArray()
        val bmp = BitmapFactory.decodeByteArray(out.toByteArray(), 0, out.size())
        val rotated = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height,
            Matrix().apply { postRotate(rotation.toFloat()) }, true)
        bmp.recycle()
        val out2 = ByteArrayOutputStream(out.size())
        rotated.compress(Bitmap.CompressFormat.JPEG, jpegQuality, out2)
        rotated.recycle()
        return out2.toByteArray()
    }

    /** YUV_420_888 to NV21, honoring row and pixel strides (they differ between devices). */
    private fun toNv21(img: Image): ByteArray {
        val w = img.width; val h = img.height
        val out = ByteArray(w * h * 3 / 2)
        val yp = img.planes[0]; val yb = yp.buffer
        var pos = 0
        if (yp.pixelStride == 1 && yp.rowStride == w) {
            yb.position(0); yb.get(out, 0, w * h); pos = w * h
        } else {
            for (row in 0 until h) {
                val base = row * yp.rowStride
                for (col in 0 until w) out[pos++] = yb.get(base + col * yp.pixelStride)
            }
        }
        val up = img.planes[1]; val vp = img.planes[2]
        val ub = up.buffer; val vb = vp.buffer
        for (row in 0 until h / 2) {
            val ubase = row * up.rowStride; val vbase = row * vp.rowStride
            for (col in 0 until w / 2) {
                out[pos++] = vb.get(vbase + col * vp.pixelStride)
                out[pos++] = ub.get(ubase + col * up.pixelStride)
            }
        }
        return out
    }

    /** Largest size no wider than [maxWidth], preferring 16:9, then 4:3. */
    private fun pickSize(sizes: Array<Size>, maxWidth: Int): Size {
        fun ok(s: Size) = s.width <= maxWidth
        for (ratio in listOf(16.0 / 9.0, 4.0 / 3.0)) {
            sizes.filter { ok(it) && Math.abs(it.width.toDouble() / it.height - ratio) < 0.02 }
                .maxByOrNull { it.width }?.let { return it }
        }
        return sizes.filter(::ok).maxByOrNull { it.width } ?: sizes.minByOrNull { it.width }!!
    }

    /** Rotation that makes the JPEG upright for the current display orientation. */
    private fun autoRotation(ctx: Context, sensor: Int, lensFacing: Int): Int {
        val display = ctx.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
        val deg = when (display?.rotation) {
            Surface.ROTATION_90 -> 90; Surface.ROTATION_180 -> 180; Surface.ROTATION_270 -> 270; else -> 0
        }
        return if (lensFacing == CameraCharacteristics.LENS_FACING_FRONT) (sensor + deg) % 360
               else (sensor - deg + 360) % 360
    }
}
