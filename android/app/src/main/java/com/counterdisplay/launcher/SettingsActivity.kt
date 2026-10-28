package com.counterdisplay.launcher

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/** Plain form for the settings. Reached by holding the dock clock for 3 s and entering the PIN. */
class SettingsActivity : Activity() {

    private lateinit var cfg: Config

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = Config(this)

        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(28), dp(20), dp(28), dp(40))
            setBackgroundColor(Color.parseColor("#14171B"))
        }

        val ip = ControlService.ipAddress(this) ?: "no network"
        val owner = Kiosk.isOwner(this)
        col.addView(label("Counter Home ${BuildConfigShim.VERSION}", 24f, true))
        col.addView(label(
            "IP $ip  |  API port ${cfg.port}  |  device owner: ${if (owner) "yes" else "no (run setup.sh)"}",
            14f, false, "#9AA4AE"))

        val url = field(col, "Home Assistant dashboard URL", cfg.haUrl)
        val tiles = field(col, "Dock tiles (JSON)", cfg.tilesJson, multiline = true, mono = true)
        val dock = field(col, "Dock side: right, left or bottom", cfg.dockSide)
        val port = field(col, "API port", cfg.port.toString(), number = true)
        val token = field(col, "API token (Home Assistant needs this)", cfg.token, mono = true)
        val pin = field(col, "Settings PIN", cfg.pin, number = true)
        val maxVol = field(col, "Max media volume, % (protects the speakers; 100 = no cap)", cfg.maxVolume.toString(), number = true)
        val lock = CheckBox(this).apply {
            text = "Kiosk lock (pin the launcher; needs device owner)"
            isChecked = cfg.kioskLock
            setTextColor(Color.WHITE)
        }
        col.addView(lock)

        col.addView(button("Save") {
            try {
                val oldPort = cfg.port
                cfg.tilesJson = tiles.text.toString()
                cfg.haUrl = url.text.toString()
                cfg.dockSide = dock.text.toString().trim().lowercase().takeIf { it in setOf("left", "right", "bottom") } ?: "right"
                cfg.port = port.text.toString().toIntOrNull() ?: 2323
                cfg.token = token.text.toString()
                cfg.pin = pin.text.toString().ifBlank { "2580" }
                cfg.kioskLock = lock.isChecked
                cfg.maxVolume = maxVol.text.toString().toIntOrNull() ?: Config.DEFAULT_MAX_VOLUME
                Volume.enforce(this, cfg)
                if (cfg.port != oldPort) ControlService.restartServer(this)
                Bus.post(Command.ConfigChanged)
                toast("Saved")
                finish()
            } catch (e: Exception) {
                toast("Tiles JSON is invalid: ${e.message}")
            }
        })

        col.addView(button(if (State.kioskPaused) "Resume kiosk lock" else "Pause kiosk lock and open Android settings") {
            if (State.kioskPaused) {
                State.kioskPaused = false
                finish()
            } else {
                State.kioskPaused = true
                Kiosk.exitLock(this)
                startActivity(Intent(Settings.ACTION_SETTINGS))
            }
        })

        col.addView(button("Release device owner (turns this back into a normal tablet)") {
            AlertDialog.Builder(this)
                .setMessage("Remove kiosk control? You'll need setup.sh and a factory reset to make it device owner again.")
                .setPositiveButton("Release") { _, _ ->
                    State.kioskPaused = true
                    Kiosk.release(this)
                    toast("Released. Pick a different home app in Android settings if you want one.")
                    finish()
                }
                .setNegativeButton("Cancel", null)
                .show()
        }.apply { setTextColor(Color.parseColor("#FF8A80")) })

        col.addView(button("Close") { finish() })

        setContentView(ScrollView(this).apply { addView(col) })
    }

    private fun field(
        parent: LinearLayout, title: String, value: String,
        multiline: Boolean = false, mono: Boolean = false, number: Boolean = false,
    ): EditText {
        parent.addView(label(title, 14f, true, "#C8CDD2").apply { setPadding(0, dp(18), 0, dp(4)) })
        val e = EditText(this).apply {
            setText(value)
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.parseColor("#22272E"))
            setPadding(dp(12), dp(10), dp(12), dp(10))
            if (mono) typeface = Typeface.MONOSPACE
            inputType = when {
                number -> InputType.TYPE_CLASS_NUMBER
                multiline -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
                else -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or InputType.TYPE_TEXT_VARIATION_URI
            }
            if (multiline) { minLines = 6; textSize = 13f }
        }
        parent.addView(e, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        return e
    }

    private fun label(text: String, size: Float, bold: Boolean, color: String = "#FFFFFF") = TextView(this).apply {
        this.text = text
        textSize = size
        setTextColor(Color.parseColor(color))
        if (bold) typeface = Typeface.DEFAULT_BOLD
    }

    private fun button(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        isAllCaps = false
        setOnClickListener { onClick() }
        layoutParams = LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(14) }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_LONG).show()

}
