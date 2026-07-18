package io.github.astrbot.touchpet

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("touch_pet", MODE_PRIVATE) }
    private lateinit var serverInput: EditText
    private lateinit var tokenInput: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildUi())
    }

    private fun buildUi(): LinearLayout {
        val pad = (20 * resources.displayMetrics.density).toInt()
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)

            addView(TextView(context).apply {
                text = "AstrBot Touch Pet"
                textSize = 26f
            })
            addView(TextView(context).apply {
                text = "配置服务器后，允许桌宠显示在其他应用上层。"
                textSize = 15f
                setPadding(0, pad / 2, 0, pad)
            })

            serverInput = EditText(context).apply {
                hint = "https://example.com:8443"
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
                setText(prefs.getString("server_url", ""))
            }
            addView(serverInput, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

            tokenInput = EditText(context).apply {
                hint = "桌宠配对令牌"
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                setText(prefs.getString("pair_token", ""))
            }
            addView(tokenInput, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

            addView(Button(context).apply {
                text = "保存并显示悬浮桌宠"
                setOnClickListener { saveAndStart() }
            }, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

            addView(Button(context).apply {
                text = "隐藏并停止桌宠"
                setOnClickListener {
                    startService(Intent(context, OverlayPetService::class.java).setAction(OverlayPetService.ACTION_STOP))
                }
            }, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

            addView(TextView(context).apply {
                text = "提示：HTTP 仅适合局域网或短期联调。公网部署请使用 HTTPS。"
                textSize = 13f
                setPadding(0, pad, 0, 0)
            })
        }
    }

    private fun saveAndStart() {
        val server = serverInput.text.toString().trim().trimEnd('/')
        val token = tokenInput.text.toString().trim()
        if (!(server.startsWith("https://") || server.startsWith("http://")) || token.length < 16) {
            Toast.makeText(this, "请填写完整服务器地址和配对令牌", Toast.LENGTH_SHORT).show()
            return
        }
        prefs.edit().putString("server_url", server).putString("pair_token", token).apply()

        if (!Settings.canDrawOverlays(this)) {
            val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
            startActivity(intent)
            Toast.makeText(this, "授权后返回，再点一次显示桌宠", Toast.LENGTH_LONG).show()
            return
        }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 33)
        }
        startForegroundService(Intent(this, OverlayPetService::class.java))
        Toast.makeText(this, "桌宠已启动", Toast.LENGTH_SHORT).show()
    }
}

