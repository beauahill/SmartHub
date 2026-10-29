package com.counterdisplay.launcher

import android.app.Activity
import android.app.ActivityManager
import android.app.admin.DeviceAdminReceiver
import android.app.admin.DevicePolicyManager
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.util.Log

private const val TAG = "CounterHome"

class KioskAdmin : DeviceAdminReceiver() {
    override fun onEnabled(context: Context, intent: Intent) {
        Log.i(TAG, "Device admin enabled")
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        ControlService.start(context)
        context.startActivity(
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
    }
}

/** Everything that needs device owner rights lives here so the rest of the app stays plain. */
object Kiosk {
    fun admin(ctx: Context) = ComponentName(ctx, KioskAdmin::class.java)
    fun dpm(ctx: Context) = ctx.getSystemService(DevicePolicyManager::class.java)!!
    fun isOwner(ctx: Context) = dpm(ctx).isDeviceOwnerApp(ctx.packageName)

    /** One-time policy setup each launch. Safe to call when not device owner (it does nothing). */
    fun applyPolicies(ctx: Context, cfg: Config) {
        if (!isOwner(ctx)) return
        val dpm = dpm(ctx)
        val admin = admin(ctx)
        try {
            dpm.setLockTaskPackages(admin, cfg.allowedPackages(ctx.packageName))
            // HOME lets the nav home button bring you back here from Spotify etc.
            // GLOBAL_ACTIONS keeps the power menu so you can still restart it by hand.
            dpm.setLockTaskFeatures(
                admin,
                DevicePolicyManager.LOCK_TASK_FEATURE_HOME or
                    DevicePolicyManager.LOCK_TASK_FEATURE_GLOBAL_ACTIONS
            )
            dpm.setKeyguardDisabled(admin, true)
            // Grant the camera to ourselves so Home Assistant can use it without a prompt on the tablet.
            // It still only runs when "Allow the camera" is on in Counter Home settings.
            dpm.setPermissionGrantState(admin, ctx.packageName, android.Manifest.permission.CAMERA,
                DevicePolicyManager.PERMISSION_GRANT_STATE_GRANTED)
            dpm.setStatusBarDisabled(admin, true)

            // Make this the permanent home app.
            val home = IntentFilter(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                addCategory(Intent.CATEGORY_DEFAULT)
            }
            dpm.addPersistentPreferredActivity(
                admin, home, ComponentName(ctx, MainActivity::class.java)
            )
            // Screen timeout is handled by Home Assistant over the API, so give Android a long one.
            dpm.setSystemSetting(admin, Settings.System.SCREEN_OFF_TIMEOUT, (30 * 60 * 1000).toString())
        } catch (e: Exception) {
            Log.w(TAG, "Policy setup failed", e)
        }
    }

    fun enterLock(activity: Activity, cfg: Config) {
        if (!cfg.kioskLock || !isOwner(activity)) return
        val am = activity.getSystemService(ActivityManager::class.java)
        if (am.lockTaskModeState == ActivityManager.LOCK_TASK_MODE_NONE) {
            try { activity.startLockTask() } catch (e: Exception) { Log.w(TAG, "startLockTask", e) }
        }
    }

    fun exitLock(activity: Activity) {
        try { activity.stopLockTask() } catch (_: Exception) { }
    }

    /** Turns the panel off. Needs device admin (force-lock); keyguard is disabled so wake goes straight back. */
    fun screenOff(ctx: Context): Boolean = try {
        dpm(ctx).lockNow(); true
    } catch (e: SecurityException) {
        Log.w(TAG, "lockNow needs device admin", e); false
    }

    @Suppress("DEPRECATION")
    fun screenOn(ctx: Context) {
        val pm = ctx.getSystemService(PowerManager::class.java)
        val wl = pm.newWakeLock(
            PowerManager.SCREEN_BRIGHT_WAKE_LOCK or
                PowerManager.ACQUIRE_CAUSES_WAKEUP or
                PowerManager.ON_AFTER_RELEASE,
            "CounterHome:wake"
        )
        wl.acquire(3000)
    }

    fun isScreenOn(ctx: Context) = ctx.getSystemService(PowerManager::class.java).isInteractive

    /** 0..255. Only works as device owner; returns false otherwise. */
    fun setBrightness(ctx: Context, value: Int): Boolean {
        if (!isOwner(ctx)) return false
        return try {
            val dpm = dpm(ctx); val admin = admin(ctx)
            dpm.setSystemSetting(admin, Settings.System.SCREEN_BRIGHTNESS_MODE,
                Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL.toString())
            dpm.setSystemSetting(admin, Settings.System.SCREEN_BRIGHTNESS, value.coerceIn(1, 255).toString())
            true
        } catch (e: Exception) { Log.w(TAG, "brightness", e); false }
    }

    fun setAutoBrightness(ctx: Context): Boolean {
        if (!isOwner(ctx)) return false
        return try {
            dpm(ctx).setSystemSetting(admin(ctx), Settings.System.SCREEN_BRIGHTNESS_MODE,
                Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC.toString()); true
        } catch (e: Exception) { false }
    }

    /** Undo everything so the tablet can be a normal tablet again. */
    fun release(activity: Activity) {
        exitLock(activity)
        if (!isOwner(activity)) return
        val dpm = dpm(activity); val admin = admin(activity)
        try {
            dpm.clearPackagePersistentPreferredActivities(admin, activity.packageName)
            dpm.setKeyguardDisabled(admin, false)
            dpm.setStatusBarDisabled(admin, false)
            dpm.setLockTaskPackages(admin, arrayOf())
            @Suppress("DEPRECATION")
            dpm.clearDeviceOwnerApp(activity.packageName)
        } catch (e: Exception) { Log.w(TAG, "release", e) }
    }
}

/** Tiny main-thread event bus between the HTTP service and the activity. */
object Bus {
    private val main = Handler(Looper.getMainLooper())
    @Volatile var listener: ((Command) -> Unit)? = null
    fun post(cmd: Command) = main.post { listener?.invoke(cmd) }
}

sealed class Command {
    object Home : Command()
    object Reload : Command()
    object WakeUp : Command()
    data class Ambient(val on: Boolean) : Command()
    data class Launch(val app: String) : Command()
    data class Navigate(val url: String) : Command()
    data class CameraState(val on: Boolean) : Command()
    object Assist : Command()
    object ConfigChanged : Command()
}
