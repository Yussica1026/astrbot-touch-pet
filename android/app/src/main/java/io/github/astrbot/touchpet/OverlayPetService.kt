package io.github.astrbot.touchpet

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import android.widget.Toast
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.math.hypot

class OverlayPetService : Service() {
    companion object {
        const val ACTION_STOP = "io.github.astrbot.touchpet.STOP"
        private const val CHANNEL_ID = "touch_pet_overlay"
        private const val NOTIFICATION_ID = 8107
    }

    private lateinit var windowManager: WindowManager
    private var petView: ImageView? = null
    private var params: WindowManager.LayoutParams? = null
    private val handler = Handler(Looper.getMainLooper())
    private val network = Executors.newSingleThreadExecutor()
    private val prefs by lazy { getSharedPreferences("touch_pet", MODE_PRIVATE) }
    private var lastTapAt = 0L
    private var singleTap: Runnable? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        if (Settings.canDrawOverlays(this)) showPet() else stopSelf()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (petView == null && Settings.canDrawOverlays(this)) showPet()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        petView?.let { runCatching { windowManager.removeView(it) } }
        petView = null
        network.shutdownNow()
        super.onDestroy()
    }

    private fun showPet() {
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        val size = (150 * resources.displayMetrics.density).toInt()
        params = WindowManager.LayoutParams(
            size,
            size,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = prefs.getInt("overlay_x", 40)
            y = prefs.getInt("overlay_y", 180)
        }
        petView = ImageView(this).apply {
            setImageResource(R.drawable.pet_placeholder)
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "可拖动的悬浮桌宠"
            setOnTouchListener(PetTouchListener())
        }
        windowManager.addView(petView, params)
    }

    private inner class PetTouchListener : View.OnTouchListener {
        private var downX = 0f
        private var downY = 0f
        private var startX = 0
        private var startY = 0
        private var dragging = false
        private var longPressed = false
        private val longPress = Runnable {
            if (!dragging) {
                longPressed = true
                sendSignal("long_press")
            }
        }

        override fun onTouch(view: View, event: MotionEvent): Boolean {
            val layout = params ?: return false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX
                    downY = event.rawY
                    startX = layout.x
                    startY = layout.y
                    dragging = false
                    longPressed = false
                    handler.postDelayed(longPress, 600)
                    return true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downX
                    val dy = event.rawY - downY
                    if (!dragging && hypot(dx.toDouble(), dy.toDouble()) > 12) {
                        dragging = true
                        handler.removeCallbacks(longPress)
                    }
                    if (dragging) {
                        val maxX = (resources.displayMetrics.widthPixels - layout.width).coerceAtLeast(0)
                        val maxY = (resources.displayMetrics.heightPixels - layout.height).coerceAtLeast(0)
                        layout.x = (startX + dx.toInt()).coerceIn(0, maxX)
                        layout.y = (startY + dy.toInt()).coerceIn(0, maxY)
                        windowManager.updateViewLayout(view, layout)
                    }
                    return true
                }
                MotionEvent.ACTION_UP -> {
                    handler.removeCallbacks(longPress)
                    if (dragging) {
                        prefs.edit().putInt("overlay_x", layout.x).putInt("overlay_y", layout.y).apply()
                        sendSignal("drag")
                    } else if (!longPressed) {
                        handleTap()
                    }
                    return true
                }
                MotionEvent.ACTION_CANCEL -> {
                    handler.removeCallbacks(longPress)
                    return true
                }
            }
            return false
        }
    }

    private fun handleTap() {
        val now = System.currentTimeMillis()
        if (now - lastTapAt <= 280) {
            singleTap?.let(handler::removeCallbacks)
            singleTap = null
            lastTapAt = 0
            sendSignal("double_tap")
        } else {
            lastTapAt = now
            singleTap = Runnable {
                if (lastTapAt == now) {
                    lastTapAt = 0
                    sendSignal("tap")
                }
            }.also { handler.postDelayed(it, 285) }
        }
    }

    private fun sendSignal(gesture: String) {
        val base = prefs.getString("server_url", "")?.trimEnd('/') ?: return
        val token = prefs.getString("pair_token", "") ?: return
        network.execute {
            runCatching {
                val connection = URL("$base/api/touch").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 10_000
                connection.readTimeout = 120_000
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $token")
                val body = JSONObject()
                    .put("gesture", gesture)
                    .put("request_id", UUID.randomUUID().toString())
                    .toString()
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                val status = connection.responseCode
                connection.disconnect()
                if (status !in 200..299) error("HTTP $status")
            }.onFailure {
                handler.post { Toast.makeText(this, "触摸信号发送失败", Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "悬浮桌宠", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun buildNotification(): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stop = PendingIntent.getService(
            this, 1, Intent(this, OverlayPetService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.pet_placeholder)
            .setContentTitle("AstrBot Touch Pet 正在运行")
            .setContentText("桌宠可以显示在其他应用上层")
            .setContentIntent(open)
            .addAction(Notification.Action.Builder(null, "停止", stop).build())
            .setOngoing(true)
            .build()
    }
}

